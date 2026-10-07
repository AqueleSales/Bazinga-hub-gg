"""Responder mensagem (estilo WhatsApp): citação em canal e DM, só do mesmo canal/conversa, resumo vem do servidor."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Message, DirectMessage, Friendship

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted')); db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    ana, fana = cliente('Ana'); beto, fbeto = cliente('Beto')

    ana.emit('criar_servidor_discord', {'nome': 'Srv'})
    srv = [m for m in ev(ana, 'servidor_discord_criado')][-1]['args'][0]
    textos = [c for c in srv['channels'] if c['type'] == 'text']
    c1 = textos[0]['id']
    ana.emit('criar_canal', {'server_id': srv['id'], 'nome': 'outro', 'privado': False}); ev(ana)
    from app.models import Channel
    c2 = Channel.query.filter_by(name='outro').first().id

    ana.emit('entrar_canal', {'canal_id': c1}); ana.emit('entrar_canal', {'canal_id': c2}); ev(ana)
    ana.emit('enviar_mensagem', {'canal_id': c1, 'texto': 'oi pessoal'}); ev(ana)
    m1 = Message.query.filter_by(channel_id=c1).first().id
    ana.emit('enviar_mensagem', {'canal_id': c2, 'texto': 'msg do outro canal'}); ev(ana)
    m2 = Message.query.filter_by(channel_id=c2).first().id

    ana.emit('enviar_mensagem', {'canal_id': c1, 'texto': 'resposta', 'reply_to': m1, 'temp_id': 'tmp_1'})
    rec = [m for m in ev(ana, 'receber_mensagem')][0]['args'][0]
    ok(rec['reply'] and rec['reply']['id'] == m1 and rec['reply']['texto'] == 'oi pessoal' and rec['reply']['autor'] == 'Ana', 'Resposta leva o resumo montado pelo servidor')

    ana.emit('enviar_mensagem', {'canal_id': c1, 'texto': 'cruzada', 'reply_to': m2}); ev(ana)
    cruz = Message.query.filter_by(text='cruzada').first()
    ok(cruz is not None and cruz.reply_to_id is None, 'Citar mensagem de OUTRO canal é ignorado')

    ana.emit('enviar_mensagem', {'canal_id': c1, 'texto': 'lixo', 'reply_to': 'abc'}); ev(ana)
    ok(Message.query.filter_by(text='lixo').first().reply_to_id is None, 'reply_to inválido não quebra')

    hist = fana.get(f'/api/mensagens/{c1}').get_json()
    com = [h for h in hist if h['texto'] == 'resposta'][0]
    ok(com['reply'] and com['reply']['id'] == m1, 'Histórico do canal devolve a citação')

    # apagar a original: a resposta fica, marcada como apagada
    db.session.delete(Message.query.get(m1)); db.session.commit()
    hist = fana.get(f'/api/mensagens/{c1}').get_json()
    com = [h for h in hist if h['texto'] == 'resposta'][0]
    ok(com['reply'] is None and com['reply_apagada'] is True, 'Original apagada: resposta sobrevive com "apagada"')

    # DM
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'oi beto'}); ev(ana); ev(beto)
    d1 = DirectMessage.query.first().id
    beto.emit('enviar_mensagem_direta', {'target_id': ids['Ana'], 'texto': 'oi ana', 'reply_to': d1})
    rec = [m for m in ev(beto, 'receber_mensagem_direta')][0]['args'][0]
    ok(rec['reply'] and rec['reply']['id'] == d1 and rec['reply']['autor'] == 'Ana', 'DM: resposta leva a citação')
    h = fbeto.get(f'/api/dms/{ids["Ana"]}').get_json()
    ok([x for x in h if x['texto'] == 'oi ana'][0]['reply']['id'] == d1, 'DM: histórico devolve a citação')

print()
print('FALHAS:', falhas if falhas else 'nenhuma')
sys.exit(1 if falhas else 0)
