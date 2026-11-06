"""Rodada 40: soundboard RÁPIDO. O relato de produção era "você ouve do seu lado, do outro demora uns 15 s, toca uma vez e nunca mais".
A causa que o código mostrava: cada toque ia ao banco ANTES de sair (pessoa, som, membro: em produção cada consulta é uma viagem até o Neon), o ouvinte só
baixava o arquivo (mais duas consultas) NA HORA do primeiro toque, e havia um freio de 2,5 s que descartava o toque em silêncio.

Aqui: o toque não faz NENHUMA consulta ao banco (som vem do cache, nome vem da lista da call), todo toque chega a quem está na call (também vários seguidos,
de pessoas diferentes), `soundboard_aquecer` avisa a call pra baixar os sons antes do 1º toque, o arquivo servido sai do cache sem consulta e nenhuma decisão
velha fica no cache (apagar, renomear e a decisão do Guardião valem na hora). Dois clientes de verdade (socketio.test_client), banco em memória, sem rede."""
import io, os, struct, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
os.environ['LIMITE_REQUISICOES'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from sqlalchemy import event
from app import create_app, db, socketio, acervo, guardiao, events
from app import acervo_events
from app.models import Role, Person, Channel, AcervoItem, ConfigApp

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def ler(rel): return open(os.path.join(RAIZ, rel), encoding='utf-8').read()

def wav(segundos, taxa=22050):
    n = int(segundos * taxa)
    pcm = b''.join(struct.pack('<h', int(8000 * (1 if (i // 40) % 2 else -1))) for i in range(n))
    return b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, taxa, taxa * 2, 2, 16) + b'data' + struct.pack('<I', len(pcm)) + pcm

guardiao._chamar = lambda partes: {'acao': 'liberar', 'categoria': 'outro', 'gravidade': 1, 'motivo': 'teste'}
guardiao.ligado = lambda: True

consultas = {'n': 0}
def contar():
    consultas['n'] = 0

with app.app_context():
    db.create_all()
    @event.listens_for(db.engine, 'before_cursor_execute')
    def _conta(conn, cursor, statement, parameters, context, executemany):
        consultas['n'] += 1

    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Ana', 'Beto', 'Caio', 'Fora'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(ConfigApp(chave='admin_ids', valor=str(ids['Dono']))); db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc
    S = {n: cliente(n) for n in ids}
    cl = {n: S[n][0] for n in S}; web = {n: S[n][1] for n in S}

    cl['Dono'].emit('criar_servidor_discord', {'nome': 'Casa'})
    sj = ev(cl['Dono'], 'servidor_discord_criado')[-1]['args'][0]; sid = sj['id']
    cl['Dono'].emit('criar_convite', {'server_id': sid}); cod = ev(cl['Dono'], 'convite_criado')[-1]['args'][0]['code']
    for n in ('Ana', 'Beto', 'Caio'):
        cl[n].emit('entrar_por_convite', {'code': cod}); ev(cl[n])
    cl['Dono'].emit('criar_canal', {'server_id': sid, 'nome': 'sala', 'tipo': 'voice'}); ev(cl['Dono'])
    sala = Channel.query.filter_by(name='sala').first().id
    cl['Beto'].emit('criar_servidor_discord', {'nome': 'Outro'}); sj2 = ev(cl['Beto'], 'servidor_discord_criado')[-1]['args'][0]
    cl['Beto'].emit('criar_canal', {'server_id': sj2['id'], 'nome': 'sala2', 'tipo': 'voice'}); ev(cl['Beto'])
    sala2 = Channel.query.filter_by(name='sala2').first().id

    def enviar(nome, dados, nome_item='Som', escopo='pessoa', server_id=None):
        form = {'tipo': 'som', 'escopo': escopo, 'nome': nome_item, 'arquivo': (io.BytesIO(dados), 'a.wav')}
        if server_id: form['server_id'] = str(server_id)
        resp = web[nome].post('/api/acervo/upload', data=form, content_type='multipart/form-data', headers={'X-Requested-With': 'fetch'})
        return resp.status_code, (resp.get_json() or {})

    _, j = enviar('Ana', wav(1), 'Buzina'); buzina = AcervoItem.query.get(j['item']['id'])
    _, j = enviar('Ana', wav(1.2), 'Aplauso'); aplauso = AcervoItem.query.get(j['item']['id'])
    _, j = enviar('Dono', wav(1), 'Gongo', escopo='servidor', server_id=sid); gongo = AcervoItem.query.get(j['item']['id'])
    ok(buzina.status == aplauso.status == gongo.status == 'aprovado', 'sons de teste aprovados (pessoal e do servidor)')

    # todo mundo na call (Ana, Beto, Caio); a Fora não
    for n in ('Ana', 'Beto', 'Caio'):
        cl[n].emit('entrar_call', {'canal_id': sala, 'peer_id': f'p-{n.lower()}', 'usuario': n}); ev(cl[n])
    for n in ('Ana', 'Beto', 'Caio', 'Fora'): ev(cl[n])
    acervo_events._ultimo.clear(); acervo_events._historico.clear(); acervo_events._ultimo_aquecer.clear(); acervo.invalidar_item()

    # ================= o toque NÃO vai ao banco =================
    cl['Ana'].emit('soundboard_aquecer', {'canal_id': sala, 'ids': [buzina.id, aplauso.id, gongo.id]})
    rb, rc, ra = ev(cl['Beto'], 'soundboard_precarregar'), ev(cl['Caio'], 'soundboard_precarregar'), ev(cl['Ana'], 'soundboard_precarregar')
    ok(rb and rc and set(rb[0]['args'][0]['ids']) == {buzina.id, aplauso.id, gongo.id} and rb[0]['args'][0]['por_id'] == ids['Ana'],
       'quem abre o soundboard avisa a call: os outros recebem os ids pra baixar antes do 1º toque')
    ok(not ra, 'quem avisou não recebe o próprio aviso (ele já tem os sons)')
    contar(); cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': buzina.id}); n_toque = consultas['n']
    rb = ev(cl['Beto'], 'soundboard_tocou'); rc = ev(cl['Caio'], 'soundboard_tocou'); ra = ev(cl['Ana'], 'soundboard_tocou')
    ok(rb and rc and ra, 'o som chega pra quem está na call, inclusive quem tocou')
    ok(n_toque == 0, f'o toque (som já aquecido) faz ZERO consultas ao banco (fez {n_toque})')
    p0 = rb[0]['args'][0]
    ok(p0['item_id'] == buzina.id and p0['por_nome'] == 'Ana' and p0['nome'] == 'Buzina' and p0['dur_ms'] and p0['por_id'] == ids['Ana'], 'o aviso leva som, nome, duração e quem tocou')

    # som que nunca foi aquecido: no máximo UMA consulta (a do cache frio), e a partir daí zero
    acervo.invalidar_item(); acervo_events._ultimo.clear(); db.session.expunge_all()
    contar(); cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': aplauso.id}); frio = consultas['n']
    ok(ev(cl['Beto'], 'soundboard_tocou') and frio <= 1, f'cache frio: o 1º toque faz no máximo 1 consulta (fez {frio})')
    acervo_events._ultimo.clear(); contar(); cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': aplauso.id})
    ok(consultas['n'] == 0 and ev(cl['Beto'], 'soundboard_tocou'), 'o 2º toque do mesmo som: zero consultas')
    ev(cl['Ana']); ev(cl['Caio'])

    # ================= toques seguidos: TODOS chegam, de várias pessoas =================
    acervo_events._ultimo.clear(); acervo_events._historico.clear()
    velho = acervo_events.INTERVALO_PESSOA_S; acervo_events.INTERVALO_PESSOA_S = 0
    for it in (buzina, aplauso, gongo): acervo.som_info(it.id)             # os sons já foram aquecidos (é o que o soundboard_aquecer faz quando alguém abre o painel)
    contar(); recebidos = {'Beto': 0, 'Caio': 0, 'Ana': 0}
    for i in range(8):
        quem = ('Ana', 'Beto', 'Caio')[i % 3]
        item = (buzina, aplauso)[i % 2] if quem == 'Ana' else gongo         # Beto e Caio só tocam o som do servidor (os pessoais são da Ana)
        cl[quem].emit('soundboard_tocar', {'canal_id': sala, 'item_id': item.id})
    for n in ('Beto', 'Caio', 'Ana'):
        recebidos[n] = len(ev(cl[n], 'soundboard_tocou'))
    ok(recebidos['Beto'] == recebidos['Caio'] == recebidos['Ana'] == 8, f'8 toques seguidos de 3 pessoas: todos chegam em todo mundo ({recebidos})')
    ok(consultas['n'] == 0, f'os 8 toques fizeram {consultas["n"]} consultas ao banco (esperado: 0)')
    acervo_events.INTERVALO_PESSOA_S = velho

    # o freio de verdade: dois toques colados da MESMA pessoa = o 2º é ignorado (e só dele); outra pessoa não é afetada
    acervo_events._ultimo.clear(); acervo_events._historico.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': buzina.id}); ev(cl['Beto']); ev(cl['Ana']); ev(cl['Caio'])
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': buzina.id})
    ok(not ev(cl['Beto'], 'soundboard_tocou'), 'dois toques colados da mesma pessoa: o segundo é ignorado')
    cl['Beto'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': gongo.id})
    ok(ev(cl['Caio'], 'soundboard_tocou'), 'o freio é por pessoa: o Beto toca logo depois da Ana')
    ok(acervo_events.INTERVALO_PESSOA_S < 1.0, f'o intervalo por pessoa é curto ({acervo_events.INTERVALO_PESSOA_S} s; era 2,5 s e parecia o botão parado)')
    ev(cl['Ana']); ev(cl['Beto']); ev(cl['Caio'])
    time.sleep(acervo_events.INTERVALO_PESSOA_S + 0.05)
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': buzina.id})
    ok(ev(cl['Beto'], 'soundboard_tocou'), 'passado o intervalo, a mesma pessoa toca de novo (não é "uma vez e nunca mais")')

    # ================= regras que continuam valendo =================
    for n in ('Ana', 'Beto', 'Caio'): ev(cl[n])
    acervo_events._ultimo.clear()
    cl['Fora'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': gongo.id})
    ok(not any(ev(cl[n], 'soundboard_tocou') for n in ('Ana', 'Beto', 'Caio')), 'quem não está na call não toca')
    cl['Beto'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': buzina.id}); rb = ev(cl['Beto'])
    ok(any(m['name'] == 'acervo_erro' for m in rb) and not ev(cl['Ana'], 'soundboard_tocou'), 'o som pessoal dos outros não é meu (e a mensagem não revela de quem é)')
    cl['Beto'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': 99999}); rb = ev(cl['Beto'])
    ok(any(m['name'] == 'acervo_erro' for m in rb), 'id que não existe volta como erro, sem derrubar')
    cl['Beto'].emit('soundboard_tocar', 'lixo'); cl['Beto'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': 'x'}); cl['Beto'].emit('soundboard_tocar', {'canal_id': {'a': 1}, 'item_id': [1]}); ev(cl['Beto'])
    ok(True, 'payload quebrado não derruba o servidor')
    # o som do servidor não toca na call de OUTRO servidor
    cl['Beto'].emit('sair_call', {'canal_id': sala, 'peer_id': 'p-beto'}); ev(cl['Beto'])
    cl['Beto'].emit('entrar_call', {'canal_id': sala2, 'peer_id': 'p-beto2', 'usuario': 'Beto'}); ev(cl['Beto'])
    acervo_events._ultimo.clear()
    cl['Beto'].emit('soundboard_tocar', {'canal_id': sala2, 'item_id': gongo.id}); rb = ev(cl['Beto'])
    ok(any(m['name'] == 'acervo_erro' and 'servidor' in m['args'][0]['msg'] for m in rb) and not any(m['name'] == 'soundboard_tocou' for m in rb), 'som de um servidor só toca nas calls dele')
    cl['Beto'].emit('sair_call', {'canal_id': sala2, 'peer_id': 'p-beto2'}); ev(cl['Beto'])
    cl['Beto'].emit('entrar_call', {'canal_id': sala, 'peer_id': 'p-beto', 'usuario': 'Beto'}); ev(cl['Beto'])
    for n in ('Ana', 'Caio'): ev(cl[n])
    # toque num canal em que o socket NÃO está
    cl['Caio'].emit('soundboard_tocar', {'canal_id': sala2, 'item_id': gongo.id}); ok(not ev(cl['Beto'], 'soundboard_tocou'), 'tocar numa call em que não estou não faz nada')
    # ouvinte
    for p in events.participantes_call.get(str(sala), []):
        if p['peer_id'] == 'p-caio': p['ouvinte'] = True
    acervo_events._ultimo.clear()
    cl['Caio'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': gongo.id}); ok(any(m['name'] == 'acervo_erro' for m in ev(cl['Caio'])), 'quem só ouve não toca')
    acervo_events._ultimo_aquecer.clear(); ev(cl['Ana']); ev(cl['Beto'])
    cl['Caio'].emit('soundboard_aquecer', {'canal_id': sala, 'ids': [gongo.id]}); ok(not ev(cl['Ana'], 'soundboard_precarregar'), 'quem só ouve também não manda os outros baixarem sons')
    for p in events.participantes_call.get(str(sala), []): p['ouvinte'] = False
    acervo_events._historico[str(sala)] = [time.monotonic()] * acervo_events.TETO_CALL[0]; acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': buzina.id}); ok(any('Muitos sons' in m['args'][0].get('msg', '') for m in ev(cl['Ana'], 'acervo_erro')), 'o teto da call (20 sons a cada 20 s) segue valendo e AVISA quem foi barrado')
    acervo_events._historico.clear()

    # ================= o aviso de aquecimento é validado no servidor =================
    acervo_events._ultimo_aquecer.clear(); ev(cl['Ana']); ev(cl['Beto']); ev(cl['Caio'])
    cl['Beto'].emit('soundboard_aquecer', {'canal_id': sala, 'ids': [buzina.id, gongo.id, 99999, 'x', None, -3, [1]]})
    rc = ev(cl['Caio'], 'soundboard_precarregar')
    ok(rc and rc[0]['args'][0]['ids'] == [gongo.id], 'o aviso só leva sons que a pessoa PODE tocar (o pessoal da Ana, id solto e lixo ficam de fora)')
    cl['Beto'].emit('soundboard_aquecer', {'canal_id': sala, 'ids': [gongo.id]}); ok(not ev(cl['Caio'], 'soundboard_precarregar'), 'o aviso tem freio (não vira inundação de downloads)')
    acervo_events._ultimo_aquecer.clear()
    cl['Beto'].emit('soundboard_aquecer', {'canal_id': sala, 'ids': list(range(1, 400))}); rc = ev(cl['Caio'], 'soundboard_precarregar')
    ok(all(len(m['args'][0]['ids']) <= acervo_events.MAX_AQUECER for m in rc), f'o aviso tem teto de {acervo_events.MAX_AQUECER} sons')
    acervo_events._ultimo_aquecer.clear()
    for n in ('Ana', 'Beto', 'Caio'): ev(cl[n])
    cl['Fora'].emit('soundboard_aquecer', {'canal_id': sala, 'ids': [gongo.id]}); ok(not any(ev(cl[n], 'soundboard_precarregar') for n in ('Ana', 'Beto', 'Caio')), 'quem não está na call não aciona o aviso')
    cl['Beto'].emit('soundboard_aquecer', 'lixo'); cl['Beto'].emit('soundboard_aquecer', {'canal_id': sala, 'ids': 'x'}); ev(cl['Beto']); ok(True, 'aviso com payload quebrado não derruba')

    # ================= o cache nunca segura decisão velha =================
    acervo_events._ultimo.clear(); acervo.invalidar_item()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': aplauso.id}); ev(cl['Ana']); ev(cl['Beto'])        # entra no cache
    cl['Ana'].emit('acervo_renomear', {'id': aplauso.id, 'nome': 'Palmas', 'emoji': '👏'}); ev(cl['Ana'])
    acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': aplauso.id}); rb = ev(cl['Beto'], 'soundboard_tocou')
    ok(rb and rb[0]['args'][0]['nome'] == 'Palmas' and rb[0]['args'][0]['emoji'] == '👏', 'renomear vale no próximo toque (o cache é refeito)')
    acervo_events._ultimo.clear()
    db.session.expire_all()
    acervo.aplicar_decisao(aplauso.id, 'confirmar')          # o Guardião/um responsável recusou
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': aplauso.id}); ra = ev(cl['Ana'])
    ok(any(m['name'] == 'acervo_erro' for m in ra) and not ev(cl['Beto'], 'soundboard_tocou'), 'som recusado pelo responsável PARA de tocar na hora (mesmo estando no cache)')
    acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': buzina.id}); ev(cl['Ana']); ev(cl['Beto'])        # entra no cache
    cl['Ana'].emit('acervo_apagar', {'id': buzina.id}); ev(cl['Ana'])
    acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': buzina.id}); ra = ev(cl['Ana'])
    ok(any(m['name'] == 'acervo_erro' for m in ra) and not ev(cl['Beto'], 'soundboard_tocou'), 'som apagado PARA de tocar na hora')
    # som em análise nunca entra no cache nem toca
    guardiao._chamar = lambda partes: (_ for _ in ()).throw(guardiao.ErroIA('fora do ar'))
    _, j = enviar('Ana', wav(1.4), 'Analise'); analise = AcervoItem.query.get(j['item']['id'])
    guardiao._chamar = lambda partes: {'acao': 'liberar', 'categoria': 'outro', 'gravidade': 1, 'motivo': 'teste'}
    ok(analise.status == 'em_analise', 'som sem IA fica em análise')
    acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': analise.id}); ra = ev(cl['Ana'])
    ok(any(m['name'] == 'acervo_erro' for m in ra) and analise.id not in acervo._META, 'som em análise não toca nem pra quem enviou, e nunca entra no cache')
    acervo.aplicar_decisao(analise.id, 'liberar')
    acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': analise.id}); ok(ev(cl['Beto'], 'soundboard_tocou'), 'liberado pelo responsável, passa a tocar na hora')

    # ================= o arquivo sai do cache, sem consulta =================
    acervo.invalidar_item()
    db.session.expunge_all()          # em produção cada pedido tem a própria sessão: sem isso o item já "conhecido" pelo teste esconde a consulta
    contar(); r1 = web['Beto'].get(f'/api/acervo/{gongo.id}/arquivo'); frio = consultas['n']
    ok(r1.status_code == 200 and r1.mimetype in ('audio/wav', 'audio/x-wav', 'audio/wave') and len(r1.data) > 1000, 'o arquivo do som é entregue a quem está logado')
    ok(frio <= 1, f'1º download (cache frio): no máximo 1 consulta (fez {frio}; antes eram 2: pessoa e arquivo)')
    contar(); r2 = web['Caio'].get(f'/api/acervo/{gongo.id}/arquivo')
    ok(r2.status_code == 200 and consultas['n'] == 0 and r2.data == r1.data, f'2º download (de outra pessoa): zero consultas ({consultas["n"]}) e o mesmo arquivo')
    etag = r2.headers.get('ETag')
    r3 = web['Caio'].get(f'/api/acervo/{gongo.id}/arquivo', headers={'If-None-Match': etag})
    ok(r3.status_code == 304, 'quem já tem o arquivo recebe 304 (nem baixa de novo)')
    ok('immutable' in r2.headers.get('Cache-Control', '') and 'private' in r2.headers.get('Cache-Control', ''), 'aprovado: o navegador guarda pra sempre (e só no aparelho de quem baixou)')
    ok(app.test_client().get(f'/api/acervo/{gongo.id}/arquivo').status_code in (401, 403), 'sem login não baixa, nem do cache')
    ok(web['Beto'].get('/api/acervo/99999/arquivo').status_code == 404, 'arquivo que não existe = 404')
    # em análise: só o dono e os responsáveis (e nunca vai pro cache)
    ok(web['Ana'].get(f'/api/acervo/{analise.id}/arquivo').status_code == 200, 'o dono baixa o próprio som')
    acervo.invalidar_item(analise.id)
    db.session.expire_all()
    analise2 = AcervoItem.query.get(analise.id); analise2.status = 'em_analise'; db.session.commit(); acervo.invalidar_item(analise.id)
    ok(web['Beto'].get(f'/api/acervo/{analise.id}/arquivo').status_code == 404, 'som em análise: outra pessoa leva 404')
    ok(web['Ana'].get(f'/api/acervo/{analise.id}/arquivo').status_code == 200 and analise.id not in acervo._BYTES, 'o dono baixa o dele em análise, e isso NÃO entra no cache')
    ok(web['Dono'].get(f'/api/acervo/{analise.id}/arquivo').status_code == 200, 'um responsável (admin) baixa o que está em análise')
    # apagar tira do cache de bytes
    web['Beto'].get(f'/api/acervo/{gongo.id}/arquivo'); ok(gongo.id in acervo._BYTES, 'depois do download o arquivo aprovado está no cache de bytes')
    cl['Dono'].emit('acervo_apagar', {'id': gongo.id}); ev(cl['Dono'])
    ok(gongo.id not in acervo._BYTES and web['Beto'].get(f'/api/acervo/{gongo.id}/arquivo').status_code == 404, 'apagar o som tira o arquivo do cache na hora (404)')
    # tetos do cache de bytes
    acervo.invalidar_item()
    class Falso:
        def __init__(self, i, n): self.id, self.dados, self.mime, self.sha, self.status = i, b'x' * n, 'audio/wav', 'h%d' % i, 'aprovado'
    for i in range(1, acervo.MAX_ITENS_BYTES + 20): acervo.guardar_arquivo(Falso(900000 + i, 1000))
    ok(len(acervo._BYTES) <= acervo.MAX_ITENS_BYTES, f'cache de arquivos tem teto de itens ({len(acervo._BYTES)} <= {acervo.MAX_ITENS_BYTES})')
    acervo.invalidar_item()
    for i in range(1, 12): acervo.guardar_arquivo(Falso(910000 + i, 3 * 1024 * 1024))
    ok(sum(len(v[1].dados) for v in acervo._BYTES.values()) <= acervo.MAX_BYTES_TOTAL and acervo._bytes_total[0] == sum(len(v[1].dados) for v in acervo._BYTES.values()),
       'cache de arquivos tem teto de bytes e a conta fecha')
    acervo.invalidar_item()
    for i in range(1, acervo.MAX_META + 40):
        acervo._guardar_meta({'id': 800000 + i}, time.monotonic())
    ok(len(acervo._META) <= acervo.MAX_META, 'cache de sons tem teto')
    acervo.invalidar_item()

# ================= o que o cliente promete =================
chat = ler('app/templates/chat.html'); ac = ler('app/static/js/acervo.js'); sj_ = ler('app/static/js/sons.js'); at = ler('app/static/js/atividades.js')
ok('soundboard_aquecer' in ac and 'soundboard_precarregar' in ac and 'Sons.precarregar' in ac, 'o cliente avisa a call dos sons que mostra e baixa os dos outros')
ok('precarregar' in sj_ and 'resume' in sj_, 'sons.js pré-carrega e espera o AudioContext acordar em vez de perder o toque')
ok("'sb_pessoal'" not in at and "'sb_servidor'" not in at, 'o soundboard NÃO é mais uma atividade (saiu do catálogo)')
ok('id="btn-main-soundboard"' in chat and 'Acervo.alternarSoundboard' in chat, 'o soundboard tem botão na barra da call (como o do Discord)')

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
