"""Localização na conta: desligada barra comprar, plantar, nota, copiar nota, entrar por pino e o radar (nos dois sentidos);
ligada tudo volta; reserva por IP (só com a localização e o IP permitidos); regra 6: quem via o pino vê ele sumir."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import events
from app.main import routes as rotas
from app.models import Role, Person, Friendship, Product, Server

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


def erros(cli):
    return [m['args'][0]['msg'] for m in ev(cli, 'erro_bazinga')]


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower(), bazinga_coins=5000)
        db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))
    prod = Product(name='Anel', price_bzc=100, is_official=True); db.session.add(prod); db.session.commit()
    prod_id = prod.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc), fc

    ana, fana = cliente('Ana')
    beto, fbeto = cliente('Beto')
    rec = ev(ana, 'preferencias_carregadas')
    ok(rec and rec[-1]['args'][0].get('localizacao_ativa') is True, 'conta nova nasce com a localização LIGADA (NULL = ligada)')
    ev(beto)

    # servidor da Ana pra plantar
    ana.emit('criar_servidor_discord', {'nome': 'Casa'}); ev(ana)
    srv = Server.query.filter_by(name='Casa').first()
    ana.emit('atualizar_localizacao', {'lat': -15.8, 'lng': -47.9}); ev(ana)
    beto.emit('atualizar_localizacao', {'lat': -15.8001, 'lng': -47.9001}); ev(beto)
    ok(ids['Beto'] in events.ultimas_posicoes, 'ligada: a posição do Beto fica no radar')

    # ---- DESLIGA (Ana) ----
    ana.emit('alternar_localizacao', {'ativa': False})
    pref = ev(ana, 'preferencias_carregadas')
    ok(pref and pref[-1]['args'][0]['localizacao_ativa'] is False, 'servidor confirma: localização desligada')
    ok(db.session.get(Person, ids['Ana']).localizacao_ativa is False, 'fica salva na conta')

    ana.emit('criar_geonote', {'lat': -15.8, 'lng': -47.9, 'texto': 'oi'})
    ok(any('localização' in m for m in erros(ana)), 'desligada: NÃO cria nota')
    ana.emit('plantar_servidor', {'lat': -15.8, 'lng': -47.9, 'server_id': srv.id})
    ok(any('localização' in m for m in erros(ana)), 'desligada: NÃO planta servidor')
    ana.emit('copiar_geonote', {'id': 1})
    ok(any('localização' in m for m in erros(ana)), 'desligada: NÃO copia nota')
    ana.emit('entrar_servidor_pin', {'server_id': srv.id})
    ok(any('localização' in m for m in erros(ana)), 'desligada: NÃO entra por pino')
    resp = fana.post(f'/api/produtos/{prod_id}/comprar')
    ok(resp.status_code == 403 and 'localização' in resp.get_json()['error'], 'desligada: NÃO compra (403)')
    ok(db.session.get(Person, ids['Ana']).bazinga_coins == 5000, 'e nenhuma moeda foi cobrada')

    # radar nos dois sentidos
    ana.emit('atualizar_localizacao', {'lat': -15.8, 'lng': -47.9}); ev(ana)
    ok(ids['Ana'] not in events.ultimas_posicoes, 'desligada: a posição da Ana não entra no radar')
    ana.emit('mapa_pedir_arredores', {'lat': -15.8, 'lng': -47.9})
    ok(not ev(ana, 'mapa_arredores') and not ev(ana, 'posicao_amigo_atualizada'), 'desligada: ela também não vê o radar nem o mapa ao redor')

    # ---- LIGA de novo ----
    ana.emit('alternar_localizacao', {'ativa': True}); ev(ana)
    ana.emit('atualizar_localizacao', {'lat': -15.8, 'lng': -47.9}); ev(ana)
    ok(ids['Ana'] in events.ultimas_posicoes, 'ligada de novo: volta pro radar')
    ana.emit('criar_geonote', {'lat': -15.8, 'lng': -47.9, 'texto': 'oi'})
    ok(not erros(ana), 'ligada de novo: cria nota')
    resp = fana.post(f'/api/produtos/{prod_id}/comprar')
    ok(resp.status_code == 200, 'ligada de novo: compra')

    # ---- regra 6: desligar tira o pino de quem já via ----
    ev(beto)
    ana.emit('alternar_localizacao', {'ativa': False}); ev(ana)
    sumiu = ev(beto, 'posicao_amigo_removida')
    ok(sumiu and sumiu[-1]['args'][0]['usuario_id'] == ids['Ana'], 'regra 6: o Beto vê o pino da Ana sumir na hora')
    ana.emit('alternar_localizacao', {'ativa': True}); ev(ana)

    # ---- plantar / entrar por pino: sem posição, sem pino, longe, perto ----
    caio, fcaio = cliente('Caio'); ev(caio)
    ana.emit('criar_servidor_discord', {'nome': 'Praca'}); ev(ana)
    praca = Server.query.filter_by(name='Praca').first()
    ana.emit('atualizar_localizacao', {'lat': -15.8, 'lng': -47.9}); ev(ana)

    # Caio ainda nunca mandou posição: o servidor não deixa passar mais
    caio.emit('entrar_servidor_pin', {'server_id': srv.id})
    ok(any('não está plantado' in m for m in erros(caio)), 'servidor NÃO plantado: ninguém entra só chutando o id')
    ok(db.session.get(Server, srv.id) and ids['Caio'] not in [m.id for m in srv.members], 'e o Caio não virou membro do servidor não plantado')

    beto.emit('atualizar_localizacao', {'lat': -15.8, 'lng': -47.9}); ev(beto)
    nova = Person(name='Duda', email='duda@x', role_id=r.id, username='duda'); db.session.add(nova); db.session.commit(); ids['Duda'] = nova.id
    duda, fduda = cliente('Duda'); ev(duda)
    duda.emit('plantar_servidor', {'lat': -15.8, 'lng': -47.9, 'server_id': srv.id})
    ok(any('dono' in m for m in erros(duda)), 'só o dono planta (regra de sempre continua)')

    ana2, _f = cliente('Ana'); ev(ana2)   # socket novo da Ana: ainda sem posição enviada
    ana2.emit('plantar_servidor', {'lat': -15.8, 'lng': -47.9, 'server_id': praca.id, 'vagas': 'ilimitado', 'duracao': 'permanente'})
    ok(any('Ainda não sei onde você está' in m for m in erros(ana2)), 'sem posição conhecida: NÃO planta (antes passava de qualquer lugar)')
    ana2.emit('criar_geonote', {'lat': -15.8, 'lng': -47.9, 'texto': 'x'})
    ok(any('Ainda não sei onde você está' in m for m in erros(ana2)), 'sem posição conhecida: NÃO cria nota')

    ana.emit('plantar_servidor', {'lat': -15.8, 'lng': -47.9, 'server_id': praca.id, 'vagas': 'ilimitado', 'duracao': 'permanente'})
    ok(not erros(ana), 'com posição e no alcance: o dono planta')

    caio.emit('atualizar_localizacao', {'lat': -23.55, 'lng': -46.63}); ev(caio)   # São Paulo, ~870 km
    caio.emit('entrar_servidor_pin', {'server_id': praca.id})
    ok(any('longe demais' in m for m in erros(caio)), 'pino plantado mas a 870 km: NÃO entra')
    caio.emit('atualizar_localizacao', {'lat': -15.8005, 'lng': -47.9005}); ev(caio)   # ~70 m do pino
    caio.emit('entrar_servidor_pin', {'server_id': praca.id})
    ok(not erros(caio) and ids['Caio'] in [m.id for m in db.session.get(Server, praca.id).members], 'perto do pino: entra e vira membro')
    from app.models import MapServer
    pino = MapServer.query.filter_by(server_id=praca.id).first()
    pino.oculta = True; db.session.commit()
    outro = Person(name='Edu', email='edu@x', role_id=r.id, username='edu'); db.session.add(outro); db.session.commit(); ids['Edu'] = outro.id
    edu, fedu = cliente('Edu'); ev(edu)
    edu.emit('atualizar_localizacao', {'lat': -15.8, 'lng': -47.9}); ev(edu)
    edu.emit('entrar_servidor_pin', {'server_id': praca.id})
    ok(any('não está plantado' in m for m in erros(edu)), 'pino escondido por denúncia: ninguém novo entra')

    # ---- IP ----
    chamadas = []

    class FakeResp:
        def json(self):
            return {'success': True, 'latitude': -15.79, 'longitude': -47.88, 'city': 'Brasília', 'region': 'Distrito Federal'}

    def fake_get(url, timeout=0):
        chamadas.append(url)
        return FakeResp()
    original = rotas.requests.get
    rotas.requests.get = fake_get
    hdr = {'X-Forwarded-For': '200.100.50.25, 10.0.0.1'}
    resp = fana.get('/api/localizacao/ip', headers=hdr)
    j = resp.get_json()
    ok(resp.status_code == 200 and abs(j['lat'] + 15.79) < 1e-6 and j['lugar'].startswith('Brasília') and j['precisao_m'] >= 5000,
       'IP: devolve posição aproximada com a cidade')
    ok(chamadas and '200.100.50.25' in chamadas[0], 'IP: usou o IP do cliente (1º público do X-Forwarded-For), não o do proxy')
    resp = fana.get('/api/localizacao/ip', headers=hdr)
    ok(resp.status_code == 429, 'IP: pedido repetido em poucos segundos é barrado')
    rotas._ultimo_pedido_ip.clear()
    resp = fana.get('/api/localizacao/ip', headers=hdr)
    ok(resp.status_code == 200 and len(chamadas) == 1, 'IP: segundo pedido sai do cache (não chama o provedor de novo)')
    rotas._ultimo_pedido_ip.clear()
    resp = fana.get('/api/localizacao/ip')   # sem cabeçalho: remote_addr do teste é 127.0.0.1 = não público
    ok(resp.status_code == 422, 'IP: rede local/sem IP público é recusada com explicação')
    ana.emit('alternar_localizacao', {'ip': False}); ev(ana)
    rotas._ultimo_pedido_ip.clear()
    ok(fana.get('/api/localizacao/ip', headers=hdr).status_code == 403, 'IP desligado nas configurações: 403')
    ana.emit('alternar_localizacao', {'ip': True, 'ativa': False}); ev(ana)
    rotas._ultimo_pedido_ip.clear()
    ok(fana.get('/api/localizacao/ip', headers=hdr).status_code == 403, 'localização desligada: IP também 403')
    ok(fbeto.get('/api/localizacao/ip').status_code != 500, 'sem erro 500 pra outra conta')
    rotas.requests.get = original
    anon = app.test_client()
    ok(anon.get('/api/localizacao/ip').status_code == 401, 'sem login: 401')

print('\nFALHAS:' if falhas else '\nTUDO OK', falhas if falhas else '')
sys.exit(1 if falhas else 0)
