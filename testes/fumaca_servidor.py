"""Regressão: servidores, canais privados, convites, mensagens - depois da mudança de carregamento (lazy) e expire_on_commit."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Server, Channel, Message, Invite

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Membro', 'Intruso'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    dono, fdono = cliente('Dono'); membro, fmembro = cliente('Membro'); intruso, fint = cliente('Intruso')

    dono.emit('criar_servidor_discord', {'nome': 'Meu Servidor'})
    srv_json = [m for m in ev(dono, 'servidor_discord_criado')][-1]['args'][0]
    sid = srv_json['id']
    ok(srv_json['membros'] == 1 and len(srv_json['channels']) == 2, 'Servidor criado com 2 canais e 1 membro')
    canal_pub = [c for c in srv_json['channels'] if c['type'] == 'text'][0]['id']

    # convite
    dono.emit('criar_convite', {'server_id': sid}); conv = [m for m in ev(dono, 'convite_criado')]
    ok(bool(conv), 'Convite criado')
    codigo = conv[-1]['args'][0]['code']
    membro.emit('entrar_por_convite', {'code': codigo})
    ra = ev(membro, 'servidor_discord_criado')
    ok(bool(ra) and ra[-1]['args'][0]['membros'] == 2, 'Membro entrou pelo convite (2 membros)')
    ok(any(m['name'] == 'membro_entrou_servidor' for m in ev(dono)), 'Dono foi avisado da entrada (regra 6)')

    # canal privado só pro dono
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'secreto', 'privado': True, 'membros': []})
    ev(dono); ev(membro)
    priv = Channel.query.filter_by(name='secreto').first()
    ok(priv is not None and priv.is_private, 'Canal privado criado')
    membro.emit('entrar_canal', {'canal_id': priv.id})
    membro.emit('enviar_mensagem', {'canal_id': priv.id, 'texto': 'invadi'})
    rm = ev(membro)
    ok(any(m['name'] == 'erro_bazinga' for m in rm) and Message.query.filter_by(channel_id=priv.id).count() == 0, 'Membro comum NÃO escreve em canal privado')
    ok(fmembro.get(f'/api/mensagens/{priv.id}').status_code == 403, 'API devolve 403 pro membro comum')
    ok(fdono.get(f'/api/mensagens/{priv.id}').status_code == 200, 'API libera pro dono')
    # intruso (nem membro do servidor)
    ok(fint.get(f'/api/mensagens/{canal_pub}').status_code == 403, 'Quem não é do servidor leva 403 até no canal público')
    intruso.emit('enviar_mensagem', {'canal_id': canal_pub, 'texto': 'hacker'})
    ok(Message.query.filter_by(channel_id=canal_pub).count() == 0, 'Intruso NÃO escreve no canal do servidor')

    # mensagem normal + recebimento
    membro.emit('entrar_canal', {'canal_id': canal_pub}); dono.emit('entrar_canal', {'canal_id': canal_pub}); ev(membro); ev(dono)
    membro.emit('enviar_mensagem', {'canal_id': canal_pub, 'texto': 'oi galera', 'temp_id': 'tmp_1'})
    rm, rd = ev(membro, 'receber_mensagem'), ev(dono, 'receber_mensagem')
    ok(len(rd) == 1 and rd[0]['args'][0]['canal_id'] == canal_pub, 'Dono recebe a mensagem do canal (com canal_id)')
    ok(len(rm) >= 1 and rm[0]['args'][0]['temp_id'] == 'tmp_1', 'Autor recebe a confirmação com o temp_id')
    # paginação: as mais recentes
    for i in range(60):
        db.session.add(Message(text=f'm{i}', person_id=ids['Dono'], channel_id=canal_pub))
    db.session.commit()
    dados = fdono.get(f'/api/mensagens/{canal_pub}').get_json()
    ok(len(dados) == 50 and dados[-1]['texto'] == 'm59', 'API traz as 50 MAIS RECENTES (e não as 50 mais antigas)')
    antes = dados[0]['id']
    mais = fdono.get(f'/api/mensagens/{canal_pub}?antes={antes}').get_json()
    ok(len(mais) == 11 and max(m['id'] for m in mais) < antes, 'Paginação ?antes= devolve as anteriores')

    # lista de membros e privacidade de canal privado na lista do servidor do membro
    membro.emit('listar_membros_servidor', {'server_id': sid})
    lm = ev(membro, 'membros_do_servidor')
    ok(bool(lm), 'listar_membros_servidor responde')
    membro.emit('carregar_meus_servidores') if False else None

    # reconexão do membro: servidor chega sem o canal privado
    membro.disconnect()
    membro2 = socketio.test_client(app, flask_test_client=fmembro)
    cm = [m for m in ev(membro2, 'carregar_meus_servidores')][-1]['args'][0]
    nomes = [c['name'] for s in cm for c in s['channels']]
    ok('secreto' not in nomes, 'Canal privado não aparece na lista do membro comum')
    dono.disconnect()
    dono2 = socketio.test_client(app, flask_test_client=fdono)
    cd = [m for m in ev(dono2, 'carregar_meus_servidores')][-1]['args'][0]
    ok('secreto' in [c['name'] for s in cd for c in s['channels']], 'Dono vê o canal privado')

    # /chat renderiza
    resp = fdono.get('/chat')
    ok(resp.status_code == 200 and b'Meu Servidor' in resp.data, '/chat renderiza com o servidor do dono')

    # expulsar
    dono2.emit('expulsar_membro', {'server_id': sid, 'person_id': ids['Membro']})
    ev(dono2)
    srv = Server.query.get(sid)
    ok(len(srv.members) == 1, 'Expulsão remove o membro')

    # apagar servidor
    dono2.emit('apagar_servidor', {'server_id': sid}); ev(dono2)
    ok(Server.query.get(sid) is None, 'Servidor apagado')

print()
print('FALHAS:', falhas if falhas else 'nenhuma')
