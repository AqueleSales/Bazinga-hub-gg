"""Rodada 36: entrega acompanhada no mapa. Papel de entregador (cadastro com aceite), designar (a própria loja ou uma pessoa), estados novos do pedido
(a caminho, entregue), posição ao vivo SÓ durante a entrega e SÓ pras pontas, destino que o servidor lê do aparelho, tempo estimado, fim automático,
Modo Fantasma, posição por IP/suspeita, revogar o compartilhamento, regra 6 e o que os arquivos do cliente prometem. Sem rede."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from datetime import timedelta
from sqlalchemy import event
from app import create_app, db, socketio, bazar, bazar_events, entregas, events
from app.models import Role, Person, Friendship, BazarLoja, BazarProduto, BazarPedido, BazarEntregador, BazarDisputa, Notificacao, br_now

falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()


def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


app = create_app()
SP = (-23.5505, -46.6333)             # onde o comprador está (o destino)
LOJA = (-23.5600, -46.6500)           # onde fica a loja


def anda(lat, lng, passo=0.0):
    return {'lat': lat + passo, 'lng': lng + passo, 'fonte': 'aparelho'}


# ---------- 1. a conta do tempo (sem banco) ----------
d, eta = entregas.estimar(SP[0], SP[1], None, 'moto')
ok(d is None and eta is None, 'sem destino não há distância nem tempo')
d, eta = entregas.estimar(SP[0], SP[1], (SP[0] + 0.01, SP[1]), 'moto')           # ~1,11 km em linha reta
ok(1100 <= d <= 1120, f'a distância é a em linha reta (~1,1 km): {d} m')
esperado = round(d * entregas.FATOR_ROTA / (28 / 3.6))
ok(abs(eta - esperado) <= 1, f'o tempo é distância x fator de rota / velocidade da moto ({eta} s)')
ok(entregas.estimar(SP[0], SP[1], (SP[0] + 0.01, SP[1]), 'a_pe')[1] > 4 * eta, 'a pé demora bem mais que de moto')
ok(entregas.estimar(SP[0], SP[1], (SP[0] + 0.0002, SP[1]), 'moto')[1] == 0, 'a menos de 60 m é "chegando" (tempo zero)')
ok(entregas.estimar(SP[0], SP[1], (SP[0] + 0.0001, SP[1]), 'carro')[0] < entregas.CHEGOU_M, 'a distância curta é devolvida')
ok(entregas.estimar(SP[0], SP[1], (SP[0] + 0.0005, SP[1]), 'moto')[1] >= 60 or entregas.estimar(SP[0], SP[1], (SP[0] + 0.0005, SP[1]), 'moto')[0] <= 60,
   'tempo mínimo de um minuto fora da zona de chegada')
try:
    entregas.transporte_valido('foguete')
    ok(False, 'transporte fora da lista é recusado')
except bazar.ErroBazar:
    ok(True, 'transporte fora da lista é recusado')
ok(entregas.transporte_valido('') == 'moto', 'sem escolha, o transporte padrão é a moto')

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('Ana', 'Beto', 'Cris', 'Duda', 'Eva', 'Fabio', 'Gil'):
        p = Person(name=nome, email=f'{nome.lower()}@x', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=30))
        db.session.add(p); db.session.commit(); ids[nome.lower()] = p.id
    loja = BazarLoja(owner_id=ids['ana'], nome='Pastelaria da Ana', categoria='comida', pix_chave='ana@exemplo.com', pix_nome='Ana', pix_cidade='Sao Paulo',
                     aberta=True, pino_lat=LOJA[0], pino_lng=LOJA[1], pino_aprox=False)
    db.session.add(loja); db.session.commit()
    prod = BazarProduto(loja_id=loja.id, nome='Pastel de queijo', preco_cent=1200, tipo='fisico', frete_cent=500, aceita_retirada=True, ativo=True)
    prod_digital = BazarProduto(loja_id=loja.id, nome='Receita', preco_cent=500, tipo='digital', ativo=True)
    db.session.add_all([prod, prod_digital]); db.session.commit()
    PROD, PROD_DIG = prod.id, prod_digital.id
    # fabio e o comprador se bloquearam
    db.session.add(Friendship(requester_id=ids['fabio'], addressee_id=ids['beto'], status='blocked')); db.session.commit()

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

    def pos(cl, lat, lng, fonte='aparelho'):
        entregas_rele_zero()
        cl.emit('atualizar_localizacao', {'lat': lat, 'lng': lng, 'fonte': fonte})
        return ev(cl)

    def entregas_rele_zero():
        for rec in entregas._ativas.values():
            rec['rele'] = 0.0          # o freio de 2 s é testado à parte

    def pedido(pid):
        db.session.expire_all()
        return db.session.get(BazarPedido, pid)

    ana, beto, cris, duda, eva, fabio = (cliente(u) for u in ('ana', 'beto', 'cris', 'duda', 'eva', 'fabio'))
    cris2 = cliente('cris')            # a mesma pessoa em outra aba (regra 6)
    for u in ('ana', 'beto', 'cris', 'duda'):
        db.session.get(Person, ids[u])

    # ---------- 2. o pedido de envio com o ponto de entrega ----------
    dados_pedido = {'produto_id': PROD, 'quantidade': 1, 'entrega': 'envio', 'endereco': 'Rua Augusta 100, Consolação, São Paulo, 01305-000', 'usar_posicao': True}
    rec = emitir(beto, 'bazar_pedir', dados_pedido)
    aberto = next(m['args'][0] for m in rec if m['name'] == 'bazar_pedido_aberto')
    ok(aberto['sem_ponto'] is True and pedido(aberto['pedido_id']).destino_lat is None, 'sem posição do aparelho o pedido sai do mesmo jeito, sem ponto, e o comprador é avisado')
    emitir(beto, 'bazar_agir', {'pedido_id': aberto['pedido_id'], 'acao': 'cancelar'})
    pos(beto, SP[0], SP[1], fonte='ip')
    rec = emitir(beto, 'bazar_pedir', dados_pedido)
    aberto = next(m['args'][0] for m in rec if m['name'] == 'bazar_pedido_aberto')
    ok(aberto['sem_ponto'] is True and pedido(aberto['pedido_id']).destino_lat is None, 'posição só por IP também não vira ponto de entrega')
    emitir(beto, 'bazar_agir', {'pedido_id': aberto['pedido_id'], 'acao': 'cancelar'})
    pos(beto, SP[0], SP[1])
    forjado = dict(dados_pedido, destino_lat=1.0, destino_lng=2.0, lat=1.0, lng=2.0)
    rec = emitir(beto, 'bazar_pedir', forjado)
    pid = next(m['args'][0]['pedido_id'] for m in rec if m['name'] == 'bazar_pedido_aberto')
    p = pedido(pid)
    ok(abs(p.destino_lat - round(SP[0], 5)) < 1e-6 and abs(p.destino_lng - round(SP[1], 5)) < 1e-6, 'o destino é a posição do aparelho lida PELO SERVIDOR (coordenada forjada no pedido é ignorada)')
    ok(p.entrega_estado is None and p.entregador_id is None, 'o pedido nasce sem entregador')
    jb = bazar.pedido_json(p, ids['beto'])
    ok(jb['entrega_mapa']['destino'] == {'lat': round(SP[0], 5), 'lng': round(SP[1], 5)} and jb['entrega_mapa']['pode_destino'], 'o comprador vê o próprio ponto de entrega e pode mudá-lo')
    ok(jb['entrega_mapa']['loja'] == {'lat': LOJA[0], 'lng': LOJA[1], 'aprox': False}, 'o mapa do pedido leva o ponto da loja')
    ok(not jb['entrega_mapa']['pode_designar'] and not jb['entrega_mapa']['pode_sair'], 'antes do pagamento confirmado ninguém designa nem sai')
    # retirada e produto digital não têm entrega acompanhada
    rec = emitir(duda, 'bazar_pedir', {'produto_id': PROD_DIG, 'quantidade': 1, 'entrega': 'digital'})
    pid_dig = next(m['args'][0]['pedido_id'] for m in rec if m['name'] == 'bazar_pedido_aberto')
    ok('entrega_mapa' not in bazar.pedido_json(pedido(pid_dig), ids['duda']), 'pedido sem envio não tem bloco de entrega no mapa')
    rec = emitir(duda, 'entrega_designar', {'pedido_id': pid_dig, 'quem': 'eu'})
    ok(erro(rec) is not None, 'designar entregador em pedido que não é de envio é recusado')

    # ---------- 3. antes de confirmar o pagamento a entrega não começa ----------
    rec = emitir(ana, 'entrega_designar', {'pedido_id': pid, 'quem': 'eu'})
    ok(erro(rec) and 'pagamento' in erro(rec).lower(), 'designar antes do pagamento confirmado é recusado')
    emitir(ana, 'bazar_agir', {'pedido_id': pid, 'acao': 'aceitar'})
    emitir(beto, 'bazar_agir', {'pedido_id': pid, 'acao': 'paguei'})
    emitir(ana, 'bazar_agir', {'pedido_id': pid, 'acao': 'confirmar'})
    ok(pedido(pid).status == 'confirmado', 'pedido chegou em "pagamento confirmado"')
    ev(beto); ev(ana)

    # ---------- 4. cadastro do entregador (aceite explícito) ----------
    rec = emitir(cris, 'entregador_cadastrar', {'ativo': True})
    ok(erro(rec) and 'entendeu' in erro(rec), 'virar entregador exige o aceite explícito')
    rec = emitir(cris, 'entregador_cadastrar', {'ativo': True, 'consentimento': True})
    est = next((m['args'][0] for m in rec if m['name'] == 'entregador_estado'), None)
    ok(est and est['cadastro']['ativo'] is True, 'com o aceite, a pessoa vira entregadora e recebe o painel')
    ok(any(m['name'] == 'entregador_estado' for m in ev(cris2)), 'a outra aba do entregador também recebe o painel (regra 6)')

    # ---------- 5. designar ----------
    rec = emitir(beto, 'entrega_designar', {'pedido_id': pid, 'quem': 'eu'})
    ok(erro(rec) is not None and pedido(pid).entregador_id is None, 'o comprador não designa entregador')
    rec = emitir(duda, 'entrega_designar', {'pedido_id': pid, 'quem': 'eu'})
    ok(erro(rec) is not None and pedido(pid).entregador_id is None, 'um estranho não designa entregador')
    rec = emitir(ana, 'entrega_designar', {'pedido_id': pid, 'quem': 'outro', 'alvo': '@eva'})
    ok(erro(rec) and 'cadastrada' in erro(rec), 'quem não se cadastrou como entregador não pode ser chamado')
    rec = emitir(ana, 'entrega_designar', {'pedido_id': pid, 'quem': 'outro', 'alvo': '@beto'})
    ok(erro(rec) is not None, 'o comprador não entrega o próprio pedido')
    emitir(fabio, 'entregador_cadastrar', {'ativo': True, 'consentimento': True})
    rec = emitir(ana, 'entrega_designar', {'pedido_id': pid, 'quem': 'outro', 'alvo': '@fabio'})
    ok(erro(rec) and 'não dá pra chamar' in erro(rec).lower(), 'quem tem bloqueio com o comprador não é chamado')
    ev(cris); ev(cris2)
    rec = emitir(ana, 'entrega_designar', {'pedido_id': pid, 'quem': 'outro', 'alvo': '@cris', 'transporte': 'moto'})
    p = pedido(pid)
    ok(p.entregador_id == ids['cris'] and p.entrega_estado == 'convidado' and p.status == 'confirmado', 'o convite fica "convidado" e o pedido segue confirmado')
    ok(any(m['name'] == 'entregador_estado' for m in ev(cris)) and any(m['name'] == 'entregador_estado' for m in ev(cris2)), 'o convite chega ao painel do entregador em todas as abas')
    ok(Notificacao.query.filter_by(person_id=ids['cris'], tipo='bazar').count() >= 1, 'o entregador recebe aviso na caixa de entrada')
    pj = entregas.entrega_json(p, ids['cris'])
    ok('endereco' not in pj and 'destino' not in pj and 'comprador' not in pj, 'ANTES de aceitar o entregador não vê endereço, ponto nem nome do comprador')
    ok(pj['produto_nome'] == 'Pastel de queijo' and 'total_cent' not in pj and 'pix' not in str(pj).lower(), 'o entregador não vê preço nem Pix')
    rec = emitir(cris, 'entrega_sair', {'pedido_id': pid, 'consentimento': True})
    ok(erro(rec) is not None and pedido(pid).status == 'confirmado', 'não dá pra sair sem ter aceitado o convite')
    rec = emitir(duda, 'entrega_responder', {'pedido_id': pid, 'aceitar': True})
    ok(erro(rec) is not None and pedido(pid).entrega_estado == 'convidado', 'um terceiro não aceita o convite dos outros')
    rec = emitir(cris, 'entrega_responder', {'pedido_id': pid, 'aceitar': False})
    ok(pedido(pid).entrega_estado == 'recusada', 'recusar o convite deixa o vendedor escolher de novo')
    ok(erro(emitir(cris, 'entrega_responder', {'pedido_id': pid, 'aceitar': True})) is not None, 'convite recusado não volta a valer')
    emitir(ana, 'entrega_designar', {'pedido_id': pid, 'quem': 'outro', 'alvo': '@cris', 'transporte': 'moto'})
    emitir(cris, 'entrega_responder', {'pedido_id': pid, 'aceitar': True})
    ok(pedido(pid).entrega_estado == 'aceita', 'aceitar o convite deixa a entrega pronta pra sair')
    pj = entregas.entrega_json(pedido(pid), ids['cris'])
    ok(pj['endereco'].startswith('Rua Augusta') and pj['destino']['lat'] == round(SP[0], 5) and pj['comprador']['nome'] == 'Beto', 'DEPOIS de aceitar ele vê o endereço, o ponto e quem recebe')
    ok(any(m['name'] == 'bazar_pedido' for m in ev(beto)) and any(m['name'] == 'bazar_pedido' for m in ev(ana)), 'comprador e vendedor recebem o pedido atualizado (regra 6)')

    # ---------- 6. sair: consentimento, posição do aparelho, só as pontas veem ----------
    rec = emitir(cris, 'entrega_sair', {'pedido_id': pid})
    ok(erro(rec) and 'entendeu' in erro(rec) and pedido(pid).status == 'confirmado', 'sair sem confirmar o aviso de compartilhamento é recusado')
    rec = emitir(cris, 'entrega_sair', {'pedido_id': pid, 'consentimento': True})
    ok(erro(rec) and 'localização do seu aparelho' in erro(rec) and pedido(pid).status == 'confirmado', 'sair sem posição do aparelho é recusado')
    pos(cris, LOJA[0], LOJA[1], fonte='ip')
    ok(erro(emitir(cris, 'entrega_sair', {'pedido_id': pid, 'consentimento': True})) is not None, 'posição só por IP não serve pra sair para entrega')
    pos(cris, LOJA[0], LOJA[1])
    for u in (ana, beto, duda, eva, cris2):
        ev(u)
    ev(cris)
    ok(not entregas.esta_compartilhando(ids['cris']), 'antes de sair ninguém compartilha posição')
    cris.emit('atualizar_localizacao', anda(*LOJA, passo=0.001))
    ok(all(not [m for m in ev(u) if m['name'] == 'entrega_ao_vivo'] for u in (ana, beto, duda, eva)), 'antes de sair, nenhuma posição do entregador é repassada')
    bazar_events._ultimo.clear()
    cris.emit('entrega_sair', {'pedido_id': pid, 'consentimento': True, 'transporte': 'moto'})
    recc = ev(cris)
    p = pedido(pid)
    ok(p.status == 'a_caminho' and p.entrega_estado == 'a_caminho' and p.saida_em is not None, 'sair leva o pedido a "a caminho"')
    ok(entregas.esta_compartilhando(ids['cris']) and pid in entregas._ativas, 'o servidor passa a repassar a posição do entregador (em memória)')
    vivos_b = [m['args'][0] for m in ev(beto) if m['name'] == 'entrega_ao_vivo']
    vivos_a = [m['args'][0] for m in ev(ana) if m['name'] == 'entrega_ao_vivo']
    vivos_c = [m['args'][0] for m in recc if m['name'] == 'entrega_ao_vivo']
    ok(len(vivos_b) == 1 and len(vivos_a) == 1 and len(vivos_c) == 1, 'a primeira posição sai na hora pro comprador, o vendedor e o entregador')
    ok(vivos_b and vivos_b[0]['dist_m'] > 0 and vivos_b[0]['eta_s'] > 60, 'a posição já vem com distância e tempo estimado até o destino')
    ok(not [m for m in ev(duda) if m['name'] in ('entrega_ao_vivo', 'bazar_pedido')] and not [m for m in ev(eva) if m['name'] == 'entrega_ao_vivo'], 'estranhos não recebem NADA da entrega')
    nots = Notificacao.query.filter_by(person_id=ids['beto'], tipo='bazar').all()
    ok(any('Saiu para entrega' in n.titulo for n in nots), 'o comprador é avisado na caixa de entrada que saiu para entrega')
    jb = bazar.pedido_json(pedido(pid), ids['beto'])
    ok(jb['status'] == 'a_caminho' and jb['rotulo'] == 'A caminho' and jb['entrega_mapa']['ultima']['eta_s'] > 0, 'o pedido do comprador já abre com a última posição (o mapa não nasce vazio)')
    ok(jb['entrega_mapa']['entregador']['nome'] == 'Cris' and jb['entrega_mapa']['transporte'] == 'moto', 'o comprador sabe quem entrega e de que jeito')

    # ---------- 7. posições seguintes ----------
    ev(ana); ev(beto); ev(duda)
    pos(cris, SP[0] - 0.005, SP[1] - 0.005)
    v1 = [m['args'][0] for m in ev(beto) if m['name'] == 'entrega_ao_vivo']
    ok(len(v1) == 1 and v1[0]['dist_m'] < vivos_b[0]['dist_m'], 'andando em direção ao destino a distância e o tempo diminuem')
    cris.emit('atualizar_localizacao', anda(SP[0], SP[1], -0.004))
    ok(not [m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'o servidor não repassa mais de uma posição a cada 2 s por entrega')
    entregas_rele_zero()
    ev(duda)
    recip = pos(cris, SP[0] - 0.003, SP[1] - 0.003, fonte='ip')
    ok(not [m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'posição por IP não é repassada pro comprador')
    sinais = [m for m in recip if m['name'] == 'entrega_sinal']
    ok(sinais and sinais[0]['args'][0]['ok'] is False, 'o entregador é avisado de que está sem GPS do aparelho')
    # salto impossível (teletransporte) = suspeita
    pos(cris, -3.1, -60.0)
    ok(not [m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'salto impossível de posição (suspeita) não é repassado')
    events.suspeitos_ate.pop(ids['cris'], None); events.ultimo_fix.pop(ids['cris'], None)
    entregas_rele_zero()
    pos(cris, SP[0] - 0.002, SP[1] - 0.002)
    ok([m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'passada a suspeita, a posição volta a ser repassada')

    # ---------- 8. Modo Fantasma ----------
    db.session.add(Friendship(requester_id=ids['cris'], addressee_id=ids['gil'], status='accepted')); db.session.commit()
    getattr(events, '_cache_contatos', {}).clear()
    amigo_de_cris = cliente('gil'); ev(amigo_de_cris)
    cris_u = db.session.get(Person, ids['cris']); cris_u.ghost_mode = True; db.session.commit()
    ev(beto); ev(ana)
    pos(cris, SP[0] - 0.0015, SP[1] - 0.0015)
    ok([m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'com o Fantasma ligado a posição ainda chega às duas pontas (o consentimento é por entrega)')
    ok(ids['cris'] not in events.ultimas_posicoes, 'mas o Fantasma continua escondendo a pessoa do radar')
    ok(not [m for m in ev(amigo_de_cris) if m['name'] == 'posicao_amigo_atualizada'], 'e nenhum amigo ou colega vê pino dela')
    cris_u.ghost_mode = False; db.session.commit()

    # ---------- 9. Localização desligada corta tudo ----------
    cris_u = db.session.get(Person, ids['cris']); cris_u.localizacao_ativa = False; db.session.commit()
    ev(beto)
    pos(cris, SP[0] - 0.001, SP[1] - 0.001)
    ok(not [m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'com a localização do app desligada nada é repassado')
    cris_u.localizacao_ativa = None; db.session.commit()

    # ---------- 10. durante a entrega ----------
    rec = emitir(beto, 'bazar_agir', {'pedido_id': pid, 'acao': 'cancelar'})
    ok(erro(rec) is not None and pedido(pid).status == 'a_caminho', 'não se cancela um pedido que já saiu para entrega')
    rec = emitir(ana, 'entrega_designar', {'pedido_id': pid, 'quem': 'eu'})
    ok(erro(rec) is not None and pedido(pid).entregador_id == ids['cris'], 'o vendedor não troca o entregador no meio da rota')
    rec = emitir(ana, 'entrega_parar', {'pedido_id': pid})
    ok(erro(rec) is not None and pedido(pid).status == 'a_caminho', 'só o entregador para o compartilhamento (o vendedor não)')
    rec = emitir(duda, 'entrega_entregue', {'pedido_id': pid})
    ok(erro(rec) is not None and pedido(pid).status == 'a_caminho', 'estranho não marca como entregue')
    # mudar o ponto de entrega no meio do caminho vale na hora
    pos(beto, SP[0] + 0.01, SP[1])
    ev(cris); ev(beto)
    emitir(beto, 'entrega_destino', {'pedido_id': pid})
    ok(abs(pedido(pid).destino_lat - round(SP[0] + 0.01, 5)) < 1e-6 and abs(entregas._ativas[pid]['dest'][0] - round(SP[0] + 0.01, 5)) < 1e-6, 'o comprador muda o ponto no meio do caminho e o tempo passa a contar pro novo')
    emitir(duda, 'entrega_destino', {'pedido_id': pid})
    ok(abs(pedido(pid).destino_lat - round(SP[0] + 0.01, 5)) < 1e-6, 'estranho não muda o ponto de entrega')
    # parar = revogar o compartilhamento
    ev(ana); ev(beto)
    rec = emitir(cris, 'entrega_parar', {'pedido_id': pid})
    p = pedido(pid)
    ok(p.status == 'confirmado' and p.entrega_estado == 'aceita' and p.saida_em is None, 'parar de compartilhar devolve o pedido a "confirmado" com a entrega aceita')
    ok(pid not in entregas._ativas and not entregas.esta_compartilhando(ids['cris']), 'e o servidor para de repassar na hora')
    ev(beto)
    pos(cris, SP[0] - 0.001, SP[1])
    ok(not [m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'depois de parar nenhuma posição chega às pontas')
    # sai de novo e entrega
    emitir(cris, 'entrega_sair', {'pedido_id': pid, 'consentimento': True, 'transporte': 'bicicleta'})
    ok(pedido(pid).status == 'a_caminho' and pedido(pid).transporte == 'bicicleta', 'pode sair de novo, agora de bicicleta')
    ev(beto); ev(ana)
    emitir(cris, 'entrega_entregue', {'pedido_id': pid})
    p = pedido(pid)
    ok(p.status == 'entregue' and p.entrega_estado == 'entregue' and p.entregue_em is not None, 'marcar entregue leva o pedido a "entregue"')
    ok(pid not in entregas._ativas, 'entregue encerra o compartilhamento')
    ok(db.session.get(BazarEntregador, ids['cris']).entregas == 1, 'o entregador soma uma entrega')
    ok(any(m['name'] == 'bazar_pedido' for m in ev(beto)) and any(m['name'] == 'bazar_pedido' for m in ev(ana)), 'as duas pontas veem "entregue" (regra 6)')
    ev(beto)
    pos(cris, SP[0], SP[1])
    ok(not [m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'entregue: a posição não é mais repassada')
    jb = bazar.pedido_json(pedido(pid), ids['beto'])
    ok(jb['entrega_mapa']['ultima'] is None and jb['status'] == 'entregue', 'o pedido entregue não carrega posição')
    rec = emitir(beto, 'bazar_agir', {'pedido_id': pid, 'acao': 'recebi'})
    p = pedido(pid)
    ok(p.status == 'concluido', 'o comprador confirma o recebimento e o pedido conclui')
    ok(p.destino_lat is None and p.destino_lng is None and p.endereco is None, 'ao concluir o ponto de entrega e o endereço são apagados')
    ok('destino' not in entregas.entrega_json(p, ids['cris']) and bazar.pedido_json(p, ids['beto'])['entrega_mapa']['destino'] is None, 'e nenhuma ponta (nem o entregador) vê mais o destino')
    ok(bazar.contar_pendencias(ids['beto']) == 0, 'sem pendência sobrando')

    # ---------- 11. a própria loja entrega; o comprador confirma com o entregador ainda a caminho ----------
    pos(beto, SP[0], SP[1])
    rec = emitir(beto, 'bazar_pedir', dados_pedido)
    pid2 = next(m['args'][0]['pedido_id'] for m in rec if m['name'] == 'bazar_pedido_aberto')
    emitir(ana, 'bazar_agir', {'pedido_id': pid2, 'acao': 'aceitar'}); emitir(beto, 'bazar_agir', {'pedido_id': pid2, 'acao': 'paguei'}); emitir(ana, 'bazar_agir', {'pedido_id': pid2, 'acao': 'confirmar'})
    pos(ana, LOJA[0], LOJA[1])
    rec = emitir(ana, 'entrega_designar', {'pedido_id': pid2, 'quem': 'eu', 'transporte': 'carro'})
    ok(pedido(pid2).entregador_id == ids['ana'] and pedido(pid2).entrega_estado == 'aceita', 'a própria loja pode entregar (fica aceita na hora)')
    ok(bazar.pedido_json(pedido(pid2), ids['ana'])['entrega_mapa']['pode_sair'], 'o vendedor-entregador vê o botão de sair')
    ev(beto); ev(ana)
    recana = emitir(ana, 'entrega_sair', {'pedido_id': pid2, 'consentimento': True})
    ok(pedido(pid2).status == 'a_caminho' and entregas.esta_compartilhando(ids['ana']), 'a loja sai para entrega')
    ok([m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'] and [m for m in recana if m['name'] == 'entrega_ao_vivo'], 'o comprador e a loja acompanham juntos')
    rec = emitir(beto, 'bazar_agir', {'pedido_id': pid2, 'acao': 'recebi'})
    ok(pedido(pid2).status == 'concluido' and pid2 not in entregas._ativas, 'o comprador pode confirmar o recebimento com o entregador ainda a caminho: a entrega acaba junto')
    ev(beto)
    pos(ana, LOJA[0] + 0.001, LOJA[1])
    ok(not [m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'concluído: acabou o compartilhamento')

    # ---------- 12. disputa trava a entrega ----------
    pos(beto, SP[0], SP[1])
    rec = emitir(beto, 'bazar_pedir', dados_pedido)
    pid3 = next(m['args'][0]['pedido_id'] for m in rec if m['name'] == 'bazar_pedido_aberto')
    emitir(ana, 'bazar_agir', {'pedido_id': pid3, 'acao': 'aceitar'}); emitir(beto, 'bazar_agir', {'pedido_id': pid3, 'acao': 'paguei'}); emitir(ana, 'bazar_agir', {'pedido_id': pid3, 'acao': 'confirmar'})
    emitir(ana, 'entrega_designar', {'pedido_id': pid3, 'quem': 'eu'})
    db.session.add(BazarDisputa(pedido_id=pid3, aberta_por_id=ids['beto'], motivo='outro', detalhe='teste de disputa aberta', status='aberta'))
    db.session.commit()
    rec = emitir(ana, 'entrega_sair', {'pedido_id': pid3, 'consentimento': True})
    ok(erro(rec) and 'disputa' in erro(rec).lower() and pedido(pid3).status == 'confirmado', 'com disputa aberta a entrega não sai')
    BazarDisputa.query.filter_by(pedido_id=pid3).update({'status': 'resolvida'}); db.session.commit()

    # ---------- 13. a entrega esquecida aberta acaba sozinha ----------
    emitir(ana, 'entrega_sair', {'pedido_id': pid3, 'consentimento': True})
    ok(pedido(pid3).status == 'a_caminho', 'saiu de novo depois da disputa')
    entregas._ativas[pid3]['inicio'] = time.time() - entregas.MAX_SEGUNDOS - 5
    ev(beto)
    pos(ana, LOJA[0] + 0.002, LOJA[1])
    p = pedido(pid3)
    ok(p.status == 'confirmado' and p.entrega_estado == 'aceita' and pid3 not in entregas._ativas, 'passou de 4 h a caminho: o compartilhamento acaba sozinho e o pedido volta a "confirmado"')
    ok(any(m['name'] == 'bazar_pedido' for m in ev(beto)), 'o comprador é avisado')

    # ---------- 14. o servidor reiniciou no meio da entrega ----------
    emitir(ana, 'entrega_sair', {'pedido_id': pid3, 'consentimento': True})
    entregas._ativas.clear(); entregas._por_entregador.clear()          # simula o reinício
    ev(beto)
    pos(ana, LOJA[0] + 0.003, LOJA[1])
    ok(not [m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'sem registro em memória nada é repassado (privacidade por padrão)')
    rec = emitir(duda, 'entrega_retomar', {'pedido_id': pid3})
    ok(erro(rec) is not None and not entregas.esta_compartilhando(ids['duda']), 'estranho não retoma a entrega dos outros')
    emitir(ana, 'entrega_retomar', {'pedido_id': pid3})
    pos(ana, LOJA[0] + 0.004, LOJA[1])
    ok([m for m in ev(beto) if m['name'] == 'entrega_ao_vivo'], 'o entregador retoma e a posição volta a chegar')
    emitir(ana, 'entrega_entregue', {'pedido_id': pid3})
    emitir(beto, 'bazar_agir', {'pedido_id': pid3, 'acao': 'recebi'})

    # ---------- 15. cancelar o cadastro derruba convites ----------
    pos(beto, SP[0], SP[1])
    rec = emitir(beto, 'bazar_pedir', dados_pedido)
    pid4 = next(m['args'][0]['pedido_id'] for m in rec if m['name'] == 'bazar_pedido_aberto')
    emitir(ana, 'bazar_agir', {'pedido_id': pid4, 'acao': 'aceitar'}); emitir(beto, 'bazar_agir', {'pedido_id': pid4, 'acao': 'paguei'}); emitir(ana, 'bazar_agir', {'pedido_id': pid4, 'acao': 'confirmar'})
    emitir(ana, 'entrega_designar', {'pedido_id': pid4, 'quem': 'outro', 'alvo': str(ids['cris'])})
    ok(pedido(pid4).entrega_estado == 'convidado', 'dá pra chamar o entregador pelo id também')
    emitir(cris, 'entregador_cadastrar', {'ativo': False})
    ok(pedido(pid4).entrega_estado == 'recusada', 'quem deixa de ser entregador derruba os convites abertos')
    ok(erro(emitir(ana, 'entrega_designar', {'pedido_id': pid4, 'quem': 'outro', 'alvo': '@cris'})) is not None, 'e não pode ser chamado de novo')
    # pedido cancelado por admin/banimento no meio: a memória é limpa
    emitir(cris, 'entregador_cadastrar', {'ativo': True, 'consentimento': True})
    emitir(ana, 'entrega_designar', {'pedido_id': pid4, 'quem': 'outro', 'alvo': '@cris'}); emitir(cris, 'entrega_responder', {'pedido_id': pid4, 'aceitar': True})
    pos(cris, LOJA[0], LOJA[1])
    emitir(cris, 'entrega_sair', {'pedido_id': pid4, 'consentimento': True})
    ok(pid4 in entregas._ativas, 'a quarta entrega está a caminho')
    from sqlalchemy import update as _upd
    db.session.execute(_upd(BazarPedido).where(BazarPedido.id == pid4).values(status='cancelado')); db.session.commit()
    bazar._efeitos_do_fim(pedido(pid4), 'cancelado'); db.session.commit()
    ok(pid4 not in entregas._ativas and pedido(pid4).destino_lat is None, 'quando o pedido termina por qualquer caminho (admin, banimento) o compartilhamento é encerrado')

    # ---------- 16. custo: posição de quem não entrega não faz consulta nova ----------
    consultas = []
    ouvinte = lambda conn, cur, stmt, params, ctx, many: consultas.append(stmt)
    event.listen(db.engine, 'before_cursor_execute', ouvinte)
    duda.emit('atualizar_localizacao', anda(-23.0, -46.0))                       # esquenta (primeira vez cria o registro do fix)
    consultas.clear(); duda.emit('atualizar_localizacao', anda(-23.0, -46.0, 0.0001)); base = len(consultas)
    consultas.clear(); duda.emit('atualizar_localizacao', anda(-23.0, -46.0, 0.0002)); outra = len(consultas)
    event.remove(db.engine, 'before_cursor_execute', ouvinte)
    ok(base == outra and entregas.repassar(ids['duda'], (0, 0), 'aparelho') == ([], [], []), f'quem não entrega paga o mesmo número de consultas de sempre ({base}) e o gancho não faz nenhuma')

    # ---------- 17. o que o cliente promete ----------
    js, css, bz, ch = ler('app/static/js/entrega_mapa.js'), ler('app/static/css/entrega_mapa.css'), ler('app/static/js/bazar.js'), ler('app/templates/chat.html')
    ok('entrega_mapa.js' in ch and 'entrega_mapa.css' in ch, 'o chat.html carrega o módulo e o estilo da entrega')
    for nome in ('entrega_ao_vivo', 'entrega_sinal', 'entregador_estado'):
        ok(f"socket.on('{nome}'" in ch, f'o chat.html escuta {nome}')
    ok('Entrega.iniciar' in ch and 'anunciarMinhaPosicao' in ch, 'o chat.html entrega ao módulo a função que reanuncia a posição')
    for ev_nome in ('entrega_designar', 'entrega_responder', 'entrega_sair', 'entrega_parar', 'entrega_entregue', 'entrega_retomar', 'entrega_destino', 'entregador_cadastrar', 'entregador_meu_estado'):
        ok(ev_nome in js, f'o módulo emite {ev_nome}')
    ok('Entrega.' in bz and 'a_caminho' in bz, 'o Bazar usa o módulo e conhece os estados novos')
    ok(all(t in js for t in ('esc(e.produto_nome)', 'esc(e.endereco)', 'esc(e.loja_nome)', 'pessoa(e.comprador)', 'pessoa(ent)')) and 'ctx.esc' in js, 'o módulo escapa nome, endereço e loja que vêm do servidor')
    ok('prefers-reduced-motion' in css, 'o CSS respeita reduzir movimento')
    ok('tile.openstreetmap.org' in js and 'L.map(' in js, 'o mini mapa usa Leaflet com o mesmo mapa base')
    ok('invalidateSize' in js and 'destruir' in js, 'o mini mapa se ajusta e é destruído ao fechar (sem vazar mapa)')
    ok(js.count('consentimento') >= 2, 'os dois consentimentos (virar entregador e sair para entrega) passam pelo aceite explícito')

print()
print('FALHAS:', len(falhas))
for f in falhas:
    print('  -', f)
sys.exit(1 if falhas else 0)
