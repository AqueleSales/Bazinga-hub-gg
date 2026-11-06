import os

import eventlet
eventlet.monkey_patch()

from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    # O depurador do Werkzeug executa código Python de quem abrir a página de erro (com a senha do PIN, mas ainda assim): nunca ligado
    # no servidor. Em produção o app sobe por `gunicorn run:app` (este bloco nem roda); o if é pra quem rodar `python run.py` num servidor.
    socketio.run(app, debug=not (os.getenv('RENDER') or os.getenv('FLASK_ENV') == 'production'))
