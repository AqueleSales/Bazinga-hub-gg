"""Pagamentos pelo app (Rodada 32): provedor (simulado só fora do Render ou pedido de propósito), liberar a loja (o dono pede, o admin libera),
pedido pago pelo app (cobrança, simulação só do comprador, confirmação sozinha, cancelamento), Pix direto intacto, Asaas simulado (split, chave só
no cabeçalho, webhook com token e reconferência) e o que o código promete."""
import json, os, sys
from datetime import timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
for k in ('RENDER', 'PAGAMENTOS', 'ASAAS_API_KEY', 'ASAAS_WEBHOOK_TOKEN', 'ASAAS_AMBIENTE', 'TAXA_PLATAFORMA_PCT'):
    os.environ.pop(k, None)
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import bazar, bazar_events, pagamentos
from app.models import Role, Person, BazarLoja, BazarProduto, BazarPedido, Cobranca, Notificacao, br_now

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cl, nome=None):
    return [m for m in cl.get_received() if nome is None or m['name'] == nome]


def setenv(**kw):
    for k, v in kw.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ---------------- 1. quando o pagamento pelo app existe ----------------
setenv(RENDER=None, PAGAMENTOS=None, ASAAS_API_KEY=None)
ok(pagamentos.provedor() == 'simulado' and pagamentos.modo_teste(), 'fora do Render, sem chave: simulado (desenvolvimento)')
setenv(RENDER='1')
ok(pagamentos.provedor() is None, 'NO RENDER sem chave: desligado (senão qualquer um "pagaria" de graça)')
setenv(PAGAMENTOS='simulado')
ok(pagamentos.provedor() == 'simulado', 'no Render só liga o simulado se alguém pedir de propósito (PAGAMENTOS=simulado)')
setenv(PAGAMENTOS='asaas')
ok(pagamentos.provedor() is None, 'PAGAMENTOS=asaas sem a chave não liga nada')
setenv(PAGAMENTOS=None, ASAAS_API_KEY='chave-secreta-asaas')
ok(pagamentos.provedor() == 'asaas' and pagamentos.modo_teste() and pagamentos.ambiente() == 'sandbox', 'com a chave: Asaas, e em sandbox por padrão (modo teste)')
setenv(ASAAS_AMBIENTE='producao')
ok(not pagamentos.modo_teste(), 'ASAAS_AMBIENTE=producao tira o aviso de modo teste')
setenv(PAGAMENTOS='desligado')
ok(pagamentos.provedor() is None, 'PAGAMENTOS=desligado desliga tudo')
setenv(PAGAMENTOS=None, ASAAS_API_KEY=None, ASAAS_AMBIENTE=None, RENDER=None)
setenv(TAXA_PLATAFORMA_PCT='99'); ok(pagamentos.taxa_pct() == 30.0, 'a taxa do Pantheon tem teto de 30%')
setenv(TAXA_PLATAFORMA_PCT='abc'); ok(pagamentos.taxa_pct() == 0.0, 'taxa inválida vira 0')
setenv(TAXA_PLATAFORMA_PCT=None)

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('Ana', 'Beto', 'Cris'):
        p = Person(name=nome, email=f'{nome.lower()}@x', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=30))
        db.session.add(p); db.session.commit(); ids[nome.lower()] = p.id
    bazar.definir_admin(ids['cris'])

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    def emitir(cl, nome, dados=None):
        bazar_events._ultimo.clear()
        cl.emit(nome, dados or {})
        return ev(cl)

    def erro(rec):
        return next((m['args'][0]['msg'] for m in rec if m['name'] == 'bazar_erro'), None)

    def ultimo_pedido(rec):
        x = [m['args'][0] for m in rec if m['name'] == 'bazar_pedido']
        return x[-1] if x else None

    ana, fc_ana = cliente('ana'); beto, fc_beto = cliente('beto'); cris, fc_cris = cliente('cris')
    H = {'X-Requested-With': 'fetch'}
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Doces da Ana', 'categoria': 'comida', 'pix_chave': 'ana@exemplo.com', 'pix_nome': 'Ana', 'pix_cidade': 'Brasilia'})
    emitir(ana, 'bazar_salvar_produto', {'nome': 'Brigadeiro', 'descricao': 'caixa com 12', 'preco_cent': 4500, 'tipo': 'fisico', 'estoque': 10, 'aceita_retirada': True})
    emitir(ana, 'bazar_salvar_produto', {'nome': 'Beijinho', 'descricao': 'caixa com 12', 'preco_cent': 3000, 'tipo': 'fisico', 'estoque': 10, 'aceita_retirada': True})
    emitir(ana, 'bazar_salvar_produto', {'nome': 'Cajuzinho', 'descricao': 'caixa com 12', 'preco_cent': 2500, 'tipo': 'fisico', 'estoque': 10, 'aceita_retirada': True})
    P1, P2, P3 = [p.id for p in BazarProduto.query.order_by(BazarProduto.id).all()]
    loja = BazarLoja.query.one()

    # ---------------- 2. sem liberação: o Pix direto continua igual ----------------
    ok(not bazar.checkout_ativo(loja), 'loja nova NÃO recebe pelo app (precisa de liberação do admin)')
    rec = emitir(beto, 'bazar_pedir', {'produto_id': P1, 'entrega': 'retirada'})
    pid = BazarPedido.query.one().id
    rec = emitir(ana, 'bazar_agir', {'pedido_id': pid, 'acao': 'aceitar'})
    ped = BazarPedido.query.get(pid)
    ok(ped.pagamento == 'pix', 'sem liberação o pedido aceito é Pix direto')
    jb = bazar.pedido_json(ped, ids['beto'])
    ok(jb['pagamento'] == 'pix' and jb.get('pix') and 'cobranca' not in jb, 'e o comprador recebe o Pix copia e cola do vendedor, como sempre')
    emitir(beto, 'bazar_agir', {'pedido_id': pid, 'acao': 'paguei'}); emitir(ana, 'bazar_agir', {'pedido_id': pid, 'acao': 'confirmar'})
    emitir(beto, 'bazar_agir', {'pedido_id': pid, 'acao': 'recebi'})
    ok(BazarPedido.query.get(pid).status == 'concluido', 'o fluxo antigo (paguei, confirmar, recebi) segue funcionando')

    # ---------------- 3. liberar a loja: o dono pede, o admin decide ----------------
    ok(emitir(beto, 'bazar_checkout_pedir') and BazarLoja.query.one().checkout_status is None, 'quem não tem loja não pede checkout')
    rec = emitir(ana, 'bazar_checkout_pedir')
    ok(BazarLoja.query.one().checkout_status == 'pedido' and any(m['name'] == 'bazar_minha' for m in rec), 'o dono pede e a loja fica "pedido" (na fila)')
    ok('já está na fila' in (erro(emitir(ana, 'bazar_checkout_pedir')) or ''), 'pedir de novo é recusado')
    ok(any('pediu pra receber' in n.titulo for n in Notificacao.query.filter_by(person_id=ids['cris']).all()), 'o admin é avisado na caixa de entrada')
    ok(fc_ana.get('/admin/api/lojas').status_code == 403, 'quem não é admin não vê a fila de lojas')
    lista = fc_cris.get('/admin/api/lojas?filtro=pedido').get_json()
    ok(len(lista['lojas']) == 1 and lista['lojas'][0]['nome'] == 'Doces da Ana' and lista['lojas'][0]['produtos'] == 3, 'o admin vê a loja que pediu, com contagem de produtos')
    ok(fc_cris.post(f'/admin/api/lojas/{loja.id}/checkout', json={'acao': 'liberar'}).status_code == 400, 'decidir sem o cabeçalho anti-forja é recusado')
    ok(fc_cris.post(f'/admin/api/lojas/{loja.id}/checkout', json={'acao': 'explodir'}, headers=H).status_code == 400, 'ação inventada é recusada')
    ok(fc_cris.post(f'/admin/api/lojas/{loja.id}/checkout', json={'acao': 'liberar', 'wallet_id': "x'; drop"}, headers=H).status_code == 400, 'carteira com lixo é recusada')
    ok(fc_ana.post(f'/admin/api/lojas/{loja.id}/checkout', json={'acao': 'liberar'}, headers=H).status_code == 403, 'o próprio dono não se libera')
    rr = fc_cris.post(f'/admin/api/lojas/{loja.id}/checkout', json={'acao': 'liberar'}, headers=H)
    db.session.refresh(loja)
    ok(rr.status_code == 200 and loja.checkout_status == 'liberado' and bazar.checkout_ativo(loja), 'admin libera (no simulado não precisa de carteira)')
    ok(any('pode receber pelo app' in n.titulo for n in Notificacao.query.filter_by(person_id=ids['ana']).all()), 'o dono é avisado')
    ok(bazar.loja_json(loja)['pague_no_app'] is True, 'a vitrine mostra "pague pelo app"')

    # ---------------- 4. pedido pago pelo app ----------------
    emitir(beto, 'bazar_pedir', {'produto_id': P2, 'entrega': 'retirada'})
    p2 = BazarPedido.query.filter_by(produto_id=P2).one().id
    emitir(ana, 'bazar_agir', {'pedido_id': p2, 'acao': 'aceitar'})
    ped = BazarPedido.query.get(p2)
    ok(ped.pagamento == 'app' and ped.status == 'aceito', 'com a loja liberada o pedido aceito é pago pelo app')
    jb = bazar.pedido_json(ped, ids['beto'])
    ok(jb['pagamento'] == 'app' and 'pix' not in jb and jb['modo_teste'] is True and jb['cobranca'] is None, 'o comprador NÃO recebe a chave do vendedor; ainda sem cobrança; modo teste')
    ok('confirmado pelo app' in (erro(emitir(beto, 'bazar_agir', {'pedido_id': p2, 'acao': 'paguei'})) or ''), 'não dá pra "avisar que pagou" num pedido do app')
    ok(BazarPedido.query.get(p2).status == 'aceito', '...e o status não mudou')
    ok(not ultimo_pedido(emitir(ana, 'bazar_agir', {'pedido_id': p2, 'acao': 'confirmar'})) or BazarPedido.query.get(p2).status == 'aceito', 'o vendedor também não confirma na mão')
    ev(ana); ev(beto)

    # gerar o Pix
    ok('Pedido não encontrado' in (erro(emitir(ana, 'bazar_pagar', {'pedido_id': p2})) or ''), 'o vendedor não gera o Pix do comprador')
    rec = emitir(beto, 'bazar_pagar', {'pedido_id': p2})
    pj = ultimo_pedido(rec)
    cb = pj and pj['cobranca']
    ok(cb and cb['copia_cola'].startswith('PANTHEON-TESTE-') and cb['valor_cent'] == 3000 and cb['simulada'], 'o comprador recebe a cobrança: código de teste (NÃO é um Pix válido), valor certo')
    rec = emitir(beto, 'bazar_pagar', {'pedido_id': p2})
    ok(Cobranca.query.filter_by(tipo='pedido', ref_id=p2).count() == 1 and ultimo_pedido(rec)['cobranca']['ext_id'] == cb['ext_id'], 'gerar de novo reaproveita a cobrança aberta (nada de cobrar duas vezes)')
    ok(bazar.pedido_json(BazarPedido.query.get(p2), ids['ana']).get('cobranca') is None, 'o vendedor não vê o código da cobrança')

    # simular: só o comprador
    ok('Pedido não encontrado' in (erro(emitir(ana, 'bazar_simular_pagamento', {'pedido_id': p2})) or ''), 'o vendedor não consegue "simular" o pagamento do comprador')
    ok(BazarPedido.query.get(p2).status == 'aceito', '...e nada mudou')
    ev(ana); ev(cris)
    rec_b = emitir(beto, 'bazar_simular_pagamento', {'pedido_id': p2})
    ped = BazarPedido.query.get(p2)
    ok(ped.status == 'confirmado' and Cobranca.query.filter_by(ref_id=p2, tipo='pedido').one().status == 'paga', 'comprador simula: cobrança paga e pedido CONFIRMADO sozinho')
    ok(any(m['name'] == 'bazar_pedido' and m['args'][0]['status'] == 'confirmado' for m in rec_b), 'regra 6: o comprador recebe o pedido atualizado')
    ok(any(m['name'] == 'bazar_pedido' and m['args'][0]['status'] == 'confirmado' for m in ev(ana)), 'regra 6: o vendedor recebe também')
    ok(any('pago pelo app' in n.titulo for n in Notificacao.query.filter_by(person_id=ids['ana']).all()), 'o vendedor é avisado pra preparar a entrega')
    ok(bazar.contar_pendencias(ids['ana']) >= 1, 'o pedido pago aparece nas pendências do vendedor')
    n_avisos = Notificacao.query.count()
    emitir(beto, 'bazar_simular_pagamento', {'pedido_id': p2})
    ok(BazarPedido.query.get(p2).status == 'confirmado' and Notificacao.query.count() == n_avisos, 'simular de novo não faz nada (nem avisa duas vezes)')
    emitir(beto, 'bazar_agir', {'pedido_id': p2, 'acao': 'recebi'})
    ok(BazarPedido.query.get(p2).status == 'concluido' and BazarLoja.query.one().vendas == 2, 'comprador confirma o recebimento: concluído e a venda conta')

    # cancelamento: a cobrança aberta morre
    emitir(beto, 'bazar_pedir', {'produto_id': P3, 'entrega': 'retirada'})
    p3 = BazarPedido.query.filter_by(produto_id=P3).one().id
    emitir(ana, 'bazar_agir', {'pedido_id': p3, 'acao': 'aceitar'}); emitir(beto, 'bazar_pagar', {'pedido_id': p3})
    est_antes = BazarProduto.query.get(P3).estoque
    emitir(ana, 'bazar_agir', {'pedido_id': p3, 'acao': 'cancelar'})
    ok(BazarPedido.query.get(p3).status == 'cancelado' and Cobranca.query.filter_by(ref_id=p3, tipo='pedido').one().status == 'cancelada', 'cancelar o pedido cancela a cobrança em aberto')
    ok(BazarProduto.query.get(P3).estoque == est_antes + 1, 'e o estoque volta')
    ok('não está mais aberta' in (erro(emitir(beto, 'bazar_simular_pagamento', {'pedido_id': p3})) or '') or BazarPedido.query.get(p3).status == 'cancelado', 'não dá pra "pagar" um pedido cancelado')

    # ---------------- 5. produção sem gateway: nada de simulação ----------------
    setenv(RENDER='1', EXIGIR_TERMOS='0')      # (no Render os Termos são exigidos: aqui não é o assunto)
    ok(not bazar.checkout_ativo(loja), 'no Render sem gateway a loja liberada volta pro Pix direto')
    ok('não está ligado' in (erro(emitir(ana, 'bazar_checkout_pedir')) or ''), 'pedir checkout sem gateway é recusado')
    setenv(RENDER=None, EXIGIR_TERMOS=None)

    # ---------------- 6. Asaas (simulado: nenhuma chamada de rede de verdade) ----------------
    setenv(ASAAS_API_KEY='chave-secreta-asaas', ASAAS_WEBHOOK_TOKEN='token-do-webhook')
    chamadas = []
    estado_asaas = {'status': 'PENDING', 'valor': 30.0}

    class R:
        def __init__(self, st, corpo):
            self.status_code = st; self._c = corpo

        def json(self):
            return self._c

    def falso(metodo, url, **kw):
        chamadas.append((metodo, url, kw))
        if url.endswith('/customers') and metodo == 'GET':
            return R(200, {'data': []})
        if url.endswith('/customers') and metodo == 'POST':
            return R(200, {'id': 'cus_1'})
        if url.endswith('/payments') and metodo == 'POST':
            return R(200, {'id': 'pay_abc123'})
        if url.endswith('/pixQrCode'):
            return R(200, {'payload': '00020126PIXREAL', 'encodedImage': 'x', 'expirationDate': '2099-01-01 10:00:00'})
        if '/payments/pay_abc123' in url and metodo == 'GET':
            return R(200, {'id': 'pay_abc123', 'status': estado_asaas['status'], 'value': estado_asaas['valor']})
        if metodo == 'DELETE':
            return R(200, {'deleted': True})
        return R(404, {'errors': [{'description': 'nada'}]})

    import requests as rq
    pagamentos.requests.request = falso
    ok(rq is pagamentos.requests, 'o teste troca só o `requests` do módulo de pagamentos')

    # loja sem carteira: no gateway real não cobra (senão o dinheiro cairia na conta do Pantheon)
    emitir(beto, 'bazar_pedir', {'produto_id': P1, 'entrega': 'retirada'})
    p4 = BazarPedido.query.filter_by(produto_id=P1).order_by(BazarPedido.id.desc()).first().id
    ok(not bazar.checkout_ativo(loja), 'no Asaas a loja sem carteira (walletId) NÃO recebe pelo app')
    emitir(ana, 'bazar_agir', {'pedido_id': p4, 'acao': 'aceitar'})
    ok(BazarPedido.query.get(p4).pagamento == 'pix', '...então o pedido cai no Pix direto')
    emitir(beto, 'bazar_agir', {'pedido_id': p4, 'acao': 'cancelar'})
    rr = fc_cris.post(f'/admin/api/lojas/{loja.id}/checkout', json={'acao': 'liberar'}, headers=H)
    ok(rr.status_code == 400 and 'carteira' in rr.get_json()['erro'], 'no Asaas o admin NÃO consegue liberar uma loja sem carteira (walletId)')
    ok(fc_cris.post(f'/admin/api/lojas/{loja.id}/checkout', json={'acao': 'revogar'}, headers=H).status_code == 200 and not bazar.checkout_ativo(db.session.get(BazarLoja, loja.id)), 'revogar tira da loja o recebimento pelo app')
    rr = fc_cris.post(f'/admin/api/lojas/{loja.id}/checkout', json={'acao': 'liberar', 'wallet_id': 'wallet-abcdef-123'}, headers=H)
    ok(db.session.get(BazarLoja, loja.id).wallet_id == 'wallet-abcdef-123' and bazar.checkout_ativo(db.session.get(BazarLoja, loja.id)), 'com a carteira colada pelo admin a loja recebe pelo app')
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Doces da Ana', 'wallet_id': 'roubada-123456', 'checkout_status': 'liberado'})
    ok(db.session.get(BazarLoja, loja.id).wallet_id == 'wallet-abcdef-123', 'o dono não consegue trocar a carteira pelo salvar da loja')

    os.environ['TAXA_PLATAFORMA_PCT'] = '10'
    emitir(beto, 'bazar_pedir', {'produto_id': P2, 'entrega': 'retirada'})
    p5 = BazarPedido.query.filter_by(produto_id=P2).order_by(BazarPedido.id.desc()).first().id
    emitir(ana, 'bazar_agir', {'pedido_id': p5, 'acao': 'aceitar'})
    ok(BazarPedido.query.get(p5).pagamento == 'app', 'com carteira, o pedido é pago pelo app no Asaas')
    chamadas.clear()
    rec = emitir(beto, 'bazar_pagar', {'pedido_id': p5})
    cobr = Cobranca.query.filter_by(ref_id=p5, tipo='pedido').one()
    ok(cobr.provedor == 'asaas' and cobr.ext_id == 'pay_abc123' and cobr.payload == '00020126PIXREAL' and cobr.valor_cent == 3000, 'cobrança criada no gateway e guardada (id, Pix copia e cola, valor)')
    post = next(k for (m, u, k) in chamadas if m == 'POST' and u.endswith('/payments'))['json']
    ok(post['billingType'] == 'PIX' and post['value'] == 30.0 and post['externalReference'] == f'pedido:{p5}', 'cobrança Pix com o valor certo e a referência do pedido')
    ok(post['split'] == [{'walletId': 'wallet-abcdef-123', 'fixedValue': 27.0}], 'o valor é DIVIDIDO: 90% pra carteira da loja, 10% de taxa fica com o Pantheon')
    ok(all(k['headers']['access_token'] == 'chave-secreta-asaas' for (_, _, k) in chamadas), 'a chave vai no cabeçalho access_token')
    ok(all('chave-secreta-asaas' not in u and 'chave-secreta-asaas' not in json.dumps(k.get('json') or {}) for (_, u, k) in chamadas), 'e nunca na URL nem no corpo')
    ok(all(u.startswith('https://api-sandbox.asaas.com/v3') for (_, u, _) in chamadas), 'sandbox por padrão')
    os.environ.pop('TAXA_PLATAFORMA_PCT')
    ok(not any(m['name'] == 'bazar_simular_pagamento' for m in rec) and 'não pode ser simulada' in (erro(emitir(beto, 'bazar_simular_pagamento', {'pedido_id': p5})) or ''),
       'no Asaas não existe "simular pagamento"')

    # webhook
    hook = lambda token, corpo: app.test_client().post('/webhooks/asaas', json=corpo, headers={'asaas-access-token': token} if token is not None else {})
    pago = {'event': 'PAYMENT_RECEIVED', 'payment': {'id': 'pay_abc123', 'status': 'RECEIVED', 'value': 30.0}}
    ok(hook(None, pago).status_code == 401 and hook('errado', pago).status_code == 401, 'webhook sem token ou com token errado: 401')
    ok(BazarPedido.query.get(p5).status == 'aceito', '...e nada muda')
    os.environ.pop('ASAAS_WEBHOOK_TOKEN')
    ok(hook('', pago).status_code == 401, 'sem ASAAS_WEBHOOK_TOKEN configurado o webhook recusa tudo')
    os.environ['ASAAS_WEBHOOK_TOKEN'] = 'token-do-webhook'
    estado_asaas.update(status='PENDING')
    ok(hook('token-do-webhook', pago).status_code == 200 and BazarPedido.query.get(p5).status == 'aceito', 'aviso falso (o gateway diz que NÃO foi pago): reconferido e ignorado')
    estado_asaas.update(status='RECEIVED', valor=1.0)
    hook('token-do-webhook', pago)
    ok(BazarPedido.query.get(p5).status == 'aceito', 'valor diferente do cobrado: ignorado')
    estado_asaas.update(status='RECEIVED', valor=30.0)
    ok(hook('token-do-webhook', {'event': 'PAYMENT_RECEIVED', 'payment': {'id': 'pay_desconhecido'}}).status_code == 200, 'pagamento que não é nosso: 200 e nada acontece')
    ev(beto); ev(ana)
    ok(hook('token-do-webhook', pago).status_code == 200 and BazarPedido.query.get(p5).status == 'confirmado', 'pagamento confirmado no gateway: pedido CONFIRMADO')
    ok(any(m['name'] == 'bazar_pedido' and m['args'][0]['status'] == 'confirmado' for m in ev(beto)), 'o comprador vê na hora (regra 6)')
    avisos = Notificacao.query.count()
    hook('token-do-webhook', pago)
    ok(Notificacao.query.count() == avisos and Cobranca.query.filter_by(ref_id=p5, tipo='pedido', status='paga').count() == 1, 'webhook repetido não aplica duas vezes')
    ok(hook('token-do-webhook', {'event': 'PAYMENT_OVERDUE', 'payment': {'id': 'pay_abc123'}}).status_code == 200 and Cobranca.query.filter_by(ref_id=p5).one().status == 'paga', 'vencimento depois de pago não desfaz')

    # gateway com erro vira mensagem, nunca vaza a chave
    pagamentos.requests.request = lambda *a, **k: R(400, {'errors': [{'description': 'CPF inválido'}]})
    emitir(beto, 'bazar_pedir', {'produto_id': P3, 'entrega': 'retirada'})
    p6 = BazarPedido.query.filter_by(produto_id=P3).order_by(BazarPedido.id.desc()).first().id
    emitir(ana, 'bazar_agir', {'pedido_id': p6, 'acao': 'aceitar'})
    msg = erro(emitir(beto, 'bazar_pagar', {'pedido_id': p6})) or ''
    ok('CPF inválido' in msg and 'chave-secreta' not in msg and Cobranca.query.filter_by(ref_id=p6).count() == 0, 'erro do gateway vira mensagem clara (sem chave) e nada é cobrado')
    pagamentos.requests.request = lambda *a, **k: (_ for _ in ()).throw(rq.ConnectionError('fora'))
    msg = erro(emitir(beto, 'bazar_pagar', {'pedido_id': p6})) or ''
    ok('não respondeu' in msg, 'gateway fora do ar: mensagem clara')
    setenv(ASAAS_API_KEY=None, ASAAS_WEBHOOK_TOKEN=None)

# ---------------- 7. o que o código promete ----------------
raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
leia = lambda *p: open(os.path.join(raiz, *p), encoding='utf-8').read()
pg = leia('app', 'pagamentos.py')
ok('hmac.compare_digest' in pg and 'consultar(c)' in pg, 'webhook: comparação de token em tempo constante e reconferência na API')
ok('wallet_id' in pg and "Essa loja ainda não tem carteira" in pg, 'no gateway real a cobrança de pedido exige carteira (o Pantheon não segura dinheiro)')
ok('nenhum banco paga isso' in pg, 'o código de teste é de propósito inválido como Pix')

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
