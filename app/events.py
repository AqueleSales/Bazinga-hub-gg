from flask_socketio import emit, join_room, leave_room
from sqlalchemy.exc import OperationalError, PendingRollbackError
from . import socketio
from .models import db, Message, Person
from datetime import datetime


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
    # Pega o usuário que veio do JS
    nome_usuario = dados.get('usuario', 'Desconhecido')

    try:
        usuario = Person.query.filter_by(name=nome_usuario).first()
        if not usuario:
            usuario = Person(name=nome_usuario, email=f"{nome_usuario}@teste.com")
            db.session.add(usuario)
            db.session.commit()

        canal_id = str(dados['canal_id'])

        nova_msg = Message(
            text=dados['texto'],
            person_id=usuario.id,
            channel_id=int(canal_id)
        )
        db.session.add(nova_msg)
        db.session.commit()

    except (OperationalError, PendingRollbackError):

        db.session.rollback()

        return  # Falha silenciosa para não crachar o servidor

    cor = usuario.role.color if usuario.role else '#23a559'

    # IMPORTANTE: Converte o horário do banco (UTC) para Brasília (UTC-3)

    from datetime import timedelta

    hora_br = nova_msg.timestamp - timedelta(hours=3)

    emit('receber_mensagem', {

        'id': nova_msg.id,

        'usuario': usuario.name,

        'texto': nova_msg.text,

        'hora': f"Hoje às {hora_br.strftime('%H:%M')}",

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
            # Manda o aviso de exclusão pra todo mundo na sala
            emit('mensagem_apagada', {'msg_id': msg_id}, to=canal_id)
    except (OperationalError, PendingRollbackError):
        db.session.rollback()


@socketio.on('entrar_call')
def lidar_entrar_call(dados):
    canal_id = str(dados['canal_id'])
    peer_id = dados['peer_id']
    nome_usuario = dados['usuario']

    sala_call = f"voz_{canal_id}"
    join_room(sala_call)

    # Avisa todos na sala de voz (menos o recém-chegado) para ligarem pra ele
    emit('novo_usuario_call', {'peer_id': peer_id, 'usuario': nome_usuario}, to=sala_call, include_self=False)


@socketio.on('sair_call')
def lidar_sair_call(dados):
    canal_id = str(dados['canal_id'])
    peer_id = dados['peer_id']
    sala_call = f"voz_{canal_id}"

    leave_room(sala_call)
    emit('usuario_saiu_call', {'peer_id': peer_id}, to=sala_call, include_self=False)