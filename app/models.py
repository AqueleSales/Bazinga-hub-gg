from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

# Inicializa o banco de dados
# expire_on_commit=False: por padrão o SQLAlchemy "esquece" todos os objetos a cada commit e relê
# cada um do banco no primeiro acesso depois (usuario.id, usuario.name...). Com o Neon cada leitura
# é uma ida de rede - um simples enviar_mensagem fazia ~8 SELECTs só pra reler a mesma pessoa.
# Cada evento/requisição tem a sua sessão, então não há dado velho circulando entre eles.
db = SQLAlchemy(session_options={'expire_on_commit': False})


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

    # Battle Pass: XP ganho mandando mensagem (com intervalo mínimo entre
    # ganhos - ver GANHO_XP_INTERVALO_SEGUNDOS em utils.py - senão dava pra
    # subir de nível só mandando mensagem vazia em loop).
    xp = db.Column(db.Integer, default=0, nullable=False)
    xp_ganho_em = db.Column(db.DateTime, nullable=True)
    # Sequência de dias seguidos entrando no app (bônus diário do Battle Pass).
    # `streak_em` é o último DIA (sem hora) em que o bônus foi pago.
    streak_dias = db.Column(db.Integer, default=0, nullable=False)
    streak_em = db.Column(db.Date, nullable=True)

    # Modo Fantasma mora no servidor (e não no localStorage) pra acompanhar a
    # pessoa entre dispositivos - e pra o servidor poder barrar a posição dela
    # de verdade, em vez de confiar que o navegador se comporta.
    ghost_mode = db.Column(db.Boolean, default=False, nullable=False)
    # Localização (Configurações > Geral). Também na conta. NULL = nunca mexeu = LIGADA (por isso a coluna é
    # anulável: contas antigas e a migração automática não têm DEFAULT). Desligada, o servidor recusa comprar/vender,
    # plantar servidor, deixar/copiar nota e o radar de amigos (ver localizacao_ligada em utils.py).
    localizacao_ativa = db.Column(db.Boolean, nullable=True)
    # Permite a posição aproximada por IP quando o aparelho não consegue achar a sua (só vale com a localização ligada).
    localizacao_ip = db.Column(db.Boolean, nullable=True)
    # Tema visual (ids em utils.TEMAS_VALIDOS: dark/light/amoled, os predefinidos e 'custom') - também na conta, pelo mesmo motivo.
    tema = db.Column(db.String(20), default='dark', nullable=False)
    # Só vale com tema == 'custom': JSON {base, cor, img, escuro, painel} já validado (utils.tema_custom_valido). Anulável: o boot cria a coluna sem DEFAULT.
    tema_custom = db.Column(db.Text, nullable=True)
    # Tema do CELULAR (o par tema/tema_custom acima é o do COMPUTADOR). Cada tipo de aparelho guarda e edita o seu; NULL = o celular ainda
    # não escolheu e usa o do computador (utils.tema_do_aparelho).
    tema_mobile = db.Column(db.String(20), nullable=True)
    tema_custom_mobile = db.Column(db.Text, nullable=True)

    # Perfil (editável na tela de Configurações)
    bio = db.Column(db.Text, nullable=True)
    custom_status = db.Column(db.String(128), nullable=True)
    banner_color = db.Column(db.String(50), nullable=True)
    # Faixa em imagem (prevalece sobre a cor) e pronomes - campos do cartão de perfil.
    banner_url = db.Column(db.String(255), nullable=True)
    # Enquadramento da faixa quando é GIF (que não dá pra recortar sem perder a animação):
    # 'x,y,zoom,espelhoH,espelhoV' em frações da área - aplicado por CSS no cartão.
    banner_ajuste = db.Column(db.String(60), nullable=True)
    pronomes = db.Column(db.String(40), nullable=True)
    # Nome da CONTA (@): o que se digita pra adicionar a pessoa. Único, minúsculo.
    # O nome de EXIBIÇÃO (`name`) é o enfeitado, pode repetir e mudar à vontade.
    username = db.Column(db.String(32), unique=True, nullable=True, index=True)
    # Emoji do status personalizado; vira a "bolinha" quando status == 'custom'.
    status_emoji = db.Column(db.String(16), nullable=True)
    # "Pensando agora": o texto do balão ao lado da foto (e o textinho embaixo do
    # nome nas listas). É separado do STATUS: `custom_status` passou a ser o texto
    # do status Personalizado (ex.: "Jogando Valorant"), que substitui o rótulo
    # "Disponível" quando a presença é `custom`.
    pensando = db.Column(db.String(128), nullable=True)
    # Tema do cartão: 'grad:#rrggbb,#rrggbb' | 'solid:#rrggbb' | 'img:<url>' | vazio
    perfil_tema = db.Column(db.String(300), nullable=True)
    # Enfeites (ids validados contra utils.ESTILOS_NOME / PLACAS / MOLDURAS)
    nome_estilo = db.Column(db.String(24), nullable=True)
    placa = db.Column(db.String(24), nullable=True)
    moldura = db.Column(db.String(24), nullable=True)
    # Cosméticos em slots extras (efeito de avatar/perfil/fala/radar/chat, som de entrada, pin de nota).
    # JSON {"efeito_avatar": "gogeta", ...}; só ids do catálogo com posse (ver cosmeticos.py).
    equipados = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="online")  # online, idle, dnd, invisible
    # Conta antiga (de antes dessa coluna existir) fica None de propósito -
    # não dá pra inventar uma data de quando a pessoa entrou de verdade.
    created_at = db.Column(db.DateTime, default=br_now, nullable=True)

    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)

    # Relacionamentos
    messages = db.relationship('Message', backref='author', lazy=True)


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
    # Cosmético do servidor (ícone na barra, cabeçalho e pino no mapa): id do catálogo (cosmeticos.py, tipo
    # 'efeito_servidor'). Só o dono aplica e só se tiver a posse do item.
    efeito = db.Column(db.String(24), nullable=True)

    # Relacionamentos
    # Quando o servidor for deletado, os canais somem junto (cascade)
    channels = db.relationship('Channel', backref='server', lazy=True, cascade="all, delete-orphan")
    invites = db.relationship('Invite', backref='server', lazy=True, cascade="all, delete-orphan")
    events = db.relationship('Event', backref='server', lazy=True, cascade="all, delete-orphan")

    # A lista de membros deste servidor!
    # lazy='select' (sob demanda). Era 'subquery' = TODA vez que um Server era carregado
    # (Server.query.get, usuario.servers...) vinham junto todas as linhas de todos os membros.
    members = db.relationship('Person', secondary=server_members, lazy='select',
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
    allowed_members = db.relationship('Person', secondary=channel_members, lazy='select',
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
    # Resposta (estilo WhatsApp): id da mensagem citada, no mesmo canal. Sem FK de propósito:
    # apagar a original não pode apagar nem travar a resposta (o cliente mostra "mensagem apagada").
    reply_to_id = db.Column(db.Integer, nullable=True)

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
    # pending (vale 24h a partir de created_at), accepted, blocked (quem bloqueou é o requester)
    status = db.Column(db.String(20), default='pending')

    created_at = db.Column(db.DateTime, default=br_now)

    # "Conversa rápida": nasceu de uma mensagem pra alguém que ainda não é amigo (sem pedido
    # de amizade explícito). As mensagens são temporárias: somem junto com a linha em 24h.
    rapida = db.Column(db.Boolean, default=False)
    # Cada ponta pode "fechar" a conversa só pra si (some do seu lado, a outra pessoa continua vendo).
    oculta_req = db.Column(db.Boolean, default=False)    # quem puxou a conversa fechou
    oculta_dest = db.Column(db.Boolean, default=False)   # quem recebeu recusou

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

    # Mensagem só de anexo (foto/gif/arquivo) vem com texto vazio.
    content = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=br_now)

    # Anexo (mesma regra de URL das mensagens de canal) e leitura (badge de não lidas).
    attachment_url = db.Column(db.String(500), nullable=True)
    attachment_type = db.Column(db.String(20), nullable=True)   # 'image' | 'video' | 'file'
    attachment_name = db.Column(db.String(255), nullable=True)
    lida = db.Column(db.Boolean, default=False)
    reply_to_id = db.Column(db.Integer, nullable=True)   # ver Message.reply_to_id

    sender = db.relationship('Person', foreign_keys=[sender_id])
    receiver = db.relationship('Person', foreign_keys=[receiver_id])


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
    # Emoji do balão (o ícone do pino) - separado do texto da nota.
    icone = db.Column(db.String(16), nullable=True)
    duration_hours = db.Column(db.Integer, default=24)
    # Escondida automaticamente quando recebe denúncias suficientes.
    oculta = db.Column(db.Boolean, default=False)

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
    oculta = db.Column(db.Boolean, default=False)

    # NOVO: Liga o Pino do Mapa ao Servidor Real de Chat
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=br_now)

    owner = db.relationship('Person', backref='map_servers', foreign_keys=[owner_id])
    server = db.relationship('Server', backref=db.backref('map_pin', uselist=False))


# ==========================================
# BATTLE PASS: progresso de missões (diárias/semanais)
# ------------------------------------------------------------
# As DEFINIÇÕES das missões vivem em código (utils.py, MISSOES) - aqui só
# o progresso de cada pessoa no período atual. `chave` = dia (YYYY-MM-DD) das
# diárias, ou a segunda-feira (YYYY-MM-DD) das semanais: virou o período, a
# chave muda e as missões novas nascem zeradas sem precisar apagar nada.
# Linhas com código começando em "_" são contadores internos (ex.: minutos
# ativos do dia), não aparecem pra pessoa.
# ==========================================
class MissaoProgresso(db.Model):
    __tablename__ = 'missao_progresso'
    __table_args__ = (db.UniqueConstraint('person_id', 'codigo', 'periodo', 'chave', name='uq_missao_periodo'),)
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    codigo = db.Column(db.String(40), nullable=False)
    periodo = db.Column(db.String(10), nullable=False)   # 'diaria' | 'semanal'
    chave = db.Column(db.String(10), nullable=False)
    progresso = db.Column(db.Integer, default=0, nullable=False)
    concluida = db.Column(db.Boolean, default=False, nullable=False)


# ==========================================
# DENÚNCIAS (notas e servidores plantados no mapa)
# ------------------------------------------------------------
# Uma por (denunciante, alvo). Com 3 denúncias de pessoas diferentes o alvo
# é escondido do mapa até alguém revisar (ver `denunciar` em events.py).
# ==========================================
class Denuncia(db.Model):
    __tablename__ = 'denuncia'
    __table_args__ = (db.UniqueConstraint('denunciante_id', 'tipo', 'alvo_id', name='uq_denuncia_unica'),)
    id = db.Column(db.Integer, primary_key=True)
    denunciante_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)        # 'nota' | 'servidor'
    alvo_id = db.Column(db.Integer, nullable=False)
    motivo = db.Column(db.String(30), nullable=False)      # +18, assedio, spam, ilegal, outro
    detalhe = db.Column(db.String(300), nullable=True)
    resolvida = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=br_now)


# ==========================================
# CAIXA DE ENTRADA (notificações que ficam guardadas)
# ------------------------------------------------------------
# DM, pedido de amizade e menção. A de DM é agregada por remetente (uma linha
# com contador) pra não virar 200 linhas numa conversa movimentada.
# ==========================================
class Notificacao(db.Model):
    __tablename__ = 'notificacao'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False)        # dm | amizade | mencao | sistema
    de_id = db.Column(db.Integer, nullable=True)           # quem originou
    titulo = db.Column(db.String(120), nullable=False)
    texto = db.Column(db.String(300), nullable=True)
    ref = db.Column(db.String(60), nullable=True)          # ex.: id do canal / da pessoa, pra abrir ao clicar
    quantidade = db.Column(db.Integer, default=1)
    lida = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=br_now)
    atualizada_em = db.Column(db.DateTime, default=br_now)


# ==========================================
# NOTIFICAÇÃO PUSH (aviso no aparelho com o app fechado)
# ------------------------------------------------------------
# Uma linha por navegador/aparelho inscrito. `endpoint` é único: se outra conta entrar no mesmo aparelho, a linha
# passa pra ela (ver /api/push/inscrever). ConfigApp guarda as chaves VAPID geradas no primeiro uso.
# ==========================================
class PushSub(db.Model):
    __tablename__ = 'push_sub'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    endpoint = db.Column(db.String(700), nullable=False, unique=True)
    p256dh = db.Column(db.String(200), nullable=False)
    auth = db.Column(db.String(100), nullable=False)
    user_agent = db.Column(db.String(250), nullable=True)
    created_at = db.Column(db.DateTime, default=br_now)


class ConfigApp(db.Model):
    __tablename__ = 'config_app'
    chave = db.Column(db.String(60), primary_key=True)
    valor = db.Column(db.Text, nullable=True)


class Silenciado(db.Model):
    """Contato que a pessoa silenciou: as mensagens dele continuam chegando, mas sem som,
    toast, badge nem caixa de entrada. Mora na conta (acompanha a pessoa em qualquer aparelho)."""
    __tablename__ = 'silenciado'
    __table_args__ = (db.UniqueConstraint('person_id', 'alvo_id', name='uq_silenciado'),)
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    alvo_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)


# ==========================================
# POSSE DE COSMÉTICOS (inventário)
# ------------------------------------------------------------
# Uma linha por (pessoa, item). `item_id` = "<tipo>:<id>" do catálogo em cosmeticos.py
# (ex.: "badge:criador", "moldura:gogeta"). Item livre não tem linha aqui: todo mundo
# tem. O servidor só aceita equipar item exclusivo se existir a linha (regra 4).
# ==========================================
class Posse(db.Model):
    __tablename__ = 'posse'
    __table_args__ = (db.UniqueConstraint('person_id', 'item_id', name='uq_posse_unica'),)
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    item_id = db.Column(db.String(60), nullable=False)
    origem = db.Column(db.String(20), default='sistema')   # laboratorio | loja | battlepass | sistema
    created_at = db.Column(db.DateTime, default=br_now)


# ==========================================
# LIVRO-RAZÃO DE DRC
# ------------------------------------------------------------
# Uma linha por movimento de moeda (ganho ou gasto), imutável: nunca se edita nem se apaga.
# `Person.bazinga_coins` continua sendo o saldo de leitura rápida, e `saldo_apos` guarda o
# que sobrou depois de cada movimento. Serve para auditar ("de onde veio esse saldo?"),
# resolver disputa de compra e, no futuro, detectar fraude. A tabela nasce pelo create_all.
# ==========================================
class MovimentoDrc(db.Model):
    __tablename__ = 'movimento_drc'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    delta = db.Column(db.Integer, nullable=False)          # + ganhou, - gastou
    saldo_apos = db.Column(db.Integer, nullable=True)
    motivo = db.Column(db.String(20), nullable=False)      # compra | nivel | missao | ajuste
    ref = db.Column(db.String(80), nullable=True)          # item_id da compra, "3->5" do nível...
    created_at = db.Column(db.DateTime, default=br_now)


class LojaEstoque(db.Model):
    """Quantas unidades de uma edição limitada do Armazém já foram vendidas. Uma linha por item limitado (nasce no 1º acesso).
    A compra é um `UPDATE ... SET vendidos = vendidos + 1 WHERE vendidos < limite`, então duas pessoas nunca levam a última unidade juntas."""
    __tablename__ = 'loja_estoque'
    item_id = db.Column(db.String(60), primary_key=True)
    vendidos = db.Column(db.Integer, nullable=False, default=0)


# ==========================================
# BAZAR DA COMUNIDADE (modelo A: classificados)
# ------------------------------------------------------------
# O app mostra loja e produto e organiza o pedido; o PAGAMENTO é Pix direto entre as duas pessoas, sem
# intermediário (o app só monta o "copia e cola" com a chave do vendedor). Não existe saldo nem escrow aqui.
# Quem vende tem UMA loja (`BazarLoja`); o `porte` decide como ela aparece: 'micro' = barraca de feira (os itens
# ficam aglomerados), 'media' = loja com fachada, 'grande' = parceira (só um admin define).
# Todas as tabelas nascem pelo create_all (sem ALTER).
# ==========================================
class BazarLoja(db.Model):
    __tablename__ = 'bazar_loja'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, unique=True)
    nome = db.Column(db.String(40), nullable=False)
    descricao = db.Column(db.String(300), nullable=True)
    categoria = db.Column(db.String(20), default='outros')
    porte = db.Column(db.String(8), default='micro')            # micro | media | grande (grande só por admin)
    regiao = db.Column(db.String(40), nullable=True)
    # Personalização: só ids conhecidos (bazar.py CORES/TOLDOS); o servidor nunca guarda texto livre que vire class/style.
    cor = db.Column(db.String(16), default='ambar')
    toldo = db.Column(db.String(16), default='vermelho')
    logo_url = db.Column(db.String(255), nullable=True)
    banner_url = db.Column(db.String(255), nullable=True)
    anuncio_titulo = db.Column(db.String(60), nullable=True)     # a "propaganda" da loja
    anuncio_texto = db.Column(db.String(160), nullable=True)
    # Pix do vendedor: só aparece pra quem tem um pedido aceito com ele.
    pix_chave = db.Column(db.String(80), nullable=True)
    pix_nome = db.Column(db.String(25), nullable=True)
    pix_cidade = db.Column(db.String(15), nullable=True)
    aberta = db.Column(db.Boolean, default=True)
    oculta = db.Column(db.Boolean, default=False)               # denúncias suficientes / moderação
    nota_soma = db.Column(db.Integer, default=0)
    nota_qtd = db.Column(db.Integer, default=0)
    vendas = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=br_now)
    # Rodada 18 (colunas novas: o boot cria sozinho, atualizar_banco.py também; tratar None como falso)
    verificada = db.Column(db.Boolean, default=False)           # selo "verificada": só um admin dá
    lat = db.Column(db.Float, nullable=True)                    # "perto de mim": posição ARREDONDADA (0,01° ~ 1 km), só se o dono pediu pra aparecer
    lng = db.Column(db.Float, nullable=True)

    owner = db.relationship('Person', foreign_keys=[owner_id])


class BazarProduto(db.Model):
    __tablename__ = 'bazar_produto'
    id = db.Column(db.Integer, primary_key=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('bazar_loja.id'), nullable=False, index=True)
    nome = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.String(600), nullable=True)
    preco_cent = db.Column(db.Integer, nullable=False)           # centavos de real (nunca float)
    tipo = db.Column(db.String(8), default='fisico')             # fisico | digital | servico
    imagens = db.Column(db.Text, nullable=True)                  # JSON: até 5 URLs (a 1ª é a capa)
    video_url = db.Column(db.String(255), nullable=True)
    estoque = db.Column(db.Integer, nullable=True)               # NULL = sem limite
    combo_itens = db.Column(db.Text, nullable=True)              # JSON: o que vem no combo (até 8 linhas)
    preco_avulso_cent = db.Column(db.Integer, nullable=True)     # soma dos itens avulsos (só pra mostrar o desconto do combo)
    entrega = db.Column(db.String(500), nullable=True)           # PRIVADO: link/instrução, o comprador só vê depois que o vendedor confirma o Pix
    ativo = db.Column(db.Boolean, default=True)
    oculta = db.Column(db.Boolean, default=False)
    vendidos = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=br_now)
    # Rodada 18: frete e retirada (só produto físico). frete_cent: NULL = não envia, 0 = frete grátis, >0 = valor somado ao total do pedido.
    frete_cent = db.Column(db.Integer, nullable=True)
    aceita_retirada = db.Column(db.Boolean, default=False)

    loja = db.relationship('BazarLoja', backref='produtos')


class BazarPedido(db.Model):
    """Um pedido = a intenção de compra + o combinado. Preço e nome são COPIADOS na hora (o produto pode mudar depois)."""
    __tablename__ = 'bazar_pedido'
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('bazar_produto.id'), nullable=False)
    loja_id = db.Column(db.Integer, db.ForeignKey('bazar_loja.id'), nullable=False, index=True)
    comprador_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    produto_nome = db.Column(db.String(80), nullable=False)
    quantidade = db.Column(db.Integer, default=1)
    preco_unit_cent = db.Column(db.Integer, nullable=False)
    total_cent = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(12), default='aguardando', index=True)   # aguardando|aceito|pago|confirmado|concluido|recusado|cancelado
    estoque_reservado = db.Column(db.Boolean, default=False)
    nota = db.Column(db.String(200), nullable=True)                       # recado do comprador na hora do pedido
    created_at = db.Column(db.DateTime, default=br_now)
    atualizado_em = db.Column(db.DateTime, default=br_now)
    # Rodada 18: como o comprador quer receber. total_cent = preço x quantidade + frete. O endereço é PRIVADO (só as duas pontas) e é apagado
    # quando o pedido termina (concluído/cancelado/recusado): guardar endereço de gente que já recebeu não serve a ninguém.
    entrega_modo = db.Column(db.String(10), nullable=True)                # envio | retirada | digital | combinar
    frete_cent = db.Column(db.Integer, nullable=True)
    endereco = db.Column(db.String(300), nullable=True)

    produto = db.relationship('BazarProduto')
    loja = db.relationship('BazarLoja')
    comprador = db.relationship('Person', foreign_keys=[comprador_id])
    vendedor = db.relationship('Person', foreign_keys=[vendedor_id])


class BazarMensagem(db.Model):
    """Conversa do pedido (só texto, sem link). Só as duas pessoas do pedido leem."""
    __tablename__ = 'bazar_mensagem'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('bazar_pedido.id'), nullable=False, index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    texto = db.Column(db.String(300), nullable=False)                     # '' quando é só imagem (comprovante)
    created_at = db.Column(db.DateTime, default=br_now)
    imagem_url = db.Column(db.String(255), nullable=True)                 # Rodada 18: comprovante/foto (só imagem do próprio app)


class BazarAvaliacao(db.Model):
    """Uma avaliação por pedido concluído, só do comprador."""
    __tablename__ = 'bazar_avaliacao'
    __table_args__ = (db.UniqueConstraint('pedido_id', name='uq_bazar_avaliacao_pedido'),)
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('bazar_pedido.id'), nullable=False)
    loja_id = db.Column(db.Integer, db.ForeignKey('bazar_loja.id'), nullable=False, index=True)
    avaliador_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    nota = db.Column(db.Integer, nullable=False)                          # 1 a 5
    texto = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=br_now)

    avaliador = db.relationship('Person', foreign_keys=[avaliador_id])


# ---- Rodada 18: favoritos, anúncios com data e clique, disputa e banimento (tabelas novas: nascem pelo create_all) ----
class BazarFavorito(db.Model):
    """Quem segue (favoritou) qual loja. Uma linha por par."""
    __tablename__ = 'bazar_favorito'
    __table_args__ = (db.UniqueConstraint('person_id', 'loja_id', name='uq_bazar_favorito'),)
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, index=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('bazar_loja.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=br_now)


class BazarAnuncio(db.Model):
    """Propaganda do carrossel do Bazar (só admin cria): arte própria, janela de datas e contagem de cliques."""
    __tablename__ = 'bazar_anuncio'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(60), nullable=False)
    texto = db.Column(db.String(160), nullable=True)
    imagem_url = db.Column(db.String(255), nullable=True)
    cor = db.Column(db.String(16), default='lavanda')            # id de bazar.CORES
    cta = db.Column(db.String(24), nullable=True)                # texto do botão
    destino = db.Column(db.String(10), default='nenhum')         # loja | link | painel | aviso | armazem | nenhum
    loja_id = db.Column(db.Integer, db.ForeignKey('bazar_loja.id'), nullable=True)
    link_url = db.Column(db.String(255), nullable=True)          # só https; abre fora do app depois de um aviso
    inicio = db.Column(db.DateTime, nullable=True)               # NULL = já começou
    fim = db.Column(db.DateTime, nullable=True)                  # NULL = sem fim
    ativo = db.Column(db.Boolean, default=True)
    cliques = db.Column(db.Integer, default=0)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=br_now)


class BazarDisputa(db.Model):
    """Uma das duas pontas pediu a análise de um admin. Abrir a disputa libera o admin a ler A CONVERSA DAQUELE PEDIDO (a tela avisa).
    O Pantheon não toca no dinheiro: a decisão só muda o estado do pedido e fica registrada; reembolso é combinado entre as pessoas."""
    __tablename__ = 'bazar_disputa'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('bazar_pedido.id'), nullable=False, index=True)
    aberta_por_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    motivo = db.Column(db.String(16), nullable=False)
    detalhe = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(10), default='aberta', index=True)   # aberta | resolvida
    resolucao = db.Column(db.String(10), nullable=True)               # concluir | cancelar | arquivar
    nota_admin = db.Column(db.String(300), nullable=True)
    resolvido_por_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=br_now)
    resolvido_em = db.Column(db.DateTime, nullable=True)


class BazarBanimento(db.Model):
    """Pessoa suspensa do Bazar (não vende, não compra, a loja some do feed). `ate` NULL = permanente. Desbanir apaga a linha."""
    __tablename__ = 'bazar_banimento'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False, unique=True)
    motivo = db.Column(db.String(200), nullable=True)
    por_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=br_now)
    ate = db.Column(db.DateTime, nullable=True)

    pessoa = db.relationship('Person', foreign_keys=[person_id])
