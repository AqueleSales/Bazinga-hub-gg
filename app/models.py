from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

# Inicializa o banco de dados
db = SQLAlchemy()


# Utilitário: Definindo o fuso horário de Brasília para todas as tabelas
def br_now():
    return datetime.now(pytz.timezone('America/Sao_Paulo'))


class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(20), nullable=True, default="#23a559")

    # Relacionamento: Um cargo pode ter várias pessoas
    users = db.relationship('Person', backref='role', lazy=True)


# ==========================================
# NOVO: Tabela de Associação (Muitos para Muitos)
# Liga os Usuários aos Servidores que eles participam
# ==========================================
server_members = db.Table('server_members',
                          db.Column('person_id', db.Integer, db.ForeignKey('person.id'), primary_key=True),
                          db.Column('server_id', db.Integer, db.ForeignKey('server.id'), primary_key=True),
                          db.Column('joined_at', db.DateTime, default=br_now)
                          )


class Person(db.Model):
    __tablename__ = 'person'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # CAMPOS PARA O LOGIN OAUTH (GOOGLE/DISCORD)
    email = db.Column(db.String(120), unique=True, nullable=False)
    avatar = db.Column(db.String(255), nullable=True)  # URL da foto de perfil
    provider_id = db.Column(db.String(100), nullable=True)  # ID único devolvido pelo Google

    # Carteira do Usuário (Começa com 500 moedas de brinde)
    bazinga_coins = db.Column(db.Integer, default=500)

    # Perfil (editável na tela de Configurações)
    bio = db.Column(db.Text, nullable=True)
    custom_status = db.Column(db.String(128), nullable=True)
    banner_color = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default="online")  # online, idle, dnd, invisible

    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)

    # Relacionamentos
    messages = db.relationship('Message', backref='author', lazy=True)
    products_for_sale = db.relationship('Product', backref='seller', lazy=True)


# ==========================================
# NOVO: O Servidor Real (Chat)
# ==========================================
class Server(db.Model):
    __tablename__ = 'server'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    owner_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    icon_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=br_now)

    # Relacionamentos
    # Quando o servidor for deletado, os canais somem junto (cascade)
    channels = db.relationship('Channel', backref='server', lazy=True, cascade="all, delete-orphan")

    # A lista de membros deste servidor!
    members = db.relationship('Person', secondary=server_members, lazy='subquery',
                              backref=db.backref('servers', lazy=True))

    owner = db.relationship('Person', foreign_keys=[owner_id])


class Channel(db.Model):
    __tablename__ = 'channel'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    channel_type = db.Column(db.String(20), default='text')  # 'text' ou 'voice'

    # Canal pode pertencer a um Servidor criado por um usuário. Nulo = canal
    # padrão do "Bazinga Hub" (o servidor global inicial, fora do sistema de Servers).
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)

    # Relacionamento: Um canal tem várias mensagens
    messages = db.relationship('Message', backref='channel', lazy=True, cascade="all, delete-orphan")


class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=br_now)

    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)


class DirectMessage(db.Model):
    __tablename__ = 'direct_message'
    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)

    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=br_now)

    sender = db.relationship('Person', foreign_keys=[sender_id])
    receiver = db.relationship('Person', foreign_keys=[receiver_id])


class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

    price_bzc = db.Column(db.Integer, nullable=True)
    price_pix = db.Column(db.Float, nullable=True)

    image_url = db.Column(db.String(255), nullable=True)
    is_official = db.Column(db.Boolean, default=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=br_now)


# ==========================================
# MAPA: GeoNotes e Servidores Plantados
# ==========================================
class GeoNote(db.Model):
    __tablename__ = 'geo_note'
    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    text = db.Column(db.Text, nullable=False)

    color = db.Column(db.String(20), default="var(--brand-color)")
    duration_hours = db.Column(db.Integer, default=24)

    # NOVO: Data exata em que a nota deve expirar
    expires_at = db.Column(db.DateTime, nullable=True)

    author_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=br_now)

    author = db.relationship('Person', backref='geonotes')


class MapServer(db.Model):
    __tablename__ = 'map_server'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)

    max_tickets = db.Column(db.Integer, nullable=True)  # Nulo = Ilimitado
    duration_hours = db.Column(db.Integer, nullable=True)  # Nulo = Permanente

    # NOVO: Data exata em que o pino some do mapa
    expires_at = db.Column(db.DateTime, nullable=True)

    owner_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)

    # NOVO: Liga o Pino do Mapa ao Servidor Real de Chat
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=br_now)

    owner = db.relationship('Person', backref='map_servers', foreign_keys=[owner_id])
    server = db.relationship('Server', backref=db.backref('map_pin', uselist=False))
