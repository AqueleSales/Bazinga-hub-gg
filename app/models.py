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

    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)

    # Relacionamento: Uma pessoa tem várias mensagens de canal
    messages = db.relationship('Message', backref='author', lazy=True)


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

    # CORREÇÃO: Apontando para person.id em vez de user.id
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)


# Tabela para salvar as DMs (Conexões Diretas)
class DirectMessage(db.Model):
    __tablename__ = 'direct_message'
    id = db.Column(db.Integer, primary_key=True)

    # CORREÇÃO: Apontando para person.id em vez de user.id
    sender_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)

    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos para puxar os nomes e avatares fácil depois
    sender = db.relationship('Person', foreign_keys=[sender_id])
    receiver = db.relationship('Person', foreign_keys=[receiver_id])