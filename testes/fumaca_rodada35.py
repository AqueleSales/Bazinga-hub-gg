"""Rodada 35: denunciar MENSAGEM (de canal e de DM), patente e título AO LADO DO NOME (mensagens ao vivo, histórico e lista de membros), e o limite
de requisições por IP. Mensagem denunciada não some sozinha (só um admin decide); só quem enxerga o canal / está na DM denuncia; o trecho fica
guardado; o admin remove e as telas se atualizam."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, bazar, utils
from app.models import Role, Person, Friendship, Channel, Server, Message, DirectMessage, Denuncia, ConfigApp

falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


app = create_app()
with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio', 'Dani'):
        pe = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower())
        db.session.add(pe); db.session.commit(); ids[n] = pe.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))
    # a Ana tem um nível alto e um título pra aparecer ao lado do nome
    ana = Person.query.get(ids['Ana']); ana.xp = 3_000_000
    db.session.commit()
    adm = ConfigApp.query.get('admin_ids') or ConfigApp(chave='admin_ids')
    adm.valor = str(ids['Dani']); db.session.add(adm); db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc), fc

    ca, fca = cliente('Ana'); ev(ca)
    ca.emit('criar_servidor_discord', {'nome': 'Casa'}); ev(ca)
    srv = Server.query.filter_by(name='Casa').first()
    canal = Channel.query.filter_by(server_id=srv.id, channel_type='text').first()
    ca.emit('criar_convite', {'server_id': srv.id}); cod = ev(ca, 'convite_criado')[-1]['args'][0]['code']
    cb, fcb = cliente('Beto'); ev(cb); cb.emit('entrar_por_convite', {'code': cod}); ev(cb)
    cc, fcc = cliente('Caio'); ev(cc)                       # Caio NÃO está no servidor
    cd, fcd = cliente('Dani'); ev(cd)
    ca = cliente('Ana')[0]; cb = cliente('Beto')[0]
    for cl in (ca, cb):
        ev(cl)
    ca.emit('entrar_canal', {'canal_id': canal.id}); cb.emit('entrar_canal', {'canal_id': canal.id})
    for cl in (ca, cb):
        ev(cl)

    # ---------------------------------------------- patente ao lado do nome ----------------------------------------------
    ca.emit('enviar_mensagem', {'canal_id': canal.id, 'texto': 'oi pessoal, tudo bem por aqui?'})
    rec = ev(cb, 'receber_mensagem')
    m = rec[-1]['args'][0] if rec else {}
    ok(m.get('patente', {}).get('id') and m['patente'].get('nome_completo') and 'sub' in m['patente'], 'a mensagem ao vivo leva a patente de quem escreveu')
    ok('titulo' in m, 'a mensagem ao vivo tem o campo título (vazio quando a pessoa não equipou)')
    hist = fcb.get(f'/api/mensagens/{canal.id}').get_json()
    h = hist[-1] if isinstance(hist, list) else {}
    ok(h.get('patente', {}).get('id') == m['patente']['id'], 'o histórico traz a mesma patente (nível 3.000.000 de XP é alto)')
    ok(m['patente']['id'] != 'iniciado', 'quem tem muito XP não aparece como Iniciado')
    cb.emit('listar_membros_servidor', {'server_id': srv.id})
    mem = ev(cb, 'membros_do_servidor')
    lista = mem[-1]['args'][0].get('membros') if mem else []
    ok(lista and all('patente' in x and 'titulo' in x for x in lista), 'a lista de membros traz patente e título de cada pessoa')
    ok(utils.identidade_mini(Person.query.get(ids['Beto']))['patente']['id'] == 'iniciado', 'quem acabou de chegar é Iniciado')

    # ---------------------------------------------- denunciar mensagem de canal ----------------------------------------------
    msg = Message.query.filter_by(channel_id=canal.id).order_by(Message.id.desc()).first()
    cb.emit('denunciar', {'tipo': 'mensagem', 'id': msg.id, 'motivo': 'spam', 'detalhe': 'só propaganda'})
    ok(ev(cb, 'denuncia_registrada'), 'quem está no canal denuncia a mensagem de outra pessoa')
    d = Denuncia.query.filter_by(tipo='mensagem', alvo_id=msg.id).first()
    ok(d and d.detalhe.startswith('Trecho: oi pessoal') and 'só propaganda' in d.detalhe, 'a denúncia guarda um trecho da mensagem (vale mesmo se ela for apagada)')
    ca.emit('denunciar', {'tipo': 'mensagem', 'id': msg.id, 'motivo': 'spam'})
    ok(ev(ca, 'erro_bazinga'), 'não dá pra denunciar a própria mensagem')
    cb.emit('denunciar', {'tipo': 'mensagem', 'id': msg.id, 'motivo': 'spam'})
    ok(ev(cb, 'denuncia_registrada')[-1]['args'][0].get('repetida'), 'denunciar de novo avisa que já foi denunciado')
    cc.emit('denunciar', {'tipo': 'mensagem', 'id': msg.id, 'motivo': 'spam'})
    ok(ev(cc, 'erro_bazinga') and Denuncia.query.filter_by(tipo='mensagem', alvo_id=msg.id).count() == 1, 'quem NÃO está no canal não denuncia (nem descobre que a mensagem existe)')
    cb.emit('denunciar', {'tipo': 'mensagem', 'id': msg.id, 'motivo': 'inventado'})
    ok(Denuncia.query.filter_by(tipo='mensagem', alvo_id=msg.id).count() == 1, 'motivo fora da lista é recusado')
    for outro in ('Caio', 'Dani'):
        pass
    ok(Message.query.get(msg.id) is not None, 'a mensagem denunciada NÃO some sozinha (só um administrador decide)')

    # fila de moderação do admin + remover
    fila = bazar.fila_de_moderacao()
    item = next((x for x in fila if x['tipo'] == 'mensagem' and x['alvo_id'] == msg.id), None)
    ok(item and item['existe'] and 'oi pessoal' in item['alvo']['titulo'] and 'Ana' in item['alvo']['sub'], 'a mensagem aparece na fila de moderação com texto e autor')
    cd.emit('bazar_moderar', {'tipo': 'mensagem', 'alvo_id': msg.id, 'acao': 'remover'})
    ok(Message.query.get(msg.id) is None, 'o admin remove a mensagem denunciada')
    ok(ev(cb, 'mensagem_apagada'), 'quem está no canal vê a mensagem sumir na hora (regra 6)')
    ok(Denuncia.query.filter_by(tipo='mensagem', alvo_id=msg.id, resolvida=True).count() == 1, 'as denúncias dessa mensagem ficam resolvidas')

    # ---------------------------------------------- denunciar mensagem direta ----------------------------------------------
    dm = DirectMessage(sender_id=ids['Ana'], receiver_id=ids['Beto'], content='mensagem privada chata')
    db.session.add(dm); db.session.commit()
    cb.emit('denunciar', {'tipo': 'dm', 'id': dm.id, 'motivo': 'assedio'}); ev(cb)
    ok(Denuncia.query.filter_by(tipo='dm', alvo_id=dm.id).count() == 1, 'quem recebeu a DM denuncia')
    cc.emit('denunciar', {'tipo': 'dm', 'id': dm.id, 'motivo': 'assedio'})
    ok(ev(cc, 'erro_bazinga') and Denuncia.query.filter_by(tipo='dm', alvo_id=dm.id).count() == 1, 'quem não está na conversa não denuncia a DM')
    ca.emit('denunciar', {'tipo': 'dm', 'id': dm.id, 'motivo': 'assedio'})
    ok(ev(ca, 'erro_bazinga'), 'quem escreveu a DM não a denuncia')
    time.sleep(0.7)                                           # (freio de 0,5 s entre ações de moderação)
    cd.emit('bazar_moderar', {'tipo': 'dm', 'alvo_id': dm.id, 'acao': 'restaurar'})
    ok(DirectMessage.query.get(dm.id) is not None and Denuncia.query.filter_by(tipo='dm', alvo_id=dm.id, resolvida=True).count() == 1, 'dispensar a denúncia mantém a DM e a dá por resolvida')
    ok(ev(cc, 'mensagem_direta_apagada') == [], 'quem não é parte da DM nunca recebe aviso dela')

# ---------------------------------------------- o cliente promete ----------------------------------------------
def ler(rel):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', rel), encoding='utf-8') as f:
        return f.read()



# ---------------------------------------------- limite de requisições ----------------------------------------------
from app import limites
limites.zerar()
ok(limites.permitido(0, 'u1', 3, 60, agora=1000.0) == (True, 0), 'limite: a 1ª requisição passa')
limites.permitido(0, 'u1', 3, 60, agora=1001.0); limites.permitido(0, 'u1', 3, 60, agora=1002.0)
estouro = limites.permitido(0, 'u1', 3, 60, agora=1003.0)
ok(estouro[0] is False and 50 <= estouro[1] <= 60, 'limite: a 4ª em 60 s é barrada e diz quanto esperar')
ok(limites.permitido(0, 'u2', 3, 60, agora=1003.0)[0], 'limite: cada pessoa tem a sua própria conta')
ok(limites.permitido(0, 'u1', 3, 60, agora=1062.0)[0], 'limite: passada a janela, volta a valer')
limites.zerar()
with app.test_client() as web:
    with web.session_transaction() as s:
        s['user_id'] = ids['Ana']
    codigos = [web.get('/api/gifs?q=gato').status_code for _ in range(63)]
    ok(codigos[:60].count(429) == 0 and codigos[60:] == [429, 429, 429], 'limite: /api/gifs deixa 60 por minuto e barra o resto com 429')
    r429 = web.get('/api/gifs?q=gato')
    ok(r429.status_code == 429 and r429.headers.get('Retry-After') and 'Muitos pedidos' in r429.get_json()['msg'], 'limite: o 429 traz Retry-After e a mensagem em português')
    limites.zerar()
with app.test_client() as web:      # sem login vale o IP (o 1º de X-Forwarded-For)
    cab = {'X-Forwarded-For': '203.0.113.9, 10.0.0.1'}
    cod = [web.get('/auth/login', headers=cab).status_code for _ in range(23)]
    ok(cod[20:] == [429, 429, 429], 'limite: o login é por IP (20 por minuto)')
    ok(web.get('/auth/login', headers={'X-Forwarded-For': '203.0.113.10'}).status_code != 429, 'limite: outro IP não é afetado')
limites.zerar()
os.environ['LIMITE_REQUISICOES'] = '0'
ok(not limites.ligado(), 'limite: LIMITE_REQUISICOES=0 desliga')
os.environ.pop('LIMITE_REQUISICOES')
ok('limites.verificar' in ler('app/__init__.py'), 'o app liga o limite em todas as requisições')

ch = ler('app/templates/chat.html')
ok('id="ctx-report"' in ch and 'so-de-outros' in ch, 'o menu da mensagem tem "Denunciar mensagem" só pra mensagem de outra pessoa')
ok("abrirDenuncia(dm ? 'dm' : 'mensagem'" in ch, 'o botão abre a denúncia de DM ou de canal conforme a conversa')
ok('function identidadeHtml' in ch and 'identidadeHtml(extras, true)' in ch and 'identidadeHtml(m, false)' in ch, 'o cliente desenha a patente (e o título) ao lado do nome nas mensagens e nos membros')
ok('anim: 0' in ch[ch.index('function identidadeHtml'):ch.index('function identidadeHtml') + 600], 'o ícone da patente ao lado do nome é parado (dezenas na tela)')

print()
print('FALHAS:', len(falhas))
for f in falhas:
    print('  -', f)
sys.exit(1 if falhas else 0)
