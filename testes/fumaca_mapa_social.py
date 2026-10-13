"""Rodada 24: mapa social. Radar de pessoas por perto (privacidade: os dois lados ligam, anônimo, aproximado, Fantasma/localização/bloqueio/
amigo/servidor em comum fora, freio de pedido), prévia de servidor plantado (alcance, oculto, lotado, nada privado) e os arquivos do cliente."""
import os, sys, re, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import events
from app.models import Role, Person, Friendship, Server, Channel, MapServer, Message, br_now
from app.utils import distancia_m

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')
LAT, LNG = -15.8745, -48.0999


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


def erros(cli):
    return [m['args'][0]['msg'] for m in ev(cli, 'erro_bazinga')]


def deslocar(dm_norte, dm_leste):
    """(lat, lng) a tantos metros ao norte/leste de LAT, LNG."""
    from math import cos, radians
    return LAT + dm_norte / 111000.0, LNG + dm_leste / (111000.0 * cos(radians(LAT)))


with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio', 'Duda', 'Eli', 'Fabi', 'Gil', 'Hana'):
        p = Person(name=n, email=f'{n.lower()}@x', role_id=r.id, username=n.lower(), bazinga_coins=0)
        db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))      # amigo: já tem pino
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Gil'], status='blocked'))       # Ana bloqueou o Gil
    db.session.commit()
    srv_comum = Server(name='Comum', owner_id=ids['Ana']); db.session.add(srv_comum); db.session.commit()
    srv_comum.members.append(db.session.get(Person, ids['Ana'])); srv_comum.members.append(db.session.get(Person, ids['Hana'])); db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc)

    def radar(cli):
        events._radar_ts.clear()   # o freio é por aba; cada pergunta do teste começa livre
        ev(cli); cli.emit('mapa_radar_pedir', {})
        m = ev(cli, 'mapa_radar')
        return m[-1]['args'][0] if m else None

    def pos(nome, dn, dl, radar_on):
        la, ln = deslocar(dn, dl)
        events.ultimas_posicoes[ids[nome]] = {'usuario_id': ids[nome], 'nome': nome, 'avatar': None, 'lat': la, 'lng': ln, '_t': time.time(), '_radar': radar_on}

    ana = cliente('Ana'); ev(ana)
    ana.emit('atualizar_localizacao', {'lat': LAT, 'lng': LNG, 'fonte': 'aparelho'}); ev(ana)

    # ---------- 1. a opção na conta ----------
    pref = ev(cliente('Beto'), 'preferencias_carregadas')
    ok(pref and pref[-1]['args'][0].get('radar_estranhos') is False, 'conta nova: radar de pessoas DESLIGADO (padrão)')
    ok(radar(ana)['ativo'] is False and radar(ana)['motivo'] == 'desligado', 'desligado: o servidor não entrega nada (motivo "desligado")')

    ana2 = cliente('Ana'); ev(ana2)     # 2ª aba da mesma conta
    ana.emit('alternar_radar_estranhos', {'ativo': True})
    a1 = ev(ana, 'preferencias_carregadas'); a2 = ev(ana2, 'preferencias_carregadas')
    ok(a1 and a1[-1]['args'][0]['radar_estranhos'] is True, 'ligar: a aba que clicou recebe a confirmação')
    ok(a2 and a2[-1]['args'][0]['radar_estranhos'] is True, 'regra 6: a OUTRA aba da mesma conta também acompanha')
    ok(db.session.get(Person, ids['Ana']).radar_estranhos is True, 'fica salvo na conta')
    ok(events.ultimas_posicoes[ids['Ana']]['_radar'] is True, 'quem já estava no mapa passa a valer pro radar na hora')

    # ---------- 2. quem aparece ----------
    pos('Caio', 600, 300, True)        # estranho, ligou, a ~670 m  -> aparece
    pos('Duda', -900, -700, True)      # estranho, ligou, a ~1,1 km -> aparece
    pos('Eli', 400, 100, False)        # estranho, NÃO ligou        -> não aparece (reciprocidade)
    pos('Fabi', 3000, 0, True)         # ligou mas está a 3 km (fora do círculo pequeno)
    pos('Beto', 200, 200, True)        # amigo: já tem pino
    pos('Hana', 300, -300, True)       # mesmo servidor: já tem pino
    pos('Gil', -200, 400, True)        # Ana bloqueou
    d = radar(ana)
    ok(d and d['ativo'] is True, 'ligado e com posição do aparelho: o radar responde')
    ok(len(d['blips']) == 2, f'só os 2 estranhos que ligaram, dentro de 2 km e sem bloqueio ({len(d["blips"])})')
    ok(all(set(b.keys()) == {'lat', 'lng'} for b in d['blips']) and set(d.keys()) <= {'ativo', 'blips', 'grade_m'}, 'o sinal é ANÔNIMO: só lat/lng, sem id, nome nem foto')
    reais = [deslocar(600, 300), deslocar(-900, -700)]
    desvios = [min(distancia_m(b['lat'], b['lng'], rl, rg) for rl, rg in reais) for b in d['blips']]
    ok(all(dv < 300 for dv in desvios), f'a posição é aproximada, mas perto da verdadeira (desvio até {max(desvios):.0f} m)')
    ok(all(not (abs(b['lat'] - rl) < 1e-6 and abs(b['lng'] - rg) < 1e-6) for b in d['blips'] for rl, rg in reais), 'nunca devolve o ponto exato')
    amostras = set()
    for _ in range(12):
        for b in radar(ana)['blips']:
            amostras.add((b['lat'], b['lng']))
    ok(len(amostras) > 2, 'o ruído é refeito a cada pedido (não dá pra cravar o ponto repetindo)')

    # ---------- 3. travas ----------
    for nome in ('Caio', 'Duda'):
        events.ultimas_posicoes[ids[nome]]['_t'] = time.time() - 400
    ok(radar(ana)['blips'] == [], 'sinal velho (> 3 min) não aparece')
    pos('Caio', 600, 300, True)
    ana.emit('alternar_fantasma', {'ativo': True}); ev(ana)
    d = radar(ana)
    ok(d['ativo'] is False and d['motivo'] == 'fantasma' and d['blips'] == [], 'Modo Fantasma: quem quer VER precisa poder ser VISTO (pausado)')
    ana.emit('alternar_fantasma', {'ativo': False}); ev(ana)
    caio = cliente('Caio'); ev(caio)
    caio.emit('atualizar_localizacao', {'lat': deslocar(600, 300)[0], 'lng': deslocar(600, 300)[1], 'fonte': 'aparelho'}); ev(caio)
    caio.emit('alternar_radar_estranhos', {'ativo': True}); ev(caio)
    ok(len(radar(ana)['blips']) >= 1, 'o Caio (que ligou e tem posição de aparelho) aparece')
    caio.emit('alternar_fantasma', {'ativo': True}); ev(caio)
    ok(ids['Caio'] not in events.ultimas_posicoes, 'Caio em Modo Fantasma: a posição nem fica guardada, ele não aparece')
    caio.emit('alternar_fantasma', {'ativo': False}); caio.emit('alternar_localizacao', {'ativa': False}); ev(caio)
    ok(ids['Caio'] not in events.ultimas_posicoes, 'Caio com a localização desligada: não aparece')
    ana.emit('alternar_localizacao', {'ativa': False}); ev(ana)
    d = radar(ana)
    ok(d['ativo'] is False and d['motivo'] == 'sem_localizacao', 'localização desligada: o radar pausa')
    ana.emit('alternar_localizacao', {'ativa': True}); ev(ana)
    events.fontes_mapa[list(events.fontes_mapa.keys())[0]] = 'ip'
    ana.emit('atualizar_localizacao', {'lat': LAT, 'lng': LNG, 'fonte': 'ip'}); ev(ana)
    d = radar(ana)
    ok(d['ativo'] is False and d['motivo'] == 'sem_posicao', 'posição só por IP não vale pro radar (precisa do aparelho)')
    ana.emit('atualizar_localizacao', {'lat': LAT, 'lng': LNG, 'fonte': 'aparelho'}); ev(ana)
    ana.emit('mapa_radar_pedir', {}); ev(ana)
    ana.emit('mapa_radar_pedir', {})
    ok(not ev(ana, 'mapa_radar'), 'freio: dois pedidos seguidos na mesma aba, o 2º é ignorado')
    ana.emit('alternar_radar_estranhos', {'ativo': False}); ev(ana)
    ok(radar(ana)['motivo'] == 'desligado', 'desligar volta ao padrão (nada entregue)')

    # ---------- 4. prévia de servidor plantado ----------
    ana.emit('alternar_radar_estranhos', {'ativo': False}); ev(ana)
    dono = db.session.get(Person, ids['Duda'])
    def plantar(nome, dn, dl, vagas=None, oculta=False, expira=None, membros_extras=0, privado=False):
        sv = Server(name=nome, owner_id=dono.id, description='Descrição pública do servidor ' + nome)
        db.session.add(sv); db.session.commit()
        sv.members.append(dono)
        for i in range(membros_extras):
            q = Person(name=f'x{nome}{i}', email=f'x{nome}{i}@x', role_id=r.id, username=f'x{nome[:3].lower()}{i}'); db.session.add(q); db.session.commit(); sv.members.append(q)
        db.session.add(Channel(name='geral', server_id=sv.id, channel_type='text'))
        db.session.add(Channel(name='segredo', server_id=sv.id, channel_type='text', is_private=True))
        db.session.commit()
        la, ln = deslocar(dn, dl)
        db.session.add(MapServer(name=nome, server_id=sv.id, owner_id=dono.id, lat=la, lng=ln, max_tickets=vagas, oculta=oculta, expires_at=expira)); db.session.commit()
        return sv
    perto = plantar('Perto', 3000, 1000)
    longe = plantar('Longe', 40000, 0)
    escondido = plantar('Escondido', 500, 500, oculta=True)
    vencido = plantar('Vencido', 500, -500, expira=br_now().replace(year=2020))
    lotado = plantar('Lotado', 1500, 0, vagas=3, membros_extras=2)
    solto = Server(name='NaoPlantado', owner_id=dono.id, description='x'); db.session.add(solto); db.session.commit()
    ev(ana)
    ana.emit('mapa_servidor_previa', {'server_id': perto.id})
    p = ev(ana, 'mapa_servidor_previa')
    ok(p and p[-1]['args'][0]['nome'] == 'Perto', 'servidor plantado dentro do alcance: a prévia abre')
    pj = p[-1]['args'][0] if p else {}
    ok(pj.get('canais') == ['geral'] and 'segredo' not in str(pj), 'a prévia mostra só canal de texto ABERTO (nunca o privado)')
    ok(not any(k in pj for k in ('mensagens', 'membros_lista', 'email')) and 'pino' in pj, 'sem mensagens, sem lista de membros, sem e-mail')
    ok(pj.get('pino', {}).get('lotado') is False and pj['pino']['vagas'] is None, 'sem limite de vagas: não está lotado')
    ana.emit('mapa_servidor_previa', {'server_id': lotado.id})
    pj = ev(ana, 'mapa_servidor_previa')[-1]['args'][0]
    ok(pj['pino']['lotado'] is True and pj['pino']['vagas'] == 3, 'servidor lotado: a prévia avisa (3/3)')
    for srv, motivo in ((longe, 'fora do alcance (40 km)'), (escondido, 'oculto por denúncia'), (vencido, 'vencido'), (solto, 'não plantado no mapa')):
        ev(ana); ana.emit('mapa_servidor_previa', {'server_id': srv.id})
        rec = ana.get_received()
        ok(not [m for m in rec if m['name'] == 'mapa_servidor_previa'] and any(m['name'] == 'erro_bazinga' for m in rec), f'prévia recusada com aviso: {motivo}')
    ana.emit('mapa_servidor_previa', {'server_id': 'abc'}); ok(not ev(ana, 'mapa_servidor_previa'), 'id inválido não derruba nada')
    ana.emit('alternar_localizacao', {'ativa': False}); ev(ana)
    ana.emit('mapa_servidor_previa', {'server_id': perto.id})
    ok(any('localização' in m for m in erros(ana)), 'localização desligada: sem prévia do mapa')
    ana.emit('alternar_localizacao', {'ativa': True}); ev(ana)

    # o Explorar continua recusando servidor não público (a liberação só vale com o alcance conferido)
    from app import explorar
    try:
        explorar.previa(db.session.get(Person, ids['Ana']), perto.id)
        ok(False, 'Explorar: servidor não público segue sem prévia')
    except explorar.ErroExplorar:
        db.session.rollback(); ok(True, 'Explorar: servidor não público segue sem prévia (só o mapa libera, depois de conferir o alcance)')

    # ---------- 5. cliente ----------
    js = open(os.path.join(RAIZ, 'static', 'js', 'mapa_social.js'), encoding='utf-8').read()
    html = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
    exp = open(os.path.join(RAIZ, 'static', 'js', 'explorar.js'), encoding='utf-8').read()
    ok(re.search(r'(?<!\w)eval\(|document\.write', js) is None, 'mapa_social.js sem eval/document.write')
    ok(js.count('ctx.esc(') >= 6 and 'ctx.escUrl(' in js, 'mapa_social.js escapa nome/avatar/servidor antes do innerHTML')
    ok('btn-mapa-amigos' in html and 'btn-mapa-servidores' in html and 'js/mapa_social.js' in html and 'css/mapa_social.css' in html, 'chat.html tem os 2 botões e carrega o módulo')
    ok(len(re.findall(r'class="fab-op"', html)) == 5 and 'data-a="amigos"' in html and 'data-a="servidores"' in html, 'o botão flutuante do celular tem 5 bolinhas')
    ok('data-mc="localizar"' in html and "MapaSocial.localizar" in html, 'o menu do contato tem "Localizar no mapa"')
    ok("socket.on('mapa_radar'" in html and "socket.on('mapa_servidor_previa'" in html and "'alternar_radar_estranhos'" in html, 'o cliente escuta e pede os eventos novos')
    ok('previaMapa' in exp and "ctx.emitir('explorar_entrar'" in exp, 'Explorar ganhou a prévia avulsa do mapa sem perder a dele')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
