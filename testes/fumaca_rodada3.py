"""Rodada 3: convite por membro, posição/notas de amigos, estado da câmera, ornamentos nas mensagens."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Friendship, GeoNote

app = create_app()
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
    for n in ('Dono', 'Membro', 'Amigo', 'Estranho'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower(), moldura='fogo' if n == 'Dono' else None,
                   nome_estilo='neon' if n == 'Dono' else None)
        db.session.add(p); db.session.commit(); ids[n] = p.id
    # Dono e Amigo são amigos, mas NÃO dividem servidor
    db.session.add(Friendship(requester_id=ids['Dono'], addressee_id=ids['Amigo'], status='accepted')); db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    dono, fdono = cliente('Dono'); membro, _ = cliente('Membro'); amigo, famigo = cliente('Amigo'); estranho, _ = cliente('Estranho')

    # ---- convite por MEMBRO (não só dono) ----
    dono.emit('criar_servidor_discord', {'nome': 'S' * 80})
    srv = ev(dono, 'servidor_discord_criado')[-1]['args'][0]
    ok(len(srv['name']) == 80, 'Nome de servidor aceita até 100 (80 passou inteiro)')
    dono.emit('criar_convite', {'server_id': srv['id']})
    cod = ev(dono, 'convite_criado')[-1]['args'][0]['code']
    membro.emit('entrar_por_convite', {'code': cod}); ev(membro)
    membro.emit('criar_convite', {'server_id': srv['id'], 'duracao': 'ilimitado', 'max_usos': 'ilimitado'})
    cv = ev(membro, 'convite_criado')
    ok(bool(cv), 'Membro (não dono) consegue gerar convite')
    ok(cv and cv[-1]['args'][0]['max_usos'] == 25 and cv[-1]['args'][0]['expira_em'] is not None,
       'Convite de membro tem teto (25 usos e prazo), mesmo pedindo ilimitado')
    estranho.emit('criar_convite', {'server_id': srv['id']})
    ok(bool(ev(estranho, 'erro_bazinga')), 'Quem NÃO é do servidor não gera convite')

    # ---- posição: amigo SEM servidor em comum vê o pino; e ao abrir o mapa recebe a última posição ----
    ev(amigo)
    dono.emit('atualizar_localizacao', {'lat': -15.8, 'lng': -47.9}); ev(dono)
    pos = ev(amigo, 'posicao_amigo_atualizada')
    ok(len(pos) >= 1 and pos[-1]['args'][0]['usuario_id'] == ids['Dono'], 'Amigo (sem servidor em comum) recebe a posição ao vivo')
    amigo2, _ = cliente('Amigo')
    amigo2.emit('mapa_pedir_arredores', {'lat': -15.8, 'lng': -47.9})
    rec = ev(amigo2)
    ok(any(m['name'] == 'posicao_amigo_atualizada' and m['args'][0]['usuario_id'] == ids['Dono'] for m in rec),
       'Ao abrir o mapa, o amigo recebe a ÚLTIMA posição conhecida (sem esperar a pessoa se mexer)')
    estranho.emit('mapa_pedir_arredores', {'lat': -15.8, 'lng': -47.9})
    ok(not any(m['name'] == 'posicao_amigo_atualizada' for m in ev(estranho)), 'Estranho NÃO recebe a posição de ninguém')

    # ---- nota de amigo vale no alcance grande; de estranho, só no pequeno ----
    ev(dono); ev(amigo); ev(amigo2)
    with app.app_context():
        db.session.add(GeoNote(lat=-15.8 + 0.06, lng=-47.9, text='longe do amigo', color='#fff', author_id=ids['Dono'],
                               expires_at=None)); db.session.commit()   # ~6.6 km
    amigo2.emit('mapa_pedir_arredores', {'lat': -15.8, 'lng': -47.9})
    notas = [m for m in ev(amigo2, 'mapa_arredores')][-1]['args'][0]['notas']
    ok(any(n['texto'] == 'longe do amigo' for n in notas), 'Amigo vê a nota do amigo a ~6 km (alcance grande)')
    estranho.emit('mapa_pedir_arredores', {'lat': -15.8, 'lng': -47.9})
    notas_e = [m for m in ev(estranho, 'mapa_arredores')][-1]['args'][0]['notas']
    ok(not any(n['texto'] == 'longe do amigo' for n in notas_e), 'Estranho NÃO vê a nota a ~6 km')

    # ---- Fantasma tira o pino dos amigos ----
    ev(amigo)
    dono.emit('alternar_fantasma', {'ativo': True}); ev(dono)
    ok(any(m['name'] == 'posicao_amigo_removida' for m in ev(amigo)), 'Fantasma remove o pino do amigo')
    amigo3, _ = cliente('Amigo')
    amigo3.emit('mapa_pedir_arredores', {'lat': -15.8, 'lng': -47.9})
    ok(not any(m['name'] == 'posicao_amigo_atualizada' for m in ev(amigo3)), 'Em Fantasma a última posição não é entregue')

    # ---- estado da câmera só de quem está de verdade na call ----
    srv_id = srv['id']
    canal_voz = [ch for ch in srv['channels'] if ch['type'] == 'voice'][0]['id']
    dono.emit('entrar_call', {'canal_id': canal_voz, 'peer_id': 'peer-dono', 'usuario': 'Dono'})
    membro.emit('entrar_call', {'canal_id': canal_voz, 'peer_id': 'peer-membro', 'usuario': 'Membro'}); ev(dono); ev(membro)
    dono.emit('estado_camera', {'canal_id': canal_voz, 'peer_id': 'peer-dono', 'ligada': True})
    ec = ev(membro, 'estado_camera')
    ok(len(ec) == 1 and ec[0]['args'][0] == {'peer_id': 'peer-dono', 'ligada': True}, 'estado_camera chega no outro lado da call')
    estranho.emit('estado_camera', {'canal_id': canal_voz, 'peer_id': 'peer-dono', 'ligada': False})
    ok(not ev(membro, 'estado_camera'), 'Quem não está na call não consegue forjar o estado da câmera de outro')

    # ---- ornamentos nas mensagens ----
    membro.emit('entrar_canal', {'canal_id': [ch for ch in srv['channels'] if ch['type'] == 'text'][0]['id']})
    canal_txt = [ch for ch in srv['channels'] if ch['type'] == 'text'][0]['id']
    dono.emit('entrar_canal', {'canal_id': canal_txt}); ev(dono); ev(membro)
    dono.emit('enviar_mensagem', {'canal_id': canal_txt, 'texto': 'oi'})
    pm = ev(membro, 'receber_mensagem')
    ok(pm and pm[0]['args'][0].get('moldura') == 'fogo' and pm[0]['args'][0].get('nome_estilo') == 'neon',
       'Mensagem ao vivo leva moldura e estilo do nome do autor')
    h = fdono.get(f'/api/mensagens/{canal_txt}').get_json()
    ok(h and h[-1].get('moldura') == 'fogo' and h[-1].get('nome_estilo') == 'neon', 'Histórico do canal também leva os ornamentos')

    # ---- limites de texto ----
    dono.emit('atualizar_perfil', {'name': 'N' * 90, 'pensando': 'p' * 200}); ev(dono)
    pdono = Person.query.get(ids['Dono'])
    ok(len(pdono.name) == 24 and len(pdono.pensando) == 50, 'Nome de exibição (24) e "pensando" (50) têm limite no servidor')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
