import os
from flask import Blueprint, redirect, url_for, session
from authlib.integrations.flask_client import OAuth
from app.models import db, Person

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
oauth = OAuth()


# Essa função será chamada lá no __init__.py principal para ligar o OAuth ao Flask
def init_oauth(app):
    oauth.init_app(app)

    # Configurando o Google
    oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'  # Pedimos apenas o e-mail e dados de perfil públicos
        }
    )


@auth_bp.route('/login/<provider>')
def login(provider):
    # Cria o cliente (Google, Discord, etc)
    client = oauth.create_client(provider)
    if not client:
        return "Provedor de login não configurado", 404

    # Diz pro Google para onde ele deve devolver o usuário depois de logar
    redirect_uri = url_for('auth.callback', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


@auth_bp.route('/callback/<provider>')
def callback(provider):
    client = oauth.create_client(provider)
    token = client.authorize_access_token()

    # Pega as informações do usuário devolvidas pelo Google
    user_info = token.get('userinfo')

    email = user_info.get('email')
    name = user_info.get('name')
    avatar = user_info.get('picture')
    provider_id = user_info.get('sub')

    # Verifica se o usuário já existe no nosso banco (Neon)
    user = Person.query.filter_by(email=email).first()

    if not user:
        # Se for a primeira vez acessando, cadastra ele!
        user = Person(name=name, email=email, avatar=avatar, provider_id=provider_id)
        db.session.add(user)
        db.session.commit()
    else:
        # Se já existir, só atualiza a foto caso ele tenha mudado no Google
        if user.avatar != avatar:
            user.avatar = avatar
            db.session.commit()

    # O momento mágico: Criando a Sessão (Crachá) do Bazinga Hub
    session['person_id'] = user.id

    # Volta pra tela inicial logado
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    # Destrói o "crachá" da pessoa
    session.pop('person_id', None)
    return redirect(url_for('main.index'))