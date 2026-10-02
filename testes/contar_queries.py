import re
"""Conta as queries de cada carga (rota /chat, connect do socket, abrir canal, mensagens) com um banco realista."""
import os, sys, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from sqlalchemy import event
from app import create_app, db, socketio
from app.models import Role, Person, Server, Channel, Message, Friendship, DirectMessage

app = create_app()
contador = collections.Counter()
ativo = {'on': False, 'rotulo': None, 'sql': []}


from sqlalchemy.engine import Engine


@event.listens_for(Engine, 'before_cursor_execute')
def _conta(conn, cursor, statement, params, context, executemany):
    if ativo['on']:
        contador[ativo['rotulo']] += 1
        ativo['sql'].append(statement.strip().split('\n')[0][:110])


def medir(rotulo, fn):
    contador[rotulo] = 0
    ativo.update(on=True, rotulo=rotulo, sql=[])
    fn()
    ativo['on'] = False
    print(f"{rotulo:38s} {contador[rotulo]:4d} queries")
    return list(ativo['sql'])


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    eu = Person(name='Eu', email='eu@x', role_id=r.id, username='eu'); db.session.add(eu)
    outros = [Person(name=f'P{i}', email=f'p{i}@x', role_id=r.id, username=f'p{i}') for i in range(40)]
    db.session.add_all(outros); db.session.commit()
    for k in range(5):
        srv = Server(name=f'S{k}', owner_id=eu.id); srv.members.append(eu)
        for p in outros[k * 5:(k * 5) + 20]:
            srv.members.append(p)
        db.session.add(srv); db.session.flush()
        for n in range(5):
            ch = Channel(name=f'c{n}', channel_type='text' if n < 3 else 'voice', server_id=srv.id)
            db.session.add(ch); db.session.flush()
            if n == 0:
                for m in range(80):
                    db.session.add(Message(text=f'msg {m}', person_id=outros[m % 20].id, channel_id=ch.id))
    for p in outros[:10]:
        db.session.add(Friendship(requester_id=eu.id, addressee_id=p.id, status='accepted'))
    db.session.commit()
    eu_id = eu.id
    canal_id = Channel.query.filter_by(name='c0').first().id

    fc = app.test_client()
    with fc.session_transaction() as s:
        s['user_id'] = eu_id
    db.session.remove()

    sql_chat = medir('GET /chat', lambda: fc.get('/chat'))
    db.session.remove()
    sql_msgs = medir(f'GET /api/mensagens/{canal_id}', lambda: fc.get(f'/api/mensagens/{canal_id}'))
    db.session.remove()
    cli = None
    def conectar():
        global cli
        cli = socketio.test_client(app, flask_test_client=fc)
    sql_conn = medir('socket connect (1a do dia)', conectar)
    db.session.remove()
    cli.disconnect(); db.session.remove()
    sql_conn2 = medir('socket connect (reconexao)', conectar)
    db.session.remove()
    medir('entrar_canal', lambda: cli.emit('entrar_canal', {'canal_id': canal_id}))
    db.session.remove()
    sql_env = medir('enviar_mensagem', lambda: cli.emit('enviar_mensagem', {'canal_id': canal_id, 'texto': 'oi'}))
    db.session.remove()
    medir('listar_membros_servidor', lambda: cli.emit('listar_membros_servidor', {'server_id': Server.query.first().id}))

    print('\n--- /chat: top repetidas ---')
    for sql, n in collections.Counter(sql_chat).most_common(6): print(n, sql)
    print('\n--- connect: top repetidas ---')
    for sql, n in collections.Counter(sql_conn).most_common(8): print(n, sql)

print()
print('--- enviar_mensagem ---')
for q in sql_env: print(' ', re.sub(r'SELECT .* FROM', 'SELECT .. FROM', q)[:100])
