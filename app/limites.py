"""Limite de requisições (Rodada 35): o que a auditoria da Rodada 30 deixou aberto. As rotas que gastam serviço de fora (Cloudinary, Giphy, o
Pillow do servidor, o download de imagem) e as de login não tinham teto por pessoa: um script podia martelar `/api/upload` ou o login.

Como funciona: janela deslizante em memória (um processo só: o app roda com `-w 1`), uma lista de horários por chave. A chave é a PESSOA logada
(`u<id>`, precisa e impossível de forjar); sem login (os endereços de entrada) vale o IP. O IP vem do primeiro endereço de `X-Forwarded-For` (o
Render põe o do cliente ali); quem forjar o cabeçalho só consegue contornar o limite das rotas SEM login, e essas são só as de entrada.

Estourou: 429 com `Retry-After` e uma mensagem em português (JSON em `/api/*`). Desligar: `LIMITE_REQUISICOES=0`. Os freios por funcionalidade
(`/api/meus-dados` a cada 20 s, o recorte de GIF a cada 1,5 s, etc.) continuam valendo; este é o teto GERAL por cima deles.
"""
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
    ('GET', '/api/gifs', 60, 60, 'busca de GIF'),
    ('GET', '/api/localizacao/ip', 30, 60, 'localização por IP'),
    ('GET', '/api/meus-dados', 6, 60, 'cópia dos dados'),
    ('*', '/auth/login', 20, 60, 'login'),
    ('*', '/auth/callback', 20, 60, 'login'),
    ('*', '/auth/desktop/', 30, 60, 'login do app'),
)

_janelas = {}                 # (indice da regra, chave) -> deque de horários
_trava = threading.Lock()
_ultima_poda = [0.0]


def ligado():
    return os.getenv('LIMITE_REQUISICOES', '1') != '0'


def ip_do_cliente():
    candidatos = [p.strip() for p in (request.headers.get('X-Forwarded-For') or '').split(',') if p.strip()]
    return (candidatos[0] if candidatos else (request.remote_addr or '?'))[:64]


def _regra_de(metodo, caminho):
    for i, (m, prefixo, n, janela, rotulo) in enumerate(REGRAS):
        if (m == '*' or m == metodo) and caminho.startswith(prefixo):
            return i, n, janela, rotulo
    return None


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
        if agora - _ultima_poda[0] > 120 and len(_janelas) > 2000:      # esquece quem não volta (a memória não cresce pra sempre)
            _ultima_poda[0] = agora
            for k in [k for k, v in _janelas.items() if not v or v[-1] <= agora - 300]:
                _janelas.pop(k, None)
        return True, 0


def verificar():
    """`before_request`: barra com 429 quem passou do teto. Devolve None (deixa passar) ou a resposta."""
    caminho = request.path
    if not (caminho.startswith('/api/') or caminho.startswith('/auth/')) or not ligado():
        return None
    achou = _regra_de(request.method, caminho)
    if not achou:
        return None
    indice, n, janela, rotulo = achou
    uid = session.get('user_id')
    chave = f'u{uid}' if uid else f'ip{ip_do_cliente()}'
    ok, espera = permitido(indice, chave, n, janela)
    if ok:
        return None
    msg = f'Calma! Muitos pedidos de {rotulo} em pouco tempo. Tente de novo em {espera} s.'
    if caminho.startswith('/api/'):
        resp = make_response(jsonify({'erro': msg, 'msg': msg, 'espere_s': espera}), 429)
    else:
        resp = make_response(msg, 429)
    resp.headers['Retry-After'] = str(espera)
    return resp


def zerar():
    """Só pros testes."""
    with _trava:
        _janelas.clear()
