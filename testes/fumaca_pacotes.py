"""Rodada 37: pacotes (bundles) do Estúdio e efeito do Estúdio à venda.
Validação (itens, tipos, preço fixo nunca acima da soma, listas fechadas), só admin escreve, estados (rascunho não existe pro app, só dar não tem preço, à venda entra no
Armazém), compra que entrega TODOS os itens (inclusive os que não são vendidos avulsos), abatimento do que a pessoa já tem, saldo curto não entrega nada, prazo de venda,
equipar tudo, dar/tirar pelo Estúdio, recompensa do passe, apagar sem tirar os itens de quem comprou, efeito em uso não apaga, recarregar do banco e o que o cliente promete.
Banco SQLite em memória; nada vai à rede."""
import os, sys, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from sqlalchemy import update
from app import create_app, db, socketio, efeitos, loja, pacotes, passe
from app import cosmeticos as cos
from app.bazar import definir_admin
from app.models import Role, Person, Posse, PacoteCustom, EfeitoCustom, MovimentoDrc

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def levanta(exc, fn):
    try:
        fn()
    except exc:
        db.session.rollback()
        return True
    return False


def ler(*partes):
    return open(os.path.join(RAIZ, *partes), encoding='utf-8').read()


H = {'X-Requested-With': 'fetch'}
C = cos.CATALOGO
with app.app_context():
    db.create_all()
    r = Role(name='M', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for nome, saldo in (('adm', 500), ('ana', 9000), ('beto', 500), ('carol', 100), ('dani', 500)):
        p = Person(name=nome, email=f'{nome}@x', role_id=r.id, username=nome, bazinga_coins=saldo); db.session.add(p); db.session.commit(); ids[nome] = p.id
    definir_admin(ids['adm'])

    def cli(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        sc = socketio.test_client(app, flask_test_client=fc); sc.get_received()
        return fc, sc

    def eu(nome):
        return db.session.get(Person, ids[nome])

    def posses(nome):
        db.session.expire_all()
        return {x.item_id: x.origem for x in Posse.query.filter_by(person_id=ids[nome]).all()}

    def saldo(nome):
        db.session.expire_all()
        return eu(nome).bazinga_coins

    fadm, _ = cli('adm'); fana, sana = cli('ana'); fbeto, sbeto = cli('beto')

    # ---------- efeito do Estúdio à venda avulso ----------
    corpo_fx = {'id': 'luz_do_estudio', 'nome': 'Luz do Estúdio', 'tipo': 'efeito_avatar', 'raridade': 'epico', 'descricao': 'Teste',
                'receita': {'pausa': 0, 'camadas': [{'tipo': 'anel', 'cor': '#f2c14e'}]}}
    ok(fadm.post('/estudio/api/efeitos', json=corpo_fx, headers=H).status_code == 200, 'Cria um efeito do Estúdio (sem vender)')
    ok(not C['efeito_avatar:luz_do_estudio'].get('preco') and not cos.TEMAS['estudio']['loja'], 'Sem "vender", o efeito não tem preço e o tema Estúdio fica fora da vitrine')
    corpo_vende = {'id': 'faisca_azul', 'nome': 'Faísca Azul', 'tipo': 'efeito_perfil', 'raridade': 'epico', 'descricao': 'À venda', 'vender': True,
                   'receita': {'pausa': 0, 'camadas': [{'tipo': 'brilho', 'cor': '#7cc4ff'}]}}
    ok(fadm.post('/estudio/api/efeitos', json=corpo_vende, headers=H).status_code == 200, 'Cria um efeito marcado "vender"')
    fa = C['efeito_perfil:faisca_azul']
    ok(fa.get('preco') == cos.PRECOS['epico']['efeito_perfil'], f'O preço do efeito vem da tabela PRECOS (epico x efeito_perfil = {fa.get("preco")})')
    ok(cos.TEMAS['estudio']['loja'] and cos.TEMAS['estudio']['categoria'] in cos.IDS_CATEGORIA and cos.TEMAS['estudio']['so_avulsos'], 'Com um efeito à venda, o tema Estúdio entra na vitrine')
    lst = fadm.get('/estudio/api/efeitos').get_json()
    ok(next(e for e in lst['efeitos'] if e['id'] == 'faisca_azul')['vender'] and lst['precos']['epico']['efeito_perfil'] == fa['preco'], 'A lista de efeitos diz quem está à venda e traz a tabela de preços')
    ok(fadm.post('/estudio/api/efeitos', json={**corpo_vende, 'vender': 'sim'}, headers=H).status_code == 200 and not C['efeito_perfil:faisca_azul'].get('preco'),
       '"vender" só vale se for exatamente true (texto solto não liga a venda)')
    fadm.post('/estudio/api/efeitos', json=corpo_vende, headers=H)
    ok('efeito_perfil:faisca_azul' not in loja._candidatas_reliquia(), 'Efeito do Estúdio não entra na relíquia da semana (a lista não muda a cada efeito novo)')
    vit = loja.vitrine_para_json(eu('ana'))
    json.dumps(vit)
    ok(any(i['id'] == 'efeito_perfil:faisca_azul' and i['preco_final'] == fa['preco'] for i in vit['itens']), 'O efeito à venda aparece na vitrine com o preço')
    t_est = next(t for t in vit['temas'] if t['id'] == 'estudio')
    ok(t_est['itens'] == ['efeito_perfil:faisca_azul'] and t_est['pacote'] is None and t_est['preco_soma'] == fa['preco'], 'O tema Estúdio lista só o que está à venda e não tem pacote')
    s0 = saldo('ana')
    res = loja.comprar(eu('ana'), 'efeito_perfil:faisca_azul')
    ok(res['preco'] == fa['preco'] and saldo('ana') == s0 - fa['preco'] and posses('ana').get('efeito_perfil:faisca_azul') == 'loja', 'Comprar o efeito: débito certo e posse com origem loja')

    # ---------- validação do pacote ----------
    base = {'id': 'combo_teste', 'nome': 'Combo de Teste', 'descricao': 'Misturado', 'estado': 'a_venda',
            'itens': ['moldura:relojoaria', 'nome:dualidade', 'placa:marmore', 'efeito_avatar:luz_do_estudio']}
    soma_esp = sum(cos.preco_de_tabela(i) for i in base['itens'])
    ok(soma_esp == 550 + 350 + cos.PRECOS['epico']['placa'] + cos.PRECOS['epico']['efeito_avatar'], f'Preço de referência: vendido avulso usa o da loja, o resto usa a tabela (soma {soma_esp})')
    ok(cos.preco_de_tabela('badge:criador') == 0 and cos.preco_de_tabela('nao:existe') == 0, 'Insígnia e item que não existe valem 0 na referência')

    def valida(**mud):
        return pacotes._validar({**base, **mud})

    E = pacotes.ErroPacote
    ok(levanta(E, lambda: valida(itens=['moldura:relojoaria'])), 'Um item só: recusado (mínimo 2)')
    ok(levanta(E, lambda: valida(itens=['moldura:relojoaria', 'moldura:gojo'])), 'Dois itens do mesmo tipo: recusado (um por slot)')
    ok(levanta(E, lambda: valida(itens=['moldura:relojoaria', 'moldura:nao_existe'])), 'Item que não existe: recusado')
    ok(levanta(E, lambda: valida(itens=['moldura:relojoaria', 'badge:criador'])), 'Insígnia no pacote: recusada')
    ok(levanta(E, lambda: valida(itens=['moldura:relojoaria', 'efeito_servidor:gogeta'])), 'Efeito de servidor no pacote: recusado (não é um slot da pessoa)')
    ok(levanta(E, lambda: valida(itens=['moldura:relojoaria', 'pacote:gojo'])), 'Pacote dentro de pacote: recusado')
    ok(levanta(E, lambda: valida(itens='moldura:relojoaria')), 'Itens que não é lista: recusado')
    ok(levanta(E, lambda: valida(id='Com Espaco1')) and levanta(E, lambda: valida(id='a')), 'Id inválido: recusado')
    ok(levanta(E, lambda: valida(nome='x')), 'Nome curto: recusado')
    ok(levanta(E, lambda: valida(icone='fa-skull" onclick="x')), 'Ícone fora da lista fechada: recusado')
    ok(levanta(E, lambda: valida(categoria='inventada')), 'Categoria fora da lista: recusada')
    ok(levanta(E, lambda: valida(cor1='javascript:alert(1)')) and levanta(E, lambda: valida(cor2='red')), 'Cor que não é #rrggbb: recusada')
    ok(levanta(E, lambda: valida(estado='publicado')), 'Estado fora da lista: recusado')
    ok(levanta(E, lambda: valida(ate='amanhã')) and levanta(E, lambda: valida(ate='2026-13-45')), 'Data de fim inválida: recusada')
    ok(levanta(E, lambda: valida(preco=soma_esp + 1)), 'Preço fixo acima da soma: recusado (nunca custa mais que comprar avulso)')
    ok(levanta(E, lambda: valida(preco='barato')) and levanta(E, lambda: valida(preco=-5)), 'Preço fixo que não é número positivo: recusado')
    ok(valida(preco=soma_esp)['preco'] == soma_esp and valida(preco='')['preco'] is None and valida(preco=0)['preco'] is None, 'Preço fixo até a soma passa; vazio ou 0 = automático')
    v = valida(itens=['moldura:relojoaria', 'nome:dualidade', 'nome:dualidade'])
    ok(v['itens'] == ['moldura:relojoaria', 'nome:dualidade'], 'Item repetido na lista é dito uma vez só')
    ok(pacotes._data_fim('2026-12-31') == __import__('datetime').datetime(2026, 12, 31, 23, 59, 59) and pacotes._data_fim('') is None, 'Data de fim "AAAA-MM-DD" vale até 23:59:59 daquele dia')
    ok(levanta(E, lambda: pacotes.salvar({**base, 'id': 'gojo'})), 'Id que já é de um tema (gojo): recusado')
    ok(pacotes.preco_automatico(750) == 550 and pacotes.preco_automatico(250) == 200 and pacotes.preco_automatico(10) == 50,
       'Preço automático: soma - 30%, múltiplo de 50, metade pra cima (750 -> 550), nunca menos de 50')

    # ---------- API: só admin ----------
    ok(fana.get('/estudio/api/pacotes').status_code == 403 and fana.post('/estudio/api/pacotes', json=base, headers=H).status_code == 403, 'Não-admin não vê nem cria pacote')
    ok(fadm.post('/estudio/api/pacotes', json=base).status_code == 400, 'Sem o cabeçalho anti-forja: recusado')
    ok(fana.delete('/estudio/api/pacotes/combo_teste', headers=H).status_code == 403, 'Não-admin não apaga pacote')
    lst = fadm.get('/estudio/api/pacotes').get_json()
    tipos_ui = {i['tipo'] for i in lst['catalogo']}
    ok(not (tipos_ui & {'badge', 'pacote', 'efeito_servidor'}) and {'moldura', 'nome', 'placa', 'faixa', 'efeito_avatar', 'som_call', 'pin_nota'} <= tipos_ui,
       'O seletor do Estúdio só traz o que se equipa (sem insígnia, pacote e efeito de servidor)')
    gojo = next(i for i in lst['catalogo'] if i['id'] == 'moldura:gojo')
    luz = next(i for i in lst['catalogo'] if i['id'] == 'efeito_avatar:luz_do_estudio')
    marm = next(i for i in lst['catalogo'] if i['id'] == 'placa:marmore')
    ok(gojo['ref'] == C['moldura:gojo']['preco'] and gojo['avulso'] and luz['ref'] == cos.PRECOS['epico']['efeito_avatar'] and not luz['avulso'] and luz['estudio'] and marm['ref'] > 0 and not marm['avulso'],
       'Cada item traz o preço de referência e se é vendido avulso (efeito do Estúdio e prêmio do passe: não)')
    ok(lst['desconto'] == int(cos.DESCONTO_PACOTE * 100) and lst['min_itens'] == 2 and set(lst['estados']) == {'rascunho', 'a_venda', 'so_dar'}
       and all(i.startswith('fa-') for i in lst['icones']) and {c['id'] for c in lst['categorias']} == set(cos.IDS_CATEGORIA), 'A API traz estados, ícones, categorias, desconto e mínimo')

    # ---------- rascunho: só existe no banco ----------
    rr = fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'rascunho'}, headers=H)
    ok(rr.status_code == 200 and rr.get_json()['id'] == 'combo_teste', 'Admin cria o pacote como rascunho')
    ok(PacoteCustom.query.get('combo_teste') is not None and 'pacote:combo_teste' not in C and 'combo_teste' not in cos.TEMAS and 'combo_teste' not in cos.PACOTES,
       'Rascunho está no banco, mas o app nem sabe dele (catálogo, temas e pacotes vazios)')
    ok(fadm.post('/estudio/api/itens/conceder', json={'item_id': 'pacote:combo_teste', 'person_id': ids['ana']}, headers=H).status_code == 400, 'Rascunho não pode ser dado')
    ok(not any(i['id'] == 'pacote:combo_teste' for i in loja.vitrine_para_json(eu('ana'))['itens']), 'Rascunho não aparece na loja')
    jr = next(p for p in fadm.get('/estudio/api/pacotes').get_json()['pacotes'] if p['id'] == 'combo_teste')
    ok(jr['estado'] == 'rascunho' and jr['no_ar'] is False and jr['soma'] == soma_esp and jr['preco_auto'] == pacotes.preco_automatico(soma_esp), 'O Estúdio mostra o rascunho com a soma e o preço automático')

    # ---------- só dar ----------
    ok(fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'so_dar'}, headers=H).status_code == 200, 'Muda pra "só dar"')
    pk = C['pacote:combo_teste']
    ok(pk['tipo'] == 'pacote' and pk.get('estudio') and not pk.get('preco') and pk['tema'] == 'combo_teste', 'Só dar: existe no catálogo, sem preço')
    ok(cos.PACOTES['combo_teste'] == {'moldura': 'relojoaria', 'nome': 'dualidade', 'placa': 'marmore', 'efeito_avatar': 'luz_do_estudio'}, 'PACOTES guarda um item por tipo (de temas diferentes)')
    ok(cos.TEMAS['combo_teste']['loja'] is False and cos.TEMAS['combo_teste']['combo'] and cos.TEMAS['combo_teste']['estudio'], 'O tema do pacote é "combo" e fora da vitrine')
    ok(pk['raridade'] == 'epico', 'A raridade do pacote é a maior dos itens')
    ok(not any(i['id'] == 'pacote:combo_teste' for i in loja.vitrine_para_json(eu('ana'))['itens']), 'Só dar não aparece na loja')
    ok(levanta(loja.ErroLoja, lambda: loja.comprar(eu('ana'), 'pacote:combo_teste')), 'Só dar não se compra')
    ok(sorted(cos.itens_para_conceder('pacote:combo_teste')) == sorted(base['itens'] + ['pacote:combo_teste']), 'Entregar o pacote = os 4 itens + o pacote (inclusive os que não têm preço)')
    ok(cos.itens_para_conceder('moldura:gojo') == ['moldura:gojo'] and cos.itens_para_conceder('nao:existe') == [], 'Item solto entrega só ele mesmo')

    # ---------- à venda ----------
    auto = pacotes.preco_automatico(soma_esp)
    ok(fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'a_venda'}, headers=H).status_code == 200 and C['pacote:combo_teste']['preco'] == auto and auto < soma_esp,
       f'À venda com preço automático ({auto} DRC, abaixo da soma {soma_esp})')
    ok(cos.TEMAS['combo_teste']['loja'] is True, 'À venda: o tema do pacote entra na vitrine')
    vit = loja.vitrine_para_json(eu('beto'))
    json.dumps(vit)
    pj = next(i for i in vit['itens'] if i['id'] == 'pacote:combo_teste')
    ok(pj['preco'] == auto and pj['preco_final'] == auto and pj['grupo'] == 'pacote', 'O pacote aparece na loja (grupo Pacotes) com o preço automático')
    tj = next(t for t in vit['temas'] if t['id'] == 'combo_teste')
    ok(sorted(tj['itens']) == sorted(base['itens']) and tj['pacote'] == 'pacote:combo_teste' and tj['preco_soma'] == soma_esp and tj['preco_pacote'] == auto and tj['categoria'] == 'fantasia'
       and tj['cores'] == ['#d4a24c', '#3a2f1c'] and tj['icone'] == 'fa-box-open', 'O tema do pacote lista TODOS os itens (também os sem preço), soma da tabela e preço do pacote')
    ex = {i['id']: i for i in vit['extras']}
    ok(set(ex) == {'placa:marmore', 'efeito_avatar:luz_do_estudio'} and all(i['fora_da_loja'] and i['pacote_id'] == 'pacote:combo_teste' and i['preco'] == 0 for i in ex.values()),
       '`extras`: só os itens do pacote que não são vendidos avulsos (a moldura e o nome, vendidos, não vêm aqui)')
    ok(not any(i['id'] in ex for i in vit['itens']), 'Os extras não entram nas prateleiras (não se compram sozinhos)')
    ok(levanta(loja.ErroLoja, lambda: loja.comprar(eu('beto'), 'placa:marmore')) and levanta(loja.ErroLoja, lambda: loja.comprar(eu('beto'), 'efeito_avatar:luz_do_estudio')),
       'Item do pacote sem preço avulso não se compra sozinho')
    ok(fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'a_venda', 'preco': soma_esp + 5}, headers=H).status_code == 400, 'API: preço fixo acima da soma: recusado')
    ok(fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'a_venda', 'preco': 1000}, headers=H).status_code == 200 and C['pacote:combo_teste']['preco'] == 1000, 'Preço fixo vale')
    fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'a_venda'}, headers=H)
    ok(C['pacote:combo_teste']['preco'] == auto, 'Voltar pro automático recalcula')

    # ---------- comprar: entrega tudo, atômico ----------
    s0 = saldo('carol')
    ok(levanta(loja.ErroLoja, lambda: loja.comprar(eu('carol'), 'pacote:combo_teste')) and saldo('carol') == s0 and not posses('carol'), 'Sem saldo: nada é entregue e nada é debitado')
    sana.get_received()
    s0 = saldo('ana')
    res = loja.comprar(eu('ana'), 'pacote:combo_teste')
    pa = posses('ana')
    ok(res['preco'] == auto and saldo('ana') == s0 - auto, f'Comprar o pacote debita o preço do pacote ({auto})')
    ok(all(i in pa and pa[i] == 'loja' for i in base['itens'] + ['pacote:combo_teste']), 'Entrega o pacote E os 4 itens (também o efeito do Estúdio e o item do passe, que não são vendidos avulsos)')
    mv = MovimentoDrc.query.filter_by(person_id=ids['ana'], motivo='compra', ref='pacote:combo_teste').all()
    ok(len(mv) == 1 and mv[0].delta == -auto, 'Um lançamento no extrato, com o pacote como referência')
    ok(levanta(loja.ErroLoja, lambda: loja.comprar(eu('ana'), 'pacote:combo_teste')), 'Comprar de novo: "você já tem"')
    # abatimento: quem já tem um item paga menos
    db.session.execute(update(Person).where(Person.id == ids['beto']).values(bazinga_coins=5000)); db.session.commit()
    loja.comprar(eu('beto'), 'moldura:relojoaria')
    s0 = saldo('beto')
    esperado = round(auto * (soma_esp - 550) / soma_esp)
    pr, entregues = loja.preco_para(posses('beto').keys() | set(), 'pacote:combo_teste')
    ok(pr == esperado and 'moldura:relojoaria' not in entregues and len(entregues) == 4, f'Quem já tem a moldura paga proporcional ao que falta ({pr} DRC) e leva só o que não tem')
    res = loja.comprar(eu('beto'), 'pacote:combo_teste')
    ok(res['preco'] == esperado and saldo('beto') == s0 - esperado and all(i in posses('beto') for i in base['itens']), 'A compra com abatimento entrega o que faltava')
    ok(loja.itens_comprados(ids['ana']) == 5 and loja.itens_comprados(ids['beto']) == 4, 'Os itens do pacote contam pra coleção como os dos pacotes da loja (o efeito avulso e os 4 do pacote)')

    # ---------- equipar tudo ----------
    sana.get_received()
    sana.emit('equipar_item', {'item_id': 'pacote:combo_teste'})
    db.session.expire_all()
    a = eu('ana')
    ok(a.moldura == 'relojoaria' and a.placa == 'marmore' and a.nome_estilo == 'dualidade' and json.loads(a.equipados).get('efeito_avatar') == 'luz_do_estudio',
       'Equipar o pacote equipa os 4 itens de temas diferentes de uma vez')
    sana.emit('listar_inventario', {})
    inv = [m for m in sana.get_received() if m['name'] == 'inventario'][0]['args'][0]
    ok(any(i['id'] == 'pacote:combo_teste' for i in inv['catalogo']) and 'combo_teste' in inv['temas'], 'O pacote aparece no inventário e o tema dele tem nome e cor')
    # quem tem o pacote mas não um dos itens só equipa o que tem
    fadm.post('/estudio/api/itens/conceder', json={'item_id': 'pacote:combo_teste', 'person_id': ids['dani']}, headers=H)
    pdani = posses('dani')
    ok(all(i in pdani for i in base['itens'] + ['pacote:combo_teste']) and all(pdani[i] == 'admin' for i in pdani), 'Admin dá o pacote: 5 posses, todas com origem admin')
    ok(fadm.post('/estudio/api/itens/conceder', json={'item_id': 'pacote:combo_teste', 'person_id': ids['dani']}, headers=H).status_code == 200 and len(posses('dani')) == 5, 'Dar de novo não duplica')

    # ---------- prazo de venda ----------
    ok(fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'a_venda', 'ate': '2020-01-01'}, headers=H).status_code == 200, 'Pacote com fim de venda no passado')
    lim = C['pacote:combo_teste'].get('limitado')
    ok(lim and lim['ate'].year == 2020 and lim['estoque'] is None, 'O fim da venda vira prazo (sem estoque)')
    vit = loja.vitrine_para_json(eu('carol'))
    ok(next(i for i in vit['itens'] if i['id'] == 'pacote:combo_teste')['limitado']['encerrado'], 'A loja mostra o pacote como encerrado (visível, mas não compra)')
    db.session.execute(update(Person).where(Person.id == ids['carol']).values(bazinga_coins=9000)); db.session.commit()
    ok(levanta(loja.ErroLoja, lambda: loja.comprar(eu('carol'), 'pacote:combo_teste')) and not posses('carol'), 'Depois do fim da venda não se compra (e nada é entregue)')
    fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'a_venda', 'ate': '2999-01-01'}, headers=H)
    vit = loja.vitrine_para_json(eu('carol'))
    ok(not next(i for i in vit['itens'] if i['id'] == 'pacote:combo_teste')['limitado']['encerrado'], 'Com o fim no futuro a venda continua aberta')
    fadm.post('/estudio/api/pacotes', json={**base, 'estado': 'a_venda'}, headers=H)
    ok(C['pacote:combo_teste'].get('limitado') is None, 'Sem data de fim, não há prazo')

    # ---------- dar e tirar pelo Estúdio ----------
    Posse.query.filter_by(person_id=ids['dani'], item_id='nome:dualidade').update({'origem': 'loja'}); db.session.commit()      # esse a Dani "comprou": tirar o pacote não pode levar
    ok(fadm.post('/estudio/api/itens/conceder', json={'item_id': 'pacote:combo_teste', 'person_id': ids['dani'], 'ativo': False}, headers=H).status_code == 200, 'Admin tira o pacote')
    pd = posses('dani')
    ok('pacote:combo_teste' not in pd and 'placa:marmore' not in pd and 'efeito_avatar:luz_do_estudio' not in pd, 'Tirar o pacote tira o carimbo e os itens que o admin tinha dado')
    ok(pd.get('nome:dualidade') == 'loja', 'O item que a pessoa já tinha de outro jeito (comprado) fica')
    ok(fadm.post('/estudio/api/itens/conceder', json={'item_id': 'pacote:gojo', 'person_id': ids['dani']}, headers=H).status_code == 200
       and 'pacote:gojo' in posses('dani') and 'moldura:gojo' in posses('dani'), 'Pacote da loja também se dá: chega com todos os itens')

    # ---------- recompensa do passe ----------
    rec_ok = passe._validar_recompensa({'nivel': 1, 'trilha': 'gratis', 'tipo': 'item', 'valor': 'pacote:combo_teste'}, 100)
    ok(rec_ok[2] == 'item' and rec_ok[3] == 'pacote:combo_teste', 'Pacote do Estúdio pode ser recompensa do passe')
    ok(levanta(passe.ErroPasse, lambda: passe._validar_recompensa({'nivel': 1, 'trilha': 'gratis', 'tipo': 'item', 'valor': 'pacote:gojo'}, 100)), 'Pacote da loja continua fora do passe')
    res = {'moedas': 0, 'itens': [], 'qtd': 0}
    passe._entregar(eu('carol'), {'tipo': 'item', 'valor': 'pacote:combo_teste', 'quantidade': 0}, 1, res); db.session.commit()
    pc = posses('carol')
    ok(all(pc.get(i) == 'passe' for i in base['itens'] + ['pacote:combo_teste']) and len(res['itens']) == 1 and res['itens'][0]['item_id'] == 'pacote:combo_teste', 'O passe entrega o pacote inteiro (origem passe) e conta como UM prêmio')
    res2 = {'moedas': 0, 'itens': [], 'qtd': 0}
    passe._entregar(eu('carol'), {'tipo': 'item', 'valor': 'pacote:combo_teste', 'quantidade': 0}, 1, res2); db.session.commit()
    ok(res2['itens'] == [] and len(posses('carol')) == 5, 'Entregar de novo não duplica nem conta prêmio')

    # ---------- editar, item que some, efeito em uso, apagar ----------
    ok(levanta(efeitos.ErroEfeito, lambda: efeitos.apagar('luz_do_estudio')), 'Efeito que está num pacote não se apaga')
    ok(fadm.delete('/estudio/api/efeitos/luz_do_estudio', headers=H).status_code == 400 and 'Combo de Teste' in fadm.delete('/estudio/api/efeitos/luz_do_estudio', headers=H).get_json()['erro'],
       'A API diz em qual pacote o efeito está')
    novo = {**base, 'itens': ['moldura:relojoaria', 'nome:dualidade']}
    ok(fadm.post('/estudio/api/pacotes', json=novo, headers=H).status_code == 200 and cos.PACOTES['combo_teste'] == {'moldura': 'relojoaria', 'nome': 'dualidade'}, 'Editar os itens atualiza o que o pacote entrega')
    ok(C['pacote:combo_teste']['preco'] == pacotes.preco_automatico(550 + 350), 'E recalcula o preço automático')
    ok(fadm.delete('/estudio/api/efeitos/luz_do_estudio', headers=H).status_code == 200 and 'efeito_avatar:luz_do_estudio' not in C, 'Tirado do pacote, o efeito pode ser apagado')
    ok(fadm.post('/estudio/api/pacotes', json=base, headers=H).status_code == 400, 'Salvar com um item que saiu do catálogo: recusado')
    row = PacoteCustom.query.get('combo_teste')
    row.itens = json.dumps(['moldura:relojoaria', 'efeito_avatar:luz_do_estudio']); db.session.commit()
    pacotes._registrar(row)
    ok('pacote:combo_teste' not in C and 'combo_teste' not in cos.TEMAS, 'Pacote que ficou com menos de 2 itens que existem sai do catálogo (sem quebrar)')
    jr = next(p for p in pacotes.listar() if p['id'] == 'combo_teste')
    ok(jr['faltando'] == ['efeito_avatar:luz_do_estudio'] and jr['no_ar'] is False, 'O Estúdio avisa qual item sumiu')
    row.itens = json.dumps(['moldura:relojoaria', 'nome:dualidade']); row.estado = 'a_venda'; db.session.commit()
    # reiniciar o servidor: tudo volta do banco
    pacotes._desregistrar('combo_teste')
    ok('pacote:combo_teste' not in C, '(antes do reinício) o pacote não está em memória')
    efeitos.carregar()
    ok('pacote:combo_teste' in C and cos.PACOTES['combo_teste'] == {'moldura': 'relojoaria', 'nome': 'dualidade'} and C['pacote:combo_teste']['preco'], 'Ao ligar o servidor, os pacotes voltam do banco (depois dos efeitos)')
    ok('efeito_perfil:faisca_azul' in C and C['efeito_perfil:faisca_azul'].get('preco') and cos.TEMAS['estudio']['loja'], 'E o efeito à venda também (com o tema Estúdio na vitrine)')

    ok(fadm.delete('/estudio/api/pacotes/combo_teste', headers=H).status_code == 200, 'Admin apaga o pacote')
    ok('pacote:combo_teste' not in C and 'combo_teste' not in cos.TEMAS and 'combo_teste' not in cos.PACOTES and 'combo_teste' not in cos.PACOTES_FIXOS and PacoteCustom.query.get('combo_teste') is None,
       'Apagou do catálogo, dos temas, dos pacotes e do banco')
    pa = posses('ana')
    ok('pacote:combo_teste' not in pa and 'moldura:relojoaria' in pa and 'nome:dualidade' in pa, 'Quem comprou fica com os itens (só o carimbo do pacote some)')
    ok(fadm.delete('/estudio/api/pacotes/combo_teste', headers=H).status_code == 400, 'Apagar de novo: pacote não encontrado')

# ---------- o que o cliente e o repositório prometem ----------
loja_js, est_js, est_html, est_css = ler('app', 'static', 'js', 'loja.js'), ler('app', 'static', 'js', 'estudio.js'), ler('app', 'templates', 'estudio.html'), ler('app', 'static', 'css', 'estudio.css')
ok("(estado.extras || [])" in loja_js and 'fora_da_loja' in loja_js and 'pacote_id' in loja_js, 'loja.js: acha os itens que só vêm no pacote e não oferece compra avulsa')
ok('VISTAS.pacotes' in est_js and "api('/pacotes'" in est_js and 'data-v="pacotes"' in est_html, 'Estúdio: a aba Pacotes existe e fala com /estudio/api/pacotes')
ok('Math.floor(soma * (1 - XP.desconto / 100) / 50 + 0.5)' in est_js, 'A prévia do preço no Estúdio usa a mesma conta (metade pra cima) do servidor')
ok("vender: !!e.vender" in est_js and 'id="ef-vender"' in est_js, 'O editor de efeitos tem o "vender avulso" e manda no salvar')
ok('.es-main .es-dica' in est_css and 'display: revert' in est_css, 'O texto de ajuda do Estúdio não é escondido pela dica flutuante dos gráficos do admin.css')
ok(not re.search(r'class="[^"]*\b(ad-|ads-)', est_js + est_html) and not re.search(r'\.(ad-|ads-)[a-z]', est_css), 'Nenhuma classe começa com ad- ou ads- (bloqueador de anúncio esconde)')
ok('efeito_custom' in ler('atualizar_banco.py') and 'vender BOOLEAN' in ler('atualizar_banco.py'), 'atualizar_banco.py cria a coluna efeito_custom.vender')
ok(c.Config.SQLALCHEMY_DATABASE_URI.startswith('sqlite'), 'Nada foi à rede: SQLite em memória')

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
