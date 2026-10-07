"""Notificações push: chave VAPID, inscrição, quem recebe (só quem não está com o app visível), "Não perturbar" e limpeza de inscrição morta."""
import os, sys
from types import SimpleNamespace
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Friendship, PushSub, ConfigApp
import pywebpush

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

# o envio roda em segundo plano; nos testes roda na hora, e o webpush vira um registrador
enviados = []
mortas = set()
def webpush_falso(subscription_info=None, data=None, **kw):
    enviados.append((subscription_info['endpoint'], data))
    if subscription_info['endpoint'] in mortas:
        raise pywebpush.WebPushException('gone', response=SimpleNamespace(status_code=410))
pywebpush.webpush = webpush_falso
import app.push as push
push.socketio.start_background_task = lambda f, *a, **k: f(*a, **k)

SUB = lambda n: {'endpoint': f'https://push.exemplo.com/{n}' + 'x' * 30, 'keys': {'p256dh': 'B' * 60, 'auth': 'a' * 22}}

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Caio'], status='accepted')); db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    ana, fana = cliente('Ana'); beto, fbeto = cliente('Beto'); caio, fcaio = cliente('Caio')

    # chave VAPID: gerada uma vez e guardada
    k1 = fbeto.get('/api/push/chave').get_json()['chave']
    k2 = fbeto.get('/api/push/chave').get_json()['chave']
    ok(k1 == k2 and len(k1) >= 80, 'Chave pública VAPID gerada e estável')
    ok(ConfigApp.query.count() == 2, 'Chaves guardadas no banco (sobrevivem a deploy)')
    ok(app.test_client().get('/api/push/chave').status_code == 401, 'Sem login não pega a chave')

    # inscrição
    ok(fbeto.post('/api/push/inscrever', json=SUB('beto')).status_code == 200, 'Beto inscreve o aparelho')
    ok(fbeto.post('/api/push/inscrever', json={'endpoint': 'http://inseguro', 'keys': {}}).status_code == 400, 'Inscrição inválida é recusada')
    ok(PushSub.query.filter_by(person_id=ids['Beto']).count() == 1, 'Uma inscrição do Beto')
    fbeto.post('/api/push/inscrever', json=SUB('beto'))
    ok(PushSub.query.filter_by(person_id=ids['Beto']).count() == 1, 'Inscrever de novo não duplica')

    # Beto conectado mas com o app em segundo plano: recebe push
    beto.emit('visibilidade', {'visivel': False}); beto.get_received()
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'oi beto, tudo bem?'}); ana.get_received(); beto.get_received()
    ok(len(enviados) == 1 and 'Ana' in enviados[0][1] and 'oi beto' in enviados[0][1] and '/chat?dm=' in enviados[0][1],
       'App em segundo plano: Beto recebe push com nome, texto e atalho pra conversa')

    # app visível: sem push (o aviso dentro do app já basta)
    enviados.clear()
    beto.emit('visibilidade', {'visivel': True})
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'e aí?'}); ana.get_received(); beto.get_received()
    ok(not enviados, 'App visível: nenhum push')

    # Não perturbar: sem push
    beto.emit('visibilidade', {'visivel': False})
    Person.query.get(ids['Beto']).status = 'dnd'; db.session.commit()
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'oi de novo'}); ana.get_received(); beto.get_received()
    ok(not enviados, 'Não perturbar: nenhum push')
    Person.query.get(ids['Beto']).status = 'online'; db.session.commit()

    # quem não tem inscrição não recebe (e nada quebra)
    caio.emit('visibilidade', {'visivel': False})
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Caio'], 'texto': 'oi caio'}); ana.get_received(); caio.get_received()
    ok(not enviados, 'Sem inscrição: nada é enviado')

    # ligação com o app em segundo plano
    beto.emit('visibilidade', {'visivel': False})
    ana.emit('chamar_amigo', {'amigo_id': ids['Beto'], 'tipo': 'voz'}); ana.get_received()
    ok(any('te ligando' in d for _, d in enviados), 'Ligação chega como push "está te ligando"')

    # inscrição que o navegador recusa (410) é apagada
    enviados.clear()
    fbeto.post('/api/push/inscrever', json=SUB('beto'))
    mortas.add(SUB('beto')['endpoint'])
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'mais uma'}); ana.get_received(); beto.get_received()
    ok(PushSub.query.filter_by(person_id=ids['Beto']).count() == 0, 'Inscrição morta (410) é removida')

    # mesmo aparelho, outra conta: o aviso passa pra quem entrou por último
    fbeto.post('/api/push/inscrever', json=SUB('aparelho'))
    fcaio.post('/api/push/inscrever', json=SUB('aparelho'))
    dono = PushSub.query.filter_by(endpoint=SUB('aparelho')['endpoint']).one().person_id
    ok(dono == ids['Caio'], 'Outra conta no mesmo aparelho assume a inscrição')
    # cancelar só vale pro dono
    fbeto.post('/api/push/cancelar', json={'endpoint': SUB('aparelho')['endpoint']})
    ok(PushSub.query.filter_by(endpoint=SUB('aparelho')['endpoint']).count() == 1, 'Quem não é dono não cancela a inscrição de outro')
    fcaio.post('/api/push/cancelar', json={'endpoint': SUB('aparelho')['endpoint']})
    ok(PushSub.query.filter_by(endpoint=SUB('aparelho')['endpoint']).count() == 0, 'O dono cancela')

    sw = app.test_client().get('/sw.js').get_data(as_text=True)
    ok("addEventListener('push'" in sw and "notificationclick" in sw, 'Service worker trata push e clique')

print()
print('FALHAS:', falhas if falhas else 'nenhuma')
sys.exit(1 if falhas else 0)
