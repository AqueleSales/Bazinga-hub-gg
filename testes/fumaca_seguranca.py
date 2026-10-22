"""Segurança (auditoria de 21/10/2026): o peer_id da call só vai pra quem ENTROU nela (prévia pública sem peer_id, canal privado
sem vazar pra quem não vê), o cliente só atende ligação de peer listado pelo servidor, cabeçalhos de segurança, CORS do socket
restrito em produção e SRI nos scripts de CDN."""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, _origens_do_socket
from app import events
from app.models import Role, Person, Channel, Server

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


def vazou(msgs, peer):
    """True se o texto de algum evento recebido contém o peer_id."""
    return any(peer in json.dumps(m['args'], ensure_ascii=False) for m in msgs)


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower())
        db.session.add(p); db.session.commit(); ids[n] = p.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc)

    ana = cliente('Ana'); ev(ana)
    ana.emit('criar_servidor_discord', {'nome': 'Casa'}); ev(ana)
    srv = Server.query.filter_by(name='Casa').first()
    pub = Channel(name='voz', channel_type='voice', server_id=srv.id)
    priv = Channel(name='segredo', channel_type='voice', server_id=srv.id, is_private=True)
    db.session.add_all([pub, priv]); db.session.commit()
    ana.emit('criar_convite', {'server_id': srv.id}); cod = ev(ana, 'convite_criado')[-1]['args'][0]['code']
    for nome in ('Beto', 'Caio'):
        cl = cliente(nome); ev(cl)
        cl.emit('entrar_por_convite', {'code': cod}); ev(cl)
    ev(ana)
    priv.allowed_members.append(db.session.get(Person, ids['Beto'])); db.session.commit()
    ana = cliente('Ana'); beto = cliente('Beto'); caio = cliente('Caio')   # reconecta pra entrar na sala do servidor
    for cl in (ana, beto, caio):
        ev(cl)

    # ---------------- 1. call pública: a prévia não traz peer_id; quem está dentro recebe a lista completa ----------------
    ana.emit('entrar_call', {'canal_id': pub.id, 'peer_id': 'PEER-ANA-SECRETO'})
    da_ana = ev(ana, 'participantes_call_mudou')
    ok(any(m['args'][0].get('completa') and vazou([m], 'PEER-ANA-SECRETO') for m in da_ana), 'quem entrou recebe a lista COMPLETA (com peer_id)')
    do_caio = ev(caio)
    ok(any(m['name'] == 'participantes_call_mudou' for m in do_caio), 'quem só olha o servidor recebe a prévia da call')
    ok(not vazou(do_caio, 'PEER-ANA-SECRETO'), 'a prévia pública NÃO traz o peer_id de ninguém')
    prev = [m['args'][0] for m in do_caio if m['name'] == 'participantes_call_mudou'][-1]
    ok(not prev.get('completa') and prev['participantes'][0]['nome'] == 'Ana', 'prévia marcada como não-completa, ainda com nome e visual')
    ev(beto)

    caio.emit('listar_participantes_call', {'canal_id': pub.id})
    sob_demanda = ev(caio)
    ok(any(m['name'] == 'participantes_call_mudou' for m in sob_demanda) and not vazou(sob_demanda, 'PEER-ANA-SECRETO'),
       'a prévia sob demanda (abrir o servidor) também não traz peer_id')

    # o segundo a entrar: quem já estava dentro recebe o peer_id dele pra ligar; o de fora continua sem ver nada
    beto.emit('entrar_call', {'canal_id': pub.id, 'peer_id': 'PEER-BETO-SECRETO'})
    ok(vazou(ev(ana, 'novo_usuario_call'), 'PEER-BETO-SECRETO'), 'quem já estava na call recebe o peer_id de quem chegou (é assim que liga)')
    ok(not vazou(ev(caio), 'PEER-BETO-SECRETO'), 'quem não entrou nunca recebe o peer_id de quem entrou')
    ev(beto)

    # trocar o visual no meio da call também não pode vazar (caminho próprio em _atualizar_visual_na_call)
    events._atualizar_visual_na_call(db.session.get(Person, ids['Ana']))
    ok(not vazou(ev(caio), 'PEER-ANA-SECRETO'), 'equipar algo no meio da call não manda peer_id pra fora')
    ok(any(m['args'][0].get('completa') for m in ev(beto, 'participantes_call_mudou')), 'e quem está dentro continua recebendo a lista completa')

    beto.emit('sair_call', {'canal_id': pub.id, 'peer_id': 'PEER-BETO-SECRETO'}); ev(beto); ev(ana); ev(caio)
    ana.emit('sair_call', {'canal_id': pub.id, 'peer_id': 'PEER-ANA-SECRETO'}); ev(ana); ev(caio); ev(beto)

    # ---------------- 2. canal de voz PRIVADO: nem o aviso ao vivo vaza pra quem não pode ver ----------------
    ana.emit('entrar_call', {'canal_id': priv.id, 'peer_id': 'PEER-PRIV'}); ev(ana)
    ok(not [m for m in ev(caio) if m['name'] == 'participantes_call_mudou'],
       'quem não pode ver o canal privado não recebe NADA da call dele (nem nome, nem peer_id)')
    do_beto = ev(beto, 'participantes_call_mudou')
    ok(do_beto and not vazou(do_beto, 'PEER-PRIV'), 'quem pode ver o canal privado recebe a prévia, sem peer_id')
    caio.emit('listar_participantes_call', {'canal_id': priv.id})
    ok(not ev(caio, 'participantes_call_mudou'), 'e não consegue pedir a lista chutando o id do canal privado')
    caio.emit('entrar_call', {'canal_id': priv.id, 'peer_id': 'PEER-INTRUSO'})
    ok(any(m['name'] == 'erro_bazinga' for m in ev(caio)) and ('PEER-INTRUSO' not in json.dumps([p['peer_id'] for p in events.participantes_call.get(str(priv.id), [])])),
       'e não entra na call privada')
    ana.emit('sair_call', {'canal_id': priv.id, 'peer_id': 'PEER-PRIV'}); ev(ana)
    ok(str(priv.id) not in events._previa_restrita, 'call vazia limpa a lista de quem acompanha o canal privado')

    # ---------------- 3. cabeçalhos de segurança ----------------
    cl = app.test_client()
    for rota in ('/entrar', '/api/novidades', '/static/css/cosmeticos.css'):
        h = cl.get(rota).headers
        ok(h.get('X-Frame-Options') == 'SAMEORIGIN' and h.get('X-Content-Type-Options') == 'nosniff', f'{rota}: anti-clickjacking e nosniff')
        ok("frame-ancestors 'self'" in (h.get('Content-Security-Policy') or '') and "object-src 'none'" in h.get('Content-Security-Policy', ''), f'{rota}: CSP de enquadramento')
    h = cl.get('/entrar').headers
    ok(h.get('Referrer-Policy') == 'strict-origin-when-cross-origin', 'Referrer-Policy que o player do YouTube aceita')
    ok('microphone=(self)' in h.get('Permissions-Policy', '') and 'camera=(self)' in h.get('Permissions-Policy', ''), 'Permissions-Policy deixa mic/câmera pro próprio app')
    ok('Strict-Transport-Security' not in h, 'sem HSTS em HTTP puro (local)')
    ok('max-age=' in cl.get('/entrar', headers={'X-Forwarded-Proto': 'https'}).headers.get('Strict-Transport-Security', ''), 'HSTS atrás do proxy HTTPS')

    # ---------------- 4. CORS do WebSocket ----------------
    ok(socketio.server.eio.cors_allowed_origins != '*', 'o socket não aceita mais qualquer origem (*)')
    antes = {k: os.environ.get(k) for k in ('RENDER', 'RENDER_EXTERNAL_URL', 'ORIGENS_PERMITIDAS')}
    try:
        for k in antes:
            os.environ.pop(k, None)
        ok(_origens_do_socket() is None, 'local: mesma origem da página (padrão do engineio)')
        os.environ['RENDER'] = 'true'
        ok(_origens_do_socket() == ['https://bazinga-hub-gg.onrender.com'], 'produção: só o endereço do app')
        os.environ['RENDER_EXTERNAL_URL'] = 'https://outro.onrender.com/'
        os.environ['ORIGENS_PERMITIDAS'] = 'https://pantheon.app, https://www.pantheon.app/'
        lista = _origens_do_socket()
        ok('https://outro.onrender.com' in lista and 'https://pantheon.app' in lista and 'https://www.pantheon.app' in lista and '*' not in lista,
           'produção: domínio próprio entra por ORIGENS_PERMITIDAS (sem barra final, sem "*")')
    finally:
        for k, v in antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

# ---------------- 5. o que o cliente promete (código-fonte) ----------------
raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
chat = open(os.path.join(raiz, 'app', 'templates', 'chat.html'), encoding='utf-8').read()
ok("mePeer.on('call', chamada =>" in chat and 'esperarPeerAutorizado(chamada.peer)' in chat, 'cliente: só atende ligação depois de conferir o peer')
ok(chat.count('call.answer(') == 2 and chat.index('esperarPeerAutorizado(chamada.peer)') < chat.index('call.answer(streamParaChamada())'),
   'cliente: os dois answer() (tela e voz) ficam DEPOIS da conferência')
ok('chamada.close()' in chat, 'cliente: ligação de peer não listado é derrubada')
ok('if (dados.completa) reconciliarCall(' in chat, 'cliente: só reconcilia a call com a lista completa (a prévia não traz peer_id)')
ok('peersDaCall.add(dados.peer_id)' in chat and 'peersDaCall.clear()' in chat, 'cliente: peers autorizados vêm de novo_usuario_call e da lista completa, e zeram ao sair')
for lib in ('leaflet.js', 'socket.io.js', 'leaflet.css', 'twemoji.min.js'):
    linha = next((l for l in chat.splitlines() if lib in l and ('<script' in l or '<link' in l)), '')
    ok('integrity="sha384-' in linha and 'crossorigin="anonymous"' in linha, f'SRI em {lib}')
ok('SRI_LIBS' in chat and 's.integrity = SRI_LIBS[url]' in chat and re.search(r"URL_PEERJS\]: 'sha384-", chat), 'SRI no PeerJS (carregado sob demanda)')
sw = open(os.path.join(raiz, 'app', 'main', 'routes.py'), encoding='utf-8').read()
ok("CACHE_CDN = 'cdn-v2'" in sw, 'cache de CDN do service worker trocado (entradas antigas sem CORS quebrariam o SRI)')

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
