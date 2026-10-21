"""Rodada 29: ordem dos servidores (barra lateral) com pastinhas e DMs fixadas, tudo na CONTA.
Regra 4: id de servidor alheio, de quem não é amigo, nome/cor fora do formato e pasta repetida são descartados NO SERVIDOR.
Regra 6: salvar avisa TODAS as abas da pessoa (e só ela). Servidor novo (ou que a ordem salva não conhece) cai no fim."""
import os, sys, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Friendship
from app import ordem

app = create_app()
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]

def prefs(cli, chave):
    """O último valor de `chave` que chegou em preferencias_carregadas (None se nenhuma trouxe)."""
    achados = [m['args'][0][chave] for m in ev(cli, 'preferencias_carregadas') if chave in m['args'][0]]
    return achados[-1] if achados else None

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Carol', 'Dani', 'Eva'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))
    db.session.add(Friendship(requester_id=ids['Eva'], addressee_id=ids['Ana'], status='accepted'))
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Carol'], status='pending'))      # ainda não é amiga
    db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc)
        return cl, fc

    ana, fana = cliente('Ana'); ana2, _ = cliente('Ana'); beto, _ = cliente('Beto')
    for cl in (ana, ana2, beto): cl.get_received()

    def criar(cli, nome):
        cli.emit('criar_servidor_discord', {'nome': nome})
        return [m for m in ev(cli, 'servidor_discord_criado')][-1]['args'][0]['id']

    s1, s2, s3 = criar(ana, 'Um'), criar(ana, 'Dois'), criar(ana, 'Três')
    s_beto = criar(beto, 'Do Beto')
    for cl in (ana, ana2, beto): cl.get_received()
    pessoa = lambda nome='Ana': (db.session.expire_all(), Person.query.get(ids[nome]))[1]

    # ---------- sem nada salvo: ordem padrão, completa ----------
    novo, _ = cliente('Ana')
    lote = ev(novo, 'preferencias_carregadas')[0]['args'][0]
    padrao = lote['ordem_servidores']
    ok(sorted(padrao) == sorted([s1, s2, s3]) and all(isinstance(x, int) for x in padrao), 'conta que nunca ordenou: o connect manda todos os servidores, soltos')
    ok(lote['ordem_dms'] == [], '...e nenhuma DM fixada')
    ok(pessoa().ordem_servidores is None and pessoa().ordem_dms is None, 'coluna anulável: NULL até a pessoa mexer')
    novo.disconnect()

    # ---------- salvar a ordem ----------
    ana.emit('salvar_ordem_servidores', {'layout': [s3, s1, s2]})
    a1, a2, b = prefs(ana, 'ordem_servidores'), prefs(ana2, 'ordem_servidores'), prefs(beto, 'ordem_servidores')
    ok(a1 == [s3, s1, s2] and a2 == [s3, s1, s2], 'as DUAS abas da Ana recebem a ordem nova (regra 6)')
    ok(b is None, '...e o Beto não recebe nada dela')
    ok(json.loads(pessoa().ordem_servidores) == [s3, s1, s2], 'a ordem fica gravada na conta')
    novo, fnovo = cliente('Ana')
    ok(prefs(novo, 'ordem_servidores') == [s3, s1, s2], 'um aparelho novo já conecta com a ordem salva')
    html = fnovo.get('/chat').get_data(as_text=True)
    m = re.search(r'const ordemServidoresIniciais = (\[.*\]);', html)
    ok(m and json.loads(m.group(1)) == [s3, s1, s2], 'o /chat já traz a ordem no HTML (sem piscar)')
    novo.disconnect()

    # ---------- regra 4: o que não é da pessoa é descartado ----------
    ana.emit('salvar_ordem_servidores', {'layout': [s2, s_beto, 999999, s1, s3, True, '1', None, 3.5, {'x': 1}]})
    ok(prefs(ana, 'ordem_servidores') == [s2, s1, s3], 'servidor alheio, id que não existe, bool, texto, lixo: tudo descartado')
    ana.emit('salvar_ordem_servidores', {'layout': [s1, s1, s2, s1, s3, s3]})
    ok(prefs(ana, 'ordem_servidores') == [s1, s2, s3], 'repetido aparece uma vez só')
    ana.emit('salvar_ordem_servidores', {'layout': [s1]})
    ok(prefs(ana, 'ordem_servidores') == [s1, s2, s3], 'quem a lista deixou de fora volta pro FIM (nunca some da barra)')
    ok(json.loads(pessoa().ordem_servidores) == [s1, s2, s3], '...e o que fica gravado também está completo')
    ev(ana2)

    # ---------- pastas ----------
    ana.emit('salvar_ordem_servidores', {'layout': [s3, {'pasta': 'abc123xy', 'nome': 'Jogos', 'cor': '#FF8800', 'ids': [s1, s2]}]})
    lay = prefs(ana, 'ordem_servidores')
    ok(lay == [s3, {'pasta': 'abc123xy', 'nome': 'Jogos', 'cor': '#ff8800', 'ids': [s1, s2]}], 'pasta criada: nome, cor (em minúsculas) e os dois servidores')
    ok(prefs(ana2, 'ordem_servidores') == lay, '...e a outra aba vê a pasta')
    ok(json.loads(pessoa().ordem_servidores) == lay, '...gravada na conta')

    ana.emit('salvar_ordem_servidores', {'layout': [s3, {'pasta': 'abc123xy', 'nome': '  Jogos ‮  da\n  galera  ', 'cor': 'vermelho', 'ids': [s2, s1]}]})
    p = prefs(ana, 'ordem_servidores')[1]
    ok(p['nome'] == 'Jogos da galera', 'renomear: caractere invisível/que inverte o texto sai e os espaços se acertam')
    ok(p['cor'] == '#5865f2', 'cor que não é #rrggbb vira a cor padrão')
    ok(p['ids'] == [s2, s1], '...e a ordem dentro da pasta é a escolhida')
    ana.emit('salvar_ordem_servidores', {'layout': [s3, {'pasta': 'abc123xy', 'nome': 'x' * 80, 'cor': '#112233', 'ids': [s2, s1]}]})
    ok(len(prefs(ana, 'ordem_servidores')[1]['nome']) == 24, 'nome da pasta tem teto de 24 caracteres')
    ana.emit('salvar_ordem_servidores', {'layout': [s3, {'pasta': 'abc123xy', 'nome': '   ', 'cor': '#112233', 'ids': [s2, s1]}]})
    ok(prefs(ana, 'ordem_servidores')[1]['nome'] == 'Pasta', 'nome vazio vira "Pasta"')
    ana.emit('salvar_ordem_servidores', {'layout': [s3, {'pasta': 'abc123xy', 'nome': 12345, 'cor': ['#fff'], 'ids': [s2, s1]}]}); ev(ana)
    ok(pessoa() and json.loads(pessoa().ordem_servidores)[1]['nome'] == 'Pasta', 'nome/cor de tipo errado não quebra nada')

    # pasta com 1 servidor se desfaz (o sobrevivente fica no lugar dela)
    ana.emit('salvar_ordem_servidores', {'layout': [s3, {'pasta': 'abc123xy', 'nome': 'Sozinha', 'cor': '#112233', 'ids': [s2]}, s1]})
    ok(prefs(ana, 'ordem_servidores') == [s3, s2, s1], 'pasta com 1 servidor se desfaz e ele fica onde a pasta estava')
    ana.emit('salvar_ordem_servidores', {'layout': [{'pasta': 'abc123xy', 'nome': 'Meio alheia', 'cor': '#112233', 'ids': [s1, s_beto]}, s2, s3]})
    ok(prefs(ana, 'ordem_servidores') == [s1, s2, s3], 'pasta que só fica com 1 depois de descartar o alheio também se desfaz')
    ana.emit('salvar_ordem_servidores', {'layout': [{'pasta': 'abc123xy', 'nome': 'Vazia', 'cor': '#112233', 'ids': []}, s2, s1, s3]})
    ok(prefs(ana, 'ordem_servidores') == [s2, s1, s3], 'pasta vazia some')
    ana.emit('salvar_ordem_servidores', {'layout': [s3, {'pasta': 'abc123xy', 'nome': 'Jogos', 'cor': '#112233', 'ids': [s1, s2]}]}); ev(ana)

    # pasta repetida, id de pasta inválido, servidor em duas pastas
    ana.emit('salvar_ordem_servidores', {'layout': [
        {'pasta': 'aaaa1111', 'nome': 'A', 'cor': '#111111', 'ids': [s1, s2]},
        {'pasta': 'aaaa1111', 'nome': 'Clone', 'cor': '#222222', 'ids': [s3]},
        {'pasta': 'Inválido!', 'nome': 'B', 'cor': '#333333', 'ids': [s3, s1]},
        {'pasta': 'bbbb2222', 'nome': 'C', 'cor': '#444444', 'ids': [s1, s3]}]})
    lay = prefs(ana, 'ordem_servidores')
    ok(lay[0] == {'pasta': 'aaaa1111', 'nome': 'A', 'cor': '#111111', 'ids': [s1, s2]}, 'a primeira pasta vale')
    ok(lay[1:] == [s3], 'pasta com id repetido ou inválido é ignorada; servidor que já estava em outra pasta não entra de novo')
    todos = [x for it in lay for x in (it['ids'] if isinstance(it, dict) else [it])]
    ok(sorted(todos) == sorted([s1, s2, s3]), 'todo servidor aparece exatamente uma vez no layout')

    # tetos
    muitos = [{'pasta': f'pasta{i:04d}', 'nome': str(i), 'cor': '#123456', 'ids': [s1, s2]} for i in range(100)]
    ana.emit('salvar_ordem_servidores', {'layout': muitos + [s3] * 1000}); ev(ana)
    ok(len(json.loads(pessoa().ordem_servidores)) <= ordem.MAX_PASTAS + 3, 'um layout gigante não passa dos tetos (30 pastas)')

    # servidor sem nada a ver / payload inválido
    antes = pessoa().ordem_servidores
    for lixo in ('abc', 5, None, [1, 2], {'layout': 'x'}, {'layout': None}, {}, {'ids': [s1]}):
        ana.emit('salvar_ordem_servidores', lixo)
    ok(not ev(ana, 'erro_bazinga') and pessoa().ordem_servidores == antes, 'payload inválido é ignorado: sem erro, sem gravar')

    # sem mudança: não regrava nem acorda as outras abas
    ana.emit('salvar_ordem_servidores', {'layout': [s2, s1, s3]}); ev(ana); ev(ana2)
    ana.emit('salvar_ordem_servidores', {'layout': [s2, s1, s3]})
    ok(prefs(ana, 'ordem_servidores') == [s2, s1, s3] and prefs(ana2, 'ordem_servidores') is None, 'repetir a mesma ordem só devolve pra quem mandou (a outra aba não é acordada)')

    # ---------- servidor novo e servidor que saiu ----------
    ana.emit('salvar_ordem_servidores', {'layout': [s3, {'pasta': 'abc123xy', 'nome': 'Jogos', 'cor': '#112233', 'ids': [s1, s2]}]}); ev(ana); ev(ana2)
    s4 = criar(ana, 'Quatro')
    novo, _ = cliente('Ana')
    lay = prefs(novo, 'ordem_servidores')
    ok(lay and lay[-1] == s4 and lay[0] == s3 and isinstance(lay[1], dict), 'servidor criado depois cai no FIM e a ordem/pasta salvas continuam')
    novo.disconnect()
    # a Ana entra no servidor do Beto (direto no banco, como o convite faria)
    from app.models import Server
    srv_b = Server.query.get(s_beto); srv_b.members.append(Person.query.get(ids['Ana'])); db.session.commit()
    novo, _ = cliente('Ana')
    lay = prefs(novo, 'ordem_servidores')
    ok(set(lay[-2:]) == {s4, s_beto} and lay[0] == s3, 'servidor em que ela entrou depois também vai pro fim (junto com o outro novo), sem mexer no que estava salvo')
    novo.disconnect()
    ana.emit('sair_do_servidor', {'server_id': s_beto}); ev(ana)
    novo, _ = cliente('Ana')
    lay = prefs(novo, 'ordem_servidores')
    flat = [x for it in lay for x in (it['ids'] if isinstance(it, dict) else [it])]
    ok(s_beto not in flat, 'servidor de que ela saiu some do layout')
    novo.disconnect()
    # dissolver pasta cujo membro saiu: a Beto-like situação aqui é simulada tirando s2 da pasta direto no banco
    srv2 = Server.query.get(s2); srv2.members.remove(Person.query.get(ids['Ana'])); db.session.commit()
    novo, _ = cliente('Ana')
    lay = prefs(novo, 'ordem_servidores')
    ok(not any(isinstance(it, dict) for it in lay) and s1 in lay and s2 not in lay,
       'quando um membro da pasta sai do servidor, a pasta que ficou com 1 se desfaz na leitura (o outro continua solto)')
    novo.disconnect()

    # ---------- DMs fixadas ----------
    ana.emit('salvar_ordem_dms', {'fixas': [ids['Dani'], ids['Carol'], ids['Eva'], ids['Beto'], ids['Eva'], 'x', None, True]})
    a1, a2, b = prefs(ana, 'ordem_dms'), prefs(ana2, 'ordem_dms'), prefs(beto, 'ordem_dms')
    ok(a1 == [ids['Eva'], ids['Beto']] and a2 == a1, 'fixadas: só amigo de verdade (aceito), sem repetição, na ordem escolhida, nas duas abas')
    ok(b is None, '...e o Beto não recebe nada')
    ok(json.loads(pessoa().ordem_dms) == [ids['Eva'], ids['Beto']], 'gravado na conta')
    ana.emit('salvar_ordem_dms', {'fixas': [ids['Beto'], ids['Eva']]})
    ok(prefs(ana, 'ordem_dms') == [ids['Beto'], ids['Eva']], 'reordenar as fixadas vale')
    ana.emit('salvar_ordem_dms', {'fixas': [ids['Ana']]})
    ok(prefs(ana, 'ordem_dms') == [], 'a própria pessoa (Anotações) não é uma fixada: Anotações já é sempre a primeira')
    ana.emit('salvar_ordem_dms', {'fixas': [ids['Beto'], ids['Eva']]}); ev(ana); ev(ana2)
    ana.emit('salvar_ordem_dms', {'fixas': [ids['Beto'], ids['Eva']]})
    ok(prefs(ana, 'ordem_dms') == [ids['Beto'], ids['Eva']] and prefs(ana2, 'ordem_dms') is None, 'repetir o mesmo não acorda a outra aba')
    antes = pessoa().ordem_dms
    for lixo in ('abc', 5, None, [1], {'fixas': 'x'}, {'fixas': None}, {}, {'layout': [1]}):
        ana.emit('salvar_ordem_dms', lixo)
    ok(not ev(ana, 'erro_bazinga') and pessoa().ordem_dms == antes, 'payload inválido de DM é ignorado')
    ana.emit('salvar_ordem_dms', {'fixas': list(range(1, 400))}); ev(ana)
    ok(len(ordem.normalizar_fixas(list(range(1, 400)))) <= ordem.MAX_FIXAS, 'teto de fixadas')
    ana.emit('salvar_ordem_dms', {'fixas': [ids['Beto'], ids['Eva']]}); ev(ana); ev(ana2)

    # o /chat já nasce com as fixadas no topo e marcadas
    html = fana.get('/chat').get_data(as_text=True)
    pos_beto = html.find(f'id="dm-{ids["Beto"]}"'); pos_eva = html.find(f'id="dm-{ids["Eva"]}"')
    ok(0 < pos_beto < pos_eva, 'no HTML as fixadas vêm na ordem escolhida (Beto antes da Eva)')
    ok(re.search(rf'id="dm-{ids["Beto"]}"[^>]*data-fixa="1"', html) and re.search(rf'id="dm-{ids["Eva"]}"[^>]*data-fixa="1"', html), '...e levam data-fixa="1"')
    ana.emit('salvar_ordem_dms', {'fixas': [ids['Eva']]}); ev(ana)
    html = fana.get('/chat').get_data(as_text=True)
    ok(html.find(f'id="dm-{ids["Eva"]}"') < html.find(f'id="dm-{ids["Beto"]}"'), 'com só a Eva fixada ela vem na frente do Beto')
    ok(not re.search(rf'id="dm-{ids["Beto"]}"[^>]*data-fixa', html), '...e o Beto deixa de ter a marca')
    m = re.search(r'const dmsFixasIniciais = (\[.*\]);', html)
    ok(m and json.loads(m.group(1)) == [ids['Eva']], 'o HTML também traz a lista de fixadas pro script')

    # amizade desfeita: a fixada não aparece mais (a lista só tem amigos) e não quebra nada
    f = Friendship.query.filter_by(requester_id=ids['Eva']).first(); f.status = 'blocked'; db.session.commit()
    html = fana.get('/chat').get_data(as_text=True)
    ok(f'id="dm-{ids["Eva"]}"' not in html, 'amiga bloqueada some da lista mesmo estando fixada')

    # ---------- funções puras ----------
    ok(ordem.normalizar_layout('{"quebrado', [1, 2]) == [] and ordem.normalizar_layout(None, [1]) == [], 'JSON quebrado/NULL = layout vazio')
    ok(ordem.completar_layout([2], [1, 2, 3]) == [2, 1, 3], 'completar: o que falta vai pro fim, na ordem padrão')
    ok(ordem.cor_de_pasta('#ABCDEF') == '#abcdef' and ordem.cor_de_pasta('#abc') == ordem.COR_PASTA_PADRAO and ordem.cor_de_pasta('red; background:url(x)') == ordem.COR_PASTA_PADRAO,
       'cor: só #rrggbb (a cor vai num style="" do navegador de quem tem a pasta)')
    ok(ordem.nome_de_pasta('<img src=x onerror=1>') == '<img src=x onerror=1>'[:24], 'o nome é texto puro (o cliente escapa); aqui só o tamanho e os invisíveis importam')

    # ---------- o que o código promete ----------
    migr = open(os.path.join(RAIZ, '..', 'atualizar_banco.py'), encoding='utf-8').read()
    ok('"ordem_servidores TEXT"' in migr and '"ordem_dms TEXT"' in migr and '# 37.' in migr, 'as colunas estão no atualizar_banco.py (passo 37)')
    mod = open(os.path.join(RAIZ, 'models.py'), encoding='utf-8').read()
    ok('ordem_servidores = db.Column(db.Text, nullable=True)' in mod and 'ordem_dms = db.Column(db.Text, nullable=True)' in mod, 'colunas anuláveis no modelo (o boot cria sem DEFAULT)')

    # ---------- o cliente (texto do código: o arrasto em si foi visto no navegador) ----------
    js = open(os.path.join(RAIZ, 'static', 'js', 'ordem.js'), encoding='utf-8').read()
    css = open(os.path.join(RAIZ, 'static', 'css', 'ordem.css'), encoding='utf-8').read()
    html = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
    ok('SEGURAR_MS = 350' in js and 'JUNTAR_MS = 2400' in js, 'segurar ~350 ms pra pegar e ~2,4 s em cima de outro pra juntar (2 a 3 s do pedido)')
    ok("'pointerdown'" in js and "'pointermove'" in js and "'pointerup'" in js and "'pointercancel'" in js, 'pointer events (mouse, toque e caneta)')
    ok("addEventListener('touchmove'" in js and '{ passive: false }' in js, 'no toque, depois de segurar, a rolagem do navegador é cancelada (touchmove não passivo)')
    ok(js.count('.innerHTML') <= 4 and 'textContent' in js, 'nome da pasta e do servidor entram por textContent/atributo (poucos innerHTML, todos com texto fixo)')
    for linha in js.splitlines():
        if '.innerHTML' in linha and '=' in linha:
            ok('nome' not in linha.split('=', 1)[1] and 'esc(' not in linha, 'innerHTML só com texto fixo: ' + linha.strip()[:70])
    ok('prefers-reduced-motion' in css and 'reduzido()' in js, 'prefers-reduced-motion desliga o balanço e o FLIP')
    ok('Alt' in js or 'altKey' in js, 'alternativa por teclado: Alt + setas')
    ok("'contextmenu'" in js and 'Tirar da pasta' in js and 'Mover para cima' in js, 'menu de contexto com Mover e Tirar da pasta')
    ok('aria-live' in js, 'o que é movido pelo teclado é anunciado (aria-live)')
    ok("ordem.js" in html and "ordem.css" in html and 'Ordem.iniciar(' in html and 'Ordem.desenharServidores(' in html, 'o chat.html liga o Ordem (CSS, JS, iniciar e a barra de servidores)')
    ok('Ordem.subirDM(card)' in html and 'Ordem.htmlMenuDM' in html and 'Ordem.acaoMenuDM' in html, 'mensagem nova na DM e o menu do contato passam pelo Ordem')
    ok(re.search(r'(?<!\.)animation:[^;]*(left|top|width|height)', css) is None, 'o CSS novo não anima left/top/width/height (só transform/opacity)')
    nov = open(os.path.join(RAIZ, 'novidades.py'), encoding='utf-8').read()
    ok("'id': 29" in nov and 'pastinhas' in nov.lower(), 'novidade 29 no topo do app/novidades.py')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
