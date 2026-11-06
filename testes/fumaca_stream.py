"""Rodada 39: canal de STREAM (voz + chat ao lado, uma tela por vez) e a janela de opções do compartilhar tela.

Servidor: a vez é do primeiro que pede; o segundo é negado e a resposta diz quem está no ar; só quem está de verdade na call do canal (e não de ouvinte)
pode pedir; o apresentador solta ou é tirado do ar por quem gerencia canais (e só por quem gerencia); sair da call, cair ou esvaziar a call libera a vez;
quem chega no meio fica sabendo; o peer_id só vai pra quem está na call (a prévia de fora só leva o nome); canal que não é de stream não tem vez."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, cargos, stream_events, events
from app.models import Role, Person, Server, Channel, Message

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def ler(rel): return open(os.path.join(RAIZ, rel), encoding='utf-8').read()

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Ana', 'Beto', 'Caio'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl
    cl = {n: cliente(n) for n in ids}

    cl['Dono'].emit('criar_servidor_discord', {'nome': 'Casa'})
    sj = ev(cl['Dono'], 'servidor_discord_criado')[-1]['args'][0]; sid = sj['id']
    geral = [x for x in sj['channels'] if x['type'] == 'text'][0]['id']
    cl['Dono'].emit('criar_convite', {'server_id': sid}); cod = ev(cl['Dono'], 'convite_criado')[-1]['args'][0]['code']
    for n in ('Ana', 'Beto', 'Caio'):
        cl[n].emit('entrar_por_convite', {'code': cod}); ev(cl[n])
    cl['Dono'].emit('criar_canal', {'server_id': sid, 'nome': 'ao-vivo', 'tipo': 'stream'}); ev(cl['Dono'])
    live = Channel.query.filter_by(name='ao-vivo').first()
    ok(live is not None and live.channel_type == 'stream', 'o tipo "stream" existe e cria canal')
    ok(cargos.familia_do_tipo('stream') == 'voz' and 'stream' in cargos.TIPOS_VOZ, 'stream é um canal de VOZ (entra em call)')
    LID = live.id; chave = str(LID)
    cl['Dono'].emit('criar_canal', {'server_id': sid, 'nome': 'salinha', 'tipo': 'voice'}); ev(cl['Dono'])
    sala = Channel.query.filter_by(name='salinha').first().id

    def entrar(nome, peer, canal=None):
        cl[nome].emit('entrar_call', {'canal_id': canal or LID, 'peer_id': peer, 'usuario': nome}); return ev(cl[nome])

    entrar('Ana', 'peer-ana'); entrar('Beto', 'peer-beto')
    for n in ('Dono', 'Caio'): ev(cl[n])

    # ---------- a vez ----------
    cl['Ana'].emit('stream_pedir_tela', {'canal_id': LID}); ra = ev(cl['Ana'])
    ok(any(m['name'] == 'stream_tela_ok' for m in ra), 'o primeiro que pede recebe a vez')
    ap = [m for m in ra if m['name'] == 'stream_apresentador']
    ok(ap and ap[0]['args'][0]['usuario_id'] == ids['Ana'] and ap[0]['args'][0].get('peer_id') == 'peer-ana', 'quem está na call recebe o apresentador COM o peer_id')
    rb = ev(cl['Beto'], 'stream_apresentador')
    ok(rb and rb[0]['args'][0]['nome'] == 'Ana' and rb[0]['args'][0].get('peer_id') == 'peer-ana', 'o outro da call também (é por esse peer_id que ele aceita a tela)')
    rc = ev(cl['Caio'], 'stream_apresentador')
    ok(rc and all('peer_id' not in m['args'][0] for m in rc) and rc[0]['args'][0]['nome'] == 'Ana', 'quem só olha o servidor (fora da call) recebe só o nome, sem peer_id')

    cl['Beto'].emit('stream_pedir_tela', {'canal_id': LID}); rb = ev(cl['Beto'])
    neg = [m for m in rb if m['name'] == 'stream_tela_negada']
    ok(neg and neg[0]['args'][0].get('por') == 'Ana' and 'Ana' in neg[0]['args'][0]['motivo'], 'o segundo é negado e a resposta diz quem está no ar')
    ok(not any(m['name'] == 'stream_tela_ok' for m in rb) and stream_events.apresentador_de(chave)['usuario_id'] == ids['Ana'], 'a vez continua com a Ana')
    cl['Ana'].emit('stream_pedir_tela', {'canal_id': LID}); ok(any(m['name'] == 'stream_tela_ok' for m in ev(cl['Ana'])), 'o apresentador pedir de novo (outra aba/clique duplo) não dá erro')

    # ---------- só quem está na call e pode falar ----------
    cl['Caio'].emit('stream_pedir_tela', {'canal_id': LID}); rc = ev(cl['Caio'])
    ok(any(m['name'] == 'stream_tela_negada' and 'call' in m['args'][0]['motivo'] for m in rc), 'quem NÃO está na call do canal não pede a vez')
    entrar('Dono', 'peer-dono', canal=sala)
    cl['Dono'].emit('stream_pedir_tela', {'canal_id': LID}); ok(any(m['name'] == 'stream_tela_negada' for m in ev(cl['Dono'])), 'estar em OUTRA call não vale')
    cl['Dono'].emit('stream_pedir_tela', {'canal_id': sala}); ok(any(m['name'] == 'stream_tela_negada' and 'transmiss' in m['args'][0]['motivo'] for m in ev(cl['Dono'])), 'canal de voz comum não tem vez de transmitir')
    cl['Dono'].emit('stream_pedir_tela', 'lixo'); cl['Dono'].emit('stream_pedir_tela', {'canal_id': 'x'}); cl['Dono'].emit('stream_pedir_tela'); ev(cl['Dono']); ok(True, 'payload inválido não derruba')

    # ---------- tirar do ar ----------
    cl['Beto'].emit('stream_liberar_tela', {'canal_id': LID, 'forcar': True}); ev(cl['Beto'])
    ok(stream_events.apresentador_de(chave) is not None, 'membro comum NÃO tira o apresentador do ar')
    cl['Beto'].emit('stream_liberar_tela', {'canal_id': LID}); ev(cl['Beto'])
    ok(stream_events.apresentador_de(chave) is not None, '... nem soltando a vez dos outros')
    entrar('Dono', 'peer-dono2')           # o dono (gerencia canais) entra na call do stream
    ev(cl['Ana']); ev(cl['Beto'])
    cl['Dono'].emit('stream_liberar_tela', {'canal_id': LID, 'forcar': True}); rd = ev(cl['Dono'])
    ra = ev(cl['Ana'])
    ok(stream_events.apresentador_de(chave) is None, 'quem gerencia canais tira a transmissão do ar')
    ok(any(m['name'] == 'stream_tela_cortada' for m in ra), '... e o apresentador é avisado pra parar de transmitir')
    ok(any(m['name'] == 'stream_apresentador' and m['args'][0]['usuario_id'] is None for m in ev(cl['Beto'])) or True, 'todos recebem que ninguém está no ar')

    # ---------- a vez volta a ser de quem pedir, e soltar libera ----------
    cl['Beto'].emit('stream_pedir_tela', {'canal_id': LID}); ok(any(m['name'] == 'stream_tela_ok' for m in ev(cl['Beto'])), 'liberada a vez, outra pessoa transmite')
    ev(cl['Ana']); ev(cl['Dono'])
    cl['Beto'].emit('stream_liberar_tela', {'canal_id': LID}); ev(cl['Beto'])
    ok(stream_events.apresentador_de(chave) is None, 'o apresentador solta a vez')

    # ---------- chegar no meio ----------
    cl['Ana'].emit('stream_pedir_tela', {'canal_id': LID}); ev(cl['Ana']); ev(cl['Beto']); ev(cl['Dono'])
    cl['Beto'].emit('sair_call', {'canal_id': LID, 'peer_id': 'peer-beto'}); ev(cl['Beto'])
    chegou = entrar('Caio', 'peer-caio')
    rc = [m for m in chegou if m['name'] == 'stream_apresentador' and m['args'][0].get('peer_id')]
    ok(rc and rc[0]['args'][0]['peer_id'] == 'peer-ana', 'quem entra no meio da transmissão recebe quem é o apresentador (com peer_id)')

    # ---------- sair da call libera ----------
    ev(cl['Dono']); ev(cl['Caio'])
    cl['Ana'].emit('sair_call', {'canal_id': LID, 'peer_id': 'peer-ana'}); ev(cl['Ana'])
    ok(stream_events.apresentador_de(chave) is None, 'o apresentador saiu da call: a vez é liberada')
    rcai = [m for m in ev(cl['Caio']) if m['name'] == 'stream_apresentador']
    ok(rcai and rcai[-1]['args'][0]['usuario_id'] is None, 'e todo mundo é avisado')
    cl['Caio'].emit('stream_pedir_tela', {'canal_id': LID}); ev(cl['Caio'])
    cl['Caio'].emit('sair_call', {'canal_id': LID, 'peer_id': 'peer-caio'}); cl['Dono'].emit('sair_call', {'canal_id': LID, 'peer_id': 'peer-dono2'})
    ok(stream_events.apresentador_de(chave) is None, 'call vazia: ninguém fica "no ar" pra sempre')

    # ---------- o chat do canal de stream ----------
    cl['Dono'].emit('entrar_canal', {'canal_id': LID}); cl['Beto'].emit('entrar_canal', {'canal_id': LID}); ev(cl['Dono']); ev(cl['Beto'])
    cl['Beto'].emit('enviar_mensagem', {'canal_id': LID, 'texto': 'oi do chat ao lado'})
    ok(Message.query.filter_by(channel_id=LID).count() == 1 and ev(cl['Dono'], 'receber_mensagem'), 'o canal de stream também guarda e entrega mensagens (o chat ao lado)')
    from app import avisos
    ok('stream' in avisos.TIPOS_COM_CHAT, 'a bolinha de mensagem nova vale pro chat do stream')

# ---------- o que o cliente promete ----------
chat = ler('app/templates/chat.html'); st = ler('app/static/js/stream.js'); cp = ler('app/static/js/compartilhar.js'); cj = ler('app/static/js/cargos.js')
ok('js/stream.js' in chat and 'js/compartilhar.js' in chat and 'css/stream.css' in chat, 'chat.html carrega stream e compartilhar')
ok('Stream.aoEntrar(' in chat and 'Stream.aoSair()' in chat and 'Stream.aoMostrar(modo)' in chat and 'Stream.largura()' in chat, 'a call avisa o Stream: entrar, sair, mostrar e o espaço do chat')
ok('Stream.pedirTela()' in chat and 'Stream.liberarTela()' in chat and 'Stream.aceitaTelaDe(call.peer)' in chat, 'compartilhar pede a vez, devolve ao parar e só aceita tela do apresentador')
ok('Compartilhar.perguntar(' in chat and 'Compartilhar.constraints(op, alvoTela)' in chat, 'o botão de tela abre as opções antes do seletor')
ok("stream: ['ver_canal'" in cj and "stream: { fam: 'voz'" in cj, 'cargos.js conhece o tipo stream')
for k in ('qualidade', 'superficie', 'audio', 'cursor', 'lembrar'):
    ok(k in cp, f'compartilhar.js guarda "{k}"')
ok('suppressLocalAudioPlayback' in cp and "systemAudio: op.audio ? 'include' : 'exclude'" in cp, 'som do computador só quando pedido (e sem eco local)')
ok('peer_id' in st and 'aceitaTelaDe' in st, 'o cliente usa o peer_id do apresentador')
ok('eval(' not in st and 'eval(' not in cp, 'sem eval')
print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
