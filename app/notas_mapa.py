"""Respostas e reações nas notas do mapa (Rodada 29). A regra mora aqui; os eventos de socket, em notas_mapa_events.py.

Desenho (regra 4: tudo conferido no servidor; regra 6: quem está olhando a nota recebe a mudança ao vivo):
  * Qualquer pessoa NO ALCANCE da nota (2 km; 15 km se for amiga do autor) pode reagir e responder, com a posição do APARELHO
    (a mesma exigência de deixar/copiar nota). Bloqueio entre as duas pontas corta tudo, sem revelar que foi bloqueio.
  * O AUTOR da nota escolhe quem responde: `todos` (padrão, `utils.RESPOSTAS_PADRAO`), `amigos` (só amigos dele; as respostas também só
    chegam ao autor e aos amigos dele) ou `ninguem` (respostas desligadas e escondidas). Reagir sempre vale pra quem vê a nota.
  * Reação: lista FECHADA de emojis (`utils.REACOES_NOTA`); só o TOTAL por emoji sai do servidor, ninguém sabe quem reagiu
    (a própria pessoa recebe só as dela). Valor explícito `ativo` (duas abas não se anulam).
  * Resposta: texto curto, sem link de quem não é amigo do autor, no máximo MAX_RESPOSTAS_NOTA por nota e MAX_RESPOSTAS_PESSOA por
    pessoa. Quem escreveu e o autor da nota apagam; 3 denúncias de pessoas diferentes escondem (mesmo mecanismo do resto do mapa).
  * Resposta e reação morrem junto com a nota (a nota vence sozinha em até 7 dias; ON DELETE CASCADE cobre a faxina em massa).
"""
from sqlalchemy import func, case, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from datetime import timedelta

from .models import db, br_now, GeoNote, GeoNoteResposta, GeoNoteReacao
from .utils import (comitar_com_retry, texto_tem_link, MODOS_RESPOSTA_NOTA, RESPOSTAS_PADRAO, REACOES_NOTA, modo_resposta_da_nota)

LIM_RESPOSTA = 140            # mesmo número do texto da nota (LIM_NOTA em events.py) e do maxlength do cliente
MAX_RESPOSTAS_NOTA = 30
MAX_RESPOSTAS_PESSOA = 5      # por nota (o autor da nota não tem esse teto: conversa com quem respondeu)


class ErroNota(Exception):
    pass


def modo_valido(valor):
    """O modo que o cliente mandou, se for um dos conhecidos; senão None (= usa o padrão)."""
    return valor if valor in MODOS_RESPOSTA_NOTA else None


def nota_viva(n, agora=None):
    """Nota que ainda existe pro mapa: não escondida por denúncia e não vencida (nota antiga sem prazo vale 24 h desde que nasceu)."""
    agora = agora or br_now()
    if n.oculta:
        return False
    if n.expires_at:
        return n.expires_at > agora
    return bool(n.timestamp and n.timestamp > agora - timedelta(hours=24))


def pode_ver_respostas(modo, autor_id, viewer_id, amigos_ids):
    """Quem enxerga as respostas de uma nota: todo mundo que vê a nota (`todos`); só o autor e os amigos dele (`amigos`); ninguém (`ninguem`)."""
    if modo == 'todos':
        return True
    if modo == 'amigos':
        return viewer_id is not None and (viewer_id == autor_id or autor_id in (amigos_ids or ()))
    return False


def resposta_para_json(r, agora=None):
    agora = agora or br_now()
    ha = max(0, int((agora - r.created_at).total_seconds())) if r.created_at else 0
    return {'id': r.id, 'autor': r.author.name if r.author else '???', 'autor_id': r.author_id, 'texto': r.text, 'ha_s': ha}


def _ordenar_reacoes(contagens):
    """[(emoji, total)] na ordem fixa da lista (a barra de reações não pula de lugar quando os totais mudam)."""
    return [{'emoji': e, 'total': contagens[e]} for e in REACOES_NOTA if contagens.get(e)]


def anexar(notas_json, notas_db, viewer_id, amigos_ids):
    """Acrescenta a cada dict de nota (`nota_para_json`) as `respostas` que o leitor pode ver, as `reacoes` (totais) e as `minhas`.
    Duas consultas pro mapa inteiro (não uma por nota), e só quando há nota."""
    if not notas_db:
        return
    amigos = set(amigos_ids or [])
    ids = [n.id for n in notas_db]

    minha = case((GeoNoteReacao.person_id == viewer_id, 1), else_=0) if viewer_id is not None else None
    colunas = [GeoNoteReacao.note_id, GeoNoteReacao.emoji, func.count()]
    if minha is not None:
        colunas.append(func.sum(minha))
    linhas = db.session.query(*colunas).filter(GeoNoteReacao.note_id.in_(ids)).group_by(GeoNoteReacao.note_id, GeoNoteReacao.emoji).all()
    totais, minhas = {}, {}
    for linha in linhas:
        totais.setdefault(linha[0], {})[linha[1]] = int(linha[2])
        if minha is not None and int(linha[3] or 0) > 0:
            minhas.setdefault(linha[0], set()).add(linha[1])

    por_nota = {}
    visiveis = [n.id for n in notas_db if pode_ver_respostas(modo_resposta_da_nota(n), n.author_id, viewer_id, amigos)]
    if visiveis:
        agora = br_now()
        rs = (GeoNoteResposta.query.options(joinedload(GeoNoteResposta.author))
              .filter(GeoNoteResposta.note_id.in_(visiveis), or_(GeoNoteResposta.oculta == None, GeoNoteResposta.oculta == False))  # noqa: E711,E712
              .order_by(GeoNoteResposta.id).all())
        for r in rs:
            por_nota.setdefault(r.note_id, []).append(resposta_para_json(r, agora))

    for j, n in zip(notas_json, notas_db):
        j['reacoes'] = _ordenar_reacoes(totais.get(n.id, {}))
        j['minhas'] = [e for e in REACOES_NOTA if e in minhas.get(n.id, ())]
        j['respostas'] = por_nota.get(n.id, [])


# ---------------------------------------------------------------------------
# AÇÕES (cada uma é uma transação; o chamador já conferiu login, posição, alcance e bloqueio)
# ---------------------------------------------------------------------------
def totais_e_minhas(note_id, person_id):
    linhas = db.session.query(GeoNoteReacao.emoji, func.count()).filter(GeoNoteReacao.note_id == note_id).group_by(GeoNoteReacao.emoji).all()
    meus = {r[0] for r in db.session.query(GeoNoteReacao.emoji).filter_by(note_id=note_id, person_id=person_id).all()}
    return _ordenar_reacoes({e: int(t) for e, t in linhas}), [e for e in REACOES_NOTA if e in meus]


def reagir(usuario, nota, emoji, ativo):
    """Liga/desliga (valor EXPLÍCITO) a reação da pessoa. Devolve (totais, minhas)."""
    if emoji not in REACOES_NOTA:
        raise ErroNota('Essa reação não existe.')
    nota_id, pessoa_id = nota.id, usuario.id

    def preparar():
        existe = GeoNoteReacao.query.filter_by(note_id=nota_id, person_id=pessoa_id, emoji=emoji).first()
        if ativo and not existe:
            db.session.add(GeoNoteReacao(note_id=nota_id, person_id=pessoa_id, emoji=emoji))
        elif not ativo and existe:
            db.session.delete(existe)

    try:
        comitar_com_retry(preparar)
    except IntegrityError:
        db.session.rollback()   # duas abas ligaram a mesma reação juntas: o resultado é o mesmo
    return totais_e_minhas(nota_id, pessoa_id)


def texto_da_resposta(texto):
    t = ' '.join(str(texto or '').split())      # espaço e quebra de linha em excesso viram um espaço só
    if not t:
        raise ErroNota('Escreva alguma coisa pra responder.')
    return t[:LIM_RESPOSTA]


def responder(usuario, nota, texto, amigo_do_autor):
    """Grava a resposta. Devolve o dict da resposta. `amigo_do_autor` já vem conferido (accepted) por quem chama."""
    modo = modo_resposta_da_nota(nota)
    ehautor = usuario.id == nota.author_id
    if modo == 'ninguem':
        raise ErroNota('As respostas desta nota estão desligadas.')
    if modo == 'amigos' and not (ehautor or amigo_do_autor):
        raise ErroNota('Só os amigos de quem deixou a nota podem responder.')
    texto = texto_da_resposta(texto)
    if texto_tem_link(texto) and not (ehautor or amigo_do_autor):
        raise ErroNota('Link (ou endereço de site) só entre amigos: vire amigo de quem deixou a nota pra mandar.')
    nota_id, pessoa_id = nota.id, usuario.id

    def preparar():
        base = GeoNoteResposta.query.filter(GeoNoteResposta.note_id == nota_id,
                                            or_(GeoNoteResposta.oculta == None, GeoNoteResposta.oculta == False))  # noqa: E711,E712
        if base.count() >= MAX_RESPOSTAS_NOTA:
            raise ErroNota(f'Essa nota já tem {MAX_RESPOSTAS_NOTA} respostas. Pra falar mais, deixe uma nota sua.')
        if not ehautor and base.filter(GeoNoteResposta.author_id == pessoa_id).count() >= MAX_RESPOSTAS_PESSOA:
            raise ErroNota(f'Você já respondeu {MAX_RESPOSTAS_PESSOA} vezes nessa nota.')
        r = GeoNoteResposta(note_id=nota_id, author_id=pessoa_id, text=texto)
        db.session.add(r)
        return r

    r = comitar_com_retry(preparar)
    return resposta_para_json(r)


def apagar_resposta(usuario, resposta_id):
    """Quem escreveu a resposta ou o autor da nota apaga. Devolve (note_id, resposta_id, nota) ou levanta ErroNota."""
    r = GeoNoteResposta.query.get(resposta_id)
    if not r:
        raise ErroNota('Essa resposta já não existe.')
    nota = GeoNote.query.get(r.note_id)
    if usuario.id != r.author_id and not (nota and usuario.id == nota.author_id):
        raise ErroNota('Você só pode apagar as suas respostas (ou qualquer uma na sua nota).')
    rid, nid = r.id, r.note_id

    def preparar():
        x = GeoNoteResposta.query.get(rid)
        if x:
            db.session.delete(x)

    comitar_com_retry(preparar)
    return nid, rid, nota
