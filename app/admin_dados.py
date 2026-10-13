"""Números e lista de pessoas da "Visão geral" do Estúdio (/admin). Só leitura; as rotas (admin.py) já conferem que quem pede é admin.

Dados pessoais: aqui saem nome, @ e e-mail de TODAS as contas. Isso só é seguro porque as rotas são só de admin (404/403 pra o resto) e as
respostas vão com `Cache-Control: no-store`. Nada daqui pode ser reaproveitado por rota de usuário comum.
Consultas: cada uma é uma ida ao Neon, então tudo é agregado no banco (GROUP BY), nunca "traz tudo e conta em Python".
"""
from datetime import timedelta

from sqlalchemy import func, case, or_

from .models import db, br_now, Person, Message, DirectMessage, Server, BazarLoja, PassePessoa
from .utils import com_retry, xp_do_nivel, nivel_da_pessoa

DIAS_VALIDOS = (7, 30, 90)
POR_PAGINA = 25
# faixas de nível de conta pro histograma: (rótulo, nível mínimo). A última não tem teto.
FAIXAS_NIVEL = (('1 a 4', 1), ('5 a 9', 5), ('10 a 19', 10), ('20 a 49', 20), ('50 a 99', 50), ('100 ou mais', 100))
ORDENS = ('recentes', 'nome', 'nivel')


def _hoje():
    return br_now().replace(hour=0, minute=0, second=0, microsecond=0)


def _por_dia(coluna, desde, dias):
    """{'AAAA-MM-DD': quantidade} das linhas com `coluna` >= desde, agrupado NO BANCO, e a lista completa dos `dias` (dia sem nada = 0)."""
    linhas = com_retry(lambda: db.session.query(func.date(coluna), func.count()).filter(coluna >= desde).group_by(func.date(coluna)).all())
    achados = {str(d)[:10]: int(n) for d, n in linhas if d is not None}
    hoje = _hoje()
    saida = []
    for i in range(dias - 1, -1, -1):
        d = (hoje - timedelta(days=i)).strftime('%Y-%m-%d')
        saida.append({'dia': d, 'n': achados.get(d, 0)})
    return saida


def _faixas_de_nivel():
    """Quantas pessoas em cada faixa de nível de conta (uma consulta só, por limites de XP)."""
    cortes = [xp_do_nivel(n) for _r, n in FAIXAS_NIVEL]          # XP necessário pra ALCANÇAR o início de cada faixa
    expr = case(*[(Person.xp < cortes[i + 1], i) for i in range(len(FAIXAS_NIVEL) - 1)], else_=len(FAIXAS_NIVEL) - 1)
    achados = dict(com_retry(lambda: db.session.query(expr, func.count()).group_by(expr).all()))
    return [{'faixa': rot, 'n': int(achados.get(i, 0))} for i, (rot, _n) in enumerate(FAIXAS_NIVEL)]


def _online_agora():
    from . import events   # import tardio: events importa o admin indiretamente
    return sum(1 for v in events.usuarios_conectados.values() if v > 0)


def resumo(dias=30):
    dias = dias if dias in DIAS_VALIDOS else 30
    hoje = _hoje()
    desde = hoje - timedelta(days=dias - 1)
    q = lambda f: com_retry(f)
    sem_data = q(lambda: Person.query.filter(Person.created_at.is_(None)).count())
    novas_7 = q(lambda: Person.query.filter(Person.created_at >= hoje - timedelta(days=6)).count())
    novas_periodo = q(lambda: Person.query.filter(Person.created_at >= desde).count())
    mensagens_hoje = q(lambda: Message.query.filter(Message.timestamp >= hoje).count()) + q(lambda: DirectMessage.query.filter(DirectMessage.timestamp >= hoje).count())
    contas = _por_dia(Person.created_at, desde, dias)
    canais = {x['dia']: x['n'] for x in _por_dia(Message.timestamp, desde, dias)}
    dms = {x['dia']: x['n'] for x in _por_dia(DirectMessage.timestamp, desde, dias)}
    mensagens = [{'dia': x['dia'], 'n': canais.get(x['dia'], 0) + dms.get(x['dia'], 0), 'canais': canais.get(x['dia'], 0), 'dms': dms.get(x['dia'], 0)} for x in contas]
    from . import passe
    snap = passe.temporada_ativa()
    jogando = q(lambda: PassePessoa.query.filter(PassePessoa.temporada_id == snap['id'], PassePessoa.xp > 0).count()) if snap else 0
    premium = q(lambda: PassePessoa.query.filter(PassePessoa.temporada_id == snap['id'], PassePessoa.premium.is_(True)).count()) if snap else 0
    return {
        'dias': dias,
        'pessoas': q(lambda: Person.query.count()),
        'online_agora': _online_agora(),
        'novas_7d': novas_7, 'novas_periodo': novas_periodo, 'contas_sem_data': sem_data,
        'mensagens_hoje': mensagens_hoje,
        'servidores': q(lambda: Server.query.count()),
        'servidores_publicos': q(lambda: Server.query.filter(Server.publico.is_(True)).count()),
        'lojas': q(lambda: BazarLoja.query.count()),
        'jogando_temporada': jogando, 'premium_temporada': premium,
        'contas_por_dia': contas, 'mensagens_por_dia': mensagens, 'niveis': _faixas_de_nivel(),
    }


def _like(texto):
    return '%' + texto.replace('\\', '').replace('%', '').replace('_', '') + '%'


def lista_pessoas(busca='', pagina=1, ordem='recentes'):
    """Uma página (25) de pessoas: nome, @, e-mail, quando entrou, nível e se está online agora. `busca` casa nome, @ ou e-mail."""
    from . import events
    busca = (busca or '').strip().lstrip('@')[:80]
    ordem = ordem if ordem in ORDENS else 'recentes'
    try:
        pagina = max(1, int(pagina))
    except (TypeError, ValueError):
        pagina = 1
    q = Person.query
    if len(busca) >= 2:
        like = _like(busca)
        q = q.filter(or_(Person.name.ilike(like), Person.username.ilike(like), Person.email.ilike(like)))
    total = com_retry(lambda: q.count())
    paginas = max(1, -(-total // POR_PAGINA))
    pagina = min(pagina, paginas)
    if ordem == 'nome':
        q = q.order_by(func.lower(Person.name), Person.id)
    elif ordem == 'nivel':
        q = q.order_by(Person.xp.desc(), Person.id)
    else:
        q = q.order_by(Person.id.desc())      # o id cresce a cada conta nova: "mais recentes" sem depender de created_at (que contas antigas não têm)
    linhas = com_retry(lambda: q.offset((pagina - 1) * POR_PAGINA).limit(POR_PAGINA).all())
    return {
        'total': total, 'pagina': pagina, 'paginas': paginas, 'por_pagina': POR_PAGINA,
        'pessoas': [{
            'id': p.id, 'nome': p.name, 'username': p.username or '', 'email': p.email or '', 'avatar': p.avatar or '',
            'criado_em': p.created_at.strftime('%d/%m/%Y') if p.created_at else None,
            'nivel': nivel_da_pessoa(p.xp or 0), 'online': events.usuarios_conectados.get(p.id, 0) > 0,
        } for p in linhas],
    }
