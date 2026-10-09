"""Bazar (modelo A): Pix copia e cola, validações, loja/produto, vitrine por porte, pedido (máquina de estados), privacidade da
chave Pix, estoque, avaliação, conversa do pedido, denúncia + moderação, corridas, regra 6."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import bazar, bazar_events
from app.bazar import ErroBazar
from datetime import timedelta
from app.models import (Role, Person, Friendship, GeoNote, Notificacao, BazarLoja, BazarProduto, BazarPedido, BazarMensagem,
                        BazarAvaliacao, Denuncia, br_now)

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


def levanta(fn, trecho=None):
    try:
        fn()
    except ErroBazar as e:
        return trecho is None or trecho.lower() in str(e).lower()
    return False


def tlv(payload):
    """Desmonta um BR Code em {id: valor} (confere os comprimentos)."""
    campos, i = {}, 0
    while i < len(payload):
        id_, n = payload[i:i + 2], int(payload[i + 2:i + 4])
        campos[id_] = payload[i + 4:i + 4 + n]
        i += 4 + n
    return campos


# ---------- 1. PIX (sem banco) ----------
ok(bazar.crc16_pix('123456789') == 0x29B1, 'CRC16/CCITT-FALSE confere com o vetor de teste oficial (123456789 -> 29B1)')
pl = bazar.pix_copia_cola('ana@exemplo.com', 'Ana Ávila', 'São Paulo', 1250, 'PNT7')
campos = tlv(pl[:-8] + pl[-8:])
ok(campos['00'] == '01' and campos['53'] == '986' and campos['54'] == '12.50' and campos['58'] == 'BR', 'Payload Pix: formato, moeda BRL, valor 12.50 e país')
ok(tlv(campos['26'])['00'] == 'br.gov.bcb.pix' and tlv(campos['26'])['01'] == 'ana@exemplo.com', 'Payload Pix: a chave do vendedor vai no campo 26')
ok(campos['59'] == 'ANA AVILA' and campos['60'] == 'SAO PAULO', 'Nome e cidade viram ASCII maiúsculo sem acento')
ok(tlv(campos['62'])['05'] == 'PNT7', 'O txid carrega o número do pedido')
ok(pl[-8:-4] == '6304' and int(pl[-4:], 16) == bazar.crc16_pix(pl[:-4]), 'O CRC no fim bate com o resto do payload')
n = bazar.normalizar_chave_pix
ok(n('529.982.247-25') == '52998224725', 'CPF válido com pontuação vira só números')
ok(n('11999998888') == '+5511999998888', '11 números que NÃO são CPF válido e parecem celular viram +55')
ok(n('+55 (61) 99999-8888') == '+5561999998888', 'Telefone com +55 e pontuação é normalizado')
ok(n('ANA@Exemplo.COM') == 'ana@exemplo.com', 'E-mail vai em minúsculo')
ok(n('123E4567-E89B-12D3-A456-426614174000') == '123e4567-e89b-12d3-a456-426614174000', 'Chave aleatória (UUID) em minúsculo')
ok(n('') is None and n('   ') is None, 'Chave vazia = sem Pix (não é erro)')
for ruim in ('abc', 'a@b', '123', '+1 555 0100', '12345678901234567890', 'rm -rf /'):
    ok(levanta(lambda r=ruim: n(r)), f'Chave inválida é recusada: {ruim!r}')
ok(bazar.chave_mascarada('ana@exemplo.com') == 'an***@exemplo.com' and bazar.chave_mascarada('52998224725') == '529***25', 'A chave aparece mascarada pro comprador')
ok(set(bazar.TOLDOS) >= {'vermelho', 'sem'} and all(re.match(r'^#[0-9a-f]{6}$', v) for v in bazar.CORES.values()), 'Cores do catálogo são hex válido')

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('Ana', 'Beto', 'Cris', 'Duda', 'Eva', 'Fabio', 'Gil', 'Hugo'):
        # contas com 30 dias (conta recém-criada não abre loja: regra da Rodada 18, testada mais abaixo com a 'Novata')
        p = Person(name=nome, email=f'{nome.lower()}@x', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=30))
        db.session.add(p); db.session.commit(); ids[nome.lower()] = p.id
    db.session.add(Friendship(requester_id=ids['hugo'], addressee_id=ids['ana'], status='blocked')); db.session.commit()

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

    def varrer(cl, **dados):
        """Percorre TODAS as páginas do feed. Devolve (payload da página 0, lista de itens)."""
        dados.setdefault('seed', 'teste')
        v = next(x for x in emitir(cl, 'bazar_listar', {**dados, 'pagina': 0}) if x['name'] == 'bazar_vitrine')['args'][0]
        itens, tem, pg = list(v['feed']['itens']), v['feed']['tem_mais'], 0
        while tem:
            pg += 1
            f = next(x for x in emitir(cl, 'bazar_listar', {**dados, 'pagina': pg}) if x['name'] == 'bazar_feed')['args'][0]
            itens += f['itens']; tem = f['tem_mais']
        return v, itens

    lojas_do = lambda itens: [i['loja']['nome'] for i in itens if i['t'] == 'loja']
    micro_do = lambda itens: [(p['nome'], p['loja_nome']) for i in itens if i['t'] == 'quad' for p in i['produtos']]
    conteudo = lambda itens: sorted([('l', i['loja']['id']) for i in itens if i['t'] == 'loja'] + [('p', p['id']) for i in itens if i['t'] == 'quad' for p in i['produtos']])
    chaves = lambda itens: [('l%d' % i['loja']['id']) if i['t'] == 'loja' else ('q%d' % i['produtos'][0]['id']) for i in itens]

    ana, beto, cris, duda = cliente('ana'), cliente('beto'), cliente('cris'), cliente('duda')
    eva, fabio, gil, hugo = cliente('eva'), cliente('fabio'), cliente('gil'), cliente('hugo')
    pessoa = lambda u: db.session.get(Person, ids[u])

    # ---------- 2. LOJA ----------
    rec = emitir(ana, 'bazar_salvar_loja', {'nome': '', 'pix_chave': ''})
    ok('nome da loja' in (erro(rec) or ''), 'Loja sem nome é recusada')
    rec = emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'descricao': 'veja em www.golpe.com'})
    ok('links' in (erro(rec) or '').lower(), 'Link na descrição é recusado (texto público não tem link)')
    rec = emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'logo_url': 'https://evil.com/pixel.png'})
    ok('logo' in (erro(rec) or '').lower(), 'Logo de host qualquer é recusado (só imagem do próprio app)')
    for url in ("https://res.cloudinary.com/x/a.png');background:url(//evil/x", 'https://res.cloudinary.com/x/a b.png', '/static/x.png")', 'https://res.cloudinary.com/x/<b>.png'):
        rec = emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'banner_url': url})
        ok('banner' in (erro(rec) or '').lower(), f'URL de imagem com aspa/parêntese/espaço/< é recusada (injeção de CSS): {url[:40]!r}')
    rec = emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'pix_chave': 'lixo'})
    ok('pix' in (erro(rec) or '').lower(), 'Chave Pix inválida é recusada na loja')
    ok(db.session.query(BazarLoja).count() == 0, 'Nada foi salvo nas tentativas inválidas')

    pessoa('ana').localizacao_ativa = False; db.session.commit()
    rec = emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana'})
    ok('localização' in (erro(rec) or '').lower() and db.session.query(BazarLoja).count() == 0, 'Com a localização desligada não dá pra abrir loja (trava do dono)')
    pessoa('ana').localizacao_ativa = True; db.session.commit()

    rec = emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'descricao': 'Retratos à mão', 'categoria': 'arte', 'porte': 'grande', 'cor': 'xxx',
                                            'toldo': '<script>', 'pix_chave': 'ana@exemplo.com', 'pix_nome': 'Ana Ávila', 'pix_cidade': 'Brasília'})
    m = next(x for x in rec if x['name'] == 'bazar_minha')['args'][0]['loja']
    ok(m['porte'] == 'micro', 'Pessoa não consegue se declarar loja "grande" (só admin)')
    ok(m['cor'] == 'ambar' and m['toldo'] == 'vermelho', 'Cor/toldo desconhecidos viram o padrão (nunca texto livre num class/style)')
    ok(m['pix_chave'] == 'ana@exemplo.com' and m['eh_dono' if 'eh_dono' in m else 'pix_configurado'], 'O dono vê a própria chave Pix')
    ok(any(x['name'] == 'bazar_mudou' for x in ev(beto)), 'Regra 6: todo mundo recebe o aviso de que o Bazar mudou')
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'porte': 'media', 'categoria': 'arte', 'cor': 'vinho', 'toldo': 'verde', 'pix_chave': 'ana@exemplo.com', 'pix_nome': 'Ana Ávila', 'pix_cidade': 'Brasília'})
    ok(db.session.query(BazarLoja).count() == 1 and db.session.query(BazarLoja).one().porte == 'media', 'Salvar de novo atualiza a MESMA loja (uma por pessoa) e o porte "media" é livre')

    # ---------- 3. PRODUTO ----------
    base = {'nome': 'Retrato em aquarela', 'descricao': 'A4, entrega em 7 dias', 'preco_cent': 4500, 'tipo': 'servico', 'estoque': 3}
    for lixo, trecho in (({'preco_cent': 50}, 'preço'), ({'preco_cent': 9_999_999_99}, 'preço'), ({'preco_cent': 'abc'}, 'preço'), ({'nome': 'Loja www.x.com'}, 'links'),
                         ({'imagens': ['https://evil.com/a.png']}, 'imagem'), ({'video_url': 'https://evil.com/v.mp4'}, 'vídeo'), ({'estoque': -1}, 'estoque'),
                         ({'estoque': 10 ** 6}, 'estoque'), ({'descricao': 'x' * 601}, '600')):
        rec = emitir(ana, 'bazar_salvar_produto', {**base, **lixo})
        ok(trecho in (erro(rec) or '').lower(), f'Produto inválido recusado ({trecho}): {list(lixo)[0]}')
    ok(db.session.query(BazarProduto).count() == 0, 'Nenhum produto inválido foi salvo')
    rec = emitir(beto, 'bazar_salvar_produto', base)
    ok('loja' in (erro(rec) or '').lower() and db.session.query(BazarProduto).count() == 0, 'Quem não tem loja não cadastra produto')

    rec = emitir(ana, 'bazar_salvar_produto', {**base, 'imagens': ['https://res.cloudinary.com/x/a.png'], 'video_url': 'https://res.cloudinary.com/x/v.mp4', 'entrega': 'Link: https://drive.exemplo/abc'})
    loja = next(x for x in rec if x['name'] == 'bazar_minha')['args'][0]['loja']
    p1 = loja['produtos'][0]
    ok(p1['preco_cent'] == 4500 and p1['estoque'] == 3 and p1['entrega'].startswith('Link'), 'Produto válido salvo (preço em centavos, estoque, entrega privada com link permitida)')
    rec = emitir(ana, 'bazar_salvar_produto', {'nome': 'Combo Pack', 'preco_cent': 6000, 'tipo': 'digital', 'combo_itens': ['Ícone', 'Banner', 'Sticker'], 'preco_avulso_cent': 8000, 'estoque': None})
    p2 = next(x for x in rec if x['name'] == 'bazar_minha')['args'][0]['loja']['produtos'][0]
    ok(p2['combo_itens'] == ['Ícone', 'Banner', 'Sticker'] and p2['preco_avulso_cent'] == 8000 and p2['estoque'] is None, 'Combo guarda os itens e o preço avulso; estoque vazio = sem limite')
    rec = emitir(ana, 'bazar_salvar_produto', {**base, 'id': p1['id'], 'nome': 'Retrato A4', 'preco_cent': 5000, 'estoque': 3})
    ok(db.session.get(BazarProduto, p1['id']).nome == 'Retrato A4' and db.session.query(BazarProduto).count() == 2, 'Editar produto altera o mesmo registro')

    # outra pessoa com loja não mexe no produto da Ana (regra 4)
    emitir(cris, 'bazar_salvar_loja', {'nome': 'Cantinho do Cris', 'pix_chave': '52998224725', 'porte': 'micro', 'categoria': 'digital'})
    rec = emitir(cris, 'bazar_salvar_produto', {**base, 'id': p1['id'], 'nome': 'ROUBADO'})
    ok('não encontrado' in (erro(rec) or '').lower() and db.session.get(BazarProduto, p1['id']).nome == 'Retrato A4', 'Não dá pra editar o produto de outra loja chutando o id')
    rec = emitir(cris, 'bazar_apagar_produto', {'id': p1['id']})
    ok(db.session.get(BazarProduto, p1['id']) is not None, 'Nem apagar')
    emitir(cris, 'bazar_salvar_produto', {'nome': 'Pack de sons', 'preco_cent': 1500, 'tipo': 'digital', 'estoque': 1, 'entrega': 'Baixe: https://x.com/pack'})
    emitir(cris, 'bazar_salvar_produto', {'nome': 'Pack de ícones', 'preco_cent': 1000, 'tipo': 'digital'})

    # limite de produtos ativos
    for i in range(bazar.MAX_PRODUTOS_ATIVOS):
        emitir(eva, 'bazar_salvar_loja', {'nome': 'Loja da Eva', 'categoria': 'moda'}) if i == 0 else None
        emitir(eva, 'bazar_salvar_produto', {'nome': f'Item {i}', 'preco_cent': 200})
    rec = emitir(eva, 'bazar_salvar_produto', {'nome': 'Um a mais', 'preco_cent': 200})
    ok('40' in (erro(rec) or ''), 'Passou de 40 produtos ativos: recusa')
    ok(db.session.query(BazarProduto).filter_by(loja_id=db.session.query(BazarLoja).filter_by(owner_id=ids['eva']).one().id).count() == 40, '...e ficaram exatamente 40')

    # ---------- 4. FEED (misturado, embaralhado por seed, paginado) ----------
    v, itens = varrer(beto)
    ok('Ateliê da Ana' in lojas_do(itens), 'Loja "media" aparece no feed (como cartão de loja)')
    ok({'Pack de sons', 'Pack de ícones'} <= {n for n, _ in micro_do(itens)}, 'Itens das barracas "micro" aparecem no feed, juntados em quadrados')
    quads = [i for i in itens if i['t'] == 'quad']
    ok(quads and all(1 <= len(q['produtos']) <= 4 for q in quads), 'Cada quadrado junta de 1 a 4 itens')
    ok(any(len({p['loja_nome'] for p in q['produtos']}) >= 2 for q in quads), 'O quadrado mistura vendedores DIFERENTES (ninguém ocupa o quadrado sozinho quando há outros)')
    ok(len(micro_do(itens)) == len(set(micro_do(itens))), 'Nenhum item aparece duas vezes no feed')
    ok(not any('entrega' in p for i in itens for p in (i['loja']['produtos'] if i['t'] == 'loja' else i['produtos'])) and not any('pix_chave' in i.get('loja', {}) for i in itens),
       'O feed público NÃO vaza chave Pix nem instrução de entrega')
    ok(v['catalogos']['categorias'] and v['eh_admin'] is False and v['minha_loja_id'] is None and v['propagandas'] == [] and v['destaques'] == [],
       'Página 0 traz catálogos e flags; sem parceira nem avaliação, propagandas e destaques vêm vazios')
    # ordem: estável com a mesma seed, muda com outra (e a mudança de dados não reembaralha nada além do necessário)
    _, again = varrer(beto)
    ok(chaves(itens) == chaves(again), 'Mesma seed = mesma ordem (atualizar a tela não reorganiza o feed)')
    ordens = {tuple(chaves(varrer(beto, seed=sd)[1])) for sd in ('a1', 'b2', 'c3', 'd4')}
    ok(len(ordens) > 1, 'Seeds diferentes embaralham de forma diferente (ninguém fica sempre em primeiro)')
    ok(conteudo(varrer(beto, seed='zz')[1]) == conteudo(itens), 'Embaralhar não perde nem inventa itens: só muda a ordem e o agrupamento')
    # paginação
    bazar.PAGINA_FEED = 3
    pag0, todos = varrer(beto, seed='pg')
    ok(len(pag0['feed']['itens']) == 3 and pag0['feed']['tem_mais'] and pag0['feed']['total'] == len(todos), 'Paginação: página de 3, "tem mais" e total certos')
    bazar.PAGINA_FEED = 14
    ok(len(todos) == len(set(chaves(todos))) and chaves(todos) == chaves(varrer(beto, seed='pg')[1]), 'As páginas juntas = o feed inteiro (mesma seed), na mesma ordem, sem repetir nem faltar')
    ok(erro(emitir(beto, 'bazar_listar', {'pagina': 'x', 'seed': 'a'})) is None, 'Página inválida não derruba (vira 0)')
    # filtros
    _, f_ = varrer(beto, busca='aquarela')
    ok(not lojas_do(f_) and not micro_do(f_), 'Busca por "aquarela": o produto foi renomeado, não bate mais')
    _, f_ = varrer(beto, busca='retrato a4')
    ok(lojas_do(f_) == ['Ateliê da Ana'] and not micro_do(f_), 'Busca acha a loja pelo nome do produto (e só ela)')
    _, f_ = varrer(beto, busca='%')
    ok(not lojas_do(f_) and not micro_do(f_), 'Busca "%" não vira curinga')
    _, f_ = varrer(beto, categoria='moda')
    ok(not lojas_do(f_) and micro_do(f_) and all(l == 'Loja da Eva' for _, l in micro_do(f_)), 'Filtro por categoria')
    _, f_ = varrer(beto, tipo='digital')
    ok(micro_do(f_) and all(p['tipo'] == 'digital' for i in f_ for p in (i['loja']['produtos'] if i['t'] == 'loja' else i['produtos'])), 'Filtro por tipo: só produto digital')
    _, f_ = varrer(beto, tipo='xablau')
    ok(len(f_) == len(itens), 'Tipo inventado é ignorado (não filtra)')

    # loja grande só por admin: vira retângulo no feed e entra no carrossel de propagandas (com o texto da própria propaganda)
    l_ana = db.session.query(BazarLoja).filter_by(owner_id=ids['ana']).one()
    l_ana.porte = 'grande'; l_ana.anuncio_titulo = 'Semana do retrato'; l_ana.anuncio_texto = 'Retrato com desconto'; db.session.commit()
    v, f_ = varrer(beto)
    ok(any(i['t'] == 'loja' and i['loja']['porte'] == 'grande' for i in f_), 'Porte "grande" (definido por admin) continua no feed, só que como retângulo')
    ok([a['nome'] for a in v['propagandas']] == ['Ateliê da Ana'] and v['propagandas'][0]['titulo'] == 'Semana do retrato', 'Propagandas = só as lojas parceiras, com o título da própria propaganda')
    ok(not any('pix_chave' in a for a in v['propagandas']), 'Propaganda não vaza dado privado')
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'porte': 'micro', 'categoria': 'arte', 'pix_chave': 'ana@exemplo.com', 'pix_nome': 'Ana Ávila', 'pix_cidade': 'Brasília'})
    ok(db.session.query(BazarLoja).filter_by(owner_id=ids['ana']).one().porte == 'grande', 'Loja grande não volta a micro por edição do dono')
    l_ana.porte = 'media'; db.session.commit()
    v, _ = varrer(beto)
    ok(v['propagandas'] == [], 'Sem parceira, o carrossel de propagandas fica só com as do próprio Panteão (cliente)')

    # ---------- 5. PEDIDO ----------
    P_RETRATO, P_COMBO = p1['id'], p2['id']
    rec = emitir(ana, 'bazar_pedir', {'produto_id': P_RETRATO})
    ok('própria loja' in (erro(rec) or ''), 'Não dá pra comprar da própria loja')
    rec = emitir(hugo, 'bazar_pedir', {'produto_id': P_RETRATO})
    ok(erro(rec) and db.session.query(BazarPedido).count() == 0, 'Quem foi bloqueado pelo vendedor não abre pedido')
    for lixo in ({'produto_id': 99999}, {'produto_id': 'abc'}, {'produto_id': P_RETRATO, 'quantidade': 0}, {'produto_id': P_RETRATO, 'quantidade': 21}, {'produto_id': P_RETRATO, 'quantidade': 'x'},
                 {'produto_id': P_RETRATO, 'quantidade': 4}, {'produto_id': P_RETRATO, 'nota': 'pague em www.golpe.com'}):
        rec = emitir(beto, 'bazar_pedir', lixo)
        ok(erro(rec) is not None, f'Pedido inválido recusado: {lixo}')
    ok(db.session.query(BazarPedido).count() == 0, 'Nenhum pedido inválido foi criado')

    rec = emitir(beto, 'bazar_pedir', {'produto_id': P_RETRATO, 'quantidade': 2, 'nota': 'pode ser com fundo azul?'})
    ped = db.session.query(BazarPedido).one()
    ok(ped.status == 'aguardando' and ped.total_cent == 10000 and ped.preco_unit_cent == 5000 and ped.produto_nome == 'Retrato A4', 'Pedido nasce "aguardando" com preço e nome COPIADOS (2 x R$ 50,00)')
    recAna = ev(ana)
    ok(any(m['name'] == 'bazar_pedido' and m['args'][0]['papel'] == 'vendedor' for m in recAna), 'Regra 6: a vendedora recebe o pedido na hora, no ponto de vista dela')
    ok(db.session.query(Notificacao).filter_by(person_id=ids['ana'], tipo='bazar').count() == 1, 'E ganha um aviso na caixa de entrada')
    ok(not [m for m in ev(cris) if m['name'] in ('bazar_pedido', 'notificacao_nova', 'bazar_pendencias')], 'Quem não é do pedido não recebe nada do pedido')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': P_RETRATO})
    ok('já tem um pedido aberto' in (erro(rec) or ''), 'Pedido duplicado do mesmo produto é recusado')
    # o preço do pedido não muda se o vendedor editar o produto depois
    ENTREGA = 'Link: https://drive.exemplo/abc'
    emitir(ana, 'bazar_salvar_produto', {**base, 'id': P_RETRATO, 'nome': 'Retrato A4', 'preco_cent': 9000, 'estoque': 3, 'entrega': ENTREGA})
    ok(db.session.get(BazarPedido, ped.id).total_cent == 10000, 'Mudar o preço do produto depois NÃO altera o pedido já feito')
    emitir(ana, 'bazar_salvar_produto', {**base, 'id': P_RETRATO, 'nome': 'Retrato A4', 'preco_cent': 5000, 'estoque': 3, 'entrega': ENTREGA})

    # ações com o papel errado / fora de hora
    for quem, acao in ((beto, 'aceitar'), (beto, 'confirmar'), (beto, 'recebi'), (ana, 'paguei'), (ana, 'recebi'), (cris, 'aceitar'), (cris, 'cancelar')):
        rec = emitir(quem, 'bazar_agir', {'pedido_id': ped.id, 'acao': acao})
        ok(erro(rec) is not None, f'Ação fora de hora/papel recusada: {acao}')
    rec = emitir(ana, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'explodir'})
    ok(erro(rec) is not None, 'Ação inventada é recusada')
    ok(db.session.get(BazarPedido, ped.id).status == 'aguardando', 'Nada mudou no pedido por causa das tentativas inválidas')

    # a vendedora sem Pix cadastrado não aceita
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'porte': 'media', 'categoria': 'arte', 'pix_chave': ''})
    rec = emitir(ana, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'aceitar'})
    ok('pix' in (erro(rec) or '').lower() and db.session.get(BazarPedido, ped.id).status == 'aguardando', 'Sem chave Pix cadastrada o vendedor não aceita pedido')
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Ateliê da Ana', 'porte': 'media', 'categoria': 'arte', 'pix_chave': 'ana@exemplo.com', 'pix_nome': 'Ana Ávila', 'pix_cidade': 'Brasília'})
    ev(beto); ev(cris)

    # a chave Pix só aparece depois de aceito, e só pro comprador
    rec_b = emitir(beto, 'bazar_abrir_pedido', {'pedido_id': ped.id})
    ok('pix' not in next(x for x in rec_b if x['name'] == 'bazar_pedido')['args'][0], 'Antes de aceito, o comprador NÃO vê a chave Pix')
    rec = emitir(ana, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'aceitar'})
    ok(db.session.get(BazarPedido, ped.id).status == 'aceito', 'Vendedor aceita')
    ok(db.session.get(BazarProduto, P_RETRATO).estoque == 1, 'Aceitar RESERVA o estoque (3 - 2 = 1)')
    pb = next(x for x in ev(beto) if x['name'] == 'bazar_pedido')['args'][0]
    ok(pb['status'] == 'aceito' and pb['pix']['valor_cent'] == 10000 and 'copia_cola' in pb['pix'], 'Regra 6: o comprador vê o Pix (copia e cola) na hora, com o valor do pedido')
    ok(tlv(pb['pix']['copia_cola'])['54'] == '100.00' and tlv(tlv(pb['pix']['copia_cola'])['26'])['01'] == 'ana@exemplo.com', 'O copia e cola leva o valor e a chave da vendedora')
    ok('ana@exemplo.com' not in str({k: v for k, v in pb['pix'].items() if k != 'copia_cola'}), 'Fora do copia e cola a chave aparece só mascarada')
    pa = next(x for x in recAna + ev(ana) if x['name'] == 'bazar_pedido')['args'][0]
    ok('pix' not in pa, 'A vendedora não recebe o bloco de Pix (é o comprador quem paga)')
    rec_c = emitir(cris, 'bazar_abrir_pedido', {'pedido_id': ped.id})
    ok(erro(rec_c) and not any(x['name'] == 'bazar_pedido' for x in rec_c), 'Terceiro não abre o pedido nem recebe o Pix')
    rec = emitir(ana, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'aceitar'})
    ok(erro(rec) and db.session.get(BazarProduto, P_RETRATO).estoque == 1, 'Aceitar duas vezes: a 2ª é recusada e o estoque não é descontado de novo')

    # conversa do pedido
    rec = emitir(beto, 'bazar_mensagem', {'pedido_id': ped.id, 'texto': 'Oi! Posso pagar agora?'})
    ok(db.session.query(BazarMensagem).count() == 1, 'Mensagem do pedido gravada')
    ok(any(x['name'] == 'bazar_pedido' and x['args'][0]['mensagens'] for x in ev(ana)), 'Regra 6: a outra ponta recebe a mensagem na hora')
    rec = emitir(beto, 'bazar_mensagem', {'pedido_id': ped.id, 'texto': 'paga aqui bit.ly/golpe'})
    ok('links' in (erro(rec) or '').lower() and db.session.query(BazarMensagem).count() == 1, 'Link na conversa do pedido é recusado')
    rec = emitir(cris, 'bazar_mensagem', {'pedido_id': ped.id, 'texto': 'intrometido'})
    ok(erro(rec) and db.session.query(BazarMensagem).count() == 1, 'Terceiro não escreve na conversa')
    rec = emitir(beto, 'bazar_mensagem', {'pedido_id': ped.id, 'texto': '   '})
    ok(erro(rec) and db.session.query(BazarMensagem).count() == 1, 'Mensagem vazia é recusada')

    # pagamento -> confirmação -> entrega -> conclusão -> avaliação
    emitir(beto, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'paguei'}); ev(ana)
    ok(db.session.get(BazarPedido, ped.id).status == 'pago', 'Comprador informa que pagou')
    pb = next(x for x in emitir(beto, 'bazar_abrir_pedido', {'pedido_id': ped.id}) if x['name'] == 'bazar_pedido')['args'][0]
    ok('entrega' not in pb, 'Antes de o vendedor confirmar o Pix, o comprador NÃO vê a instrução de entrega')
    emitir(ana, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'nao_recebi'})
    ok(db.session.get(BazarPedido, ped.id).status == 'aceito', 'Vendedor que não achou o Pix devolve o pedido pra "aceito"')
    emitir(beto, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'paguei'})
    emitir(ana, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'confirmar'}); ev(beto)
    pb = next(x for x in emitir(beto, 'bazar_abrir_pedido', {'pedido_id': ped.id}) if x['name'] == 'bazar_pedido')['args'][0]
    ok(pb['status'] == 'confirmado' and pb['entrega'].startswith('Link'), 'Confirmado o Pix, o comprador passa a ver a instrução de entrega')
    rec = emitir(beto, 'bazar_avaliar', {'pedido_id': ped.id, 'nota': 5})
    ok('concluir' in (erro(rec) or ''), 'Não avalia antes de concluir')
    emitir(beto, 'bazar_agir', {'pedido_id': ped.id, 'acao': 'recebi'})
    ok(db.session.get(BazarPedido, ped.id).status == 'concluido', 'Comprador confirma o recebimento: concluído')
    ok(db.session.get(BazarProduto, P_RETRATO).vendidos == 2 and db.session.query(BazarLoja).filter_by(owner_id=ids['ana']).one().vendas == 1, 'Contadores de vendas sobem')
    for nota in (0, 6, 'x'):
        rec = emitir(beto, 'bazar_avaliar', {'pedido_id': ped.id, 'nota': nota})
        ok(erro(rec) is not None, f'Nota inválida recusada: {nota!r}')
    rec = emitir(cris, 'bazar_avaliar', {'pedido_id': ped.id, 'nota': 5})
    ok(erro(rec) is not None, 'Quem não comprou não avalia')
    rec = emitir(ana, 'bazar_avaliar', {'pedido_id': ped.id, 'nota': 5})
    ok(erro(rec) is not None, 'A vendedora não avalia a si mesma')
    emitir(beto, 'bazar_avaliar', {'pedido_id': ped.id, 'nota': 4, 'texto': 'Ficou lindo!'})
    la = db.session.query(BazarLoja).filter_by(owner_id=ids['ana']).one()
    ok(la.nota_qtd == 1 and la.nota_soma == 4, 'Avaliação entra na média da loja')
    rec = emitir(beto, 'bazar_avaliar', {'pedido_id': ped.id, 'nota': 1})
    ok('já avaliou' in (erro(rec) or '') and db.session.query(BazarLoja).filter_by(owner_id=ids['ana']).one().nota_qtd == 1, 'Só uma avaliação por pedido (e a média não muda)')

    v, _ = varrer(beto)
    ok(v['destaques'] == [], 'Destaque "bem avaliadas": UMA avaliação só não basta (mínimo de 3: uma nota 5 sozinha não vira destaque)')
    la.nota_qtd, la.nota_soma = 3, 12; db.session.commit()
    v, _ = varrer(beto)
    ok([d['nome'] for d in v['destaques']] == ['Ateliê da Ana'] and v['destaques'][0]['nota'] == 4.0, 'Destaque "bem avaliadas": com 3 avaliações entra por nota de verdade (e mostra a nota)')
    la.nota_qtd, la.nota_soma = 1, 4; db.session.commit()    # volta ao que era pro resto do teste
    st = next(x for x in emitir(ana, 'bazar_minha_loja') if x['name'] == 'bazar_minha')['args'][0]['loja']['stats']
    ok(st['concluidos'] == 1 and st['receita_cent'] == 10000 and st['abertos'] == 0, 'Painel do vendedor: 1 concluído, R$ 100,00 concluídos, nada aberto')

    # cancelar depois de aceito devolve o estoque; recusar também
    emitir(beto, 'bazar_pedir', {'produto_id': P_RETRATO, 'quantidade': 1})
    p_b = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    emitir(ana, 'bazar_agir', {'pedido_id': p_b.id, 'acao': 'aceitar'})
    ok(db.session.get(BazarProduto, P_RETRATO).estoque == 0, 'Segundo pedido reservou a última unidade')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': P_RETRATO, 'quantidade': 1})
    ok('esgotado' in (erro(rec) or '').lower(), 'Esgotado: o item não aceita novo pedido')
    emitir(beto, 'bazar_agir', {'pedido_id': p_b.id, 'acao': 'cancelar'})
    ok(db.session.get(BazarPedido, p_b.id).status == 'cancelado' and db.session.get(BazarProduto, P_RETRATO).estoque == 1, 'Cancelar um pedido aceito devolve o estoque')
    emitir(beto, 'bazar_pedir', {'produto_id': P_RETRATO, 'quantidade': 1})
    p_c = db.session.query(BazarPedido).order_by(BazarPedido.id.desc()).first()
    emitir(ana, 'bazar_agir', {'pedido_id': p_c.id, 'acao': 'recusar'})
    ok(db.session.get(BazarPedido, p_c.id).status == 'recusado' and db.session.get(BazarProduto, P_RETRATO).estoque == 1, 'Recusar não mexe no estoque (nunca foi reservado)')
    rec = emitir(beto, 'bazar_agir', {'pedido_id': p_c.id, 'acao': 'cancelar'})
    ok(erro(rec) is not None, 'Pedido recusado não volta')

    # corrida do último item: dois compradores, uma unidade, a vendedora aceita os dois
    emitir(cris, 'bazar_salvar_produto', {'id': db.session.query(BazarProduto).filter_by(nome='Pack de sons').one().id, 'nome': 'Pack de sons', 'preco_cent': 1500, 'tipo': 'digital', 'estoque': 1, 'entrega': 'Baixe: https://x.com/pack'})
    P_SOM = db.session.query(BazarProduto).filter_by(nome='Pack de sons').one().id
    emitir(beto, 'bazar_pedir', {'produto_id': P_SOM}); emitir(duda, 'bazar_pedir', {'produto_id': P_SOM})
    pa_, pb_ = db.session.query(BazarPedido).filter_by(produto_id=P_SOM).order_by(BazarPedido.id).all()
    emitir(cris, 'bazar_agir', {'pedido_id': pa_.id, 'acao': 'aceitar'})
    rec = emitir(cris, 'bazar_agir', {'pedido_id': pb_.id, 'acao': 'aceitar'})
    ok('estoque' in (erro(rec) or '').lower(), 'Corrida do último item: o 2º aceite é recusado por falta de estoque')
    ok(db.session.get(BazarPedido, pb_.id).status == 'aguardando' and db.session.get(BazarProduto, P_SOM).estoque == 0, '...o pedido que falhou continua "aguardando" (rollback) e o estoque não foi pra negativo')
    # transição dupla vinda de duas abas: a 2ª não aplica de novo
    import app.bazar as bz
    with app.app_context():
        u_ana = db.session.get(Person, ids['ana'])
    ok(levanta(lambda: bz.agir_no_pedido(db.session.get(Person, ids['cris']), pa_.id, 'aceitar')), 'Aceitar um pedido já aceito (outra aba) levanta erro em vez de aplicar de novo')

    # limite de pedidos abertos por comprador
    emitir(eva, 'bazar_salvar_loja', {'nome': 'Loja da Eva', 'categoria': 'moda'})
    eva_prods = db.session.query(BazarProduto).filter_by(loja_id=db.session.query(BazarLoja).filter_by(owner_id=ids['eva']).one().id).limit(15).all()
    for pr in eva_prods:
        emitir(gil, 'bazar_pedir', {'produto_id': pr.id})
    ok(db.session.query(BazarPedido).filter(BazarPedido.comprador_id == ids['gil'], BazarPedido.status == 'aguardando').count() == bazar.MAX_PEDIDOS_ABERTOS_COMPRADOR,
       f'Um comprador não abre mais de {bazar.MAX_PEDIDOS_ABERTOS_COMPRADOR} pedidos ao mesmo tempo')

    # lista de pedidos + pendências
    mp = next(x for x in emitir(ana, 'bazar_meus_pedidos') if x['name'] == 'bazar_pedidos')['args'][0]
    ok(len(mp['vendendo']) >= 3 and mp['comprando'] == [], 'Meus pedidos: a vendedora vê o que vende')
    ok(all('pix' not in p and 'mensagens' not in p for p in mp['vendendo']), 'A lista não carrega Pix nem conversa (só o pedido aberto)')

    # produto com pedido: apagar só desativa
    emitir(ana, 'bazar_apagar_produto', {'id': P_RETRATO})
    ok(db.session.get(BazarProduto, P_RETRATO).ativo is False, 'Produto que já teve pedido é desativado (o histórico depende dele), não apagado')
    emitir(ana, 'bazar_apagar_produto', {'id': P_COMBO})
    ok(db.session.get(BazarProduto, P_COMBO) is None, 'Produto sem pedido é apagado de verdade')
    _, f_ = varrer(beto)
    ok('Ateliê da Ana' not in lojas_do(f_), 'Loja sem produto ativo some do feed')

    # ---------- 6. DENÚNCIA + MODERAÇÃO ----------
    L_CRIS = db.session.query(BazarLoja).filter_by(owner_id=ids['cris']).one().id
    rec = emitir(cris, 'denunciar', {'tipo': 'loja', 'id': L_CRIS, 'motivo': 'spam'})
    ok(any(x['name'] == 'erro_bazinga' for x in rec), 'Não dá pra denunciar a própria loja')
    for u, cl in (('eva', eva), ('fabio', fabio)):
        emitir(cl, 'denunciar', {'tipo': 'loja', 'id': L_CRIS, 'motivo': 'ilegal', 'detalhe': 'vende coisa errada'})
    ok(not db.session.get(BazarLoja, L_CRIS).oculta, 'Duas denúncias ainda não escondem a loja')
    ev(beto)
    emitir(gil, 'denunciar', {'tipo': 'loja', 'id': L_CRIS, 'motivo': 'ilegal'})
    ok(db.session.get(BazarLoja, L_CRIS).oculta is True, 'Terceira denúncia de pessoas diferentes esconde a loja')
    ok(any(x['name'] == 'bazar_mudou' for x in ev(beto)), 'Regra 6: todo mundo é avisado que a vitrine mudou')
    _, f_ = varrer(beto)
    ok(not any(l == 'Cantinho do Cris' for _, l in micro_do(f_)), 'Loja oculta some do feed')
    rec = emitir(beto, 'bazar_abrir_loja', {'loja_id': L_CRIS})
    ok(erro(rec) is not None, 'E ninguém abre a página dela')
    rec = emitir(cris, 'bazar_abrir_loja', {'loja_id': L_CRIS})
    ok(any(x['name'] == 'bazar_loja' and x['args'][0]['eh_dono'] for x in rec), 'O dono ainda vê a própria loja')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': db.session.query(BazarProduto).filter_by(nome='Pack de ícones').one().id})
    ok(erro(rec) is not None, 'Não dá pra pedir de loja oculta')

    rec = emitir(beto, 'bazar_moderacao_listar')
    ok(erro(rec) and not any(x['name'] == 'bazar_moderacao' for x in rec), 'Quem não é admin não abre a fila de moderação')
    rec = emitir(beto, 'bazar_moderar', {'tipo': 'loja', 'alvo_id': L_CRIS, 'acao': 'restaurar'})
    ok(erro(rec) and db.session.get(BazarLoja, L_CRIS).oculta is True, 'Nem moderar (o servidor confere a cada chamada)')
    bazar.definir_admin(ids['duda'])
    fila = next(x for x in emitir(duda, 'bazar_moderacao_listar') if x['name'] == 'bazar_moderacao')['args'][0]['fila']
    g = next(f for f in fila if f['tipo'] == 'loja' and f['alvo_id'] == L_CRIS)
    ok(g['total'] == 3 and g['alvo']['oculta'] and {d['por'] for d in g['denuncias']} == {'Eva', 'Fabio', 'Gil'}, 'Admin vê a fila: 3 denúncias, quem fez, e que o alvo está oculto')
    emitir(duda, 'bazar_moderar', {'tipo': 'loja', 'alvo_id': L_CRIS, 'acao': 'restaurar'})
    ok(db.session.get(BazarLoja, L_CRIS).oculta is False and db.session.query(Denuncia).filter_by(tipo='loja', alvo_id=L_CRIS, resolvida=True).count() == 3, 'Restaurar: a loja volta e as 3 denúncias são dispensadas')
    emitir(hugo, 'denunciar', {'tipo': 'loja', 'id': L_CRIS, 'motivo': 'spam'})
    ok(not db.session.get(BazarLoja, L_CRIS).oculta, 'Depois de restaurada, a contagem recomeça do zero (1 denúncia nova não esconde)')

    # produto denunciado e removido
    P_ICONE = db.session.query(BazarProduto).filter_by(nome='Pack de ícones').one().id
    for cl in (eva, fabio, gil):
        emitir(cl, 'denunciar', {'tipo': 'produto', 'id': P_ICONE, 'motivo': 'spam'})
    ok(db.session.get(BazarProduto, P_ICONE).oculta is True, 'Produto também esconde com 3 denúncias')
    emitir(duda, 'bazar_moderar', {'tipo': 'produto', 'alvo_id': P_ICONE, 'acao': 'remover'})
    ok(db.session.get(BazarProduto, P_ICONE) is None, 'Remover derruba o produto (sem pedido: apaga)')
    fila = next(x for x in emitir(duda, 'bazar_moderacao_listar') if x['name'] == 'bazar_moderacao')['args'][0]['fila']
    ok(not any(f['tipo'] == 'produto' and f['alvo_id'] == P_ICONE for f in fila), 'E sai da fila')

    # nota do mapa denunciada, removida pela mesma tela
    nota = GeoNote(lat=-15.8, lng=-47.9, text='nota ruim', author_id=ids['cris'], duration_hours=24); db.session.add(nota); db.session.commit()
    for cl in (eva, fabio, gil):
        emitir(cl, 'denunciar', {'tipo': 'nota', 'id': nota.id, 'motivo': 'assedio'})
    ok(db.session.get(GeoNote, nota.id).oculta is True, 'Nota do mapa esconde com 3 denúncias (regra antiga continua)')
    fila = next(x for x in emitir(duda, 'bazar_moderacao_listar') if x['name'] == 'bazar_moderacao')['args'][0]['fila']
    ok(any(f['tipo'] == 'nota' and f['alvo']['titulo'] == 'nota ruim' for f in fila), 'A tela de moderação também cobre nota do mapa (pendência antiga)')
    emitir(duda, 'bazar_moderar', {'tipo': 'nota', 'alvo_id': nota.id, 'acao': 'remover'})
    ok(db.session.get(GeoNote, nota.id) is None, 'Remover apaga a nota')
    rec = emitir(duda, 'bazar_moderar', {'tipo': 'usuario', 'alvo_id': ids['cris'], 'acao': 'remover'})
    ok(erro(rec) is not None, 'Pessoa não é "removida" (não existe banimento): só registrada')
    rec = emitir(duda, 'bazar_moderar', {'tipo': 'xablau', 'alvo_id': 1, 'acao': 'remover'})
    ok(erro(rec) is not None, 'Tipo inventado é recusado')

    # sem login nada responde
    anon = socketio.test_client(app); anon.get_received()
    for nome in ('bazar_listar', 'bazar_pedir', 'bazar_salvar_loja', 'bazar_agir', 'bazar_moderacao_listar'):
        anon.emit(nome, {'produto_id': 1})
    ok(not ev(anon), 'Sem login: nenhum evento do Bazar responde')

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
