from flask import Blueprint, render_template, session, jsonify
from sqlalchemy.exc import OperationalError, PendingRollbackError
from datetime import datetime, timedelta
from ..models import Person, Channel, Message, db
from livekit import api

main_bp = Blueprint("main", __name__)


# Função unificada e corrigida para o Fuso de Brasília (UTC-3)
def formatar_data_br(data_utc):
    if not data_utc:
        return "Data desconhecida"

    hoje_br = datetime.utcnow() - timedelta(hours=3)
    data_br = data_utc - timedelta(hours=3)

    if data_br.date() == hoje_br.date():
        return f"Hoje às {data_br.strftime('%H:%M')}"
    elif data_br.date() == (hoje_br - timedelta(days=1)).date():
        return f"Ontem às {data_br.strftime('%H:%M')}"
    else:
        return f"{data_br.strftime('%d/%m/%Y')} às {data_br.strftime('%H:%M')}"


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/chat")
def chat():
    if 'person_id' not in session:
        try:
            usuario = Person.query.filter_by(name='Sales').first()
            if not usuario:
                usuario = Person(name='Sales', email='sales@teste.com')
                db.session.add(usuario)
                db.session.commit()
            session['person_id'] = usuario.id
        except (OperationalError, PendingRollbackError):
            db.session.rollback()
            return "Erro de conexão com o banco. Recarregue a página."

    try:
        usuario_atual = Person.query.get(session['person_id'])
        text_channels = Channel.query.filter_by(channel_type="text").all()
        voice_channels = Channel.query.filter_by(channel_type="voice").all()
        default_channel = Channel.query.filter_by(name="geral").first()

        messages = []
        if default_channel:
            messages = Message.query.filter_by(channel_id=default_channel.id).order_by(Message.timestamp.asc()).limit(
                50).all()
            for m in messages:
                # Usando a função atualizada de fuso horário
                m.formatada = formatar_data_br(m.timestamp)

    except (OperationalError, PendingRollbackError):
        db.session.rollback()
        usuario_atual = Person.query.get(session.get('person_id'))
        text_channels = []
        voice_channels = []
        default_channel = None
        messages = []

    return render_template(
        "chat.html",
        usuario_atual=usuario_atual,
        text_channels=text_channels,
        voice_channels=voice_channels,
        default_channel=default_channel,
        messages=messages
    )


@main_bp.route('/api/mensagens/<int:canal_id>')
def pegar_mensagens(canal_id):
    try:
        mensagens_db = Message.query.filter_by(channel_id=canal_id).order_by(Message.timestamp.asc()).limit(50).all()

        mensagens_formatadas = []
        for msg in mensagens_db:
            nome_usuario = msg.author.name if msg.author else "Desconhecido"
            cor = msg.author.role.color if msg.author and msg.author.role else "#23a559"

            mensagens_formatadas.append({
                "id": msg.id,
                "usuario": nome_usuario,
                "texto": msg.text,
                "hora": formatar_data_br(msg.timestamp),
                "cor": cor
            })

        return jsonify({"mensagens": mensagens_formatadas})

    except Exception as e:
        db.session.rollback()
        # Se algo falhar, imprime no seu terminal para você ler, mas não quebra o site
        print(f"\n[BAZINGA ERRO - API MENSAGENS] {e}\n")
        return jsonify({"mensagens": []})


@main_bp.route('/api/token_voz/<int:canal_id>')
def gerar_token_livekit(canal_id):
    if 'person_id' not in session:
        return jsonify({"erro": "Não autorizado"}), 403

    usuario_atual = Person.query.get(session['person_id'])

    # COLE AS SUAS CHAVES AQUI
    LIVEKIT_URL = "wss://SEU-PROJETO.livekit.cloud"
    LIVEKIT_API_KEY = "SUA_API_KEY"
    LIVEKIT_API_SECRET = "SEU_API_SECRET"

    nome_sala = f"canal-voz-{canal_id}"

    # O Flask assina o passaporte dizendo: "Esse cara pode entrar nessa sala"
    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(str(usuario_atual.id))
        .with_name(usuario_atual.name)
        .with_grants(api.VideoGrants(
            room_join=True,
            room=nome_sala,
        ))
    )

    return jsonify({"token": token.to_jwt(), "url": LIVEKIT_URL})