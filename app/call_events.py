"""Eventos extras da call (Rodada 34): convidar um amigo pra entrar na voz em que você está.

O pedido passa pelo servidor porque quem decide é ele: só quem está DE VERDADE na call convida, só um amigo, só pra um canal de
voz que o amigo pode ver (membro do servidor e, se o canal é privado, convidado dele). Quem não é do servidor não recebe nada:
o aviso diria o nome do servidor e do canal. Aviso ao vivo vai pra todas as abas do amigo (sala pessoal) e vira push se ele
está fora do app.
"""
import time

from flask import request
from flask_socketio import emit

from . import socketio, cargos
from .models import db, Person, Server, Channel
from .utils import com_retry, pode_ver_canal
from .events import usuario_logado, sala_pessoal, sao_amigos, esta_online, push_se_ausente, participantes_call, _call_por_sid, _meta_call

_ultimo_convite = {}                 # (quem, amigo) -> hora; uma pessoa não chama a outra de novo antes de 20 s
ESPERA_CONVITE_S = 20


@socketio.on('convidar_voz')
def convidar_voz(dados=None):
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    chave = str(dados.get('canal_id'))
    try:
        amigo_id = int(dados.get('amigo_id'))
    except (TypeError, ValueError):
        return
    atual = _call_por_sid.get(request.sid)
    meta = _meta_call.get(atual) if atual else None
    if not atual or atual[0] != chave or not meta or meta['usuario_id'] != usuario.id:
        return                                                        # só quem está nessa call convida pra ela
    if chave.startswith('dm_'):
        emit('erro_bazinga', {'msg': 'Essa é uma ligação só entre vocês dois. Convide pra um canal de voz de um servidor.'})
        return
    if not sao_amigos(usuario.id, amigo_id):
        emit('erro_bazinga', {'msg': 'Só dá pra convidar amigos.'})
        return
    try:
        canal = com_retry(lambda: Channel.query.get(int(chave)))
        amigo = com_retry(lambda: Person.query.get(amigo_id))
        if not canal or canal.channel_type not in cargos.TIPOS_VOZ or not amigo or not pode_ver_canal(amigo, canal):
            emit('erro_bazinga', {'msg': 'Essa pessoa ainda não está nesse servidor (ou não enxerga esse canal). Mande o convite do servidor primeiro.'})
            return
        if any(p['usuario_id'] == amigo_id for p in participantes_call.get(chave, [])):
            emit('voz_convite_enviado', {'amigo_id': amigo_id, 'ja_na_call': True})
            return
        agora = time.time()
        if agora - _ultimo_convite.get((usuario.id, amigo_id), 0) < ESPERA_CONVITE_S:
            emit('erro_bazinga', {'msg': 'Você acabou de chamar essa pessoa. Espere um pouquinho pra chamar de novo.'})
            return
        _ultimo_convite[(usuario.id, amigo_id)] = agora
        if len(_ultimo_convite) > 500:
            for k in [k for k, v in _ultimo_convite.items() if agora - v > 120]:
                _ultimo_convite.pop(k, None)
        srv = com_retry(lambda: Server.query.get(canal.server_id)) if canal.server_id else None
        if not srv:
            return
        socketio.emit('voz_convite', {
            'de_id': usuario.id, 'de_nome': usuario.name, 'de_avatar': usuario.avatar,
            'canal_id': canal.id, 'canal_nome': canal.name, 'server_id': srv.id, 'server_nome': srv.name,
        }, to=sala_pessoal(amigo_id))
        if not esta_online(amigo_id):
            push_se_ausente(amigo_id, f'{usuario.name} te chamou pra call', f'#{canal.name} em {srv.name}',
                            tag=f'voz-{usuario.id}', extra={'tipo': 'chamada', 'de_id': usuario.id, 'icone': usuario.avatar})
        emit('voz_convite_enviado', {'amigo_id': amigo_id})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CONVIDAR VOZ] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível convidar: {e}'})
