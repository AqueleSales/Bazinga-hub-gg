from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request, current_app
from sqlalchemy.exc import OperationalError, PendingRollbackError, SQLAlchemyError
from sqlalchemy import or_, and_
import os
import uuid
import cloudinary
import cloudinary.uploader
from ..models import (Person, Channel, Message, DirectMessage, Product, Purchase,
                      GeoNote, MapServer, Server, Invite, Reaction, Friendship, br_now, db)
from ..utils import com_retry, comitar_com_retry, canal_permitido
from .. import socketio
from ..events import sala_servidor

main_bp = Blueprint("main", __name__)

EXTENSOES_IMAGEM = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
EXTENSOES_VIDEO = {'mp4', 'webm', 'mov'}
EXTENSOES_PERMITIDAS = EXTENSOES_IMAGEM | EXTENSOES_VIDEO

# Assinaturas dos formatos que a gente aceita. Checar a extensão do nome não
# basta - qualquer arquivo renomeado para .png passaria.
ASSINATURAS_IMAGEM = (
    b'\x89PNG\r\n\x1a\n',      # png
    b'\xff\xd8\xff',            # jpg/jpeg
    b'GIF87a', b'GIF89a',       # gif
    b'RIFF',                    # webp (RIFF....WEBP)
)

# Limites por tipo. O navegador já comprime as imagens antes de mandar
# (ver comprimirImagem() no chat.html), então 8 MB é folga de sobra.
LIMITE_IMAGEM = 8 * 1024 * 1024
LIMITE_VIDEO = 25 * 1024 * 1024


def _assinatura_de_video(cabecalho):
    """mp4/mov têm 'ftyp' no offset 4; webm começa com o magic do Matroska."""
    if cabecalho[4:8] == b'ftyp':
        return True
    if cabecalho.startswith(b'\x1a\x45\xdf\xa3'):
        return True
    return False


def usuario_da_sessao():
    """Person logada, ou None. Não levanta exceção se o banco estiver frio."""
    if 'user_id' not in session:
        return None
    try:
        return com_retry(lambda: Person.query.get(session['user_id']))
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"[ERRO BANCO] usuario_da_sessao: {e}")
        return None


@main_bp.app_errorhandler(413)
def arquivo_grande_demais(e):
    """Com MAX_CONTENT_LENGTH o Flask corta o request sozinho e devolve uma
    página HTML de erro - o fetch() do upload esperava JSON e quebrava."""
    return jsonify({'error': 'Imagem grande demais (máximo 5 MB)'}), 413


@main_bp.context_processor
def inject_user():
    # Procura pelo 'user_id' que a nossa rota do Google salvou na Sessão
    return dict(user=usuario_da_sessao())


def formatar_data(ts):
    if not ts: return ""
    # br_now() e não datetime.now(): o servidor do Render roda em UTC, então
    # comparar com a hora local dele trocava "Hoje"/"Ontem" perto da meia-noite.
    hoje = br_now().date()
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


# ==========================================
# PORTA DE ENTRADA INDEPENDENTE (/entrar)
# ------------------------------------------------------------------
# Página própria de login, sem passar pela home da Bazinga. É o link que dá
# pra mandar pra alguém de fora do grupo.
# ==========================================
@main_bp.route("/entrar")
def entrar():
    # Já logado (veio da home ou de uma sessão anterior): entra direto no
    # Bazingacord, sem passar por essa página de bloqueio.
    if usuario_da_sessao():
        return redirect(url_for('main.chat'))
    # Marca que o login começou por aqui, para o callback do Google saber
    # que a pessoa deve cair direto no chat.
    session['veio_do_entrar'] = True
    return render_template("entrar.html")


@main_bp.route("/abrir")
def abrir():
    """Tela pós-login: continuar no navegador, abrir no Chrome ou instalar o app."""
    usuario = usuario_da_sessao()
    if not usuario:
        return redirect(url_for('main.entrar'))
    return render_template("abrir.html", usuario_atual=usuario)


@main_bp.route("/manifest.webmanifest")
def manifest():
    """Manifesto do PWA - é o que faz o botão 'Instalar app' existir de verdade
    (o navegador só oferece a instalação se achar este arquivo + service worker)."""
    return jsonify({
        "name": "Bazinga Hub",
        "short_name": "Bazinga",
        "description": "Chat, mapa e eventos da Bazinga.",
        "start_url": "/chat",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0b0c10",
        "theme_color": "#5865F2",
        "orientation": "any",
        "icons": [
            {"src": url_for('static', filename='css/img/bazinga_logo.png'),
             "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
        ]
    })


@main_bp.route("/sw.js")
def service_worker():
    """Service worker mínimo.

    Não faz cache de nada de propósito: o app é todo dinâmico (socket, banco),
    e um cache agressivo só serviria pra servir tela velha. Ele existe porque
    o navegador exige um service worker registrado para permitir instalar o PWA.
    """
    js = (
        "self.addEventListener('install', () => self.skipWaiting());\n"
        "self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));\n"
        "self.addEventListener('fetch', () => {});\n"
    )
    return current_app.response_class(js, mimetype='application/javascript')


@main_bp.route("/chat")
def chat():
    if 'user_id' not in session:
        # Sem login e tentando entrar direto no chat: cai na página de
        # bloqueio (/entrar), não silenciosamente de volta pra home.
        return redirect(url_for('main.entrar'))

    try:
        def carregar():
            usuario_atual = Person.query.get(session['user_id'])
            if not usuario_atual:
                return None

            # Canais padrão do "Bazinga Hub" global (server_id nulo = não pertence a
            # nenhum Servidor criado por usuário)
            text_channels = Channel.query.filter_by(channel_type="text", server_id=None).all()
            voice_channels = Channel.query.filter_by(channel_type="voice", server_id=None).all()
            default_channel = Channel.query.filter_by(name="geral", server_id=None).first()

            messages = []
            if default_channel:
                messages = Message.query.filter_by(channel_id=default_channel.id).order_by(Message.timestamp.asc()).limit(50).all()
                for m in messages:
                    m.formatada = formatar_data(m.timestamp)

            # Amizades aceitas de verdade (antes isso pegava TODO MUNDO do banco
            # e chamava de "amigo" - só decoração, não vinha de pedido nenhum).
            aceitas = Friendship.query.filter(
                Friendship.status == 'accepted',
                or_(Friendship.requester_id == usuario_atual.id, Friendship.addressee_id == usuario_atual.id)
            ).all()
            ids_amigos = [f.addressee_id if f.requester_id == usuario_atual.id else f.requester_id for f in aceitas]
            amigos = Person.query.filter(Person.id.in_(ids_amigos)).all() if ids_amigos else []

            return usuario_atual, text_channels, voice_channels, default_channel, messages, amigos

        resultado = com_retry(carregar)
        if resultado is None:
            session.pop('user_id', None)
            return redirect(url_for('main.index'))
        usuario_atual, text_channels, voice_channels, default_channel, messages, amigos = resultado

    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"[ERRO BANCO] rota /chat: {e}")
        return "Erro de conexão com o banco. Recarregue a página."

    # Mensagem de "entrou pelo convite" deixada pela rota /convite/<code>
    aviso_convite = session.pop('aviso_convite', None)

    return render_template(
        "chat.html",
        aviso_convite=aviso_convite,
        usuario_atual=usuario_atual,
        text_channels=text_channels,
        voice_channels=voice_channels,
        default_channel=default_channel,
        messages=messages,
        amigos=amigos,
        membro_desde_texto=membro_desde_texto(usuario_atual.created_at)
    )


MESES_ABREVIADOS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                     'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def membro_desde_texto(criado_em):
    """'Set. 2026', ou None se a conta é antiga e não tem essa data guardada."""
    if not criado_em:
        return None
    return f"{MESES_ABREVIADOS[criado_em.month - 1]}. {criado_em.year}"


@main_bp.route("/api/mensagens/<int:canal_id>")
def pegar_mensagens(canal_id):
    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'error': 'Acesso negado'}), 401

    # Sem isso dava pra ler o histórico de qualquer canal só chutando o id.
    if not canal_permitido(usuario, canal_id):
        return jsonify({'error': 'Você não tem acesso a esse canal'}), 403

    try:
        mensagens_db = com_retry(lambda: Message.query.filter_by(channel_id=canal_id)
                                 .order_by(Message.timestamp.asc()).limit(50).all())
    except (OperationalError, PendingRollbackError) as e:
        db.session.rollback()
        print(f"[ERRO BANCO] /api/mensagens/{canal_id}: {e}")
        return jsonify({'error': 'Banco indisponível, tente de novo'}), 503

    # Reações de todas as mensagens de uma vez (em vez de uma query por mensagem)
    ids = [m.id for m in mensagens_db]
    reacoes_por_msg = {}
    if ids:
        for r in Reaction.query.filter(Reaction.message_id.in_(ids)).all():
            grupo = reacoes_por_msg.setdefault(r.message_id, {})
            item = grupo.setdefault(r.emoji, {'emoji': r.emoji, 'total': 0, 'quem': []})
            item['total'] += 1
            item['quem'].append(r.person_id)

    dados = []
    for msg in mensagens_db:
        dados.append({
            'id': msg.id,
            'autor': msg.author.name,
            'autor_id': msg.person_id,
            'avatar': msg.author.avatar,
            'texto': msg.text or '',
            'anexo_url': msg.attachment_url,
            'anexo_tipo': msg.attachment_type,
            'anexo_nome': msg.attachment_name,
            'editada': msg.edited_at is not None,
            'fixada': bool(msg.is_pinned),
            'reacoes': list(reacoes_por_msg.get(msg.id, {}).values()),
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
            'autor_id': msg.sender_id,
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


# ==========================================
# COMPRAR PRODUTO OFICIAL (paga com Bazinga Coins)
# ==========================================
@main_bp.route("/api/produtos/<int:produto_id>/comprar", methods=["POST"])
def comprar_produto(produto_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Acesso negado'}), 401

    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'error': 'Acesso negado'}), 401

    try:
        produto = com_retry(lambda: Product.query.get(produto_id))

        if not produto or not produto.is_official or produto.price_bzc is None:
            return jsonify({'error': 'Este item não pode ser comprado com Bazinga Coins aqui.'}), 400

        if (usuario.bazinga_coins or 0) < produto.price_bzc:
            return jsonify({'error': 'Você não tem Bazinga Coins suficientes.'}), 400

        # Registra a compra: antes as moedas eram descontadas e nada era
        # guardado, então o usuário pagava e não recebia nada.
        def preparar():
            usuario.bazinga_coins = (usuario.bazinga_coins or 0) - produto.price_bzc
            db.session.add(Purchase(
                buyer_id=usuario.id,
                product_id=produto.id,
                price_paid_bzc=produto.price_bzc
            ))

        comitar_com_retry(preparar)

        return jsonify({'saldo': usuario.bazinga_coins, 'produto': produto.name})
    except Exception as e:
        db.session.rollback()
        print("Erro ao comprar produto:", e)
        return jsonify({'error': f'Erro ao processar a compra: {e}'}), 500


# ==========================================
# INVENTÁRIO: o que o usuário já comprou
# ==========================================
@main_bp.route("/api/inventario")
def get_inventario():
    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'error': 'Acesso negado'}), 401

    try:
        compras = com_retry(lambda: Purchase.query.filter_by(buyer_id=usuario.id)
                            .order_by(Purchase.created_at.desc()).all())
        return jsonify([{
            'id': c.id,
            'produto_id': c.product_id,
            'nome': c.product.name if c.product else 'Item removido',
            'image_url': c.product.image_url if c.product else None,
            'preco_pago': c.price_paid_bzc,
            'comprado_em': formatar_data(c.created_at)
        } for c in compras])
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO INVENTARIO] (rode atualizar_banco.py se for erro de tabela): {e}")
        return jsonify([])


# ==========================================
# MAPA: Carregar Notas HQ e Servidores plantados (ignora itens expirados)
# ==========================================
@main_bp.route("/api/mapa/dados")
def dados_do_mapa():
    if 'user_id' not in session:
        return jsonify({'error': 'Acesso negado'}), 401

    try:
        agora = br_now()

        def buscar():
            notas_db = GeoNote.query.filter(
                or_(GeoNote.expires_at == None, GeoNote.expires_at > agora)
            ).all()
            servers_db = MapServer.query.filter(
                or_(MapServer.expires_at == None, MapServer.expires_at > agora)
            ).all()

            # autor_id/owner_id vão junto porque o frontend decidia quem é dono
            # comparando o NOME - dois usuários com o mesmo nome do Google viam
            # os botões de editar/apagar um do outro.
            notas = [{
                'id': n.id, 'lat': n.lat, 'lng': n.lng,
                'texto': n.text, 'autor': n.author.name if n.author else '???',
                'autor_id': n.author_id, 'cor': n.color
            } for n in notas_db]

            # Nome e ícone vêm do Servidor ligado, não da cópia feita na hora
            # de plantar: senão renomear o servidor não mudava nada no mapa.
            servers = [{
                'id': s.id, 'lat': s.lat, 'lng': s.lng,
                'name': (s.server.name if s.server else s.name),
                'icon_url': (s.server.icon_url if s.server else None),
                'owner': s.owner.name if s.owner else '???',
                'owner_id': s.owner_id,
                'vagas': s.max_tickets if s.max_tickets else 'ilimitado',
                'online': len(s.server.members) if s.server else 1,
                'server_id': s.server_id
            } for s in servers_db]

            return notas, servers

        notas, servers = com_retry(buscar)
        return jsonify({'notas': notas, 'servers': servers})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MAPA] Falha ao carregar notas/servidores (rode atualizar_banco.py se for erro de coluna): {e}")
        return jsonify({'notas': [], 'servers': []})


# ==========================================
# UPLOAD DE IMAGENS (Avatar de usuário / Ícone de servidor)
# ==========================================
@main_bp.route("/api/upload", methods=["POST"])
def upload_imagem():
    if 'user_id' not in session:
        return jsonify({'error': 'Acesso negado'}), 401

    arquivo = request.files.get('file')
    if not arquivo or arquivo.filename == '':
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    extensao = arquivo.filename.rsplit('.', 1)[-1].lower() if '.' in arquivo.filename else ''
    if extensao not in EXTENSOES_PERMITIDAS:
        return jsonify({'error': 'Formato não permitido (use imagem, gif ou vídeo)'}), 400

    e_video = extensao in EXTENSOES_VIDEO

    # Confere a assinatura real do arquivo: um .php/.svg renomeado para .png
    # passava só na checagem de extensão.
    cabecalho = arquivo.stream.read(16)
    arquivo.stream.seek(0, os.SEEK_END)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)

    if e_video:
        if not _assinatura_de_video(cabecalho):
            return jsonify({'error': 'Esse arquivo não é um vídeo de verdade'}), 400
        if tamanho > LIMITE_VIDEO:
            return jsonify({'error': 'Vídeo muito pesado (máximo 25 MB)'}), 400
    else:
        if not cabecalho.startswith(ASSINATURAS_IMAGEM):
            return jsonify({'error': 'Esse arquivo não é uma imagem de verdade'}), 400
        if tamanho > LIMITE_IMAGEM:
            return jsonify({'error': 'Imagem muito pesada (máximo 8 MB)'}), 400

    # Vai pro Cloudinary, não pro disco local: o disco do Render free é
    # efêmero e some a cada restart/redeploy (avatar, ícone de servidor e
    # anexo de mensagem desapareciam sempre que o container reiniciava).
    nome_seguro = uuid.uuid4().hex
    try:
        resultado = cloudinary.uploader.upload(
            arquivo,
            public_id=nome_seguro,
            resource_type='video' if e_video else 'image',
            folder='bazinga',
        )
    except Exception as e:
        print(f"[ERRO UPLOAD] Falha ao enviar pro Cloudinary: {e}")
        return jsonify({'error': f'Não foi possível enviar o arquivo: {e}'}), 500

    url = resultado.get('secure_url')
    return jsonify({'url': url, 'tipo': 'video' if e_video else 'image', 'tamanho': tamanho})


# ==========================================
# CONVITE: link que leva direto pra dentro do servidor
# ==========================================
@main_bp.route("/convite/<code>")
def entrar_por_link(code):
    """Abre o convite. Quem não está logado vai pro login e volta pra cá."""
    usuario = usuario_da_sessao()
    if not usuario:
        session['convite_pendente'] = code
        return redirect(url_for('main.index'))

    try:
        convite = com_retry(lambda: Invite.query.filter_by(code=code).first())
        if not convite or not convite.esta_valido():
            session['aviso_convite'] = 'Convite inválido ou expirado.'
            return redirect(url_for('main.chat'))

        servidor = Server.query.get(convite.server_id)
        if not servidor:
            session['aviso_convite'] = 'Esse servidor não existe mais.'
            return redirect(url_for('main.chat'))

        if usuario not in servidor.members:
            def preparar():
                servidor.members.append(usuario)
                convite.uses = (convite.uses or 0) + 1

            comitar_com_retry(preparar)
            # Rota HTTP pura (sem contexto de socket): o navegador de quem
            # entrou ainda nem conectou no socket nesse momento (só conecta
            # depois do redirect pra /chat), então não tem "self" pra excluir.
            socketio.emit('membro_entrou_servidor', {
                'server_id': servidor.id,
                'membro': {'id': usuario.id, 'nome': usuario.name, 'avatar': usuario.avatar}
            }, to=sala_servidor(servidor.id))
            session['aviso_convite'] = f'Você entrou em {servidor.name}!'
        else:
            session['aviso_convite'] = f'Você já estava em {servidor.name}.'

        return redirect(url_for('main.chat'))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CONVITE] {e}")
        session['aviso_convite'] = 'Não foi possível entrar pelo convite.'
        return redirect(url_for('main.chat'))