"""Mensagem nova nos canais dos servidores: "não lida" por pessoa e por canal (Rodada 39).

Antes só a DM tinha bolinha de não lida; servidor e canal não avisavam nada. Aqui mora a regra, sem socket:

* `CanalLeitura` guarda até qual mensagem a pessoa leu em cada canal (por conta, então vale em qualquer aparelho).
* `canais_nao_lidos()` conta o que passou desse ponto em UMA consulta (as linhas que faltam são criadas na primeira vez, com o
  ponto de leitura no topo do canal: quem acabou de entrar no servidor, ou o deploy, nunca vê histórico antigo como "não lido").
* `marcar_lido()` leva o ponto até o topo do canal e também dá por lidas as menções daquele canal na caixa de entrada.

O tempo real (avisar quem está com o app aberto) fica em `avisos_events.py`.
"""
from sqlalchemy import and_, func, text
from sqlalchemy.exc import IntegrityError

from .models import db, CanalLeitura, Message, Notificacao
from . import cargos
from .utils import comitar_com_retry

# Canais que guardam conversa: os de texto (menos a vitrine de lojas, que ninguém escreve) e o de stream (voz + chat ao lado).
TIPOS_COM_CHAT = tuple(t for t in cargos.TIPOS_TEXTO if t not in cargos.TIPOS_SEM_MENSAGEM) + ('stream',)
TETO_CONTADOR = 99          # a bolinha mostra "99+": contar além disso é gastar consulta à toa


def canais_com_chat(servidores_json):
    """Ids dos canais com conversa que a pessoa enxerga, a partir do JSON dos servidores dela (já filtrado por permissão)."""
    ids = []
    for srv in servidores_json or []:
        for c in srv.get('channels') or []:
            if c.get('type') in TIPOS_COM_CHAT:
                ids.append(int(c['id']))
    return ids


def nao_lidas(pessoa_id, canal_ids):
    """{canal_id: quantidade} só dos canais com mensagem nova de OUTRA pessoa depois do ponto de leitura (no máximo 99).
    Uma consulta no caso comum; só a primeira vez de cada canal faz mais duas (achar o topo e gravar o ponto)."""
    ids = list(dict.fromkeys(int(i) for i in canal_ids))
    if not ids:
        return {}
    linhas = (db.session.query(CanalLeitura.channel_id, func.count(Message.id))
              .outerjoin(Message, and_(Message.channel_id == CanalLeitura.channel_id,
                                       Message.id > CanalLeitura.ultimo_id,
                                       Message.person_id != pessoa_id))
              .filter(CanalLeitura.person_id == pessoa_id, CanalLeitura.channel_id.in_(ids))
              .group_by(CanalLeitura.channel_id).all())
    com_linha = {c for c, _ in linhas}
    faltam = [i for i in ids if i not in com_linha]
    if faltam:
        topos = dict(db.session.query(Message.channel_id, func.max(Message.id))
                     .filter(Message.channel_id.in_(faltam)).group_by(Message.channel_id).all())
        try:
            # inserção em lote (uma ida ao banco), sem objeto ORM por linha
            db.session.execute(CanalLeitura.__table__.insert(),
                               [{'person_id': pessoa_id, 'channel_id': cid, 'ultimo_id': topos.get(cid) or 0} for cid in faltam])
            db.session.commit()
        except IntegrityError:
            db.session.rollback()        # duas abas abrindo juntas: a outra gravou primeiro, tudo bem
    return {int(c): min(int(n), TETO_CONTADOR) for c, n in linhas if n}


def marcar_lido(pessoa_id, canal):
    """Leva o ponto de leitura até a última mensagem do canal e dá por lidas as menções dele na caixa de entrada."""
    topo = db.session.query(func.max(Message.id)).filter(Message.channel_id == canal.id).scalar() or 0

    def preparar():
        linha = CanalLeitura.query.filter_by(person_id=pessoa_id, channel_id=canal.id).first()
        if linha:
            linha.ultimo_id = max(linha.ultimo_id or 0, topo)
        else:
            db.session.add(CanalLeitura(person_id=pessoa_id, channel_id=canal.id, ultimo_id=topo))
        if canal.server_id:
            Notificacao.query.filter_by(person_id=pessoa_id, tipo='mencao', lida=False,
                                        ref=f'{canal.server_id}:{canal.id}').update({'lida': True}, synchronize_session=False)

    try:
        comitar_com_retry(preparar)
    except IntegrityError:
        db.session.rollback()            # corrida de duas abas na primeira linha: a próxima chamada acerta


def marcar_tudo_lido(pessoa_id):
    """"Marcar tudo como lido" da caixa de entrada: todos os canais vão pro topo (uma instrução só)."""
    def preparar():
        db.session.execute(text(
            "UPDATE canal_leitura SET ultimo_id = COALESCE((SELECT MAX(m.id) FROM message m WHERE m.channel_id = canal_leitura.channel_id), 0) "
            "WHERE person_id = :p"), {'p': pessoa_id})

    comitar_com_retry(preparar)
