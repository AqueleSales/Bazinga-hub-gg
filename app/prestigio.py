"""Prestígio (impulso) de servidor, Rodada 35. Sem socket; os eventos moram em prestigio_events.py.

O QUE É: cada servidor tem um NÍVEL (0 a 4) que sobe com os IMPULSOS que as pessoas com a Brasa ativa dão a ele e com o tamanho da comunidade.
O nível libera recursos que EXISTEM de verdade (nada prometido a mais):
  * visibilidade do pino no mapa de mais longe (alcance_m: 15 km no nível 0 até o mundo todo no nível 4);
  * mais cargos por servidor (cargos_extra);
  * o barquinho do servidor no Explorar fica maior (porte mínimo).

PONTOS = 5 por impulso + 1 a cada 5 membros (conta até 100 membros, ou seja, no máximo 20 pontos). Níveis: 10, 30, 60 e 100 pontos.
Só tamanho dá no máximo o nível 1 (50 membros); do nível 2 em diante precisa de impulso de gente com Brasa.

REGRAS:
  * Impulsionar exige ser MEMBRO do servidor e ter a Brasa ATIVA. Cada pessoa tem IMPULSOS_POR_PESSOA impulsos, no máximo um por servidor.
  * O impulso só CONTA enquanto a Brasa da pessoa vale (conferido na leitura: a linha fica e volta a contar se ela renovar). Quem sai ou é removido
    do servidor perde o impulso dele ali (cargos.limpar_membro).
  * Nada aqui cobra: a Brasa segue grátis por enquanto (olimpo.gratis()). O preço/nome do impulso é decisão do dono.
  * PRIVACIDADE DO MAPA: o nível só estica quem enxerga o PINO DO SERVIDOR (que o dono escolheu plantar). Nunca mostra posição de pessoas, notas,
    lojas nem o radar: esses seguem nos raios de sempre. De fora do raio normal (RAIO_SERVIDORES_M) a posição do pino sai ARREDONDADA (~1 km), então
    quem planta o servidor "de casa" não entrega o endereço pro mundo. Entrar pelo pino continua exigindo estar dentro do raio normal.
"""
import time

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from .models import db, Server, MapServer, Person, ServerBoost, server_members, br_now
from .utils import com_retry, comitar_com_retry, eh_membro, RAIO_SERVIDORES_M

IMPULSOS_POR_PESSOA = 2
PONTOS_POR_IMPULSO = 5
MEMBROS_POR_PONTO = 5
MEMBROS_TETO = 100
LIMITES_PONTOS = (0, 10, 30, 60, 100)               # pontos mínimos de cada nível
NOMES = ('Comum', 'Em alta', 'Destaque', 'Prestigiado', 'Lendário')
MUNDO_M = 20_100_000                                # meia volta ao mundo: o nível 4 enxerga o servidor em qualquer lugar
ALCANCE_M = (RAIO_SERVIDORES_M, 30_000, 100_000, 500_000, MUNDO_M)
CARGOS_EXTRA = (0, 5, 10, 15, 25)
PORTE_MIN = (1, 1, 2, 3, 4)                         # barquinho do Explorar (1 canoa ... 4 galeão), nunca menor que isso
GRADE_LONGE = 0.01                                  # ~1 km: o pino visto de fora do raio normal é arredondado a isto
TTL_NIVEL_S = 30
TTL_PINOS_S = 60


class ErroPrestigio(Exception):
    pass


_cache_nivel = {}          # server_id -> (ts, info)
_cache_pinos = {'ts': 0.0, 'lista': []}


def invalidar(server_id=None):
    """Chame depois de mudar impulso/membros/pino: o nível é recalculado na próxima leitura."""
    if server_id is None:
        _cache_nivel.clear()
    else:
        _cache_nivel.pop(int(server_id), None)
    _cache_pinos['ts'] = 0.0


def pontos_de(impulsos, membros):
    return PONTOS_POR_IMPULSO * int(impulsos) + min(int(membros), MEMBROS_TETO) // MEMBROS_POR_PONTO


def nivel_de(pontos):
    n = 0
    for i, minimo in enumerate(LIMITES_PONTOS):
        if pontos >= minimo:
            n = i
    return n


def alcance_m(nivel):
    return ALCANCE_M[max(0, min(int(nivel or 0), len(ALCANCE_M) - 1))]


def cargos_extra(nivel):
    return CARGOS_EXTRA[max(0, min(int(nivel or 0), len(CARGOS_EXTRA) - 1))]


def porte_minimo(nivel):
    return PORTE_MIN[max(0, min(int(nivel or 0), len(PORTE_MIN) - 1))]


def _info(impulsos, membros):
    pontos = pontos_de(impulsos, membros)
    n = nivel_de(pontos)
    prox = LIMITES_PONTOS[n + 1] if n + 1 < len(LIMITES_PONTOS) else None
    return {'nivel': n, 'nome': NOMES[n], 'pontos': pontos, 'impulsos': int(impulsos), 'membros': int(membros),
            'proximo_pontos': prox, 'faltam': (prox - pontos) if prox is not None else 0, 'alcance_m': alcance_m(n)}


def niveis(ids):
    """{server_id: info} em lote, com cache curto (o mapa pergunta a cada passo da pessoa: não pode custar ida ao banco toda vez)."""
    ids = [int(i) for i in ids if i]
    agora = time.time()
    falta = [i for i in set(ids) if i not in _cache_nivel or agora - _cache_nivel[i][0] > TTL_NIVEL_S]
    if falta:
        imp = dict(com_retry(lambda: db.session.query(ServerBoost.server_id, func.count(ServerBoost.id))
                             .join(Person, Person.id == ServerBoost.person_id)
                             .filter(ServerBoost.server_id.in_(falta), Person.olimpo_ate > br_now())
                             .group_by(ServerBoost.server_id).all()))
        mem = dict(com_retry(lambda: db.session.query(server_members.c.server_id, func.count(server_members.c.person_id))
                             .filter(server_members.c.server_id.in_(falta)).group_by(server_members.c.server_id).all()))
        for i in falta:
            _cache_nivel[i] = (agora, _info(imp.get(i, 0), mem.get(i, 0)))
    return {i: _cache_nivel[i][1] for i in ids}


def info(server_id):
    return niveis([server_id])[int(server_id)]


def pinos_de_longe():
    """Pinos plantados cujo servidor tem alcance MAIOR que o normal: [{pino_id, server_id, lat, lng, nivel, alcance_m}]. Cache de 1 min
    (uma consulta global, não uma por pedido de mapa)."""
    agora = time.time()
    if agora - _cache_pinos['ts'] <= TTL_PINOS_S:
        return _cache_pinos['lista']
    agora_dt = br_now()
    pinos = com_retry(lambda: MapServer.query.filter(
        MapServer.server_id.isnot(None), MapServer.oculta.isnot(True),
        (MapServer.expires_at.is_(None)) | (MapServer.expires_at > agora_dt)).limit(2000).all())
    ni = niveis([p.server_id for p in pinos])
    lista = [{'pino_id': p.id, 'server_id': p.server_id, 'lat': p.lat, 'lng': p.lng, 'nivel': ni[p.server_id]['nivel'],
              'alcance_m': ni[p.server_id]['alcance_m']} for p in pinos if ni[p.server_id]['nivel'] > 0]
    _cache_pinos['lista'] = lista
    _cache_pinos['ts'] = agora
    return lista


def aproximar(lat, lng):
    """Posição do pino vista de LONGE: arredondada a ~1 km."""
    return round(round(lat / GRADE_LONGE) * GRADE_LONGE, 5), round(round(lng / GRADE_LONGE) * GRADE_LONGE, 5)


def tabela_de_niveis():
    return [{'nivel': i, 'nome': NOMES[i], 'pontos': LIMITES_PONTOS[i], 'alcance_m': ALCANCE_M[i], 'cargos_extra': CARGOS_EXTRA[i],
             'porte': PORTE_MIN[i]} for i in range(len(NOMES))]


def _brasa_ativa(pessoa):
    from . import olimpo
    return olimpo.ativo(pessoa)


def meus_impulsos(pessoa_id):
    """Ids dos servidores onde esta pessoa gastou um impulso."""
    return [r[0] for r in com_retry(lambda: db.session.query(ServerBoost.server_id).filter(ServerBoost.person_id == pessoa_id).order_by(ServerBoost.id).all())]


def estado(usuario, srv):
    """O que a janela do Prestígio mostra. Só quem é membro do servidor pede (o evento confere)."""
    from . import olimpo
    i = info(srv.id)
    meus = meus_impulsos(usuario.id)
    quem = com_retry(lambda: db.session.query(Person.id, Person.name, Person.olimpo_ate).join(ServerBoost, ServerBoost.person_id == Person.id)
                     .filter(ServerBoost.server_id == srv.id).order_by(ServerBoost.id).limit(30).all())
    agora = br_now()
    return {'server_id': srv.id, **i, 'tabela': tabela_de_niveis(), 'eu_impulsiono': srv.id in meus, 'meus_usados': len(meus),
            'meus_total': IMPULSOS_POR_PESSOA, 'brasa_ativa': _brasa_ativa(usuario), 'brasa_nome': olimpo.NOME, 'brasa_gratis': olimpo.gratis(),
            'quem': [{'id': p[0], 'nome': p[1], 'vale': bool(p[2] and p[2] > agora)} for p in quem],
            'raio_normal_m': RAIO_SERVIDORES_M, 'pontos_por_impulso': PONTOS_POR_IMPULSO, 'membros_por_ponto': MEMBROS_POR_PONTO}


def impulsionar(usuario, srv, ativo):
    """Liga/desliga o impulso desta pessoa neste servidor (valor EXPLÍCITO: duas abas não se anulam). Devolve True se mudou algo."""
    if not eh_membro(usuario, srv.id):
        raise ErroPrestigio('Só quem está no servidor pode impulsioná-lo.')
    ativo = bool(ativo)

    def preparar():
        existente = ServerBoost.query.filter_by(server_id=srv.id, person_id=usuario.id).first()
        if ativo:
            if existente:
                return False
            if not _brasa_ativa(usuario):
                from . import olimpo
                raise ErroPrestigio(f'Impulsionar um servidor é um benefício da {olimpo.NOME}. Ative a sua em Configurações > {olimpo.NOME}.')
            if ServerBoost.query.filter_by(person_id=usuario.id).count() >= IMPULSOS_POR_PESSOA:
                raise ErroPrestigio(f'Você já usou os seus {IMPULSOS_POR_PESSOA} impulsos. Tire um de outro servidor pra usar aqui.')
            db.session.add(ServerBoost(server_id=srv.id, person_id=usuario.id))
            return True
        if not existente:
            return False
        db.session.delete(existente)
        return True

    try:
        mudou = comitar_com_retry(preparar)
    except IntegrityError:        # clique duplo / duas abas: a outra gravou primeiro
        db.session.rollback()
        mudou = False
    if mudou:
        invalidar(srv.id)
    return bool(mudou)
