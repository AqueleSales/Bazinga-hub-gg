"""Rodada 39: mensagem nova nos servidores e canais (bolinha de "não lida"), caixa de entrada que zera de verdade.

Cobre: ponto de leitura criado no topo (histórico antigo nunca vira "não lido"), contagem na conexão, aviso ao vivo só pra quem enxerga o canal
(público = sala do servidor; privado = só convidados), marcar canal como lido (e propagar às outras abas), citação lida junto, "marcar tudo como lido"
(canais + DMs), mensagem própria nunca conta, e o que o cliente promete (arquivos, ganchos, CSS)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Server, Channel, Message, CanalLeitura, Notificacao, DirectMessage, Friendship

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')
def ler(rel): return open(os.path.join(RAIZ, rel), encoding='utf-8').read()

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    def reconectar(nome):
        # igual a cliente(), mas SEM esvaziar a fila: quero ver o que o servidor manda no connect
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc)

    ana, _ = cliente('Ana'); beto, _ = cliente('Beto'); caio, _ = cliente('Caio')
    ana.emit('criar_servidor_discord', {'nome': 'Casa'})
    srv = [m for m in ev(ana, 'servidor_discord_criado')][-1]['args'][0]; sid = srv['id']
    geral = [x for x in srv['channels'] if x['type'] == 'text'][0]['id']
    ana.emit('criar_canal', {'server_id': sid, 'nome': 'extra'}); ev(ana)
    extra = Channel.query.filter_by(name='extra').first().id
    ana.emit('criar_convite', {'server_id': sid}); cod = ev(ana, 'convite_criado')[-1]['args'][0]['code']
    for cl in (beto, caio):
        cl.emit('entrar_por_convite', {'code': cod}); ev(cl)
    ana.emit('criar_canal', {'server_id': sid, 'nome': 'secreto', 'privado': True, 'membros': [ids['Beto']]}); ev(ana)
    secreto = Channel.query.filter_by(name='secreto').first().id

    # histórico que já existia ANTES de alguém abrir o app: nunca vira "não lido"
    for i in range(5):
        db.session.add(Message(text=f'antigo{i}', person_id=ids['Ana'], channel_id=extra))
    db.session.commit()
    beto.disconnect(); beto = reconectar('Beto')
    rec = ev(beto, 'canais_nao_lidos')
    ok(len(rec) == 1 and rec[0]['args'][0] == {}, 'primeira conexão: histórico antigo NÃO vira não lido (ponto de leitura no topo)')
    ok(CanalLeitura.query.filter_by(person_id=ids['Beto'], channel_id=extra).count() == 1, 'ponto de leitura criado por canal')

    # Beto está olhando o #geral; Ana escreve no #extra e no #geral
    beto.emit('entrar_canal', {'canal_id': geral}); ev(beto)
    ana.emit('entrar_canal', {'canal_id': extra}); ev(ana)
    ana.emit('enviar_mensagem', {'canal_id': extra, 'texto': 'oi do extra', 'temp_id': 't1'})
    ativ = ev(beto, 'canal_atividade')
    ok(len(ativ) == 1 and ativ[0]['args'][0]['canal_id'] == extra and ativ[0]['args'][0]['server_id'] == sid, 'quem não está no canal recebe canal_atividade')
    ok(set(ativ[0]['args'][0]) == {'server_id', 'canal_id', 'canal_nome', 'msg_id', 'autor_id'}, 'o aviso não leva o texto da mensagem')
    ok(len(ev(caio, 'canal_atividade')) == 1, 'outro membro (sala do servidor) também recebe')
    ok(not [m for m in ev(ana, 'canal_atividade')], 'quem escreveu não recebe o próprio aviso')

    # canal privado: Caio (membro sem acesso) NÃO fica sabendo; Beto (convidado) fica
    ana.emit('entrar_canal', {'canal_id': secreto}); ev(ana); ev(caio); ev(beto)
    ana.emit('enviar_mensagem', {'canal_id': secreto, 'texto': 'segredo'})
    ok(len(ev(beto, 'canal_atividade')) == 1, 'convidado do canal privado recebe o aviso')
    ok(not ev(caio, 'canal_atividade'), 'membro SEM acesso ao canal privado não recebe nada (nem o nome vaza)')

    # reconexão do Beto: contagem certa (1 no #extra, 1 no #secreto)
    beto.disconnect(); beto = reconectar('Beto')
    mapa = ev(beto, 'canais_nao_lidos')[-1]['args'][0]
    ok(mapa.get(str(extra)) == 1 or mapa.get(extra) == 1, 'na conexão a contagem do #extra é 1')
    ok((mapa.get(str(secreto)) or mapa.get(secreto)) == 1, 'na conexão a contagem do canal privado é 1 (pra quem pode ver)')
    ok(not (mapa.get(str(geral)) or mapa.get(geral)), 'canal sem mensagem nova não aparece')

    # mensagem do próprio Beto nunca conta pra ele
    beto.emit('entrar_canal', {'canal_id': extra}); beto.emit('enviar_mensagem', {'canal_id': extra, 'texto': 'eu mesmo'}); ev(beto)
    beto.disconnect(); beto = reconectar('Beto')
    mapa = ev(beto, 'canais_nao_lidos')[-1]['args'][0]
    ok((mapa.get(str(extra)) or mapa.get(extra)) == 1, 'a mensagem que EU mandei não soma como não lida')

    # citação na caixa de entrada + canal lido leva as duas
    db.session.add(Notificacao(person_id=ids['Beto'], tipo='mencao', de_id=ids['Ana'], titulo='Ana te citou', texto='oi', ref=f'{sid}:{extra}', lida=False))
    db.session.commit()
    beto.emit('canal_lido', {'canal_id': extra})
    eco = ev(beto, 'canal_lido')
    ok(len(eco) == 1 and eco[0]['args'][0]['canal_id'] == extra, 'canal_lido volta pras abas da própria pessoa (regra 6)')
    ok(Notificacao.query.filter_by(person_id=ids['Beto'], tipo='mencao', lida=False).count() == 0, 'abrir o canal dá por lida a citação dele')
    topo = db.session.query(db.func.max(Message.id)).filter_by(channel_id=extra).scalar()
    ok(CanalLeitura.query.filter_by(person_id=ids['Beto'], channel_id=extra).first().ultimo_id == topo, 'ponto de leitura vai pro topo do canal')
    # alheio: quem não enxerga o canal não marca nada
    caio.emit('canal_lido', {'canal_id': secreto}); ok(not ev(caio, 'canal_lido'), 'sem acesso ao canal não há canal_lido')
    caio.emit('canal_lido', 'lixo'); caio.emit('canal_lido', {'canal_id': 'x'}); ok(True, 'payload inválido não derruba')

    # marcar tudo como lido: canais + DMs
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted')); db.session.commit()
    db.session.add(DirectMessage(sender_id=ids['Ana'], receiver_id=ids['Beto'], content='psiu', lida=False)); db.session.commit()
    beto.emit('marcar_notificacoes_lidas', {})
    rb = ev(beto)
    nomes = [m['name'] for m in rb]
    ok('canais_nao_lidos' in nomes and [m for m in rb if m['name'] == 'canais_nao_lidos'][-1]['args'][0] == {}, '"marcar tudo como lido" zera os canais')
    ok('dm_lidas' in nomes, '... e avisa as DMs que foram lidas')
    ok(DirectMessage.query.filter_by(receiver_id=ids['Beto'], lida=False).count() == 0, '... e as DMs ficam lidas no banco')
    beto.disconnect(); beto = reconectar('Beto')
    ok(ev(beto, 'canais_nao_lidos')[-1]['args'][0] == {}, 'depois de marcar tudo, a reconexão não traz nada não lido')

    # apagar UM aviso da caixa
    n = Notificacao(person_id=ids['Beto'], tipo='sistema', titulo='x'); db.session.add(n); db.session.commit(); nid = n.id
    caio.emit('apagar_notificacao', {'id': nid}); ev(caio)
    ok(Notificacao.query.filter_by(id=nid).count() == 1, 'ninguém apaga aviso dos outros')
    beto.emit('apagar_notificacao', {'id': nid}); ev(beto)
    ok(Notificacao.query.filter_by(id=nid).count() == 0, 'a pessoa apaga o próprio aviso (X do item)')
    beto.emit('apagar_notificacao', 'lixo'); beto.emit('apagar_notificacao', {'id': 'a'}); ok(True, 'payload inválido do X não derruba')

# ---- o que o cliente promete ----
chat = ler('templates/chat.html'); js = ler('static/js/avisos.js'); css = ler('static/css/avisos.css'); lm = ler('static/css/loja_mapa.css')
ok("js/avisos.js" in chat and "css/avisos.css" in chat and 'Avisos.iniciar(' in chat, 'chat.html carrega e inicia o Avisos')
ok('Avisos.abriuCanal(' in chat and 'Avisos.chegouNoAberto(' in chat and 'Avisos.pintar()' in chat, 'ganchos: abrir canal, mensagem no canal aberto, recontar a caixa')
ok("socket.on('canais_nao_lidos'" in js and "socket.on('canal_atividade'" in js and "socket.on('canal_lido'" in js, 'o cliente escuta os 3 eventos')
ok('av-pilula' in css and 'av-num' in css and 'av-canal' in css, 'CSS da pílula, do número vermelho e do canal')
ok('animation' not in css.split('@keyframes avPulo')[0].replace('.av-num.pulo { animation: avPulo', ''), 'só o número que chega anima (e só transform)')
ok("document.body.dataset.vista = viewName" in chat and 'body[data-vista]:not([data-vista="home"]) .lg-dock' in lm, 'a gaveta "Lojas" só aparece com o mapa à vista')
ok('lg-conta">0<' not in ler('static/js/loja_mapa.js'), 'sem contador vermelho na aba "Lojas" (parecia notificação)')
ok("#dm-chat-view { background-color: var(--bg-primary); }" in chat and 'background-color: var(--bg-primary); position: absolute; top: 48px' not in chat,
   'o fundo da DM não é mais inline (o papel de parede personalizado aparece)')
ok('ib-n-nao' in chat and 'ib-qtd ${n.lida' in chat and "data-ib-x" in chat, 'caixa de entrada: filtro "não lidas", contador cinza quando lida, X por aviso')

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
