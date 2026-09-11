from flask import session
from flask_socketio import emit, join_room, leave_room
from sqlalchemy.exc import OperationalError, PendingRollbackError
from datetime import timedelta
from . import socketio
from .models import db, Message, Person, DirectMessage


@socketio.on('entrar_canal')
def handle_join(dados):
    canal_id = str(dados['canal_id'])
    join_room(canal_id)


@socketio.on('sair_canal')
def handle_leave(dados):
    canal_id = str(dados['canal_id'])
    leave_room(canal_id)


@socketio.on('enviar_mensagem')
def lidar_com_mensagem(dados):
    user_id = session.get('user_id')
    if not user_id:
        return

    try:
        usuario = Person.query.get(user_id)
        if not usuario:
            return

        canal_id = str(dados['canal_id'])

        nova_msg = Message(
            text=dados['texto'],
            person_id=usuario.id,
            channel_id=int(canal_id)
        )
        db.session.add(nova_msg)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CHAT GERAL] Não foi possível salvar: {e}")
        return

    cor = usuario.role.color if usuario.role else '#23a559'
    hora_br = nova_msg.timestamp - timedelta(hours=3)
    hora_formatada = f"Hoje às {hora_br.strftime('%H:%M')}"

    emit('receber_mensagem', {
        'id': nova_msg.id,
        'usuario': usuario.name,
        'avatar': usuario.avatar,
        'texto': nova_msg.text,
        'hora': hora_formatada,
        'cor': cor
    }, to=canal_id)


@socketio.on('apagar_mensagem')
def lidar_com_exclusao(dados):
    msg_id = dados.get('msg_id')
    try:
        msg = Message.query.get(msg_id)
        if msg:
            canal_id = str(msg.channel_id)
            db.session.delete(msg)
            db.session.commit()
            emit('mensagem_apagada', {'msg_id': msg_id}, to=canal_id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO AO APAGAR] {e}")


@socketio.on('entrar_call')
def lidar_entrar_call(dados):
    canal_id = str(dados['canal_id'])
    peer_id = dados['peer_id']
    nome_usuario = dados['usuario']

    sala_call = f"voz_{canal_id}"
    join_room(sala_call)

    user_id = session.get('user_id')
    avatar = None
    if user_id:
        try:
            usuario = Person.query.get(user_id)
            if usuario:
                avatar = usuario.avatar
        except Exception as e:
            db.session.rollback()

    emit('novo_usuario_call', {
        'peer_id': peer_id,
        'usuario': nome_usuario,
        'avatar': avatar,
        'canal_id': canal_id
    }, to=sala_call, include_self=False)


@socketio.on('sair_call')
def lidar_sair_call(dados):
    canal_id = str(dados['canal_id'])
    peer_id = dados['peer_id']
    sala_call = f"voz_{canal_id}"

    leave_room(sala_call)
    emit('usuario_saiu_call', {'peer_id': peer_id}, to=sala_call, include_self=False)


# ==========================================
# EVENTOS PARA MENSAGENS DIRETAS (DMs)
# ==========================================
@socketio.on('entrar_dm')
def on_entrar_dm(data):
    user_id = session.get('user_id')
    if not user_id:
        return

    target_id = int(data.get('target_id'))
    room = f"dm_{min(user_id, target_id)}_{max(user_id, target_id)}"
    join_room(room)
    print(f"[SISTEMA] Usuário {user_id} entrou na sala de DM: {room}")


@socketio.on('enviar_mensagem_direta')
def on_enviar_mensagem_direta(data):
    user_id = session.get('user_id')
    if not user_id:
        print("[ERRO DM] Usuário não está logado na sessão.")
        return

    target_id = int(data.get('target_id'))
    texto = data.get('texto')

    try:
        usuario = Person.query.get(user_id)
        if not usuario:
            print("[ERRO DM] Usuário não encontrado no banco.")
            return

        # 1. Tenta salvar no banco de dados (Se o target_id não existir, vai dar erro aqui)
        nova_msg = DirectMessage(sender_id=user_id, receiver_id=target_id, content=texto)
        db.session.add(nova_msg)
        db.session.commit()

        print(f"[SUCESSO] DM salva no banco! De: {user_id} Para: {target_id}")

        hora_br = nova_msg.timestamp - timedelta(hours=3)
        hora_formatada = f"Hoje às {hora_br.strftime('%H:%M')}"

        # 2. Envia para a sala privada
        room = f"dm_{min(user_id, target_id)}_{max(user_id, target_id)}"
        cor = usuario.role.color if usuario.role else '#5865F2'

        emit('receber_mensagem_direta', {
            'id': nova_msg.id,
            'usuario': usuario.name,
            'usuario_id': usuario.id,
            'avatar': usuario.avatar,
            'texto': texto,
            'hora': hora_formatada,
            'cor': cor
        }, room=room)

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRÍTICO NA DM] O banco bloqueou o salvamento: {e}")
        return