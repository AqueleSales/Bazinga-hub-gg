"""Eventos de Socket.IO do ACERVO (figurinhas e sons). A regra está em acervo.py; o arquivo entra por HTTP (acervo_routes.py).

  acervo_listar {server_id?}           -> acervo {meus, servidor, cotas, presets, som_entrada}  (só pra quem pediu)
  acervo_apagar {id} · acervo_renomear {id, nome, emoji}   -> acervo_mudou {server_id}       (pras abas de quem mexeu, ou o servidor, regra 6)
  som_entrada_definir {valor}          -> som_entrada_ok {valor}                               (todas as abas de quem mudou)
  soundboard_tocar {canal_id, item_id} -> soundboard_tocou {...}                               (a call inteira ouve)
Erro de regra volta como `acervo_erro {msg}`; erro inesperado, como `erro_bazinga` (regra 3).

Soundboard (o servidor decide, regra 4): só toca quem está de verdade na call (e não de ouvinte); o som tem que ser APROVADO e ser do próprio
acervo da pessoa ou do servidor DESSA call; intervalo de 2,5 s por pessoa e no máximo 12 sons a cada 20 s na call inteira.
O áudio é entregue pelo arquivo (/api/acervo/<id>/arquivo) e cada cliente toca no próprio volume, ou cala (por pessoa e por aparelho).
"""
import time

from flask import request

from .seguranca import emit
from . import acervo, socketio
from .models import db
from .events import usuario_logado, sala_pessoal, sala_servidor, _call_por_sid, _meta_call, participantes_call

INTERVALO_PESSOA_S = 2.5
TETO_CALL = (12, 20.0)            # 12 sons a cada 20 s na call
_ultimo = {}                      # pessoa -> instante
_historico = {}                   # chave da call -> [instantes]


def _dict(d):
    return d if isinstance(d, dict) else {}


def _avisar_mudou(item_ou_servidor, usuario):
    server_id = getattr(item_ou_servidor, 'server_id', item_ou_servidor)
    emit('acervo_mudou', {'server_id': server_id}, to=sala_servidor(server_id) if server_id else sala_pessoal(usuario.id))


@socketio.on('acervo_listar')
def acervo_listar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        emit('acervo', acervo.listar(usuario, _dict(dados).get('server_id')))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ACERVO LISTAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível abrir o acervo: {e}'})


@socketio.on('acervo_apagar')
def acervo_apagar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        item = acervo.AcervoItem.query.get(int(_dict(dados).get('id')))
        server_id = item.server_id if item else None
        acervo.apagar(usuario, _dict(dados).get('id'))
        _avisar_mudou(server_id, usuario)
    except acervo.ErroAcervo as e:
        emit('acervo_erro', {'msg': str(e)})
    except (TypeError, ValueError):
        return
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ACERVO APAGAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar: {e}'})


@socketio.on('acervo_renomear')
def acervo_renomear(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    try:
        item = acervo.renomear(usuario, d.get('id'), d.get('nome'), d.get('emoji'))
        _avisar_mudou(item, usuario)
    except acervo.ErroAcervo as e:
        emit('acervo_erro', {'msg': str(e)})
    except (TypeError, ValueError):
        return
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ACERVO RENOMEAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível renomear: {e}'})


@socketio.on('som_entrada_definir')
def som_entrada_definir(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    if 'valor' not in _dict(dados):
        return                                   # payload quebrado não pode zerar o som: pra voltar ao padrão o cliente manda valor null de propósito
    try:
        novo = acervo.definir_som_entrada(usuario, _dict(dados).get('valor'))
        # quem já está numa call leva o som novo na próxima vez que alguém entrar depois dele; a lista da call guarda o valor
        for (chave, peer), meta in list(_meta_call.items()):
            if meta['usuario_id'] == usuario.id:
                for p in participantes_call.get(chave, []):
                    if p['peer_id'] == peer:
                        p['som_entrada'] = novo
        emit('som_entrada_ok', {'valor': novo}, to=sala_pessoal(usuario.id))
    except acervo.ErroAcervo as e:
        emit('acervo_erro', {'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO SOM ENTRADA] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível trocar o som de entrada: {e}'})


@socketio.on('soundboard_tocar')
def soundboard_tocar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    chave = str(d.get('canal_id'))
    try:
        minha = _call_por_sid.get(request.sid)
        if not minha or minha[0] != chave:
            return
        eu = next((p for p in participantes_call.get(chave, []) if p['peer_id'] == minha[1]), None)
        if not eu or eu.get('ouvinte'):
            emit('acervo_erro', {'msg': 'Você está só ouvindo nesta call, então não pode tocar sons.'})
            return
        agora = time.monotonic()
        if agora - _ultimo.get(usuario.id, 0) < INTERVALO_PESSOA_S:
            return                                              # clique duplo/insistência: ignora em silêncio
        recentes = [t for t in _historico.get(chave, []) if agora - t < TETO_CALL[1]]
        if len(recentes) >= TETO_CALL[0]:
            emit('acervo_erro', {'msg': 'Muitos sons ao mesmo tempo nesta call. Espere um pouco.'})
            return
        item = acervo.item_usavel(usuario, d.get('item_id'), 'som')
        if not item:
            emit('acervo_erro', {'msg': 'Esse som não está disponível (ainda em análise, apagado ou de outro servidor).'})
            return
        if item.escopo == 'servidor' and item.server_id != (_meta_call.get(minha) or {}).get('server_id'):
            emit('acervo_erro', {'msg': 'Os sons de um servidor só tocam nas calls dele.'})
            return
        _ultimo[usuario.id] = agora
        recentes.append(agora)
        _historico[chave] = recentes
        socketio.emit('soundboard_tocou', {'canal_id': chave, 'item_id': item.id, 'nome': item.nome, 'emoji': item.emoji, 'dur_ms': item.dur_ms,
                                           'por_id': usuario.id, 'por_nome': usuario.name}, to=f"voz_{chave}")
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO SOUNDBOARD] {e}")
