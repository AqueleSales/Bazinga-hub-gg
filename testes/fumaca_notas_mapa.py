"""Rodada 29: responder e reagir nas notas do mapa.
Cobre: alcance (2 km; 15 km se for amigo do autor), posição do aparelho, localização desligada, bloqueio (sem revelar), modos de resposta
(todos / só amigos / desligadas), link só entre amigos, limites, reações (lista fechada, só totais, valor explícito, nunca quem reagiu),
quem recebe cada aviso ao vivo (regra 6: outras abas, amigo longe, estranho NÃO recebe resposta de modo "amigos"), apagar, denúncia que esconde,
fila de moderação, a nota apagada leva tudo junto, número de consultas fixo e os arquivos do cliente."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from sqlalchemy import event
from app import create_app, db, socketio
from app import events, notas_mapa_events, notas_mapa
from app.models import (Role, Person, Friendship, GeoNote, GeoNoteResposta, GeoNoteReacao, Notificacao, Denuncia, br_now)
from app.utils import dados_do_mapa_perto, REACOES_NOTA

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')
LAT, LNG = -15.8745, -48.0999


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


def erros_nota(cli):
    return [m['args'][0]['msg'] for m in ev(cli, 'geonote_erro')]


def deslocar(dm_norte, dm_leste=0):
    from math import cos, radians
    return LAT + dm_norte / 111000.0, LNG + dm_leste / (111000.0 * cos(radians(LAT)))


def livre():
    """Os freios de ritmo (1,2 s pra responder) atrapalhariam o teste; os de verdade têm teste próprio mais abaixo."""
    notas_mapa_events._ultimo.clear()


with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio', 'Duda', 'Eli', 'Fabi', 'Gil'):
        p = Person(name=n, email=f'{n.lower()}@x', role_id=r.id, username=n.lower(), bazinga_coins=0)
        db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))      # Beto é amigo da Ana
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Eli'], status='blocked'))        # Ana bloqueou o Eli
    db.session.add(Friendship(requester_id=ids['Gil'], addressee_id=ids['Ana'], status='accepted'))       # Gil também é amigo (vai denunciar)
    Person.query.get(ids['Fabi']).localizacao_ativa = False
    db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl

    def posicionar(cl, nome, pos, fonte=None):
        d = {'lat': pos[0], 'lng': pos[1]}
        if fonte:
            d['fonte'] = fonte
        cl.emit('atualizar_localizacao', d); ev(cl)

    perto = (LAT, LNG)
    ana = cliente('Ana'); ana2 = cliente('Ana')                 # a Ana em duas abas
    beto = cliente('Beto'); caio = cliente('Caio'); caio2 = cliente('Caio')
    duda = cliente('Duda'); eli = cliente('Eli'); fabi = cliente('Fabi'); gil = cliente('Gil')
    posicionar(ana, 'Ana', perto); posicionar(ana2, 'Ana', perto)
    posicionar(beto, 'Beto', deslocar(5000))                    # 5 km: amigo da Ana alcança, estranho não
    posicionar(caio, 'Caio', deslocar(40, 30)); posicionar(caio2, 'Caio', deslocar(40, 30))
    posicionar(duda, 'Duda', deslocar(5000))                    # estranha a 5 km
    posicionar(eli, 'Eli', deslocar(20)); posicionar(fabi, 'Fabi', deslocar(20))
    posicionar(gil, 'Gil', deslocar(60))

    # ---------------------------------------------------------------- nota nova
    ana.emit('criar_geonote', {'lat': perto[0], 'lng': perto[1], 'texto': 'Show de graça hoje!', 'duracao': 24}); ev(ana)
    nota = GeoNote.query.filter_by(author_id=ids['Ana']).first()
    NID = nota.id
    ok(nota.respostas_modo is None, 'nota sem escolha de modo fica NULL (usa o padrão do código)')
    ok(events.nota_para_json(nota)['respostas_modo'] == 'todos', 'o payload da nota diz o modo (padrão: todos)')

    # ---------------------------------------------------------------- responder (modo todos)
    livre()
    caio.emit('geonote_responder', {'id': NID, 'texto': '  Onde  é\n o show?  '})
    rc = ev(caio, 'geonote_resposta'); ra = ev(ana, 'geonote_resposta'); ra2 = ev(ana2, 'geonote_resposta'); rb = ev(beto, 'geonote_resposta')
    rc2 = ev(caio2, 'geonote_resposta'); rd = ev(duda, 'geonote_resposta'); rg = ev(gil, 'geonote_resposta')
    ok(len(rc) >= 1 and rc[0]['args'][0]['resposta']['texto'] == 'Onde é o show?', 'quem respondeu recebe a resposta (espaços e quebra de linha colapsados)')
    ok(len(ra) >= 1 and len(ra2) >= 1, 'o autor recebe a resposta em TODAS as abas (regra 6)')
    ok(len(rc2) >= 1, 'a outra aba de quem respondeu também recebe')
    ok(len(rb) >= 1, 'o amigo do autor, mesmo a 5 km, recebe a resposta')
    ok(len(rg) >= 1, 'o outro amigo do autor, no alcance, recebe a resposta')
    ok(len(rd) == 0, 'estranha a 5 km (fora do alcance e sem ser amiga) não recebe nada')
    r1 = rc[0]['args'][0]
    ok(r1['note_id'] == NID and r1['resposta']['autor'] == 'Caio' and r1['resposta']['autor_id'] == ids['Caio'], 'a resposta leva o autor certo')
    ok(GeoNoteResposta.query.filter_by(note_id=NID).count() == 1, 'gravou uma resposta')
    notif = Notificacao.query.filter_by(person_id=ids['Ana'], tipo='nota').all()
    ok(len(notif) == 1 and 'Caio' in notif[0].titulo and notif[0].ref == str(NID), 'o autor ganha um aviso na caixa de entrada que aponta pra nota')
    ok(not Notificacao.query.filter_by(person_id=ids['Caio'], tipo='nota').count(), 'quem respondeu não se avisa')

    # autor responde na própria nota: não gera aviso pra si
    livre()
    ana.emit('geonote_responder', {'id': NID, 'texto': 'No parque, às 20h'}); ev(ana)
    ok(GeoNoteResposta.query.filter_by(note_id=NID).count() == 2, 'o autor também responde na própria nota')
    ok(Notificacao.query.filter_by(person_id=ids['Ana'], tipo='nota').count() == 1, 'e não avisa a si mesmo')

    # ---------------------------------------------------------------- quem NÃO pode
    livre(); duda.emit('geonote_responder', {'id': NID, 'texto': 'oi'})
    ok(any('longe' in m for m in erros_nota(duda)), 'estranha fora do alcance: "longe demais"')
    livre(); eli.emit('geonote_responder', {'id': NID, 'texto': 'oi'})
    msgs = erros_nota(eli)
    ok(msgs and all('bloque' not in m.lower() for m in msgs) and any('disponível' in m for m in msgs), 'bloqueado não responde e a mensagem não revela o bloqueio')
    livre(); fabi.emit('geonote_responder', {'id': NID, 'texto': 'oi'})
    ok(any('localização' in m.lower() for m in erros_nota(fabi)), 'localização desligada: recusado com o motivo')
    ip = cliente('Gil'); posicionar(ip, 'Gil', deslocar(60), fonte='ip')
    livre(); ip.emit('geonote_responder', {'id': NID, 'texto': 'oi'})
    ok(any('aproximada' in m for m in [x['args'][0]['msg'] for x in ev(ip, 'erro_bazinga')]), 'posição só por IP não deixa agir (mesma regra de deixar nota)')
    livre(); caio.emit('geonote_responder', {'id': 999999, 'texto': 'oi'})
    ok(any('disponível' in m for m in erros_nota(caio)), 'nota que não existe: recusado')
    livre(); caio.emit('geonote_responder', {'id': NID, 'texto': '   '})
    ok(any('Escreva' in m for m in erros_nota(caio)), 'resposta vazia: recusada')
    livre(); caio.emit('geonote_responder', {'id': NID, 'texto': 'x' * 400}); ev(caio)
    ok(max(len(x.text) for x in GeoNoteResposta.query.filter_by(note_id=NID).all()) == 140, 'texto cortado em 140')
    livre(); caio.emit('geonote_responder', {'id': NID, 'texto': 'olha meu site meusite.com.br'})
    ok(any('Link' in m for m in erros_nota(caio)), 'estranho não manda link')
    livre(); beto.emit('geonote_responder', {'id': NID, 'texto': 'ingressos em ingresso.com.br'}); ev(beto)
    ok(GeoNoteResposta.query.filter_by(author_id=ids['Beto']).count() == 1, 'amigo do autor pode mandar link')
    # payload torto não derruba o servidor
    for torto in (None, 'x', [], {'id': 'abc'}, {'id': None}):
        livre(); caio.emit('geonote_responder', torto)
    ev(caio)
    ok(True, 'payload torto é ignorado sem exceção')

    # ---------------------------------------------------------------- limites
    ate = GeoNoteResposta.query.filter_by(author_id=ids['Caio'], note_id=NID).count()
    for i in range(10):
        livre(); caio.emit('geonote_responder', {'id': NID, 'texto': f'mais um {i}'})
    ev(caio)
    ok(GeoNoteResposta.query.filter_by(author_id=ids['Caio'], note_id=NID).count() == 5, 'no máximo 5 respostas por pessoa na mesma nota')
    livre(); caio.emit('geonote_responder', {'id': NID, 'texto': 'de novo'})
    ok(any('5 vezes' in m for m in erros_nota(caio)), 'e avisa por que parou')
    # freio de ritmo de verdade
    notas_mapa_events._ultimo.clear()
    beto.emit('geonote_responder', {'id': NID, 'texto': 'rapido 1'}); beto.emit('geonote_responder', {'id': NID, 'texto': 'rapido 2'})
    ok(any('Calma' in m for m in erros_nota(beto)), 'duas respostas coladas: a segunda leva o freio de ritmo')

    # ---------------------------------------------------------------- reações
    livre(); ev(ana); ev(ana2); ev(beto); ev(caio); ev(caio2); ev(duda); ev(gil)
    caio.emit('geonote_reagir', {'id': NID, 'emoji': '🔥', 'ativo': True})
    rc = ev(caio, 'geonote_reacoes'); ra = ev(ana, 'geonote_reacoes'); rb = ev(beto, 'geonote_reacoes'); rc2 = ev(caio2, 'geonote_reacoes'); rd = ev(duda, 'geonote_reacoes')
    ok(any(m['args'][0].get('minhas') == ['🔥'] for m in rc), 'quem reagiu recebe as reações dele (minhas)')
    ok(any(m['args'][0].get('minhas') == ['🔥'] for m in rc2), 'e a outra aba dele também')
    ok(ra and ra[0]['args'][0]['reacoes'] == [{'emoji': '🔥', 'total': 1}] and 'minhas' not in ra[0]['args'][0], 'o autor recebe o total, sem "minhas"')
    ok(rb and 'minhas' not in rb[0]['args'][0], 'o amigo longe recebe o total, sem "minhas"')
    ok(len(rd) == 0, 'estranha fora do alcance não recebe a reação')
    todos = [m['args'][0] for lst in (rc, ra, rb, rc2) for m in lst]
    ok(not any(('quem' in p or 'person_id' in p or 'ids' in p) for p in todos), 'nenhum payload diz QUEM reagiu')
    livre(); caio.emit('geonote_reagir', {'id': NID, 'emoji': '🔥', 'ativo': True}); ev(caio)
    ok(GeoNoteReacao.query.filter_by(note_id=NID, emoji='🔥').count() == 1, 'ligar a mesma reação duas vezes não duplica (valor explícito)')
    livre(); beto.emit('geonote_reagir', {'id': NID, 'emoji': '🔥', 'ativo': True}); livre(); beto.emit('geonote_reagir', {'id': NID, 'emoji': '❤️', 'ativo': True}); ev(beto)
    livre(); gil.emit('geonote_reagir', {'id': NID, 'emoji': '🔥', 'ativo': True}); ev(gil)
    ok(GeoNoteReacao.query.filter_by(note_id=NID, emoji='🔥').count() == 3, 'o total conta pessoas diferentes')
    livre(); caio.emit('geonote_reagir', {'id': NID, 'emoji': '💩', 'ativo': True})
    ok(any('não existe' in m for m in erros_nota(caio)), 'emoji fora da lista fechada: recusado')
    livre(); caio.emit('geonote_reagir', {'id': NID, 'emoji': '🔥', 'ativo': False}); ev(caio)
    ok(GeoNoteReacao.query.filter_by(note_id=NID, emoji='🔥').count() == 2, 'desligar tira só a dele')
    livre(); duda.emit('geonote_reagir', {'id': NID, 'emoji': '👍', 'ativo': True})
    ok(any('longe' in m for m in erros_nota(duda)), 'fora do alcance não reage')
    livre(); eli.emit('geonote_reagir', {'id': NID, 'emoji': '👍', 'ativo': True}); ev(eli)
    ok(GeoNoteReacao.query.filter_by(person_id=ids['Eli']).count() == 0, 'bloqueado não reage')

    # ---------------------------------------------------------------- o mapa já carrega tudo (quem entra depois)
    def arredores(cli):
        cli.emit('mapa_pedir_arredores', {'lat': perto[0], 'lng': perto[1]})
        m = ev(cli, 'mapa_arredores')
        return m[-1]['args'][0] if m else None

    d = arredores(caio)
    n = next((x for x in d['notas'] if x['id'] == NID), None)
    ok(n is not None and d['reacoes_permitidas'] == list(REACOES_NOTA), 'o mapa manda a lista de reações permitidas (uma fonte só)')
    ok(n and len(n['respostas']) >= 3 and n['respostas'][0]['texto'] == 'Onde é o show?', 'o mapa carrega as respostas em ordem')
    ok(n and n['reacoes'] == [{'emoji': '❤️', 'total': 1}, {'emoji': '🔥', 'total': 2}] and n['minhas'] == [], f'totais na ordem fixa da lista; "minhas" vazio pra quem não reagiu (veio {n and n["reacoes"]} / {n and n["minhas"]})')
    nb = next(x for x in arredores(beto)['notas'] if x['id'] == NID)
    ok(sorted(nb['minhas']) == sorted(['🔥', '❤️']), f'o amigo vê as reações DELE marcadas (e só as dele) (veio {nb["minhas"]})')
    ok(all('autor_id' in x and 'ha_s' in x for x in n['respostas']), 'cada resposta leva autor, id e idade')

    # ---------------------------------------------------------------- modo "só amigos"
    for cl in (ana, ana2, beto, caio, caio2, duda, gil): ev(cl)
    ana.emit('editar_geonote', {'id': NID, 'respostas_modo': 'amigos'})
    ed = ev(caio, 'geonote_editada')
    ok(ed and ed[0]['args'][0]['respostas_modo'] == 'amigos', 'editar a nota avisa o novo modo a quem está no alcance')
    ok(GeoNote.query.get(NID).respostas_modo == 'amigos', 'modo gravado')
    for cl in (ana, ana2, beto, caio, caio2, duda, gil): ev(cl)
    livre(); caio.emit('geonote_responder', {'id': NID, 'texto': 'posso?'})
    ok(any('amigos' in m for m in erros_nota(caio)), 'estranho não responde mais no modo "só amigos"')
    livre(); gil.emit('geonote_responder', {'id': NID, 'texto': 'eu vou!'})
    rg = ev(gil, 'geonote_resposta'); ra = ev(ana, 'geonote_resposta'); rb = ev(beto, 'geonote_resposta'); rc = ev(caio, 'geonote_resposta'); rc2 = ev(caio2, 'geonote_resposta')
    ok(rg and ra and rb, 'amigo responde; o autor (as duas abas) e os outros amigos recebem')
    ok(len(rc) == 0 and len(rc2) == 0, 'o estranho NÃO recebe a resposta do modo "só amigos" (nem fica sabendo)')
    d = arredores(caio); n = next(x for x in d['notas'] if x['id'] == NID)
    ok(n['respostas'] == [] and n['respostas_modo'] == 'amigos', 'e o mapa dele não carrega as respostas dessa nota')
    n = next(x for x in arredores(gil)['notas'] if x['id'] == NID)
    ok(len(n['respostas']) >= 4, 'o amigo vê todas as respostas')
    n = next(x for x in arredores(ana)['notas'] if x['id'] == NID)
    ok(len(n['respostas']) >= 4, 'o autor vê todas as respostas')
    for cl in (ana, ana2, beto, caio, caio2, duda, gil): ev(cl)
    livre(); caio.emit('geonote_reagir', {'id': NID, 'emoji': '😮', 'ativo': True})
    ok(any(m['args'][0]['id'] == NID for m in ev(caio, 'geonote_reacoes')), 'reagir continua aberto a quem vê a nota, mesmo em "só amigos"')

    # ---------------------------------------------------------------- modo "desligadas"
    ana.emit('editar_geonote', {'id': NID, 'respostas_modo': 'ninguem'}); ev(ana)
    livre(); beto.emit('geonote_responder', {'id': NID, 'texto': 'oi?'})
    ok(any('desligadas' in m for m in erros_nota(beto)), 'respostas desligadas: nem amigo responde')
    livre(); ana.emit('geonote_responder', {'id': NID, 'texto': 'oi?'})
    ok(any('desligadas' in m for m in erros_nota(ana)), 'nem o próprio autor')
    n = next(x for x in arredores(ana)['notas'] if x['id'] == NID)
    ok(n['respostas'] == [], 'e as respostas antigas ficam escondidas (voltam se o autor reabrir)')
    ana.emit('editar_geonote', {'id': NID, 'respostas_modo': 'lixo'}); ev(ana)
    ok(GeoNote.query.get(NID).respostas_modo is None, 'modo inválido vira "padrão" (NULL), nunca um valor solto no banco')
    n = next(x for x in arredores(caio)['notas'] if x['id'] == NID)
    ok(len(n['respostas']) >= 4, 'padrão = todos: respostas de volta pra todo mundo')

    # ---------------------------------------------------------------- apagar resposta
    for cl in (ana, ana2, beto, caio, caio2, duda, gil): ev(cl)
    rid_beto = GeoNoteResposta.query.filter_by(author_id=ids['Beto']).first().id
    rid_caio = GeoNoteResposta.query.filter_by(author_id=ids['Caio']).first().id
    livre(); caio.emit('geonote_resposta_apagar', {'id': rid_beto})
    ok(any('só pode apagar' in x['args'][0]['msg'] for x in ev(caio, 'geonote_erro')), 'um estranho não apaga resposta dos outros')
    livre(); caio.emit('geonote_resposta_apagar', {'id': rid_caio})
    ok(GeoNoteResposta.query.get(rid_caio) is None, 'quem escreveu apaga a sua')
    ok(any(m['args'][0] == {'id': rid_caio, 'note_id': NID} for m in ev(ana, 'geonote_resposta_apagada')), 'o autor da nota vê sumir (regra 6)')
    livre(); ana.emit('geonote_resposta_apagar', {'id': rid_beto}); ev(ana)
    ok(GeoNoteResposta.query.get(rid_beto) is None, 'o autor da nota apaga qualquer resposta dela')
    livre(); ana.emit('geonote_resposta_apagar', {'id': 999999})
    ok(any('já não existe' in x['args'][0]['msg'] for x in ev(ana, 'geonote_erro')), 'apagar o que não existe: avisa')

    # ---------------------------------------------------------------- denúncia esconde a resposta
    livre(); gil.emit('geonote_responder', {'id': NID, 'texto': 'resposta ofensiva'}); ev(gil)
    rid_ruim = GeoNoteResposta.query.filter_by(author_id=ids['Gil']).order_by(GeoNoteResposta.id.desc()).first().id
    gil.emit('denunciar', {'tipo': 'resposta', 'id': rid_ruim, 'motivo': 'assedio'})
    ok(any('próprio' in x['args'][0]['msg'] for x in ev(gil, 'erro_bazinga')), 'não dá pra denunciar a própria resposta')
    for cl in (ana, ana2, beto, caio, caio2, duda, gil): ev(cl)
    for quem in (ana, beto, caio):
        quem.emit('denunciar', {'tipo': 'resposta', 'id': rid_ruim, 'motivo': 'assedio'})
    ok(GeoNoteResposta.query.get(rid_ruim).oculta is True, '3 denúncias de pessoas diferentes escondem a resposta')
    ok(any(m['args'][0].get('id') == rid_ruim for m in ev(duda, 'geonote_resposta_apagada')), 'e a resposta some pra todo mundo (aviso em broadcast)')
    n = next(x for x in arredores(caio)['notas'] if x['id'] == NID)
    ok(all(x['id'] != rid_ruim for x in n['respostas']), 'o mapa não carrega mais a resposta escondida')
    from app import bazar
    fila = bazar.fila_de_moderacao()
    item = next((f for f in fila if f['tipo'] == 'resposta' and f['alvo_id'] == rid_ruim), None)
    ok(item is not None and item['existe'] and item['alvo']['titulo'] == 'resposta ofensiva', 'a fila de moderação do Estúdio lista a resposta denunciada')
    ok(item and item['alvo']['sub'] == 'Resposta a uma nota do mapa' and item['alvo']['oculta'] is True, 'com a descrição e o estado "escondida"')
    info = bazar.moderar(Person.query.get(ids['Ana']), 'resposta', rid_ruim, 'remover') if False else None   # Ana não é admin: ver abaixo
    from app.models import ConfigApp
    db.session.add(ConfigApp(chave='admin_ids', valor=str(ids['Duda']))); db.session.commit()
    info = bazar.moderar(Person.query.get(ids['Duda']), 'resposta', rid_ruim, 'remover')
    ok(info['nota_id'] == NID and GeoNoteResposta.query.get(rid_ruim) is None, 'o admin remove a resposta e o aviso sabe de qual nota era')

    # ---------------------------------------------------------------- consultas: não crescem com o número de notas
    def contar(fn):
        n = {'q': 0}
        def conta(*a, **k): n['q'] += 1
        event.listen(db.engine, 'before_cursor_execute', conta)
        try:
            fn()
        finally:
            event.remove(db.engine, 'before_cursor_execute', conta)
        return n['q']

    q_uma = contar(lambda: dados_do_mapa_perto(perto[0], perto[1], [ids['Ana']], viewer_id=ids['Caio']))
    for i in range(6):
        nn = GeoNote(lat=perto[0] + 0.0001 * i, lng=perto[1], text=f'nota {i}', author_id=ids['Ana'] if i % 2 else ids['Beto'], expires_at=br_now().replace(year=br_now().year + 1))
        db.session.add(nn); db.session.commit()
        db.session.add(GeoNoteResposta(note_id=nn.id, author_id=ids['Caio'], text='r')); db.session.add(GeoNoteReacao(note_id=nn.id, person_id=ids['Caio'], emoji='👍')); db.session.commit()
    db.session.expire_all()
    q_muitas = contar(lambda: dados_do_mapa_perto(perto[0], perto[1], [ids['Ana']], viewer_id=ids['Caio']))
    # nota_para_json lê o autor e o que ele equipou; o que importa é que respostas+reações não somem 1 consulta POR NOTA
    ok(q_muitas - q_uma <= 4, f'respostas e reações vêm em consultas fixas, não uma por nota ({q_uma} -> {q_muitas} com 7 notas)')

    # ---------------------------------------------------------------- copiar e apagar a nota
    ana.emit('criar_geonote', {'lat': perto[0], 'lng': perto[1] + 0.0003, 'texto': 'outra', 'respostas_modo': 'amigos'}); ev(ana)
    outra = GeoNote.query.filter_by(text='outra').first()
    ok(outra.respostas_modo == 'amigos', 'criar a nota já com o modo escolhido')
    ana.emit('criar_geonote', {'lat': perto[0], 'lng': perto[1] + 0.0004, 'texto': 'modo ruim', 'respostas_modo': 'xyz'}); ev(ana)
    ok(GeoNote.query.filter_by(text='modo ruim').first().respostas_modo is None, 'modo inválido na criação também vira padrão')
    livre(); caio.emit('geonote_reagir', {'id': NID, 'emoji': '👍', 'ativo': True}); ev(caio)
    caio.emit('copiar_geonote', {'id': NID, 'lat': perto[0], 'lng': perto[1] + 0.0005}); ev(caio)
    copia = GeoNote.query.filter_by(author_id=ids['Caio'], text='Show de graça hoje!').first()
    ok(copia is not None and GeoNoteResposta.query.filter_by(note_id=copia.id).count() == 0 and GeoNoteReacao.query.filter_by(note_id=copia.id).count() == 0,
       'a cópia de uma nota nasce sem respostas nem reações')
    ok(GeoNoteResposta.query.filter_by(note_id=NID).count() > 0 and GeoNoteReacao.query.filter_by(note_id=NID).count() > 0, '(a original continua com as dela)')
    ana.emit('apagar_geonote', {'id': NID}); ev(ana)
    ok(GeoNote.query.get(NID) is None and GeoNoteResposta.query.filter_by(note_id=NID).count() == 0 and GeoNoteReacao.query.filter_by(note_id=NID).count() == 0,
       'apagar a nota leva respostas e reações junto')
    ok(not any(GeoNoteResposta.query.filter(~GeoNoteResposta.note_id.in_([g.id for g in GeoNote.query.all()])).all()), 'nenhuma resposta órfã')

    # nota vencida: ninguém responde nem reage
    velha = GeoNote(lat=perto[0], lng=perto[1], text='velha', author_id=ids['Ana'], expires_at=br_now().replace(year=br_now().year - 1))
    db.session.add(velha); db.session.commit()
    livre(); caio.emit('geonote_responder', {'id': velha.id, 'texto': 'oi'})
    ok(any('disponível' in m for m in erros_nota(caio)), 'nota vencida não recebe resposta')

# ---------------------------------------------------------------- o cliente e os arquivos
chat = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
js = open(os.path.join(RAIZ, 'static', 'js', 'notas_mapa.js'), encoding='utf-8').read()
css = open(os.path.join(RAIZ, 'static', 'css', 'notas_mapa.css'), encoding='utf-8').read()
ok(all(s in chat for s in ("socket.on('geonote_resposta'", "socket.on('geonote_reacoes'", "socket.on('geonote_resposta_apagada'", "socket.on('geonote_erro'")),
   'o chat.html escuta todos os eventos novos do servidor')
ok(all(s in js for s in ("'geonote_responder'", "'geonote_reagir'", "'geonote_resposta_apagar'")), 'o módulo do cliente emite os três eventos de ação')
ok("notas_mapa.js" in chat and "notas_mapa.css" in chat and 'NotasMapa.iniciar(' in chat and 'NotasMapa.montar(' in chat, 'o chat.html carrega o módulo, inicia e monta a conversa em cada balão')
ok('note-respostas-modo' in chat and "respostas_modo: lerModoRespostasNota()" in chat, 'o modal da nota tem o seletor de quem pode responder e manda o modo (criar e editar)')
ok('nota-thread' in js and '.nota-thread' in css and 'nt-resp' in css, 'a conversa tem marcação e estilo')
ok("n.tipo === 'nota'" in chat and 'ib-ico.nota' in css, 'a caixa de entrada sabe abrir a notificação de nota')
ok("tipo === 'resposta'" in chat or "d.tipo === 'resposta'" in chat, 'a denúncia entende "resposta"')
ok(re.search(r"esc\(r\.autor\)", js) and re.search(r"esc\(r\.texto\)", js), 'nome e texto da resposta passam por esc() antes do innerHTML')
print()
if falhas:
    print(f'{len(falhas)} FALHA(S):')
    for f in falhas:
        print(' -', f)
    sys.exit(1)
print('TUDO OK')
