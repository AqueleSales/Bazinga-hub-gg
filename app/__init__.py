import sys
import os
import time

# Adiciona a raiz do projeto ao sys.path para garantir que o Python ache o config.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, request, session
from flask.sessions import SecureCookieSessionInterface
from flask_socketio import SocketIO
from .models import db

socketio = SocketIO()

# Nome exibido do app. Trocar aqui troca no chat, login, manifesto do PWA etc.
# (identificadores internos - colunas do banco, eventos do socket - mantêm o
# nome antigo de propósito: renomear isso exigiria migração sem ganho nenhum.)
APP_NOME = "Pantheon"
MOEDA_NOME = "Dracmas"
MOEDA_SIGLA = "DRC"

# Versão do que está no ar. Vai no HTML (o que a aba carregou) e é reenviada pelo socket a cada conexão: se as duas
# divergirem, a aba é velha (ficou aberta durante um deploy) e o cliente pede pra recarregar. Sem isso, uma aba
# antiga falava um "dialeto" velho com o servidor novo (call, mapa, mensagens) e parecia bug sem causa.
APP_VERSAO = (os.environ.get('RENDER_GIT_COMMIT') or '')[:10] or str(int(time.time()))


def _origens_do_socket():
    """Origens que podem abrir o WebSocket. Antes era "*": qualquer site aberto no navegador da pessoa podia tentar falar com o
    servidor em nome dela. Em produção vale só o endereço do app (RENDER_EXTERNAL_URL, o endereço fixo e ORIGENS_PERMITIDAS, separadas
    por vírgula, pra domínio próprio). Fora do Render devolve None = o padrão do python-engineio: só a mesma origem da página."""
    if not os.getenv('RENDER'):
        return None
    extras = [o.strip().rstrip('/') for o in (os.getenv('ORIGENS_PERMITIDAS') or '').split(',') if o.strip()]
    base = [(os.getenv('RENDER_EXTERNAL_URL') or '').rstrip('/'), 'https://bazinga-hub-gg.onrender.com']
    return sorted({o for o in base + extras if o})


def create_app():
    app = Flask(__name__)

    # --- CÓDIGO À PROVA DE BALAS ---
    try:
        # Tenta achar o config.py na raiz do projeto
        from config import Config
    except ImportError:
        # Se não achar na raiz, pega o config.py que está dentro da pasta app
        from .config import Config

    app.config.from_object(Config)

    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins=_origens_do_socket())

    # --- INÍCIO DO NOVO CÓDIGO (Registrando o OAuth) ---
    from .auth.routes import auth_bp, init_oauth
    init_oauth(app)
    app.register_blueprint(auth_bp)
    # --- FIM DO NOVO CÓDIGO ---

    from .main.routes import main_bp
    app.register_blueprint(main_bp)

    from .admin import admin_bp
    app.register_blueprint(admin_bp)

    class _SessaoCookie(SecureCookieSessionInterface):
        def should_set_cookie(self, app, session):
            # Sessão permanente renova o cookie em TODA resposta (é o que faz o prazo andar a cada visita). Em arquivo
            # estático isso são dezenas de Set-Cookie por carregamento de página, sem ganho nenhum.
            if request.endpoint == 'static' and not session.modified:
                return False
            return super().should_set_cookie(app, session)

    app.session_interface = _SessaoCookie()

    @app.before_request
    def _login_que_dura():
        # Quem já estava logado com o cookie "de sessão" (criado antes da correção, some ao fechar o navegador) vira
        # permanente na próxima visita, sem precisar passar pelo Google de novo.
        if request.endpoint != 'static' and 'user_id' in session and not session.permanent:
            session.permanent = True

    # Compressão (gzip) dos arquivos estáticos de texto: os temas gerados (cosm_<categoria>.css/js) somam alguns MB crus mas comprimem ~8x.
    # O servidor de arquivos do Flask não comprime; sem isto o 1º carregamento no celular baixaria tudo cru. Guarda o resultado em memória
    # (chave = caminho + data do arquivo), então comprime uma vez só por deploy.
    import gzip as _gzip
    _cache_gz = {}
    _TIPOS_GZ = ('text/css', 'text/javascript', 'application/javascript', 'application/json', 'image/svg+xml', 'text/plain')

    @app.after_request
    def _cabecalhos_de_seguranca(resp):
        # Não sobrescreve o que uma rota já definiu. O app tem CSS/JS inline (chat.html), então uma CSP com `script-src` quebraria
        # tudo: aqui ficam só as diretivas que não dependem disso (quem pode embutir a página, <base> e plugins).
        h = resp.headers
        h.setdefault('X-Frame-Options', 'SAMEORIGIN')
        h.setdefault('X-Content-Type-Options', 'nosniff')
        h.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')   # o player do YouTube exige Referer
        h.setdefault('Permissions-Policy', 'camera=(self), microphone=(self), geolocation=(self), display-capture=(self), payment=(), usb=()')
        h.setdefault('Content-Security-Policy', "frame-ancestors 'self'; base-uri 'self'; object-src 'none'")
        if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https':
            h.setdefault('Strict-Transport-Security', 'max-age=31536000')
        return resp

    @app.after_request
    def _comprimir_estatico(resp):
        try:
            if (request.method != 'GET' or resp.status_code != 200 or not request.path.startswith('/static/') or resp.headers.get('Content-Encoding')
                    or 'gzip' not in (request.headers.get('Accept-Encoding') or '') or (resp.mimetype or '') not in _TIPOS_GZ):
                return resp
            chave = (request.path, resp.headers.get('ETag') or resp.headers.get('Last-Modified') or '')
            dados = _cache_gz.get(chave)
            if dados is None:
                resp.direct_passthrough = False
                bruto = resp.get_data()
                if len(bruto) < 2048:
                    return resp
                dados = _gzip.compress(bruto, 6)
                if len(_cache_gz) > 400:
                    _cache_gz.clear()
                _cache_gz[chave] = dados
            resp.direct_passthrough = False
            resp.set_data(dados)
            resp.headers['Content-Encoding'] = 'gzip'
            resp.headers['Content-Length'] = str(len(dados))
            resp.headers.add('Vary', 'Accept-Encoding')
        except Exception as e:      # compressão é só otimização: nunca derruba um arquivo estático
            print(f'[GZIP ESTATICO] {e}')
        return resp

    from . import events
    from .novidades import novidade_atual

    def _versao_estatico(caminho):
        """Data de modificação do arquivo estático: vira ?v=<n> na URL, então um deploy novo nunca serve CSS/JS velho do cache."""
        try:
            return int(os.path.getmtime(os.path.join(app.static_folder, caminho)))
        except OSError:
            return 0

    def _servidores_ice():
        """STUN + TURN da call. TURN próprio (TURN_URLS separado por vírgula, TURN_USERNAME, TURN_CREDENTIAL) vai na
        frente: o relay público grátis (openrelay) é instável, e sem relay quem está atrás de NAT mais fechado (rede de
        faculdade, 4G) nunca conecta - parece que "sumiu da call"."""
        lista = [{'urls': 'stun:stun.l.google.com:19302'}, {'urls': 'stun:global.stun.twilio.com:3478'}]
        proprios = [u.strip() for u in (os.environ.get('TURN_URLS') or '').split(',') if u.strip()]
        if proprios:
            lista.append({'urls': proprios, 'username': os.environ.get('TURN_USERNAME', ''),
                          'credential': os.environ.get('TURN_CREDENTIAL', '')})
        for u in ('turn:openrelay.metered.ca:80', 'turn:openrelay.metered.ca:443', 'turn:openrelay.metered.ca:443?transport=tcp'):
            lista.append({'urls': u, 'username': 'openrelayproject', 'credential': 'openrelayproject'})
        return lista

    @app.context_processor
    def _injetar_marca():
        from .cosmeticos import GERADO
        # temas gerados (tools/cosm/gerar.js): um par css/js por categoria, cada um com a própria versão (?v=) pro navegador nunca servir arquivo velho
        cosm_gen = [{'cat': c, 'css_v': _versao_estatico(f'css/cosm_{c}.css'), 'js_v': _versao_estatico(f'js/cosm_{c}.js')} for c in GERADO.get('arquivos', [])]
        return {'cosm_gen': cosm_gen, 'cosm_base_css_v': _versao_estatico('css/cosm_base.css'),
                'app_nome': APP_NOME, 'moeda_nome': MOEDA_NOME, 'moeda_sigla': MOEDA_SIGLA,
                'cosm_css_v': _versao_estatico('css/cosmeticos.css'), 'cosm_js_v': _versao_estatico('js/cosmeticos.js'), 'cosm_temas_css_v': _versao_estatico('css/cosm_temas.css'), 'cosm_temas_js_v': _versao_estatico('js/cosm_temas.js'),
                'loja_css_v': _versao_estatico('css/loja.css'), 'loja_js_v': _versao_estatico('js/loja.js'),
                'bazar_css_v': _versao_estatico('css/bazar.css'), 'bazar_js_v': _versao_estatico('js/bazar.js'),
                'titulos_css_v': _versao_estatico('css/titulos.css'), 'efeitos_js_v': _versao_estatico('js/efeitos.js'), 'efeitos_css_v': _versao_estatico('css/efeitos.css'), 'explorar_css_v': _versao_estatico('css/explorar.css'), 'mapa_social_css_v': _versao_estatico('css/mapa_social.css'), 'mapa_social_js_v': _versao_estatico('js/mapa_social.js'), 'notas_mapa_css_v': _versao_estatico('css/notas_mapa.css'), 'notas_mapa_js_v': _versao_estatico('js/notas_mapa.js'), 'conexoes_css_v': _versao_estatico('css/conexoes.css'), 'conexoes_js_v': _versao_estatico('js/conexoes.js'), 'explorar_js_v': _versao_estatico('js/explorar.js'), 'passe_css_v': _versao_estatico('css/passe.css'), 'passe_js_v': _versao_estatico('js/passe.js'), 'admin_css_v': _versao_estatico('css/admin.css'), 'admin_js_v': _versao_estatico('js/admin.js'), 'admin_graficos_js_v': _versao_estatico('js/admin_graficos.js'),
                'musica_css_v': _versao_estatico('css/musica.css'), 'musica_js_v': _versao_estatico('js/musica.js'),
                'cargos_css_v': _versao_estatico('css/cargos.css'), 'cargos_js_v': _versao_estatico('js/cargos.js'),
                'ordem_css_v': _versao_estatico('css/ordem.css'), 'ordem_js_v': _versao_estatico('js/ordem.js'),
                'app_versao': APP_VERSAO, 'ice_servers': _servidores_ice(), 'novidade_atual': novidade_atual()}

    with app.app_context():
        try:
            db.create_all()
            print("[BAZINGA INFO] Banco de dados conectado com sucesso!")
            adicionar_colunas_que_faltam()
            from .efeitos import carregar as _carregar_efeitos
            _carregar_efeitos()   # efeitos do Estúdio entram no catálogo (ver app/efeitos.py)
        except Exception as e:
            print(f"[BAZINGA AVISO] Banco de dados Neon dormindo no boot. O site vai ligar mesmo assim! Detalhe: {e}")

    return app


def adicionar_colunas_que_faltam():
    """Rede de segurança contra o bug nº 1 do projeto: coluna nova no models.py
    que nunca chegou no banco real (o `create_all` só cria tabela, não coluna).

    No boot compara cada tabela do modelo com a do banco e faz ALTER TABLE ADD COLUMN
    no que faltar. Só adiciona (nunca apaga/altera), sem NOT NULL nem DEFAULT - então o
    código trata None como "falso/vazio" nas colunas novas. O `atualizar_banco.py`
    continua valendo para ajustes de dados e índices.
    """
    from sqlalchemy import inspect, text
    try:
        insp = inspect(db.engine)
        existentes = set(insp.get_table_names())
        for tabela in db.metadata.sorted_tables:
            if tabela.name not in existentes:
                continue
            tem = {c['name'] for c in insp.get_columns(tabela.name)}
            for col in tabela.columns:
                if col.name in tem:
                    continue
                tipo = col.type.compile(dialect=db.engine.dialect)
                try:
                    db.session.execute(text(f'ALTER TABLE "{tabela.name}" ADD COLUMN "{col.name}" {tipo}'))
                    db.session.commit()
                    print(f"[MIGRACAO] Coluna criada: {tabela.name}.{col.name} ({tipo})")
                except Exception as e:
                    db.session.rollback()
                    print(f"[MIGRACAO] Não consegui criar {tabela.name}.{col.name}: {e}")
    except Exception as e:
        db.session.rollback()
        print(f"[MIGRACAO] Verificação de colunas pulada: {e}")