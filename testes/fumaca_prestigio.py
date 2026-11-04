"""Prestígio (impulso) de servidor, Rodada 35: pontos e níveis, quem pode impulsionar (membro + Brasa ativa, limite por pessoa, um por servidor), Brasa vencida não conta,
sair do servidor tira o impulso, regra 6 (nível novo chega a todo membro e a todas as abas), alcance do PINO no mapa (nunca notas/lojas/pessoas), posição arredondada de longe,
prévia de longe sem poder entrar, retirada quando o alcance encolhe, mais cargos, barquinho do Explorar, custo de consultas e o que o cliente promete."""
import os, sys, re
from datetime import timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
for k in ('RENDER', 'PAGAMENTOS', 'ASAAS_API_KEY'):
    os.environ.pop(k, None)
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from sqlalchemy import event
from app import create_app, db, socketio, prestigio, prestigio_events, explorar, cargos
from app.models import Role, Person, Server, Channel, MapServer, ServerBoost, GeoNote, ServerRole, br_now
from app.utils import RAIO_SERVIDORES_M, dados_do_mapa_perto, distancia_m

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cl, nome=None):
    return [m for m in cl.get_received() if nome is None or m['name'] == nome]


def ler(*partes):
    return open(os.path.join(RAIZ, *partes), encoding='utf-8').read()


PINO = (-15.8034, -47.9047)       # fora da grade de 0,01°, pra o arredondamento aparecer
PERTO = (-15.8090, -47.9000)       # ~1 km
A_40KM = (-15.4400, -47.9000)      # ~40 km
A_300KM = (-18.5000, -47.9000)     # ~300 km
A_1000KM = (-24.8000, -47.9000)    # ~1000 km

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}

    def nova(nome, brasa=False):
        p = Person(name=nome, email=f'{nome.lower()}@x', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=30),
                   olimpo_ate=(br_now() + timedelta(days=10)) if brasa else None)
        db.session.add(p); db.session.commit(); ids[nome.lower()] = p.id
        return p

    for n in ('Dono',):
        nova(n, brasa=True)
    nova('Ana', brasa=True)          # membro com Brasa
    nova('Beto')                     # membro SEM Brasa
    nova('Cris', brasa=True)         # tem Brasa mas NÃO é membro
    nova('Longe')                    # só olha o mapa de longe
    boosters = [nova(f'Bo{i}', brasa=True) for i in range(20)]

    srv = Server(name='Praça', owner_id=ids['dono'], description='Uma comunidade legal pra conversar todo dia.')
    db.session.add(srv); db.session.commit()
    for n in ('dono', 'ana', 'beto'):
        srv.members.append(db.session.get(Person, ids[n]))
    for b in boosters:
        srv.members.append(b)
    db.session.add(Channel(name='geral', server_id=srv.id, channel_type='text')); db.session.commit()
    SID = srv.id
    # servidor pequeno de outro dono (pra testar limite por pessoa e o alheio)
    outro = Server(name='Outro', owner_id=ids['cris']); db.session.add(outro); db.session.commit()
    outro.members.append(db.session.get(Person, ids['cris'])); outro.members.append(db.session.get(Person, ids['ana'])); db.session.commit()
    OUTRO = outro.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl

    def emitir(cl, nome, dados=None):
        prestigio_events._ultimo.clear()
        cl.emit(nome, dados or {})
        return ev(cl)

    def msg_erro(rec):
        return next((m['args'][0]['msg'] for m in rec if m['name'] in ('prestigio_erro', 'erro_bazinga')), None)

    def estado(rec):
        return next((m['args'][0] for m in rec if m['name'] == 'prestigio_estado'), None)

    def boosts(n, srv_id=SID):
        """Deixa o servidor com exatamente `n` impulsos de gente com Brasa (direto no banco: aqui o que interessa é o NÍVEL)."""
        ServerBoost.query.filter_by(server_id=srv_id).delete()
        for b in boosters[:n]:
            db.session.add(ServerBoost(server_id=srv_id, person_id=b.id))
        db.session.commit()
        prestigio.invalidar()

    # ---------------- 1. contas puras ----------------
    ok(prestigio.pontos_de(0, 0) == 0 and prestigio.pontos_de(2, 10) == 12 and prestigio.pontos_de(0, 1000) == 20, 'pontos: 5 por impulso e 1 a cada 5 membros (até 100)')
    ok([prestigio.nivel_de(p) for p in (0, 9, 10, 29, 30, 59, 60, 99, 100, 5000)] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4], 'os níveis começam nos pontos certos (10, 30, 60, 100)')
    ok(prestigio.nivel_de(prestigio.pontos_de(0, 100000)) == 1, 'só tamanho dá no máximo o nível 1: do 2 em diante precisa de impulso')
    ok(prestigio.alcance_m(0) == RAIO_SERVIDORES_M and all(a < b for a, b in zip(prestigio.ALCANCE_M, prestigio.ALCANCE_M[1:])), 'o nível 0 é o raio de sempre e o alcance só cresce')
    ok(len(prestigio.NOMES) == len(prestigio.LIMITES_PONTOS) == len(prestigio.ALCANCE_M) == len(prestigio.CARGOS_EXTRA) == len(prestigio.PORTE_MIN) == 5, 'as 5 tabelas têm o mesmo tamanho')
    ok(prestigio.alcance_m(99) == prestigio.ALCANCE_M[-1] and prestigio.alcance_m(-3) == RAIO_SERVIDORES_M and prestigio.alcance_m(None) == RAIO_SERVIDORES_M, 'nível fora da faixa não estoura')
    ok(prestigio.ALCANCE_M[-1] >= 20_000_000, 'o nível 4 enxerga o servidor do outro lado do mundo')
    la, ln = prestigio.aproximar(-15.80123, -47.90456)
    ok(abs(la - (-15.8)) < 0.006 and abs(ln - (-47.9)) < 0.006 and distancia_m(-15.80123, -47.90456, la, ln) < 1000, 'aproximar: arredonda a ~1 km')
    ok(prestigio.aproximar(la, ln) == (la, ln), '...e arredondar duas vezes dá o mesmo ponto')

    dono, ana, beto, cris, longe = (cliente(n) for n in ('dono', 'ana', 'beto', 'cris', 'longe'))
    ana2 = cliente('ana')            # a segunda aba da Ana

    # ---------------- 2. quem pode impulsionar ----------------
    rec = emitir(ana, 'prestigio_pedir', {'server_id': SID})
    e = estado(rec)
    ok(e and e['nivel'] == 0 and e['impulsos'] == 0 and e['meus_total'] == 2 and e['brasa_ativa'], 'membro abre o estado: nível 0, 2 impulsos disponíveis, Brasa ativa')
    ok(len(e['tabela']) == 5 and e['tabela'][2]['alcance_m'] == 100_000, 'a tabela de níveis vai junto (a tela não tem cópia própria)')
    ok(e['nivel'] == prestigio.nivel_de(e['pontos']), 'o nível do estado bate com os pontos')
    ok('não encontrado' in (msg_erro(emitir(cris, 'prestigio_pedir', {'server_id': SID})) or ''), 'quem NÃO é membro não abre o estado')
    ok('não encontrado' in (msg_erro(emitir(cris, 'prestigio_impulsionar', {'server_id': SID, 'ativo': True})) or ''), '...nem impulsiona (mesmo com Brasa)')
    ok('não encontrado' in (msg_erro(emitir(ana, 'prestigio_pedir', {'server_id': 99999})) or '') and 'não encontrado' in (msg_erro(emitir(ana, 'prestigio_pedir', {'server_id': 'x'})) or ''),
       'servidor que não existe e id inválido dão a mesma resposta (não revela servidor alheio)')
    ok(emitir(ana, 'prestigio_pedir', {'server_id': None}) is not None, 'payload ruim não derruba')
    ok('Brasa' in (msg_erro(emitir(beto, 'prestigio_impulsionar', {'server_id': SID, 'ativo': True})) or ''), 'membro SEM Brasa não impulsiona (a mensagem explica)')
    ok(ServerBoost.query.count() == 0, '...e nada foi gravado')

    ev(dono); ev(beto); ev(cris)
    rec = emitir(ana, 'prestigio_impulsionar', {'server_id': SID, 'ativo': True})
    ok(ServerBoost.query.filter_by(server_id=SID, person_id=ids['ana']).count() == 1, 'membro com Brasa impulsiona')
    e = estado(rec)
    ok(e and e['eu_impulsiono'] and e['impulsos'] == 1 and e['meus_usados'] == 1, 'quem impulsionou recebe o estado novo')
    ok(any(m['name'] == 'prestigio_estado' for m in ev(ana2)), 'regra 6: a OUTRA aba da mesma pessoa também recebe o estado')
    mudou = ev(dono, 'prestigio_mudou')
    ok(mudou and mudou[-1]['args'][0]['impulsos'] == 1 and mudou[-1]['args'][0]['por'] == 'Ana' and mudou[-1]['args'][0]['server_id'] == SID, 'regra 6: os outros membros recebem o nível novo')
    ok(len(ev(beto, 'prestigio_mudou')) == 1, '...todos os membros')
    ok(not ev(cris, 'prestigio_mudou'), '...e quem não está no servidor não recebe nada')
    # valor explícito: repetir não duplica nem desfaz
    emitir(ana, 'prestigio_impulsionar', {'server_id': SID, 'ativo': True})
    ok(ServerBoost.query.filter_by(server_id=SID, person_id=ids['ana']).count() == 1, 'impulsionar de novo não duplica (um por servidor)')
    ok(not ev(dono, 'prestigio_mudou'), '...e não avisa ninguém à toa')
    # limite por pessoa
    emitir(ana, 'prestigio_impulsionar', {'server_id': OUTRO, 'ativo': True})
    rec = emitir(ana, 'prestigio_pedir', {'server_id': SID})
    ok(estado(rec)['meus_usados'] == 2, 'segundo impulso em outro servidor')
    boosts(0)                                               # limpa os dos testes de nível, mas deixa os da Ana abaixo
    db.session.add(ServerBoost(server_id=SID, person_id=ids['ana'])); db.session.commit(); prestigio.invalidar()
    # a Ana tem 2 impulsos usados (OUTRO + SID): um terceiro, em qualquer lugar, é recusado
    srv3 = Server(name='Terceiro', owner_id=ids['ana']); db.session.add(srv3); db.session.commit(); srv3.members.append(db.session.get(Person, ids['ana'])); db.session.commit()
    ok('já usou' in (msg_erro(emitir(ana, 'prestigio_impulsionar', {'server_id': srv3.id, 'ativo': True})) or ''), 'o limite é por PESSOA (2): o terceiro impulso é recusado com explicação')
    emitir(ana, 'prestigio_impulsionar', {'server_id': OUTRO, 'ativo': False})
    ok(ServerBoost.query.filter_by(server_id=OUTRO).count() == 0, 'tirar o impulso libera a vaga')
    emitir(ana, 'prestigio_impulsionar', {'server_id': srv3.id, 'ativo': True})
    ok(ServerBoost.query.filter_by(server_id=srv3.id).count() == 1, '...e dá pra usar em outro servidor')
    emitir(ana, 'prestigio_impulsionar', {'server_id': srv3.id, 'ativo': False})
    emitir(ana, 'prestigio_impulsionar', {'server_id': SID, 'ativo': False})
    ok(ServerBoost.query.filter_by(person_id=ids['ana']).count() == 0, 'tirar de novo não dá erro')

    # ---------------- 3. Brasa vencida não conta; renovou, volta ----------------
    boosts(6)
    ok(prestigio.info(SID)['nivel'] == 2, '6 impulsos de gente com Brasa = nível 2')
    for b in boosters[:3]:
        b.olimpo_ate = br_now() - timedelta(days=1)
    db.session.commit(); prestigio.invalidar()
    i = prestigio.info(SID)
    ok(i['impulsos'] == 3 and i['nivel'] == 1, 'impulso de quem está com a Brasa VENCIDA não conta (3 de 6): o nível cai')
    ok(ServerBoost.query.filter_by(server_id=SID).count() == 6, '...mas a linha fica')
    for b in boosters[:3]:
        b.olimpo_ate = br_now() + timedelta(days=5)
    db.session.commit(); prestigio.invalidar()
    ok(prestigio.info(SID)['nivel'] == 2, 'renovou a Brasa: os impulsos voltam a contar')
    e = estado(emitir(ana, 'prestigio_pedir', {'server_id': SID}))
    ok(len(e['quem']) == 6 and all(q['vale'] for q in e['quem']), 'a janela lista quem impulsiona')

    # ---------------- 4. quem sai leva o impulso ----------------
    db.session.add(ServerBoost(server_id=SID, person_id=ids['ana'])); db.session.commit(); prestigio.invalidar()
    antes = prestigio.info(SID)['impulsos']
    ana.emit('sair_do_servidor', {'server_id': SID}); ev(ana)
    ok(ServerBoost.query.filter_by(server_id=SID, person_id=ids['ana']).count() == 0, 'quem sai do servidor perde o impulso que tinha dado a ele')
    ok(prestigio.info(SID)['impulsos'] == antes - 1, '...e o nível é recalculado na hora')
    srv_db = db.session.get(Server, SID); srv_db.members.append(db.session.get(Person, ids['ana'])); db.session.commit()

    # ---------------- 5. o pino no mapa ----------------
    pino = MapServer(name='Praça', lat=PINO[0], lng=PINO[1], owner_id=ids['dono'], server_id=SID)
    db.session.add(pino); db.session.commit()
    nota = GeoNote(text='nota do pino', lat=PINO[0], lng=PINO[1], author_id=ids['dono'], expires_at=br_now() + timedelta(hours=5)); db.session.add(nota); db.session.commit()

    def arredores(cl, pos):
        prestigio_events._ultimo.clear()
        cl.emit('mapa_pedir_arredores', {'lat': pos[0], 'lng': pos[1]})
        return next(m['args'][0] for m in cl.get_received() if m['name'] == 'mapa_arredores')

    boosts(0); ev(longe)
    ok(prestigio.info(SID)['nivel'] == 0, 'sem impulso: nível 0')
    d = arredores(longe, PERTO)
    ok([s['id'] for s in d['servers']] == [pino.id] and not d['servers'][0].get('longe') and d['servers'][0]['lat'] == PINO[0], 'nível 0, a ~1 km: vê o pino com a posição EXATA')
    ok(d['servers'][0]['nivel'] == 0, 'o pino leva o nível')
    ok(arredores(longe, A_40KM)['servers'] == [], 'nível 0, a 40 km: não vê (o raio de sempre)')

    boosts(2)
    ok(prestigio.info(SID)['nivel'] == 1, '2 impulsos = nível 1')
    d = arredores(longe, A_40KM)
    ok(d['servers'] == [], 'nível 1 alcança 30 km: a 40 km ainda não')
    boosts(6)
    d = arredores(longe, A_40KM)
    ok(len(d['servers']) == 1 and d['servers'][0]['nivel'] == 2, 'nível 2 (100 km): quem está a 40 km passa a ver o pino')
    s = d['servers'][0]
    ok(s.get('longe') is True and (s['lat'], s['lng']) != PINO and distancia_m(s['lat'], s['lng'], PINO[0], PINO[1]) < 1000, 'de longe a posição do pino sai ARREDONDADA (~1 km), marcada como "longe"')
    ok(s['owner_id'] == ids['dono'], 'o resto do pino (dono, nome, vagas) é o de sempre')
    ok(d['notas'] == [] and d['lojas'] == [], 'PRIVACIDADE: o nível não estica notas nem lojas (só o pino do servidor)')
    ok(set(d) == {'notas', 'servers', 'lojas', 'raio_notas_m', 'raio_servidores_m', 'reacoes_permitidas', 'centro'}, '...nem acrescenta nada de pessoas ao payload do mapa')
    ok(d['raio_servidores_m'] == RAIO_SERVIDORES_M, 'o raio que o cliente desenha em volta de VOCÊ continua o de sempre')
    ok(arredores(longe, A_300KM)['servers'] == [], 'nível 2: a 300 km não vê')
    ok(arredores(longe, A_1000KM)['servers'] == [], '...nem a 1000 km')
    boosts(12)
    ok(prestigio.info(SID)['nivel'] == 3 and len(arredores(longe, A_300KM)['servers']) == 1 and arredores(longe, A_1000KM)['servers'] == [], 'nível 3 (500 km): vê a 300 km, não a 1000')
    boosts(20)
    ok(prestigio.info(SID)['nivel'] == 4 and len(arredores(longe, A_1000KM)['servers']) == 1, 'nível 4: vê a 1000 km (o mundo todo)')
    d = arredores(longe, (35.0, 139.0))
    ok(len(d['servers']) == 1 and d['servers'][0]['longe'], 'nível 4: até do outro lado do mundo')
    # o dono vê a posição exata dele mesmo de longe
    dono_p = cliente('dono')
    d = arredores(dono_p, A_300KM)
    ok(d['servers'] and (d['servers'][0]['lat'], d['servers'][0]['lng']) == PINO and not d['servers'][0].get('longe'), 'o DONO do pino sempre vê a posição exata dele')

    # explorar (olhar outro lugar) usa a mesma regra
    prestigio_events._ultimo.clear()
    import app.events as evs
    evs._explorar_ts.clear()
    longe.emit('mapa_explorar', {'lat': A_1000KM[0], 'lng': A_1000KM[1]})
    exp = next(m['args'][0] for m in longe.get_received() if m['name'] == 'mapa_arredores')
    ok(exp['explorando'] and len(exp['servers']) == 1 and exp['servers'][0]['longe'], 'explorar também mostra o pino de nível alto (aproximado)')

    # oculto / vencido / sem servidor: some mesmo com nível alto
    pino.oculta = True; db.session.commit(); prestigio.invalidar()
    ok(arredores(longe, A_1000KM)['servers'] == [], 'pino escondido pela moderação não aparece, nem com nível alto')
    pino.oculta = False; pino.expires_at = br_now() - timedelta(hours=1); db.session.commit(); prestigio.invalidar()
    ok(arredores(longe, A_1000KM)['servers'] == [], 'pino vencido não aparece')
    pino.expires_at = None; db.session.commit(); prestigio.invalidar()
    ok(len(arredores(longe, A_1000KM)['servers']) == 1, '...e volta quando vale de novo')

    # prévia de longe: dá pra olhar; entrar não
    longe.emit('atualizar_localizacao', {'lat': A_1000KM[0], 'lng': A_1000KM[1], 'fonte': 'aparelho'}); ev(longe)
    arredores(longe, A_1000KM)
    prestigio_events._ultimo.clear()
    longe.emit('mapa_servidor_previa', {'server_id': SID})
    rec = ev(longe)
    pv = next((m['args'][0] for m in rec if m['name'] == 'mapa_servidor_previa'), None)
    ok(pv and pv['pino']['longe'] is True and pv['nivel'] == 4 and pv['pino']['raio_entrar_m'] == RAIO_SERVIDORES_M, 'a prévia de longe abre, marcada como "longe" e com o nível')
    ok('descricao' in pv and 'membros' in pv and 'mensagens' not in str(pv).lower() and 'peer' not in str(pv).lower(), '...e continua sendo a prévia SEGURA de sempre')
    longe.emit('entrar_servidor_pin', {'server_id': SID})
    rec = ev(longe)
    ok(any('longe demais' in (m['args'][0].get('msg', '')) for m in rec if m['name'] == 'erro_bazinga'), 'ENTRAR pelo pino continua exigindo estar dentro do raio normal')
    ok(not db.session.query(Person).filter(Person.id == ids['longe']).join(Person.servers).filter(Server.id == SID).count(), '...e a pessoa não entrou')
    boosts(0)
    longe.emit('mapa_servidor_previa', {'server_id': SID})
    ok(any('fora do seu alcance' in (m['args'][0].get('msg', '')) for m in ev(longe) if m['name'] == 'erro_bazinga'), 'sem o nível a prévia de longe volta a ser recusada')

    # ---------------- 6. ao vivo: o alcance cresce e encolhe ----------------
    boosts(0)
    longe.emit('atualizar_localizacao', {'lat': A_40KM[0], 'lng': A_40KM[1], 'fonte': 'aparelho'}); arredores(longe, A_40KM); ev(longe)
    # a Ana (com Brasa) volta a ser membro e impulsiona: 1 impulso não muda o nível de 40 km. Use gente suficiente via banco + um impulso de verdade no fim.
    boosts(5)       # 25 pontos + 8 membros/5 => nível 1; falta 1 impulso de verdade pra nível 2 (30)
    prestigio.invalidar()
    i0 = prestigio.info(SID)
    ok(i0['nivel'] == 1, 'preparo: nível 1 (a 40 km ainda não vê)')
    ev(longe)
    ana_b = cliente('ana')
    rec = emitir(ana_b, 'prestigio_impulsionar', {'server_id': SID, 'ativo': True})
    ok(prestigio.info(SID)['nivel'] == 2, 'o impulso de verdade fecha 30 pontos: nível 2')
    novo = ev(longe, 'novo_servidor_mapa')
    ok(novo and novo[-1]['args'][0]['longe'] is True and novo[-1]['args'][0]['nivel'] == 2 and novo[-1]['args'][0]['lat'] != PINO[0], 'regra 6: quem passou a estar no alcance recebe o pino na hora (aproximado)')
    sub = [m for m in ev(dono, 'prestigio_mudou') if m['args'][0].get('subiu')]
    ok(sub, 'e o servidor todo fica sabendo que SUBIU de nível')
    ev(longe)
    emitir(ana_b, 'prestigio_impulsionar', {'server_id': SID, 'ativo': False})
    ok(prestigio.info(SID)['nivel'] == 1, 'tirar o impulso derruba o nível')
    ok(any(m['name'] == 'servidor_mapa_apagado' and m['args'][0]['id'] == pino.id for m in ev(longe)), 'regra 6: quem deixou de estar no alcance perde o pino da tela')

    # plantar de novo avisa pelo alcance do nível
    boosts(20)
    apag = MapServer.query.filter_by(server_id=SID).first(); db.session.delete(apag); db.session.commit(); prestigio.invalidar()
    dono_c = cliente('dono')
    dono_c.emit('atualizar_localizacao', {'lat': PINO[0], 'lng': PINO[1], 'fonte': 'aparelho'}); ev(dono_c); ev(longe)
    longe.emit('atualizar_localizacao', {'lat': A_300KM[0], 'lng': A_300KM[1], 'fonte': 'aparelho'}); ev(longe)
    dono_c.emit('plantar_servidor', {'server_id': SID, 'lat': PINO[0], 'lng': PINO[1]})
    n1 = ev(dono_c, 'novo_servidor_mapa')
    ok(n1 and n1[-1]['args'][0]['nivel'] == 4 and not n1[-1]['args'][0].get('longe') and n1[-1]['args'][0]['lat'] == PINO[0], 'quem plantou recebe o pino exato e com nível')
    nl = ev(longe, 'novo_servidor_mapa')
    ok(nl and nl[-1]['args'][0]['longe'] is True, 'plantar: quem está a 300 km recebe o pino aproximado (nível 4)')

    # ---------------- 7. cargos a mais ----------------
    srv_c = Server(name='Cargos', owner_id=ids['dono']); db.session.add(srv_c); db.session.commit()
    srv_c.members.append(db.session.get(Person, ids['dono'])); db.session.commit()
    for i in range(cargos.MAX_CARGOS):
        db.session.add(ServerRole(server_id=srv_c.id, nome=f'c{i}', cor='#112233', permissoes=0, posicao=i))
    srv_c.estrutura = True; db.session.commit(); cargos.invalidar(srv_c.id)
    dono_c.get_received()
    dono_c.emit('cargo_criar', {'server_id': srv_c.id, 'nome': 'extra'})
    ok(any('no máximo 25' in (m['args'][0].get('msg', '')) for m in ev(dono_c) if m['name'] == 'erro_bazinga'), 'sem prestígio, o 26º cargo é recusado (e diz que o prestígio libera mais)')
    ok(ServerRole.query.filter_by(server_id=srv_c.id).count() == 25, '...nada foi criado')
    for b in boosters[:3]:
        srv_c.members.append(b)
    db.session.commit()
    for b in boosters[:3]:
        db.session.add(ServerBoost(server_id=srv_c.id, person_id=b.id))
    db.session.commit(); prestigio.invalidar()
    ok(prestigio.info(srv_c.id)['nivel'] == 1, 'preparo: 3 impulsos = nível 1')
    dono_c.emit('cargo_criar', {'server_id': srv_c.id, 'nome': 'extra'}); ev(dono_c)
    ok(ServerRole.query.filter_by(server_id=srv_c.id).count() == 26, 'nível 1 libera mais cargos: o 26º é criado')
    ok(cargos.MAX_SOBRESCRITAS >= cargos.MAX_CARGOS + max(prestigio.CARGOS_EXTRA) + 1, 'o teto de sobrescritas por canal cabe todos os cargos do nível máximo')

    # ---------------- 8. Explorar: barquinho maior ----------------
    pq = Server(name='Pequeno', owner_id=ids['dono'], description='Uma comunidade legal pra conversar todo dia.'); db.session.add(pq); db.session.commit()
    pq.members.append(db.session.get(Person, ids['dono'])); db.session.add(Channel(name='geral', server_id=pq.id, channel_type='text')); db.session.commit()
    explorar.definir_publico(pq, True, 'jogos')
    u = db.session.get(Person, ids['longe'])
    it = next(i for i in explorar.lista(u)['mar'] if i['id'] == pq.id)
    ok(it['porte'] == 1 and it['nivel'] == 0, 'servidor pequeno e sem nível: canoa')
    for b in boosters[:12]:
        pq.members.append(b); db.session.add(ServerBoost(server_id=pq.id, person_id=b.id))
    db.session.commit(); prestigio.invalidar()
    it = next(i for i in explorar.lista(u)['mar'] if i['id'] == pq.id)
    ok(it['nivel'] == 3 and it['porte'] == 3, 'nível 3 dá pelo menos uma caravela mesmo com poucos membros (o porte por membros continua valendo se for maior)')
    ok(explorar.previa(u, pq.id)['nivel'] == 3, 'a prévia do Explorar leva o nível')

    # ---------------- 9. apagar o servidor limpa os impulsos ----------------
    boosts(3)
    dono_c.emit('apagar_servidor', {'server_id': SID}); ev(dono_c)
    ok(ServerBoost.query.filter_by(server_id=SID).count() == 0, 'apagar o servidor leva os impulsos junto')

    # ---------------- 10. consultas: com o cache quente, o mapa não pergunta por impulso ----------------
    boosts(6, pq.id)
    d0 = dados_do_mapa_perto(PINO[0], PINO[1], [], viewer_id=ids['longe'])      # esquenta
    sqls = []

    def espiar(conn, cursor, statement, parameters, context, executemany):
        sqls.append(statement)
    event.listen(db.engine, 'before_cursor_execute', espiar)
    dados_do_mapa_perto(PINO[0], PINO[1], [], viewer_id=ids['longe'])
    dados_do_mapa_perto(A_40KM[0], A_40KM[1], [], viewer_id=ids['longe'])
    event.remove(db.engine, 'before_cursor_execute', espiar)
    ok(not any('server_boost' in q.lower() for q in sqls), 'com o cache quente, dois pedidos de mapa não consultam os impulsos')

    # ---------------- 11. o que o cliente promete ----------------
    js, css = ler('static', 'js', 'prestigio.js'), ler('static', 'css', 'prestigio.css')
    m = re.search(r"const NOMES = \[(.*?)\];", js)
    ok(m and [x.strip().strip("'") for x in m.group(1).split(',')] == list(prestigio.NOMES), 'prestigio.js tem os mesmos nomes de nível do servidor')
    ok(all(f"'{ev_}'" in js or ev_ in js for ev_ in ('prestigio_pedir', 'prestigio_impulsionar')) and 'ativo: a === \'dar\'' in js, 'a tela manda o valor EXPLÍCITO do impulso (duas abas não se anulam)')
    ok('.pr-card' in css and '.bsv-nivel' in css and '.ex-nivel' in css, 'o CSS cobre a janela, o cartão do mapa e o Explorar')
    chat = ler('templates', 'chat.html')
    ok(all(x in chat for x in ('Prestigio.iniciar', "socket.on('prestigio_estado'", "socket.on('prestigio_mudou'", "socket.on('prestigio_erro'", 'css/prestigio.css', 'js/prestigio.js')), 'o chat.html liga o módulo e os 3 eventos')
    ok('nivelPino' in chat and 'longePino' in chat and 'pedirPreviaDoPino' in chat, 'o cartão do pino no mapa mostra o nível e, de longe, só deixa ver a prévia')
    ok('Prestigio.menu' in ler('static', 'js', 'cargos.js'), 'o menu do servidor ganha "Prestígio e impulso"')
    ok('Brasa' in js and 'grátis' in js, 'quem não tem Brasa vê o caminho (ativar) e a tela avisa que é grátis por enquanto')
    ok('olimpo.gratis' in ler('prestigio.py') or 'brasa_gratis' in ler('prestigio.py'), 'nada aqui cobra: o estado só repete se a Brasa é grátis')

print()
print('TUDO CERTO' if not falhas else f'{len(falhas)} FALHA(S):')
for f in falhas:
    print(' -', f)
sys.exit(1 if falhas else 0)
