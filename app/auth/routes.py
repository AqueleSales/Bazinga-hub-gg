from flask import Blueprint, redirect, url_for, session
from authlib.integrations.flask_client import OAuth
from app import db
from app.models import Person, Role
from app.utils import com_retry, comitar_com_retry
import os

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


def cargo_padrao_id():
    """Cargo de quem acabou de entrar.

    Antes isso era `role_id=1` fixo - e o Role 1 do seed.py é MODERADORES,
    ou seja, todo mundo que logava com o Google virava moderador. Agora procura
    o cargo de membro pelo nome e, se o seed nunca rodou, entra sem cargo
    (em vez de estourar erro de chave estrangeira).
    """
    cargo = com_retry(lambda: Role.query.filter_by(name="MEMBROS").first())
    return cargo.id if cargo else None


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
        def criar():
            novo = Person(name=name, email=email, avatar=avatar,
                          provider_id=provider_id, role_id=cargo_padrao_id())
            db.session.add(novo)
            return novo

        user = comitar_com_retry(criar)
    elif user.avatar != avatar:
        # comitar_com_retry e não com_retry(db.session.commit): se o commit
        # falha, o rollback do retry descarta a alteração e a tentativa
        # seguinte comitaria uma sessão vazia.
        def atualizar_avatar():
            user.avatar = avatar

        comitar_com_retry(atualizar_avatar)

    session['user_id'] = user.id

    # Se a pessoa chegou por um link de convite antes de logar, volta pra ele
    # em vez de jogar na home e perder o convite.
    codigo = session.pop('convite_pendente', None)
    if codigo:
        return redirect(url_for('main.entrar_por_link', code=codigo))

    # Quem entrou pela página /entrar não passa pela home da Bazinga:
    # cai direto na tela de "abrir o app".
    if session.pop('veio_do_entrar', None):
        return redirect(url_for('main.abrir'))

    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('main.index'))