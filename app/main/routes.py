from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request, current_app
from sqlalchemy.exc import OperationalError, PendingRollbackError, SQLAlchemyError
from sqlalchemy import or_, and_
from werkzeug.utils import secure_filename
import os
import uuid
from ..models import (Person, Channel, Message, DirectMessage, Product, Purchase,
                      GeoNote, MapServer, br_now, db)
from ..utils import com_retry, comitar_com_retry, canal_permitido

main_bp = Blueprint("main", __name__)

EXTENSOES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Assinaturas dos formatos que a gente aceita. Checar a extensão do nome não
# basta - qualquer arquivo renomeado para .png passaria.
ASSINATURAS_IMAGEM = (
    b'\x89PNG\r\n\x1a\n',      # png
    b'\xff\xd8\xff',            # jpg/jpeg
    b'GIF87a', b'GIF89a',       # gif
    b'RIFF',                    # webp (RIFF....WEBP)
)


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


@main_bp.route("/chat")
def chat():
    if 'user_id' not in session:
        return redirect(url_for('main.index'))

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

            # Busca todas as pessoas no banco (exceto você) para simular sua lista de amigos
            amigos = Person.query.filter(Person.id != usuario_atual.id).all()

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

            servers = [{
                'id': s.id, 'lat': s.lat, 'lng': s.lng,
                'name': s.name, 'owner': s.owner.name if s.owner else '???',
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
        return jsonify({'error': 'Formato de imagem não permitido'}), 400

    # Confere a assinatura real do arquivo: um .php/.svg renomeado para .png
    # passava só na checagem de extensão.
    cabecalho = arquivo.stream.read(12)
    arquivo.stream.seek(0)
    if not cabecalho.startswith(ASSINATURAS_IMAGEM):
        return jsonify({'error': 'Esse arquivo não é uma imagem de verdade'}), 400

    pasta_uploads = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(pasta_uploads, exist_ok=True)

    nome_seguro = f"{uuid.uuid4().hex}.{extensao}"
    caminho_completo = os.path.join(pasta_uploads, secure_filename(nome_seguro))
    arquivo.save(caminho_completo)

    url = url_for('static', filename=f'uploads/{nome_seguro}')
    return jsonify({'url': url})