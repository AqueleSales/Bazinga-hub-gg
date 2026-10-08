"""Armazém (loja em DRC): catálogo, compra atômica, livro-razão, pacote com abatimento, saldo curto, clique duplo, regra 6."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from sqlalchemy import update
from app import create_app, db, socketio
from app import events, loja
from app import cosmeticos as cos
from app import utils as u
from app.models import Role, Person, Posse, MovimentoDrc

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


# ---------- 1. o catálogo da loja é coerente ----------
vendaveis = {i: d for i, d in cos.CATALOGO.items() if d.get('preco')}
ok(vendaveis and all(isinstance(d['preco'], int) and d['preco'] > 0 for d in vendaveis.values()), 'Todo item à venda tem preço inteiro e positivo')
ok(all(d['tema'] in cos.TEMAS and cos.TEMAS[d['tema']].get('loja') for d in vendaveis.values()), 'Todo item à venda pertence a um tema da loja')
ok(not any(d.get('preco') for i, d in cos.CATALOGO.items() if d['tema'] in ('gogeta', 'sasuke', 'fusao') or d['tipo'] == 'badge'),
   'Laboratório e insígnias NÃO estão à venda')
for tid, t in cos.TEMAS.items():
    if not t.get('loja'):
        continue
    avulsos = loja.itens_do_pacote(tid)
    soma = sum(cos.CATALOGO[i]['preco'] for i in avulsos)
    pacote = cos.CATALOGO.get(f'pacote:{tid}')
    ok(pacote and pacote['preco'] < soma, f'Pacote {t["nome"]} é mais barato que a soma dos itens ({pacote and pacote["preco"]} < {soma})')
    ok(len(avulsos) >= 3, f'Pacote {t["nome"]} entrega pelo menos 3 itens')
ok('relojoaria' in u.MOLDURAS and 'dualidade' in u.PLACAS and 'relojoaria' in u.ESTILOS_NOME and 'dualidade' in u.FAIXAS_ANIMADAS,
   'Os ids novos entram nas tuplas de validação do servidor (senão o editor de perfil recusa)')

C = cos.CATALOGO
PM, PN, PP, PF = (C[f'{t}:dualidade']['preco'] for t in ('moldura', 'nome', 'placa', 'faixa'))
PK = C['pacote:dualidade']['preco']
SOMA = PM + PN + PP + PF
SALDO_ANA = PM + PK + 400

TEMAS_LOJA = [t for t, d in cos.TEMAS.items() if d.get('loja')]
ok(len(TEMAS_LOJA) >= 7, f'Há {len(TEMAS_LOJA)} temas à venda')
CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'static', 'css', 'cosmeticos.css'), encoding='utf-8').read()
JS_LOJA = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'static', 'js', 'loja.js'), encoding='utf-8').read()
for t in TEMAS_LOJA:
    its = {tp: C.get(f'{tp}:{t}') for tp in ('moldura', 'nome', 'placa', 'faixa')}
    ok(all(its.values()), f'Tema {t}: tem moldura, nome, placa e faixa')
    ok(all(d['preco'] == cos.PRECOS[d['raridade']][d['tipo']] for d in its.values() if d), f'Tema {t}: cada preço vem da tabela PRECOS (raridade x tipo)')
    soma = sum(d['preco'] for d in its.values() if d)
    esperado = max(50, int(round(soma * (1 - cos.DESCONTO_PACOTE) / 50.0)) * 50)
    ok(C[f'pacote:{t}']['preco'] == esperado and esperado < soma, f'Tema {t}: pacote = soma ({soma}) com {int(cos.DESCONTO_PACOTE * 100)}% de desconto, arredondado ({esperado})')
    ok(set(cos.PACOTES[t]) == {'moldura', 'nome', 'placa', 'faixa'}, f'Tema {t}: o pacote equipa os 4 itens')
    for classe in (f'.moldura-{t}::before', f'.ne-{t}', f'.placa-{t}', f'.user-profile-bar.placa-{t}', f'.banner-anim-{t}'):
        ok(classe in CSS, f'Tema {t}: o CSS tem {classe} (item sem CSS aparece "vazio" pra quem compra)')
    ok(re.search(rf"^\s+{t}: \(\) =>", JS_LOJA, re.M) is not None, f'Tema {t}: tem arte do carrossel em loja.js (ARTES)')
    ok(t in {x['tema'] for x in loja.DESTAQUES}, f'Tema {t}: tem slide em loja.DESTAQUES')
ok(all(isinstance(t['cores'], list) and len(t['cores']) == 2 and all(re.match(r'^#[0-9a-fA-F]{6}$', c) for c in t['cores'] + [t['cor']]) for t in (cos.TEMAS[x] for x in TEMAS_LOJA)),
   'Cores dos temas são hex válido (vão pra um style="" no navegador)')
ok(all(re.match(r'^[a-z_]{1,24}$', t) for t in TEMAS_LOJA), 'Ids de tema são seguros pra virar classe CSS')

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for nome, user, saldo in (('Ana', 'ana', SALDO_ANA), ('Beto', 'beto', 100), ('Cris', 'cris', 5000), ('Duda', 'duda', PM)):
        p = Person(name=nome, email=f'{user}@x', role_id=r.id, username=user, bazinga_coins=saldo)
        db.session.add(p); db.session.commit(); ids[user] = p.id

    def saldo(user):
        db.session.expire_all()
        return db.session.get(Person, ids[user]).bazinga_coins

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    def comprar(cl, item_id, **extra):
        events._ultima_compra.clear()        # o freio de clique repetido é testado à parte
        cl.emit('comprar_item', {'item_id': item_id, **extra})
        return ev(cl)

    ana, fana = cliente('ana'); ana2, _ = cliente('ana'); beto, _ = cliente('beto'); cris, _ = cliente('cris'); duda, _ = cliente('duda')

    # ---------- 2. vitrine ----------
    ana.emit('listar_loja')
    v = ev(ana, 'loja')[-1]['args'][0]
    ok(v['saldo'] == SALDO_ANA, 'A vitrine mostra o saldo real da pessoa')
    ok({t['id'] for t in v['temas']} == set(TEMAS_LOJA), 'Só os temas da loja aparecem (laboratório fica de fora)')
    ok(all(not i['possui'] for i in v['itens']), 'Quem não comprou nada não "possui" nada')
    pk = next(i for i in v['itens'] if i['id'] == 'pacote:dualidade')
    ok(pk['preco_final'] == PK, f'Sem nada avulso, o pacote custa o preço cheio ({PK})')
    ok(v['destaques'] and all(x['tema'] in {t['id'] for t in v['temas']} for x in v['destaques']), 'Destaques apontam pra temas que existem')

    # ---------- 3. compra avulsa ----------
    rec = comprar(ana, 'moldura:dualidade', preco_esperado=PM)
    ok(any(m['name'] == 'compra_ok' for m in rec), 'Compra avulsa: servidor confirma (compra_ok)')
    ok(saldo('ana') == PK + 400, f'Compra avulsa: debitou exatamente {PM}')
    ok('moldura:dualidade' in cos.posses_da_pessoa(ids['ana']), 'Compra avulsa: a posse foi entregue')
    ok(db.session.query(Posse).filter_by(person_id=ids['ana'], item_id='moldura:dualidade').one().origem == 'loja', 'A posse nasce com origem "loja"')
    mv = db.session.query(MovimentoDrc).filter_by(person_id=ids['ana'], motivo='compra').all()
    ok(len(mv) == 1 and mv[0].delta == -PM and mv[0].saldo_apos == PK + 400 and mv[0].ref == 'moldura:dualidade', 'Livro-razão: o valor negativo, o saldo depois e a ref = o item')
    inv = [m for m in rec if m['name'] == 'inventario']
    ok(inv and 'moldura:dualidade' in inv[-1]['args'][0]['posses'], 'O inventário atualizado já vem com o item')
    ok(any(m['name'] == 'saldo_atualizado' and m['args'][0]['saldo'] == PK + 400 for m in rec), 'Evento de saldo novo')

    # regra 6: a OUTRA aba da mesma pessoa também recebe
    rec2 = ev(ana2)
    ok(any(m['name'] == 'compra_ok' for m in rec2) and any(m['name'] == 'saldo_atualizado' for m in rec2) and any(m['name'] == 'inventario' for m in rec2),
       'Regra 6: a outra aba da Ana recebe compra, saldo e inventário')
    ok(not ev(beto), 'E ninguém de fora recebe nada')

    # equipar o que comprou funciona (e antes de comprar não funcionava)
    ana.emit('equipar_item', {'item_id': 'moldura:dualidade'})
    pa = [m for m in ev(ana) if m['name'] == 'perfil_atualizado']
    ok(pa and pa[-1]['args'][0]['moldura'] == 'dualidade', 'Depois de comprar dá pra equipar')
    beto.emit('equipar_item', {'item_id': 'moldura:dualidade'})
    ok(any(m['name'] == 'erro_bazinga' for m in ev(beto)), 'Sem comprar, não equipa (a posse é checada)')

    # ---------- 4. recusas ----------
    rec = comprar(ana, 'moldura:dualidade')
    ok(any(m['name'] == 'compra_recusada' and 'já tem' in m['args'][0]['msg'] for m in rec) and saldo('ana') == PK + 400, 'Comprar de novo: recusa e NÃO cobra')
    rec = comprar(beto, 'moldura:relojoaria')
    ok(any(m['name'] == 'compra_recusada' and 'suficiente' in m['args'][0]['msg'] for m in rec), 'Saldo curto: recusa com explicação')
    ok(saldo('beto') == 100 and not cos.posses_da_pessoa(ids['beto']), 'Saldo curto: nada cobrado, nada entregue')
    for lixo in ('moldura:gogeta', 'badge:criador', 'pacote:gogeta', 'moldura:padrao', 'xablau:1', '', 'moldura:' + 'a' * 300, 'nome:dualidade" onmouseover="x'):
        rec = comprar(cris, lixo)
        ok(any(m['name'] == 'compra_recusada' for m in rec) and not any(m['name'] == 'compra_ok' for m in rec), f'Item fora da loja é recusado: {lixo[:30]!r}')
    ok(saldo('cris') == 5000 and not cos.posses_da_pessoa(ids['cris']), 'Nenhuma tentativa inválida cobrou ou entregou')
    rec = comprar(cris, 'nome:dualidade', preco_esperado=1)
    ok(any(m['name'] == 'compra_recusada' and 'preço mudou' in m['args'][0]['msg'] for m in rec) and saldo('cris') == 5000,
       'Preço esperado diferente do real: recusa (e manda a vitrine corrigida)')
    ok(any(m['name'] == 'loja' for m in rec), '...junto com a vitrine atualizada')
    for esquisito in (str(PN), True, [PN], {'a': 1}):
        comprar(cris, 'nome:dualidade', preco_esperado=esquisito)
        ok(saldo('cris') == 5000 or cos.posses_da_pessoa(ids['cris']), f'preco_esperado esquisito ({esquisito!r}) não derruba o servidor')
        db.session.query(Posse).filter_by(person_id=ids['cris']).delete()
        db.session.query(MovimentoDrc).filter_by(person_id=ids['cris']).delete()
        db.session.execute(update(Person).where(Person.id == ids['cris']).values(bazinga_coins=5000)); db.session.commit()

    # ---------- 5. saldo exato / clique duplo / saldo velho em memória ----------
    rec = comprar(duda, 'moldura:relojoaria')
    ok(any(m['name'] == 'compra_ok' for m in rec) and saldo('duda') == 0, 'Saldo exato compra e zera')
    rec = comprar(duda, 'nome:relojoaria')
    ok(any(m['name'] == 'compra_recusada' for m in rec) and saldo('duda') == 0, 'Com saldo zero, a próxima é recusada')

    # O pior cenário: a cópia da pessoa na memória acha que tem 5000, mas no banco só restam 100 (outra aba gastou).
    pessoa_velha = db.session.get(Person, ids['cris'])
    db.session.execute(update(Person).where(Person.id == ids['cris']).values(bazinga_coins=100)); db.session.commit()
    pessoa_velha.bazinga_coins = 5000                               # estado velho em memória (como numa 2ª aba)
    db.session.expunge(pessoa_velha)                                # não vira UPDATE na hora do commit
    try:
        loja.comprar(pessoa_velha, 'moldura:dualidade')
        ok(False, 'Saldo velho em memória: devia ser recusado (o banco só tem 100)')
    except loja.ErroLoja:
        ok(True, 'Saldo velho em memória: recusado, porque o débito confere o saldo do BANCO (nada de gastar duas vezes)')
    db.session.rollback()
    ok(saldo('cris') == 100 and not cos.posses_da_pessoa(ids['cris']), '...e nada foi cobrado nem entregue')
    db.session.execute(update(Person).where(Person.id == ids['cris']).values(bazinga_coins=5000)); db.session.commit()

    # freio de clique repetido
    events._ultima_compra.clear()
    cris.emit('comprar_item', {'item_id': 'nome:dualidade'}); cris.emit('comprar_item', {'item_id': 'placa:dualidade'})
    rec = ev(cris)
    ok(sum(1 for m in rec if m['name'] == 'compra_ok') == 1 and any(m['name'] == 'compra_recusada' and 'Calma' in m['args'][0]['msg'] for m in rec),
       'Dois pedidos colados: só o primeiro passa')
    ok(saldo('cris') == 5000 - PN, f'...e só {PN} foram cobrados')

    # ---------- 6. pacote com abatimento ----------
    # Cris já tem nome:dualidade. Faltam moldura+placa+faixa; o preço do pacote é abatido na mesma proporção
    cris.emit('listar_loja'); vc = ev(cris, 'loja')[-1]['args'][0]
    pc = next(i for i in vc['itens'] if i['id'] == 'pacote:dualidade')
    ok(pc['preco_final'] == round(PK * (SOMA - PN) / SOMA), f'Pacote com 1 item avulso já comprado sai abatido ({pc["preco_final"]})')
    rec = comprar(cris, 'pacote:dualidade', preco_esperado=pc['preco_final'])
    ok(any(m['name'] == 'compra_ok' for m in rec), 'Compra do pacote abatido passa')
    ok(saldo('cris') == 5000 - PN - pc['preco_final'], 'E cobra o valor abatido')
    posses = cos.posses_da_pessoa(ids['cris'])
    ok({'pacote:dualidade', 'moldura:dualidade', 'nome:dualidade', 'placa:dualidade', 'faixa:dualidade'} <= posses, 'Entrega o pacote e os 4 itens')
    ok(db.session.query(Posse).filter_by(person_id=ids['cris']).count() == 5, 'Sem posse duplicada (o nome já tinha)')
    cris.emit('equipar_item', {'item_id': 'pacote:dualidade'})
    pa = [m for m in ev(cris) if m['name'] == 'perfil_atualizado']
    ok(pa and pa[-1]['args'][0]['moldura'] == 'dualidade' and pa[-1]['args'][0]['placa'] == 'dualidade', 'O pacote comprado equipa o tema inteiro')

    # pacote cheio, quem não tem nada
    rec = comprar(ana, 'pacote:relojoaria')
    ok(any(m['name'] == 'compra_ok' and m['args'][0]['preco'] == PK for m in rec), 'Pacote cheio custa o preço de tabela')
    ok(saldo('ana') == 400, 'Sobrou o que tinha de reserva (400)')
    ok(len([p for p in cos.posses_da_pessoa(ids['ana']) if p.endswith(':relojoaria')]) == 5, 'Entregou pacote + 4 itens da Relojoaria')

    # tem todos os avulsos mas não o pacote: sai de graça (só pra constar)
    ana_posses = cos.posses_da_pessoa(ids['ana'])
    for i in loja.itens_do_pacote('dualidade'):
        if i not in ana_posses:
            db.session.add(Posse(person_id=ids['ana'], item_id=i, origem='teste'))
    db.session.commit()
    pr, ent = loja.preco_para(cos.posses_da_pessoa(ids['ana']), 'pacote:dualidade')
    ok(pr == 0 and ent == ['pacote:dualidade'], 'Quem já tem todos os avulsos leva o pacote por 0')
    s0 = saldo('ana')
    rec = comprar(ana, 'pacote:dualidade')
    ok(any(m['name'] == 'compra_ok' for m in rec) and saldo('ana') == s0, 'Pacote grátis não cobra nada')
    ok(not db.session.query(MovimentoDrc).filter_by(person_id=ids['ana'], ref='pacote:dualidade').count(), 'E não escreve movimento de 0 no livro-razão')

    # ---------- 7. livro-razão fecha a conta ----------
    for user in ('ana', 'cris', 'duda'):
        movs = db.session.query(MovimentoDrc).filter_by(person_id=ids[user]).order_by(MovimentoDrc.id).all()
        ok(all(m.delta < 0 and m.saldo_apos is not None and m.saldo_apos >= 0 for m in movs if m.motivo == 'compra'), f'Livro-razão de {user}: compras são negativas e o saldo nunca fica negativo')
        if movs:
            ok(movs[-1].saldo_apos == saldo(user), f'Livro-razão de {user}: o último "saldo_apos" bate com o saldo real')

    # ganho por nível também entra no razão
    pessoa = db.session.get(Person, ids['beto'])
    antes = pessoa.bazinga_coins
    nivel_antes = u.nivel_da_pessoa(pessoa.xp)
    u._somar_xp(pessoa, 5000, nivel_antes); db.session.commit()
    ganho = db.session.query(MovimentoDrc).filter_by(person_id=ids['beto'], motivo='nivel').one()
    ok(ganho.delta > 0 and ganho.saldo_apos == antes + ganho.delta == db.session.get(Person, ids['beto']).bazinga_coins, 'Subir de nível escreve o ganho no livro-razão com o saldo certo')

    # ---------- 7b. extrato ----------
    cris.emit('listar_movimentos')
    ex = ev(cris, 'movimentos')[-1]['args'][0]
    ok(ex['saldo'] == saldo('cris') and ex['itens'][0]['motivo'] == 'compra' and ex['itens'][0]['delta'] < 0, 'Extrato: o saldo bate e o movimento mais novo é a última compra (negativo)')
    ok(ex['itens'][0]['titulo'] == C['pacote:dualidade']['nome'], 'Extrato: mostra o NOME do item comprado (não o id)')
    ok(ex['gasto_total'] == sum(-m.delta for m in db.session.query(MovimentoDrc).filter_by(person_id=ids['cris']).all() if m.delta < 0), 'Extrato: o total gasto fecha com o livro-razão')
    beto.emit('listar_movimentos')
    eb = ev(beto, 'movimentos')[-1]['args'][0]
    ok(all(m['titulo'] != C['pacote:dualidade']['nome'] for m in eb['itens']), 'Extrato é só da própria pessoa (o do Beto não tem as compras da Cris)')
    anon_ex = socketio.test_client(app); anon_ex.get_received(); anon_ex.emit('listar_movimentos')
    ok(not ev(anon_ex), 'Sem login: o extrato não responde')

    # ---------- 8. a rota antiga não cobra nem entrega ----------
    resp = fana.post('/api/produtos/1/comprar')
    ok(resp.status_code == 410, 'Rota antiga de compra responde 410')
    # sem login nada acontece
    anon = socketio.test_client(app); anon.get_received()
    anon.emit('comprar_item', {'item_id': 'moldura:dualidade'}); anon.emit('listar_loja')
    ok(not ev(anon), 'Sem login: comprar_item e listar_loja não respondem nada')

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
