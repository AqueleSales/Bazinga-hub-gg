"""Conversa rápida (mensagem pra desconhecido), nome repetido, silenciar, denunciar pessoa,
nota antiga sem prazo e recorte de GIF no servidor."""
import os, sys, io
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from datetime import timedelta
from app import create_app, db, socketio
from app.models import Role, Person, Server, Friendship, DirectMessage, GeoNote, Denuncia, br_now

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n, nome, user in (('Ana', 'Ana', 'ana'), ('Beto', 'Beto', 'beto'), ('Caio', 'Caio', 'caio'), ('Dani', 'Duda', 'duda.a'), ('Dani2', 'Duda', 'duda.b')):
        p = Person(name=nome, email=f'{n}@x', role_id=r.id, username=user); db.session.add(p); db.session.commit(); ids[n] = p.id
    # Ana e Beto dividem um servidor (estranhos entre si, mas se conhecem do servidor)
    srv = Server(name='S', owner_id=ids['Ana']); db.session.add(srv); db.session.flush()
    for n in ('Ana', 'Beto', 'Caio'):
        srv.members.append(Person.query.get(ids[n]))
    db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    ana, fana = cliente('Ana'); beto, fbeto = cliente('Beto'); caio, fcaio = cliente('Caio'); dani, _ = cliente('Dani')

    # ---------- conversa rápida ----------
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'oi, vi seu servidor'})
    ra, rb = ev(ana), ev(beto)
    f = Friendship.query.filter_by(requester_id=ids['Ana'], addressee_id=ids['Beto']).first()
    ok(f is not None and f.rapida and f.status == 'pending', '1ª mensagem pra desconhecido cria a conversa rápida (pendente, rapida)')
    ok(any(m['name'] == 'receber_mensagem_direta' for m in rb), 'Beto recebe a mensagem')
    snap_b = [m for m in rb if m['name'] == 'amizades'][-1]['args'][0]
    ok(len(snap_b['pedidos']) == 1 and snap_b['pedidos'][0]['rapida'] and snap_b['pedidos'][0]['direcao'] == 'recebido', 'Beto vê a conversa rápida como RECEBIDA')
    snap_a = [m for m in ra if m['name'] == 'amizades'][-1]['args'][0]
    ok(len(snap_a['pedidos']) == 1 and snap_a['pedidos'][0]['direcao'] == 'enviado', 'Ana vê como ENVIADA')

    # Ana fecha a conversa: some só pra ela
    pid = f.id
    ana.emit('cancelar_pedido_amizade', {'pedido_id': pid})
    ra, rb = ev(ana, 'amizades'), ev(beto, 'amizades')
    ok(Friendship.query.get(pid) is not None and Friendship.query.get(pid).oculta_req, 'Fechar conversa rápida só esconde do lado de quem puxou')
    ok(ra and len(ra[-1]['args'][0]['pedidos']) == 0, 'Some da lista da Ana')
    ok(rb and len(rb[-1]['args'][0]['pedidos']) == 1, 'Beto continua vendo (pode ler)')

    # Beto aceita; como a Ana tinha fechado, o pedido VOLTA pra ela decidir
    beto.emit('responder_pedido_amizade', {'pedido_id': pid, 'acao': 'aceitar'})
    ra, rb = ev(ana), ev(beto)
    f = Friendship.query.get(pid)
    ok(f.status == 'pending' and f.requester_id == ids['Beto'] and not f.rapida and not f.oculta_req, 'Aceitar depois do "fechar" vira pedido de volta (Beto -> Ana)')
    snap_a = [m for m in ra if m['name'] == 'amizades'][-1]['args'][0]
    ok(len(snap_a['pedidos']) == 1 and snap_a['pedidos'][0]['direcao'] == 'recebido', 'Ana volta a ver a conversa, agora pra decidir')
    ok(DirectMessage.query.count() == 1, 'As mensagens continuam lá')
    ana.emit('responder_pedido_amizade', {'pedido_id': pid, 'acao': 'aceitar'}); ev(ana); ev(beto)
    ok(Friendship.query.get(pid).status == 'accepted', 'Ana aceita: viram amigos')

    # Caio escreve pro Beto; Beto RECUSA: some do lado do Beto, Caio segue vendo; novas msgs não chegam no Beto
    caio.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'e aí'}); ev(caio); ev(beto)
    fc = Friendship.query.filter_by(requester_id=ids['Caio'], addressee_id=ids['Beto']).first()
    # (Beto e Caio dividem servidor, sem relação -> rapida)
    ok(fc is not None and fc.rapida, 'Caio -> Beto também nasce como conversa rápida')
    beto.emit('responder_pedido_amizade', {'pedido_id': fc.id, 'acao': 'recusar'}); ev(beto); ev(caio)
    fc = Friendship.query.get(fc.id)
    ok(fc is not None and fc.oculta_dest, 'Recusar conversa rápida só esconde do lado do Beto')
    caio.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'ei??'})
    ok(not any(m['name'] == 'receber_mensagem_direta' for m in ev(beto)), 'Beto (que recusou) não recebe mais nada dessa conversa')
    ok(not any(m['name'] == 'notificacao_nova' for m in ev(beto)), '...nem notificação')

    # 24h: pedido E mensagens somem
    fc_id = fc.id
    fc = Friendship.query.get(fc_id); fc.created_at = br_now() - timedelta(hours=25); db.session.commit()
    n_antes = DirectMessage.query.filter(DirectMessage.sender_id == ids['Caio']).count()
    caio.emit('listar_amizades'); ev(caio)
    db.session.expire_all()
    ok(Friendship.query.filter_by(id=fc_id).first() is None, 'Passou de 24h: a conversa rápida some')
    ok(DirectMessage.query.filter(DirectMessage.sender_id == ids['Caio']).count() == 0 and n_antes > 0, '...e as mensagens temporárias também')

    # ---------- nome repetido ----------
    ana.emit('enviar_pedido_amizade', {'busca': 'Duda'})
    msg = [m['args'][0]['msg'] for m in ev(ana, 'erro_bazinga')]
    ok(msg and '@duda.a' in msg[0] and '@duda.b' in msg[0], 'Nome de exibição repetido pede o @ (não escolhe qualquer um)')
    ana.emit('enviar_pedido_amizade', {'busca': '@duda.b'})
    ok(any(m['name'] == 'pedido_amizade_enviado' for m in ev(ana)), 'Com o @ funciona')

    # ---------- silenciar ----------
    beto.emit('silenciar_contato', {'alvo_id': ids['Ana'], 'ativo': True})
    snap = [m for m in ev(beto, 'amizades')][-1]['args'][0]
    ok(ids['Ana'] in snap['silenciados'], 'Silenciar entra no retrato das amizades')
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'oi de novo'})
    rb = ev(beto)
    ok(any(m['name'] == 'receber_mensagem_direta' for m in rb) and not any(m['name'] == 'notificacao_nova' for m in rb), 'Silenciado: mensagem chega, mas sem notificação')
    beto.emit('silenciar_contato', {'alvo_id': ids['Ana'], 'ativo': False}); ev(beto)

    # ---------- denunciar pessoa ----------
    beto.emit('denunciar', {'tipo': 'usuario', 'id': ids['Ana'], 'motivo': 'assedio', 'detalhe': 'teste'})
    ok(any(m['name'] == 'denuncia_registrada' for m in ev(beto)) and Denuncia.query.filter_by(tipo='usuario').count() == 1, 'Denunciar pessoa grava a denúncia')
    beto.emit('denunciar', {'tipo': 'usuario', 'id': ids['Beto'], 'motivo': 'spam'})
    ok(any(m['name'] == 'erro_bazinga' for m in ev(beto)), 'Não dá pra se denunciar')

    # ---------- nota antiga sem prazo ----------
    from app.utils import dados_do_mapa_perto
    velha = GeoNote(lat=-15.8, lng=-47.9, text='antiga', author_id=ids['Ana'], expires_at=None, timestamp=br_now() - timedelta(days=5))
    nova = GeoNote(lat=-15.8, lng=-47.9, text='recente sem prazo', author_id=ids['Ana'], expires_at=None, timestamp=br_now() - timedelta(hours=2))
    db.session.add_all([velha, nova]); db.session.commit()
    d = dados_do_mapa_perto(-15.8, -47.9)
    textos = [n['texto'] for n in d['notas']]
    ok('antiga' not in textos and 'recente sem prazo' in textos, 'Nota antiga sem prazo (5 dias) some; a de 2h ainda aparece com contagem')
    ok(all(n['restante_s'] is not None for n in d['notas']), 'Toda nota tem tempo restante')

    # ---------- recorte de GIF ----------
    gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'animacao_teste.gif')
    if os.path.exists(gif_path):
        dados = open(gif_path, 'rb').read()
        resp = fana.post('/api/gif/recortar', data={'file': (io.BytesIO(dados), 'a.gif'), 'formato': 'faixa', 'escala': '1.5', 'ox': '-0.2', 'oy': '-0.1', 'fh': '1'},
                         content_type='multipart/form-data')
        from PIL import Image
        im = Image.open(io.BytesIO(resp.data))
        ok(resp.status_code == 200 and im.size == (816, 260) and getattr(im, 'n_frames', 1) == 3, 'Recorte de GIF mantém a animação (3 quadros) no tamanho da faixa')
        r2 = fana.post('/api/gif/recortar', data={'url': 'https://evil.com/x.gif', 'formato': 'faixa'}, content_type='multipart/form-data')
        ok(r2.status_code in (400, 429), 'Recorte por URL só aceita o CDN do Giphy')
    else:
        print('(pulado: testes/animacao_teste.gif não existe)')

print()
print('FALHAS:', falhas if falhas else 'nenhuma')
