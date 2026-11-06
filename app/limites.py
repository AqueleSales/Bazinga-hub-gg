"""Limite de requisições (Rodada 35, ampliado na Rodada 38): o que a auditoria da Rodada 30 deixou aberto. As rotas que gastam serviço de fora (Cloudinary,
Giphy, o Pillow do servidor, o download de imagem) e as de login não tinham teto por pessoa: um script podia martelar `/api/upload` ou o login.

Como funciona: janela deslizante em memória (um processo só: o app roda com `-w 1`), uma lista de horários por chave.
- Pessoa logada: a chave é a PESSOA (`u<id>`, precisa e impossível de forjar: o cookie é assinado).
- Sem login: a chave é o IP. **No Render o `X-Forwarded-For` que o cliente manda NÃO é descartado: o proxy só ANEXA o IP dele no fim da lista**,
  então o primeiro endereço é forjável (um script troca o cabeçalho a cada pedido e foge do limite). Por isso o pedido sem login passa por DUAS
  chaves: a ponta esquerda (o IP "de verdade" na maioria dos casos, apertada: é por onde se limita cada pessoa) e a ponta DIREITA (a que o nosso
  proxy anexou: não se forja, mas pode ser a do próprio proxy, compartilhada por todos, por isso o teto dela é `FATOR_BORDA` vezes maior).
  Quem forja a esquerda ainda esbarra na direita.

Ordem das regras: as específicas (`REGRAS`) valem primeiro; o que sobrar cai no teto GERAL (pessoa logada: `GERAL_PESSOA` por minuto; anônimo:
`GERAL_IP`). Estourou: 429 com `Retry-After` e uma mensagem em português (JSON em `/api/*`). Desligar tudo: `LIMITE_REQUISICOES=0`.
Os freios por funcionalidade (`/api/meus-dados` a cada 20 s, o recorte de GIF a cada 1,5 s, etc.) continuam valendo; este é o teto GERAL por cima deles.
O teto de EVENTOS do socket (flood de mensagem, conexões) mora em `app/seguranca.py` e usa as mesmas funções daqui.
"""
import ipaddress
import os
import threading
import time
from collections import deque

from flask import request, session, jsonify, make_response

# (método ou '*', prefixo do caminho, requisições, janela em segundos, rótulo). A primeira regra que casa vale.
REGRAS = (
    ('POST', '/api/upload', 40, 60, 'envio de arquivos'),
    ('POST', '/api/gif/recortar', 20, 60, 'recorte de animação'),
    ('POST', '/api/video/animar', 12, 60, 'conversão de vídeo'),
    ('POST', '/api/imagem/importar', 15, 60, 'importação de imagem'),
    ('POST', '/api/conexoes/importar-cv', 8, 60, 'leitura de currículo'),
    ('POST', '/estudio/api/arquivos', 30, 60, 'envio de arquivos do Estúdio'),
    ('GET', '/api/gifs', 60, 60, 'busca de GIF'),
    ('GET', '/api/localizacao/ip', 30, 60, 'localização por IP'),
    ('GET', '/api/meus-dados', 6, 60, 'cópia dos dados'),
    ('GET', '/api/convite/', 80, 60, 'consulta de convite'),
    ('*', '/auth/login', 20, 60, 'login'),
    ('*', '/auth/callback', 20, 60, 'login'),
    ('*', '/auth/desktop/', 30, 60, 'login do app'),
    ('POST', '/webhooks/', 120, 60, 'aviso de pagamento'),
    ('*', '/static/', 3000, 60, 'arquivos do app'),
)

GERAL_PESSOA = 900            # qualquer outro pedido de quem está logado, por minuto (o app conversa por socket: 15/s é muito)
GERAL_IP = 300                # qualquer outro pedido de quem NÃO está logado (as páginas de entrada, manifesto, termos), por minuto
FATOR_BORDA = 10              # o balde da ponta direita do X-Forwarded-For é tantas vezes maior que o da esquerda

_IDX_GERAL_PESSOA = -1
_IDX_GERAL_IP = -2
_IDX_CONEXAO_SOCKET = -3      # usados por app/seguranca.py
_IDX_HANDSHAKE = -4

_janelas = {}                 # (indice da regra, chave) -> deque de horários
_trava = threading.Lock()
_ultima_poda = [0.0]
_TETO_CHAVES = 30000          # quem forja mil endereços não pode encher a memória: passou disso, esquece tudo e recomeça


def ligado():
    return os.getenv('LIMITE_REQUISICOES', '1') != '0'


def _ip_ou_none(texto):
    """O endereço, já normalizado (IPv6 colapsa no /64: cada pessoa tem uma faixa inteira e trocar o final não adianta), ou None se não for IP."""
    try:
        ip = ipaddress.ip_address((texto or '').strip())
    except ValueError:
        return None
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f'{ip}/64', strict=False).network_address)
    return str(ip)


def ips_de(xff, remoto):
    """(esquerda, direita) de um `X-Forwarded-For`, só endereços válidos. Sem o cabeçalho (ou sem nenhum IP válido nele) os dois são o `remoto`.
    Não depende do Flask: o middleware do socket (que roda antes do Flask) usa esta mesma função."""
    partes = [_ip_ou_none(p) for p in (xff or '').split(',')[:20]]
    partes = [p for p in partes if p]
    if not partes:
        base = _ip_ou_none(remoto) or (remoto or '?')[:64]
        return base, base
    return partes[0], partes[-1]


def ips_do_cliente():
    return ips_de(request.headers.get('X-Forwarded-For'), request.remote_addr)


def ip_do_cliente():
    """O IP "de verdade" (ponta esquerda). Forjável: nunca use pra decidir permissão, só pra repartir limite."""
    return ips_do_cliente()[0]


def _regra_de(metodo, caminho):
    for i, (m, prefixo, n, janela, rotulo) in enumerate(REGRAS):
        if (m == '*' or m == metodo) and caminho.startswith(prefixo):
            return i, n, janela, rotulo
    return None


def _podar(agora):
    if len(_janelas) > _TETO_CHAVES:
        _janelas.clear()
        return
    if agora - _ultima_poda[0] > 120 and len(_janelas) > 2000:      # esquece quem não volta (a memória não cresce pra sempre)
        _ultima_poda[0] = agora
        for k in [k for k, v in _janelas.items() if not v or v[-1] <= agora - 300]:
            _janelas.pop(k, None)


def permitido(indice, chave, limite, janela, agora=None):
    """Conta mais um pedido da `chave` na regra `indice`. Devolve (ok, segundos_ate_poder_de_novo)."""
    agora = time.time() if agora is None else agora
    with _trava:
        dq = _janelas.setdefault((indice, chave), deque())
        corte = agora - janela
        while dq and dq[0] <= corte:
            dq.popleft()
        if len(dq) >= limite:
            return False, max(1, int(dq[0] + janela - agora) + 1)
        dq.append(agora)
        _podar(agora)
        return True, 0


def permitido_por_ip(indice, limite, janela, agora=None):
    """O pedido de quem NÃO tem login: passa pelas duas pontas do X-Forwarded-For (ver o topo do arquivo). Devolve (ok, espera)."""
    esq, dir_ = ips_do_cliente()
    ok, espera = permitido(indice, f'ip{esq}', limite, janela, agora)
    if not ok:
        return ok, espera
    return permitido(indice, f'bd{dir_}', limite * FATOR_BORDA, janela, agora)


def verificar():
    """`before_request`: barra com 429 quem passou do teto. Devolve None (deixa passar) ou a resposta."""
    if request.method == 'OPTIONS' or not ligado():
        return None
    caminho = request.path
    uid = session.get('user_id')
    achou = _regra_de(request.method, caminho)
    if achou:
        indice, n, janela, rotulo = achou
    elif uid:
        indice, n, janela, rotulo = _IDX_GERAL_PESSOA, GERAL_PESSOA, 60, 'acessos'
    else:
        indice, n, janela, rotulo = _IDX_GERAL_IP, GERAL_IP, 60, 'acessos'
    if uid:
        ok, espera = permitido(indice, f'u{uid}', n, janela)
    else:
        ok, espera = permitido_por_ip(indice, n, janela)
    if ok:
        return None
    msg = f'Calma! Muitos pedidos de {rotulo} em pouco tempo. Tente de novo em {espera} s.'
    if caminho.startswith('/api/') or caminho.startswith('/estudio/api/') or caminho.startswith('/admin/api/'):
        resp = make_response(jsonify({'erro': msg, 'error': msg, 'msg': msg, 'espere_s': espera}), 429)
    else:
        resp = make_response(msg, 429)
    resp.headers['Retry-After'] = str(espera)
    return resp


def zerar():
    """Só pros testes."""
    with _trava:
        _janelas.clear()
