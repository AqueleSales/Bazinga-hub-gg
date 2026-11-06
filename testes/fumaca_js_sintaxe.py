"""Rodada 39: o JS que o servidor entrega precisa PARSEAR. Erro de sintaxe no chat.html (ou em um dos módulos) derruba o app inteiro sem aviso
(a tela fica sem nada funcionando), e nenhum outro teste enxerga isso porque ninguém executa o JS. Aqui o /chat é renderizado de verdade
(com Jinja), cada <script> inline é checado no Node (`node --check`) e todo arquivo de static/js também.
Roda sem navegador. Com o Node ausente o teste avisa e passa (o resto da suíte não depende dele)."""
import os, re, subprocess, sys, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db
from app.models import Role, Person

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

NODE = shutil.which('node')
if not NODE:
    print('AVISO: node não encontrado: checagem de sintaxe do JS pulada')
    sys.exit(0)

app = create_app()
tmp = tempfile.mkdtemp(prefix='sintaxe_')

def checar(nome, codigo):
    arq = os.path.join(tmp, nome)
    open(arq, 'w', encoding='utf-8').write(codigo)
    r = subprocess.run([NODE, '--check', arq], capture_output=True, text=True, encoding='utf-8')
    return r.returncode == 0, (r.stderr or '')[:600]

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    p = Person(name='Ana', email='a@x', role_id=r.id, username='ana'); db.session.add(p); db.session.commit()
    fc = app.test_client()
    with fc.session_transaction() as s: s['user_id'] = p.id
    resp = fc.get('/chat')
    ok(resp.status_code == 200, f'/chat renderiza (status {resp.status_code})')
    html = resp.get_data(as_text=True)

# scripts inline do HTML renderizado
sem_comentarios = re.sub(r'<!--.*?-->', '', html, flags=re.S)       # comentário HTML que cita <script> não é script
inline = [m.group(1) for m in re.finditer(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', sem_comentarios, re.S) if m.group(1).strip()]
ok(len(inline) >= 1, f'{len(inline)} scripts inline no /chat')
for i, codigo in enumerate(inline):
    bom, erro = checar(f'inline_{i}.js', codigo)
    ok(bom, f'script inline #{i} ({len(codigo)} caracteres) parseia' + ('' if bom else '\n' + erro))

# cada arquivo de static/js (os módulos carregados pelo chat e pelo resto)
pasta = os.path.join(RAIZ, 'app', 'static', 'js')
for nome in sorted(os.listdir(pasta)):
    if not nome.endswith('.js') or nome.endswith('.min.js'):
        continue
    codigo = open(os.path.join(pasta, nome), encoding='utf-8').read()
    bom, erro = checar(nome, codigo)
    ok(bom, f'static/js/{nome} parseia' + ('' if bom else '\n' + erro))

# os módulos novos desta rodada estão no /chat e na ordem certa (os scripts do chat usam os globais deles)
for modulo in ('avisos.js', 'texto_rico.js', 'stream.js', 'compartilhar.js'):
    ok(f'js/{modulo}' in html, f'{modulo} é carregado pelo /chat')
ok(html.index('js/texto_rico.js') < html.index('const rawChannelId'), 'texto_rico.js carrega antes do script principal')

shutil.rmtree(tmp, ignore_errors=True)
print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
