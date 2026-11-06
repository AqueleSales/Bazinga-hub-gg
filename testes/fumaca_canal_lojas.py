"""Canal de LOJAS (tipo de canal `lojas`), Rodada 35: tipo da lista fechada (inventado é recusado), só quem gerencia canais cria, ninguém escreve nele (nem o dono),
a vitrine mostra as lojas de quem está no servidor + as parceiras (nunca loja de fora), só o que o Bazar já mostraria (aberta, sem moderação, sem banido, com produto), busca/categoria/
origem, canal privado e de outro servidor não vazam, nada de Pix/carteira no payload, número de consultas fixo, regra 6 (a vitrine pede de novo quando o Bazar muda) e o que o cliente promete."""
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
from app import create_app, db, socketio, cargos, bazar, lojas_canal, lojas_canal_events
from app import bazar_events
from app.models import Role, Person, Server, Channel, Message, BazarLoja, BazarProduto, BazarBanimento, br_now

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


with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('Dono', 'Ana', 'Beto', 'Cris', 'Duda', 'Edu', 'Fora', 'Parceira'):
        p = Person(name=nome, email=f'{nome.lower()}@x', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=30))
        db.session.add(p); db.session.commit(); ids[nome.lower()] = p.id

    srv = Server(name='Vila', owner_id=ids['dono']); db.session.add(srv); db.session.commit()
    for n in ('dono', 'ana', 'beto', 'cris', 'duda', 'edu'):
        srv.members.append(db.session.get(Person, ids[n]))
    geral = Channel(name='geral', server_id=srv.id, channel_type='text'); db.session.add(geral); db.session.commit()
    SID = srv.id
    outro = Server(name='Outra vila', owner_id=ids['fora']); db.session.add(outro); db.session.commit()
    outro.members.append(db.session.get(Person, ids['fora'])); db.session.commit()
    canal_outro = Channel(name='lojas', server_id=outro.id, channel_type='lojas'); db.session.add(canal_outro); db.session.commit()

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl

    def emitir(cl, nome, dados=None):
        bazar_events._ultimo.clear(); lojas_canal_events._ultimo.clear()
        cl.emit(nome, dados or {})
        return ev(cl)

    def msg_erro(rec):
        return next((m['args'][0]['msg'] for m in rec if m['name'] in ('lojas_canal_erro', 'erro_bazinga', 'bazar_erro')), None)

    def vitrine(rec):
        return next((m['args'][0] for m in rec if m['name'] == 'lojas_canal'), None)

    dono, ana, beto, cris, duda, edu, fora, parceira = (cliente(n) for n in ('dono', 'ana', 'beto', 'cris', 'duda', 'edu', 'fora', 'parceira'))

    def abrir_loja(cl, nome, categoria='comida', produtos=('Brigadeiro',), preco=4500):
        emitir(cl, 'bazar_salvar_loja', {'nome': nome, 'categoria': categoria, 'cor': 'vinho', 'pix_chave': 'segredo@exemplo.com', 'pix_nome': 'Fulano', 'pix_cidade': 'Brasilia',
                                         'descricao': f'Descrição de {nome}'})
        for p in produtos:
            emitir(cl, 'bazar_salvar_produto', {'nome': p, 'descricao': 'bom', 'preco_cent': preco, 'tipo': 'fisico', 'estoque': 10})

    # ---------------- 1. o tipo ----------------
    ok('lojas' in cargos.TIPOS_CANAL and cargos.TIPOS_CANAL['lojas']['familia'] == 'texto' and 'lojas' in cargos.TIPOS_TEXTO, '`lojas` é um tipo da lista fechada, da família texto')
    ok(cargos.tipo_valido('lojas') == 'lojas' and cargos.tipo_valido('lojas-falso') is None and cargos.tipo_valido('LOJAS') is None, 'tipo inventado (ou com outra caixa) continua recusado')
    dono.emit('criar_canal', {'server_id': SID, 'nome': 'vitrine', 'tipo': 'lojas-falso'}); rec = ev(dono)
    ok(Channel.query.filter_by(server_id=SID, name='vitrine').count() == 0, 'criar canal com tipo inventado não cria nada')
    ana.emit('criar_canal', {'server_id': SID, 'nome': 'vitrine', 'tipo': 'lojas'}); ev(ana)
    ok(Channel.query.filter_by(server_id=SID, name='vitrine').count() == 0, 'membro comum (sem gerenciar canais) não cria canal de lojas')
    dono.emit('criar_canal', {'server_id': SID, 'nome': 'vitrine', 'tipo': 'lojas'}); rec = ev(dono)
    canal = Channel.query.filter_by(server_id=SID, name='vitrine').first()
    ok(canal is not None and canal.channel_type == 'lojas', 'quem gerencia canais cria o canal de lojas')
    CID = canal.id
    pv = cargos.TIPOS_CANAL['lojas']
    # trocar o tipo só dentro da família
    dono.emit('editar_canal', {'canal_id': CID, 'tipo': 'voice'}); ev(dono)
    ok(db.session.get(Channel, CID).channel_type == 'lojas', 'não dá pra transformar o canal de lojas em voz')

    # ---------------- 2. ninguém escreve ----------------
    n0 = Message.query.count()
    for cl in (dono, ana):
        cl.emit('entrar_canal', {'canal_id': CID}); cl.get_received()
        cl.emit('enviar_mensagem', {'canal_id': CID, 'texto': 'oi pessoal'})
    erros = ev(dono) + ev(ana)
    ok(Message.query.count() == n0, 'nem o dono nem membro nenhum escreve no canal de lojas')
    ok(any('vitrine' in (m['args'][0].get('msg', '')) for m in erros if m['name'] == 'erro_bazinga'), '...e a mensagem explica por quê')
    ok(cargos.checar_envio(db.session.get(Person, ids['dono']), srv, canal, True)[0] is False, 'nem com anexo (a trava vale pra qualquer envio)')
    ok(cargos.checar_envio(db.session.get(Person, ids['dono']), srv, geral, False)[0] is True, 'canal de texto comum segue livre')

    # ---------------- 3. a vitrine ----------------
    ok('não está disponível' in (msg_erro(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID})) or '') or vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID})) is not None, 'preparo')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID}))
    ok(d is not None and d['itens'] == [] and d['total'] == 0 and d['canal_id'] == CID, 'sem loja nenhuma: vitrine vazia (o cliente explica como aparecer)')
    abrir_loja(ana, 'Doces da Ana', 'comida', ('Brigadeiro', 'Beijinho'))
    abrir_loja(beto, 'Arte do Beto', 'arte', ('Poster',), 9000)
    abrir_loja(fora, 'Loja de Fora', 'comida', ('Pizza',))                       # NÃO é do servidor
    abrir_loja(parceira, 'Mega Parceira', 'digital', ('Cartão',))                # vai virar parceira
    BazarLoja.query.filter_by(owner_id=ids['parceira']).first().porte = 'grande'; db.session.commit()
    emitir(cris, 'bazar_salvar_loja', {'nome': 'Sem Produto', 'categoria': 'moda', 'cor': 'vinho', 'pix_chave': 'cris@exemplo.com', 'pix_nome': 'Cris', 'pix_cidade': 'Brasilia'})   # sem produto
    # PADRÃO (Rodada 39): só as lojas das pessoas do servidor; as parceiras só entram se quem gerencia o canal ligar a opção
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID}))
    ok(sorted(i['nome'] for i in d['itens']) == ['Arte do Beto', 'Doces da Ana'] and d['parceiras'] is False, 'padrão: só as lojas do servidor, parceiras de fora')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'origem': 'parceiras'}))
    ok('Mega Parceira' not in [i['nome'] for i in d['itens']], 'pedir "parceiras" com a opção desligada não traz nada de parceira')
    emitir(ana, 'editar_canal', {'canal_id': CID, 'opcoes': {'lojas_parceiras': True}})
    ok('Mega Parceira' not in [i['nome'] for i in vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID}))['itens']], 'membro comum não liga a opção (precisa gerenciar canais)')
    emitir(dono, 'editar_canal', {'canal_id': CID, 'opcoes': {'lojas_parceiras': 'sim', 'inventada': True}})
    ok(not cargos.opcoes_do_canal(Channel.query.get(CID)), 'opção com valor que não é bool ou chave inventada é descartada')
    emitir(dono, 'editar_canal', {'canal_id': CID, 'opcoes': {'lojas_parceiras': True}})
    ok(cargos.opcoes_do_canal(Channel.query.get(CID)) == {'lojas_parceiras': True}, 'o dono liga "incluir as lojas parceiras"')
    ok(cargos.opcoes_do_canal(geral) == {} and not geral.opcoes, 'canal de texto comum não ganha opção de lojas')
    emitir(dono, 'editar_canal', {'canal_id': geral.id, 'opcoes': {'lojas_parceiras': True}}); ok(not cargos.opcoes_do_canal(Channel.query.get(geral.id)), '... mesmo se mandarem')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID}))
    nomes = sorted(i['nome'] for i in d['itens'])
    ok(d['parceiras'] is True and nomes == ['Arte do Beto', 'Doces da Ana', 'Mega Parceira'], f'com a opção ligada a vitrine tem as lojas dos membros e as parceiras: {nomes}')
    ok('Loja de Fora' not in nomes, 'loja de quem NÃO está no servidor não aparece')
    ok('Sem Produto' not in nomes, 'loja sem produto à vista não ocupa a vitrine')
    por = {i['nome']: i for i in d['itens']}
    ok(por['Doces da Ana']['origem'] == 'servidor' and por['Mega Parceira']['origem'] == 'parceira', 'cada loja diz se é do servidor ou parceira')
    ok([p['nome'] for p in por['Doces da Ana']['produtos']] and por['Doces da Ana']['total_produtos'] == 2, 'os produtos vêm no cartão (pra "Pedir")')
    ok(d['total'] == 3 and d['categorias'][0]['id'] == 'arte' and {c['id']: c['qtd'] for c in d['categorias']}['comida'] == 1, 'contagem por categoria bate')
    txt = str(d).lower()
    ok('segredo@' not in txt and 'pix_chave' not in txt and 'wallet' not in txt and 'entrega' not in {k for i in d['itens'] for p in i['produtos'] for k in p}, 'NADA de Pix, carteira nem texto privado de entrega no payload')
    ok(set(por['Doces da Ana']) == set(bazar.loja_json(BazarLoja.query.filter_by(owner_id=ids['ana']).first(), []).keys()) | {'produtos', 'total_produtos', 'origem'}, 'é o mesmo recorte público do feed do Bazar')

    # filtros
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'origem': 'servidor'}))
    ok(sorted(i['nome'] for i in d['itens']) == ['Arte do Beto', 'Doces da Ana'], 'filtro "do servidor"')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'origem': 'parceiras'}))
    ok([i['nome'] for i in d['itens']] == ['Mega Parceira'], 'filtro "parceiras"')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'categoria': 'arte'}))
    ok([i['nome'] for i in d['itens']] == ['Arte do Beto'], 'filtro por categoria')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'categoria': 'inventada'}))
    ok(d['total'] == 3 and d['categoria'] == '', 'categoria inventada é ignorada (não esvazia nem quebra)')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'busca': 'poster'}))
    ok([i['nome'] for i in d['itens']] == ['Arte do Beto'], 'busca acha pelo produto')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'busca': 'doces'}))
    ok([i['nome'] for i in d['itens']] == ['Doces da Ana'], 'busca acha pelo nome da loja')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'busca': 'Beijinho'}))
    ok([p['nome'] for p in d['itens'][0]['produtos']] == ['Beijinho'], 'busca por produto mostra o produto que bateu')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'busca': '%'}))
    ok(d['total'] == 0, 'curinga do LIKE na busca não casa com tudo')
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'origem': 'x', 'busca': 'a' * 500, 'seed': {'x': 1}}))
    ok(d is not None, 'origem inventada, busca enorme e seed estranha não derrubam')
    a = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'seed': 'abc'}))
    b = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'seed': 'abc'}))
    ok([i['id'] for i in a['itens']] == [i['id'] for i in b['itens']], 'a ordem é estável com a mesma seed (a tela não pula)')

    # o que o Bazar esconde, a vitrine esconde
    loja_ana = BazarLoja.query.filter_by(owner_id=ids['ana']).first()
    loja_ana.aberta = False; db.session.commit()
    ok('Doces da Ana' not in [i['nome'] for i in vitrine(emitir(beto, 'lojas_canal_pedir', {'canal_id': CID}))['itens']], 'loja FECHADA some da vitrine')
    loja_ana.aberta = True; loja_ana.oculta = True; db.session.commit()
    ok('Doces da Ana' not in [i['nome'] for i in vitrine(emitir(beto, 'lojas_canal_pedir', {'canal_id': CID}))['itens']], 'loja escondida pela moderação some')
    loja_ana.oculta = False; db.session.add(BazarBanimento(person_id=ids['ana'], motivo='teste', por_id=ids['dono'], ate=None)); db.session.commit()
    ok('Doces da Ana' not in [i['nome'] for i in vitrine(emitir(beto, 'lojas_canal_pedir', {'canal_id': CID}))['itens']], 'loja de quem foi banido do Bazar some')
    BazarBanimento.query.delete(); db.session.commit()
    prod = BazarProduto.query.filter_by(loja_id=loja_ana.id).all()
    for p in prod:
        p.oculta = True
    db.session.commit()
    ok('Doces da Ana' not in [i['nome'] for i in vitrine(emitir(beto, 'lojas_canal_pedir', {'canal_id': CID}))['itens']], 'produto escondido não conta (loja sem produto à vista some)')
    for p in prod:
        p.oculta = False
    db.session.commit()
    ok('Doces da Ana' in [i['nome'] for i in vitrine(emitir(beto, 'lojas_canal_pedir', {'canal_id': CID}))['itens']], '...e tudo volta quando o Bazar volta')

    # ---------------- 4. permissão (regra 4) ----------------
    ok('não está disponível' in (msg_erro(emitir(fora, 'lojas_canal_pedir', {'canal_id': CID})) or ''), 'quem NÃO está no servidor não abre a vitrine')
    ok('não está disponível' in (msg_erro(emitir(ana, 'lojas_canal_pedir', {'canal_id': geral.id})) or ''), 'canal que não é de lojas não vira vitrine (nem o geral)')
    ok('não está disponível' in (msg_erro(emitir(ana, 'lojas_canal_pedir', {'canal_id': canal_outro.id})) or ''), 'canal de lojas de OUTRO servidor não abre pra quem não é de lá')
    for lixo in (None, 'x', -1, 99999, [1], {'a': 1}):
        rec = emitir(ana, 'lojas_canal_pedir', {'canal_id': lixo})
        ok(msg_erro(rec) is not None and vitrine(rec) is None, f'id de canal {lixo!r} é recusado sem derrubar')
    ok(emitir(ana, 'lojas_canal_pedir', 'lixo') is not None, 'payload que não é objeto também não derruba')
    # a lista é sempre do servidor DO CANAL, não do que o cliente diz
    d = vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': CID, 'server_id': outro.id}))
    ok('Loja de Fora' not in [i['nome'] for i in d['itens']], 'um server_id mandado pelo cliente não muda de qual servidor é a vitrine')
    # canal privado: só quem foi convidado
    priv = Channel(name='vip', server_id=SID, channel_type='lojas', is_private=True); db.session.add(priv); db.session.commit()
    priv.allowed_members.append(db.session.get(Person, ids['ana'])); db.session.commit()
    ok(vitrine(emitir(ana, 'lojas_canal_pedir', {'canal_id': priv.id})) is not None, 'canal de lojas PRIVADO abre pra quem foi convidado')
    ok('não está disponível' in (msg_erro(emitir(beto, 'lojas_canal_pedir', {'canal_id': priv.id})) or ''), '...e não abre pra membro que não foi')
    # sobrescrita por cargo: tirar "ver canal" do Membro esconde a vitrine
    from app.models import ChannelOverwrite
    canal.sobrescrita = True
    db.session.add(ChannelOverwrite(channel_id=CID, role_id=None, allow=0, deny=cargos.BIT_CANAL['ver_canal'])); db.session.commit()
    cargos.invalidar(SID)
    ok('não está disponível' in (msg_erro(emitir(beto, 'lojas_canal_pedir', {'canal_id': CID})) or ''), 'sobrescrita por cargo que nega "ver canal" esconde a vitrine também')
    ChannelOverwrite.query.delete(); canal.sobrescrita = False; db.session.commit(); cargos.invalidar(SID)
    ok(vitrine(emitir(beto, 'lojas_canal_pedir', {'canal_id': CID})) is not None, '...e volta quando a regra sai')

    # ---------------- 5. consultas fixas ----------------
    for i in range(8):
        pe = Person(name=f'Lojista{i}', email=f'l{i}@x', role_id=r.id, username=f'lojista{i}', created_at=br_now() - timedelta(days=30)); db.session.add(pe); db.session.commit()
        srv.members.append(pe)
        l = BazarLoja(owner_id=pe.id, nome=f'Loja {i}', categoria='outros', porte='micro', cor='ambar', toldo='vermelho', pix_chave='x@x.com', pix_nome='x', pix_cidade='x'); db.session.add(l); db.session.commit()
        db.session.add(BazarProduto(loja_id=l.id, nome=f'Item {i}', preco_cent=1000, tipo='fisico', ativo=True)); db.session.commit()
    sqls = []

    def espiar(conn, cursor, statement, parameters, context, executemany):
        sqls.append(statement)
    ana_p = db.session.get(Person, ids['ana'])
    event.listen(db.engine, 'before_cursor_execute', espiar)
    d = lojas_canal.listar(db.session.get(Channel, CID))
    event.remove(db.engine, 'before_cursor_execute', espiar)
    ok(d['total'] >= 10 and len(sqls) <= 5, f'listar {d["total"]} lojas custa só {len(sqls)} consultas (não cresce com o número de lojas)')

    # ---------------- 6. regra 6 ----------------
    ev(beto); ev(ana)
    emitir(cris, 'bazar_salvar_produto', {'nome': 'Bolsa', 'descricao': 'x', 'preco_cent': 2000, 'tipo': 'fisico', 'estoque': 3})
    ok(any(m['name'] == 'bazar_mudou' for m in ev(beto) + ev(ana)), 'loja/produto novo avisa todo mundo com bazar_mudou (a vitrine aberta pede de novo)')
    chat = ler('templates', 'chat.html')
    ok("socket.on('bazar_mudou', () => { Bazar.mudou(); LojasCanal.mudou(); })" in chat, 'o chat.html religa o bazar_mudou à vitrine')
    ok('LojasCanal.mudou()' in chat.split("socket.on('membro_entrou_servidor'")[1][:900], '...e quem entra no servidor também atualiza a vitrine aberta')

    # ---------------- 7. o que o cliente promete ----------------
    js, cj = ler('static', 'js', 'lojas_canal.js'), ler('static', 'js', 'cargos.js')
    ok("lojas: { fam: 'texto'" in cj and "lojas: ['ver_canal']" in cj, 'cargos.js conhece o tipo (família texto, só "ver canal" nas permissões do canal)')
    ok('LojasCanal.abrir(canal)' in cj and 'LojasCanal.fechar()' in cj and "canal.type === 'lojas'" in cj, 'abrir o canal troca a conversa pela vitrine; qualquer outro canal fecha a vitrine')
    ok(all(f"'{t}'" in cj or f'{t}:' in cj for t in cargos.TIPOS_CANAL), 'todos os tipos do servidor existem no cliente')
    ok('abrirLoja(Number(ped.dataset.loja), Number(ped.dataset.produto))' in js and 'lojas_canal_pedir' in js, '"Pedir" abre o produto no Bazar (as regras de pedido ficam lá)')
    ok('abrirLoja: (lojaId, produtoId)' in chat and 'Bazar.abrirLojaDe(lojaId, produtoId)' in chat, 'o chat.html leva loja e produto até o Bazar')
    bz = ler('static', 'js', 'bazar.js')
    ok('function abrirLojaDe(id, produtoId)' in bz and 'produtoPendente' in bz, 'Bazar.abrirLojaDe aceita o produto')
    ok('esc(' in js and 'ctx.escUrl(l.logo_url)' in js and 'innerHTML = ' in js and "${l.nome}" not in js and "${p.nome}" not in js, 'nome de loja e de produto passam por esc() (nada cru no innerHTML)')
    ok('.lojas-aberto' in ler('static', 'css', 'lojas_canal.css'), 'o CSS esconde a conversa quando a vitrine está aberta')
    ok('css/lojas_canal.css' in chat and 'js/lojas_canal.js' in chat and 'LojasCanal.iniciar' in chat, 'o chat.html carrega e liga o módulo')

print()
print('TUDO CERTO' if not falhas else f'{len(falhas)} FALHA(S):')
for f in falhas:
    print(' -', f)
sys.exit(1 if falhas else 0)
