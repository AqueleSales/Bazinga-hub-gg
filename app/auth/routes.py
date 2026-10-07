from flask import Blueprint, redirect, url_for, session, request, render_template
from authlib.integrations.flask_client import OAuth
from app import db
from app.models import Person, Role
from app.utils import com_retry, comitar_com_retry, gerar_username
import os
import re
import time
import hmac
import hashlib
import secrets

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


def _avatar_e_do_google(url):
    """True se a pessoa não escolheu foto própria (vazio ou foto do Google)."""
    return not url or 'googleusercontent.com' in url


@auth_bp.route('/login')
def login():
    redirect_uri = url_for('auth.callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/callback/google')
def callback():
    # Estado do OAuth que não bate (login começou em outro navegador/janela, sessão expirou) ou o Google recusou:
    # antes virava "Erro interno" e o app caía. Agora volta pra tela de entrada com um aviso.
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo') or oauth.google.userinfo(token=token)
    except Exception as e:
        print(f"[ERRO LOGIN GOOGLE] {type(e).__name__}: {e}")
        return redirect(url_for('main.entrar', erro='login'))
    if not user_info or not user_info.get('email'):
        return redirect(url_for('main.entrar', erro='login'))

    email = user_info.get('email')
    name = user_info.get('name')
    avatar = user_info.get('picture')
    provider_id = user_info.get('sub')

    user = com_retry(lambda: Person.query.filter_by(email=email).first())

    if not user:
        def criar():
            novo = Person(name=name, email=email, avatar=avatar, username=gerar_username(name, email),
                          provider_id=provider_id, role_id=cargo_padrao_id())
            db.session.add(novo)
            return novo

        user = comitar_com_retry(criar)
    elif avatar and user.avatar != avatar and _avatar_e_do_google(user.avatar):
        # Só sincroniza com o Google se a pessoa ainda usa uma foto DO GOOGLE
        # (ou nenhuma). Antes isto sobrescrevia o avatar a cada login, então
        # o GIF/foto escolhido no perfil sumia toda vez que a sessão nova
        # (outro dispositivo, outra rede, cookie limpo) passava por aqui.
        #
        # comitar_com_retry e não com_retry(db.session.commit): se o commit
        # falha, o rollback do retry descarta a alteração e a tentativa
        # seguinte comitaria uma sessão vazia.
        def atualizar_avatar():
            user.avatar = avatar

        comitar_com_retry(atualizar_avatar)

    session['user_id'] = user.id

    # Login iniciado pelo app desktop: o Google roda no navegador do sistema
    # (ele barra OAuth dentro do Electron), e a sessão é entregue ao app por
    # um código de uso único em panteao://. Ver "Rodada 7" no CLAUDE.md.
    desafio = session.pop('desktop_desafio', None)
    if desafio:
        session.pop('veio_do_entrar', None)
        return _concluir_login_desktop(user.id, desafio)

    # Se a pessoa chegou por um link de convite antes de logar, volta pra ele
    # em vez de jogar na home e perder o convite.
    codigo = session.pop('convite_pendente', None)
    if codigo:
        return redirect(url_for('main.entrar_por_link', code=codigo))

    # Quem entrou pela página /entrar não passa pela home da Bazinga:
    # cai direto no Bazingacord.
    if session.pop('veio_do_entrar', None):
        return redirect(url_for('main.chat'))

    return redirect(url_for('main.index'))


# ---------------------------------------------------------------------
# Login do app desktop (Electron)
# ---------------------------------------------------------------------
# O Google barra OAuth dentro de webview ("disallowed_useragent"), então o
# app abre o navegador do sistema em /entrar?desktop=1&desafio=<sha256>.
# Depois do Google o servidor gera um CÓDIGO de uso único (~60s) e manda
# panteao://auth?codigo=... de volta pro app, que troca o código por sessão
# em /auth/desktop/trocar. A sessão (cookie) NUNCA vai na URL do protocolo.
#
# PKCE: o app guarda um `verificador` aleatório e só envia o hash dele
# (`desafio`). Quem interceptar o panteao:// não consegue trocar o código
# sem o verificador. Em memória, igual a `usuarios_conectados`: vale porque
# o deploy é -w 1 (ver Procfile).
CODIGO_DESKTOP_VALE_SEGUNDOS = 60
REGEX_DESAFIO = re.compile(r'^[a-f0-9]{64}$')
_codigos_desktop = {}   # codigo -> {'user_id', 'desafio', 'expira'}


def desafio_desktop_valido(valor):
    return bool(valor) and bool(REGEX_DESAFIO.match(valor))


def _limpar_codigos_desktop():
    agora = time.time()
    for k in [k for k, v in _codigos_desktop.items() if v['expira'] < agora]:
        _codigos_desktop.pop(k, None)


def _concluir_login_desktop(user_id, desafio):
    _limpar_codigos_desktop()
    codigo = secrets.token_urlsafe(32)
    _codigos_desktop[codigo] = {'user_id': user_id, 'desafio': desafio,
                                'expira': time.time() + CODIGO_DESKTOP_VALE_SEGUNDOS}
    return render_template('desktop_ok.html', link_app=f'panteao://auth?codigo={codigo}')


@auth_bp.route('/desktop/concluir')
def desktop_concluir():
    """Já logado no navegador e abrindo o app desktop: pula o Google e só emite o código."""
    desafio = session.pop('desktop_desafio', None)
    if 'user_id' not in session or not desafio_desktop_valido(desafio):
        return redirect(url_for('main.entrar'))
    return _concluir_login_desktop(session['user_id'], desafio)


@auth_bp.route('/desktop/trocar')
def desktop_trocar():
    """O Electron navega aqui (com o código + verificador) pra receber o cookie de sessão."""
    codigo = request.args.get('codigo', '')
    verificador = request.args.get('verificador', '')
    # pop ANTES de validar: o código morre na primeira tentativa, certa ou errada
    entrada = _codigos_desktop.pop(codigo, None)
    if not entrada or entrada['expira'] < time.time():
        return redirect(url_for('main.entrar'))
    hash_recebido = hashlib.sha256(verificador.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(hash_recebido, entrada['desafio']):
        return redirect(url_for('main.entrar'))
    session.clear()
    session['user_id'] = entrada['user_id']
    session.permanent = True
    return redirect(url_for('main.chat'))


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    # Volta pra página de bloqueio, não pra home: é de lá que se entra de
    # novo no Bazingacord.
    return redirect(url_for('main.entrar'))