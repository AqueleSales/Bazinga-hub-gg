from flask import Blueprint, redirect, url_for, session, request
from authlib.integrations.flask_client import OAuth
from app import db
from app.models import Person
import os
import time
from sqlalchemy.exc import OperationalError

auth_bp = Blueprint('auth', __name__)

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

    # MÁGICA ANTI-QUEDA AQUI:
    # Se o banco estiver dormindo, ele tenta, falha, rola pra trás e tenta de novo.
    try:
        user = Person.query.filter_by(email=email).first()
    except OperationalError:
        db.session.rollback()
        time.sleep(1)  # Dá 1 segundo pro banco terminar de acordar
        user = Person.query.filter_by(email=email).first()

    if not user:
        # Se for um usuário novo, cria e salva no banco
        user = Person(
            name=name,
            email=email,
            avatar=avatar,
            provider_id=provider_id,
            role_id=1
        )
        try:
            db.session.add(user)
            db.session.commit()
        except OperationalError:
            db.session.rollback()
            time.sleep(1)
            db.session.add(user)
            db.session.commit()
    else:
        # Se já existir, só atualiza a fotinha caso ele tenha mudado no Google
        if user.avatar != avatar:
            user.avatar = avatar
            try:
                db.session.commit()
            except OperationalError:
                db.session.rollback()
                time.sleep(1)
                db.session.commit()

    # Cria a sessão oficial do Flask
    session['user_id'] = user.id

    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('main.index'))