"""Rodada 34: clipes da call (clipe automático que aparece, sinal (!), pop-up, cortar, mandar e baixar). O que dá pra provar sem uma call de verdade:
a lógica pura (detector e armazém) roda no Node (testes/clipes_logica.js), os arquivos estáticos prometem o que a tela precisa, o upload aceita o clipe (vídeo de até 25 MB)
e nada de dado de fora entra na tela sem escapar. O que SÓ um navegador com call real prova (gravar de verdade, cortar, enviar) foi visto à mão: ver CLAUDE.md, Rodada 34."""
import io, os, re, shutil, subprocess, sys
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, RAIZ)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['GUARDIAO'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db
from app.models import Role, Person

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ler(*partes):
    return open(os.path.join(RAIZ, *partes), encoding='utf-8').read()


# ---------------- 1. lógica pura (Node) ----------------
node = shutil.which('node')
if node:
    r = subprocess.run([node, os.path.join(RAIZ, 'testes', 'clipes_logica.js')], capture_output=True, text=True, encoding='utf-8')
    ultima = (r.stdout.strip().splitlines() or [''])[-1]
    ok(r.returncode == 0, 'detector e armazém de clipes (Node): ' + ultima)
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-800:])
else:
    print('PULADO (sem node no PATH): testes/clipes_logica.js')

# ---------------- 2. arquivos e ganchos no chat ----------------
js = ler('app', 'static', 'js', 'clipes.js')
css = ler('app', 'static', 'css', 'clipes.css')
html = ler('app', 'templates', 'chat.html')
init = ler('app', '__init__.py')
ok("filename='css/clipes.css'" in html and "filename='js/clipes.js'" in html and 'clipes_css_v' in html and 'clipes_js_v' in html, 'o chat carrega clipes.css e clipes.js com versão (?v=)')
ok("'clipes_css_v'" in init and "'clipes_js_v'" in init, 'as versões dos arquivos novos são injetadas no template')
ok(html.index("js/clipes.js") < html.index('Clipes.iniciar('), 'o clipes.js carrega antes de ser iniciado')
for velho in ('clip-gaveta', 'clip-edit-modal', 'clip-trim', 'candidatosAutoClip', 'compositorBuffer', 'montarClipeDoBuffer', 'abrirEdicaoClipe', 'pollerAutoClipId', 'segmentoCompleto'):
    ok(velho not in html, f'o chat não tem mais "{velho}" (a heurística e o corte de mentira antigos saíram)')
for gancho in ('Clipes.iniciar(', 'Clipes.aoEntrarNaCall()', 'Clipes.aoSairDaCall()', 'Clipes.clipar()', 'Clipes.definirAuto('):
    ok(gancho in html, f'o chat chama {gancho}')
# ids que a sessão do layout da call (botão "+") mantém: sem eles o clipe quebra
for ident in ('id="clip-alerta"', 'id="pop-btn-clipar"', 'id="switch-clip-auto"', 'id="btn-main-clip"', 'id="media-popup"'):
    ok(ident in html, f'continua no chat: {ident}')
ok(re.search(r'function disconnectCall\(\) \{.*?pararBufferClipe\(\);', html, re.S) is not None, 'sair da call chama pararBufferClipe() (os clipes somem junto com a call)')
ok(js.count('Clipes = (() =>') == 1 and 'module.exports = { ClipesDetector, ClipesArmazem }' in js, 'clipes.js exporta a lógica pura pro Node e tem o objeto Clipes')

# ---------------- 3. o que o pedido do dono promete ----------------
ok('TTL_MS = 20 * 60 * 1000' in js, 'cada clipe vive 20 minutos')
ok("armazem.limpar('fim')" in js and 'sinal.classList.remove' in js and 'fecharModal' in js, 'a call acabou: todos os clipes somem, o sinal some e o pop-up fecha')
ok("sinal.classList.toggle('visivel', total > 0)" in js, 'o sinal (!) fica enquanto houver clipe')
ok("sinal.classList.add('chegou', 'dica')" in js and '.clip-alerta.chegou' in css and '.clip-alerta.tem-novos::before' in css, 'clipe novo: o sinal faz uma animação (chacoalha, anel e dica)')
ok('INTERVALO_MIN_MS = 45000' in js and "'risada'" in js and 'GRITO' in js and 'junto3' in js, 'gatilhos: pico de volume, risada e gente falando junto, com tempo mínimo entre clipes')
ok("'dm'" in js and "'canal'" in js and 'data-cl="baixar"' in js and 'data-cl="cortar"' in js, 'dá pra cortar, mandar pra alguém (DM), mandar num chat (canal) e baixar')
ok(re.search(r'cl-chip novo.*?cl-chip visto.*?cl-chip feito', js, re.S) is not None, 'a lista separa o que é novo, o que já foi visto e o que já teve ação')
ok('voltarLista(c.id)' in js and '.cl-card.cl-destaca' in css or '.cl-grade .cl-card.cl-destaca' in css, 'depois de agir, volta pra lista e o cartão da ação ganha uma animação')
ok('requestAnimationFrame(desenhar' not in js and 'setInterval(desenhar' in js, 'o compositor desenha por setInterval (rAF para com a janela escondida e o gravador nem começava)')
ok('createMediaElementSource' in js and 'new MediaRecorder' in js and 'ffmpeg' not in js.split('*/')[0].lower().replace('sem ffmpeg', ''), 'o corte é de verdade: toca o trecho e grava de novo (sem ffmpeg)')
ok('LIMITE_MB = 25' in js and 'ctx.upload(' in js, 'o clipe sobe pelo upload de sempre, com o limite de 25 MB avisado antes')
ok(re.search(r'ctx\.enviarDM\(alvo, dados\)', js) and re.search(r'ctx\.enviarCanal\(alvo, dados\)', js), 'mandar usa os eventos de mensagem de sempre (a outra pessoa recebe ao vivo, regra 6)')

# ---------------- 4. XSS: nada de fora entra no innerHTML sem escapar ----------------
ok('${a.nome' not in js.replace('${T(a.nome)}', '') and '${c.name' not in js.replace('${T(c.name)}', '') and '${g.servidor' not in js.replace('${T(g.servidor)}', ''), 'nome de amigo, de canal e de servidor passam por esc()')
ok("ctx.escUrl(a.avatar)" in js and 'data-nome="${T(a.nome)}"' in js, 'avatar passa por escUrl e o nome no atributo é escapado')
ok(re.search(r"data:image\\/jpeg;base64,\[A-Za-z0-9\+/=\]\+\$", js) is not None, 'a miniatura só entra se for um JPEG em base64 gerado aqui')
ok('eval(' not in js and 'new Function' not in js and 'document.write' not in js, 'sem eval/Function/document.write')

# ---------------- 5. CSS: só transform/opacity nas animações ----------------
chaves = re.findall(r'@keyframes\s+(\w+)\s*\{(.*?\})\s*\}', css, re.S)
ok(len(chaves) >= 8, f'as animações do clipes.css foram encontradas ({len(chaves)})')
for nome, corpo in chaves:
    props = set(re.findall(r'([a-z-]+)\s*:', re.sub(r'\([^)]*\)', '', corpo)))
    ok(props <= {'transform', 'opacity'}, f'@keyframes {nome} só mexe em transform/opacity ({sorted(props)})')
ok('body.rolando .clip-alerta::before' in css, 'o anel do sinal pausa com body.rolando')
ok('.call-janela.mini .clip-alerta' in css, 'o sinal tem tamanho próprio na janelinha da call')
ok(re.search(r'\.cl-overlay \{[^}]*padding', css) and '@media (max-width: 720px)' in css, 'o pop-up tem layout de celular')

# ---------------- 6. upload do clipe (vídeo até 25 MB) ----------------
import cloudinary.uploader as cu
subidas = []
cu.upload = lambda arq, **kw: (subidas.append(kw), {'secure_url': 'https://res.cloudinary.com/x/video/upload/clipe.webm'})[1]
with app.app_context():
    db.create_all()
    papel = Role(name='MEMBROS', color='#7289da'); db.session.add(papel); db.session.commit()
    ana = Person(name='Ana', email='ana@teste.local', role_id=papel.id, username='ana'); db.session.add(ana); db.session.commit()
    cl = app.test_client()
    with cl.session_transaction() as s:
        s['user_id'] = ana.id
    MB = 1024 * 1024
    webm = lambda n: io.BytesIO(b'\x1a\x45\xdf\xa3' + b'\x00' * (n - 4))
    png = lambda n: io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * (n - 8))
    post = lambda f, nome: cl.post('/api/upload', data={'file': (f, nome)}, content_type='multipart/form-data')
    r = post(webm(1 * MB), 'clipe.webm')
    ok(r.status_code == 200 and r.get_json()['tipo'] == 'video', 'clipe pequeno sobe como vídeo')
    r = post(webm(7 * MB), 'clipe.webm')
    ok(r.status_code == 200 and r.get_json()['url'].endswith('clipe.webm'), 'clipe de 7 MB sobe (antes o teto global de 5 MB cortava e dizia "imagem grande demais")')
    r = post(webm(24 * MB), 'clipe.webm')
    ok(r.status_code == 200, 'vídeo de 24 MB sobe')
    r = post(webm(25 * MB + 512 * 1024), 'clipe.webm')
    ok(r.status_code == 400 and 'máximo 25 MB' in r.get_json()['error'], 'vídeo acima de 25 MB é recusado pela rota, com o motivo certo')
    r = post(webm(27 * MB), 'clipe.webm')
    ok(r.status_code == 413 and 'vídeo até 25 MB' in r.get_json()['error'] and 'Imagem' not in r.get_json()['error'], 'requisição enorme leva 413 com aviso que fala de vídeo e de imagem (JSON, não página de erro)')
    r = post(png(9 * MB), 'foto.png')
    ok(r.status_code == 400 and 'máximo 8 MB' in r.get_json()['error'], 'imagem acima de 8 MB continua recusada (o limite de imagem não mudou)')
    r = post(io.BytesIO(b'isso nao e um video' * 100), 'falso.webm')
    ok(r.status_code == 400 and 'vídeo de verdade' in r.get_json()['error'], 'arquivo renomeado pra .webm sem a assinatura de vídeo continua barrado')
    sem_login = app.test_client().post('/api/upload', data={'file': (webm(1 * MB), 'c.webm')}, content_type='multipart/form-data')
    ok(sem_login.status_code == 401, 'sem login não sobe nada')
    ok(all(k.get('resource_type') == 'video' for k in subidas), 'o clipe vai pro Cloudinary como vídeo')

# ---------------- 7. novidade ----------------
from app import novidades
topo = novidades.NOVIDADES[0]
ok(topo['id'] >= 37 and 'lipe' in topo['titulo'], 'entrada nova no topo das novidades (clipes da call)')

print()
print('FALHARAM:' if falhas else 'Tudo certo.', *falhas, sep='\n' if falhas else ' ')
sys.exit(1 if falhas else 0)
