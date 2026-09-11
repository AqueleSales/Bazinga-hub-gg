from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Inicializa o banco de dados
db = SQLAlchemy()


class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(20), nullable=True, default="#23a559")

    # Relacionamento: Um cargo pode ter várias pessoas
    users = db.relationship('Person', backref='role', lazy=True)


class Person(db.Model):
    __tablename__ = 'person'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # CAMPOS PARA O LOGIN OAUTH (GOOGLE/DISCORD)
    email = db.Column(db.String(120), unique=True, nullable=False)
    avatar = db.Column(db.String(255), nullable=True)  # URL da foto de perfil
    provider_id = db.Column(db.String(100), nullable=True)  # ID único devolvido pelo Google

    # NOVO: Carteira do Usuário (Começa com 500 moedas de brinde)
    bazinga_coins = db.Column(db.Integer, default=500)

    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)

    # Relacionamento: Uma pessoa tem várias mensagens de canal
    messages = db.relationship('Message', backref='author', lazy=True)

    # NOVO: Relacionamento: Produtos que essa pessoa colocou à venda no Bazar
    products_for_sale = db.relationship('Product', backref='seller', lazy=True)


class Channel(db.Model):
    __tablename__ = 'channel'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    channel_type = db.Column(db.String(20), default='text')  # Pode ser 'text' ou 'voice'

    # Relacionamento: Um canal tem várias mensagens
    messages = db.relationship('Message', backref='channel', lazy=True)


class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)


# Tabela para salvar as DMs (Conexões Diretas)
class DirectMessage(db.Model):
    __tablename__ = 'direct_message'
    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)

    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos para puxar os nomes e avatares fácil depois
    sender = db.relationship('Person', foreign_keys=[sender_id])
    receiver = db.relationship('Person', foreign_keys=[receiver_id])


# ==========================================
# Tabela de Produtos do Mercado Elite
# ==========================================
class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Preços (Separados para ficar compatível com o seed_loja.py)
    price_bzc = db.Column(db.Integer, nullable=True)
    price_pix = db.Column(db.Float, nullable=True)

    image_url = db.Column(db.String(255), nullable=True)

    # is_official = True (Loja Bazinga) | is_official = False (Bazar da Comunidade)
    is_official = db.Column(db.Boolean, default=False)

    # Se for um item do Bazar, quem está vendendo? (Se for da Loja Oficial, fica nulo)
    seller_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==========================================
# NOVAS TABELAS: Mapa (GeoNotes e Servidores)
# ==========================================
class GeoNote(db.Model):
    __tablename__ = 'geo_note'
    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    text = db.Column(db.Text, nullable=False)

    # NOVAS COLUNAS: Cor e Duração
    color = db.Column(db.String(20), default="var(--brand-color)")
    duration_hours = db.Column(db.Integer, default=24)

    author_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('Person', backref='geonotes')


class MapServer(db.Model):
    __tablename__ = 'map_server'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)

    # NOVAS COLUNAS: Limite de Vagas e Duração
    max_tickets = db.Column(db.Integer, nullable=True)  # Nulo = Ilimitado
    duration_hours = db.Column(db.Integer, nullable=True)  # Nulo = Permanente

    owner_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship('Person', backref='map_servers')