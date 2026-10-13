"""Explorar servidores: só o que o dono publicou aparece, prévia sem mensagens/canais privados, entrar sem convite, regra 6, busca/tema/seed,
tamanho do barco, admin tira do ar. Banco SQLite em memória."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, explorar, passe_events, explorar_events
from app.bazar import definir_admin
from app.models import Role, Person, Server, Channel, Message, server_members

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def recebidos(cl, nome=None):
    return [m for m in cl.get_received() if nome is None or m['name'] == nome]


H = {'X-Requested-With': 'fetch'}
with app.app_context():
    db.create_all()
    r = Role(name='M', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('dono', 'ana', 'beto', 'adm'):
        p = Person(name=n.title(), email=f'{n}@x', role_id=r.id, username=n); db.session.add(p); db.session.commit(); ids[n] = p.id
    definir_admin(ids['adm'])
    extras = []
    for i in range(120):
        p = Person(name=f'x{i}', email=f'x{i}@x', role_id=r.id, username=f'x{i:03d}'); db.session.add(p); extras.append(p)
    db.session.commit()

    def pessoa(n):
        db.session.expire_all()
        return db.session.get(Person, ids[n])

    def servidor(nome, membros, desc='Uma comunidade legal pra conversar todo dia.', publico=None, tema='jogos'):
        s = Server(name=nome, owner_id=ids['dono'], description=desc); db.session.add(s); db.session.commit()
        s.members.append(db.session.get(Person, ids['dono']))
        for p in extras[:membros - 1]:
            s.members.append(p)
        db.session.add(Channel(name='geral', server_id=s.id, channel_type='text')); db.session.add(Channel(name='segredo', server_id=s.id, channel_type='text', is_private=True))
        db.session.add(Channel(name='voz', server_id=s.id, channel_type='voice')); db.session.commit()
        if publico:
            explorar.definir_publico(s, True, tema)
        return s

    def cliente(n):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[n]
        sc = socketio.test_client(app, flask_test_client=fc); sc.get_received()
        return fc, sc

    s_canoa = servidor('Canoa', 3, publico=True, tema='arte')
    s_vel = servidor('Veleiro', 10, publico=True, tema='jogos')
    s_cara = servidor('Caravela Grande', 50, publico=True, tema='jogos')
    s_gal = servidor('Galeao', 110, publico=True, tema='musica')
    s_priv = servidor('Privado', 8, publico=False)
    ana = pessoa('ana')

    # ---------- o que aparece ----------
    L = explorar.lista(ana)
    nomes = {i['nome'] for i in L['mar']}
    ok(nomes == {'Canoa', 'Veleiro', 'Caravela Grande', 'Galeao'} and L['total'] == 4, 'Só servidor público aparece (o privado não)')
    ok({i['nome']: i['porte'] for i in L['mar']} == {'Canoa': 1, 'Veleiro': 2, 'Caravela Grande': 3, 'Galeao': 4}, 'Tamanho do barco por nº de membros (1 canoa, 2 veleiro, 3 caravela, 4 galeão)')
    ok(L['terra'][0]['nome'] == 'Galeao' and [i['membros'] for i in L['terra']] == sorted([i['membros'] for i in L['terra']], reverse=True), 'Terra: os mais movimentados primeiro')
    ok(set(L['por_tema']) == {'arte', 'jogos', 'musica'} and len(L['por_tema']['jogos']) == 2, 'Listas por tema só com os temas que têm servidor')
    ok(sum(t['qtd'] for t in L['temas']) == 4 and len(L['temas']) == len(explorar.TEMAS_EXPLORAR), 'Chips de tema com a contagem')
    ok(all(not i['meu'] for i in L['mar']), 'Nenhum marcado como "meu" (ana ainda não está em nenhum)')
    ok(explorar.lista(ana, tema='jogos')['total'] == 2 and not explorar.lista(ana, tema='jogos')['por_tema'], 'Filtrar por tema')
    ok(explorar.lista(ana, tema='nao_existe')['total'] == 4, 'Tema inválido é ignorado (não quebra nem filtra)')
    ok(explorar.lista(ana, busca='galeao')['total'] == 1 and explorar.lista(ana, busca='comunidade')['total'] == 4, 'Busca por nome e por descrição')
    ok(explorar.lista(ana, busca='100%')['total'] == 0 and explorar.lista(ana, busca='_')['total'] == 0, '% e _ na busca não viram curinga')
    a1 = [i['id'] for i in explorar.lista(ana, seed='1')['mar']]
    ok(a1 == [i['id'] for i in explorar.lista(ana, seed='1')['mar']], 'A ordem do mar é estável com a mesma seed')
    ok(any([i['id'] for i in explorar.lista(ana, seed=str(k))['mar']] != a1 for k in range(2, 8)), 'E muda com outra seed (botão de embaralhar)')

    # ---------- publicar: regras ----------
    sem_desc = servidor('SemDesc', 4, desc='curta')
    E = explorar.ErroExplorar
    def levanta(fn):
        try:
            fn()
        except E:
            db.session.rollback(); return True
        return False
    ok(levanta(lambda: explorar.definir_publico(sem_desc, True, 'jogos')), 'Publicar sem descrição de verdade: recusado')
    sem_desc.description = 'Agora tem uma descrição decente.'; db.session.commit()
    ok(levanta(lambda: explorar.definir_publico(sem_desc, True, 'tema_inventado')), 'Publicar sem tema válido: recusado')
    Channel.query.filter_by(server_id=sem_desc.id, channel_type='text').update({'is_private': True}); db.session.commit()
    ok(levanta(lambda: explorar.definir_publico(sem_desc, True, 'jogos')), 'Publicar sem nenhum canal de texto aberto: recusado')
    Channel.query.filter_by(server_id=sem_desc.id, channel_type='text').update({'is_private': False}); db.session.commit()
    explorar.definir_publico(sem_desc, True, 'estudos')
    ok(db.session.get(Server, sem_desc.id).publico is True and explorar.lista(ana)['total'] == 5, 'Cumpridos os requisitos, o servidor aparece')

    # ---------- prévia: privacidade ----------
    db.session.add(Message(text='mensagem secreta do canal', person_id=ids['dono'], channel_id=Channel.query.filter_by(server_id=s_vel.id, name='geral').first().id)); db.session.commit()
    P = explorar.previa(ana, s_vel.id)
    ok(P['canais'] == ['geral'] and 'segredo' not in P['canais'], 'A prévia lista só canais de texto NÃO privados')
    ok(P['canais_voz'] == 1 and P['membros'] == 10 and P['dono'] == 'Dono', 'Prévia: canais de voz, membros e dono')
    ok('mensagem secreta' not in str(P) and 'x0' not in str(P) and 'email' not in str(P).lower(), 'A prévia não traz mensagem, membro nominal nem e-mail')
    ok(levanta(lambda: explorar.previa(ana, s_priv.id)), 'Servidor não público: sem prévia pra quem não é membro')
    ok(explorar.previa(pessoa('dono'), s_priv.id)['meu'] is True, '...mas o dono/membro abre o próprio')
    ok(levanta(lambda: explorar.previa(ana, 99999)), 'Servidor que não existe: erro de regra')
    ok(explorar.surpresa(ana)['id'] in {s_canoa.id, s_vel.id, s_cara.id, s_gal.id, sem_desc.id}, 'Surpreenda-me devolve um servidor público')

    # ---------- entrar ----------
    fana, sana = cliente('ana'); _, sbeto = cliente('beto'); _, sdono = cliente('dono')
    sana.emit('explorar_entrar', {'server_id': s_priv.id})
    ev = recebidos(sana)
    ok(any(m['name'] == 'explorar_erro' for m in ev) and not explorar.eh_membro(pessoa('ana'), s_priv.id), 'Não entra direto em servidor que não é público')
    explorar_events._ultimo.clear()
    sana.emit('explorar_entrar', {'server_id': s_vel.id})
    ev = recebidos(sana); nomes_ev = [m['name'] for m in ev]
    ok(explorar.eh_membro(pessoa('ana'), s_vel.id) and 'servidor_discord_criado' in nomes_ev and 'entrou_por_convite' in nomes_ev, 'Servidor público: entra sem convite e a aba abre o servidor')
    j = [m for m in ev if m['name'] == 'servidor_discord_criado'][0]['args'][0]
    ok(all(c['name'] != 'segredo' for c in j['channels']), 'Quem entra NÃO recebe canal privado')
    sdono.get_received()
    sdono2 = cliente('dono')[1]
    explorar_events._ultimo.clear()
    sbeto.emit('explorar_entrar', {'server_id': s_vel.id})
    ok(any(m['name'] == 'membro_entrou_servidor' for m in recebidos(sdono2)), 'Regra 6: os membros que já estavam lá são avisados da pessoa nova')
    sana.get_received(); explorar_events._ultimo.clear()
    sana.emit('explorar_entrar', {'server_id': s_vel.id})
    ev = recebidos(sana)
    ok(db.session.query(server_members).filter(server_members.c.server_id == s_vel.id, server_members.c.person_id == ids['ana']).count() == 1 and not any(m['name'] == 'membro_entrou_servidor' for m in ev), 'Entrar de novo não duplica membro nem reanuncia')
    ok(explorar.lista(pessoa('ana'))['mar'] and any(i['meu'] for i in explorar.lista(pessoa('ana'))['mar'] if i['id'] == s_vel.id), 'Depois de entrar, o servidor vem marcado como "meu"')

    # ---------- dono liga/desliga ----------
    explorar_events._ultimo.clear()
    sana.emit('definir_explorar', {'server_id': s_vel.id, 'publico': False}); ev = recebidos(sana)
    ok(any(m['name'] == 'explorar_erro' for m in ev) and db.session.get(Server, s_vel.id).publico is True, 'Quem não é dono não despublica')
    explorar_events._ultimo.clear()
    sdono2.emit('definir_explorar', {'server_id': s_vel.id, 'publico': False}); ev = recebidos(sdono2)
    ok(any(m['name'] == 'explorar_definido' for m in ev) and db.session.get(Server, s_vel.id).publico is False, 'O dono tira o servidor do Explorar')
    ok(s_vel.id not in {i['id'] for i in explorar.lista(ana)['mar']}, 'E ele some do mar na hora')
    explorar_events._ultimo.clear()
    sana.emit('definir_explorar', {'server_id': s_priv.id, 'publico': True, 'tema': 'jogos'})
    ok(db.session.get(Server, s_priv.id).publico is not True, 'Quem não é dono não publica servidor dos outros')

    # sem login
    anon = socketio.test_client(app); anon.get_received()
    for ev_ in ('explorar_pedir', 'explorar_previa', 'explorar_surpresa', 'explorar_entrar', 'definir_explorar'):
        anon.emit(ev_, {'server_id': s_cara.id})
    ok(not anon.get_received(), 'Sem login: nenhum evento do Explorar responde')

    # ---------- admin ----------
    fadm, _ = cliente('adm')
    ok(fana.get('/admin/api/servidores').status_code == 403, 'Não-admin não vê a lista de servidores públicos')
    lst = fadm.get('/admin/api/servidores').get_json()['servidores']
    ok({x['nome'] for x in lst} >= {'Galeao', 'Canoa'} and s_vel.id not in {x['id'] for x in lst}, 'Admin lista os servidores públicos')
    ok(fadm.post(f'/admin/api/servidores/{s_gal.id}/despublicar', json={}).status_code == 400, 'Despublicar sem o cabeçalho anti-forja: recusado')
    ok(fadm.post(f'/admin/api/servidores/{s_gal.id}/despublicar', json={}, headers=H).status_code == 200 and db.session.get(Server, s_gal.id).publico is False, 'Admin tira um servidor do Explorar')
    ok(explorar.eh_membro(pessoa('dono'), s_gal.id), 'O servidor segue existindo com os membros')

    # ---------- front-end ----------
    js = open(os.path.join(RAIZ, 'static', 'js', 'explorar.js'), encoding='utf-8').read()
    css = open(os.path.join(RAIZ, 'static', 'css', 'explorar.css'), encoding='utf-8').read()
    html = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
    ok(js.count('ctx.esc(') > 15 and 'ctx.escUrl(' in js, 'explorar.js escapa o que vem do servidor (nome, descrição, canais, ícone)')
    ok(re.search(r'(?<!\w)eval\(|document\.write', js) is None, 'Sem eval/document.write')
    ok('linear-gradient' not in css, 'Cena chapada, sem gradiente')
    ok('id="explorar-modal"' in html and "Explorar.abrir()" in html and "socket.on('explorar'" in html and 'cfg-explorar-on' in html, 'chat.html monta o modal, abre pelo "+" e tem o toggle nas configurações')
    ok('Em breve</span></b><small>Um mapa vivo' not in html, 'O cartão do "+" deixou de ser "em breve"')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
