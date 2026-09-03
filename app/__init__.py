import sys
import os

# Adiciona a raiz do projeto ao sys.path para garantir que o Python ache o config.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from flask_socketio import SocketIO
from .models import db

socketio = SocketIO()


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

    with app.app_context():
        try:
            db.create_all()
            print("[BAZINGA INFO] Banco de dados conectado com sucesso!")
        except Exception as e:
            print(f"[BAZINGA AVISO] Banco de dados Neon dormindo no boot. O site vai ligar mesmo assim! Detalhe: {e}")

    return app