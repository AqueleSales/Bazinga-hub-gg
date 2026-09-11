from flask import Blueprint, render_template, session, jsonify, redirect, url_for
from sqlalchemy.exc import OperationalError, PendingRollbackError
from datetime import datetime
from sqlalchemy import or_, and_
from ..models import Person, Channel, Message, DirectMessage, Product, db

main_bp = Blueprint("main", __name__)


@main_bp.context_processor
def inject_user():
    user = None
    # Procura pelo 'user_id' que a nossa nova rota do Google salvou na Sessão
    if 'user_id' in session:
        try:
            user = Person.query.get(session['user_id'])
        except (OperationalError, PendingRollbackError):
            db.session.rollback()
    return dict(user=user)


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
    # O user já é injetado pelo context_processor, não precisa passar aqui!
    return render_template("index.html")


@main_bp.route("/chat")
def chat():
    if 'user_id' not in session:
        return redirect(url_for('main.index'))

    try:
        usuario_atual = Person.query.get(session['user_id'])
        if not usuario_atual:
            session.pop('user_id', None)
            return redirect(url_for('main.index'))

        text_channels = Channel.query.filter_by(channel_type="text").all()
        voice_channels = Channel.query.filter_by(channel_type="voice").all()
        default_channel = Channel.query.filter_by(name="geral").first()

        messages = []
        if default_channel:
            messages = Message.query.filter_by(channel_id=default_channel.id).order_by(Message.timestamp.asc()).limit(50).all()
            for m in messages:
                m.formatada = formatar_data(m.timestamp)

        # Busca todas as pessoas no banco (exceto você) para simular sua lista de amigos
        amigos = Person.query.filter(Person.id != usuario_atual.id).all()

    except (OperationalError, PendingRollbackError):
        db.session.rollback()
        return "Erro de conexão com o banco. Recarregue a página."

    return render_template(
        "chat.html",
        usuario_atual=usuario_atual,
        text_channels=text_channels,
        voice_channels=voice_channels,
        default_channel=default_channel,
        messages=messages,
        amigos=amigos
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
            'avatar': msg.author.avatar,
            'texto': msg.text,
            'hora': formatar_data(msg.timestamp),
            'cor': msg.author.role.color if msg.author.role else '#23a559'
        })

    return jsonify(dados)


# ==========================================
# Buscar histórico de Conexões Diretas (DMs)
# ==========================================
@main_bp.route("/api/dms/<int:target_id>")
def get_dms(target_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Acesso negado'}), 401

    meu_id = session['user_id']

    try:
        mensagens_db = DirectMessage.query.filter(
            or_(
                and_(DirectMessage.sender_id == meu_id, DirectMessage.receiver_id == target_id),
                and_(DirectMessage.sender_id == target_id, DirectMessage.receiver_id == meu_id)
            )
        ).order_by(DirectMessage.timestamp.asc()).limit(50).all()
    except (OperationalError, PendingRollbackError):
        db.session.rollback()
        mensagens_db = []

    dados = []
    for msg in mensagens_db:
        dados.append({
            'id': msg.id,
            'autor': msg.sender.name,
            'avatar': msg.sender.avatar,
            'texto': msg.content,
            'hora': formatar_data(msg.timestamp),
            'cor': msg.sender.role.color if msg.sender.role else '#5865F2'
        })

    return jsonify(dados)


# ==========================================
# ROTA DO MERCADO ELITE: Buscar Produtos
# ==========================================
@main_bp.route("/api/produtos")
def get_produtos():
    if 'user_id' not in session:
        return jsonify({'error': 'Acesso negado'}), 401

    try:
        produtos_db = Product.query.order_by(Product.created_at.desc()).all()
        dados = []
        for p in produtos_db:
            dados.append({
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price_bzc': p.price_bzc,
                'price_pix': p.price_pix,
                'image_url': p.image_url,
                'is_official': p.is_official,
                # Pega o nome do vendedor se existir, senão é a Bazinga Oficial
                'seller': p.seller.name if p.seller else 'Bazinga Oficial'
            })
        return jsonify(dados)
    except Exception as e:
        db.session.rollback()
        print("Erro na rota de produtos:", e)
        return jsonify([])