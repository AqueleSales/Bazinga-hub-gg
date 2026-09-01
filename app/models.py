from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
# Importa o timezone para lidar melhor com o horário do Brasil (opcional, mas recomendado)
from pytz import timezone

db = SQLAlchemy()


# 1. Tabela de Cargos (Roles)
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # Ex: "MODERADORES"
    color = db.Column(db.String(10), default="#949ba4")  # Cor do cargo em Hex


# 2. Tabela de Usuários (Person) - Mantendo o nome que você usava no Bazingawards
class Person(db.Model):
    __tablename__ = 'person'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    avatar = db.Column(db.String(255), nullable=True)  # URL da foto do Google/Discord

    # Chave estrangeira ligando o usuário a um cargo
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    role = db.relationship('Role', backref='members')

    # Relação com as mensagens
    messages = db.relationship('Message', backref='author', lazy=True)


# 3. Tabela de Canais
class Channel(db.Model):
    __tablename__ = 'channels'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # Ex: "geral"
    channel_type = db.Column(db.String(20), default="text")  # "text" ou "voice"

    messages = db.relationship('Message', backref='channel', lazy=True)


# 4. Tabela de Mensagens
class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)