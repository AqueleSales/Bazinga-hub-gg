import sys
import os

# Adiciona a raiz do projeto ao sys.path para garantir que o Python ache o config.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from flask_socketio import SocketIO
from .models import db

socketio = SocketIO()

# Nome exibido do app. Trocar aqui troca no chat, login, manifesto do PWA etc.
# (identificadores internos - colunas do banco, eventos do socket - mantêm o
# nome antigo de propósito: renomear isso exigiria migração sem ganho nenhum.)
APP_NOME = "Panteão"
MOEDA_NOME = "Dracmas"
MOEDA_SIGLA = "DRC"


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
    socketio.init_app(app, cors_allowed_origins="*")

    # --- INÍCIO DO NOVO CÓDIGO (Registrando o OAuth) ---
    from .auth.routes import auth_bp, init_oauth
    init_oauth(app)
    app.register_blueprint(auth_bp)
    # --- FIM DO NOVO CÓDIGO ---

    from .main.routes import main_bp
    app.register_blueprint(main_bp)

    from . import events

    def _versao_estatico(caminho):
        """Data de modificação do arquivo estático: vira ?v=<n> na URL, então um deploy novo nunca serve CSS/JS velho do cache."""
        try:
            return int(os.path.getmtime(os.path.join(app.static_folder, caminho)))
        except OSError:
            return 0

    @app.context_processor
    def _injetar_marca():
        return {'app_nome': APP_NOME, 'moeda_nome': MOEDA_NOME, 'moeda_sigla': MOEDA_SIGLA,
                'cosm_css_v': _versao_estatico('css/cosmeticos.css'), 'cosm_js_v': _versao_estatico('js/cosmeticos.js')}

    with app.app_context():
        try:
            db.create_all()
            print("[BAZINGA INFO] Banco de dados conectado com sucesso!")
            adicionar_colunas_que_faltam()
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