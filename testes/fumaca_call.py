"""Calls: uma pessoa só em UMA call, reentrada depois de queda do socket (graça), limpeza de fantasma, só o dono mexe na
própria entrada, ligação por DM (aba certa, aceitar uma vez, vídeo/voz, offline), versão do app, posição ao vivo."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, APP_VERSAO
from app import events
from app.models import Role, Person, Friendship

app = create_app()
events.GRACA_CALL_SEGUNDOS = 0.4   # teste rápido
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower())
        db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted')); db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc)
        return cl

    ana = cliente('Ana')
    rec = ev(ana)
    ok(any(m['name'] == 'versao_app' and m['args'][0]['versao'] == APP_VERSAO for m in rec), 'connect manda a versão do app')
    beto = cliente('Beto'); ev(beto)

    # servidor com 2 canais de voz
    ana.emit('criar_servidor_discord', {'nome': 'Casa'}); ev(ana)
    from app.models import Channel, Server
    srv = Server.query.filter_by(name='Casa').first()
    v1 = Channel(name='voz1', channel_type='voice', server_id=srv.id); v2 = Channel(name='voz2', channel_type='voice', server_id=srv.id)
    db.session.add_all([v1, v2]); db.session.commit()
    ana.emit('criar_convite', {'server_id': srv.id}); cod = ev(ana, 'convite_criado')[-1]['args'][0]['code']
    beto.emit('entrar_por_convite', {'code': cod}); ev(beto); ev(ana)
    ana = cliente('Ana'); beto = cliente('Beto'); ev(ana); ev(beto)   # reconecta pra entrar na sala do servidor

    # ---- entrar numa call; o outro recebe novo_usuario_call; a lista oficial volta pra quem entrou ----
    ana.emit('entrar_call', {'canal_id': v1.id, 'peer_id': 'peer-ana-1'}); ev(ana)
    beto.emit('entrar_call', {'canal_id': v1.id, 'peer_id': 'peer-beto-1'})
    ra, rb = ev(ana), ev(beto)
    ok(any(m['name'] == 'novo_usuario_call' and m['args'][0]['peer_id'] == 'peer-beto-1' and m['args'][0]['reentrada'] is False for m in ra),
       'Quem já estava na call recebe novo_usuario_call de quem chegou')
    lista = [m for m in rb if m['name'] == 'participantes_call_mudou']
    ok(lista and {p['peer_id'] for p in lista[-1]['args'][0]['participantes']} == {'peer-ana-1', 'peer-beto-1'},
       'Quem chegou recebe a lista oficial da call')

    # ---- UMA call por pessoa: Beto entra na voz2 sem sair da voz1 -> sai da voz1 sozinho ----
    ev(ana)
    beto.emit('entrar_call', {'canal_id': v2.id, 'peer_id': 'peer-beto-2'})
    ra = ev(ana)
    ok(any(m['name'] == 'usuario_saiu_call' and m['args'][0]['peer_id'] == 'peer-beto-1' for m in ra),
       'Entrar em outra call tira a pessoa da anterior (sem fantasma em 2 calls)')
    ok({p['peer_id'] for p in events.participantes_call.get(str(v1.id), [])} == {'peer-ana-1'}, 'Lista da voz1 ficou só com a Ana')
    ok({p['peer_id'] for p in events.participantes_call.get(str(v2.id), [])} == {'peer-beto-2'}, 'Lista da voz2 tem o Beto')

    # ---- mesma pessoa, 2ª aba: a nova vence e a velha é avisada ----
    beto2 = cliente('Beto'); ev(beto2); ev(beto)
    beto2.emit('entrar_call', {'canal_id': v2.id, 'peer_id': 'peer-beto-aba2'})
    ok(any(m['name'] == 'call_substituida' and m['args'][0]['peer_id'] == 'peer-beto-2' for m in ev(beto)),
       'A aba antiga recebe call_substituida')
    ok({p['peer_id'] for p in events.participantes_call.get(str(v2.id), [])} == {'peer-beto-aba2'},
       'Só a entrada nova do Beto sobrou (nada de duplicata)')
    beto2.disconnect(); socketio.sleep(0.8)
    ok(str(v2.id) not in events.participantes_call, 'Disconnect sem voltar: sai da call depois da graça')

    # ---- queda do socket: dentro da graça, volta com o MESMO peer e não some ----
    ana.disconnect()
    ok({p['peer_id'] for p in events.participantes_call.get(str(v1.id), [])} == {'peer-ana-1'}, 'Durante a graça a Ana continua na lista')
    ana = cliente('Ana'); ev(ana)
    ana.emit('entrar_call', {'canal_id': v1.id, 'peer_id': 'peer-ana-1'})
    socketio.sleep(0.8)
    ok({p['peer_id'] for p in events.participantes_call.get(str(v1.id), [])} == {'peer-ana-1'}, 'Reentrada com o mesmo peer cancela a saída')

    # ---- só o dono mexe na própria entrada ----
    caio = cliente('Caio'); ev(caio)
    caio.emit('sair_call', {'canal_id': v1.id, 'peer_id': 'peer-ana-1'})
    ok({p['peer_id'] for p in events.participantes_call.get(str(v1.id), [])} == {'peer-ana-1'}, 'Outra pessoa não consegue tirar a Ana da call')

    # ---- pedir_ligacao: Beto (de fora) não consegue; quem está na call consegue ----
    beto3 = cliente('Beto'); ev(beto3)
    beto3.emit('entrar_call', {'canal_id': v1.id, 'peer_id': 'peer-beto-3'}); ev(beto3); ev(ana)
    beto3.emit('pedir_ligacao', {'canal_id': v1.id, 'peer_id': 'peer-ana-1'})
    pedidos = [m for m in ev(ana, 'novo_usuario_call') if m['args'][0]['peer_id'] == 'peer-beto-3']
    ok(pedidos and pedidos[-1]['args'][0]['reentrada'] is True, 'pedir_ligacao faz a Ana ligar de novo pro Beto')
    caio.emit('pedir_ligacao', {'canal_id': v1.id, 'peer_id': 'peer-ana-1'})
    ok(not ev(ana, 'novo_usuario_call'), 'Quem não está na call não consegue pedir ligação')

    # ---- ligação por DM: aceitar volta só pra aba que ligou; vídeo/voz; offline ----
    beto3.emit('sair_call', {'canal_id': v1.id, 'peer_id': 'peer-beto-3'}); ev(beto3)
    ana_b = cliente('Ana'); ev(ana_b)                    # 2ª aba da Ana
    beto = cliente('Beto'); beto_b = cliente('Beto'); ev(beto); ev(beto_b); ev(ana); ev(ana_b)
    ana.emit('chamar_amigo', {'amigo_id': ids['Beto'], 'tipo': 'video'})
    ok(bool(ev(beto, 'chamada_recebida')) and bool(ev(beto_b, 'chamada_recebida')), 'As duas abas do Beto recebem o toque')
    beto.emit('aceitar_chamada', {'de_id': ids['Ana']})
    ra, ra_b, rb, rb_b = ev(ana, 'chamada_aceita'), ev(ana_b, 'chamada_aceita'), ev(beto, 'chamada_aceita'), ev(beto_b, 'chamada_aceita')
    ok(len(ra) == 1 and ra[0]['args'][0]['tipo'] == 'video', 'A aba da Ana que ligou recebe chamada_aceita (tipo=video)')
    ok(len(ra_b) == 0, 'A OUTRA aba da Ana NÃO entra na call (era a duplicata)')
    ok(len(rb) == 1 and len(rb_b) == 0, 'Só a aba do Beto que atendeu entra; a outra não')
    beto_b_res = ev(beto_b)
    # (beto_b já foi esvaziado acima; confere o resolvido de novo numa 2ª ligação)
    ana.emit('chamar_amigo', {'amigo_id': ids['Beto'], 'tipo': 'voz'}); ev(beto); ev(beto_b)
    beto_b.emit('recusar_chamada', {'de_id': ids['Ana']})
    ok(any(m['name'] == 'chamada_resolvida' for m in ev(beto)), 'Recusar numa aba fecha o toque nas outras abas')
    beto.emit('aceitar_chamada', {'de_id': ids['Ana']})
    ok(not ev(beto, 'chamada_aceita') and not ev(ana, 'chamada_aceita'), 'Atender chamada que já acabou não entra em call')

    caio.disconnect(); socketio.sleep(0.1)
    ana.emit('chamar_amigo', {'amigo_id': ids['Beto'], 'tipo': 'voz'}); ev(beto); ev(beto_b)
    ana.disconnect(); ana_b.disconnect()
    ok(bool(ev(beto, 'chamada_cancelada')), 'Quem liga e some cancela o toque de quem estava recebendo')

print()
print('TUDO CERTO' if not falhas else f'{len(falhas)} FALHA(S)')
sys.exit(1 if falhas else 0)
