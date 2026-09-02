from flask import Flask
from flask_socketio import SocketIO
from .models import db
from .config import Config  # ou simplesmente importe de app se preferir

# Instancia o socketio AQUI, quebrando o ciclo do erro!
socketio = SocketIO()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa os plugins
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    # Importa e registra as rotas
    from .main.routes import main_bp
    app.register_blueprint(main_bp)

    # Importa os eventos SÓ AGORA, depois do socketio já estar criado
    from . import events

    # Criação das tabelas blindada contra o "Sono do Neon"
    with app.app_context():
        try:
            db.create_all()
            print("[BAZINGA INFO] Banco de dados conectado com sucesso!")
        except Exception as e:
            print(f"[BAZINGA AVISO] Banco de dados Neon dormindo no boot. O site vai ligar mesmo assim! Detalhe: {e}")

    return app