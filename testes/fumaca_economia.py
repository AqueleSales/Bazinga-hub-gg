"""Economia da Rodada 14: missão que paga DRC (livro-razão + extrato), e as mecânicas novas do Armazém
(relíquia da semana, tempo/estoque limitado, coleção "colete N", efeitos avulsos). Banco SQLite em memória."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
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


# ---------- 0. todo item do catálogo tem id seguro e arte (CSS/JS) ----------
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'static')
CSS = open(os.path.join(RAIZ, 'css', 'cosmeticos.css'), encoding='utf-8').read()
JS_COSM = open(os.path.join(RAIZ, 'js', 'cosmeticos.js'), encoding='utf-8').read()


def lista_js(trecho):
    """['a', 'b'] de `NOME: ['a', 'b']` ou `const NOME = ['a', 'b']` no cosmeticos.js."""
    m = re.search(trecho + r"\s*\[([^\]]*)\]", JS_COSM)
    return set(re.findall(r"'([a-z_]+)'", m.group(1))) if m else set()


REGISTRO_JS = {'efeito_avatar': lista_js(r'const EFEITOS_AVATAR =\s*'), 'efeito_perfil': lista_js(r'const EFEITOS_PERFIL =\s*'),
               'efeito_fala': lista_js(r'\bfala:'), 'efeito_radar': lista_js(r'\bradar:'), 'efeito_chat': lista_js(r'\bchat:'),
               'som_call': lista_js(r'\bsom:'), 'pin_nota': lista_js(r'\bpin:'), 'efeito_servidor': lista_js(r'\bservidor:')}
CSS_DO_TIPO = {'moldura': ['.moldura-{v}::before'], 'placa': ['.placa-{v}', '.user-profile-bar.placa-{v}'], 'nome': ['.ne-{v}'], 'faixa': ['.banner-anim-{v}'],
               'efeito_avatar': ['.ef-av-{v}'], 'efeito_perfil': ['.ef-pf-{v}'], 'efeito_fala': ['.fala-{v}'], 'efeito_radar': ['.radar-{v}'],
               'efeito_chat': ['.chat-ef-{v}'], 'pin_nota': ['.pin-{v}'], 'efeito_servidor': ['.sv-ef-{v}']}
for iid, d in cos.CATALOGO.items():
    if d['tipo'] in ('badge', 'pacote'):
        continue
    ok(re.match(r'^[a-z_]{1,24}$', d['valor']) is not None, f'{iid}: id só com letras minúsculas e _ (o cliente descarta qualquer outro, e o preview some)')
    for modelo in CSS_DO_TIPO.get(d['tipo'], []):
        ok(modelo.format(v=d['valor']) in CSS, f'{iid}: o CSS tem {modelo.format(v=d["valor"])}')
    if d['tipo'] in REGISTRO_JS:
        ok(d['valor'] in REGISTRO_JS[d['tipo']], f'{iid}: o id está registrado em cosmeticos.js ({d["tipo"]})')

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for nome, user, saldo in (('Ana', 'ana', 500), ('Beto', 'beto', 500)):
        p = Person(name=nome, email=f'{user}@x', role_id=r.id, username=user, bazinga_coins=saldo)
        db.session.add(p); db.session.commit(); ids[user] = p.id

    def pessoa(user):
        db.session.expire_all()
        return db.session.get(Person, ids[user])

    # ---------- 1. missão paga DRC ----------
    ok(u.DRC_POR_MISSAO == {'diaria': 10, 'semanal': 40}, 'Missão diária paga 10 e semanal 40 DRC')
    sorteio_original = u._sortear_codigos
    u._sortear_codigos = lambda uid, periodo, chave: (['d_msg10', 'd_ativo15', 'd_dm5'] if periodo == 'diaria' else ['s_msg150', 's_dm30', 's_nota3'])
    try:
        ana = pessoa('ana')
        antes = ana.bazinga_coins
        res = u.registrar_eventos(ana, {'mensagem': 10})
        ok(res and [m['titulo'] for m in res['concluidas']] == ['Bate-papo'], 'Diária de 10 mensagens concluída')
        ok(res['concluidas'][0].get('drc') == 10, 'O aviso da missão concluída leva o DRC (10)')
        ana = pessoa('ana')
        # 150 XP da missão cruzam o nível 2 (100 XP): +50 DRC de nível, além dos +10 da missão
        ganho_nivel = sum(u.recompensa_do_nivel(n)['coins'] for n in range(2, u.nivel_da_pessoa(ana.xp) + 1))
        ok(ana.bazinga_coins == antes + ganho_nivel + 10, f'Saldo = antes + nível ({ganho_nivel}) + missão (10): {ana.bazinga_coins}')
        movs = MovimentoDrc.query.filter_by(person_id=ana.id).order_by(MovimentoDrc.id).all()
        ok([m.motivo for m in movs] == ['nivel', 'missao'], f'Livro-razão: nível e missão em linhas separadas ({[m.motivo for m in movs]})')
        ok(movs[-1].delta == 10 and movs[-1].ref == 'd_msg10' and movs[-1].saldo_apos == ana.bazinga_coins, 'Movimento da missão: +10, ref da missão, saldo_apos = saldo atual')
        ok(sum(m.delta for m in movs) == ana.bazinga_coins - antes, 'A soma do livro-razão bate com o saldo ganho')

        # repetir o evento não paga de novo
        u.registrar_eventos(ana, {'mensagem': 10})
        ok(pessoa('ana').bazinga_coins == ana.bazinga_coins and MovimentoDrc.query.filter_by(person_id=ana.id, motivo='missao').count() == 1,
           'Missão já concluída não paga duas vezes')

        # semanal: 150 mensagens (a diária já foi) paga 40
        saldo_antes = pessoa('ana').bazinga_coins
        res = u.registrar_eventos(pessoa('ana'), {'mensagem': 150})
        sem = [m for m in res['concluidas'] if m['titulo'] == 'Voz da comunidade']
        ok(sem and sem[0]['drc'] == 40, 'Semanal "150 mensagens" concluída e paga 40')
        movs_missao = MovimentoDrc.query.filter_by(person_id=ana.id, motivo='missao').all()
        ok(movs_missao[-1].delta == 40 and movs_missao[-1].ref == 's_msg150', 'Livro-razão: +40 da semanal')

        # duas missões na mesma chamada: um movimento só, soma e lista os códigos
        beto = pessoa('beto')
        res = u.registrar_eventos(beto, {'mensagem': 10, 'dm': 5})
        movs_b = MovimentoDrc.query.filter_by(person_id=beto.id, motivo='missao').all()
        ok(len(movs_b) == 1 and movs_b[0].delta == 20 and set(movs_b[0].ref.split(',')) == {'d_msg10', 'd_dm5'}, 'Duas diárias juntas: 1 movimento de +20 com os dois códigos')

        # payload da missão mostra o DRC
        mj = u.missoes_do_usuario(pessoa('beto'))
        ok(all('drc' in m for m in mj['diarias'] + mj['semanais']), 'Payload das missões leva o campo drc')
        ok({m['drc'] for m in mj['diarias']} == {10} and {m['drc'] for m in mj['semanais']} == {40}, 'drc: 10 nas diárias e 40 nas semanais')

        # extrato mostra o nome da missão
        ex = loja.extrato(pessoa('beto'))
        titulos = [i['titulo'] for i in ex['itens'] if i['motivo'] == 'missao']
        ok(titulos and titulos[0].startswith('Missão: ') and 'Bate-papo' in titulos[0], f'Extrato: título da missão ({titulos})')
    finally:
        u._sortear_codigos = sorteio_original

    # ======================================================================
    # Mecânicas do Armazém: relíquia da semana, edições limitadas, coleção
    # ======================================================================
    from datetime import datetime, timedelta
    from app.models import LojaEstoque

    for nome, user, saldo in (('Cris', 'cris', 100000), ('Duda', 'duda', 100000), ('Eva', 'eva', 100000), ('Pobre', 'pobre', 10)):
        p = Person(name=nome, email=f'{user}@x', role_id=r.id, username=user, bazinga_coins=saldo)
        db.session.add(p); db.session.commit(); ids[user] = p.id

    def saldo_de(user):
        db.session.expire_all()
        return db.session.get(Person, ids[user]).bazinga_coins

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as sess:
            sess['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl

    def ev(cl, nome):
        return [m for m in cl.get_received() if m['name'] == nome]

    def comprar(cl, item_id, esperado=None):
        events._ultima_compra.clear()
        cl.get_received()
        cl.emit('comprar_item', {'item_id': item_id, 'preco_esperado': esperado})
        return cl.get_received()

    def vitrine(cl):
        cl.get_received(); cl.emit('listar_loja')
        return ev(cl, 'loja')[-1]['args'][0]

    def recusas(rec):
        return [m['args'][0]['msg'] for m in rec if m['name'] == 'compra_recusada']

    def compra_ok(rec):
        return [m for m in rec if m['name'] == 'compra_ok']

    # ---------- 2. relíquia da semana ----------
    seg = datetime(2026, 10, 5)
    semana = [loja.reliquia_da_semana(seg + timedelta(days=d, hours=h)) for d in range(7) for h in (0, 23)]
    ok(len(set(semana)) == 1, 'A relíquia é a mesma de segunda 00h até domingo 23h')
    proxima = loja.reliquia_da_semana(seg + timedelta(days=7))
    ok(proxima != semana[0], 'Na segunda seguinte a relíquia troca')
    pool = loja._candidatas_reliquia()
    vistas = [loja.reliquia_da_semana(seg + timedelta(days=7 * k)) for k in range(len(pool))]
    ok(len(set(vistas)) == len(pool), f'Nenhuma relíquia se repete antes de passar as {len(pool)} do catálogo')
    ok(all(cos.CATALOGO[i]['tipo'] != 'pacote' and cos.TEMAS[cos.CATALOGO[i]['tema']].get('loja') for i in vistas),
       'Relíquia é sempre item avulso de tema da loja (nunca pacote nem edição limitada)')
    rel = loja.reliquia_da_semana()
    d_rel = cos.CATALOGO[rel]
    preco_rel, _ = loja.preco_para(set(), rel)
    ok(preco_rel < d_rel['preco'] and abs(preco_rel - d_rel['preco'] * 0.75) <= 5, f'Preço da relíquia = tabela com 25% (de {d_rel["preco"]} por {preco_rel})')
    outro = next(i for i in pool if i != rel)
    ok(loja.preco_para(set(), outro)[0] == cos.CATALOGO[outro]['preco'], 'Item que não é a relíquia custa o preço de tabela')
    ok(0 < loja.segundos_ate_trocar() <= 7 * 86400, 'O relógio da semana: faltam entre 0 e 7 dias pra trocar')

    cris = cliente('cris')
    v = vitrine(cris)
    ok(v['reliquia'] and v['reliquia']['item_id'] == rel and v['reliquia']['termina_em'] > 0 and v['reliquia']['desconto'] == 25,
       'Vitrine informa a relíquia, o desconto e quanto falta')
    it = next(i for i in v['itens'] if i['id'] == rel)
    ok(it.get('reliquia') and it['preco_final'] == preco_rel and it['preco'] == d_rel['preco'], 'No item da vitrine: preco_final com desconto e preco de tabela intactos')
    antes = saldo_de('cris')
    rec = comprar(cris, rel, preco_rel)
    ok(compra_ok(rec) and saldo_de('cris') == antes - preco_rel, f'Comprar a relíquia cobra o preço com desconto ({preco_rel})')
    mov = MovimentoDrc.query.filter_by(person_id=ids['cris'], motivo='compra').order_by(MovimentoDrc.id.desc()).first()
    ok(mov.delta == -preco_rel and mov.ref == rel, 'Livro-razão grava o valor realmente cobrado')
    duda = cliente('duda')
    rec = comprar(duda, rel, d_rel['preco'])         # tela com o preço velho
    ok(recusas(rec) and 'preço mudou' in recusas(rec)[0] and saldo_de('duda') == 100000, 'Preço de tabela na tela + relíquia no servidor: recusa e não cobra')
    ok(compra_ok(comprar(duda, rel, preco_rel)), '...e com o preço certo passa')

    # ---------- 3. edições limitadas ----------
    lim = cos.CATALOGO['moldura:pioneiro']['limitado']
    ok(lim['ate'] and lim['estoque'] is None, 'Pioneiro é limitada por PRAZO (sem estoque)')
    v = vitrine(cris)
    pio = next(i for i in v['itens'] if i['id'] == 'moldura:pioneiro')
    ok(pio['limitado']['termina_em'] > 0 and not pio['limitado']['encerrado'] and pio['limitado']['restam'] is None, 'Vitrine: Pioneiro tem prazo correndo')
    lote = next(i for i in v['itens'] if i['id'] == 'placa:lote_um')
    ok(lote['limitado']['restam'] == 100 and lote['limitado']['estoque'] == 100 and lote['limitado']['termina_em'] is None, 'Vitrine: Lote 001 mostra 100 de 100')
    ok(not any(t['id'] == 'edicao' for t in v['temas']) and 'pacote:edicao' not in cos.CATALOGO, 'Edição limitada não vira chip de tema nem ganha pacote')
    ok(compra_ok(comprar(cris, 'moldura:pioneiro', cos.CATALOGO['moldura:pioneiro']['preco'])), 'Dentro do prazo: compra o Pioneiro')

    # prazo vencido: o servidor recusa mesmo com a tela velha
    original_ate = lim['ate']
    lim['ate'] = datetime(2020, 1, 1)
    try:
        saldo_antes = saldo_de('duda')
        rec = comprar(duda, 'moldura:pioneiro', cos.CATALOGO['moldura:pioneiro']['preco'])
        ok(recusas(rec) and 'encerrada' in recusas(rec)[0], f'Prazo vencido: recusa ({recusas(rec)})')
        ok(saldo_de('duda') == saldo_antes and 'moldura:pioneiro' not in cos.posses_da_pessoa(ids['duda']), '...sem cobrar e sem entregar')
        v = vitrine(duda)
        ok(next(i for i in v['itens'] if i['id'] == 'moldura:pioneiro')['limitado']['encerrado'], 'Vitrine marca como encerrado')
    finally:
        lim['ate'] = original_ate

    # estoque: só 2 unidades
    lote_lim = cos.CATALOGO['placa:lote_um']['limitado']
    estoque_original = lote_lim['estoque']
    lote_lim['estoque'] = 2
    try:
        preco_lote = cos.CATALOGO['placa:lote_um']['preco']
        eva = cliente('eva'); pobre = cliente('pobre')
        ok(compra_ok(comprar(cris, 'placa:lote_um', preco_lote)), 'Estoque 2: a 1ª pessoa compra')
        ok(compra_ok(comprar(duda, 'placa:lote_um', preco_lote)), '...a 2ª também')
        rec = comprar(eva, 'placa:lote_um', preco_lote)
        ok(recusas(rec) and 'Esgotado' in recusas(rec)[0] and saldo_de('eva') == 100000, f'A 3ª leva "Esgotado" e não é cobrada ({recusas(rec)})')
        db.session.expire_all()
        ok(db.session.get(LojaEstoque, 'placa:lote_um').vendidos == 2, 'O contador de vendidos parou em 2')
        v = vitrine(eva)
        lote = next(i for i in v['itens'] if i['id'] == 'placa:lote_um')
        ok(lote['limitado']['restam'] == 0 and lote['limitado']['esgotado'], 'Vitrine marca como esgotado (restam 0)')
    finally:
        lote_lim['estoque'] = estoque_original

    # sem DRC não gasta unidade do estoque (o rollback devolve)
    linha = db.session.get(LojaEstoque, 'faixa:eclipse')
    vendidos_antes = linha.vendidos if linha else 0
    rec = comprar(pobre, 'faixa:eclipse', cos.CATALOGO['faixa:eclipse']['preco'])
    db.session.expire_all()
    linha = db.session.get(LojaEstoque, 'faixa:eclipse')
    ok(recusas(rec) and 'DRC suficiente' in recusas(rec)[0] and (linha.vendidos if linha else 0) == vendidos_antes,
       'Sem DRC: recusa e a unidade volta pro estoque (rollback)')

    # ---------- 4. coleção ----------
    ok([c['meta'] for c in cos.COLECOES] == sorted(c['meta'] for c in cos.COLECOES), 'Metas da coleção em ordem crescente')
    ok(all(cos.CATALOGO[c['item_id']].get('preco') is None for c in cos.COLECOES), 'Prêmios de coleção não têm preço (não se vendem)')
    rec = comprar(eva, 'placa:colecionador')
    ok(recusas(rec) == ['Este item não está à venda.'], 'Prêmio de coleção não pode ser comprado')

    avulsos = [i for i in pool if i not in cos.posses_da_pessoa(ids['eva'])]
    ganhou = []
    for k, item in enumerate(avulsos[:12], start=1):
        preco = loja.preco_para(cos.posses_da_pessoa(ids['eva']), item)[0]
        rec = comprar(eva, item, preco)
        if not compra_ok(rec):
            ok(False, f'Compra {k} ({item}) falhou: {rec}')
            break
        for pr in compra_ok(rec)[0]['args'][0]['premios']:
            ganhou.append((k, pr['item_id']))
    ok(ganhou == [(4, 'placa:colecionador'), (12, 'moldura:curador')], f'Prêmios saem exatamente na 4ª e na 12ª compra ({ganhou})')
    pe = cos.posses_da_pessoa(ids['eva'])
    ok({'placa:colecionador', 'moldura:curador'} <= pe and 'nome:acervo' not in pe, 'Posse: tem os 2 prêmios e ainda não o 3º')
    ok(loja.itens_comprados(ids['eva']) == 12, 'Contagem de itens comprados = 12')
    v = vitrine(eva)
    col = v['colecao']
    ok(col['comprados'] == 12 and [p['ganho'] for p in col['premios']] == [True, True, False] and col['premios'][2]['faltam'] == 12,
       'Vitrine: progresso 12, 2 prêmios ganhos, faltam 12 pro último')
    ok(all('rotulo' in p['item'] for p in col['premios']), 'Vitrine: cada prêmio vem com o rótulo pra desenhar')

    # o prêmio se equipa como qualquer item; quem não ganhou não equipa
    eva.get_received(); eva.emit('equipar_item', {'item_id': 'placa:colecionador'})
    db.session.expire_all()
    ok(ev(eva, 'perfil_atualizado') and db.session.get(Person, ids['eva']).placa == 'colecionador', 'Prêmio de coleção se equipa')
    cris.get_received(); cris.emit('equipar_item', {'item_id': 'nome:acervo'})
    ok(ev(cris, 'erro_bazinga'), 'Quem não ganhou o prêmio não equipa')

    # pacote: entrega 4 itens e esses 4 contam; o pacote em si não
    antes_pk = loja.itens_comprados(ids['duda'])
    pk = 'pacote:manga'
    if not (set(loja.itens_do_pacote('manga')) & cos.posses_da_pessoa(ids['duda'])):
        comprar(duda, pk, loja.preco_para(cos.posses_da_pessoa(ids['duda']), pk)[0])
        ok(loja.itens_comprados(ids['duda']) == antes_pk + 4, 'Pacote conta pelos 4 itens que entrega (não conta o pacote)')

    # ======================================================================
    # JJK (Gojo, Sukuna, Mahoraga e o combo): itens LENDÁRIOS À VENDA no Armazém (nada de presente)
    # ======================================================================
    JJK = [i for i, d in cos.CATALOGO.items() if d['tema'] in ('gojo', 'sukuna', 'mahoraga', 'jjk')]
    ok(len(JJK) == 40, f'JJK: 3 temas x 12 itens + 3 pacotes + o combo = 40 ({len(JJK)})')
    ok(all(cos.CATALOGO[i].get('preco') for i in JJK), 'JJK: todo item tem preço (é pra comprar)')
    ok(not any(i in cos.LABORATORIO[q] for q in cos.LABORATORIO for i in JJK), 'JJK não é concedido a ninguém de graça (nem aos testers)')
    for tema in ('gojo', 'sukuna', 'mahoraga'):
        its = {tp: cos.CATALOGO[f'{tp}:{tema}'] for tp in ('moldura', 'nome', 'placa', 'faixa')}
        ok(all(d['raridade'] == 'lendario' for d in its.values()) and cos.CATALOGO[f'pacote:{tema}']['raridade'] == 'lendario', f'{tema}: visuais e pacote são lendários')
        ok({'moldura', 'nome', 'placa', 'faixa', 'efeito_avatar', 'efeito_perfil', 'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota'} == set(cos.PACOTES[tema]),
           f'{tema}: o pacote equipa os 11 slots (visuais + 7 efeitos)')
        ok(f'efeito_servidor:{tema}' in cos.CATALOGO, f'{tema}: tem efeito de servidor (avulso)')
    ok(cos.PACOTES['jjk']['moldura'] == 'gojo' and cos.PACOTES['jjk']['nome'] == 'sukuna' and cos.PACOTES['jjk']['efeito_perfil'] == 'sukuna', 'Combo JJK mistura os dois lados')
    ok(all(f'{t}:{v}' in cos.CATALOGO for t, v in cos.PACOTES['jjk'].items()), 'Todo item do combo existe no catálogo')
    soma_combo = sum(cos.CATALOGO[f'{t}:{v}']['preco'] for t, v in cos.PACOTES['jjk'].items())
    ok(cos.CATALOGO['pacote:jjk']['preco'] == max(50, int(round(soma_combo * (1 - cos.DESCONTO_PACOTE) / 50.0)) * 50) < soma_combo, f'Combo custa a soma dos 11 itens ({soma_combo}) com 30% de desconto')

    v = vitrine(cliente('cris'))
    ids_tema = {t['id'] for t in v['temas']}
    ok({'gojo', 'sukuna', 'mahoraga'} <= ids_tema and 'jjk' not in ids_tema, 'Vitrine: Gojo, Sukuna e Mahoraga são temas; o combo é só um pacote')
    ok(any(i['id'] == 'pacote:jjk' for i in v['itens']) and all(i['grupo'] for i in v['itens'] if i['tema'] in ('gojo', 'sukuna', 'mahoraga')), 'Vitrine: o combo aparece nos pacotes')
    ok({'gojo', 'sukuna', 'mahoraga'} <= {d['tema'] for d in v['destaques']}, 'Vitrine: os 3 têm slide no carrossel')

    # comprar o combo (com abatimento de quem já tem um item) entrega os 11 misturados e equipa a mistura
    rico = Person(name='Rico', email='r@x', role_id=r.id, username='rico', bazinga_coins=30000)
    db.session.add(rico); db.session.commit(); ids['rico'] = rico.id
    rc = cliente('rico')
    ok(compra_ok(comprar(rc, 'moldura:gojo', cos.CATALOGO['moldura:gojo']['preco'])), 'Compra um item avulso do Gojo')
    preco_combo, entregues = loja.preco_para(cos.posses_da_pessoa(ids['rico']), 'pacote:jjk')
    ok(preco_combo < cos.CATALOGO['pacote:jjk']['preco'], f'Combo sai abatido de quem já tem a moldura Gojo ({preco_combo})')
    ok(compra_ok(comprar(rc, 'pacote:jjk', preco_combo)), 'Compra o combo')
    pj = cos.posses_da_pessoa(ids['rico'])
    ok({f'{t}:{v}' for t, v in cos.PACOTES['jjk'].items()} <= pj and 'pacote:jjk' in pj, 'Combo entrega os 11 itens misturados e o pacote')
    rc.get_received(); rc.emit('equipar_item', {'item_id': 'pacote:jjk'})
    db.session.expire_all()
    p_r = db.session.get(Person, ids['rico'])
    ok(p_r.moldura == 'gojo' and p_r.nome_estilo == 'sukuna' and p_r.placa == 'gojo', 'Combo equipado: moldura Gojo, nome Sukuna, placa Gojo')
    ok(cos.equipados_da_pessoa(p_r).get('efeito_perfil') == 'sukuna' and cos.equipados_da_pessoa(p_r).get('som_call') == 'gojo', 'Combo equipado: domínio do Sukuna no cartão e som do Gojo na call')
    pobre2 = cliente('pobre'); pobre2.get_received(); pobre2.emit('equipar_item', {'item_id': 'efeito_perfil:sukuna'})
    db.session.expire_all()
    ok(ev(pobre2, 'erro_bazinga') and cos.equipados_da_pessoa(db.session.get(Person, ids['pobre'])).get('efeito_perfil') is None, 'Quem não comprou o efeito do JJK não equipa')

    # os domínios não têm mão/dedo (ficaram feios) e a boca/dentes do Sukuna saiu (Rodada 17): só aura, marcas, cortes, vazio, olhos e timão
    ok('maoSukuna' not in JS_COSM and 'maoGojo' not in JS_COSM and 'sk-maos' not in CSS and 'gj-mao' not in CSS, 'Domínios sem mãos nem dedos')
    ok('dentesSvg' not in JS_COSM and 'sk-mand' not in CSS and 'svgDentes' not in open(os.path.join(RAIZ, 'js', 'loja.js'), encoding='utf-8').read(), 'Sukuna sem a boca/dentes fechando (nem no cartão, nem no carrossel)')
    m_raj = re.search(r'const RAJADAS_SUKUNA = (\[\[.*?\]\]);', JS_COSM)
    n_cortes = sum(int(q) for _, q in re.findall(r'\[([\d.]+), (\d+)\]', m_raj.group(1))) if m_raj else 0
    ok(n_cortes >= 40, f'Sukuna: montes de cortes pretos no ciclo ({n_cortes} em rajadas)')
    m_marcas = re.search(r'const MARCAS_SUKUNA = (\{.*?\});', JS_COSM)
    marcas = __import__('json').loads(m_marcas.group(1)) if m_marcas else {}
    ok(all(len(marcas.get(k, '')) > 150 for k in ('testa', 'nariz', 'face')) and marcas.get('vb', '').startswith('0 0 '), 'Sukuna: as marcas do rosto (testa, nariz, bochechas) estão desenhadas')
    ok(all(re.fullmatch(r'[MLQZ0-9 .\-]+', marcas[k]) for k in ('testa', 'nariz', 'face')), 'Marcas: só comandos de caminho SVG (nada de texto solto que vire HTML)')
    ok('class="sk-marcas"' in JS_COSM or "marcasSukunaSvg('sk-marcas')" in JS_COSM, 'Sukuna: o domínio mostra as marcas')
    ok('.sk-marcas' in CSS and '.sk-borda' in CSS and '.sk-chama' in CSS, 'Sukuna: aura vermelha (borda/chama) e marcas no CSS')
    # nome do Sukuna: flecha de fogo caindo + chamas
    ok('@keyframes sukunaFlecha' in CSS and '.ne-sukuna::before' in CSS and '.ne-sukuna::after' in CSS and '@keyframes sukunaChamas' in CSS, 'Nome do Sukuna: flecha de fogo (::after) e chamas (::before)')
    # Gojo: vazio que enche o cartão inteiro, seis olhos humanos, orbes de verdade no avatar
    ok(re.search(r'\.gj-vazio \{ position: absolute; inset: 0;', CSS) is not None, 'Gojo: o vazio enche o cartão inteiro (inset 0, nada de bolha)')
    m_olhos = re.search(r'const olhos = (\[\[.*?\]\])\.map', JS_COSM)
    ok(m_olhos is not None and len(re.findall(r'\[\d+, \d+\]', m_olhos.group(1))) == 6, 'Gojo: seis olhos em volta do anel')
    ok('function olhoHumanoSvg' in JS_COSM and 'gj-iris' in JS_COSM and 'gj-olhos' not in CSS, 'Gojo: olhos humanos (esclera, íris, pupila, cílios), sem o brilho azul antigo')
    ok('gj-azul' in JS_COSM and 'gj-verm' in JS_COSM and 'gj-roxo' in JS_COSM and '@keyframes gjVai' in CSS, 'Gojo: avatar com orbe azul, vermelho que vem ao encontro e o roxo da fusão')
    # Mahoraga: timão (leme) no perfil e na faixa, girando em degraus duros
    ok('function timaoSvg' in JS_COSM and 'class="mh-giro"' in JS_COSM and 'mhFaixaGira' in CSS, 'Mahoraga: timão no cartão e na faixa')
    ok(re.search(r'\.banner-anim-mahoraga::before \{[^}]*data:image/svg\+xml', CSS) is not None, 'Mahoraga: a faixa desenha o timão (imagem), não só um disco preto')
    ok(len(re.findall(r'rotate\(\d+deg\)', CSS[CSS.index('@keyframes mhGiro'):CSS.index('@keyframes mhGiro') + 3600])) >= 24, 'Mahoraga: 8 estalos de 45° (gira, assenta e para)')
    # sons de entrada: os três arquivos que o dono mandou, curtos, ligados ao id certo
    AUDIO = os.path.join(RAIZ, 'audio')
    for id_som, arq in (('gojo', 'dominio_gojo.mp3'), ('sukuna', 'dominio_sukuna.mp3'), ('mahoraga', 'roda_mahoraga.mp3')):
        caminho = os.path.join(AUDIO, arq)
        ok(os.path.isfile(caminho) and 5_000 < os.path.getsize(caminho) < 400_000, f'Som de entrada {id_som}: {arq} existe e é um arquivo leve')
        ok(f"{id_som}: ['/static/audio/{arq}'" in JS_COSM, f'Som de entrada {id_som}: ligado ao arquivo em ARQ_SOM')

    # ---- script do dono: dar DRC (livro-razão 'ajuste', saldo nunca negativo) ----
    import conceder_drc
    ana_id = ids['ana']
    antes_saldo = db.session.get(Person, ana_id).bazinga_coins or 0
    novo = conceder_drc.ajustar(ana_id, 40000)
    ok(novo == antes_saldo + 40000, f'conceder_drc: +40.000 DRC ({antes_saldo} -> {novo})')
    mov = MovimentoDrc.query.filter_by(person_id=ana_id, motivo='ajuste').order_by(MovimentoDrc.id.desc()).first()
    ok(mov is not None and mov.delta == 40000 and mov.saldo_apos == novo, 'conceder_drc: o movimento "ajuste" guarda o delta e o saldo que ficou')
    ok(loja.extrato(db.session.get(Person, ana_id))['itens'][0]['rotulo'] == 'Ajuste', 'conceder_drc: aparece no extrato como "Ajuste"')
    n_antes = MovimentoDrc.query.filter_by(person_id=ana_id).count()
    ok(conceder_drc.ajustar(ana_id, -(novo + 1)) is None and MovimentoDrc.query.filter_by(person_id=ana_id).count() == n_antes
       and db.session.get(Person, ana_id).bazinga_coins == novo, 'conceder_drc: tirar mais do que a pessoa tem não grava nada')
    ok(conceder_drc.ajustar(ana_id, -1000) == novo - 1000, 'conceder_drc: valor negativo tira DRC')

    # ---- Bazar: filtros em dois blocos separados ----
    BAZAR_JS = open(os.path.join(RAIZ, 'js', 'bazar.js'), encoding='utf-8').read()
    BAZAR_CSS = open(os.path.join(RAIZ, 'css', 'bazar.css'), encoding='utf-8').read()
    ok(BAZAR_JS.count('class="bz-fgrupo"') == 2 and 'bz-frotulo' in BAZAR_JS and '.bz-fgrupo + .bz-fgrupo' in BAZAR_CSS and '#bz-v-feed { display: flex; flex-direction: column; gap:' in BAZAR_CSS,
       'Bazar: os filtros são dois blocos rotulados e o feed tem espaçamento entre as partes')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
