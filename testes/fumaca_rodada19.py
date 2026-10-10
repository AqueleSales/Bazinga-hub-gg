"""Rodada 19 (feedback do teste com amigos): login que dura, nome Pantheon, notificações (ícone, aviso duplicado, selo que piscava),
som da call (áudio próprio por stream, fone que cala de verdade, microfone com aviso) e menus de mic/fone fora da barra lateral.

O que NÃO dá pra provar aqui: som saindo de verdade em duas pessoas (precisa de 2 aparelhos). O que dá: o cliente usa os elementos certos."""
import os, re, sys
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, RAIZ)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, APP_NOME
from app.models import Role, Person

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()

chat = ler('app/templates/chat.html')

# ---------------------------------------------------------------- login que dura
with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    p = Person(name='Ana', email='ana@x', role_id=r.id, username='ana'); db.session.add(p); db.session.commit()
    uid = p.id

ok(app.config['PERMANENT_SESSION_LIFETIME'].days >= 365, 'Login: a sessão dura pelo menos 1 ano')
cl = app.test_client()
with cl.session_transaction() as s:
    s['user_id'] = uid                       # cookie antigo, "de sessão" (sumia ao fechar o navegador)
resp = cl.get('/entrar')
cookies = [h for h in resp.headers.getlist('Set-Cookie') if h.startswith('session=')]
ok(bool(cookies) and 'expires=' in cookies[0].lower(), 'Login: quem já estava logado ganha cookie com validade na próxima visita (sem passar pelo Google)')
ok(not any(h.startswith('session=') for h in cl.get('/static/img/logo.svg').headers.getlist('Set-Cookie')), 'Login: arquivo estático não renova o cookie')
ok(not any('expires=' in h.lower() for h in app.test_client().get('/entrar').headers.getlist('Set-Cookie') if h.startswith('session=')), 'Login: visitante sem login não ganha cookie permanente')
callback = ler('app/auth/routes.py')
ok(re.search(r"session\['user_id'\] = user\.id\s*\n(?:\s*#.*\n)*\s*session\.permanent = True", callback), 'Login: o callback do Google marca a sessão como permanente')
cl.get('/auth/logout')
with cl.session_transaction() as s:
    ok('user_id' not in s, 'Login: sair da conta continua tirando o login')

# ---------------------------------------------------------------- nome
ok(APP_NOME == 'Pantheon', 'Nome: o app se chama Pantheon')
manifesto = app.test_client().get('/manifest.webmanifest').get_json()
ok(manifesto['name'] == 'Pantheon' and manifesto['short_name'] == 'Pantheon', 'Nome: o manifesto do PWA diz Pantheon')
def sem_pasta_antiga(texto):   # desktop/main.js cita "Panteão" de propósito: pasta de dados antiga e entrada antiga do "iniciar com o Windows"
    return '\n'.join(l for l in texto.splitlines() if 'userData' not in l and 'se chamava' not in l and "electron.app.Panteão" not in l and 'Panteão pra Pantheon' not in l)
ok(not any('Panteão' in sem_pasta_antiga(ler(f)) for f in ('app/static/js/bazar.js', 'app/static/js/loja.js', 'desktop/main.js', 'desktop/login.html', 'app/bazar.py')),
   'Nome: não sobrou "Panteão" em texto do app (a patente de nível 900+ é a única que mantém)')
ok(manifesto['icons'] and any(i.get('purpose') == 'monochrome' for i in manifesto['icons']), 'Notificação: o manifesto traz o ícone monocromático')

# ---------------------------------------------------------------- notificação
sw = app.test_client().get('/sw.js').get_data(as_text=True)
ok("badge: '/static/img/icone-badge.png'" in sw, 'Notificação: o aviso usa o ícone pequeno próprio (não o PNG colorido do app)')
from PIL import Image
badge = Image.open(os.path.join(RAIZ, 'app/static/img/icone-badge.png')).convert('RGBA')
visiveis = [px for px in badge.getdata() if px[3] > 0]
ok(len(visiveis) > 500 and all(px[:3] == (255, 255, 255) for px in visiveis), 'Notificação: o ícone pequeno é uma silhueta branca (o Android só usa o alfa)')
ok(badge.getpixel((0, 0))[3] == 0, 'Notificação: o ícone pequeno tem fundo transparente')
ok('window.pushNesteAparelho' in chat and re.search(r"if \(window\.pushNesteAparelho\) return;", chat), 'Notificação: com push ligado a página não manda um segundo aviso igual')
ok(re.search(r"\.dm-notification-badge\.active \{[^}]*\}", chat) and 'animation' not in re.search(r"\.dm-notification-badge\.active \{[^}]*\}", chat).group(0), 'DM: o contador de não lidas não pisca mais pra sempre')
ok("if (n.tipo === 'dm' && n.de_id && vistaAtual === 'dm' && Number(currentDmUserId) === Number(n.de_id)) novo.lida = true;" in chat, 'DM: mensagem de quem estou vendo não conta como não lida (não pisca o título/caixa)')

# ---------------------------------------------------------------- som da call
card = re.search(r"function adicionarVideoCard\(.*?\n        \}\n", chat, re.S).group(0)
ok('<video autoplay muted playsinline' in card and 'ligarAudioRemoto(card, stream)' in card, 'Call: o <video> só mostra a imagem (mudo) e o som vem de um <audio> por stream')
ok(re.search(r"function ligarAudioRemoto\(card, stream\) \{.*?a\.srcObject = stream;.*?tocarAudioRemoto\(a\);", chat, re.S), 'Call: o <audio> remoto recebe o stream e tem play() chamado na mão')
ok("showToast('O navegador está segurando o som da call." in chat and "['pointerup', 'touchend', 'click', 'keydown']" in chat, 'Call: se o navegador barrar o som, avisa e libera no próximo toque')
ok('aplicarSurdez();' in chat and re.search(r"function aplicarSurdez\(\) \{[^}]*\.muted = !!deafened", chat), 'Call: o fone desligado cala quem fala (antes só mudava o ícone)')
mv = re.search(r"function monitorarVolume\(.*?\n        \}\n", chat, re.S).group(0)
ok('new (window.AudioContext' not in mv and 'garantirAudio()' in mv, 'Call: o medidor de voz usa o AudioContext compartilhado (antes criava um por pessoa e nunca fechava)')
ok('async function abrirMicrofone()' in chat and "stream = await abrirMicrofone();" in chat and "motivoDoMicFalhou(mediaErr)" in chat, 'Call: microfone que falha tenta de novo com menos exigência e AVISA o motivo')
ok('semMicrofone' in chat and 'reaplicarMic();' in chat, 'Call: quem entrou sem microfone tenta de novo ao desmutar')
ok('diagnosticarAudioDaCall' in chat and 'bytesReceived' in chat, 'Call: ligação sem som chegando vira aviso na tela (não só console)')

# ---------------------------------------------------------------- menus de mic/fone
ok('function posicionarMenuHardware(menu, grupo)' in chat and 'document.body.appendChild(menu)' in chat, 'Menu mic/fone: vai pro <body> ao abrir (a barra lateral cortava)')
ok(re.search(r"\.hardware-menu\.flutuante \{[^}]*position: fixed[^}]*z-index: 2600", chat), 'Menu mic/fone: posição fixa, acima da call e abaixo dos modais')
ok("!e.target.closest('.hardware-menu')" in chat, 'Menu mic/fone: clicar dentro do menu (já no <body>) não fecha ele')

# ---------------------------------------------------------------- desktop
main = ler('desktop/main.js')
ok("autoplayPolicy: 'no-user-gesture-required'" in main, 'Desktop: o app libera o som automático da call')
ok("app.setAppUserModelId('gg.panteao.desktop')" in main and '"appId": "gg.panteao.desktop"' in ler('desktop/package.json'), 'Desktop: notificação do Windows sai como o app (AppUserModelId = appId)')
ok("app.setPath('userData'" in main, 'Desktop: a pasta de dados antiga é mantida (o login e as prefs sobrevivem à troca de nome)')

print('\nFALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
