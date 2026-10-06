"""Login do app desktop (código de uso único + PKCE) e service worker (o que pode e o que nunca pode ser cacheado)."""
import os, sys, time, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, APP_VERSAO
from app.models import Role, Person
from app.auth import routes as auth_routes

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def novo_par():
    verificador = os.urandom(24).hex()
    return verificador, hashlib.sha256(verificador.encode()).hexdigest()


def pegar_codigo(html):
    ini = html.index('panteao://auth?codigo=') + len('panteao://auth?codigo=')
    fim = html.index('"', ini)
    return html[ini:fim]


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ana = Person(name='Ana', email='ana@x', role_id=r.id, username='ana'); db.session.add(ana); db.session.commit()
    ana_id = ana.id

    # ---- /entrar?desktop=1 só vale com desafio de 64 hex ----
    cli = app.test_client()
    resp = cli.get('/entrar?desktop=1&desafio=lixo')
    with cli.session_transaction() as s:
        ok('desktop_desafio' not in s, 'desafio inválido não é guardado na sessão')
    verificador, desafio = novo_par()
    cli = app.test_client()
    resp = cli.get(f'/entrar?desktop=1&desafio={desafio}')
    with cli.session_transaction() as s:
        ok(s.get('desktop_desafio') == desafio, 'desafio válido fica na sessão do navegador')

    # ---- já logado no navegador: pula o Google e emite o código direto ----
    cli = app.test_client()
    with cli.session_transaction() as s:
        s['user_id'] = ana_id
    resp = cli.get(f'/entrar?desktop=1&desafio={desafio}', follow_redirects=True)
    html = resp.get_data(as_text=True)
    ok('panteao://auth?codigo=' in html, 'navegador logado recebe a página que devolve o código ao app')
    codigo = pegar_codigo(html)

    # ---- verificador errado NÃO troca (e queima o código) ----
    app_cli = app.test_client()
    resp = app_cli.get(f'/auth/desktop/trocar?codigo={codigo}&verificador=errado')
    with app_cli.session_transaction() as s:
        ok('user_id' not in s, 'verificador errado não cria sessão')
    resp = app_cli.get(f'/auth/desktop/trocar?codigo={codigo}&verificador={verificador}')
    with app_cli.session_transaction() as s:
        ok('user_id' not in s, 'código já foi queimado pela tentativa errada')

    # ---- caminho feliz + uso único ----
    cli = app.test_client()
    with cli.session_transaction() as s:
        s['user_id'] = ana_id
    codigo = pegar_codigo(cli.get(f'/entrar?desktop=1&desafio={desafio}', follow_redirects=True).get_data(as_text=True))
    app_cli = app.test_client()
    resp = app_cli.get(f'/auth/desktop/trocar?codigo={codigo}&verificador={verificador}')
    with app_cli.session_transaction() as s:
        ok(s.get('user_id') == ana_id, 'código + verificador certos entregam a sessão')
    ok(resp.status_code == 302 and resp.headers['Location'].endswith('/chat'), 'depois da troca vai pro /chat')
    outro = app.test_client()
    outro.get(f'/auth/desktop/trocar?codigo={codigo}&verificador={verificador}')
    with outro.session_transaction() as s:
        ok('user_id' not in s, 'o mesmo código não funciona duas vezes')

    # ---- código expirado ----
    codigo = pegar_codigo(cli.get(f'/entrar?desktop=1&desafio={desafio}', follow_redirects=True).get_data(as_text=True))
    auth_routes._codigos_desktop[codigo]['expira'] = time.time() - 1
    exp = app.test_client()
    exp.get(f'/auth/desktop/trocar?codigo={codigo}&verificador={verificador}')
    with exp.session_transaction() as s:
        ok('user_id' not in s, 'código expirado não troca')
    auth_routes._limpar_codigos_desktop()
    ok(codigo not in auth_routes._codigos_desktop, 'limpeza apaga código vencido')

    # ---- sem desktop=1 o /entrar continua igual ----
    cli = app.test_client()
    resp = cli.get('/entrar')
    ok(resp.status_code == 200 and b'btn-google' in resp.data, '/entrar normal continua mostrando o login')

    # ---- service worker ----
    cli = app.test_client()
    resp = cli.get('/sw.js')
    js = resp.get_data(as_text=True)
    ok(resp.status_code == 200 and APP_VERSAO in js, 'sw.js leva a versão do app (muda a cada deploy)')
    ok(resp.headers.get('Cache-Control') == 'no-cache', 'sw.js não é cacheado pelo navegador')
    ok("startsWith('/static/')" in js, 'sw cacheia /static')
    for proibido in ("'/chat'", "'/socket.io", "'/api/", "'/auth/"):
        ok(f"startsWith({proibido}" not in js, f'sw nunca menciona cache de {proibido}')
    ok("req.method !== 'GET'" in js, 'sw ignora POST')
    ok('__' not in js.replace('__proto__', ''), 'sw não tem placeholder sobrando')

    # ---- manifesto ----
    m = cli.get('/manifest.webmanifest').get_json()
    ok(m['start_url'] == '/chat' and m['display'] == 'standalone' and m['id'] == '/chat', 'manifesto ok')

print('\nFALHAS:' if falhas else '\nTUDO OK', falhas if falhas else '')
sys.exit(1 if falhas else 0)
