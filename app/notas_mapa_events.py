"""Eventos de Socket.IO das respostas e reações nas notas do mapa (a regra mora em notas_mapa.py).

Regra 6: a mudança vai pra quem está olhando a nota, não só pra quem agiu:
  * reação e resposta (modo `todos`): as abas que estão no alcance da nota (`_emitir_perto`) + os amigos do autor (alcance grande);
  * resposta no modo `amigos`: SÓ o autor da nota e os amigos dele (estranho no alcance nem fica sabendo);
  * sempre: todas as abas do autor da nota e de quem agiu (sala pessoal).
Os handlers do cliente são idempotentes (a mesma resposta pode chegar duas vezes por salas diferentes).
Erro de regra volta como `geonote_erro {id, msg}`; erro inesperado como `erro_bazinga` (regra 3).
"""
import time

from flask import request
from flask_socketio import emit

from . import socketio, notas_mapa
from .notas_mapa import ErroNota
from .models import db, br_now, GeoNote, GeoNoteResposta
from .utils import (com_retry, localizacao_ligada, MSG_LOCALIZACAO_DESLIGADA, distancia_m,
                    RAIO_NOTAS_M, RAIO_SERVIDORES_M, modo_resposta_da_nota)
from .events import (usuario_logado, sala_pessoal, centros_mapa, _exigir_presenca, _emitir_perto, _avisar_amigos,
                     relacao_entre, criar_notificacao)

_ultimo = {}


def _freio(usuario, chave, intervalo):
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


def _id(dados):
    try:
        return int((dados or {}).get('id'))
    except (TypeError, ValueError, AttributeError):
        return None


def _seguro(rotulo, nota_id, fn):
    try:
        fn()
    except ErroNota as e:
        db.session.rollback()
        emit('geonote_erro', {'id': nota_id, 'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO NOTA {rotulo}] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível {rotulo}: {e}'})


def _contexto(usuario, nota_id):
    """Carrega a nota e confere o que vale pra QUALQUER ação do leitor sobre ela: localização ligada, posição do aparelho, nota viva,
    sem bloqueio entre as pontas e dentro do alcance (2 km; 15 km se for amigo do autor). Devolve (nota, amigo_do_autor) ou None
    depois de ter avisado o motivo."""
    if not localizacao_ligada(usuario):
        emit('geonote_erro', {'id': nota_id, 'msg': MSG_LOCALIZACAO_DESLIGADA})
        return None
    if not _exigir_presenca():
        return None
    nota = com_retry(lambda: GeoNote.query.get(nota_id)) if nota_id else None
    if not nota or not notas_mapa.nota_viva(nota):
        emit('geonote_erro', {'id': nota_id, 'msg': 'Essa nota não está mais disponível.'})
        return None
    amigo = False
    if nota.author_id != usuario.id:
        rel = com_retry(lambda: relacao_entre(usuario.id, nota.author_id))
        if rel is not None and rel.status == 'blocked':
            emit('geonote_erro', {'id': nota_id, 'msg': 'Essa nota não está mais disponível.'})   # não revela o bloqueio
            return None
        amigo = rel is not None and rel.status == 'accepted'
    centro = centros_mapa.get(request.sid)
    raio = RAIO_SERVIDORES_M if amigo else RAIO_NOTAS_M
    if centro is None or distancia_m(centro[0], centro[1], nota.lat, nota.lng) > raio * 1.15:
        emit('geonote_erro', {'id': nota_id, 'msg': 'Essa nota está longe demais. Chegue mais perto.'})
        return None
    return nota, amigo


def _difundir(evento, payload, nota, so_amigos_do_autor):
    """Quem vê a nota (ou, com `so_amigos_do_autor`, só o autor e os amigos dele) + as abas do autor."""
    try:
        if not so_amigos_do_autor:
            _emitir_perto(evento, payload, nota.lat, nota.lng, RAIO_NOTAS_M)
        _avisar_amigos(evento, payload, nota.author)
        emit(evento, payload, to=sala_pessoal(nota.author_id))
    except Exception as e:
        print(f"[ERRO DIFUNDIR NOTA] {e}")


@socketio.on('geonote_responder')
def geonote_responder(dados):
    usuario = usuario_logado()
    nota_id = _id(dados)
    if not usuario or nota_id is None:
        return
    if _freio(usuario, 'responder', 1.2):
        emit('geonote_erro', {'id': nota_id, 'msg': 'Calma! Espere um instante pra responder de novo.'})
        return

    def tarefa():
        ctx = _contexto(usuario, nota_id)
        if not ctx:
            return
        nota, amigo = ctx
        resposta = notas_mapa.responder(usuario, nota, dados.get('texto'), amigo)
        payload = {'note_id': nota.id, 'resposta': resposta}
        modo = modo_resposta_da_nota(nota)
        _difundir('geonote_resposta', payload, nota, so_amigos_do_autor=(modo == 'amigos'))
        emit('geonote_resposta', payload, to=sala_pessoal(usuario.id))
        if nota.author_id != usuario.id:
            criar_notificacao(nota.author_id, 'nota', f'{usuario.name} respondeu à sua nota', resposta['texto'],
                              de_id=usuario.id, ref=str(nota.id))

    _seguro('responder à nota', nota_id, tarefa)


@socketio.on('geonote_reagir')
def geonote_reagir(dados):
    usuario = usuario_logado()
    nota_id = _id(dados)
    if not usuario or nota_id is None:
        return
    if _freio(usuario, 'reagir', 0.35):
        return

    def tarefa():
        ctx = _contexto(usuario, nota_id)
        if not ctx:
            return
        nota, _amigo = ctx
        totais, minhas = notas_mapa.reagir(usuario, nota, (dados or {}).get('emoji'), bool((dados or {}).get('ativo')))
        # Só os totais vão pra quem vê a nota (ninguém sabe quem reagiu); as reações da própria pessoa vão só pras abas dela.
        _difundir('geonote_reacoes', {'id': nota.id, 'reacoes': totais}, nota, so_amigos_do_autor=False)
        emit('geonote_reacoes', {'id': nota.id, 'reacoes': totais, 'minhas': minhas}, to=sala_pessoal(usuario.id))

    _seguro('reagir à nota', nota_id, tarefa)


@socketio.on('geonote_resposta_apagar')
def geonote_resposta_apagar(dados):
    usuario = usuario_logado()
    resposta_id = _id(dados)
    if not usuario or resposta_id is None:
        return
    if _freio(usuario, 'apagar_resposta', 0.35):
        return

    def tarefa():
        nota_id, rid, nota = notas_mapa.apagar_resposta(usuario, resposta_id)
        payload = {'id': rid, 'note_id': nota_id}
        if nota is not None:
            _difundir('geonote_resposta_apagada', payload, nota, so_amigos_do_autor=(modo_resposta_da_nota(nota) == 'amigos'))
        emit('geonote_resposta_apagada', payload, to=sala_pessoal(usuario.id))

    _seguro('apagar a resposta', None, tarefa)
