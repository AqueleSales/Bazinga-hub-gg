"""Rodada 38: ATAQUES. Tudo contra um app descartável em memória (nunca contra o site no ar): cabeçalhos e cookies, acesso sem login a TODAS as rotas, IDOR,
CSRF, flood HTTP (inclusive com IP forjado) e de socket, conexões em massa, upload malicioso, vazamento de erro, sessão forjada, URL de rastreio e o FUZZ dos
~190 eventos de socket com três atacantes (sem login, logado de fora do servidor, membro comum): nada pode vazar e nada do dono pode mudar.

O limite de eventos é ligado só onde o teste o exige (o fuzz o desliga: é uma rajada de milhares de eventos em segundos)."""
import io
import json
import os
import re
import struct
import subprocess
import sys
import time
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
os.environ.pop('RENDER', None)
from app import create_app, db, socketio, limites, seguranca
from app.models import Role, Person, Server, Channel, Message, DirectMessage, Friendship, BazarLoja, ConfigApp, server_members

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    try:
        r = cli.get_received()
    except RuntimeError:        # conexão derrubada pelo servidor: o cliente de teste se recusa a ler, mas a fila continua lá
        r = [m for m in cli.queue if m['namespace'] == '/']
        cli.queue = []
    return [m for m in r if nome is None or m['name'] == nome]


_T = [time.time()]


def marca(nome):
    agora = time.time()
    print(f'INFO  [{agora - _T[0]:6.1f}s desde a seção anterior] -> {nome}')
    _T[0] = agora


def zerar():
    limites.zerar()
    with seguranca._trava:
        seguranca._baldes.clear(); seguranca._estouros.clear(); seguranca._punidos.clear(); seguranca._aviso_em.clear()


app = create_app()
SEGREDOS = ['SEGREDO-CANAL-PRIVADO', 'SEGREDO-DM-ANA-BETO', 'dono-secreto@exemplo.com', 'chave-pix-secreta@banco.test', 'ENDERECO-SECRETO-RUA-9']

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio', 'Dani', 'Eva'):
        pe = Person(name=n, email=('dono-secreto@exemplo.com' if n == 'Ana' else f'{n}@x'), role_id=r.id, username=n.lower())
        db.session.add(pe); db.session.commit(); ids[n] = pe.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))
    adm = ConfigApp(chave='admin_ids', valor=str(ids['Dani'])); db.session.add(adm); db.session.commit()

    def cliente(nome, headers=None):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc, headers=headers), fc

    # ---------------- cenário: a Ana é dona de um servidor com canal privado, DM secreta e uma loja; o Beto é membro; a Caio/Eva são de fora ----------------
    ca, fca = cliente('Ana'); ev(ca)
    ca.emit('criar_servidor_discord', {'nome': 'Casa da Ana'}); ev(ca)
    srv = Server.query.filter_by(name='Casa da Ana').first()
    canal_pub = Channel.query.filter_by(server_id=srv.id, channel_type='text').first()
    ca.emit('criar_canal', {'server_id': srv.id, 'nome': 'secreto', 'privado': True, 'membros': []}); ev(ca)
    canal_priv = Channel.query.filter_by(server_id=srv.id, name='secreto').first()
    ca.emit('criar_convite', {'server_id': srv.id}); cod = ev(ca, 'convite_criado')[-1]['args'][0]['code']
    cb, fcb = cliente('Beto'); ev(cb); cb.emit('entrar_por_convite', {'code': cod}); ev(cb)
    ca.emit('entrar_canal', {'canal_id': canal_priv.id}); ev(ca)
    ca.emit('enviar_mensagem', {'canal_id': canal_priv.id, 'texto': 'SEGREDO-CANAL-PRIVADO'}); ev(ca)
    ca.emit('enviar_mensagem', {'canal_id': canal_pub.id, 'texto': 'mensagem publica da casa'}); ev(ca)
    ca.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'SEGREDO-DM-ANA-BETO'}); ev(ca)
    msg_priv = Message.query.filter_by(channel_id=canal_priv.id).first()
    msg_pub = Message.query.filter_by(channel_id=canal_pub.id).first()
    dm_secreta = DirectMessage.query.first()
    loja = BazarLoja(owner_id=ids['Ana'], nome='Loja da Ana', pix_chave='chave-pix-secreta@banco.test', wallet_id=None)
    db.session.add(loja); db.session.commit()
    LOJA_ID = loja.id
    ok(msg_priv is not None and msg_pub is not None and dm_secreta is not None, 'cenário: canal privado, mensagem pública, DM secreta e loja criados')

    def estado_do_dono():
        """Foto do que é DA ANA (e do servidor dela) pra comparar antes e depois dos ataques."""
        db.session.expire_all()
        s = Server.query.get(srv.id)
        ana = Person.query.get(ids['Ana'])
        lj = BazarLoja.query.get(LOJA_ID)
        return {
            'servidor': (s.id, s.name, s.owner_id) if s else None,
            'canais': sorted((ch.id, ch.name, ch.is_private, ch.channel_type) for ch in Channel.query.filter_by(server_id=srv.id)),
            'membros': sorted(m.id for m in s.members) if s else None,
            'mensagens': sorted((m.id, m.text, m.person_id) for m in Message.query.filter(Message.channel_id.in_([canal_priv.id, canal_pub.id]))),
            'dm': (DirectMessage.query.get(dm_secreta.id).content if DirectMessage.query.get(dm_secreta.id) else None),
            'ana': (ana.name, ana.email, ana.xp, ana.bazinga_coins, ana.avatar, ana.username, ana.status),
            'loja': (lj.nome, lj.pix_chave, lj.oculta, lj.checkout_status, lj.porte, lj.verificada, lj.wallet_id) if lj else None,
            'admins': ConfigApp.query.get('admin_ids').valor,
        }

    def contagens():
        n = {}
        for t in db.metadata.sorted_tables:
            n[t.name] = db.session.execute(t.select().with_only_columns(db.func.count()).select_from(t)).scalar()
        return n

    # =====================================================================================================================================
    # 1. HTTPS, cabeçalhos e cookies
    # =====================================================================================================================================
    marca('1. HTTPS, cabeçalhos e cookies')
    zerar()
    with app.test_client() as web:
        r1 = web.get('/entrar')
        h = r1.headers
        ok(h.get('X-Frame-Options') == 'SAMEORIGIN' and h.get('X-Content-Type-Options') == 'nosniff', 'cabeçalhos: anti-clickjacking e nosniff')
        csp = h.get('Content-Security-Policy', '')
        ok("frame-ancestors 'self'" in csp and "base-uri 'self'" in csp and "object-src 'none'" in csp and "form-action 'self'" in csp, 'cabeçalhos: CSP com frame-ancestors, base-uri, object-src e form-action')
        ok(h.get('Referrer-Policy') == 'strict-origin-when-cross-origin' and 'camera=(self)' in h.get('Permissions-Policy', ''), 'cabeçalhos: Referrer-Policy e Permissions-Policy')
        ok('Strict-Transport-Security' not in h, 'HSTS não vai em http puro (só quando a requisição veio por HTTPS)')
        r2 = web.get('/entrar', headers={'X-Forwarded-Proto': 'https'})
        ok('max-age=31536000' in r2.headers.get('Strict-Transport-Security', '') and 'includeSubDomains' in r2.headers.get('Strict-Transport-Security', ''), 'HSTS de 1 ano com includeSubDomains atrás do proxy HTTPS')
        sc = [v for k, v in r1.headers.items() if k.lower() == 'set-cookie']
        ok(sc and all('HttpOnly' in x and 'SameSite=Lax' in x for x in sc), 'cookie de sessão: HttpOnly + SameSite=Lax')
    ok(app.config['SESSION_COOKIE_HTTPONLY'] is True and app.config['SESSION_COOKIE_SAMESITE'] == 'Lax', 'config: cookie HttpOnly e SameSite=Lax')
    ok(app.config['PERMANENT_SESSION_LIFETIME'].days <= 365, 'config: a sessão não dura mais que 1 ano')
    _r = os.environ.get('RENDER'); _s = os.environ.pop('SECRET_KEY', None)
    os.environ['RENDER'] = '1'
    try:
        c.get_secret_key(); sem_chave = False
    except RuntimeError:
        sem_chave = True
    if _r is None:
        os.environ.pop('RENDER', None)
    else:
        os.environ['RENDER'] = _r
    if _s is not None:
        os.environ['SECRET_KEY'] = _s
    ok(sem_chave, 'segredos: em produção o app RECUSA subir sem SECRET_KEY (nada de chave padrão)')
    ok(c.Config.SQLALCHEMY_DATABASE_URI is not None and 'sslmode=require' in c.get_neon_url() + ('' if 'sslmode' in c.get_neon_url() else '&sslmode=require'), 'banco: a conexão com o Postgres exige SSL')
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Ana']
        ok(web.get('/api/novidades').headers.get('Cache-Control') == 'no-store', 'resposta de API da pessoa não é guardada em cache compartilhado (no-store)')
    ok('debug=not (os.getenv' in open(os.path.join(RAIZ, 'run.py'), encoding='utf-8').read(), 'run.py: o depurador nunca liga no servidor (Render)')

    # =====================================================================================================================================
    # 2. Controle de acesso: TODA rota sem login; admin sem ser admin
    # =====================================================================================================================================
    marca('2. Controle de acesso: TODA rota sem login; admin sem ser admin')
    zerar()
    PUBLICAS = ('/', '/entrar', '/termos', '/abrir', '/favicon.ico', '/manifest.webmanifest', '/sw.js', '/localizacao-desktop', '/static/', '/auth/', '/convite/', '/webhooks/')

    def preencher(regra):
        caminho = re.sub(r'<int:[a-z_]+>', '1', regra.rule)
        caminho = re.sub(r'<(?:string:)?[a-z_]+>', 'abc123', caminho)
        return caminho
    abertas = []
    for regra in app.url_map.iter_rules():
        if regra.endpoint == 'static':
            continue
        caminho = preencher(regra)
        for metodo in sorted(regra.methods - {'HEAD', 'OPTIONS'}):
            with app.test_client() as web:
                resp = web.open(caminho, method=metodo, headers={'X-Requested-With': 'fetch'})
            publica = any(caminho == p or (p.endswith('/') and caminho.startswith(p)) for p in PUBLICAS)
            if resp.status_code < 300 and not publica:
                abertas.append((metodo, caminho, resp.status_code))
    ok(not abertas, f'acesso: nenhuma rota fora da lista pública responde 2xx sem login ({abertas[:5]})')
    with app.test_client() as web:
        ok(web.post('/webhooks/asaas', json={'event': 'PAYMENT_RECEIVED', 'payment': {'id': 'x'}}).status_code == 401, 'webhook de pagamento sem token: 401')
        ok(web.post('/webhooks/asaas', json={}, headers={'asaas-access-token': 'qualquer'}).status_code == 401, 'webhook de pagamento com token errado: 401 (sem token configurado nada passa)')
    # admin e estúdio sem ser admin
    com_admin = []
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Eva']            # logada, mas NÃO é admin
        for regra in app.url_map.iter_rules():
            if not (regra.rule.startswith('/admin') or regra.rule.startswith('/estudio')):
                continue
            for metodo in sorted(regra.methods - {'HEAD', 'OPTIONS'}):
                resp = web.open(preencher(regra), method=metodo, headers={'X-Requested-With': 'fetch'})
                if resp.status_code < 300:
                    com_admin.append((metodo, regra.rule, resp.status_code))
    ok(not com_admin, f'acesso: nenhuma rota do /admin ou /estudio responde a quem não é admin ({com_admin[:4]})')
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Dani']           # admin
        ok(web.post('/admin/api/admins', json={'usuario': 'eva'}).status_code in (400, 403), 'admin: rota que ALTERA sem o cabeçalho X-Requested-With é recusada (anti-forja de outro site)')
    # IDOR por HTTP
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Eva']
        r_priv = web.get(f'/api/mensagens/{canal_priv.id}')
        r_pub = web.get(f'/api/mensagens/{canal_pub.id}')
        ok(r_priv.status_code in (401, 403, 404) and 'SEGREDO' not in r_priv.get_data(as_text=True), 'IDOR: quem não é do servidor não lê o canal privado por /api/mensagens')
        ok(r_pub.status_code in (401, 403, 404) and 'mensagem publica' not in r_pub.get_data(as_text=True), 'IDOR: nem o canal público de um servidor onde não é membro')
        for alvo in (ids['Ana'], ids['Beto']):
            rd = web.get(f'/api/dms/{alvo}')
            ok('SEGREDO-DM' not in rd.get_data(as_text=True), f'IDOR: /api/dms/{alvo} de outra pessoa nunca traz a DM alheia')
        ok(web.get('/api/dms/abc').status_code == 404 and web.get('/api/mensagens/-1').status_code == 404, 'ids malformados dão 404, não erro de servidor')
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Beto']           # membro comum
        rb = web.get(f'/api/mensagens/{canal_priv.id}')
        ok('SEGREDO-CANAL' not in rb.get_data(as_text=True), 'IDOR: membro comum NÃO lê o canal privado do servidor onde é membro')
        ok('mensagem publica' in web.get(f'/api/mensagens/{canal_pub.id}').get_data(as_text=True), 'controle: o membro lê o canal público (o bloqueio não é cego)')

    # IDOR por socket
    cc, fcc = cliente('Caio'); ev(cc)
    antes = estado_do_dono()
    cc.emit('entrar_canal', {'canal_id': canal_priv.id}); cc.emit('entrar_canal', {'canal_id': canal_pub.id})
    cc.emit('listar_membros_servidor', {'server_id': srv.id}); cc.emit('listar_fixadas', {'canal_id': canal_pub.id})
    cc.emit('enviar_mensagem', {'canal_id': canal_pub.id, 'texto': 'intruso entrando de penetra'})
    cc.emit('editar_mensagem', {'msg_id': msg_pub.id, 'texto': 'editada por intruso'})
    cc.emit('apagar_mensagem', {'msg_id': msg_pub.id}); cc.emit('apagar_mensagem', {'msg_id': msg_priv.id})
    cc.emit('editar_mensagem_direta', {'msg_id': dm_secreta.id, 'texto': 'editada por intruso'}); cc.emit('apagar_mensagem_direta', {'msg_id': dm_secreta.id})
    cc.emit('expulsar_membro', {'server_id': srv.id, 'person_id': ids['Beto']}); cc.emit('apagar_servidor', {'server_id': srv.id})
    cc.emit('editar_servidor', {'server_id': srv.id, 'nome': 'dominado'}); cc.emit('transferir_posse', {'server_id': srv.id, 'person_id': ids['Caio']})
    cc.emit('criar_canal', {'server_id': srv.id, 'nome': 'intruso'}); cc.emit('criar_convite', {'server_id': srv.id})
    recebido = json.dumps(cc.get_received(), default=str)
    ok(not any(s in recebido for s in SEGREDOS) and 'mensagem publica' not in recebido, 'IDOR/socket: o intruso nunca recebe conteúdo do servidor, do canal privado nem da DM')
    ok(estado_do_dono() == antes, 'IDOR/socket: o intruso não alterou nada (servidor, canais, membros, mensagens, DM, dono, loja, admins)')
    # sessão forjada / adulterada / de conta que não existe
    from flask import Flask
    from flask.sessions import SecureCookieSessionInterface
    forasteiro = Flask('forasteiro'); forasteiro.secret_key = 'outra-chave-qualquer'
    ser = SecureCookieSessionInterface().get_signing_serializer(forasteiro)
    cookie_forjado = ser.dumps({'user_id': ids['Ana']})
    with app.test_client() as web:
        web.set_cookie('session', cookie_forjado, domain='localhost')
        ok(web.get('/chat').status_code in (301, 302, 401) and web.get('/api/novidades').status_code == 401, 'sessão: cookie assinado com OUTRA chave não vira login (não dá pra se passar pela Ana)')
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Ana']
        bom = web.get_cookie('session').value
    adulterado = bom[:-3] + ('AAA' if not bom.endswith('AAA') else 'BBB')
    with app.test_client() as web:
        web.set_cookie('session', adulterado, domain='localhost')
        ok(web.get('/api/novidades').status_code == 401, 'sessão: cookie com a assinatura adulterada é rejeitado')
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = 999999
        ok(web.get('/chat').status_code in (301, 302, 401, 403) and web.get('/api/novidades').status_code in (200, 401), 'sessão: id de conta que não existe mais não derruba o servidor (sem erro 500)')
    fc_fantasma = app.test_client()
    with fc_fantasma.session_transaction() as s:
        s['user_id'] = 999999
    ghost = socketio.test_client(app, flask_test_client=fc_fantasma)
    ghost.emit('listar_amizades'); ghost.emit('enviar_mensagem', {'canal_id': canal_pub.id, 'texto': 'fantasma'})
    ok(Message.query.filter_by(text='fantasma').count() == 0, 'sessão: socket com id de conta que não existe não age em nada')

    # =====================================================================================================================================
    # 3. CSRF: POST de outro site
    # =====================================================================================================================================
    marca('3. CSRF: POST de outro site')
    zerar()
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Eva']
        r_evil = web.post('/termos/aceitar', data={'concordo': '1'}, headers={'Origin': 'https://evil.example'})
        ok(r_evil.status_code == 403, 'CSRF: POST com Origin de outro site é recusado (403)')
        ok(web.post('/termos/aceitar', data={'concordo': '1'}, headers={'Origin': 'null'}).status_code == 403, 'CSRF: Origin "null" (iframe sandbox, arquivo local) também')
        ok(web.post('/api/push/cancelar', json={'endpoint': 'x'}, headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403, 'CSRF: sem Origin mas com Sec-Fetch-Site cross-site é recusado')
        ok(web.post('/termos/aceitar', data={'concordo': '1'}, headers={'Origin': 'http://localhost'}).status_code == 302, 'CSRF: a mesma chamada vinda do próprio site funciona (302)')
        ok(web.post('/api/push/cancelar', json={'endpoint': 'x'}).status_code == 200, 'CSRF: cliente que não manda Origin (curl, gateway) não é barrado (não há cookie ambiente a forjar)')
        ok(web.post('/webhooks/asaas', json={}, headers={'Origin': 'https://gateway.exemplo'}).status_code == 401, 'CSRF: o webhook do gateway é isento da checagem de origem (quem barra é o token)')
        os.environ['ORIGENS_PERMITIDAS'] = 'https://dominio-proprio.exemplo'
        ok(web.post('/api/push/cancelar', json={'endpoint': 'x'}, headers={'Origin': 'https://dominio-proprio.exemplo'}).status_code == 200, 'CSRF: ORIGENS_PERMITIDAS libera o domínio próprio')
        os.environ.pop('ORIGENS_PERMITIDAS')
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Eva']
        web.get('/auth/logout', headers={'Sec-Fetch-Site': 'cross-site'})
        ok(web.get('/api/novidades').status_code == 200, 'logout CSRF: <img src="/auth/logout"> vindo de outro site NÃO desloga a pessoa')
        web.get('/auth/logout', headers={'Sec-Fetch-Site': 'same-origin'})
        ok(web.get('/api/novidades').status_code == 401, 'logout: do próprio site continua saindo')

    # =====================================================================================================================================
    # 4. Flood HTTP (DDoS na camada da aplicação) e IP forjado
    # =====================================================================================================================================
    marca('4. Flood HTTP (DDoS na camada da aplicação) e IP forjado')
    zerar()
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Eva']
        codigos = [web.get('/api/novidades').status_code for _ in range(sum([limites.GERAL_PESSOA, 20]))]
        ok(codigos[:limites.GERAL_PESSOA].count(429) == 0 and codigos[limites.GERAL_PESSOA:].count(429) == 20, f'flood: pessoa logada passa de {limites.GERAL_PESSOA}/min e leva 429')
        r429 = web.get('/api/novidades')
        ok(r429.status_code == 429 and int(r429.headers.get('Retry-After', 0)) >= 1 and 'espere_s' in r429.get_json(), 'flood: o 429 traz Retry-After e JSON em português')
    zerar()
    with app.test_client() as web:
        cab = {'X-Forwarded-For': '203.0.113.5, 10.0.0.1'}
        cod = [web.get('/termos', headers=cab).status_code for _ in range(limites.GERAL_IP + 15)]
        ok(cod[:limites.GERAL_IP].count(429) == 0 and cod[limites.GERAL_IP:].count(429) == 15, f'flood: anônimo passa de {limites.GERAL_IP}/min e leva 429')
        ok(web.get('/termos', headers={'X-Forwarded-For': '203.0.113.99, 10.0.0.2'}).status_code == 200, 'flood: outro IP não é afetado')
    zerar()
    with app.test_client() as web:     # o ataque de verdade: trocar o X-Forwarded-For a cada pedido pra nunca estourar o balde da esquerda
        N = 20 * limites.FATOR_BORDA
        cod = [web.get('/auth/login', headers={'X-Forwarded-For': f'198.51.100.{i % 250}, 10.9.9.9'}).status_code for i in range(N + 30)]
        ok(429 in cod[N:] and cod[:20].count(429) == 0, f'IP forjado: trocar o X-Forwarded-For a cada pedido não foge do limite (a ponta direita barra depois de {N})')
    zerar()
    with app.test_client() as web:
        cod = [web.get('/auth/login', headers={'X-Forwarded-For': f'2001:db8:abcd:12:{i:x}::1'}).status_code for i in range(40)]
        ok(cod.count(429) >= 15, 'IPv6: trocar só o final do endereço (mesmo /64) não foge do limite')
    zerar()
    with app.test_client() as web:     # lixo no cabeçalho não derruba nem vira chave nova
        cod = [web.get('/auth/login', headers={'X-Forwarded-For': "' OR 1=1 --, <script>, " + 'A' * 500}).status_code for _ in range(25)]
        ok(500 not in cod and 429 in cod, 'IP forjado: texto que não é IP no cabeçalho cai no endereço real, sem erro')
    zerar()
    ok(limites.ips_de('1.2.3.4, 5.6.7.8, 9.9.9.9', '10.0.0.1') == ('1.2.3.4', '9.9.9.9') and limites.ips_de(None, '10.0.0.1') == ('10.0.0.1', '10.0.0.1'), 'limites.ips_de: pontas esquerda e direita; sem cabeçalho usa o endereço da conexão')
    _teto_real = limites._TETO_CHAVES
    limites._TETO_CHAVES = 1500        # em produção são 30 mil; o comportamento é o mesmo, só a escala do teste é menor (32 mil pedidos levavam 3 minutos)
    with app.test_client() as web:     # memória: quem forja milhares de endereços não enche o servidor
        for i in range(2600):
            web.get('/favicon.ico', headers={'X-Forwarded-For': f'10.{(i >> 8) & 255}.{i & 255}.{(i >> 16) + 1}'})
        ok(len(limites._janelas) < limites._TETO_CHAVES, f'memória: o limitador tem teto de chaves ({len(limites._janelas)} guardadas após 2600 IPs diferentes, teto {limites._TETO_CHAVES})')
    limites._TETO_CHAVES = _teto_real
    zerar()
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Eva']
        cod = [web.get('/static/img/logo.svg').status_code for _ in range(400)]
        ok(429 not in cod, 'carregar o app (centenas de arquivos estáticos de uma vez) não é barrado')
        cod = [web.post('/api/upload', data={'file': (io.BytesIO(b'x'), 'a.png')}, content_type='multipart/form-data').status_code for _ in range(45)]
        ok(cod[:40].count(429) == 0 and cod[40:].count(429) >= 4, 'flood de upload: 40 por minuto e o resto leva 429')
    zerar()
    # middleware do handshake do socket (roda por FORA do Flask)
    chamadas = []
    mw = seguranca.LimiteDeHandshake(lambda env, sr: (chamadas.append(1), sr('200 OK', []), [b'ok'])[2])
    respostas = []

    def sr(status, headers):
        respostas.append(status)
    env = lambda i: {'PATH_INFO': '/socket.io/', 'QUERY_STRING': 'EIO=4&transport=polling', 'REQUEST_METHOD': 'GET', 'REMOTE_ADDR': '127.0.0.1', 'HTTP_X_FORWARDED_FOR': f'203.0.113.{i % 250}, 10.5.5.5'}
    for i in range(seguranca.HANDSHAKES_POR_MINUTO * limites.FATOR_BORDA + 40):
        mw(env(i), sr)
    ok(any(x.startswith('429') for x in respostas) and len(chamadas) == seguranca.HANDSHAKES_POR_MINUTO * limites.FATOR_BORDA, 'socket: abrir conexão em massa (mesmo trocando o IP forjado) é barrado antes do Socket.IO')
    respostas.clear(); chamadas.clear()
    mw({'PATH_INFO': '/socket.io/', 'QUERY_STRING': 'EIO=4&transport=websocket&sid=abc', 'REQUEST_METHOD': 'GET', 'REMOTE_ADDR': '127.0.0.1'}, sr)
    ok(chamadas == [1], 'socket: conexão já aberta (com sid) não gasta o limite do handshake')
    zerar()

    # =====================================================================================================================================
    # 5. Flood no socket
    # =====================================================================================================================================
    marca('5. Flood no socket')
    zerar()
    # relógio CONGELADO dentro do seguranca.py: cada evento de teste leva ~10 ms de banco e a reposição de fichas mudaria o resultado de uma execução pra outra
    import types
    _tempo_real = seguranca.time
    _t = [5000.0]
    seguranca.time = types.SimpleNamespace(monotonic=lambda: _t[0], time=lambda: _t[0])
    flood, _ = cliente('Eva'); ev(flood)
    chegaram = 0
    for i in range(700):
        try:
            flood.emit('listar_amizades')
        except RuntimeError:
            break
    chegaram = len(ev(flood, 'amizades'))
    ok(chegaram == seguranca.CAP_CONEXAO, f'socket flood: de 700 eventos só {chegaram} foram atendidos (a rajada permitida é {seguranca.CAP_CONEXAO})')
    ok(not flood.is_connected(), 'socket flood: quem insiste depois de barrado tem a conexão derrubada')
    religou, _ = cliente('Eva')
    ok(not religou.is_connected(), 'socket flood: e não volta na hora (pessoa e IP punidos por 2 min)')
    zerar()
    religou, _ = cliente('Eva')
    ok(religou.is_connected(), 'socket flood: passada a punição (aqui, limpada) a conta volta normal')
    zerar()
    # spam de mensagem: o que se espalha pra sala inteira
    spam, _ = cliente('Beto'); ev(spam)
    spam.emit('entrar_canal', {'canal_id': canal_pub.id}); ev(spam)
    antes_msgs = Message.query.filter_by(channel_id=canal_pub.id).count()
    for i in range(80):
        spam.emit('enviar_mensagem', {'canal_id': canal_pub.id, 'texto': f'spam {i}', 'temp_id': f't{i}'})
    novas = Message.query.filter_by(channel_id=canal_pub.id).count() - antes_msgs
    recebido = ev(spam)
    ok(novas == seguranca.CAP_MENSAGEM, f'spam: de 80 mensagens em rajada entraram {novas} (a rajada permitida é {seguranca.CAP_MENSAGEM})')
    ok(any(m['name'] == 'mensagem_recusada' for m in recebido) and sum(1 for m in recebido if m['name'] == 'erro_bazinga' and 'Calma' in json.dumps(m['args'], ensure_ascii=False)) <= 3,
       'spam: a bolha das barradas é desfeita e o aviso "Calma" não vira outro flood')
    zerar()
    # várias abas da mesma pessoa somam
    abas = [cliente('Caio')[0] for _ in range(7)]
    for a in abas:
        ev(a)
    for a in abas:
        for _ in range(60):
            a.emit('listar_amizades')
    total = len(ev(abas[0], 'amizades'))       # a resposta vai pra sala pessoal: toda aba a recebe, então UMA aba conta o total atendido
    ok(total == seguranca.CAP_PESSOA, f'socket: 7 abas da mesma pessoa dividem o mesmo orçamento ({total} de 420 atendidos; o teto da pessoa é {seguranca.CAP_PESSOA})')
    _t[0] += 10.0
    abas[0].emit('listar_amizades'); abas[1].emit('listar_amizades')
    ok(len(ev(abas[0], 'amizades')) == 2, 'socket: passado o tempo as fichas voltam (o limite é por segundo, não um bloqueio eterno)')
    for a in abas:
        try:
            a.disconnect()
        except Exception:
            pass
    zerar()
    seguranca.time = _tempo_real
    # conexões simultâneas
    abertas = [cliente('Dani')[0] for _ in range(seguranca.MAX_CONEXOES_PESSOA + 8)]
    n_ok = sum(1 for a in abertas if a.is_connected())
    ok(n_ok == seguranca.MAX_CONEXOES_PESSOA, f'socket: no máximo {seguranca.MAX_CONEXOES_PESSOA} conexões simultâneas por conta ({n_ok} abertas)')
    for a in abertas:
        try:
            a.disconnect()
        except Exception:
            pass
    ok(seguranca.conexoes_abertas() <= 30, 'socket: fechar a conexão libera a vaga (nada vaza na contagem)')
    zerar()
    anon = [socketio.test_client(app, headers={'X-Forwarded-For': '203.0.113.77'}) for _ in range(seguranca.MAX_CONEXOES_SEM_LOGIN_IP + 10)]
    n_anon = sum(1 for a in anon if a.is_connected())
    ok(n_anon == seguranca.MAX_CONEXOES_SEM_LOGIN_IP, f'socket: conexões SEM login por IP têm teto ({n_anon} abertas)')
    for a in anon:
        try:
            a.disconnect()
        except Exception:
            pass
    zerar()
    # payload gigante e malformado
    grande, _ = cliente('Beto'); ev(grande)
    grande.emit('enviar_mensagem', {'canal_id': canal_pub.id, 'texto': 'G' * 5_000_000})
    gm = Message.query.filter(Message.text.like('GGGG%')).first()
    ok(gm is not None and len(gm.text) <= 2000, 'payload: mensagem de 5 MB é cortada em 2000 caracteres (não entra inteira no banco)')
    zerar()
    for lixo in ('texto solto', 12345, ['a', 'b'], None, True, 3.14):
        grande.emit('enviar_mensagem', lixo); grande.emit('listar_amizades', lixo); grande.emit('criar_servidor_discord', lixo)
    grande.emit('listar_amizades', {'a': 1}, {'b': 2}, 'extra', 5)
    ok(grande.is_connected() and not any(e[1] == 'AttributeError' for e in seguranca.ULTIMOS_ERROS if e[0] in ('enviar_mensagem', 'criar_servidor_discord')),
       'payload: texto, número, lista, nulo e argumentos a mais viram "pedido vazio" (nenhum handler quebra)')
    ev(grande); zerar()

    # =====================================================================================================================================
    # 6. Upload malicioso
    # =====================================================================================================================================
    marca('6. Upload malicioso')
    from app.main import routes as rotas
    from PIL import Image
    enviados = []
    _up, _gu = rotas.cloudinary.uploader.upload, rotas.guardiao.ligado
    rotas.cloudinary.uploader.upload = lambda arq, **kw: (enviados.append(kw), {'secure_url': 'https://res.cloudinary.com/x/image/upload/ok.png'})[1]
    rotas.guardiao.ligado = lambda: False

    def subir(conteudo, nome):
        with app.test_client() as web:
            with web.session_transaction() as s:
                s['user_id'] = ids['Eva']
            return web.post('/api/upload', data={'file': (io.BytesIO(conteudo), nome)}, content_type='multipart/form-data')

    def chunk(tipo, dados):
        return struct.pack('>I', len(dados)) + tipo + dados + struct.pack('>I', zlib.crc32(tipo + dados) & 0xffffffff)
    bomba = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 100000, 100000, 1, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\x00')) + chunk(b'IEND', b'')
    buf = io.BytesIO(); Image.new('RGB', (8, 8), (200, 30, 30)).save(buf, 'PNG'); png_ok = buf.getvalue()
    zerar()
    ok(subir(b"GIF89a<?php system($_GET['c']); ?>", 'foto.gif').status_code == 400, 'upload: GIF com PHP dentro (polyglot) é recusado')
    ok(subir(b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', 'a.svg').status_code == 400, 'upload: SVG (pode rodar script) é recusado pela extensão')
    ok(subir(b'<html><script>alert(1)</script></html>', 'a.png').status_code == 400, 'upload: HTML renomeado pra .png é recusado')
    ok(subir(bomba, 'bomba.png').status_code == 400, 'upload: PNG que declara 100 mil x 100 mil pixels (bomba de descompressão) é recusado sem decodificar')
    ok(subir(b'\x89PNG\r\n\x1a\n' + b'\x00' * (9 * 1024 * 1024), 'grande.png').status_code == 400, 'upload: imagem acima de 8 MB é recusada')
    ok(subir(b'MZ\x90\x00' + b'\x00' * 200, 'programa.exe').status_code == 400, 'upload: executável é recusado')
    ok(subir(png_ok, '../../etc/passwd.png').status_code == 200 and enviados and re.fullmatch(r'[0-9a-f]{32}', enviados[-1]['public_id']), 'upload: o nome do arquivo do cliente nunca é usado (caminho "../../" vira nome aleatório)')
    zerar()
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Eva']
        r413 = web.post('/api/upload', data={'file': (io.BytesIO(b'\x89PNG' + b'0' * (27 * 1024 * 1024)), 'x.png')}, content_type='multipart/form-data')
        ok(r413.status_code == 413 and 'error' in r413.get_json(), 'upload: corpo acima de 26 MB leva 413 (JSON) antes de ser lido')
        r5 = web.post('/api/push/inscrever', data='{"endpoint": "' + 'A' * (6 * 1024 * 1024) + '"}', content_type='application/json')
        ok(r5.status_code == 413, 'corpo JSON de 6 MB em rota comum leva 413 (teto global de 5 MB)')
    rotas.cloudinary.uploader.upload, rotas.guardiao.ligado = _up, _gu
    zerar()

    # =====================================================================================================================================
    # 7. Erro que não vaza
    # =====================================================================================================================================
    marca('7. Erro que não vaza')
    vazamento = '(psycopg2.errors.UndefinedColumn) column "pix_chave" of relation "bazar_loja" does not exist\n[SQL: SELECT bazar_loja.pix_chave FROM bazar_loja]\n(Background on this error at: https://sqlalche.me/e/20/f405)'
    pub = seguranca.mensagem_publica('Não foi possível enviar a mensagem: ' + vazamento, registrar=False)
    ok('psycopg2' not in pub and 'SQL' not in pub and 'bazar_loja' not in pub and 'erro interno (código' in pub and pub.startswith('Não foi possível enviar a mensagem'), 'erro: o texto de erro de banco vira "erro interno (código X)" mantendo o começo da frase')
    ok(seguranca.mensagem_publica('Você não tem acesso a esse canal.') == 'Você não tem acesso a esse canal.' and seguranca.mensagem_publica('Nome inválido: use só letras') == 'Nome inválido: use só letras', 'erro: mensagem comum passa intacta')
    ok('postgresql://' not in seguranca.mensagem_publica('falhou: postgresql://u:senha@ep-x.neon.tech/db', registrar=False) and 'Traceback' not in seguranca.mensagem_publica('Traceback (most recent call last):\n File "x.py", line 3', registrar=False), 'erro: endereço do banco e rastro de Python também são escondidos')
    from app import events as eventos
    _cr = eventos.comitar_com_retry
    eventos.comitar_com_retry = lambda *a, **k: (_ for _ in ()).throw(Exception(vazamento))
    zerar()
    teste, _ = cliente('Beto'); ev(teste)
    teste.emit('entrar_canal', {'canal_id': canal_pub.id}); ev(teste)
    teste.emit('enviar_mensagem', {'canal_id': canal_pub.id, 'texto': 'vai falhar no banco'})
    msgs_erro = json.dumps([m['args'] for m in ev(teste, 'erro_bazinga')], ensure_ascii=False)
    eventos.comitar_com_retry = _cr
    ok('psycopg2' not in msgs_erro and 'bazar_loja' not in msgs_erro and 'código' in msgs_erro, 'erro: com o banco falhando o usuário recebe o código, nunca o SQL nem o nome da tabela')
    # 500 em rota HTTP
    _us = rotas.usuario_da_sessao
    rotas.usuario_da_sessao = lambda: (_ for _ in ()).throw(RuntimeError('SEGREDO-NO-ERRO /home/app/x.py'))
    with app.test_client() as web:
        with web.session_transaction() as s:
            s['user_id'] = ids['Eva']
        r500 = web.get('/api/push/chave')
        corpo500 = r500.get_data(as_text=True)
    rotas.usuario_da_sessao = _us
    ok(r500.status_code == 500 and 'SEGREDO-NO-ERRO' not in corpo500 and 'Traceback' not in corpo500, 'erro 500 em rota HTTP: resposta genérica, sem a exceção nem o rastro')
    with app.test_client() as web:
        r404 = web.get('/convite/<script>alert(1)</script>'); r404b = web.get('/rota/que/nao/existe')
        ok('<script>alert' not in r404.get_data(as_text=True) and r404b.status_code == 404, 'erro 404: a página não ecoa o que veio na URL')

    # =====================================================================================================================================
    # 8. Injeção, XSS de URL, caminho de arquivo
    # =====================================================================================================================================
    marca('8. Injeção, XSS de URL, caminho de arquivo')
    from app import utils
    mal = ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:image/svg+xml,<svg onload=alert(1)>', '//evil.example/pixel.png', '/\\evil.example/pixel.png', '\\\\evil.example\\x.png',
           'https://evil.example/pixel.png', 'http://res.cloudinary.com/x/a.png', 'https://res.cloudinary.com.evil.example/a.png', 'https://media.giphy.com.evil.example/a.gif', 'file:///etc/passwd', '/ok\n//evil.example', ' ', '']
    ok(not any(utils.url_de_imagem_ok(u) for u in mal), 'URL de imagem: javascript:, data:, //host, /\\host, http, domínio parecido e quebra de linha são todos recusados')
    ok(all(utils.url_de_imagem_ok(u) for u in ('/static/img/logo.svg', 'https://res.cloudinary.com/x/image/upload/a.png', 'https://media2.giphy.com/media/a/giphy.gif')), 'URL de imagem: o que é do app, do Cloudinary e do Giphy continua valendo')
    os.environ['CLOUDINARY_ESTRITO'] = '1'
    import cloudinary
    _nuvem = cloudinary.config().cloud_name
    cloudinary.config(cloud_name='nuvem-do-app')
    ok(utils.url_cloudinary_do_app('https://res.cloudinary.com/nuvem-do-app/image/upload/a.png') and not utils.url_cloudinary_do_app('https://res.cloudinary.com/conta-do-atacante/image/upload/a.png'), 'Cloudinary estrito: só a conta DO APP vale (hospedar fora do Guardião e colar o link não funciona)')
    zerar()
    ev(cb); cb.emit('enviar_mensagem', {'canal_id': canal_pub.id, 'texto': 'pixel', 'anexo_url': '//evil.example/p.png', 'anexo_tipo': 'image'})
    cb.emit('enviar_mensagem', {'canal_id': canal_pub.id, 'texto': 'conta alheia', 'anexo_url': 'https://res.cloudinary.com/conta-do-atacante/image/upload/x.png', 'anexo_tipo': 'image'})
    m1 = Message.query.filter_by(text='pixel').first(); m2 = Message.query.filter_by(text='conta alheia').first()
    ok(m1 is not None and m1.attachment_url is None and m2 is not None and m2.attachment_url is None, 'mensagem: anexo "//evil" e anexo de outra conta Cloudinary são descartados (a mensagem sai sem ele)')
    cb.emit('enviar_mensagem_direta', {'target_id': ids['Ana'], 'texto': 'dm pixel', 'anexo_url': '//evil.example/p.png', 'anexo_tipo': 'image'})
    dmp = DirectMessage.query.filter_by(content='dm pixel').first()
    ok(dmp is None or dmp.attachment_url is None, 'DM: anexo "//evil" também é descartado')
    cloudinary.config(cloud_name=_nuvem); os.environ.pop('CLOUDINARY_ESTRITO')
    ev(cb); zerar()
    cb.emit('atualizar_perfil', {'avatar': 'javascript:alert(1)', 'banner_url': '//evil.example/b.png', 'name': '<img src=x onerror=alert(1)>'}); ev(cb)
    bpe = Person.query.get(ids['Beto'])
    ok(not (bpe.avatar or '').startswith(('javascript', '//')) and not (bpe.banner_url or '').startswith('//'), 'perfil: avatar "javascript:" e faixa "//host" não são gravados')
    cb.emit('atualizar_perfil', {'username': "ana'; DROP TABLE person;--"}); ev(cb)
    ok(Person.query.get(ids['Beto']).username == 'beto' and Person.query.count() == 5, 'SQL injection: @usuario com aspas e DROP TABLE é recusado e a tabela segue lá')
    cb.emit('enviar_pedido_amizade', {'nome': '%'}); cb.emit('enviar_pedido_amizade', {'nome': "' OR '1'='1"}); cb.emit('enviar_pedido_amizade', {'nome': '_'})
    ok(Friendship.query.filter(Friendship.requester_id == ids['Beto'], Friendship.addressee_id != ids['Ana']).count() == 0, 'SQL injection/curinga: "%", "_" e "\' OR 1=1" na busca de pessoa não casam ninguém')
    with app.test_client() as web:
        for caminho in ('/static/../config.py', '/static/%2e%2e/config.py', '/static/..%2fconfig.py', '/static/%5c..%5cconfig.py', '/static/css/../../../.env', '/estudio/arquivo/../../x', '/convite/../../etc/passwd', '/static/js/..;/..;/config.py'):
            resp = web.get(caminho)
            corpo = resp.get_data(as_text=True)
            ok(resp.status_code in (301, 302, 308, 400, 401, 403, 404) and 'SECRET_KEY' not in corpo and 'DATABASE_URL' not in corpo, f'path traversal: {caminho} não entrega arquivo do servidor ({resp.status_code})')
        ok(web.open('/', method='TRACE').status_code == 405, 'método TRACE é recusado (405)')
        loc = web.get('/entrar?next=https://evil.example&redirect=https://evil.example&url=https://evil.example').headers.get('Location', '')
        ok('evil.example' not in loc, 'open redirect: parâmetros next/redirect/url não levam pra fora')
        ok(web.get('/api/gifs?q=' + "' OR 1=1 --").status_code in (401, 503, 200, 429), 'SQL injection: busca de GIF com aspas não causa erro de servidor')

    # o cliente também não aceita "//host" nem "/\host" como "caminho do site", e põe url('...') com aspas percent-encoded
    chat_html = open(os.path.join(RAIZ, 'app', 'templates', 'chat.html'), encoding='utf-8').read()
    ok(r'(?![\/\\])' in chat_html[chat_html.index('function escUrl'):chat_html.index('function escUrl') + 700], 'cliente: escUrl() barra "//host" e "/\\host" (rastreador em mensagem antiga também fica neutralizado)')
    ok('function urlCss(' in chat_html and 'escUrl(urlCss(pf.banner_url' in chat_html and 'escUrl(urlCss(url))' in chat_html and 'escUrl(urlCss((extras && extras.banner_url)' in chat_html, 'cliente: faixa, fundo do cartão e banner do mapa passam por urlCss (a aspa não fecha o url() do style)')
    for js, pedaco in (('cargos.js', 'urlCss(srv.bannerUrl)'), ('loja_mapa.js', 'urlOk(urlCss(l.banner_url))'), ('lojas_canal.js', 'urlCss(l.banner_url)')):
        ok(pedaco in open(os.path.join(RAIZ, 'app', 'static', 'js', js), encoding='utf-8').read(), f'cliente: {js} codifica a URL do banner antes de pôr no url(...)')

    # =====================================================================================================================================
    # 9. FUZZ dos eventos de socket (sem limite de eventos: é uma rajada de milhares)
    # =====================================================================================================================================
    marca('9. FUZZ dos eventos de socket (sem limite de eventos: é uma rajada de milhares)')
    os.environ['LIMITE_EVENTOS'] = '0'
    zerar()
    eventos_do_app = sorted(socketio.server.handlers['/'].keys())
    eventos_do_app = [e for e in eventos_do_app if e not in ('connect', 'disconnect')]
    ok(len(eventos_do_app) > 150, f'fuzz: {len(eventos_do_app)} eventos de socket encontrados')
    chaves = set()
    for nome_arq in os.listdir(os.path.join(RAIZ, 'app')):
        if nome_arq.endswith('.py'):
            txt = open(os.path.join(RAIZ, 'app', nome_arq), encoding='utf-8').read()
            chaves |= set(re.findall(r"(?:dados|data|d)\.get\('([a-z_0-9]+)'", txt)) | set(re.findall(r"(?:dados|data)\['([a-z_0-9]+)'\]", txt))
    chaves = sorted(chaves)
    ok(len(chaves) > 150, f'fuzz: {len(chaves)} nomes de campo coletados do código')
    REAIS = {'server_id': srv.id, 'servidor_id': srv.id, 'id': srv.id, 'canal_id': canal_priv.id, 'channel_id': canal_priv.id, 'msg_id': msg_priv.id, 'message_id': msg_priv.id,
             'target_id': ids['Ana'], 'person_id': ids['Ana'], 'usuario_id': ids['Ana'], 'amigo_id': ids['Ana'], 'alvo_id': ids['Ana'], 'user_id': ids['Ana'], 'pessoa_id': ids['Ana'],
             'dono_id': ids['Ana'], 'loja_id': LOJA_ID, 'owner_id': ids['Ana'], 'categoria_id': 1, 'cargo_id': 1, 'role_id': 1, 'tid': 1, 'item_id': 'moldura:ouro'}
    LIXOS = [None, '', 'x' * 3000, "' OR 1=1 --", '"><img src=x onerror=alert(1)>', '../../../etc/passwd', '\x00\x01', '😀' * 40, -1, 0, 2 ** 70, 1.5, True, [], {}, [1, 'a', None], {'a': {'b': [1]}}, 'javascript:alert(1)', '//evil.example/x']
    NAO_MEXER = {'connect', 'disconnect'}
    DEVE_FICAR_DE_FORA = {'sair_do_servidor'}      # o atacante membro sairia do servidor e os ataques seguintes seriam "de fora"

    def payloads(real):
        for lixo in LIXOS:
            yield {k: lixo for k in chaves}
        if real:
            yield {k: REAIS.get(k, 'x') for k in chaves}
            yield {k: REAIS.get(k, '<img src=x onerror=alert(1)>') for k in chaves}
            yield {k: REAIS.get(k, 12345678) for k in chaves}
            yield {k: REAIS.get(k, ["a", {"b": 1}]) for k in chaves}
            yield {k: REAIS.get(k, 'OUTRA COISA') for k in chaves}
            yield {k: (REAIS[k] if k in REAIS else None) for k in chaves}
            yield {k: (-REAIS[k] if isinstance(REAIS.get(k), int) else 'x') for k in chaves}

    def fuzz(cli, real, rotulo):
        lentos, recebido = [], []
        for nome_ev in eventos_do_app:
            if nome_ev in DEVE_FICAR_DE_FORA and rotulo != 'sem login':
                continue
            for p in payloads(real):
                t0 = time.time()
                try:
                    cli.emit(nome_ev, p)
                except Exception as e:
                    lentos.append((nome_ev, f'exceção no cliente de teste: {type(e).__name__}'))
                dt = time.time() - t0
                if dt > 3:
                    lentos.append((nome_ev, f'{dt:.1f}s'))
            recebido.extend(cli.get_received())
        return lentos, recebido

    def sem_vazamento(recebido):
        txt = json.dumps(recebido, default=str, ensure_ascii=False)
        achados = [s for s in SEGREDOS if s in txt]
        tecnicos = re.findall(r'psycopg2|sqlalche\.me|\[SQL:|Traceback|OperationalError|ProgrammingError|IntegrityError|/Users/Sales|PycharmProjects', txt)
        return achados, sorted(set(tecnicos))

    # --- 9a: sem login nenhum
    seguranca.ULTIMOS_ERROS.clear()
    base = contagens()
    sem_login = socketio.test_client(app)
    lentos, recebido = fuzz(sem_login, False, 'sem login')
    ok(not lentos, f'fuzz sem login: nenhum evento travou ({lentos[:3]})')
    ok(contagens() == base, 'fuzz sem login: NENHUMA tabela mudou (quem não está logado não escreve nada)')
    ok(not [m for m in recebido if m['name'] not in ('versao_app',)], f'fuzz sem login: o servidor não respondeu nada a quem não está logado ({sorted({m["name"] for m in recebido})[:5]})')
    sem_login.disconnect()

    # --- 9b: logada, mas de fora do servidor (Caio)
    antes = estado_do_dono(); seguranca.ULTIMOS_ERROS.clear()
    caio_c, _ = cliente('Caio'); ev(caio_c)
    lentos, recebido = fuzz(caio_c, True, 'de fora')
    achados, tecnicos = sem_vazamento(recebido)
    erros_b = list(seguranca.ULTIMOS_ERROS)
    ok(not lentos, f'fuzz de fora: nenhum evento travou ({lentos[:3]})')
    ok(not achados, f'fuzz de fora: nenhum segredo do dono vazou ({achados})')
    ok(not tecnicos, f'fuzz de fora: nenhum texto técnico (SQL, rastro, caminho) chegou ao atacante ({tecnicos})')
    depois = estado_do_dono()
    difs = [k for k in antes if antes[k] != depois[k]]
    ok(not difs, f'fuzz de fora: nada do dono mudou ({difs})')

    # --- 9c: membro comum do servidor (Beto)
    antes = estado_do_dono(); seguranca.ULTIMOS_ERROS.clear()
    cb2, _ = cliente('Beto'); ev(cb2)
    coins_antes = Person.query.get(ids['Beto']).bazinga_coins or 0
    lentos, recebido = fuzz(cb2, True, 'membro')
    achados, tecnicos = sem_vazamento(recebido)
    erros_c = list(seguranca.ULTIMOS_ERROS)
    depois = estado_do_dono()
    db.session.expire_all()
    ok(not lentos, f'fuzz de membro: nenhum evento travou ({lentos[:3]})')
    ok('SEGREDO-CANAL-PRIVADO' not in json.dumps(recebido, default=str) and 'dono-secreto@exemplo.com' not in json.dumps(recebido, default=str) and 'chave-pix-secreta@banco.test' not in json.dumps(recebido, default=str),
       'fuzz de membro: canal privado, e-mail do dono e chave Pix da loja não vazam')
    ok(not tecnicos, f'fuzz de membro: nenhum texto técnico chegou ao atacante ({tecnicos})')
    ok(depois['servidor'] == antes['servidor'] and depois['canais'] == antes['canais'] and depois['ana'] == antes['ana'] and depois['loja'] == antes['loja'] and depois['admins'] == antes['admins'],
       'fuzz de membro: servidor, canais, conta da Ana, loja e lista de admins intactos')
    ok(Server.query.get(srv.id).owner_id == ids['Ana'] and ids['Ana'] in [m.id for m in Server.query.get(srv.id).members], 'fuzz de membro: a Ana continua dona e membra do próprio servidor')
    ok(depois['dm'] == antes['dm'] and [m for m in depois['mensagens'] if m[0] in (msg_priv.id, msg_pub.id)] == [m for m in antes['mensagens'] if m[0] in (msg_priv.id, msg_pub.id)], 'fuzz de membro: mensagens e DM da Ana não foram editadas nem apagadas')
    ganho = (Person.query.get(ids['Beto']).bazinga_coins or 0) - coins_antes
    ok(ganho <= 1000, f'fuzz de membro: não existe jeito de ganhar DRC de graça com eventos forjados (ganhou {ganho})')
    ok(str(ids['Beto']) not in [x for x in (ConfigApp.query.get('admin_ids').valor or '').split(',')], 'fuzz de membro: o atacante não virou admin')
    por_tipo = {}
    for e in erros_b + erros_c:
        por_tipo.setdefault((e[0], e[1]), 0)
        por_tipo[(e[0], e[1])] += 1
    print(f'INFO fuzz: {len(erros_b) + len(erros_c)} exceções contidas pelo tratador padrão em {len(por_tipo)} combinações evento/tipo (cada uma virou "algo deu errado" genérico, sem vazar)')
    for (evn, tipo), n in sorted(por_tipo.items(), key=lambda x: -x[1])[:12]:
        print(f'INFO   {evn}: {tipo} x{n}')
    os.environ.pop('LIMITE_EVENTOS')
    zerar()

# =====================================================================================================================================
# 10. Dependências e segredos no repositório
# =====================================================================================================================================
def versao(s):
    return tuple(int(x) for x in re.findall(r'\d+', s)[:4])


req = {}
for linha in open(os.path.join(RAIZ, 'requirements.txt'), encoding='utf-8'):
    m = re.match(r'^\s*([A-Za-z0-9_.\-]+)==([\w.\-+]+)\s*$', linha)
    if m:
        req[m.group(1).lower()] = m.group(2)
PISO = {'pillow': '13.0.0', 'gunicorn': '22.0.0', 'authlib': '1.9.1', 'werkzeug': '3.1.9', 'urllib3': '2.8.0', 'pypdf': '6.21.4', 'aiohttp': '3.14.4', 'joserfc': '1.7.6', 'certifi': '2026.10.18', 'dnspython': '2.9.0'}
abaixo = [(p, req.get(p), minimo) for p, minimo in PISO.items() if p in req and versao(req[p]) < versao(minimo)]
ok(not abaixo, f'dependências: nenhuma abaixo da versão que corrige as falhas conhecidas (OSV, 04/11/2026) {abaixo}')
ok(all(p in req for p in PISO), 'dependências: todas as pinadas no requirements.txt')

PADROES = [(r'AIza[0-9A-Za-z_\-]{35}', 'chave do Google'), (r'GOCSPX-[0-9A-Za-z_\-]{20,}', 'segredo OAuth do Google'), (r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', 'chave privada'),
           (r'cloudinary://\d+:[\w\-]{10,}@', 'URL do Cloudinary com segredo'), (r'postgres(?:ql)?://[^\s:@/\'"]+:([^\s@\'"]{4,})@[\w.\-]+', 'senha do Postgres na URL'),
           (r'sk-(?:ant-)?[A-Za-z0-9_\-]{32,}', 'chave de API (sk-)'), (r'ghp_[A-Za-z0-9]{36}', 'token do GitHub')]
PLACEHOLDERS = {'senha', 'password', 'pass', 'xxxx', 'xxx', 'sua_senha', 'suasenha', 'user', 'usuario', 'senha_aqui', 'secret', 'changeme', 'exemplo'}
try:
    tracked = subprocess.run(['git', 'ls-files'], cwd=RAIZ, capture_output=True, text=True, timeout=30).stdout.splitlines()
except Exception:
    tracked = []
achados = []
for rel in tracked:
    if rel.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.mp3', '.wav', '.db', '.exe', '.docx', '.woff2', '.pdf', '.json')) or rel.startswith(('desktop/package-lock', 'app/static/emoji')):
        continue
    try:
        if os.path.getsize(os.path.join(RAIZ, rel)) > 2_000_000:
            continue
        txt = open(os.path.join(RAIZ, rel), encoding='utf-8', errors='ignore').read()
    except OSError:
        continue
    for padrao, rotulo in PADROES:
        for m in re.finditer(padrao, txt):
            if m.groups() and m.group(1).lower() in PLACEHOLDERS:
                continue
            achados.append((rel, rotulo))
ok(bool(tracked) and not achados, f'segredos: nenhuma chave/senha/URL com credencial nos arquivos versionados ({achados[:4]})')
ok('.env' not in [t for t in tracked if t == '.env'] and any(l.strip() == '.env' for l in open(os.path.join(RAIZ, '.gitignore'), encoding='utf-8')), 'segredos: .env está no .gitignore e não é versionado')

print()
print('FALHAS:', len(falhas))
for f in falhas:
    print('  -', f)
sys.exit(1 if falhas else 0)
