import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Server, Friendship, DirectMessage, GeoNote, br_now
from datetime import timedelta

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def eventos(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ps = {}
    for n in ('Ana', 'Beto', 'Caio'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); ps[n] = p
    db.session.commit()
    ids = {n: p.id for n, p in ps.items()}

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc)
        cl.get_received()
        return cl

    ana, beto, caio = cliente('Ana'), cliente('Beto'), cliente('Caio')

    # ---------- AMIZADE ----------
    ana.emit('enviar_pedido_amizade', {'busca': '@beto'})
    ra = eventos(ana); rb = eventos(beto)
    ok(any(m['name'] == 'pedido_amizade_enviado' for m in ra), 'Ana recebe confirmacao de pedido enviado')
    ok(any(m['name'] == 'pedido_amizade_recebido' for m in rb), 'Beto recebe pedido_amizade_recebido')
    snap_b = [m for m in rb if m['name'] == 'amizades'][-1]['args'][0]
    snap_a = [m for m in ra if m['name'] == 'amizades'][-1]['args'][0]
    ok(len(snap_b['pedidos']) == 1 and snap_b['pedidos'][0]['direcao'] == 'recebido', 'Beto ve pedido RECEBIDO')
    ok(len(snap_a['pedidos']) == 1 and snap_a['pedidos'][0]['direcao'] == 'enviado', 'Ana ve pedido ENVIADO (aguardando)')
    ok(any(m['name'] == 'notificacao_nova' for m in rb), 'Beto ganha notificacao na caixa de entrada')
    pid = snap_b['pedidos'][0]['pedido_id']

    # quem enviou nao pode aceitar o proprio pedido
    ana.emit('responder_pedido_amizade', {'pedido_id': pid, 'acao': 'aceitar'})
    eventos(ana)
    ok(Friendship.query.get(pid).status == 'pending', 'Quem enviou NAO consegue aceitar o proprio pedido')

    # DM durante o pedido pendente
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'oi beto', 'temp_id': 'abc123'})
    rb = eventos(beto)
    ok(any(m['name'] == 'receber_mensagem_direta' for m in rb), 'DM chega com pedido pendente')
    nots = [m for m in rb if m['name'] == 'notificacao_nova']
    ok(any(n['args'][0]['tipo'] == 'dm' for n in nots), 'DM gera notificacao agrupada')
    eventos(ana)

    # Caio (sem relacao nem servidor em comum) nao pode mandar DM
    caio.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'oi'})
    rc = eventos(caio)
    ok(any(m['name'] == 'erro_bazinga' for m in rc), 'Estranho sem servidor/amizade NAO manda DM')

    # anexo invalido eh descartado, valido passa
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': '', 'anexo_url': 'https://evil.com/x.png', 'anexo_tipo': 'image'})
    ok(not any(m['name'] == 'receber_mensagem_direta' for m in eventos(beto)), 'DM so com anexo externo invalido eh ignorada')
    eventos(ana)
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': '', 'anexo_url': 'https://res.cloudinary.com/x/a.png', 'anexo_tipo': 'image'})
    rb = eventos(beto)
    ok(any(m['name'] == 'receber_mensagem_direta' and m['args'][0]['anexo_url'] for m in rb), 'DM so com anexo cloudinary passa')
    eventos(ana)

    # nao lidas
    beto.emit('marcar_dm_lida', {'amigo_id': ids['Ana']})
    ok(any(m['name'] == 'dm_lidas' for m in eventos(beto)), 'marcar_dm_lida responde')
    ok(DirectMessage.query.filter_by(receiver_id=ids['Beto'], lida=False).count() == 0, 'Todas as DMs ficaram lidas')

    # Beto aceita
    beto.emit('responder_pedido_amizade', {'pedido_id': pid, 'acao': 'aceitar'})
    ra = eventos(ana); rb = eventos(beto)
    ok(Friendship.query.get(pid).status == 'accepted', 'Beto aceitou')
    ok(any(m['name'] == 'amizades' and len(m['args'][0]['amigos']) == 1 for m in ra), 'Ana ve Beto como amigo na hora (regra 6)')

    # bloquear
    beto.emit('bloquear_usuario', {'usuario_id': ids['Ana']})
    eventos(beto); eventos(ana)
    ok(Friendship.query.get(pid).status == 'blocked' and Friendship.query.get(pid).requester_id == ids['Beto'], 'Bloqueio grava o bloqueador como requester')
    ana.emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'texto': 'oi?'})
    ok(any(m['name'] == 'erro_bazinga' for m in eventos(ana)), 'Bloqueado NAO manda DM')
    ana.emit('enviar_pedido_amizade', {'busca': '@beto'})
    ok(any(m['name'] == 'erro_bazinga' for m in eventos(ana)), 'Bloqueado NAO consegue novo pedido')
    beto.emit('desbloquear_usuario', {'usuario_id': ids['Ana']})
    eventos(beto); eventos(ana)
    ok(Friendship.query.get(pid) is None, 'Desbloquear apaga a linha')

    # expiracao de 24h
    ana.emit('enviar_pedido_amizade', {'busca': '@caio'}); eventos(ana); eventos(caio)
    f = Friendship.query.filter_by(requester_id=ids['Ana'], addressee_id=ids['Caio']).first()
    f.created_at = br_now() - timedelta(hours=25); db.session.commit()
    caio.emit('listar_amizades'); rc = eventos(caio, 'amizades')
    ok(rc and len(rc[-1]['args'][0]['pedidos']) == 0, 'Pedido de 25h expira sozinho')

    # ---------- MAPA ----------
    ana.emit('mapa_pedir_arredores', {'lat': -15.80, 'lng': -47.90}); eventos(ana)
    beto.emit('mapa_pedir_arredores', {'lat': -15.801, 'lng': -47.901}); eventos(beto)   # perto (~150m)
    caio.emit('mapa_pedir_arredores', {'lat': -23.55, 'lng': -46.63}); eventos(caio)     # longe (SP)
    ana.emit('criar_geonote', {'lat': -15.8005, 'lng': -47.9005, 'texto': 'oi mundo', 'icone': '🍕', 'duracao': 1, 'cor': '#5865F2'})
    ra, rb, rc = eventos(ana), eventos(beto), eventos(caio)
    ok(any(m['name'] == 'nova_geonote' for m in ra), 'Autora recebe a nota')
    ok(any(m['name'] == 'nova_geonote' and m['args'][0]['icone'] == '🍕' for m in rb), 'Quem esta perto recebe a nota (com icone)')
    ok(not any(m['name'] == 'nova_geonote' for m in rc), 'Quem esta longe NAO recebe a nota (privacidade)')
    nota = GeoNote.query.first()
    ok(nota.expires_at is not None, 'Nota tem expires_at')
    # fora do alcance
    ana.emit('criar_geonote', {'lat': -23.55, 'lng': -46.63, 'texto': 'longe'})
    ok(any(m['name'] == 'erro_bazinga' for m in eventos(ana)), 'Nota fora do alcance eh recusada')
    # arredores
    caio.emit('mapa_pedir_arredores', {'lat': -15.80, 'lng': -47.90})
    d = [m for m in eventos(caio) if m['name'] == 'mapa_arredores'][-1]['args'][0]
    ok(len(d['notas']) == 1 and d['notas'][0]['restante_s'] > 3000, 'Arredores devolve a nota com tempo restante')
    # expirada some
    nota.expires_at = br_now() - timedelta(minutes=1); db.session.commit()
    caio.emit('mapa_pedir_arredores', {'lat': -15.80, 'lng': -47.90})
    d = [m for m in eventos(caio) if m['name'] == 'mapa_arredores'][-1]['args'][0]
    ok(len(d['notas']) == 0, 'Nota expirada nao aparece')
    nota.expires_at = br_now() + timedelta(hours=1); db.session.commit()
    # copiar
    beto.emit('copiar_geonote', {'id': nota.id, 'lat': -15.8012, 'lng': -47.9012})
    rb = eventos(beto)
    ok(any(m['name'] == 'nota_copiada' for m in rb), 'Beto copia a nota pro proprio alcance')
    ok(GeoNote.query.filter_by(author_id=ids['Beto']).count() == 1, 'Copia pertence ao Beto')
    # denunciar: 3 pessoas escondem
    ana_nota_id = nota.id
    for n in ('Beto', 'Caio'):
        pass
    beto.emit('denunciar', {'tipo': 'nota', 'id': ana_nota_id, 'motivo': '+18'}); eventos(beto)
    caio.emit('denunciar', {'tipo': 'nota', 'id': ana_nota_id, 'motivo': '+18'}); eventos(caio)
    ok(not GeoNote.query.get(ana_nota_id).oculta, '2 denuncias ainda nao escondem')
    ana.emit('denunciar', {'tipo': 'nota', 'id': ana_nota_id, 'motivo': 'spam'})
    ok(any(m['name'] == 'erro_bazinga' for m in eventos(ana)), 'Nao pode denunciar o proprio conteudo')
    # terceira denuncia: cria um quarto usuario
    p4 = Person(name='Dani', email='d@x', role_id=r.id, username='dani'); db.session.add(p4); db.session.commit(); ids['Dani'] = p4.id
    dani = cliente('Dani')
    dani.emit('denunciar', {'tipo': 'nota', 'id': ana_nota_id, 'motivo': 'ilegal'})
    rd = eventos(dani)
    ok(GeoNote.query.get(ana_nota_id).oculta, '3 denuncias escondem a nota')
    beto.emit('denunciar', {'tipo': 'nota', 'id': ana_nota_id, 'motivo': '+18'})
    ok(any(m['name'] == 'denuncia_registrada' and m['args'][0].get('repetida') for m in eventos(beto)), 'Denuncia repetida eh tratada')

    # ---------- PERFIL ----------
    ana.emit('atualizar_perfil', {'name': 'Ana', 'banner_url': 'https://media2.giphy.com/media/x/200.gif', 'banner_ajuste': '-0.2,-0.1,1.5,0,0',
                                  'perfil_tema': 'img:https://res.cloudinary.com/a/b.gif|0,0,1,0,0'})
    pa = [m for m in eventos(ana) if m['name'] == 'perfil_atualizado'][-1]['args'][0]
    ok(pa['banner_url'].startswith('https://media2.giphy.com/') and pa['banner_ajuste'] == '-0.2,-0.1,1.5,0,0', 'Faixa GIF do Giphy + ajuste salvam')
    ok(pa['perfil_tema'].startswith('img:https://res.cloudinary.com/'), 'Tema com imagem + ajuste salva')
    ana.emit('atualizar_perfil', {'name': 'Ana', 'banner_ajuste': 'javascript:alert(1)'})
    pa = [m for m in eventos(ana) if m['name'] == 'perfil_atualizado'][-1]['args'][0]
    ok(pa['banner_ajuste'] is None, 'Ajuste invalido eh descartado')

print()
print('FALHAS:', falhas if falhas else 'nenhuma')
