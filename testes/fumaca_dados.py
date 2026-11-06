"""Rodada 40: DADOS PESSOAIS (antes eram uma atividade compartilhada da call; a rolagem agora é de quem rolou).

Regras (app/dados.py): a expressão é lida por uma lista FECHADA (nada de eval), os limites valem (30 dados, +-999, 10 moedas), o pedido dos botões
({grupos, mod}) vira a mesma expressão e o resultado sai do SystemRandom. Eventos (app/dados_events.py), com clientes de verdade: PRIVADO por padrão
(só quem rolou recebe; nada de estado compartilhado nem de ocupar a atividade da call), PÚBLICO só se a pessoa escolher (a call recebe um aviso; um canal
de texto recebe uma mensagem normal, pelo caminho de sempre), quem só ouve não mostra pra call, sorteio só entre quem está na call.
Cliente: a matemática do 3D e do painel roda no Node (testes/dados3d_logica.js)."""
import os, re, subprocess, sys, statistics, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
os.environ['LIMITE_REQUISICOES'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, dados as regras, atividades, jogos, events, dados_events
from app.models import Role, Person, Channel, Message

falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def ler(rel): return open(os.path.join(RAIZ, rel), encoding='utf-8').read()
def ev(cli, nome=None): return [m for m in cli.get_received() if nome is None or m['name'] == nome]

# ---------- a leitura da expressão ----------
g, mod = regras.ler_expressao('2d20kh1+1d6+5')
ok(len(g) == 2 and g[0] == {'dado': 'd20', 'qtd': 2, 'sinal': 1, 'manter': ('kh', 1)} and g[1]['dado'] == 'd6' and mod == 5, 'lê 2d20kh1+1d6+5')
g, mod = regras.ler_expressao(' D8 - 1d4 - 2 ')
ok([x['sinal'] for x in g] == [1, -1] and mod == -2, 'espaços, maiúsculas e sinais de menos')
ok(regras.ler_expressao('d100')[0][0]['qtd'] == 1, 'sem número = 1 dado (o d100 segue valendo no servidor)')
for ruim, motivo in [('', 'vazia'), ('2d7', 'dado que não existe'), ('d20+', 'sinal sobrando'), ('abc', 'lixo'), ('31d6', 'dados demais'), ('2d6kh3', 'ficar com mais do que rolou'),
                     ('2d6kh0', 'ficar com zero'), ('d20+5000', 'modificador gigante'), ('__import__("os")', 'tentativa de código'), ('1d20+' * 30 + '1d20', 'comprida demais'),
                     ('2d6**2', 'potência'), ('d20/2', 'divisão'), ('0d6', 'zero dados'), ('2d20kx1', 'sufixo inventado')]:
    try:
        regras.ler_expressao(ruim); ok(False, f'expressão {motivo} ({ruim[:20]!r}) deveria ser recusada')
    except regras.ErroRolagem:
        ok(True, f'recusa expressão {motivo}')

# ---------- o pedido dos botões ----------
ok(regras.expressao_de({'grupos': [{'dado': 'd6', 'qtd': 2}, {'dado': 'd20', 'qtd': 1}], 'mod': 3}) == '2d6+1d20+3', 'botões: 2 d6 + 1 d20 com +3 viram "2d6+1d20+3"')
ok(regras.expressao_de({'grupos': [{'dado': 'd6', 'qtd': 1}, {'dado': 'd6', 'qtd': 2}], 'mod': -2}) == '3d6-2', 'o mesmo dado repetido soma')
ok(regras.expressao_de({'grupos': [{'dado': 'd4'}]}) == '1d4', 'sem quantidade = 1')
for ruim, motivo in [({'grupos': []}, 'sem dado'), ({'grupos': 'x'}, 'grupos que não é lista'), ({'grupos': [{'dado': 'd7', 'qtd': 1}]}, 'dado fora da lista'), ({'grupos': [{'dado': 'd6', 'qtd': 'x'}]}, 'quantidade lixo'),
                     ({'grupos': [{'dado': 'd6', 'qtd': 0}]}, 'quantidade zero'), ({'grupos': [{'dado': 'd6', 'qtd': -3}]}, 'quantidade negativa'), ({'grupos': ['d6']}, 'item que não é dict'),
                     ({'grupos': [{'dado': 'd6'}] * 9}, 'tipos demais'), ({'grupos': [{'dado': 'd6', 'qtd': 1}], 'mod': 'x'}, 'modificador lixo'), ({'grupos': [{'dado': 'd6', 'qtd': 10 ** 30}]}, 'quantidade gigante')]:
    try:
        regras.rolar(ruim); ok(False, f'pedido {motivo} deveria ser recusado')
    except regras.ErroRolagem:
        ok(True, f'recusa pedido dos botões: {motivo}')
try:
    regras.rolar({'grupos': [{'dado': 'd6', 'qtd': 31}]}); ok(False, '31 dados deveria ser recusado')
except regras.ErroRolagem:
    ok(True, 'mais de 30 dados é recusado mesmo vindo dos botões')
ok(regras.expressao_de({'dado': 'd20', 'modo': 'vantagem', 'mod': 3}) == '2d20kh1+3' and regras.expressao_de({'dado': 'd6', 'qtd': 3, 'mod': -2}) == '3d6-2', 'o formato antigo (um grupo) segue valendo')

# ---------- rolando ----------
e = regras.rolar({'expr': '2d20kh1+5'})
v = e['grupos'][0]['valores']
ok(e['tipo'] == 'rolagem' and e['total'] == max(v) + 5 and e['texto'] == str(max(v) + 5) and e['grupos'][0]['mantidos'] == [v.index(max(v))], 'vantagem fica com o MAIOR e o total soma o modificador')
for _ in range(60):
    x = regras.rolar({'expr': '2d20kl1'}); assert x['total'] == min(x['grupos'][0]['valores'])
ok(True, 'desvantagem fica com o MENOR (60 rolagens)')
for _ in range(60):
    x = regras.rolar({'expr': '4d6kh3'}); vv = x['grupos'][0]['valores']; assert x['total'] == sum(sorted(vv)[1:]) and len(x['grupos'][0]['mantidos']) == 3
ok(True, '4d6kh3 soma só os 3 maiores (60 rolagens)')
x = regras.rolar({'expr': '1d20-1d4-3'})
ok(x['total'] == x['grupos'][0]['valores'][0] - x['grupos'][1]['valores'][0] - 3, 'termo com sinal de menos subtrai')
x = regras.rolar({'grupos': [{'dado': 'd12', 'qtd': 2}], 'mod': 1})
ok(x['expr'] == '2d12+1' and x['total'] == sum(x['grupos'][0]['valores']) + 1 and all(1 <= n <= 12 for n in x['grupos'][0]['valores']), 'o pedido dos botões também rola')
ok(regras.rolar({'expr': '3d6', 'texto': '999', 'total': 999, 'grupos': [{'dado': 'd4', 'qtd': 1}]})['total'] <= 18, 'o cliente não decide o resultado: texto e total mandados por ele são ignorados')
for lixo in ({'expr': ['x']}, {'tipo': 'xadrez'}, {'tipo': 'rolagem', 'expr': '2d7'}):
    try:
        regras.rolar(lixo); ok(False, f'{lixo} deveria ser recusado')
    except regras.ErroRolagem:
        ok(True, f'pedido quebrado volta como erro: {str(lixo)[:40]}')
amostra = [regras.rolar({'expr': '1d20'})['total'] for _ in range(2000)]
ok(min(amostra) == 1 and max(amostra) == 20 and 9.5 < statistics.mean(amostra) < 11.5, f'd20: de 1 a 20, média {statistics.mean(amostra):.2f}')
ok({regras.rolar({'expr': '1d10'})['total'] for _ in range(400)} == set(range(1, 11)), 'd10 sai de 1 a 10 (e só isso)')
r100 = [regras.rolar({'expr': '1d100'})['total'] for _ in range(500)]
ok(min(r100) >= 1 and max(r100) <= 100 and max(r100) > 90, 'd100 vai de 1 a 100')
for d in ('d4', 'd6', 'd8', 'd10', 'd12', 'd20'):
    ok(set(regras.rolar({'expr': '1' + d})['total'] for _ in range(600)) == set(range(1, regras.DADOS[d] + 1)), f'{d} cobre todas as faces')

# ---------- moedas e sorteio ----------
m1 = regras.rolar({'tipo': 'moeda'}); ok(m1['texto'] in ('Cara', 'Coroa') and len(m1['moedas']) == 1, 'uma moeda: cara ou coroa')
m5 = regras.rolar({'tipo': 'moeda', 'qtd': 5}); ok(len(m5['moedas']) == 5 and f"{m5['moedas'].count('Cara')} cara" in m5['texto'], f'cinco moedas: {m5["texto"]}')
ok(len(regras.rolar({'tipo': 'moeda', 'qtd': 99})['moedas']) == regras.MAX_MOEDAS, 'no máximo 10 moedas')
try:
    regras.rolar({'tipo': 'moeda', 'qtd': 'x'}); ok(False, 'quantidade de moedas lixo deveria ser recusada')
except regras.ErroRolagem:
    ok(True, 'quantidade de moedas inválida é recusada')
ok({regras.sortear(['Ana', 'Beto', 'Caio'])['texto'] for _ in range(200)} == {'Ana', 'Beto', 'Caio'}, 'sorteio escolhe só entre os nomes dados e dá chance a todos')
try:
    regras.sortear([]); ok(False, 'sorteio sem ninguém deveria ser recusado')
except regras.ErroRolagem:
    ok(True, 'sorteio sem ninguém é recusado')

# ---------- o texto que vai pro canal ----------
t = regras.texto_para_canal('Ana', {'tipo': 'rolagem', 'expr': '2d12+2', 'texto': '10', 'mod': 2, 'grupos': [{'dado': 'd12', 'valores': [3, 5], 'mantidos': [0, 1], 'sinal': 1}]})
ok(t == '🎲 **Ana** rolou `2d12+2`: [3, 5] + 2 = **10**', f'mensagem da rolagem: {t}')
t = regras.texto_para_canal('Ana', {'tipo': 'rolagem', 'expr': '2d20kh1', 'texto': '17', 'mod': 0, 'grupos': [{'dado': 'd20', 'valores': [17, 4], 'mantidos': [0], 'sinal': 1}]})
ok('[17]' in t and '4' not in t.split('[17]')[1].split('=')[0], 'na vantagem o dado descartado não aparece na mensagem')
t = regras.texto_para_canal('**`<b>Ana`**', {'tipo': 'moeda', 'texto': 'Cara', 'moedas': ['Cara']})
ok('<' not in t and t.count('**') == 4 and '`' not in t, f'nome com marcação não quebra a mensagem: {t}')
ok(regras.texto_para_canal('Ana', {'tipo': 'sorteio', 'texto': 'Beto'}) == '🎯 **Ana** sorteou: **Beto**', 'mensagem do sorteio')
ok(regras.texto_para_canal('Ana', {'tipo': 'moeda', 'texto': '2 caras e 1 coroa', 'moedas': ['Cara', 'Cara', 'Coroa']}).startswith('🪙 **Ana** jogou 3 moedas'), 'mensagem das moedas')

# ---------- os eventos, com clientes de verdade ----------
app = create_app()
with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Ana', 'Beto', 'Caio', 'Fora'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id
    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl
    cl = {n: cliente(n) for n in ids}
    cl['Dono'].emit('criar_servidor_discord', {'nome': 'Casa'})
    sj = ev(cl['Dono'], 'servidor_discord_criado')[-1]['args'][0]; sid = sj['id']
    geral = [x for x in sj['channels'] if x['type'] == 'text'][0]['id']
    cl['Dono'].emit('criar_convite', {'server_id': sid}); cod = ev(cl['Dono'], 'convite_criado')[-1]['args'][0]['code']
    for n in ('Ana', 'Beto', 'Caio'):
        cl[n].emit('entrar_por_convite', {'code': cod}); ev(cl[n])
    cl['Dono'].emit('criar_canal', {'server_id': sid, 'nome': 'sala', 'tipo': 'voice'}); ev(cl['Dono'])
    cl['Dono'].emit('criar_canal', {'server_id': sid, 'nome': 'segredo', 'tipo': 'text', 'privado': True, 'membros': []}); ev(cl['Dono'])
    sala = Channel.query.filter_by(name='sala').first().id
    segredo = Channel.query.filter_by(name='segredo').first()
    segredo_id = segredo.id if segredo else None
    cl['Beto'].emit('criar_servidor_discord', {'nome': 'Outro'}); sj2 = ev(cl['Beto'], 'servidor_discord_criado')[-1]['args'][0]
    outro_canal = [x for x in sj2['channels'] if x['type'] == 'text'][0]['id']
    for n in ('Ana', 'Beto', 'Caio'):
        cl[n].emit('entrar_call', {'canal_id': sala, 'peer_id': f'p-{n.lower()}', 'usuario': n})
    for n in ids: ev(cl[n])
    for n in ('Beto', 'Caio', 'Dono'):
        cl[n].emit('entrar_canal', {'canal_id': geral}); ev(cl[n])
    dados_events.FREIO_ROLAR_S = 0; dados_events.FREIO_CANAL_S = 0
    def rolar_ana(**kw):
        base = {'grupos': [{'dado': 'd6', 'qtd': 2}], 'mod': 1}
        cl['Ana'].emit('dados_rolar', {**base, **kw})

    # --- PRIVADO é o padrão: só quem rolou recebe ---
    rolar_ana()
    ra = ev(cl['Ana'], 'dados_resultado')
    ok(len(ra) == 1, 'quem rolou recebe o resultado')
    res = ra[0]['args'][0]
    ok(res['tipo'] == 'rolagem' and res['expr'] == '2d6+1' and res['total'] == sum(res['grupos'][0]['valores']) + 1 and res['quem']['id'] == ids['Ana'] and res['id'], 'o resultado vem do servidor, completo e com id')
    ok(res['visivel'] == {'call': False, 'canal': None, 'aviso': ''}, 'sem escolher mostrar: ninguém mais vê')
    outros = [m['name'] for n in ('Beto', 'Caio', 'Dono', 'Fora') for m in ev(cl[n])]
    ok(not any(x in ('dados_resultado', 'dados_publico', 'atividade_estado', 'receber_mensagem') for x in outros), f'ninguém mais recebe nada (privado) {outros}')
    ok(atividades.da_call(str(sala)) is None, 'a rolagem não cria atividade na call (não ocupa a vaga)')
    cl['Ana'].emit('atividade_iniciar', {'canal_id': sala, 'tipo': 'xadrez'})
    ok(atividades.da_call(str(sala)) is not None, 'com os dados abertos dá pra abrir o xadrez na mesma call')
    atividades.encerrar(str(sala)); ev(cl['Ana'])
    cl['Ana'].emit('atividade_iniciar', {'canal_id': sala, 'tipo': 'dados'})
    ok(atividades.da_call(str(sala)) is None and 'dados' not in atividades.TIPOS_ATIVIDADE, 'dados não é mais um tipo de atividade da call (pedir pra iniciar não cria nada)')
    ok('dados' not in jogos.JOGOS and not hasattr(jogos, 'DadosESorteio'), 'o jogo antigo (estado compartilhado) saiu do jogos.py')

    # --- a rolagem sempre é do servidor ---
    cl['Ana'].emit('dados_rolar', {'expr': '3d6', 'texto': '18', 'total': 18, 'grupos': [{'dado': 'd4', 'qtd': 1}], 'publico': 'sim'})
    res = ev(cl['Ana'], 'dados_resultado')[0]['args'][0]
    ok(res['expr'] == '3d6' and res['total'] == sum(res['grupos'][0]['valores']), 'campos de resultado mandados pelo cliente são ignorados')
    ok(res['visivel']['call'] is False and not ev(cl['Beto'], 'dados_publico'), '"publico" só vale com true de verdade ("sim" não conta)')

    # --- PÚBLICO: a call recebe um aviso ---
    rolar_ana(publico=True)
    res = ev(cl['Ana'], 'dados_resultado')[0]['args'][0]
    rb, rc = ev(cl['Beto'], 'dados_publico'), ev(cl['Caio'], 'dados_publico')
    ok(res['visivel']['call'] is True and rb and rc, 'público: quem está na call recebe o aviso (os dois)')
    ok(rb[0]['args'][0]['id'] == res['id'] and rb[0]['args'][0]['total'] == res['total'] and rb[0]['args'][0]['quem']['nome'] == 'Ana', 'o aviso traz o MESMO resultado (id e total) e quem rolou')
    ok(set(rb[0]['args'][0]['quem']) == {'id', 'nome', 'avatar'} and 'visivel' not in rb[0]['args'][0], 'o aviso só leva quem rolou (id, nome, foto): nada da configuração de quem rolou')
    ok(not ev(cl['Ana'], 'dados_publico'), 'quem rolou não recebe o próprio aviso (já tem o resultado no painel)')
    ok(not ev(cl['Fora'], 'dados_publico') and not ev(cl['Dono'], 'dados_publico'), 'quem não está na call não recebe (nem o dono do servidor)')
    # moeda e sorteio públicos também
    cl['Ana'].emit('dados_rolar', {'tipo': 'moeda', 'qtd': 2, 'publico': True}); ev(cl['Ana'])
    rb = ev(cl['Beto'], 'dados_publico'); ok(rb and rb[0]['args'][0]['tipo'] == 'moeda' and len(rb[0]['args'][0]['moedas']) == 2, 'moeda pública chega na call')
    cl['Ana'].emit('dados_rolar', {'tipo': 'sorteio', 'publico': True}); ra = ev(cl['Ana'], 'dados_resultado')[0]['args'][0]
    rb = ev(cl['Beto'], 'dados_publico')
    ok(ra['tipo'] == 'sorteio' and ra['texto'] in ('Ana', 'Beto', 'Caio') and rb and rb[0]['args'][0]['texto'] == ra['texto'], 'sorteio público: todo mundo vê o mesmo sorteado')
    ev(cl['Caio'])

    # --- público sem estar numa call ---
    for n in ids: ev(cl[n])
    cl['Fora'].emit('dados_rolar', {'grupos': [{'dado': 'd20', 'qtd': 1}], 'publico': True})
    rf = ev(cl['Fora'], 'dados_resultado')
    ok(rf and rf[0]['args'][0]['visivel']['call'] is False, 'quem não está numa call rola e vê, mas não mostra pra ninguém')
    ok(not any(ev(cl[n], 'dados_publico') for n in ('Ana', 'Beto', 'Caio', 'Dono')), 'o público de quem está fora da call não vaza pra call dos outros')
    for n in ids: ev(cl[n])

    # --- sorteio ---
    cl['Fora'].emit('dados_rolar', {'tipo': 'sorteio'}); rf = ev(cl['Fora'])
    ok(any(m['name'] == 'dados_erro' and 'call' in m['args'][0]['msg'] for m in rf) and not any(m['name'] == 'dados_resultado' for m in rf), 'sorteio fora de call é recusado com o motivo')
    sorteados = set()
    for _ in range(30):
        cl['Ana'].emit('dados_rolar', {'tipo': 'sorteio'})
        sorteados.add(ev(cl['Ana'], 'dados_resultado')[0]['args'][0]['texto'])
    ok(sorteados == {'Ana', 'Beto', 'Caio'}, f'sorteio só entre quem está na call, e todos têm chance: {sorted(sorteados)}')
    for n in ids: ev(cl[n])

    # --- quem só ouve a call ---
    for p in events.participantes_call.get(str(sala), []):
        if p['peer_id'] == 'p-caio': p['ouvinte'] = True
    cl['Caio'].emit('dados_rolar', {'grupos': [{'dado': 'd8', 'qtd': 1}], 'publico': True})
    rc = ev(cl['Caio'], 'dados_resultado')
    ok(rc and rc[0]['args'][0]['visivel']['call'] is False and 'ouve' in rc[0]['args'][0]['visivel']['aviso'], 'quem só ouve rola, mas é avisado de que não mostra pra call')
    ok(not ev(cl['Ana'], 'dados_publico') and not ev(cl['Beto'], 'dados_publico'), 'e a call não recebe nada dele')
    for p in events.participantes_call.get(str(sala), []): p['ouvinte'] = False

    # --- publicar num canal de texto (uma mensagem normal) ---
    for n in ids: ev(cl[n])
    rolar_ana(publico=True, canal_id=geral, na_call=False)
    ra = ev(cl['Ana'])
    res = [m for m in ra if m['name'] == 'dados_resultado'][0]['args'][0]
    ok(res['visivel']['canal'] == geral and res['visivel']['call'] is False, 'resultado diz onde saiu: só no canal (a pessoa desligou o aviso na call)')
    msgs = [m for m in ev(cl['Beto'], 'receber_mensagem')]
    ok(msgs and msgs[0]['args'][0]['canal_id'] == geral and f"= **{res['total']}**" in msgs[0]['args'][0]['texto'] and msgs[0]['args'][0]['usuario'] == 'Ana'
       and msgs[0]['args'][0]['texto'].startswith('🎲 **Ana** rolou `2d6+1`'), 'quem está no canal recebe uma mensagem normal com o resultado, em nome de quem rolou')
    ok(any(m['name'] == 'receber_mensagem' for m in ra), 'quem rolou também recebe a mensagem (confirmação)')
    ok(Message.query.filter_by(channel_id=geral, person_id=ids['Ana']).count() == 1, 'a mensagem foi gravada no canal')
    ok(not ev(cl['Caio'], 'dados_publico'), 'com na_call=false a call não recebe o aviso')
    rolar_ana(publico=True, canal_id=geral)                                    # na_call padrão = liga
    ok(ev(cl['Caio'], 'dados_publico') and Message.query.filter_by(channel_id=geral).count() == 2, 'sem na_call=false: a call vê E o canal recebe')
    # canal sem acesso / de outro servidor / inventado
    for n in ids: ev(cl[n])
    antes = Message.query.count()
    if segredo_id:
        rolar_ana(publico=True, canal_id=segredo_id, na_call=False); ra = ev(cl['Ana'])
        r1 = [m for m in ra if m['name'] == 'dados_resultado'][0]['args'][0]
        ok(r1['visivel']['canal'] is False and 'sem acesso' in r1['visivel']['aviso'], 'canal privado em que a pessoa não está: não posta e avisa')
    rolar_ana(publico=True, canal_id=outro_canal, na_call=False); r2 = [m for m in ev(cl['Ana']) if m['name'] == 'dados_resultado'][0]['args'][0]
    ok(r2['visivel']['canal'] is False, 'canal de OUTRO servidor (em que ela não está) não recebe')
    for lixo in ('x', 0, -5, [1], {'a': 1}, 10 ** 12):
        rolar_ana(publico=True, canal_id=lixo, na_call=False); ev(cl['Ana'])
    ok(Message.query.count() == antes, 'canal_id inventado ou quebrado nunca vira mensagem')
    # privado nunca posta, mesmo mandando canal_id
    rolar_ana(canal_id=geral); ev(cl['Ana'])
    ok(Message.query.count() == antes and not ev(cl['Beto'], 'receber_mensagem'), 'com o olho fechado, canal_id é ignorado: nada vai pro canal')
    # freio da mensagem no canal
    dados_events.FREIO_CANAL_S = 60; dados_events._ultimo_canal.clear()
    rolar_ana(publico=True, canal_id=geral, na_call=False); ev(cl['Ana'])
    rolar_ana(publico=True, canal_id=geral, na_call=False); r3 = [m for m in ev(cl['Ana']) if m['name'] == 'dados_resultado'][0]['args'][0]
    ok(r3['visivel']['canal'] is False and 'Calma' in r3['visivel']['aviso'] and Message.query.filter_by(channel_id=geral).count() == 3, 'o canal tem freio (uma mensagem de rolagem a cada poucos segundos)')
    dados_events.FREIO_CANAL_S = 0
    # canal de anúncios: a mensagem passa pela regra do canal (quem não pode escrever lá não escreve pelos dados)
    cl['Dono'].emit('criar_canal', {'server_id': sid, 'nome': 'avisos', 'tipo': 'anuncios'}); ev(cl['Dono'])
    anuncios = Channel.query.filter_by(name='avisos').first()
    if anuncios:
        antes = Message.query.count()
        rolar_ana(publico=True, canal_id=anuncios.id, na_call=False); ev(cl['Ana'])
        ok(Message.query.count() == antes, 'canal de anúncios: quem não tem permissão de escrever não escreve pelos dados')

    # --- freio e payload quebrado ---
    dados_events.FREIO_ROLAR_S = 5; dados_events._ultimo.clear()
    rolar_ana(); rolar_ana()
    ok(len(ev(cl['Ana'], 'dados_resultado')) == 1, 'duas rolagens coladas da mesma pessoa: a segunda é ignorada')
    dados_events.FREIO_ROLAR_S = 0
    for lixo in ('lixo', 123, None, [], {'grupos': 'x'}, {'grupos': [{'dado': 'd99'}]}, {'expr': '__import__("os")'}, {'tipo': 'xadrez'}, {'tipo': 'moeda', 'qtd': 'x'}):
        cl['Ana'].emit('dados_rolar', lixo)
    saida = ev(cl['Ana'])
    ok(not any(m['name'] == 'dados_resultado' for m in saida) and any(m['name'] == 'dados_erro' for m in saida), 'pedidos quebrados voltam como erro, sem derrubar e sem rolar')
    cl['Ana'].emit('dados_rolar', {'grupos': [{'dado': 'd6', 'qtd': 1}]}); ok(ev(cl['Ana'], 'dados_resultado'), 'depois do lixo o servidor continua respondendo')
    cl['Ana'].emit('dados_rolar', {'grupos': [{'dado': 'd6', 'qtd': 99}]})
    ok(any(m['name'] == 'dados_erro' and '30' in m['args'][0]['msg'] for m in ev(cl['Ana'])), 'mais de 30 dados: o servidor recusa com o limite')
    app.test_client()
    sem = socketio.test_client(app); sem.get_received()
    sem.emit('dados_rolar', {'grupos': [{'dado': 'd6', 'qtd': 1}]}); ok(not sem.get_received(), 'sem login o servidor não responde')

    # --- a escolha do olho mora na conta (preferência) ---
    cl['Ana'].emit('salvar_preferencias', {'dados_publico': True}); pr = ev(cl['Ana'], 'preferencias_carregadas')
    ok(pr and pr[-1]['args'][0]['prefs']['dados_publico'] is True, 'o olho aberto é salvo na conta e volta pras abas')
    cl['Ana'].emit('salvar_preferencias', {'dados_publico': 'sim'}); pr = ev(cl['Ana'], 'preferencias_carregadas')
    ok(db.session.get(Person, ids['Ana']).preferencias and '"dados_publico": true' in db.session.get(Person, ids['Ana']).preferencias.replace('":true', '": true'), 'valor que não é booleano é descartado (o salvo continua)')

# ---------- o que o cliente promete ----------
chat = ler('app/templates/chat.html'); dj = ler('app/static/js/dados.js'); d3 = ler('app/static/js/dados3d.js'); ati = ler('app/static/js/atividades.js')
aj = ler('app/static/js/atividades_jogos.js'); dcss = ler('app/static/css/dados.css'); cfg = ler('app/static/js/config_usuario.js')
ok('js/dados.js' in chat and 'css/dados.css' in chat and chat.index('js/dados3d.js') < chat.index('js/dados.js'), 'chat.html carrega o dados3d antes do painel de dados')
ok('Dados.iniciar(' in chat and "if (tipo === 'dados') Dados.abrir()" in chat, 'o chat liga o painel e a atividade "Dados" só ABRE o painel pessoal')
ok("{ tipo: 'dados'" in ati and 'local: true' in ati.split("tipo: 'dados'")[1].split('\n')[0], 'no catálogo de atividades os dados são "locais" (não começam uma atividade da call)')
ok('Dados3D' not in aj and 'corpoDados' not in aj and 'd-add' not in aj and "'dados-limpar'" not in aj and 'bandeja' not in aj, 'o atividades_jogos.js não tem mais o código dos dados')
ok('AtividadesJogos.depois' not in ati, 'o painel de atividades não chama mais o gancho dos dados')
ok('data-dd="olho"' in dj and 'data-dd="config"' in dj and 'fa-eye-slash' in dj and 'dados_publico' in chat, 'o título tem o olho (privado/público) e a engrenagem (onde mostrar)')
ok(all(f'.dd-{d}' in dcss for d in ('d4', 'd6', 'd8', 'd10', 'd12', 'd20')) and all(f"{d}:" in dj for d in ('d4', 'd6', 'd8', 'd10', 'd12', 'd20')), 'os seis dados têm forma e cor próprias')
ok('data-dd="rolar"' in dj and 'data-dd="limpar"' in dj and 'dd-total' in dj and 'data-dd="mod"' in dj, 'Rolar, Limpar, o ± do modificador e o Total estão no painel')
ok('aj-expr' not in dj and 'type="text"' not in dj and 'vantagem' not in dj.lower(), 'sem campo de expressão e sem vantagem/desvantagem na tela (o servidor ainda lê a gramática)')
ok('Math.random' not in dj and 'Math.random' not in d3.split('function preparar')[0], 'o painel não sorteia nada: o resultado é só o do servidor')
ok("socket.emit('dados_rolar'" in dj and "'dados_resultado'" in dj and "'dados_publico'" in dj and "'dados_erro'" in dj, 'o painel fala com o servidor pelos eventos dos dados')
ok('esc(' in dj and 'innerHTML' in dj and '${e.quem.nome}' not in dj and 'C.esc(e.quem.nome)' in dj, 'nome de quem rolou passa por esc() antes de virar HTML')
ok('eval(' not in dj + d3 and 'new Function' not in dj + d3, 'sem eval')
ok('eval(' not in d3 and 'innerHTML' not in d3, 'dados3d.js não usa eval nem innerHTML')
ok('prefers-reduced-motion' in d3 and 'cancelAnimationFrame' in d3 and 'prefers-reduced-motion' in dcss, 'respeita "reduzir movimento" e para o laço')
ok('requestAnimationFrame(quadro)' in d3 and 'A.raf = 0' in d3, 'o laço só roda enquanto anima')
ok('dados_publico' in cfg and 'aoMudar' in cfg and 'salvar,' in cfg, 'o config_usuario guarda o olho na conta e avisa o painel')
ok(not re.search(r'\.dd[^{]*\{[^}]*transition:[^}]*\b(width|height|left|top|margin)\b', dcss), 'o CSS dos dados só anima transform/opacity')
saida = subprocess.run(['node', os.path.join(RAIZ, 'testes', 'dados3d_logica.js')], capture_output=True, text=True, encoding='utf-8')
falhas_node = [l for l in saida.stdout.splitlines() if l.startswith('FALHA')]
ok(saida.returncode == 0 and not falhas_node, 'a geometria 3D, a animação e as contas do painel passam nos testes do Node (%d verificações)' % sum(1 for l in saida.stdout.splitlines() if l.startswith(('OK', 'FALHA'))))
for l in falhas_node: print('     ', l)

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
