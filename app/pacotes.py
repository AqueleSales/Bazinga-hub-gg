"""Pacotes (bundles) do Pantheon Estúdio: o admin junta itens de QUALQUER tema, um por slot, e o pacote entra no catálogo como `pacote:<id>`.

Sem socket e sem código novo no navegador: o pacote reaproveita o que já existe (Armazém, inventário "equipar tudo", recompensa do passe, "dar a alguém").
Do ponto de vista do app ele é um tema "combo" como o Combo JJK: `TEMAS[id]`, `PACOTES_FIXOS[id]` (o que ele equipa) e o item `pacote:<id>`.

Estados (`PacoteCustom.estado`):
  * rascunho  -> só existe no banco e no Estúdio; o app nem sabe dele (não se compra, não se dá, não aparece em lugar nenhum);
  * a_venda   -> entra no Armazém, em DRC (preço automático = soma da tabela menos o desconto de pacote, ou um preço fixo nunca acima da soma);
  * so_dar    -> existe no catálogo mas não tem preço: só o admin dá ("Dar a alguém") ou o passe entrega como recompensa.
`ate` (opcional) é o fim da venda: depois dele o pacote segue visível, mas não se compra (mesma regra das edições limitadas).

Entregar um pacote (compra, passe ou admin) dá o pacote E CADA item dele, inclusive os que não são vendidos avulsos (efeito do Estúdio, prêmio do passe):
quem decide a lista é `cosmeticos.itens_para_conceder`. Quem já tinha o pacote antes de o admin mexer nos itens fica com o que recebeu.

Regras que não se negociam: só admin escreve (as rotas ficam em app/estudio.py); tudo que vira `class=""` ou `style=""` no navegador de todo mundo vem de lista fechada
(ícone, categoria, estado) ou de `#rrggbb`; o cliente nunca manda preço final, só o que o admin quis (automático ou fixo), e o servidor confere contra a soma.
"""
import json
import math
import re
from datetime import datetime

from .cosmeticos import (CATALOGO, TEMAS, PACOTES, PACOTES_FIXOS, TIPOS_EQUIPAVEIS, IDS_CATEGORIA, ORDEM_RARIDADE, ROTULO_TIPO,
                         DESCONTO_PACOTE, _item, preco_de_tabela, recalcular_pacotes)
from .models import db, br_now, PacoteCustom, Posse
from .utils import com_retry, comitar_com_retry

ESTADOS = ('rascunho', 'a_venda', 'so_dar')
MIN_ITENS = 2
ICONES = ('fa-box-open', 'fa-gift', 'fa-star', 'fa-crown', 'fa-bolt', 'fa-fire', 'fa-gem', 'fa-heart', 'fa-moon', 'fa-sun',
          'fa-wand-magic-sparkles', 'fa-dragon', 'fa-ghost', 'fa-skull', 'fa-leaf', 'fa-snowflake', 'fa-trophy', 'fa-rocket',
          'fa-feather', 'fa-shield-halved')
_RE_ID = re.compile(r'^[a-z_]{2,24}$')
_RE_COR = re.compile(r'^#[0-9a-fA-F]{6}$')


class ErroPacote(Exception):
    """Erro de regra com mensagem que o admin pode ler."""


# ------------------------------------------------------------
# preço
# ------------------------------------------------------------
def soma_de(itens):
    return sum(preco_de_tabela(i) for i in itens)


def preco_automatico(soma):
    """A conta dos pacotes da loja: a soma menos DESCONTO_PACOTE, em múltiplos de 50 (nunca menos de 50). Metade arredonda PRA CIMA, igual ao
    `Math.round` da tela do Estúdio (o `round` do Python arredonda a metade pro par e a prévia divergiria 50 DRC em alguns casos)."""
    return max(50, int(math.floor(soma * (1 - DESCONTO_PACOTE) / 50.0 + 0.5)) * 50)


# ------------------------------------------------------------
# validação
# ------------------------------------------------------------
def _itens_validos(lista):
    """Lista de item_id -> lista limpa. Só item que existe no catálogo e que se EQUIPA (moldura, placa, nome, faixa e os efeitos), um por tipo."""
    if not isinstance(lista, list):
        raise ErroPacote('Escolha os itens do pacote.')
    vistos, por_tipo, saida = set(), {}, []
    for bruto in lista:
        item = str(bruto or '').strip()
        if not item or item in vistos:
            continue
        vistos.add(item)
        d = CATALOGO.get(item)
        if not d or d['tipo'] not in TIPOS_EQUIPAVEIS:
            raise ErroPacote(f'"{item[:40]}" não pode entrar num pacote. Só entram moldura, placa, nome, faixa e os efeitos que se equipam '
                             '(insígnia, efeito de servidor e outro pacote não).')
        if d['tipo'] in por_tipo:
            raise ErroPacote(f'Só um item por tipo: {ROTULO_TIPO.get(d["tipo"], d["tipo"])} aparece duas vezes ("{CATALOGO[por_tipo[d["tipo"]]]["nome"]}" e "{d["nome"]}").')
        por_tipo[d['tipo']] = item
        saida.append(item)
    if len(saida) < MIN_ITENS:
        raise ErroPacote(f'Um pacote precisa de pelo menos {MIN_ITENS} itens.')
    return saida


def _data_fim(valor):
    """'' / None -> None; 'AAAA-MM-DD' -> esse dia às 23:59:59; 'AAAA-MM-DDTHH:MM' -> a hora dita. Horário de Brasília, sem fuso (como o resto do banco)."""
    v = str(valor or '').strip()
    if not v:
        return None
    try:
        if len(v) == 10:
            return datetime.strptime(v, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        return datetime.fromisoformat(v).replace(tzinfo=None, microsecond=0)
    except ValueError:
        raise ErroPacote('A data de fim não está num formato válido.')


def _validar(dados):
    pid = str(dados.get('id') or '').strip().lower()
    if not _RE_ID.match(pid):
        raise ErroPacote('O id usa só letras minúsculas e _ (2 a 24 caracteres).')
    nome = str(dados.get('nome') or '').strip()
    if not 2 <= len(nome) <= 40:
        raise ErroPacote('O nome tem de 2 a 40 caracteres.')
    descricao = ' '.join(str(dados.get('descricao') or '').split())[:160]
    icone = dados.get('icone') or 'fa-box-open'
    if icone not in ICONES:
        raise ErroPacote('Ícone inválido.')
    categoria = dados.get('categoria') or 'fantasia'
    if categoria not in IDS_CATEGORIA:
        raise ErroPacote('Categoria inválida.')
    cores = []
    for k, padrao in (('cor1', '#d4a24c'), ('cor2', '#3a2f1c')):
        c = dados.get(k) or padrao
        if not _RE_COR.match(str(c)):
            raise ErroPacote('As cores usam o formato #rrggbb.')
        cores.append(str(c).lower())
    estado = dados.get('estado') or 'rascunho'
    if estado not in ESTADOS:
        raise ErroPacote('Estado inválido (rascunho, à venda ou só dar).')
    itens = _itens_validos(dados.get('itens'))
    soma = soma_de(itens)
    preco = dados.get('preco')
    if preco in (None, '', 0, '0'):
        preco = None
    else:
        try:
            preco = int(preco)
        except (TypeError, ValueError):
            raise ErroPacote('O preço precisa ser um número inteiro de DRC.')
        if not 1 <= preco <= max(soma, 1):
            raise ErroPacote(f'O preço fixo vai de 1 até a soma dos itens ({soma} DRC): o pacote nunca custa mais que comprar tudo avulso.')
    if estado == 'a_venda' and soma <= 0:
        raise ErroPacote('Esses itens não têm preço de referência na tabela, então o pacote não pode ser vendido. Use "só dar" ou troque algum item.')
    return {'id': pid, 'nome': nome, 'descricao': descricao, 'icone': icone, 'categoria': categoria, 'cor1': cores[0], 'cor2': cores[1],
            'estado': estado, 'itens': itens, 'preco': preco, 'ate': _data_fim(dados.get('ate'))}


# ------------------------------------------------------------
# entrar e sair do catálogo
# ------------------------------------------------------------
def _lista(p):
    try:
        v = json.loads(p.itens)
    except (TypeError, ValueError):
        return []
    return [i for i in v if isinstance(i, str)] if isinstance(v, list) else []


def _desregistrar(pid):
    CATALOGO.pop(f'pacote:{pid}', None)
    PACOTES.pop(pid, None)
    PACOTES_FIXOS.pop(pid, None)
    t = TEMAS.get(pid)
    if t and t.get('estudio'):
        TEMAS.pop(pid, None)


def _registrar(p):
    """Põe (ou tira) o pacote no CATALOGO/TEMAS/PACOTES em memória. Devolve o preço de venda (ou None se não está à venda).
    Item que sumiu do catálogo (efeito apagado) é ignorado; com menos de MIN_ITENS o pacote não entra."""
    _desregistrar(p.id)
    if p.estado not in ('a_venda', 'so_dar'):
        return None
    itens = [i for i in _lista(p) if i in CATALOGO and CATALOGO[i]['tipo'] in TIPOS_EQUIPAVEIS]
    por_tipo = {}
    for i in itens:
        por_tipo.setdefault(CATALOGO[i]['tipo'], CATALOGO[i]['valor'])
    if len(por_tipo) < MIN_ITENS:
        print(f'[PACOTES] "{p.id}" tem menos de {MIN_ITENS} itens que ainda existem: ficou fora do catálogo.')
        return None
    if p.id in TEMAS or f'pacote:{p.id}' in CATALOGO:
        print(f'[PACOTES] "{p.id}" repete um tema ou pacote que já existe: ficou fora do catálogo.')
        return None
    soma = soma_de(itens)
    venda = p.estado == 'a_venda' and soma > 0
    TEMAS[p.id] = {'nome': p.nome, 'cor': p.cor1, 'combo': True, 'estudio': True, 'desc': p.descricao or '', 'cores': [p.cor1, p.cor2],
                   'icone': p.icone, 'lema': (p.descricao or 'Um pacote montado no Pantheon.')[:90], 'categoria': p.categoria, 'loja': venda,
                   'sem_hero': True}
    PACOTES_FIXOS[p.id] = por_tipo
    extra = {'estudio': True, 'animado': True}
    preco = None
    if venda:
        preco = min(p.preco, soma) if p.preco else preco_automatico(soma)
        extra['preco'] = preco
    if p.ate:
        extra['limitado'] = {'estoque': None, 'ate': p.ate}
    raridade = max((CATALOGO[i]['raridade'] for i in itens), key=lambda r: ORDEM_RARIDADE.get(r, 0))
    _item('pacote', p.id, p.nome, p.descricao or 'Um pacote montado no Pantheon.', p.id, raridade, **extra)
    recalcular_pacotes()
    return preco


def carregar():
    """Lê os pacotes do banco e registra os que estão à venda ou só pra dar. Idempotente. Roda DEPOIS dos efeitos do Estúdio (eles podem ser itens do pacote)."""
    for p in com_retry(lambda: PacoteCustom.query.all()):
        _registrar(p)


# ------------------------------------------------------------
# o que o Estúdio mostra
# ------------------------------------------------------------
def para_json(p):
    itens = _lista(p)
    vivos = [i for i in itens if i in CATALOGO]
    soma = soma_de(vivos)
    auto = preco_automatico(soma) if soma > 0 else None
    no_ar = f'pacote:{p.id}' in CATALOGO
    return {'id': p.id, 'nome': p.nome, 'descricao': p.descricao or '', 'icone': p.icone, 'categoria': p.categoria, 'cor1': p.cor1, 'cor2': p.cor2,
            'estado': p.estado, 'itens': itens, 'faltando': [i for i in itens if i not in CATALOGO], 'preco': p.preco,
            'ate': p.ate.strftime('%Y-%m-%d') if p.ate and p.ate.hour == 23 and p.ate.minute == 59 else (p.ate.strftime('%Y-%m-%dT%H:%M') if p.ate else None),
            'soma': soma, 'preco_auto': auto, 'preco_final': (CATALOGO.get(f'pacote:{p.id}') or {}).get('preco'), 'no_ar': no_ar}


def listar():
    return [para_json(p) for p in com_retry(lambda: PacoteCustom.query.order_by(PacoteCustom.criado_em.desc()).all())]


def catalogo_para_ui():
    """Todo item que dá pra pôr num pacote (se equipa), com o que o seletor do Estúdio precisa pra procurar e somar."""
    saida = []
    for d in CATALOGO.values():
        if d['tipo'] not in TIPOS_EQUIPAVEIS:
            continue
        t = TEMAS.get(d['tema']) or {}
        saida.append({'id': d['id'], 'tipo': d['tipo'], 'rotulo': ROTULO_TIPO.get(d['tipo'], d['tipo']), 'nome': d['nome'], 'tema': d['tema'] or '',
                      'tema_nome': t.get('nome') or (d['tema'] or ''), 'raridade': d['raridade'], 'ref': preco_de_tabela(d['id']),
                      'avulso': bool(d.get('preco')), 'estudio': bool(d.get('custom'))})
    ordem = {t: n for n, t in enumerate(TIPOS_EQUIPAVEIS)}
    saida.sort(key=lambda x: (ordem.get(x['tipo'], 99), x['tema_nome'].lower(), x['nome'].lower()))
    return saida


def pacotes_que_usam(item_id):
    """Nomes dos pacotes (em qualquer estado) que têm este item. Serve pra recusar apagar um efeito que está num pacote."""
    return [p.nome for p in com_retry(lambda: PacoteCustom.query.all()) if item_id in _lista(p)]


# ------------------------------------------------------------
# salvar e apagar
# ------------------------------------------------------------
def salvar(dados):
    d = _validar(dados)
    pid = d['id']
    existente = com_retry(lambda: PacoteCustom.query.get(pid))
    if not existente and (pid in TEMAS or f'pacote:{pid}' in CATALOGO):
        raise ErroPacote('Já existe um tema ou pacote com esse id. Escolha outro id.')

    def preparar():
        p = PacoteCustom.query.get(pid)
        if not p:
            p = PacoteCustom(id=pid, criado_em=br_now())
            db.session.add(p)
        p.nome, p.descricao, p.icone, p.categoria = d['nome'], d['descricao'] or None, d['icone'], d['categoria']
        p.cor1, p.cor2, p.estado, p.preco, p.ate = d['cor1'], d['cor2'], d['estado'], d['preco'], d['ate']
        p.itens = json.dumps(d['itens'], separators=(',', ':'))
        return p

    p = comitar_com_retry(preparar)
    _registrar(p)
    return pid


def apagar(pid):
    p = com_retry(lambda: PacoteCustom.query.get(pid))
    if not p:
        raise ErroPacote('Pacote não encontrado.')

    def preparar():
        Posse.query.filter_by(item_id=f'pacote:{pid}').delete()      # só o "carimbo" do pacote: os itens que a pessoa recebeu continuam dela
        PacoteCustom.query.filter_by(id=pid).delete()

    comitar_com_retry(preparar)
    _desregistrar(pid)
