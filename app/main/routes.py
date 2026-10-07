from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request, current_app, Response
from sqlalchemy.exc import OperationalError, PendingRollbackError, SQLAlchemyError
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import joinedload
import os
import re
import time
import uuid
import cloudinary
import cloudinary.uploader
import requests
from ..models import (Person, Channel, Message, DirectMessage, Product, Purchase,
                      GeoNote, MapServer, Server, Invite, Reaction, Friendship, PushSub, br_now, db, server_members)
from ..utils import (eh_membro, com_retry, comitar_com_retry, canal_permitido, membro_desde_texto, garantir_username,
                     dados_do_mapa_perto, coordenada_valida, RAIO_NOTAS_M, RAIO_SERVIDORES_M,
                     localizacao_ligada, localizacao_ip_permitida, MSG_LOCALIZACAO_DESLIGADA,
                     recortar_animacao, animar_quadros, FORMATOS_ANIMADOS, MAX_QUADROS_ANIMACAO)
from .. import socketio, APP_NOME, MOEDA_NOME, APP_VERSAO
from ..events import sala_servidor, servidor_para_json, servidores_para_json, _estado_inventario
from ..cosmeticos import posses_da_pessoa, posses_com_regras, equipados_da_pessoa, badges_do_conjunto, patente_do_nivel
from ..utils import nivel_da_pessoa, resumos_de_resposta_canal, resumos_de_resposta_dm

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


# O teto global (5 MB, config.py) barrava um GIF de 6-10 MB ANTES de a rota rodar - o aviso falava
# em "5 MB" mesmo a rota aceitando 10. Essas duas rotas têm teto próprio, só na requisição delas.
_TETO_POR_ROTA = {'/api/gif/recortar': 12 * 1024 * 1024, '/api/video/animar': 16 * 1024 * 1024}


@main_bp.before_request
def teto_de_upload_por_rota():
    teto = _TETO_POR_ROTA.get(request.path)
    if teto:
        request.max_content_length = teto


@main_bp.app_errorhandler(413)
def arquivo_grande_demais(e):
    """Com MAX_CONTENT_LENGTH o Flask corta o request sozinho e devolve uma
    página HTML de erro - o fetch() do upload esperava JSON e quebrava."""
    return jsonify({'error': 'Imagem grande demais (máximo 5 MB)'}), 413


# ==========================================
# PUSH: chave pública, inscrever e cancelar (um aparelho por vez)
# ==========================================
@main_bp.route("/api/push/chave")
def push_chave():
    if not usuario_da_sessao():
        return jsonify({'error': 'Acesso negado'}), 401
    from ..push import chave_publica
    try:
        return jsonify({'chave': chave_publica()})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PUSH CHAVE] {e}")
        return jsonify({'error': 'Avisos indisponíveis agora'}), 503


@main_bp.route("/api/push/inscrever", methods=["POST"])
def push_inscrever():
    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'error': 'Acesso negado'}), 401
    dados = request.get_json(silent=True) or {}
    endpoint = str(dados.get('endpoint') or '')
    chaves = dados.get('keys') or {}
    p256dh, auth = str(chaves.get('p256dh') or ''), str(chaves.get('auth') or '')
    if not endpoint.startswith('https://') or len(endpoint) > 700 or not (20 < len(p256dh) <= 200) or not (8 < len(auth) <= 100):
        return jsonify({'error': 'Inscrição inválida'}), 400
    try:
        def preparar():
            sub = PushSub.query.filter_by(endpoint=endpoint).first()
            if not sub:
                sub = PushSub(endpoint=endpoint, p256dh=p256dh, auth=auth, person_id=usuario.id)
                db.session.add(sub)
            sub.person_id = usuario.id          # outra conta no mesmo aparelho: o aviso passa pra quem está logado agora
            sub.p256dh, sub.auth = p256dh, auth
            sub.user_agent = (request.headers.get('User-Agent') or '')[:250]
        comitar_com_retry(preparar)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PUSH INSCREVER] {e}")
        return jsonify({'error': 'Não consegui salvar agora'}), 500
    return jsonify({'ok': True})


@main_bp.route("/api/push/cancelar", methods=["POST"])
def push_cancelar():
    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'ok': True})
    endpoint = str((request.get_json(silent=True) or {}).get('endpoint') or '')
    try:
        def preparar():
            PushSub.query.filter_by(endpoint=endpoint, person_id=usuario.id).delete(synchronize_session=False)
        comitar_com_retry(preparar)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PUSH CANCELAR] {e}")
    return jsonify({'ok': True})


@main_bp.app_errorhandler(500)
def erro_interno(e):
    """Página própria no lugar do "Internal Server Error" cru (o app instalado ficava preso nela)."""
    print(f"[ERRO 500] {request.path}: {e}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Erro interno. Tente de novo.'}), 500
    return Response(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Ops</title><body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0c10;'
        'color:#f2f3f5;font-family:system-ui,sans-serif;text-align:center;padding:24px">'
        '<div><h1 style="margin:0 0 8px">Algo deu errado aqui</h1>'
        '<p style="color:#9aa0a6;margin:0 0 22px">Foi um tropeço do servidor, não é com você. Tenta de novo.</p>'
        '<a href="/entrar" style="display:inline-block;background:#5865F2;color:#fff;text-decoration:none;'
        'padding:12px 22px;border-radius:12px;font-weight:600">Voltar ao início</a></div>',
        status=500, mimetype='text/html')


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
    # Login pedido pelo app desktop (abre este link no navegador do sistema).
    # Guardamos só o hash do verificador; o callback do Google emite o código.
    if request.args.get('desktop') == '1':
        from ..auth.routes import desafio_desktop_valido
        desafio = request.args.get('desafio', '')
        if desafio_desktop_valido(desafio):
            session['desktop_desafio'] = desafio
            if usuario_da_sessao():
                return redirect(url_for('auth.desktop_concluir'))
            return render_template("entrar.html")
    # "Baixar o app" da home: mostra a página mesmo pra quem já está logado (senão o redirect abaixo escondia o download).
    if request.args.get('instalar') == '1':
        return render_template("entrar.html", erro=None)
    # Já logado (veio da home ou de uma sessão anterior): entra direto no
    # Bazingacord, sem passar por essa página de bloqueio.
    if usuario_da_sessao():
        return redirect(url_for('main.chat'))
    # Marca que o login começou por aqui, para o callback do Google saber
    # que a pessoa deve cair direto no chat.
    session['veio_do_entrar'] = True
    return render_template("entrar.html", erro=request.args.get('erro'))


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
        "name": APP_NOME,
        "short_name": APP_NOME,
        "description": f"Chat, mapa e eventos do {APP_NOME}.",
        "id": "/chat",
        "start_url": "/chat",
        "scope": "/",
        "categories": ["social"],
        "display": "standalone",
        "background_color": "#0b0c10",
        "theme_color": "#7289da",
        "orientation": "any",
        "icons": [
            {"src": url_for('static', filename='img/icone-192.png'),
             "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": url_for('static', filename='img/icone-512.png'),
             "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": url_for('static', filename='img/logo.svg'),
             "sizes": "any", "type": "image/svg+xml", "purpose": "any"}
        ]
    })


@main_bp.route("/sw.js")
def service_worker():
    """Service worker: guarda só o que é ESTÁTICO, nunca a parte dinâmica.

    O app é todo dinâmico (socket, banco), então cache de página/API serviria
    tela velha. Aqui entram apenas:
      - /static/* (css, js, imagens, emoji, áudio): cache versionado por
        APP_VERSAO. O texto deste arquivo muda a cada deploy, então o
        navegador instala o SW novo e a ativação apaga o cache antigo.
      - bibliotecas de CDN com versão fixa na URL (Leaflet, socket.io,
        fontes...): cache à parte, que sobrevive a deploys.
    Jamais cacheados: /chat, /entrar, /socket.io, /api/*, /auth/* e qualquer
    POST. Navegação sem rede cai numa página "sem conexão" com botão de
    tentar de novo (em vez da tela de erro do navegador).
    """
    # Em debug o estático NÃO é cacheado: editar css/js sem reiniciar o servidor
    # não muda APP_VERSAO, e o navegador ficaria mostrando o arquivo velho.
    js = (_SW_TEMPLATE.replace('__VERSAO__', APP_VERSAO).replace('__NOME__', APP_NOME)
          .replace('__CACHEAR_ESTATICO__', 'false' if current_app.debug else 'true'))
    resposta = current_app.response_class(js, mimetype='application/javascript')
    resposta.headers['Cache-Control'] = 'no-cache'   # o navegador precisa ver o SW novo logo após o deploy
    resposta.headers['Service-Worker-Allowed'] = '/'
    return resposta


_SW_TEMPLATE = r"""
const VERSAO = '__VERSAO__';

// ---- Notificações push: o servidor manda JSON {titulo, corpo, url, tag, urgente, tipo, de_id} ----
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (er) { d = { corpo: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.titulo || '__NOME__', {
    body: d.corpo || '',
    tag: d.tag || undefined,
    renotify: !!d.tag,
    icon: '/static/img/icone-192.png',
    badge: '/static/img/icone-192.png',
    data: d,
    requireInteraction: !!d.urgente,
    vibrate: d.urgente ? [300, 150, 300, 150, 300] : [120]
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const d = e.notification.data || {};
  const alvo = d.url || '/chat';
  e.waitUntil((async () => {
    const abas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of abas) {
      if (new URL(c.url).origin === self.location.origin) {
        await c.focus();
        c.postMessage({ tipo: 'push_clique', dados: d });
        return;
      }
    }
    await self.clients.openWindow(alvo);   // a página lê ?dm=ID e abre a conversa
  })());
});

const CACHE_ESTATICO = 'estatico-' + VERSAO;
const CACHE_CDN = 'cdn-v1';
const CACHEAR_ESTATICO = __CACHEAR_ESTATICO__;

// CDN só entra no cache se a URL carrega versão fixa (nunca @latest / @1):
// senão a biblioteca nova nunca chegaria.
function cdnVersionado(u) {
  if (u.hostname === 'cdnjs.cloudflare.com' || u.hostname === 'fonts.gstatic.com') return true;
  if (u.hostname === 'cdn.jsdelivr.net' || u.hostname === 'unpkg.com') return /@\d+\.\d+\.\d+/.test(u.pathname);
  return false;
}

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', e => e.waitUntil((async () => {
  const nomes = await caches.keys();
  await Promise.all(nomes.filter(n => n !== CACHE_ESTATICO && n !== CACHE_CDN).map(n => caches.delete(n)));
  await self.clients.claim();
})()));

async function cacheAntes(req, nomeCache) {
  const cache = await caches.open(nomeCache);
  const guardado = await cache.match(req);
  if (guardado) return guardado;
  const resp = await fetch(req);
  // 200 normal ou opaca (script/estilo de CDN sem CORS); erro nunca é guardado
  if (resp.ok || resp.type === 'opaque') cache.put(req, resp.clone());
  return resp;
}

const PAGINA_OFFLINE = `<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sem conexão · __NOME__</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0c10;color:#f2f3f5;
font-family:system-ui,sans-serif;text-align:center;padding:24px}p{color:#9aa0a6;margin:8px 0 22px}
button{background:#5865F2;color:#fff;border:0;border-radius:12px;padding:12px 22px;font:600 15px system-ui;cursor:pointer}</style></head>
<body><div><h1>Sem conexão</h1><p>Não consegui falar com o servidor. Confira a internet e tente de novo.</p>
<button onclick="location.reload()">Tentar de novo</button></div></body></html>`;

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const u = new URL(req.url);

  if (u.origin === self.location.origin) {
    if (u.pathname.startsWith('/static/')) {
      if (CACHEAR_ESTATICO) e.respondWith(cacheAntes(req, CACHE_ESTATICO));
      return;
    }
    if (req.mode === 'navigate') {
      e.respondWith(fetch(req).catch(() => new Response(PAGINA_OFFLINE,
        { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } })));
    }
    return;   // o resto (api, socket.io, auth...) vai direto pra rede, sem tocar
  }

  if (cdnVersionado(u)) e.respondWith(cacheAntes(req, CACHE_CDN));
});
"""


# ==========================================
# LOCALIZAÇÃO POR IP (reserva)
# ------------------------------------------------------------------
# Só entra quando o aparelho não achou a posição (Windows/Google/GPS). É aproximada (cidade, às vezes só a região),
# e VPN ou dados móveis fazem ela cair no provedor, não em você: por isso é só reserva e o cliente avisa.
# O provedor é trocável (PROVEDOR_IP); sem chave, mas com limite - por isso o cache por IP.
# ==========================================
PROVEDOR_IP = "https://ipwho.is/{ip}?fields=success,latitude,longitude,city,region,country,message"
_cache_ip = {}           # ip -> (ts, payload)
_ultimo_pedido_ip = {}   # usuario_id -> ts


def _ip_do_cliente():
    """Primeiro IP público de X-Forwarded-For (o Render põe o do cliente ali) ou o do socket."""
    import ipaddress
    candidatos = [p.strip() for p in (request.headers.get('X-Forwarded-For') or '').split(',') if p.strip()]
    candidatos.append(request.remote_addr or '')
    for c in candidatos:
        try:
            ip = ipaddress.ip_address(c)
        except ValueError:
            continue
        if ip.is_global:
            return str(ip)
    return None


@main_bp.route("/api/localizacao/ip")
def localizacao_por_ip():
    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'error': 'Acesso negado'}), 401
    if not localizacao_ip_permitida(usuario):
        return jsonify({'error': 'A localização por IP está desligada nas suas configurações.'}), 403

    agora = time.time()
    if agora - _ultimo_pedido_ip.get(usuario.id, 0) < 15:
        return jsonify({'error': 'Calma: espere uns segundos antes de tentar de novo.'}), 429
    _ultimo_pedido_ip[usuario.id] = agora

    ip = _ip_do_cliente()
    if not ip:
        return jsonify({'error': 'Não achei um IP público (rede local?).'}), 422

    guardado = _cache_ip.get(ip)
    if guardado and agora - guardado[0] < 3600:
        return jsonify(guardado[1])

    try:
        r = requests.get(PROVEDOR_IP.format(ip=ip), timeout=4)
        d = r.json()
    except Exception as e:
        print(f"[ERRO IP LOC] {e}")
        return jsonify({'error': 'Não consegui consultar a localização por IP agora.'}), 502
    pos = coordenada_valida(d.get('latitude'), d.get('longitude')) if d.get('success') else None
    if not pos:
        return jsonify({'error': 'Não consegui descobrir onde esse IP fica.'}), 502

    payload = {'lat': pos[0], 'lng': pos[1], 'precisao_m': 10000,
               'lugar': ', '.join(x for x in (d.get('city'), d.get('region')) if x)}
    if len(_cache_ip) > 500:
        _cache_ip.clear()
    _cache_ip[ip] = (agora, payload)
    return jsonify(payload)


@main_bp.route("/chat")
def chat():
    if 'user_id' not in session:
        # Sem login e tentando entrar direto no chat: cai na página de
        # bloqueio (/entrar), não silenciosamente de volta pra home.
        return redirect(url_for('main.entrar'))

    try:
        def carregar():
            usuario_atual = Person.query.options(joinedload(Person.role)).get(session['user_id'])
            if not usuario_atual:
                return None

            # Canais padrão do "Bazinga Hub" global (server_id nulo = não pertence a
            # nenhum Servidor criado por usuário)
            text_channels = Channel.query.filter_by(channel_type="text", server_id=None).all()
            voice_channels = Channel.query.filter_by(channel_type="voice", server_id=None).all()
            default_channel = Channel.query.filter_by(name="geral", server_id=None).first()

            messages = []
            if default_channel:
                messages = Message.query.filter_by(channel_id=default_channel.id).order_by(Message.id.desc()).limit(50).all()
                messages.reverse()
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

            # Lista de servidores já no HTML: antes ela só chegava pelo socket
            # (`carregar_meus_servidores`), então com o Render/Neon "acordando"
            # a barra de servidores ficava vazia por vários segundos - parecia
            # que os servidores tinham sumido. O socket ainda reenvia e
            # reconcilia depois.
            servidores_iniciais = servidores_para_json(list(usuario_atual.servers), usuario_atual)

            # Inventário já no HTML (1 query): moldura/efeitos/insígnias nascem desenhados, sem esperar o socket.
            inventario_inicial = _estado_inventario(usuario_atual, posses_com_regras(usuario_atual))

            return (usuario_atual, text_channels, voice_channels, default_channel, messages, amigos,
                    servidores_iniciais, inventario_inicial)

        resultado = com_retry(carregar)
        if resultado is None:
            session.pop('user_id', None)
            return redirect(url_for('main.index'))
        (usuario_atual, text_channels, voice_channels, default_channel, messages, amigos,
         servidores_iniciais, inventario_inicial) = resultado

    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"[ERRO BANCO] rota /chat: {e}")
        return "Erro de conexão com o banco. Recarregue a página."

    try:
        garantir_username(usuario_atual)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO USERNAME] {e}")

    # Mensagem de "entrou pelo convite" deixada pela rota /convite/<code>
    aviso_convite = session.pop('aviso_convite', None)

    resposta = current_app.make_response(render_template(
        "chat.html",
        aviso_convite=aviso_convite,
        usuario_atual=usuario_atual,
        text_channels=text_channels,
        voice_channels=voice_channels,
        default_channel=default_channel,
        messages=messages,
        amigos=amigos,
        servidores_iniciais=servidores_iniciais,
        inventario_inicial=inventario_inicial,
        patente_inicial=patente_do_nivel(nivel_da_pessoa(usuario_atual.xp)),
        badges_iniciais=badges_do_conjunto(set(inventario_inicial['posses'])),
        membro_desde_texto=membro_desde_texto(usuario_atual.created_at)
    ))
    resposta.headers['Cache-Control'] = 'no-store'   # a página tem a versão do app embutida (ver APP_VERSAO)
    return resposta


GIPHY_API_KEY = os.getenv('GIPHY_API_KEY')


@main_bp.route("/api/gifs")
def buscar_gifs():
    """Busca de GIF pro compose bar (painel ao lado do emoji), igual ao
    Discord - a key fica só aqui no servidor, o navegador nunca vê ela."""
    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'error': 'Acesso negado'}), 401

    if not GIPHY_API_KEY:
        return jsonify({'error': 'Busca de GIF não configurada (falta GIPHY_API_KEY no servidor).'}), 503

    busca = (request.args.get('q') or '').strip()[:100]
    endpoint = 'search' if busca else 'trending'
    params = {'api_key': GIPHY_API_KEY, 'limit': 24, 'rating': 'pg-13', 'lang': 'pt'}
    if busca:
        params['q'] = busca

    try:
        resp = requests.get(f'https://api.giphy.com/v1/gifs/{endpoint}', params=params, timeout=6)
        resp.raise_for_status()
        dados = resp.json().get('data', [])
    except Exception as e:
        print(f"[ERRO BUSCA GIF] {e}")
        return jsonify({'error': 'Não consegui buscar GIFs agora, tenta de novo.'}), 502

    # Só o que a gente usa - a resposta do Giphy vem enorme (dezenas de
    # variações de tamanho, links de embed, estatística) e não interessa nada
    # disso pro cliente.
    gifs = []
    for g in dados:
        imagens = g.get('images', {})
        preview = imagens.get('fixed_width_small', {}).get('url')
        envio = imagens.get('fixed_height', {}).get('url')
        if preview and envio:
            gifs.append({'id': g.get('id'), 'preview': preview, 'url': envio,
                         'nome': (g.get('title') or 'GIF')[:255]})

    return jsonify(gifs)


@main_bp.route("/api/mensagens/<int:canal_id>")
def pegar_mensagens(canal_id):
    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'error': 'Acesso negado'}), 401

    # Sem isso dava pra ler o histórico de qualquer canal só chutando o id.
    if not canal_permitido(usuario, canal_id):
        return jsonify({'error': 'Você não tem acesso a esse canal'}), 403

    try:
        # joinedload aqui é o que faz essa rota valer a pena existir: sem ele,
        # cada `msg.author` e cada `msg.author.role` (usados embaixo) dispara
        # uma query própria - até 50 mensagens x 2 = ~100 idas ao banco só pra
        # abrir um canal. Com NullPool (toda query = conexão nova no Neon),
        # isso sozinho já explicava boa parte do "demora pra trocar de canal".
        # As 50 MAIS RECENTES (desc + limit) e depois reordena pra exibir. Antes era
        # asc + limit(50): num canal com mais de 50 mensagens vinham as 50 mais
        # ANTIGAS - "sai e volta no servidor e não carrega as mensagens".
        # `antes` = id da mensagem mais antiga que o cliente já tem (carregar anteriores).
        consulta = Message.query.filter_by(channel_id=canal_id)
        antes = request.args.get('antes', type=int)
        if antes:
            consulta = consulta.filter(Message.id < antes)
        mensagens_db = com_retry(lambda: consulta
                                 .options(joinedload(Message.author).joinedload(Person.role))
                                 .order_by(Message.id.desc()).limit(50).all())
        mensagens_db.reverse()
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

    respostas = resumos_de_resposta_canal([m.reply_to_id for m in mensagens_db if m.reply_to_id], canal_id)
    dados = []
    for msg in mensagens_db:
        dados.append({
            'id': msg.id,
            'reply': respostas.get(msg.reply_to_id) if msg.reply_to_id else None,
            'reply_apagada': bool(msg.reply_to_id and msg.reply_to_id not in respostas),
            'autor': msg.author.name,
            'autor_id': msg.person_id,
            'avatar': msg.author.avatar,
            'nome_estilo': msg.author.nome_estilo, 'moldura': msg.author.moldura, 'equipados': equipados_da_pessoa(msg.author),
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
        consulta = DirectMessage.query.filter(
            or_(
                and_(DirectMessage.sender_id == meu_id, DirectMessage.receiver_id == target_id),
                and_(DirectMessage.sender_id == target_id, DirectMessage.receiver_id == meu_id)
            )
        )
        antes = request.args.get('antes', type=int)
        if antes:
            consulta = consulta.filter(DirectMessage.id < antes)
        # Mesmo conserto do canal: as 50 mais RECENTES, não as 50 mais antigas.
        mensagens_db = com_retry(lambda: consulta
                                 .options(joinedload(DirectMessage.sender).joinedload(Person.role))
                                 .order_by(DirectMessage.id.desc()).limit(50).all())
        mensagens_db.reverse()
    except (OperationalError, PendingRollbackError):
        db.session.rollback()
        mensagens_db = []

    respostas = resumos_de_resposta_dm([m.reply_to_id for m in mensagens_db if m.reply_to_id], meu_id, target_id)
    dados = []
    for msg in mensagens_db:
        dados.append({
            'id': msg.id,
            'reply': respostas.get(msg.reply_to_id) if msg.reply_to_id else None,
            'reply_apagada': bool(msg.reply_to_id and msg.reply_to_id not in respostas),
            'autor': msg.sender.name,
            'autor_id': msg.sender_id,
            'avatar': msg.sender.avatar,
            'nome_estilo': msg.sender.nome_estilo, 'moldura': msg.sender.moldura, 'equipados': equipados_da_pessoa(msg.sender),
            'texto': msg.content or '',
            'anexo_url': msg.attachment_url,
            'anexo_tipo': msg.attachment_type,
            'anexo_nome': msg.attachment_name,
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
                'seller': p.seller.name if p.seller else f'{APP_NOME} Oficial'
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

    # Medida de segurança: comprar (e, quando existir, vender) exige a localização ligada.
    if not localizacao_ligada(usuario):
        return jsonify({'error': MSG_LOCALIZACAO_DESLIGADA}), 403

    try:
        produto = com_retry(lambda: Product.query.get(produto_id))

        if not produto or not produto.is_official or produto.price_bzc is None:
            return jsonify({'error': f'Este item não pode ser comprado com {MOEDA_NOME} aqui.'}), 400

        if (usuario.bazinga_coins or 0) < produto.price_bzc:
            return jsonify({'error': f'Você não tem {MOEDA_NOME} suficientes.'}), 400

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
    """Só devolve o que está dentro do raio de quem pede (?lat=&lng=). Sem posição
    não devolve nada: o mapa não é mais um "mundo inteiro" que todo mundo baixa."""
    if 'user_id' not in session:
        return jsonify({'error': 'Acesso negado'}), 401

    pos = coordenada_valida(request.args.get('lat'), request.args.get('lng'))
    if not pos:
        return jsonify({'notas': [], 'servers': [], 'raio_notas_m': RAIO_NOTAS_M,
                        'raio_servidores_m': RAIO_SERVIDORES_M})
    try:
        return jsonify(com_retry(lambda: dados_do_mapa_perto(*pos)))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MAPA] Falha ao carregar notas/servidores: {e}")
        return jsonify({'notas': [], 'servers': [], 'raio_notas_m': RAIO_NOTAS_M,
                        'raio_servidores_m': RAIO_SERVIDORES_M})


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
# RECORTE DE GIF (mantém a animação)
# ------------------------------------------------------------
# O navegador não consegue recortar GIF sem perder a animação (o canvas pega 1 quadro). O cliente
# manda o GIF (arquivo, ou o link de um GIF do Giphy) + o enquadramento que a pessoa escolheu, e
# aqui cada quadro é recortado com o Pillow. Devolve um WebP animado - o cliente envia ele pelo
# mesmo caminho de upload de qualquer imagem.
# ==========================================
_ultimo_recorte = {}
_RE_GIPHY_URL = re.compile(r'^https://media\d*\.giphy\.com/')
LIMITE_GIF_BYTES = 10 * 1024 * 1024


@main_bp.route("/api/gif/recortar", methods=["POST"])
def recortar_gif():
    if 'user_id' not in session:
        return jsonify({'error': 'Acesso negado'}), 401

    # Cada recorte custa CPU: um por vez e com um respiro entre eles.
    agora = time.time()
    if agora - _ultimo_recorte.get(session['user_id'], 0) < 1.5:
        return jsonify({'error': 'Calma - espere um instante e tente de novo.'}), 429
    _ultimo_recorte[session['user_id']] = agora

    formato = request.form.get('formato', 'quadrado')
    if formato not in FORMATOS_ANIMADOS:
        return jsonify({'error': 'Formato inválido'}), 400
    try:
        escala = float(request.form.get('escala', 1))
        ox = float(request.form.get('ox', 0))
        oy = float(request.form.get('oy', 0))
    except ValueError:
        return jsonify({'error': 'Parâmetros inválidos'}), 400
    espelho_h = request.form.get('fh') in ('1', 'true')
    espelho_v = request.form.get('fv') in ('1', 'true')

    arquivo = request.files.get('file')
    if arquivo:
        dados = arquivo.read(LIMITE_GIF_BYTES + 1)
    else:
        url = request.form.get('url', '')
        # Só o CDN do Giphy: buscar URL qualquer a pedido do usuário seria um buraco (SSRF).
        if not _RE_GIPHY_URL.match(url):
            return jsonify({'error': 'Origem não permitida'}), 400
        try:
            resp = requests.get(url, timeout=10, stream=True)
            resp.raise_for_status()
            dados = resp.raw.read(LIMITE_GIF_BYTES + 1, decode_content=True)
        except Exception as e:
            return jsonify({'error': f'Não consegui baixar o GIF: {e}'}), 502
    if not dados or len(dados) > LIMITE_GIF_BYTES:
        return jsonify({'error': 'GIF muito pesado (máximo 10 MB)'}), 400
    if not dados.startswith((b'GIF8', b'RIFF', b'\x89PNG')):
        return jsonify({'error': 'Esse arquivo não é um GIF/animação de verdade'}), 400

    try:
        saida = recortar_animacao(dados, formato, escala, ox, oy, espelho_h, espelho_v)
    except Exception as e:
        print(f"[ERRO RECORTE GIF] {e}")
        return jsonify({'error': 'Não consegui processar esse GIF'}), 422
    return Response(saida, mimetype='image/webp')


# Vídeo (mp4/webm/mov) como foto/faixa/fundo: o navegador manda os quadros já extraídos (JPEG) e
# aqui eles viram um WebP animado - nada de ffmpeg no servidor (ver `animar_quadros`).
_ultimo_video = {}
LIMITE_QUADRO_BYTES = 600 * 1024


@main_bp.route("/api/video/animar", methods=["POST"])
def animar_video():
    if 'user_id' not in session:
        return jsonify({'error': 'Acesso negado'}), 401

    agora = time.time()
    if agora - _ultimo_video.get(session['user_id'], 0) < 3:
        return jsonify({'error': 'Calma - espere um instante e tente de novo.'}), 429
    _ultimo_video[session['user_id']] = agora

    try:
        fps = int(request.form.get('fps', 12))
    except ValueError:
        return jsonify({'error': 'Parâmetros inválidos'}), 400

    quadros = []
    for arq in request.files.getlist('quadro')[:MAX_QUADROS_ANIMACAO]:
        dados = arq.read(LIMITE_QUADRO_BYTES + 1)
        if len(dados) > LIMITE_QUADRO_BYTES or not dados.startswith(b'\xff\xd8'):
            return jsonify({'error': 'Quadro inválido'}), 400
        quadros.append(dados)
    if len(quadros) < 2:
        return jsonify({'error': 'Vídeo curto demais'}), 400

    try:
        saida = animar_quadros(quadros, fps)
    except Exception as e:
        print(f"[ERRO VIDEO->ANIMACAO] {e}")
        return jsonify({'error': 'Não consegui converter esse vídeo'}), 422
    return Response(saida, mimetype='image/webp')


# ==========================================
# PRÉVIA DO CONVITE (o cartão bonito na DM e no chat)
# ------------------------------------------------------------------
# Só nome, ícone e número de membros: o suficiente pra decidir entrar, e nada que vaze canais/membros. Exige login e
# um código VÁLIDO (quem chuta código não descobre servidor nenhum: o inválido e o inexistente respondem igual).
# ==========================================
_RE_CODIGO_CONVITE = re.compile(r'^[a-z0-9]{4,16}$')


@main_bp.route("/api/convite/<code>/previa")
def previa_do_convite(code):
    usuario = usuario_da_sessao()
    if not usuario:
        return jsonify({'error': 'Acesso negado'}), 401
    code = (code or '').strip().lower()
    if not _RE_CODIGO_CONVITE.match(code):
        return jsonify({'valido': False})
    try:
        convite = com_retry(lambda: Invite.query.filter_by(code=code).first())
        if not convite or not convite.esta_valido():
            return jsonify({'valido': False})
        srv = com_retry(lambda: Server.query.get(convite.server_id))
        if not srv:
            return jsonify({'valido': False})
        membros = com_retry(lambda: db.session.query(func.count()).select_from(server_members)
                            .filter(server_members.c.server_id == srv.id).scalar()) or 0
        restante_s = None
        if convite.expires_at:
            restante_s = max(0, int((convite.expires_at - br_now()).total_seconds()))
        usos_restantes = None if convite.max_uses is None else max(0, convite.max_uses - (convite.uses or 0))
        return jsonify({
            'valido': True,
            'codigo': convite.code,
            'servidor': {'nome': srv.name, 'icone': srv.icon_url, 'membros': int(membros),
                         'descricao': (srv.description or '')[:120]},
            'criado_por': convite.creator.name if convite.creator else None,
            'restante_s': restante_s,
            'usos_restantes': usos_restantes,
            'ja_membro': bool(eh_membro(usuario, srv.id)),
            # só pra quem já é membro (botão "Abrir"): quem não é não precisa do id e não ganha nada com ele
            'server_id': srv.id if eh_membro(usuario, srv.id) else None,
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PREVIA CONVITE] {e}")
        return jsonify({'valido': False})


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