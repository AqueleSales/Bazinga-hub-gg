from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

# Inicializa o banco de dados
db = SQLAlchemy()


# Utilitário: Definindo o fuso horário de Brasília para todas as tabelas
def br_now():
    """Agora, no horário de Brasília, SEM tzinfo.

    Todas as colunas de data aqui são `db.DateTime` (TIMESTAMP sem fuso), que
    guardam só a hora de parede. Se esta função devolvesse um datetime com
    fuso, gravar funcionaria (o driver descarta o tzinfo), mas qualquer
    comparação em Python - `br_now() >= convite.expires_at`, por exemplo -
    estouraria com "can't compare offset-naive and offset-aware datetimes",
    já que o valor lido do banco volta sem fuso.
    """
    return datetime.now(pytz.timezone('America/Sao_Paulo')).replace(tzinfo=None)


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
    # Conta antiga (de antes dessa coluna existir) fica None de propósito -
    # não dá pra inventar uma data de quando a pessoa entrou de verdade.
    created_at = db.Column(db.DateTime, default=br_now, nullable=True)

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

    # Configurações editáveis depois da criação
    description = db.Column(db.Text, nullable=True)
    banner_color = db.Column(db.String(50), nullable=True)

    # Relacionamentos
    # Quando o servidor for deletado, os canais somem junto (cascade)
    channels = db.relationship('Channel', backref='server', lazy=True, cascade="all, delete-orphan")
    invites = db.relationship('Invite', backref='server', lazy=True, cascade="all, delete-orphan")
    events = db.relationship('Event', backref='server', lazy=True, cascade="all, delete-orphan")

    # A lista de membros deste servidor!
    members = db.relationship('Person', secondary=server_members, lazy='subquery',
                              backref=db.backref('servers', lazy=True))

    owner = db.relationship('Person', foreign_keys=[owner_id])


# Quem pode entrar num canal PRIVADO. Canal público ignora esta tabela.
# O dono do servidor sempre tem acesso, esteja aqui ou não.
channel_members = db.Table('channel_members',
                           db.Column('channel_id', db.Integer, db.ForeignKey('channel.id'), primary_key=True),
                           db.Column('person_id', db.Integer, db.ForeignKey('person.id'), primary_key=True)
                           )


class Channel(db.Model):
    __tablename__ = 'channel'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    channel_type = db.Column(db.String(20), default='text')  # 'text' ou 'voice'

    # Canal pode pertencer a um Servidor criado por um usuário. Nulo = canal
    # padrão do "Bazinga Hub" (o servidor global inicial, fora do sistema de Servers).
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)

    # Configurações do canal
    topic = db.Column(db.String(255), nullable=True)   # "assunto" mostrado no header
    is_private = db.Column(db.Boolean, default=False)  # só o dono e convidados veem
    position = db.Column(db.Integer, default=0)        # ordem na sidebar

    # Relacionamento: Um canal tem várias mensagens
    messages = db.relationship('Message', backref='channel', lazy=True, cascade="all, delete-orphan")

    # Só vale quando is_private=True
    allowed_members = db.relationship('Person', secondary=channel_members, lazy='subquery',
                                      backref=db.backref('canais_privados', lazy=True))


class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    # Mensagem só de anexo (foto/vídeo/gif) vem com texto vazio, por isso
    # nullable=True aqui - antes era obrigatório ter texto.
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=br_now)

    # Anexo: imagem, gif ou vídeo. Guarda a URL já processada (comprimida no
    # navegador antes do upload) e o tipo, pra saber se renderiza <img> ou <video>.
    attachment_url = db.Column(db.String(500), nullable=True)
    attachment_type = db.Column(db.String(20), nullable=True)  # 'image' | 'video'
    attachment_name = db.Column(db.String(255), nullable=True)

    edited_at = db.Column(db.DateTime, nullable=True)
    is_pinned = db.Column(db.Boolean, default=False)

    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)

    reactions = db.relationship('Reaction', backref='message', lazy=True, cascade="all, delete-orphan")


class Reaction(db.Model):
    """Uma reação de emoji de uma pessoa numa mensagem.

    Uma linha por (mensagem, pessoa, emoji) - a contagem é feita agrupando,
    e a unicidade impede a mesma pessoa reagir duas vezes com o mesmo emoji.
    """
    __tablename__ = 'reaction'
    id = db.Column(db.Integer, primary_key=True)

    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    emoji = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, default=br_now)

    person = db.relationship('Person', foreign_keys=[person_id])

    __table_args__ = (
        db.UniqueConstraint('message_id', 'person_id', 'emoji', name='uq_reacao_unica'),
    )


class Invite(db.Model):
    """Convite para entrar num servidor, por link ou QR code.

    O `code` é o que vai na URL (/convite/<code>) e dentro do QR.
    """
    __tablename__ = 'invite'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)

    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)

    expires_at = db.Column(db.DateTime, nullable=True)  # Nulo = nunca expira
    max_uses = db.Column(db.Integer, nullable=True)     # Nulo = ilimitado
    uses = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=br_now)

    creator = db.relationship('Person', foreign_keys=[creator_id])

    def esta_valido(self):
        if self.expires_at is not None and br_now() >= self.expires_at:
            return False
        if self.max_uses is not None and (self.uses or 0) >= self.max_uses:
            return False
        return True


class Event(db.Model):
    """Evento do calendário de um servidor."""
    __tablename__ = 'event'
    id = db.Column(db.Integer, primary_key=True)

    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)

    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)

    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=True)

    # Enfeite do quadradinho no calendário
    emoji = db.Column(db.String(16), nullable=True, default="🎉")
    color = db.Column(db.String(20), nullable=True, default="#5865F2")

    created_at = db.Column(db.DateTime, default=br_now)

    creator = db.relationship('Person', foreign_keys=[creator_id])


class Friendship(db.Model):
    """Uma linha por par (quem pediu -> quem recebeu). Aceita vira amizade nos
    dois sentidos - quem consulta procura o outro id tanto em requester_id
    quanto em addressee_id (ver amigos_de() em events.py)."""
    __tablename__ = 'friendship'
    id = db.Column(db.Integer, primary_key=True)

    requester_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    addressee_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted

    created_at = db.Column(db.DateTime, default=br_now)

    requester = db.relationship('Person', foreign_keys=[requester_id])
    addressee = db.relationship('Person', foreign_keys=[addressee_id])

    __table_args__ = (
        db.UniqueConstraint('requester_id', 'addressee_id', name='uq_pedido_unico'),
    )


class DirectMessage(db.Model):
    __tablename__ = 'direct_message'
    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)

    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=br_now)

    sender = db.relationship('Person', foreign_keys=[sender_id])
    receiver = db.relationship('Person', foreign_keys=[receiver_id])


class Purchase(db.Model):
    """Compra efetivada na loja.

    Sem isso a rota de compra só descontava as Bazinga Coins e não registrava
    nada - o usuário pagava e não recebia (nem dava pra auditar depois).
    """
    __tablename__ = 'purchase'
    id = db.Column(db.Integer, primary_key=True)

    buyer_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

    # Quanto custou no momento da compra (o preço do produto pode mudar depois)
    price_paid_bzc = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=br_now)

    buyer = db.relationship('Person', backref='purchases', foreign_keys=[buyer_id])
    product = db.relationship('Product', backref='purchases')


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
