from flask import Blueprint, redirect, url_for, session, request
from authlib.integrations.flask_client import OAuth
from app import db
from app.models import Person
import os
import time
from sqlalchemy.exc import OperationalError

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )


def com_retry(fn, tentativas=4, espera=1.5):
    """Roda fn() e tenta de novo se o Neon estiver 'acordando' de um cold start.
    3 tentativas de 1s não é suficiente às vezes - isso aqui espera mais a cada vez."""
    for tentativa in range(tentativas):
        try:
            return fn()
        except OperationalError:
            db.session.rollback()
            if tentativa == tentativas - 1:
                raise
            time.sleep(espera * (tentativa + 1))  # 1.5s, 3s, 4.5s...


@auth_bp.route('/login')
def login():
    redirect_uri = url_for('auth.callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/callback/google')
def callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')

    email = user_info.get('email')
    name = user_info.get('name')
    avatar = user_info.get('picture')
    provider_id = user_info.get('sub')

    user = com_retry(lambda: Person.query.filter_by(email=email).first())

    if not user:
        user = Person(name=name, email=email, avatar=avatar, provider_id=provider_id, role_id=1)

        def salvar():
            db.session.add(user)
            db.session.commit()

        com_retry(salvar)
    elif user.avatar != avatar:
        user.avatar = avatar
        com_retry(db.session.commit)

    session['user_id'] = user.id
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('main.index'))