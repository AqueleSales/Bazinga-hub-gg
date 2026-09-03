from flask import Blueprint, render_template, session, jsonify, redirect, url_for
from sqlalchemy.exc import OperationalError, PendingRollbackError
from datetime import datetime
from ..models import Person, Channel, Message, db

main_bp = Blueprint("main", __name__)


def formatar_data(ts):
    if not ts: return ""
    hoje = datetime.now().date()
    data_msg = ts.date()
    hora_str = ts.strftime('%H:%M')

    if data_msg == hoje:
        return f"Hoje às {hora_str}"
    elif (hoje - data_msg).days == 1:
        return f"Ontem às {hora_str}"
    else:
        return f"{ts.strftime('%d/%m/%Y')} às {hora_str}"


@main_bp.route("/")
def index():
    # Se a pessoa estiver logada, pegamos os dados dela para enviar para o Hub (ex: fotinha na Navbar)
    user = None
    if 'person_id' in session:
        try:
            user = Person.query.get(session['person_id'])
        except (OperationalError, PendingRollbackError):
            db.session.rollback()

    return render_template("index.html", user=user)


@main_bp.route("/chat")
def chat():
    # --- O GUARDIÃO ---
    # Se não tiver a sessão (ou seja, não logou pelo Google), volta pra página inicial!
    if 'person_id' not in session:
        return redirect(url_for('main.index'))

    try:
        # Pega as informações de quem está logado lá no Neon
        usuario_atual = Person.query.get(session['person_id'])

        # Proteção extra: se resetarmos o banco e o ID sumir de lá, desloga o cara na marra
        if not usuario_atual:
            session.pop('person_id', None)
            return redirect(url_for('main.index'))

        text_channels = Channel.query.filter_by(channel_type="text").all()
        voice_channels = Channel.query.filter_by(channel_type="voice").all()
        default_channel = Channel.query.filter_by(name="geral").first()

        messages = []
        if default_channel:
            messages = Message.query.filter_by(channel_id=default_channel.id).order_by(Message.timestamp.asc()).limit(
                50).all()
            for m in messages:
                m.formatada = formatar_data(m.timestamp)

    except (OperationalError, PendingRollbackError):
        db.session.rollback()
        return "Erro de conexão com o banco. Recarregue a página."

    # Agora injetamos o usuário REAl que veio do Google direto no seu chat.html
    return render_template(
        "chat.html",
        usuario_atual=usuario_atual,
        text_channels=text_channels,
        voice_channels=voice_channels,
        default_channel=default_channel,
        messages=messages
    )


@main_bp.route("/api/mensagens/<int:canal_id>")
def pegar_mensagens(canal_id):
    try:
        mensagens_db = Message.query.filter_by(channel_id=canal_id).order_by(Message.timestamp.asc()).limit(50).all()
    except (OperationalError, PendingRollbackError):
        db.session.rollback()
        mensagens_db = Message.query.filter_by(channel_id=canal_id).order_by(Message.timestamp.asc()).limit(50).all()

    dados = []
    for msg in mensagens_db:
        dados.append({
            'id': msg.id,
            'autor': msg.author.name,
            'texto': msg.text,
            'hora': formatar_data(msg.timestamp),
            'cor': msg.author.role.color if msg.author.role else '#23a559'
        })

    return jsonify(dados)