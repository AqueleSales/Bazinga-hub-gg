"""Bazar, Rodada 18: reputação (conta nova, limite de loja nova, selo), frete/retirada/endereço, favoritos, ordenação e "perto de mim",
anúncios (datas, cliques, só admin), disputa (travas, admin lê a conversa, decisões), banimento, imagem na conversa do pedido."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from datetime import timedelta
from app import create_app, db, socketio
from app import bazar, bazar_events
from app.bazar import ErroBazar
from app.models import (Role, Person, BazarLoja, BazarProduto, BazarPedido, BazarMensagem, BazarFavorito, BazarAnuncio, BazarDisputa,
                        BazarBanimento, Notificacao, br_now)

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('Ana', 'Beto', 'Cris', 'Duda', 'Eva', 'Fabio', 'Gil', 'Novata'):
        dias = 0 if nome == 'Novata' else 30
        p = Person(name=nome, email=f'{nome.lower()}@x', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=dias))
        db.session.add(p); db.session.commit(); ids[nome.lower()] = p.id

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl

    def emitir(cl, nome, dados=None):
        bazar_events._ultimo.clear()
        cl.emit(nome, dados or {})
        return ev(cl)

    def erro(rec):
        return next((m['args'][0]['msg'] for m in rec if m['name'] == 'bazar_erro'), None)

    def pega(rec, nome):
        return next((m['args'][0] for m in rec if m['name'] == nome), None)

    def varrer(cl, **dados):
        dados.setdefault('seed', 'teste')
        v = pega(emitir(cl, 'bazar_listar', {**dados, 'pagina': 0}), 'bazar_vitrine')
        itens, tem, pg = list(v['feed']['itens']), v['feed']['tem_mais'], 0
        while tem:
            pg += 1
            f = pega(emitir(cl, 'bazar_listar', {**dados, 'pagina': pg}), 'bazar_feed')
            itens += f['itens']; tem = f['tem_mais']
        return v, itens

    lojas_do = lambda itens: [i['loja']['nome'] for i in itens if i['t'] == 'loja']
    micro_do = lambda itens: [p['nome'] for i in itens if i['t'] == 'quad' for p in i['produtos']]
    ana, beto, cris, duda = cliente('ana'), cliente('beto'), cliente('cris'), cliente('duda')
    eva, fabio, gil, novata = cliente('eva'), cliente('fabio'), cliente('gil'), cliente('novata')
    ana2 = cliente('ana')                      # a mesma pessoa em outra aba
    bazar.definir_admin(ids['duda'])
    pessoa = lambda u: db.session.get(Person, ids[u])

    # ---------- 1. REPUTAÇÃO ----------
    rec = emitir(novata, 'bazar_salvar_loja', {'nome': 'Loja da Novata'})
    ok('dias' in (erro(rec) or '') and db.session.query(BazarLoja).filter_by(owner_id=ids['novata']).count() == 0, 'Conta de hoje não abre loja (proteção contra conta descartável)')
    pessoa('novata').created_at = None; db.session.commit()
    rec = emitir(novata, 'bazar_salvar_loja', {'nome': 'Loja da Novata'})
    ok(pega(rec, 'bazar_minha') is not None, 'Conta antiga (sem data de criação) abre loja normalmente')
    db.session.delete(db.session.query(BazarLoja).filter_by(owner_id=ids['novata']).one()); db.session.commit()

    emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'categoria': 'arte', 'porte': 'media', 'pix_chave': 'ana@exemplo.com', 'pix_nome': 'Ana Avila', 'pix_cidade': 'Brasilia'})
    L_ANA = db.session.query(BazarLoja).filter_by(owner_id=ids['ana']).one().id
    rec = emitir(ana, 'bazar_salvar_produto', {'nome': 'Quadro grande', 'preco_cent': 50_000, 'tipo': 'fisico'})
    ok('Loja nova' in (erro(rec) or '') and 'R$ 300,00' in (erro(rec) or ''), 'Loja nova não vende produto acima de R$ 300,00 até concluir 3 vendas')
    rec = emitir(ana, 'bazar_salvar_produto', {'nome': 'Quadro pequeno', 'preco_cent': 30_000, 'tipo': 'fisico', 'frete_cent': 1500, 'aceita_retirada': True, 'estoque': 5})
    ok(pega(rec, 'bazar_minha') is not None, 'Dentro do limite (R$ 300,00) passa')
    L = db.session.get(BazarLoja, L_ANA)
    ok(bazar.reputacao(L) == 'nova', 'Reputação: loja sem vendas é "nova"')
    L.vendas = 3; db.session.commit()
    ok(bazar.reputacao(L) == 'comum', 'Reputação: com 3 vendas concluídas sai do limite ("comum")')
    rec = emitir(ana, 'bazar_salvar_produto', {'nome': 'Quadro grande', 'preco_cent': 50_000, 'tipo': 'fisico'})
    ok(pega(rec, 'bazar_minha') is not None, 'Depois de 3 vendas o limite de valor cai')
    L.vendas, L.nota_qtd, L.nota_soma = 6, 4, 19; db.session.commit()
    ok(bazar.reputacao(L) == 'confiavel', 'Reputação: 6 vendas e nota 4,75 = "confiável"')
    rec = emitir(beto, 'bazar_verificar', {'loja_id': L_ANA})
    ok(erro(rec) and not db.session.get(BazarLoja, L_ANA).verificada, 'Quem não é admin não dá selo de verificada')
    emitir(duda, 'bazar_verificar', {'loja_id': L_ANA, 'ativo': True})
    ok(db.session.get(BazarLoja, L_ANA).verificada is True and bazar.reputacao(db.session.get(BazarLoja, L_ANA)) == 'verificada', 'Admin dá o selo e ele vira a reputação "verificada"')
    emitir(duda, 'bazar_verificar', {'loja_id': L_ANA, 'ativo': False})
    L.vendas, L.nota_qtd, L.nota_soma = 1, 0, 0; db.session.commit()      # volta pro resto do teste

    # ---------- 2. FRETE, RETIRADA E ENDEREÇO ----------
    P_FIS = db.session.query(BazarProduto).filter_by(nome='Quadro pequeno').one().id
    pj = bazar.produto_json(db.session.get(BazarProduto, P_FIS))
    ok(pj['entregas'] == ['envio', 'retirada'] and pj['frete_cent'] == 1500, 'Produto físico com frete e retirada oferece os dois modos')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': P_FIS})
    ok('como quer receber' in (erro(rec) or '').lower(), 'Com dois modos de entrega, o comprador precisa escolher')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': P_FIS, 'entrega': 'envio'})
    ok('endereço' in (erro(rec) or '').lower(), 'Envio sem endereço é recusado')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': P_FIS, 'entrega': 'envio', 'endereco': 'Rua 1'})
    ok('endereço completo' in (erro(rec) or '').lower(), 'Endereço curto demais é recusado')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': P_FIS, 'entrega': 'envio', 'endereco': 'veja https://golpe.com/x'})
    ok('links' in (erro(rec) or '').lower(), 'Link no endereço é recusado')
    ok(db.session.query(BazarPedido).count() == 0, 'Nenhum pedido inválido foi aberto')
    emitir(beto, 'bazar_pedir', {'produto_id': P_FIS, 'quantidade': 2, 'entrega': 'envio', 'endereco': 'Rua das Flores 10, Samambaia, Brasília, 72300-000'})
    ped = db.session.query(BazarPedido).one()
    ok(ped.total_cent == 30_000 * 2 + 1500 and ped.frete_cent == 1500 and ped.entrega_modo == 'envio', 'Total = preço x quantidade + frete (R$ 601,50)')
    pj_v = bazar.pedido_json(ped, ids['ana'])
    pj_c = bazar.pedido_json(ped, ids['beto'])
    ok(pj_v.get('endereco', '').startswith('Rua das Flores') and pj_c.get('endereco', '').startswith('Rua das Flores'), 'As duas pontas veem o endereço')
    ok(pj_v['subtotal_cent'] == 60_000 and pj_v['frete_cent'] == 1500 and pj_v['entrega_rotulo'] == 'Envio', 'O pedido mostra subtotal, frete e o modo de entrega')
    emitir(ana, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'aceitar'})
    pj_c = bazar.pedido_json(db.session.get(BazarPedido, ped.id), ids['beto'])
    ok(pj_c['pix']['valor_cent'] == 60_000 + 1500, 'O Pix cobra o TOTAL com frete')
    rec = emitir(cris, 'bazar_abrir_pedido', {'pedido_id': ped.id})
    ok(erro(rec) and not pega(rec, 'bazar_pedido'), 'Terceiro não abre o pedido (nem vê o endereço)')
    emitir(beto, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'cancelar'})
    p_fim = db.session.get(BazarPedido, ped.id)
    ok(p_fim.status == 'cancelado' and p_fim.endereco is None and db.session.get(BazarProduto, P_FIS).estoque == 5, 'Ao terminar o pedido o endereço é APAGADO e o estoque volta')
    ok('endereco' not in bazar.pedido_json(p_fim, ids['ana']), '...e o vendedor não vê mais o endereço')
    emitir(beto, 'bazar_pedir', {'produto_id': P_FIS, 'entrega': 'retirada'})
    ped2 = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    ok(ped2.total_cent == 30_000 and ped2.frete_cent == 0 and ped2.endereco is None and ped2.entrega_modo == 'retirada', 'Retirada em mãos: sem frete e sem endereço')
    emitir(beto, 'bazar_agir', {'pedido_id': ped2.id, 'acao': 'cancelar'})
    emitir(ana, 'bazar_salvar_produto', {'nome': 'Arquivo digital', 'preco_cent': 1000, 'tipo': 'digital', 'frete_cent': 999, 'aceita_retirada': True})
    P_DIG = db.session.query(BazarProduto).filter_by(nome='Arquivo digital').one().id
    pjd = bazar.produto_json(db.session.get(BazarProduto, P_DIG))
    ok(pjd['entregas'] == ['digital'] and pjd['frete_cent'] is None and not pjd['aceita_retirada'], 'Produto digital ignora frete/retirada e entrega "digital"')
    emitir(beto, 'bazar_pedir', {'produto_id': P_DIG, 'entrega': 'envio', 'endereco': 'Rua das Flores 10, Samambaia'})
    pd_ = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    ok(pd_.entrega_modo == 'digital' and pd_.frete_cent == 0 and pd_.endereco is None and pd_.total_cent == 1000, 'Pedir "envio" de produto digital não grava endereço nem soma frete (o servidor escolhe o modo)')
    emitir(beto, 'bazar_agir', {'pedido_id': pd_.id, 'acao': 'cancelar'})
    emitir(ana, 'bazar_salvar_produto', {'nome': 'Sem frete definido', 'preco_cent': 800, 'tipo': 'fisico'})
    P_SF = db.session.query(BazarProduto).filter_by(nome='Sem frete definido').one().id
    ok(bazar.produto_json(db.session.get(BazarProduto, P_SF))['entregas'] == ['combinar'], 'Físico sem frete nem retirada = "a combinar na conversa" (como era antes)')
    rec = emitir(ana, 'bazar_salvar_produto', {'nome': 'Caro frete', 'preco_cent': 800, 'tipo': 'fisico', 'frete_cent': 99_999_999})
    ok('frete' in (erro(rec) or '').lower(), 'Frete absurdo é recusado')

    # ---------- 3. IMAGEM NA CONVERSA DO PEDIDO ----------
    emitir(beto, 'bazar_pedir', {'produto_id': P_SF})
    ped3 = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    rec = emitir(beto, 'bazar_mensagem', {'pedido_id': ped3.id})
    ok('imagem' in (erro(rec) or '').lower(), 'Mensagem vazia (sem texto nem imagem) é recusada')
    rec = emitir(beto, 'bazar_mensagem', {'pedido_id': ped3.id, 'imagem_url': 'https://evil.com/p.png'})
    ok('imagem' in (erro(rec) or '').lower() and db.session.query(BazarMensagem).count() == 0, 'Imagem de host qualquer é recusada')
    emitir(beto, 'bazar_mensagem', {'pedido_id': ped3.id, 'imagem_url': 'https://res.cloudinary.com/x/comprovante.png'})
    m = db.session.query(BazarMensagem).one()
    ok(m.texto == '' and m.imagem_url.endswith('comprovante.png'), 'Só imagem (comprovante do Pix) vale como mensagem')
    ok(bazar.pedido_json(ped3, ids['ana'], com_mensagens=True)['mensagens'][0]['imagem'].endswith('comprovante.png'), 'A outra ponta recebe a imagem na conversa')
    rec = emitir(ana2, 'bazar_abrir_pedido', {'pedido_id': ped3.id})
    emitir(beto, 'bazar_agir', {'pedido_id': ped3.id, 'acao': 'cancelar'})

    # ---------- 4. FAVORITOS ----------
    emitir(cris, 'bazar_salvar_loja', {'nome': 'Cantinho do Cris', 'categoria': 'digital', 'porte': 'micro', 'pix_chave': '52998224725'})
    emitir(cris, 'bazar_salvar_produto', {'nome': 'Pack de sons', 'preco_cent': 1500, 'tipo': 'digital'})
    L_CRIS = db.session.query(BazarLoja).filter_by(owner_id=ids['cris']).one().id
    ev(ana2)
    rec = emitir(ana, 'bazar_favoritar', {'loja_id': L_ANA, 'ativo': True})
    ok('própria loja' in (erro(rec) or ''), 'Não dá pra favoritar a própria loja')
    emitir(beto, 'bazar_favoritar', {'loja_id': L_ANA, 'ativo': True})
    emitir(beto, 'bazar_favoritar', {'loja_id': L_ANA, 'ativo': True})
    ok(db.session.query(BazarFavorito).filter_by(person_id=ids['beto']).count() == 1, 'Favoritar duas vezes (duas abas) deixa UMA linha só')
    beto_aba2 = cliente('beto')
    emitir(beto, 'bazar_favoritar', {'loja_id': L_CRIS, 'ativo': True})
    ok(sorted(pega(ev(beto_aba2), 'bazar_favoritos')['ids']) == sorted([L_ANA, L_CRIS]), 'Regra 6: a outra aba do Beto recebe a lista de favoritos')
    v, _ = varrer(beto)
    ok(sorted(v['favoritos']) == sorted([L_ANA, L_CRIS]), 'A vitrine traz os favoritos da pessoa')
    _, so_fav = varrer(beto, favoritas=True)
    ok(lojas_do(so_fav) == ['Ateliê da Ana'] and 'Pack de sons' in micro_do(so_fav), 'Filtro "só favoritas" mostra só o que ele segue')
    _, fav_gil = varrer(gil, favoritas=True)
    ok(fav_gil == [], 'Quem não segue ninguém vê o filtro vazio (não vaza favoritos de outro)')
    lj = pega(emitir(beto, 'bazar_abrir_loja', {'loja_id': L_ANA}), 'bazar_loja')
    ok(lj['favorita'] is True and lj['seguidores'] == 1, 'A página da loja diz se eu sigo e quantos seguidores tem')
    emitir(gil, 'bazar_favoritar', {'loja_id': L_ANA, 'ativo': True})
    ok(pega(emitir(gil, 'bazar_abrir_loja', {'loja_id': L_ANA}), 'bazar_loja')['seguidores'] == 2, 'Seguidores contam pessoas diferentes')
    emitir(beto, 'bazar_favoritar', {'loja_id': L_ANA, 'ativo': False})
    ok(db.session.query(BazarFavorito).filter_by(person_id=ids['beto'], loja_id=L_ANA).count() == 0, 'Desfavoritar remove')
    rec = emitir(beto, 'bazar_favoritar', {'loja_id': 9999, 'ativo': True})
    ok(erro(rec) is not None, 'Loja que não existe não vira favorita')

    # ---------- 5. ORDENAÇÃO E "PERTO DE MIM" ----------
    emitir(eva, 'bazar_salvar_loja', {'nome': 'Loja da Eva', 'categoria': 'moda', 'porte': 'media'})
    emitir(eva, 'bazar_salvar_produto', {'nome': 'Colar barato', 'preco_cent': 500, 'tipo': 'fisico'})
    emitir(eva, 'bazar_salvar_produto', {'nome': 'Colar médio', 'preco_cent': 2500, 'tipo': 'fisico'})
    emitir(fabio, 'bazar_salvar_loja', {'nome': 'Barraca do Fabio', 'categoria': 'comida', 'porte': 'micro'})
    emitir(fabio, 'bazar_salvar_produto', {'nome': 'Brigadeiro', 'preco_cent': 300, 'tipo': 'fisico'})
    emitir(fabio, 'bazar_salvar_produto', {'nome': 'Bolo', 'preco_cent': 4000, 'tipo': 'fisico'})
    Le, Lf = (db.session.query(BazarLoja).filter_by(owner_id=ids[u]).one() for u in ('eva', 'fabio'))
    Le.vendas, Le.nota_soma, Le.nota_qtd = 9, 10, 2          # nota 5,0
    Lg = db.session.get(BazarLoja, L_ANA); Lg.vendas, Lg.nota_soma, Lg.nota_qtd = 2, 8, 2   # nota 4,0
    Lc = db.session.get(BazarLoja, L_CRIS); Lc.vendas = 1
    db.session.commit()
    ordem_lojas = lambda o: lojas_do(varrer(gil, ordem=o)[1])
    ok(ordem_lojas('vendidos') == ['Loja da Eva', 'Ateliê da Ana'], 'Ordem "mais vendidos": a loja com mais vendas primeiro')
    ok(ordem_lojas('nota') == ['Loja da Eva', 'Ateliê da Ana'], 'Ordem "melhor avaliadas": nota 5,0 antes de 4,0')
    ok(ordem_lojas('novas') == ['Loja da Eva', 'Ateliê da Ana'], 'Ordem "mais novas": a aberta por último vem primeiro')
    ok(ordem_lojas('preco_menor') == ['Loja da Eva', 'Ateliê da Ana'] and ordem_lojas('preco_maior') == ['Ateliê da Ana', 'Loja da Eva'],
       'Ordem por preço usa o item mais barato/mais caro da loja')
    micro_menor = micro_do(varrer(gil, ordem='preco_menor')[1])
    ok(micro_menor == sorted(micro_menor, key=lambda n: {'Brigadeiro': 300, 'Pack de sons': 1500, 'Bolo': 4000}.get(n, 0)), f'Itens das barracas pequenas também saem por preço: {micro_menor}')
    _, mix1 = varrer(gil, ordem='mix', seed='aaa'); _, mix2 = varrer(gil, ordem='mix', seed='aaa'); _, mix3 = varrer(gil, ordem='mix', seed='bbb')
    ok(mix1 == mix2, 'Misturado: mesma seed, mesma ordem')
    ok(varrer(gil, ordem='xablau')[1] == varrer(gil, ordem='mix')[1], 'Ordem desconhecida vira "misturado"')
    rec = emitir(gil, 'bazar_listar', {'ordem': 'perto', 'seed': 'x', 'pagina': 0})
    ok('localização do aparelho' in (erro(rec) or ''), '"Perto de mim" sem posição do aparelho é recusado com o motivo')
    rec = emitir(eva, 'bazar_salvar_loja', {'nome': 'Loja da Eva', 'categoria': 'moda', 'porte': 'media', 'no_mapa': True})
    ok('perto de mim' in (erro(rec) or ''), 'Pedir pra aparecer em "perto de mim" sem posição do aparelho é recusado (e a loja não muda)')
    eva.emit('atualizar_localizacao', {'lat': -15.83561, 'lng': -48.07231}); ev(eva)
    emitir(eva, 'bazar_salvar_loja', {'nome': 'Loja da Eva', 'categoria': 'moda', 'porte': 'media', 'no_mapa': True})
    Le = db.session.query(BazarLoja).filter_by(owner_id=ids['eva']).one()
    ok((Le.lat, Le.lng) == (-15.84, -48.07), 'A posição da loja é ARREDONDADA (0,01° ~ 1 km): nunca o ponto exato')
    gil.emit('atualizar_localizacao', {'lat': -15.80, 'lng': -48.05}); ev(gil)
    _, perto = varrer(gil, ordem='perto')
    ok(lojas_do(perto) == ['Loja da Eva'] and perto[0]['loja']['distancia_km'] >= 1, '"Perto de mim" só mostra quem pediu pra aparecer e está no raio, com a distância')
    ok(not any(i['t'] == 'quad' for i in perto), '...e quem não pediu (barracas, outras lojas) não aparece')
    gil.emit('atualizar_localizacao', {'lat': -23.55, 'lng': -46.63}); ev(gil)      # São Paulo (2 salto grande: vira "suspeita")
    rec = emitir(gil, 'bazar_listar', {'ordem': 'perto', 'seed': 'x', 'pagina': 0})
    ok(erro(rec) is not None, 'Posição "suspeita" (salto impossível) não vale pra "perto de mim"')
    emitir(eva, 'bazar_salvar_loja', {'nome': 'Loja da Eva', 'categoria': 'moda', 'porte': 'media', 'no_mapa': False})
    ok(db.session.query(BazarLoja).filter_by(owner_id=ids['eva']).one().lat is None, 'Desmarcar apaga a posição guardada')
    emitir(eva, 'bazar_salvar_loja', {'nome': 'Loja da Eva', 'categoria': 'moda', 'porte': 'media', 'no_mapa': True})
    ok(db.session.query(BazarLoja).filter_by(owner_id=ids['eva']).one().lat == -15.84, 'Marcar de novo com o aparelho ligado volta a guardar')

    # ---------- 6. ANÚNCIOS ----------
    rec = emitir(beto, 'bazar_anuncio_salvar', {'titulo': 'Meu anúncio'})
    ok(erro(rec) and db.session.query(BazarAnuncio).count() == 0, 'Quem não é admin não cria anúncio')
    ok(erro(emitir(beto, 'bazar_anuncios_listar')) is not None, 'Nem lista (os cliques são do admin)')
    v, _ = varrer(beto)
    ok(v['casa_padrao'] is True and not any(p['tipo'] == 'anuncio' for p in v['propagandas']), 'Sem anúncio cadastrado, a vitrine pede os 3 padrões do Pantheon (casa_padrao)')
    hoje = br_now().strftime('%Y-%m-%d')
    futuro = (br_now() + timedelta(days=5)).strftime('%Y-%m-%d')
    passado = (br_now() - timedelta(days=5)).strftime('%Y-%m-%d')
    for lixo, trecho in (({'titulo': ''}, 'título'), ({'destino': 'link', 'link_url': 'http://inseguro.com'}, 'link'), ({'destino': 'link', 'link_url': 'https://user@evil.com'}, 'link'),
                         ({'destino': 'link', 'link_url': "https://a.com/x'onclick=1"}, 'link'), ({'destino': 'loja', 'loja_id': 99999}, 'loja'),
                         ({'imagem_url': 'https://evil.com/a.png'}, 'arte'), ({'inicio': '2026-13-45'}, 'data'), ({'inicio': futuro, 'fim': passado}, 'fim')):
        rec = emitir(duda, 'bazar_anuncio_salvar', {'titulo': 'Promo', 'destino': 'nenhum', **lixo})
        ok(trecho in (erro(rec) or '').lower(), f'Anúncio inválido recusado ({trecho}): {list(lixo)[0]}')
    ok(db.session.query(BazarAnuncio).count() == 0, 'Nenhum anúncio inválido foi salvo')
    emitir(duda, 'bazar_anuncio_salvar', {'titulo': 'Promo no ar', 'texto': 'Descontos', 'destino': 'link', 'link_url': 'https://www.exemplo.com.br/promo?x=1', 'cta': 'Ver oferta',
                                          'imagem_url': 'https://res.cloudinary.com/x/arte.png', 'inicio': passado, 'fim': futuro})
    emitir(duda, 'bazar_anuncio_salvar', {'titulo': 'Promo futura', 'destino': 'loja', 'loja_id': L_ANA, 'inicio': futuro})
    emitir(duda, 'bazar_anuncio_salvar', {'titulo': 'Promo velha', 'destino': 'nenhum', 'inicio': (br_now() - timedelta(days=9)).strftime('%Y-%m-%d'), 'fim': passado})
    emitir(duda, 'bazar_anuncio_salvar', {'titulo': 'Promo pausada', 'destino': 'nenhum', 'ativo': False})
    emitir(duda, 'bazar_anuncio_salvar', {'titulo': 'Promo da loja', 'destino': 'loja', 'loja_id': L_ANA})
    v, _ = varrer(beto)
    noar = [p for p in v['propagandas'] if p['tipo'] == 'anuncio']
    ok(sorted(p['titulo'] for p in noar) == ['Promo da loja', 'Promo no ar'], f'No carrossel só os anúncios que estão no ar agora (sem futuro, vencido nem pausado): {[p["titulo"] for p in noar]}')
    ok(v['casa_padrao'] is False, 'Com anúncio cadastrado os padrões do Pantheon não aparecem')
    a_link = next(p for p in noar if p['titulo'] == 'Promo no ar')
    ok(a_link['link_url'] == 'https://www.exemplo.com.br/promo?x=1' and a_link['cta'] == 'Ver oferta' and a_link['imagem_url'].endswith('arte.png'), 'O anúncio leva arte, botão e o link (só https)')
    lista = pega(emitir(duda, 'bazar_anuncios_listar'), 'bazar_anuncios')['lista']
    ok({a['titulo']: a['estado'] for a in lista} == {'Promo no ar': 'no ar', 'Promo futura': 'agendado', 'Promo velha': 'encerrado', 'Promo pausada': 'pausado', 'Promo da loja': 'no ar'}, 'O admin vê o estado de cada um (no ar, agendado, encerrado, pausado)')
    emitir(beto, 'bazar_anuncio_clique', {'id': a_link['id']})
    emitir(gil, 'bazar_anuncio_clique', {'id': a_link['id']})
    emitir(beto, 'bazar_anuncio_clique', {'id': a_link['id']})            # o freio por pessoa (5 s) segura o repetido
    ok(db.session.get(BazarAnuncio, a_link['id']).cliques == 3, 'Cliques contam (+1 atômico por clique)')
    beto.emit('bazar_anuncio_clique', {'id': a_link['id']}); beto.emit('bazar_anuncio_clique', {'id': a_link['id']}); ev(beto)
    ok(db.session.get(BazarAnuncio, a_link['id']).cliques == 3, 'O freio por pessoa (5 s) segura o clique repetido (script ou clique duplo)')
    bazar_events._ultimo.clear()
    futuro_id = next(a['id'] for a in lista if a['titulo'] == 'Promo futura'); velho_id = next(a['id'] for a in lista if a['titulo'] == 'Promo velha'); pausado_id = next(a['id'] for a in lista if a['titulo'] == 'Promo pausada')
    for aid in (futuro_id, velho_id, pausado_id):
        emitir(fabio, 'bazar_anuncio_clique', {'id': aid})
    ok(all((db.session.get(BazarAnuncio, a).cliques or 0) == 0 for a in (futuro_id, velho_id, pausado_id)), 'Clique em anúncio futuro, vencido ou pausado não conta')
    emitir(duda, 'bazar_anuncio_salvar', {'id': velho_id, 'titulo': 'Promo velha reativada', 'destino': 'nenhum', 'fim': futuro})
    ok(db.session.get(BazarAnuncio, velho_id).titulo == 'Promo velha reativada', 'Editar mantém o mesmo anúncio (e os cliques)')
    rec = emitir(beto, 'bazar_anuncio_apagar', {'id': velho_id})
    ok(erro(rec) and db.session.get(BazarAnuncio, velho_id) is not None, 'Quem não é admin não apaga anúncio')
    emitir(duda, 'bazar_anuncio_apagar', {'id': velho_id})
    ok(db.session.get(BazarAnuncio, velho_id) is None, 'Admin apaga')
    rec = emitir(duda, 'bazar_anuncios_padrao')
    ok('Já existem' in (erro(rec) or ''), 'Os 3 anúncios padrão só podem ser importados quando não há nenhum')
    for a in db.session.query(BazarAnuncio).all():
        db.session.delete(a)
    db.session.commit()
    emitir(duda, 'bazar_anuncios_padrao')
    ok(db.session.query(BazarAnuncio).count() == 3 and {a.destino for a in db.session.query(BazarAnuncio)} == {'painel', 'aviso', 'armazem'}, 'Importar os padrões cria os 3 (editáveis)')
    L_ANA_OCULTA = db.session.get(BazarLoja, L_ANA)
    emitir(duda, 'bazar_anuncio_salvar', {'titulo': 'Vai pra Ana', 'destino': 'loja', 'loja_id': L_ANA})
    L_ANA_OCULTA.oculta = True; db.session.commit()
    v, _ = varrer(beto)
    ok('Vai pra Ana' not in [p['titulo'] for p in v['propagandas']], 'Anúncio que leva a uma loja oculta some do carrossel')
    L_ANA_OCULTA.oculta = False; db.session.commit()

    # ---------- 7. DISPUTA ----------
    emitir(beto, 'bazar_pedir', {'produto_id': P_SF})
    pd1 = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    rec = emitir(beto, 'bazar_disputar', {'pedido_id': pd1.id, 'motivo': 'nao_recebi', 'detalhe': 'paguei e nada chegou até agora'})
    ok('não pode entrar em disputa' in (erro(rec) or ''), 'Pedido ainda "aguardando" não entra em disputa (nada foi pago)')
    emitir(ana, 'bazar_agir', {'pedido_id': pd1.id, 'acao': 'aceitar'})
    emitir(beto, 'bazar_agir', {'pedido_id': pd1.id, 'acao': 'paguei'})
    emitir(ana, 'bazar_agir', {'pedido_id': pd1.id, 'acao': 'confirmar'})
    ok(erro(emitir(ana, 'bazar_disputar', {'pedido_id': pd1.id, 'motivo': 'nao_recebi', 'detalhe': 'tentando um motivo do comprador'})) is not None, 'Vendedor não usa motivo de comprador ("paguei e não recebi")')
    ok(erro(emitir(beto, 'bazar_disputar', {'pedido_id': pd1.id, 'motivo': 'nao_recebi', 'detalhe': 'curto'})) is not None, 'Relato curto demais é recusado')
    ok(erro(emitir(cris, 'bazar_disputar', {'pedido_id': pd1.id, 'motivo': 'sumiu', 'detalhe': 'sou de fora, mas quero opinar'})) is not None, 'Terceiro não abre disputa no pedido dos outros')
    ev(ana); ev(beto)
    emitir(beto, 'bazar_mensagem', {'pedido_id': pd1.id, 'texto': 'Cadê meu produto? Já faz 10 dias.'})
    emitir(ana, 'bazar_mensagem', {'pedido_id': pd1.id, 'texto': 'Postei ontem, deve chegar.'})
    ev(ana); ev(beto); ev(duda)
    emitir(beto, 'bazar_disputar', {'pedido_id': pd1.id, 'motivo': 'nao_recebi', 'detalhe': 'paguei, o vendedor confirmou e nada chegou'})
    ok(db.session.query(BazarDisputa).filter_by(pedido_id=pd1.id, status='aberta').count() == 1, 'Comprador abriu a disputa')
    rec_ana = ev(ana)
    ok(pega(rec_ana, 'bazar_pedido')['em_disputa'] is True, 'Regra 6: a outra ponta recebe o pedido já "em disputa"')
    ok(any(n.tipo == 'bazar' and n.ref == 'disputa' for n in db.session.query(Notificacao).filter_by(person_id=ids['duda'])), 'Os admins recebem aviso na caixa de entrada')
    ok(erro(emitir(beto, 'bazar_disputar', {'pedido_id': pd1.id, 'motivo': 'sumiu', 'detalhe': 'tentando abrir uma segunda disputa'})) is not None, 'Não abre duas disputas ao mesmo tempo no mesmo pedido')
    rec = emitir(ana, 'bazar_agir', {'pedido_id': pd1.id, 'acao': 'cancelar'})
    ok('em disputa' in (erro(rec) or ''), 'Com a disputa aberta as ações do pedido ficam travadas')
    ok(erro(emitir(beto, 'bazar_agir', {'pedido_id': pd1.id, 'acao': 'recebi'})) is not None and db.session.get(BazarPedido, pd1.id).status == 'confirmado', '...inclusive "recebi" (ninguém conclui no meio da análise)')
    emitir(ana, 'bazar_mensagem', {'pedido_id': pd1.id, 'texto': 'Mas a conversa continua liberada.'})
    ok(db.session.query(BazarMensagem).filter_by(pedido_id=pd1.id).count() == 3, 'A conversa do pedido segue liberada durante a disputa')
    ok(erro(emitir(beto, 'bazar_disputas_listar')) is not None and not pega(ev(beto), 'bazar_disputas'), 'Quem não é admin não lista disputas')
    ok(erro(emitir(ana, 'bazar_disputa_resolver', {'disputa_id': 1, 'acao': 'cancelar', 'nota': 'eu sou o vendedor'})) is not None, 'Nem decide (nem o vendedor da própria disputa)')
    dados = pega(emitir(duda, 'bazar_disputas_listar'), 'bazar_disputas')
    d1 = dados['abertas'][0]
    ok(len(dados['abertas']) == 1 and d1['pedido']['id'] == pd1.id and d1['aberta_por'] == 'comprador', 'Admin vê a disputa aberta, de quem veio')
    ok([m['texto'] for m in d1['mensagens']] == ['Cadê meu produto? Já faz 10 dias.', 'Postei ontem, deve chegar.', 'Mas a conversa continua liberada.'] and d1['mensagens'][0]['autor'] == 'comprador',
       'Admin lê a conversa daquele pedido, na ordem, sabendo quem falou')
    ok(d1['comprador']['nome'] == 'Beto' and d1['vendedor']['nome'] == 'Ana', 'E sabe quem é comprador e quem é vendedor')
    rec = emitir(duda, 'bazar_disputa_resolver', {'disputa_id': d1['disputa']['id'], 'acao': 'cancelar'})
    ok('nota' in (erro(rec) or '').lower(), 'A decisão exige uma nota (as duas pontas precisam saber o porquê)')
    rec = emitir(duda, 'bazar_disputa_resolver', {'disputa_id': d1['disputa']['id'], 'acao': 'xablau', 'nota': 'x'})
    ok(erro(rec) is not None, 'Ação inventada é recusada')
    est_antes = db.session.get(BazarProduto, P_SF).estoque
    ev(ana); ev(beto)
    emitir(duda, 'bazar_disputa_resolver', {'disputa_id': d1['disputa']['id'], 'acao': 'cancelar', 'nota': 'Sem rastreio e o vendedor não comprovou o envio.'})
    pf = db.session.get(BazarPedido, pd1.id)
    ok(pf.status == 'cancelado' and db.session.get(BazarDisputa, d1['disputa']['id']).status == 'resolvida' and db.session.get(BazarDisputa, d1['disputa']['id']).resolucao == 'cancelar', 'Decisão "cancelar": pedido cancelado e disputa resolvida')
    rb = pega(ev(beto), 'bazar_pedido')
    ok(rb['disputa']['status'] == 'resolvida' and 'rastreio' in rb['disputa']['nota_admin'] and rb['em_disputa'] is False, 'Regra 6: as duas pontas leem a nota da decisão')
    ok(erro(emitir(duda, 'bazar_disputa_resolver', {'disputa_id': d1['disputa']['id'], 'acao': 'arquivar', 'nota': 'de novo'})) is not None, 'Decidir duas vezes a mesma disputa é recusado')
    # concluir: pedido pago com vendedor que entregou
    emitir(beto, 'bazar_pedir', {'produto_id': P_SF})
    pd2 = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    emitir(ana, 'bazar_agir', {'pedido_id': pd2.id, 'acao': 'aceitar'}); emitir(beto, 'bazar_agir', {'pedido_id': pd2.id, 'acao': 'paguei'})
    emitir(ana, 'bazar_disputar', {'pedido_id': pd2.id, 'motivo': 'nao_paguei', 'detalhe': 'o Pix não caiu na minha conta de jeito nenhum'})
    d2 = db.session.query(BazarDisputa).filter_by(pedido_id=pd2.id).one()
    rec = emitir(duda, 'bazar_disputa_resolver', {'disputa_id': d2.id, 'acao': 'concluir', 'nota': 'Pix conferido: o comprador pagou e recebeu.'})
    ok(erro(rec) is None, 'Concluir pedido com Pix informado é permitido')
    ok(db.session.get(BazarPedido, pd2.id).status == 'concluido', 'Decisão "concluir": pedido pago vira concluído')
    ok(db.session.get(BazarLoja, L_ANA).vendas == 3, 'Concluir pela disputa conta a venda da loja (1 antiga + ... = 3 com este)')
    # arquivar: destrava sem mudar o pedido
    emitir(beto, 'bazar_pedir', {'produto_id': P_SF})
    pd3 = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    emitir(ana, 'bazar_agir', {'pedido_id': pd3.id, 'acao': 'aceitar'})
    emitir(beto, 'bazar_disputar', {'pedido_id': pd3.id, 'motivo': 'sumiu', 'detalhe': 'o vendedor parou de responder as mensagens'})
    d3 = db.session.query(BazarDisputa).filter_by(pedido_id=pd3.id).one()
    ok(erro(emitir(duda, 'bazar_disputa_resolver', {'disputa_id': d3.id, 'acao': 'concluir', 'nota': 'tentando concluir pedido só aceito'})) is not None, 'Não dá pra "concluir" um pedido que nem foi pago')
    emitir(duda, 'bazar_disputa_resolver', {'disputa_id': d3.id, 'acao': 'arquivar', 'nota': 'Os dois voltaram a conversar.'})
    ok(db.session.get(BazarPedido, pd3.id).status == 'aceito', 'Decisão "arquivar": o pedido fica como estava')
    ok(pega(emitir(beto, 'bazar_agir', {'pedido_id': pd3.id, 'acao': 'cancelar'}) or [], 'bazar_erro') is None and db.session.get(BazarPedido, pd3.id).status == 'cancelado', '...e destrava as ações (o comprador cancela)')
    # depois de concluído: disputa só por alguns dias
    pc = db.session.get(BazarPedido, pd2.id)
    ok(bazar.pedido_json(pc, ids['beto'])['pode_disputar'] is True, 'Pedido concluído há pouco ainda pode ir pra disputa')
    pc.atualizado_em = br_now() - timedelta(days=bazar.DISPUTA_DIAS_APOS_CONCLUIR + 1); db.session.commit()
    ok(bazar.pedido_json(pc, ids['beto'])['pode_disputar'] is False and erro(emitir(beto, 'bazar_disputar', {'pedido_id': pc.id, 'motivo': 'outro', 'detalhe': 'já faz muito tempo mesmo'})) is not None, '...mas depois de 14 dias não')

    # admin que é PARTE do pedido não decide o próprio caso
    emitir(duda, 'bazar_pedir', {'produto_id': P_SF})
    pdd = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    emitir(ana, 'bazar_agir', {'pedido_id': pdd.id, 'acao': 'aceitar'}); emitir(duda, 'bazar_agir', {'pedido_id': pdd.id, 'acao': 'paguei'})
    emitir(duda, 'bazar_disputar', {'pedido_id': pdd.id, 'motivo': 'sumiu', 'detalhe': 'a vendedora parou de responder as mensagens'})
    dd = db.session.query(BazarDisputa).filter_by(pedido_id=pdd.id).one()
    lista_adm = pega(emitir(duda, 'bazar_disputas_listar'), 'bazar_disputas')['abertas']
    ok(any(x['disputa']['id'] == dd.id and x['sou_parte'] is True for x in lista_adm), 'A lista do admin marca quando ele é parte do pedido')
    rec = emitir(duda, 'bazar_disputa_resolver', {'disputa_id': dd.id, 'acao': 'cancelar', 'nota': 'decidindo o meu próprio caso'})
    ok('parte neste pedido' in (erro(rec) or '') and db.session.get(BazarDisputa, dd.id).status == 'aberta', 'Admin não decide a disputa em que ele é parte (outro admin precisa)')
    ok(not any(n.ref == 'disputa' and n.titulo.startswith('Nova disputa') for n in db.session.query(Notificacao).filter_by(person_id=ids['duda']).order_by(Notificacao.id.desc()).limit(1)), 'E não recebe aviso de "nova disputa" da própria disputa')
    db.session.get(BazarDisputa, dd.id).status = 'resolvida'; db.session.commit()
    emitir(duda, 'bazar_agir', {'pedido_id': pdd.id, 'acao': 'cancelar'})

    # ---------- 8. BANIMENTO ----------
    emitir(gil, 'bazar_salvar_loja', {'nome': 'Loja do Gil', 'categoria': 'casa', 'porte': 'media', 'pix_chave': 'gil@exemplo.com', 'pix_nome': 'Gil', 'pix_cidade': 'Brasilia'})
    emitir(gil, 'bazar_salvar_produto', {'nome': 'Vaso', 'preco_cent': 2000, 'tipo': 'fisico', 'estoque': 4})
    L_GIL = db.session.query(BazarLoja).filter_by(owner_id=ids['gil']).one().id
    P_VASO = db.session.query(BazarProduto).filter_by(nome='Vaso').one().id
    emitir(fabio, 'bazar_pedir', {'produto_id': P_VASO, 'quantidade': 2})
    pv = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    emitir(gil, 'bazar_agir', {'pedido_id': pv.id, 'acao': 'aceitar'})
    ok(db.session.get(BazarProduto, P_VASO).estoque == 2, 'Pedido aceito reservou 2 do estoque')
    emitir(eva, 'bazar_pedir', {'produto_id': P_VASO}); pv2 = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    ok(erro(emitir(beto, 'bazar_banir', {'pessoa_id': ids['gil'], 'motivo': 'golpe'})) is not None and not db.session.query(BazarBanimento).count(), 'Quem não é admin não bane')
    ok(erro(emitir(duda, 'bazar_banir', {'pessoa_id': ids['duda'], 'motivo': 'x'})) is not None, 'Admin não bane a si mesmo')
    bazar.definir_admin(ids['cris'])
    ok(erro(emitir(duda, 'bazar_banir', {'pessoa_id': ids['cris'], 'motivo': 'x'})) is not None, 'Admin não bane outro admin')
    bazar.definir_admin(ids['cris'], False)
    ok('motivo' in (erro(emitir(duda, 'bazar_banir', {'pessoa_id': ids['gil'], 'motivo': ''})) or '').lower(), 'Banir exige motivo')
    ok(erro(emitir(duda, 'bazar_banir', {'usuario': '@ninguem_assim', 'motivo': 'x'})) is not None, 'Banir por @ que não existe é recusado')
    ev(fabio); ev(eva)
    rec = emitir(duda, 'bazar_banir', {'usuario': '@Gil', 'motivo': 'Golpe: vendeu e sumiu', 'dias': 30})
    ok(db.session.query(BazarBanimento).filter_by(person_id=ids['gil']).count() == 1 and pega(rec, 'bazar_banidos')['lista'][0]['usuario'] == 'gil', 'Admin bane pelo @ (que é único), com motivo e prazo')
    ok(db.session.get(BazarPedido, pv.id).status == 'cancelado' and db.session.get(BazarPedido, pv2.id).status == 'cancelado', 'Os pedidos em aberto dele (vendedor) foram cancelados')
    ok(db.session.get(BazarProduto, P_VASO).estoque == 4, '...e o estoque reservado voltou')
    rf = pega(ev(fabio), 'bazar_pedido')
    ok(rf is not None and rf['status'] == 'cancelado', 'Regra 6: o comprador recebe o pedido cancelado')
    ok(any('suspensa' in (n.texto or '') for n in db.session.query(Notificacao).filter_by(person_id=ids['fabio'])), 'O comprador é avisado do motivo na caixa de entrada')
    v, itens = varrer(beto)
    ok('Loja do Gil' not in lojas_do(itens) and 'Loja do Gil' not in [d['nome'] for d in v['destaques']], 'A loja do banido some do feed')
    ok(erro(emitir(beto, 'bazar_abrir_loja', {'loja_id': L_GIL})) is not None, '...e ninguém abre a página dela')
    ok(pega(emitir(gil, 'bazar_abrir_loja', {'loja_id': L_GIL}), 'bazar_loja')['eh_dono'], 'O banido ainda vê a própria loja (histórico)')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': P_VASO})
    ok('não está mais disponível' in (erro(rec) or ''), 'Ninguém pede produto de quem está banido')
    ok('suspensa' in (erro(emitir(gil, 'bazar_salvar_produto', {'nome': 'Outro vaso', 'preco_cent': 1000})) or ''), 'O banido não cadastra produto')
    ok('suspensa' in (erro(emitir(gil, 'bazar_salvar_loja', {'nome': 'Loja do Gil'})) or ''), 'Nem edita a loja')
    ok('suspensa' in (erro(emitir(gil, 'bazar_pedir', {'produto_id': P_SF})) or ''), 'Nem compra')
    ok('Motivo: Golpe' in (erro(emitir(gil, 'bazar_pedir', {'produto_id': P_SF})) or ''), 'A mensagem diz o motivo')
    v_gil = pega(emitir(gil, 'bazar_listar', {'seed': 'x', 'pagina': 0}), 'bazar_vitrine')
    ok(v_gil['banido'] and v_gil['banido']['motivo'].startswith('Golpe') and v_gil['banido']['ate'], 'A vitrine do banido traz o aviso (motivo e até quando)')
    ok(v['banido'] is None, 'Quem não está banido não recebe aviso nenhum')
    ok(any(l['nome'] == 'Gil' for l in pega(emitir(duda, 'bazar_banidos_listar'), 'bazar_banidos')['lista']) and erro(emitir(beto, 'bazar_banidos_listar')) is not None, 'Só admin lista os banidos')
    b = db.session.query(BazarBanimento).filter_by(person_id=ids['gil']).one()
    b.ate = br_now() - timedelta(minutes=1); db.session.commit()
    ok(bazar._banimento_ativo(ids['gil']) is None and 'Loja do Gil' in lojas_do(varrer(beto)[1]), 'Banimento com prazo vencido acaba sozinho (a loja volta)')
    b.ate = None; db.session.commit()
    ok(bazar._banimento_ativo(ids['gil']) is not None, 'Banimento sem prazo é permanente')
    ok(erro(emitir(beto, 'bazar_desbanir', {'pessoa_id': ids['gil']})) is not None and db.session.query(BazarBanimento).count() == 1, 'Quem não é admin não desbane')
    emitir(duda, 'bazar_desbanir', {'pessoa_id': ids['gil']})
    ok(db.session.query(BazarBanimento).count() == 0 and 'Loja do Gil' in lojas_do(varrer(beto)[1]), 'Desbanir devolve a loja ao feed')
    ok(erro(emitir(duda, 'bazar_desbanir', {'pessoa_id': ids['gil']})) is not None, 'Desbanir quem não está banido é recusado')
    # banir comprador: os pedidos abertos dele caem
    emitir(fabio, 'bazar_pedir', {'produto_id': P_VASO}); pv3 = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    emitir(duda, 'bazar_banir', {'pessoa_id': ids['fabio'], 'motivo': 'Pedidos falsos', 'dias': 7})
    ok(db.session.get(BazarPedido, pv3.id).status == 'cancelado', 'Banir um COMPRADOR cancela os pedidos abertos dele também')
    emitir(duda, 'bazar_desbanir', {'pessoa_id': ids['fabio']})
    # denúncia dispensada junto do banimento
    for cl in (eva, beto, ana):
        emitir(cl, 'denunciar', {'tipo': 'usuario', 'id': ids['gil'], 'motivo': 'spam'})
    fila = pega(emitir(duda, 'bazar_moderacao_listar'), 'bazar_moderacao')['fila']
    g = next(f for f in fila if f['tipo'] == 'usuario' and f['alvo_id'] == ids['gil'])
    ok(g['alvo']['pessoa_id'] == ids['gil'], 'A fila de moderação diz quem seria banido por cada denúncia')
    emitir(duda, 'bazar_banir', {'pessoa_id': ids['gil'], 'motivo': 'Denúncias procedentes', 'denuncia_tipo': 'usuario', 'denuncia_alvo': ids['gil']})
    fila = pega(emitir(duda, 'bazar_moderacao_listar'), 'bazar_moderacao')['fila']
    ok(not any(f['tipo'] == 'usuario' and f['alvo_id'] == ids['gil'] for f in fila), 'Banir a partir da denúncia dispensa as denúncias dessa pessoa')
    emitir(duda, 'bazar_desbanir', {'pessoa_id': ids['gil']})

    # sem login nada responde
    anon = socketio.test_client(app); anon.get_received()
    for nome in ('bazar_favoritar', 'bazar_disputar', 'bazar_banir', 'bazar_anuncio_salvar', 'bazar_verificar', 'bazar_disputas_listar', 'bazar_anuncio_clique'):
        anon.emit(nome, {'loja_id': 1, 'id': 1})
    ok(not ev(anon), 'Sem login: nenhum evento novo do Bazar responde')

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
