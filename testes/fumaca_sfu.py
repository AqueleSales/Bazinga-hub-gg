"""Rodada 39: preparação do SFU (call híbrida P2P + LiveKit num servidor Oracle).

Configuração (só vale tudo configurado e wss://), política (P2P até o limite, depois SFU; DM sempre P2P), escolha FIXA por call (uma vez SFU, fica até esvaziar),
token JWT do LiveKit (decodificado e verificado por um HMAC independente do código), o que a PÁGINA pode ver (nunca chave nem segredo) e os eventos: só quem
está na call recebe token, ouvinte não publica, canal de stream só dá tela ao apresentador. O adaptador do navegador não existe ainda: o módulo do cliente roda
no Node (testes/call_transporte_logica.js) e prova que, sem adaptador, toda call segue P2P."""
import base64
import contextlib
import hashlib
import hmac
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
for k in ('CALL_MODE', 'CALL_P2P_MAX', 'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET'):
    os.environ.pop(k, None)
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, sfu
from app import events, sfu_events, stream_events
from app.models import Role, Person, Channel, Server

falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()


SEGREDO = 'S' * 12 + 'e-g-r-e-d-o-d-e-t-e-s-t-e-0123456789'      # 47 caracteres
CHAVE = 'APItesteSFU01'
URL = 'wss://sfu.exemplo.com'


@contextlib.contextmanager
def com_env(**kw):
    antes = {k: os.environ.get(k) for k in kw}
    try:
        for k, v in kw.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def completo(**extra):
    d = dict(LIVEKIT_URL=URL, LIVEKIT_API_KEY=CHAVE, LIVEKIT_API_SECRET=SEGREDO)
    d.update(extra)
    return com_env(**d)


def b64d(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def decodificar(token, segredo=SEGREDO):
    """Confere o JWT SEM usar o código do projeto: separa, recalcula o HMAC-SHA256 e compara. Devolve (cabecalho, carga, assinatura_ok)."""
    h, p, s = token.split('.')
    esperado = base64.urlsafe_b64encode(hmac.new(segredo.encode(), f'{h}.{p}'.encode(), hashlib.sha256).digest()).rstrip(b'=').decode()
    return json.loads(b64d(h)), json.loads(b64d(p)), hmac.compare_digest(esperado, s)


# ------------------------------------------------------------------ configuração -----------------------------------------
with com_env(CALL_MODE=None, CALL_P2P_MAX=None, LIVEKIT_URL=None, LIVEKIT_API_KEY=None, LIVEKIT_API_SECRET=None):
    ok(sfu.modo() == 'p2p' and not sfu.configurado() and not sfu.ativo(), 'sem nenhuma variável: P2P, nada configurado, nada ativo')
    ok(sfu.politica(2) == 'p2p' and sfu.politica(40) == 'p2p', 'sem configuração, até uma call enorme segue P2P')
    ok(sfu.politica_da_pagina() == {'modo': 'p2p', 'limite_p2p': 4, 'sfu': False, 'url': ''}, 'a página recebe "tudo P2P" e nenhum endereço')
with com_env(CALL_MODE='sfu'):
    ok(sfu.modo() == 'sfu' and not sfu.ativo() and sfu.politica(40) == 'p2p', 'CALL_MODE=sfu SEM as chaves não liga nada (nunca quebra a call por falta de configuração)')
for mod, esperado in (('auto', 'auto'), ('AUTO', 'auto'), (' sfu ', 'sfu'), ('P2P', 'p2p'), ('zzz', 'p2p'), ('', 'p2p')):
    with com_env(CALL_MODE=mod):
        ok(sfu.modo() == esperado, f'CALL_MODE={mod!r} vira {esperado!r}')
for lim, esperado in (('4', 4), ('2', 2), ('1', 2), ('0', 2), ('-5', 2), ('50', 50), ('999', 50), ('abc', 4), ('', 4), (None, 4), ('6', 6)):
    with com_env(CALL_P2P_MAX=lim):
        ok(sfu.limite_p2p() == esperado, f'CALL_P2P_MAX={lim!r} vira {esperado}')
for ruim in ('ws://sfu.exemplo.com', 'http://sfu.exemplo.com', 'https://sfu.exemplo.com', 'wss://', 'wss://a', 'wss://user:senha@sfu.exemplo.com', 'wss://sfu.exemplo.com/ x',
             'wss://sfu.exemplo.com/"x', 'wss://sfu.exemplo.com?x=1', 'wss://sfu .exemplo.com', 'javascript:alert(1)', 'wss://sfu.exemplo.com:99999999', ''):
    with completo(LIVEKIT_URL=ruim):
        ok(not sfu.configurado() and sfu.url_publica() == '', f'endereço inválido não configura: {ruim!r}')
for bom in ('wss://sfu.exemplo.com', 'wss://sfu.exemplo.com:7880', 'wss://sfu.exemplo.com/livekit', 'wss://150-230-1-2.nip.io'):
    with completo(LIVEKIT_URL=bom):
        ok(sfu.configurado() and sfu.url_publica() == bom, f'endereço válido: {bom}')
with completo(LIVEKIT_API_SECRET='curto'):
    ok(not sfu.configurado(), 'segredo curto (< 32) não configura')
with completo(LIVEKIT_API_KEY='x y'):
    ok(not sfu.configurado(), 'chave de API com espaço não configura')
with completo(LIVEKIT_API_KEY=''):
    ok(not sfu.configurado(), 'sem chave de API não configura')

# ------------------------------------------------------------------ política ---------------------------------------------
with completo(CALL_MODE='auto', CALL_P2P_MAX='4'):
    ok(sfu.ativo() and [sfu.politica(n) for n in (1, 2, 4, 5, 9)] == ['p2p', 'p2p', 'p2p', 'sfu', 'sfu'], 'auto: P2P até 4 pessoas, SFU a partir da 5ª')
    ok(sfu.politica(30, dm=True) == 'p2p', 'ligação de DM é sempre P2P')
    pg = sfu.politica_da_pagina()
    ok(pg == {'modo': 'auto', 'limite_p2p': 4, 'sfu': True, 'url': URL}, 'a página recebe modo, limite e endereço')
    ok(SEGREDO not in json.dumps(pg) and CHAVE not in json.dumps(pg), 'a política da página NÃO leva chave nem segredo')
with completo(CALL_MODE='sfu'):
    ok(sfu.politica(1) == 'sfu' and sfu.politica(2, dm=True) == 'p2p', 'sfu: toda call de servidor usa o SFU (DM continua P2P)')
with completo(CALL_MODE='p2p'):
    ok(not sfu.ativo() and sfu.politica(40) == 'p2p' and sfu.politica_da_pagina()['sfu'] is False, 'p2p: mesmo configurado, ninguém usa o SFU')

# ------------------------------------------------------------------ escolha fixa por call --------------------------------
with completo(CALL_MODE='auto', CALL_P2P_MAX='3'):
    sfu._transporte.clear()
    r = [sfu.ao_entrar('c1', n) for n in (1, 2, 3, 4, 5, 3)]
    ok(r == [('p2p', False), ('p2p', False), ('p2p', False), ('sfu', True), ('sfu', False), ('sfu', False)], 'a call vira SFU ao passar do limite, avisa UMA vez e fica SFU mesmo se cair de gente')
    ok(sfu.transporte_da_call('c1') == 'sfu' and sfu.transporte_da_call('c2') == 'p2p', 'o transporte é por call')
    sfu.ao_sair('c1', 2)
    ok(sfu.transporte_da_call('c1') == 'sfu', 'ainda tem gente: continua SFU')
    sfu.ao_sair('c1', 0)
    ok(sfu.transporte_da_call('c1') == 'p2p' and 'c1' not in sfu._transporte, 'call vazia esquece o transporte (a próxima nasce P2P)')
    ok(sfu.ao_entrar('dm_1_2', 9, dm=True) == ('p2p', False), 'DM nunca migra')

# ------------------------------------------------------------------ token ------------------------------------------------
with completo():
    t = sfu.emitir_token(7, 'Ana', '12', publicar=True, tela=True, agora=1_800_000_000)
    cab, carga, assin = decodificar(t)
    ok(cab == {'alg': 'HS256', 'typ': 'JWT'} and assin, 'JWT HS256 com assinatura que bate com o HMAC calculado de fora')
    ok(carga['iss'] == CHAVE and carga['sub'] == 'u7' and carga['name'] == 'Ana', 'iss = chave da API, sub = u<id>, name = nome')
    ok(carga['nbf'] == 1_800_000_000 - 10 and carga['iat'] == 1_800_000_000 and carga['exp'] == 1_800_000_000 + sfu.TOKEN_TTL_S, 'janela de validade: 10 s de folga atrás e 10 min pra frente')
    v = carga['video']
    ok(v['room'] == 'pantheon-12' and v['roomJoin'] is True and v['canSubscribe'] is True and v['canPublish'] is True, 'sala derivada da call, entra, assiste e publica')
    ok(v['canPublishSources'] == ['microphone', 'camera', 'screen_share', 'screen_share_audio'], 'com tela liberada, as 4 fontes')
    t2 = sfu.emitir_token(7, 'Ana', '12', publicar=True, tela=False, agora=1_800_000_000)
    ok(decodificar(t2)[1]['video']['canPublishSources'] == ['microphone', 'camera'], 'sem tela: só microfone e câmera')
    t3 = sfu.emitir_token(7, 'Ana', '12', publicar=False, tela=True, agora=1_800_000_000)
    v3 = decodificar(t3)[1]['video']
    ok(v3['canPublish'] is False and v3['canPublishData'] is False and 'canPublishSources' not in v3 and v3['canSubscribe'] is True, 'ouvinte: assiste, mas NÃO publica nada (nem tela, mesmo pedindo)')
    ok(decodificar(t, 'outro-segredo-qualquer-com-mais-de-32-caracteres')[2] is False, 'com outro segredo a assinatura NÃO confere')
    ok(SEGREDO not in t and SEGREDO.encode() not in b64d(t.split('.')[1]) and SEGREDO.encode() not in b64d(t.split('.')[0]), 'o segredo não aparece no token')
    nome = decodificar(sfu.emitir_token(1, 'A\x00b\nc\x7f' + 'x' * 100, 5))[1]['name']
    ok(len(nome) == 40 and all(ord(ch) >= 32 and ord(ch) != 127 for ch in nome), 'nome sem caractere de controle e com no máximo 40')
    ok(sfu.sala_do_sfu('dm_1_2') == 'pantheon-dm_1_2' and sfu.sala_do_sfu('a/b c;..') == 'pantheon-a_b_c___' and len(sfu.sala_do_sfu('x' * 500)) <= 60, 'nome da sala só tem [A-Za-z0-9_-] e é curto')
    ok(decodificar(sfu.emitir_token(3, 'Zé', '9'))[1]['sub'] == 'u3', 'o id da pessoa vira u<id> (nunca o nome)')
with com_env(LIVEKIT_URL=None, LIVEKIT_API_KEY=None, LIVEKIT_API_SECRET=None):
    try:
        sfu.emitir_token(1, 'Ana', '1'); ok(False, 'sem configuração o token deveria falhar')
    except sfu.ErroSfu:
        ok(True, 'sem configuração, emitir token levanta ErroSfu')

# ------------------------------------------------------------------ eventos ----------------------------------------------
app = create_app()
events.GRACA_CALL_SEGUNDOS = 0.3
sfu_events.ESPERA_TOKEN_S = 0


def ev(cli, nome=None):
    return [x for x in cli.get_received() if nome is None or x['name'] == nome]


def ultimo(cli, nome):
    r = ev(cli, nome)
    return r[-1]['args'][0] if r else None


with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio', 'Dani'):
        pe = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower())
        db.session.add(pe); db.session.commit(); ids[n] = pe.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc)

    ana = cliente('Ana'); ev(ana)
    ana.emit('criar_servidor_discord', {'nome': 'Sala'}); ev(ana)
    srv = Server.query.filter_by(name='Sala').first()
    voz = Channel(name='voz', channel_type='voice', server_id=srv.id)
    palco = Channel(name='palco', channel_type='palco', server_id=srv.id)
    live = Channel(name='live', channel_type='stream', server_id=srv.id)
    db.session.add_all([voz, palco, live]); db.session.commit()
    ana.emit('criar_convite', {'server_id': srv.id}); cod = ev(ana, 'convite_criado')[-1]['args'][0]['code']
    for n in ('Beto', 'Caio', 'Dani'):
        cl = cliente(n); ev(cl); cl.emit('entrar_por_convite', {'code': cod}); ev(cl)
    ana = cliente('Ana'); beto = cliente('Beto'); caio = cliente('Caio'); dani = cliente('Dani')
    for cl in (ana, beto, caio, dani):
        ev(cl)
    V, P, L = voz.id, palco.id, live.id

    # --- SFU desligado: ninguém recebe nada e a call segue igual ---
    with com_env(CALL_MODE=None, LIVEKIT_URL=None, LIVEKIT_API_KEY=None, LIVEKIT_API_SECRET=None):
        ana.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-ana'}); ev(ana)
        ana.emit('sfu_pedir_token', {'canal_id': V})
        ok((ultimo(ana, 'sfu_token') or {}).get('motivo') == 'desligado', 'SFU desligado: o pedido de token volta "desligado"')
        beto.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-beto'}); ev(beto)
        ok(not [m for m in ev(ana) if m['name'] == 'call_transporte'], 'SFU desligado: ninguém é avisado de troca de transporte')
        for cl in (ana, beto):
            cl.emit('sair_call', {'canal_id': V}); ev(cl)

    # --- auto com limite 2: a 3ª pessoa derruba a call pro SFU, uma vez só ---
    with completo(CALL_MODE='auto', CALL_P2P_MAX='2'):
        sfu._transporte.clear()
        for cl, pid in ((ana, 'p-ana'), (beto, 'p-beto')):
            cl.emit('entrar_call', {'canal_id': V, 'peer_id': pid})
        ok(not [m for m in ev(ana) + ev(beto) if m['name'] == 'call_transporte'], 'até o limite (2 pessoas) ninguém é avisado: segue P2P')
        caio.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-caio'})
        avisos = [(nome, ultimo_a) for nome, cl in (('ana', ana), ('beto', beto), ('caio', caio)) for ultimo_a in [m['args'][0] for m in ev(cl, 'call_transporte')]]
        ok(len(avisos) == 3 and all(a['transporte'] == 'sfu' and a['canal_id'] == str(V) for _, a in avisos), 'a 3ª pessoa passa do limite: as 3 recebem "call_transporte = sfu" (regra 6)')
        dani.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-dani'})
        ok(not [m for m in ev(ana) + ev(dani) if m['name'] == 'call_transporte'], 'a 4ª pessoa NÃO repete o aviso')

        # token: quem está na call recebe, com a sala certa
        ana.emit('sfu_pedir_token', {'canal_id': V}); t = ultimo(ana, 'sfu_token')
        ok(t and t['ok'] and t['url'] == URL and t['sala'] == f'pantheon-{V}' and t['identidade'] == f'u{ids["Ana"]}' and t['publica'] is True, 'Ana (na call) recebe o token com a sala e a identidade dela')
        cab, carga, assin = decodificar(t['token'])
        ok(assin and carga['video']['room'] == f'pantheon-{V}' and carga['sub'] == f'u{ids["Ana"]}', 'o token confere (assinatura, sala e identidade)')
        ok(SEGREDO not in json.dumps(t), 'a resposta do servidor NÃO leva o segredo')
        # quem está fora da call, em outra call ou sem login não recebe
        for cl, quem in ((cliente('Dani'), 'sem estar na call'),):
            ev(cl); cl.emit('sfu_pedir_token', {'canal_id': V})
            ok((ultimo(cl, 'sfu_token') or {}).get('motivo') == 'fora_da_call' and not any('token' in m['args'][0] for m in ev(cl, 'sfu_token')), f'{quem}: nada de token ("fora_da_call")')
        ana.emit('sfu_pedir_token', {'canal_id': P})
        ok((ultimo(ana, 'sfu_token') or {}).get('motivo') == 'fora_da_call', 'pedir token de OUTRA call (que a pessoa não está) é recusado')
        ana.emit('sfu_pedir_token', {'canal_id': '999999'})
        ok((ultimo(ana, 'sfu_token') or {}).get('motivo') == 'fora_da_call', 'call que não existe: recusado')
        for payload in (None, 'x', 5, [], {'canal_id': None}, {}):
            ana.emit('sfu_pedir_token', payload)
        ok(True, 'payloads quebrados não derrubam o servidor')
        anon = socketio.test_client(app)
        anon.emit('sfu_pedir_token', {'canal_id': V})
        ok(not [m for m in anon.get_received() if m['name'] == 'sfu_token'], 'sem login nem resposta')

        # freio entre pedidos
        sfu_events.ESPERA_TOKEN_S = 2.0
        sfu_events._ultimo.clear()
        ana.emit('sfu_pedir_token', {'canal_id': V}); a1 = ultimo(ana, 'sfu_token')
        ana.emit('sfu_pedir_token', {'canal_id': V}); a2 = ultimo(ana, 'sfu_token')
        ok(a1['ok'] and a2['ok'] is False and a2['motivo'] == 'calma', 'dois pedidos seguidos: o segundo leva "calma"')
        sfu_events.ESPERA_TOKEN_S = 0

        # quando todo mundo sai, a call esquece o transporte
        for cl in (ana, beto, caio, dani):
            cl.emit('sair_call', {'canal_id': V}); ev(cl)
        ok(sfu.transporte_da_call(str(V)) == 'p2p', 'call vazia: o transporte volta pra P2P')

    # --- call P2P (abaixo do limite) pede token: "p2p" ---
    with completo(CALL_MODE='auto', CALL_P2P_MAX='4'):
        sfu._transporte.clear()
        ana.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-ana2'}); ev(ana)
        ana.emit('sfu_pedir_token', {'canal_id': V})
        ok((ultimo(ana, 'sfu_token') or {}).get('motivo') == 'p2p', 'call pequena (ainda P2P) não ganha token')
        ana.emit('sair_call', {'canal_id': V}); ev(ana)

    # --- palco: ouvinte não publica; stream: só o apresentador manda tela ---
    with completo(CALL_MODE='sfu'):
        sfu._transporte.clear()
        ana.emit('entrar_call', {'canal_id': P, 'peer_id': 'pa-ana'}); beto.emit('entrar_call', {'canal_id': P, 'peer_id': 'pa-beto'})
        ev(ana); ev(beto)
        ana.emit('sfu_pedir_token', {'canal_id': P}); beto.emit('sfu_pedir_token', {'canal_id': P})
        ta, tb = ultimo(ana, 'sfu_token'), ultimo(beto, 'sfu_token')
        ok(ta and ta['ok'] and ta['publica'] is True, 'palco: o dono pode publicar')
        ok(tb and tb['ok'] and tb['publica'] is False and decodificar(tb['token'])[1]['video']['canPublish'] is False, 'palco: quem só ouve (sem falar_palco) recebe token que NÃO publica')
        for cl in (ana, beto):
            cl.emit('sair_call', {'canal_id': P}); ev(cl)

        for cl, pid in ((ana, 'ps-ana'), (beto, 'ps-beto')):
            cl.emit('entrar_call', {'canal_id': L, 'peer_id': pid})
        ev(ana); ev(beto)
        ana.emit('stream_pedir_tela', {'canal_id': L}); ev(ana); ev(beto)
        ana.emit('sfu_pedir_token', {'canal_id': L}); beto.emit('sfu_pedir_token', {'canal_id': L})
        sa, sb = ultimo(ana, 'sfu_token'), ultimo(beto, 'sfu_token')
        fa = decodificar(sa['token'])[1]['video']['canPublishSources']; fb = decodificar(sb['token'])[1]['video']['canPublishSources']
        ok(sa['tela'] is True and 'screen_share' in fa, 'stream: o apresentador (Ana) recebe a permissão de transmitir tela')
        ok(sb['tela'] is False and 'screen_share' not in fb and fb == ['microphone', 'camera'], 'stream: quem NÃO é o apresentador (Beto) só recebe microfone e câmera')
        for cl in (ana, beto):
            cl.emit('sair_call', {'canal_id': L}); ev(cl)

        # ligação de DM: sempre P2P, mesmo com o modo sfu
        a_dm = f'dm_{min(ids["Ana"], ids["Beto"])}_{max(ids["Ana"], ids["Beto"])}'
        ana.emit('entrar_call', {'canal_id': a_dm, 'peer_id': 'pd-ana'}); ev(ana)
        ana.emit('sfu_pedir_token', {'canal_id': a_dm})
        ok((ultimo(ana, 'sfu_token') or {}).get('motivo') in ('p2p', 'fora_da_call'), 'ligação de DM nunca recebe token do SFU')
        ana.emit('sair_call', {'canal_id': a_dm}); ev(ana)

# ------------------------------------------------------------------ a página e o cliente -----------------------------------
with completo(CALL_MODE='auto', CALL_P2P_MAX='4'), app.app_context():
    cl = app.test_client()
    with cl.session_transaction() as s:
        s['user_id'] = ids['Ana']
    html = cl.get('/chat').get_data(as_text=True)
    ok('const CALL_POLITICA = ' in html and f'"url":"{URL}"' in html.replace(' ', '') and '"sfu":true' in html.replace(' ', ''), 'o /chat leva a política do SFU (modo, limite, endereço)')
    ok(SEGREDO not in html and CHAVE not in html, 'o /chat NÃO leva a chave nem o segredo do SFU')
    ok('js/call_transporte.js' in html and html.index('js/call_transporte.js') < html.index('const CALL_POLITICA') < html.index('CallTransporte.iniciar('), 'a política é declarada ANTES do iniciar() (o módulo carrega antes, mas só lê no iniciar)')
with com_env(CALL_MODE=None, LIVEKIT_URL=None, LIVEKIT_API_KEY=None, LIVEKIT_API_SECRET=None), app.app_context():
    cl = app.test_client()
    with cl.session_transaction() as s:
        s['user_id'] = ids['Ana']
    html = cl.get('/chat').get_data(as_text=True).replace(' ', '')
    ok('"sfu":false' in html and '"url":""' in html, 'sem configuração, o /chat diz "sfu: false" e não leva endereço')

chat = ler('app/templates/chat.html'); ct = ler('app/static/js/call_transporte.js'); ev_py = ler('app/events.py')
ok('CallTransporte.iniciar({ socket, politica: CALL_POLITICA })' in chat, 'chat.html liga o módulo passando a política (o <script> carrega antes da constante)')
ok('sfu_events.ao_entrar_na_call(chave)' in ev_py and 'sfu_events.ao_sair_da_call(chave)' in ev_py and 'from . import sfu_events' in ev_py, 'events.py chama os ganchos de entrar e sair')
ok('LIVEKIT_API_SECRET' not in ct and 'LIVEKIT_API_KEY' not in ct, 'o JS não conhece as variáveis secretas')
ok(os.path.exists(os.path.join(RAIZ, 'docs', 'PLANO_SFU.md')), 'docs/PLANO_SFU.md existe')

saida = subprocess.run(['node', os.path.join(RAIZ, 'testes', 'call_transporte_logica.js')], capture_output=True, text=True, encoding='utf-8')
falhas_node = [l for l in saida.stdout.splitlines() if l.startswith('FALHA')]
ok(saida.returncode == 0 and not falhas_node, 'o módulo do cliente passa no Node: sem adaptador toda call segue P2P (%d verificações)' % sum(1 for l in saida.stdout.splitlines() if l.startswith(('OK', 'FALHA'))))
for l in falhas_node:
    print('     ', l)

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
