"""Editar e apagar mensagem de DM: eventos PRÓPRIOS (o id de uma DirectMessage não é o de uma Message de canal; a numeração se cruza).
Bug de origem: a DM usava `editar_mensagem`/`apagar_mensagem`, o servidor procurava o id entre as mensagens de CANAL e dava
"só pode editar as suas próprias" (era de outra pessoa) ou, pior, mexia numa mensagem sua de um servidor."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Message, DirectMessage, Friendship, Channel

app = create_app()
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')
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
    for n in ('Ana', 'Beto', 'Carol', 'Dani'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Carol'], status='pending'))      # nem amiga (ainda): sem link
    db.session.add(Friendship(requester_id=ids['Dani'], addressee_id=ids['Ana'], status='blocked'))       # Dani bloqueou a Ana
    db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    ana, fana = cliente('Ana'); beto, fbeto = cliente('Beto'); carol, _ = cliente('Carol'); dani, _ = cliente('Dani')
    ana2, _ = cliente('Ana')        # a mesma Ana em outra aba

    # Um servidor da Ana com uma mensagem de canal do BETO e uma da própria ANA, com os MESMOS ids que as DMs vão ter.
    ana.emit('criar_servidor_discord', {'nome': 'Srv'})
    srv = ev(ana, 'servidor_discord_criado')[-1]['args'][0]
    canal = [x for x in srv['channels'] if x['type'] == 'text'][0]['id']
    db.session.add(Message(text='canal do Beto', person_id=ids['Beto'], channel_id=canal))
    db.session.add(Message(text='canal da Ana', person_id=ids['Ana'], channel_id=canal)); db.session.commit()
    canal_beto = Message.query.filter_by(text='canal do Beto').first().id
    canal_ana = Message.query.filter_by(text='canal da Ana').first().id

    def mandar(de, cli, para, texto):
        cli.emit('enviar_mensagem_direta', {'target_id': ids[para], 'texto': texto}); ev(cli)
        return DirectMessage.query.filter_by(sender_id=ids[de], receiver_id=ids[para], content=texto).first()

    dm1 = mandar('Ana', ana, 'Beto', 'oi beto')
    dm2 = mandar('Ana', ana, 'Beto', 'tudo bem?')
    ok(dm1.id == canal_beto and dm2.id == canal_ana, f'(prepara) os ids da DM e os de canal se cruzam: DM {dm1.id}/{dm2.id} = canal {canal_beto}/{canal_ana}')
    for cl in (ana, ana2, beto, carol, dani): ev(cl)

    # ---------- editar ----------
    ana.emit('editar_mensagem_direta', {'msg_id': dm1.id, 'texto': '  oi beto, editado  '})
    ea, ea2, eb = ev(ana, 'mensagem_direta_editada'), ev(ana2, 'mensagem_direta_editada'), ev(beto, 'mensagem_direta_editada')
    db.session.expire_all()
    novo = DirectMessage.query.get(dm1.id)
    ok(novo.content == 'oi beto, editado' and novo.edited_at is not None, 'o autor edita a própria DM (texto sem espaços sobrando e marcada como editada)')
    ok(ea and ea[0]['args'][0] == {'msg_id': dm1.id, 'texto': 'oi beto, editado', 'editada': True}, 'a aba de quem editou recebe o novo texto')
    ok(ea2 and eb, 'a outra aba dele e o outro lado da conversa também recebem (regra 6)')
    ok(Message.query.get(canal_beto).text == 'canal do Beto' and Message.query.get(canal_beto).edited_at is None, 'a mensagem de CANAL de mesmo id (do Beto) não foi tocada')
    ok(not ev(carol, 'mensagem_direta_editada') and not ev(dani, 'mensagem_direta_editada'), 'terceiros não recebem nada da edição')

    beto.emit('editar_mensagem_direta', {'msg_id': dm1.id, 'texto': 'o Beto reescreve a Ana'})
    err = ev(beto, 'erro_bazinga'); db.session.expire_all()
    ok(err and 'só pode editar' in err[0]['args'][0]['msg'] and DirectMessage.query.get(dm1.id).content == 'oi beto, editado', 'quem recebeu a DM não edita a mensagem do outro')
    ok(not ev(ana, 'mensagem_direta_editada'), '...e a Ana não vê nada mudar')

    ana.emit('editar_mensagem_direta', {'msg_id': dm1.id, 'texto': 'oi beto, editado'})
    ok(not ev(ana, 'mensagem_direta_editada') and not ev(beto, 'mensagem_direta_editada'), 'editar pro mesmo texto não avisa ninguém')
    ana.emit('editar_mensagem_direta', {'msg_id': dm1.id, 'texto': '   '}); ev(ana)
    db.session.expire_all()
    ok(DirectMessage.query.get(dm1.id).content == 'oi beto, editado', 'editar pra vazio (sem anexo) é ignorado')
    ana.emit('editar_mensagem_direta', {'msg_id': dm1.id, 'texto': 'x' * 5000}); ev(ana); db.session.expire_all()
    ok(len(DirectMessage.query.get(dm1.id).content) == 2000, 'o texto editado respeita o teto de 2000 caracteres')
    ana.emit('editar_mensagem_direta', {'msg_id': dm1.id, 'texto': 'oi beto, editado'}); ev(ana, None)

    for lixo in ('abc', [1, 2], {'msg_id': 'x'}, {'msg_id': -5, 'texto': 'a'}, {'msg_id': 999999, 'texto': 'a'}, {'msg_id': None}):
        ana.emit('editar_mensagem_direta', lixo)
    ok(not ev(ana, 'erro_bazinga'), 'payload inválido ou id que não existe não quebra nem avisa erro')

    # link: quem ainda não é amigo não manda link, nem editando
    dmc = mandar('Ana', ana, 'Carol', 'oi carol'); ev(carol)
    ana.emit('editar_mensagem_direta', {'msg_id': dmc.id, 'texto': 'olha https://golpe.example.com/x'})
    err = ev(ana, 'erro_bazinga'); db.session.expire_all()
    ok(err and 'só entre amigos' in err[0]['args'][0]['msg'].lower() and DirectMessage.query.get(dmc.id).content == 'oi carol', 'editar pra enfiar link numa conversa que não é de amigos é recusado')
    ana.emit('editar_mensagem_direta', {'msg_id': dmc.id, 'texto': 'oi carol, tudo bem'}); db.session.expire_all()
    ok(DirectMessage.query.get(dmc.id).content == 'oi carol, tudo bem', '...mas texto comum edita normalmente')

    # bloqueio corta
    db.session.add(DirectMessage(sender_id=ids['Ana'], receiver_id=ids['Dani'], content='antes do bloqueio')); db.session.commit()
    dmd = DirectMessage.query.filter_by(receiver_id=ids['Dani']).first()
    ana.emit('editar_mensagem_direta', {'msg_id': dmd.id, 'texto': 'depois do bloqueio'})
    err = ev(ana, 'erro_bazinga'); db.session.expire_all()
    ok(err and DirectMessage.query.get(dmd.id).content == 'antes do bloqueio' and not ev(dani, 'mensagem_direta_editada'), 'quem foi bloqueado não consegue mais editar a mensagem pra quem bloqueou')

    # anotações (DM pra si mesma): uma sala só
    self_dm = mandar('Ana', ana, 'Ana', 'minha anotação'); ev(ana2)
    ana.emit('editar_mensagem_direta', {'msg_id': self_dm.id, 'texto': 'anotação nova'})
    ok(len(ev(ana, 'mensagem_direta_editada')) == 1, 'Anotações: edita e a aba recebe o aviso uma vez só')

    # ---------- histórico ----------
    h = fana.get(f'/api/dms/{ids["Beto"]}').get_json()
    por_id = {m['id']: m for m in h}
    ok(por_id[dm1.id]['editada'] is True and por_id[dm2.id]['editada'] is False, '/api/dms marca (editada) só na que foi editada')

    # ---------- apagar ----------
    beto.emit('apagar_mensagem_direta', {'msg_id': dm2.id})
    err = ev(beto, 'erro_bazinga')
    ok(err and 'só pode apagar' in err[0]['args'][0]['msg'] and DirectMessage.query.get(dm2.id) is not None, 'quem recebeu não apaga a mensagem do outro')
    ok(Message.query.get(canal_ana) is not None, 'e a mensagem de CANAL de mesmo id (da Ana) continua lá')

    ana.emit('apagar_mensagem_direta', {'msg_id': dm2.id})
    aa, aa2, ab = ev(ana, 'mensagem_direta_apagada'), ev(ana2, 'mensagem_direta_apagada'), ev(beto, 'mensagem_direta_apagada')
    db.session.expire_all()
    ok(DirectMessage.query.get(dm2.id) is None, 'o autor apaga a própria DM')
    ok(aa and aa[0]['args'][0] == {'msg_id': dm2.id} and aa2 and ab, 'as duas pontas (e todas as abas) recebem o aviso pra tirar a bolha')
    ok(Message.query.get(canal_ana) is not None and Message.query.get(canal_ana).text == 'canal da Ana' and Message.query.get(canal_beto) is not None,
       'nenhuma mensagem de CANAL foi apagada (era o risco do id cruzado)')
    ana.emit('apagar_mensagem_direta', {'msg_id': dm2.id}); ok(not ev(ana, 'erro_bazinga'), 'apagar de novo (já apagada) não dá erro')
    for lixo in ('abc', [1], {'msg_id': 'x'}, {'msg_id': 0}):
        ana.emit('apagar_mensagem_direta', lixo)
    ok(not ev(ana, 'erro_bazinga'), 'apagar com payload inválido não quebra')

    # dono do servidor não ganha poder nenhum sobre DM (só o autor apaga)
    ok(DirectMessage.query.get(dm1.id) is not None, 'a outra DM da conversa segue intacta')

    # ---------- o cliente fala com os eventos certos ----------
    html = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
    ok("dados.dm ? 'editar_mensagem_direta' : 'editar_mensagem'" in html, 'o cliente edita DM pelo evento de DM e canal pelo de canal')
    ok("dm ? 'apagar_mensagem_direta' : 'apagar_mensagem'" in html, 'o cliente apaga DM pelo evento de DM e canal pelo de canal')
    ok("socket.on('mensagem_direta_editada'" in html and "socket.on('mensagem_direta_apagada'" in html, 'o cliente escuta os avisos de DM')
    ok("#messages-container .message[data-msg-id=" in html and "#dm-messages-container .message[data-msg-id=" in html,
       'cada aviso só mexe no container da sua conversa (id de DM e de canal se repetem)')
    ok("document.querySelector(`.message[data-msg-id=\"${dados.msg_id}\"]`)" not in html, 'nenhum aviso de canal procura a bolha no documento inteiro')
    ok('so-canal' in html and "toggle('em-dm'" in html, 'na DM o menu esconde reagir e fixar (só existem em canal)')
    ok("!dados.dm && Cargos.podeApagarMensagem" in html, 'na DM o dono do servidor aberto não ganha o botão de apagar mensagem dos outros')
    ok('edited_at TIMESTAMP' in open(os.path.join(RAIZ, '..', 'atualizar_banco.py'), encoding='utf-8').read(), 'a coluna nova está no atualizar_banco.py')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
