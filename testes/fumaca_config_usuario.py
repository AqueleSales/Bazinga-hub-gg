"""Configurações do usuário (Rodada 34): preferências da conta (lista fechada, só o que difere do padrão, todas as abas acompanham, nada vira HTML sem validar),
notificações por tipo (o servidor não cria a entrada nem manda push), histórico de Cobrança (só da própria pessoa, sem o código do Pix), cópia dos dados (LGPD),
resumo de privacidade, Brasa (o plano pago renomeado), e o que o chat.html promete (grupos, busca, sub-abas, ganchos de som/hora/volume)."""
import json, os, re, sys
from datetime import timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
for k in ('RENDER', 'PAGAMENTOS', 'ASAAS_API_KEY', 'OLIMPO_GRATIS', 'OLIMPO_PRECO_CENT', 'EXIGIR_TERMOS'):
    os.environ.pop(k, None)
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app import create_app, db, socketio
from app import preferencias, olimpo, config_usuario, config_usuario_events, pagamentos
from app.cosmeticos import CATALOGO, BADGE_OLIMPO
from app.models import (Role, Person, Friendship, Notificacao, Cobranca, MovimentoDrc, BazarLoja, BazarProduto, BazarPedido, Message, Channel, Server, br_now)

app = create_app()
falhas = []
consultas = []


@event.listens_for(Engine, 'before_cursor_execute')
def _conta(conn, cursor, statement, params, context, executemany):
    consultas.append(statement)


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cl, nome=None):
    return [m for m in cl.get_received() if nome is None or m['name'] == nome]


RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
leia = lambda *p: open(os.path.join(RAIZ, *p), encoding='utf-8').read()

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('Ana', 'Beto', 'Caio'):
        p = Person(name=nome, email=f'{nome.lower()}@x.com', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=30), bazinga_coins=300)
        db.session.add(p); db.session.commit(); ids[nome.lower()] = p.id
    db.session.add(Friendship(requester_id=ids['ana'], addressee_id=ids['beto'], status='accepted')); db.session.commit()

    def pessoa(n):
        db.session.expire_all()
        return db.session.get(Person, ids[n])

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    ana, fana = cliente('ana'); ana2, _ = cliente('ana'); beto, fbeto = cliente('beto'); caio, fcaio = cliente('caio')

    # ---------------- 1. preferencias.py: lista fechada ----------------
    ok(preferencias.normalizar({'texto': 'g', 'densidade': 'ampla', 'sublinhar': True, 'n_dm': False}) == {'texto': 'g', 'densidade': 'ampla', 'sublinhar': True, 'n_dm': False}, 'valores válidos passam')
    ok(preferencias.normalizar({'texto': 'enorme', 'densidade': '<x>', 'sublinhar': 'true', 'reduz_mov': 1, 'hora12': None, 'n_dm': 'nao', 'inventada': True}) == {}, 'valor fora da lista, bool que não é bool e chave inventada são descartados')
    ok(preferencias.normalizar(['texto']) == {} and preferencias.normalizar('texto') == {} and preferencias.normalizar(None) == {}, 'entrada que não é objeto vira vazio')
    ok(set(preferencias.PADRAO) == {'texto', 'densidade', 'sublinhar', 'reduz_mov', 'hora12'} | {'n_' + t for t in preferencias.IDS_AVISO}, 'os campos são exatamente os esperados')
    ok(all(preferencias.PADRAO['n_' + t] is True for t in preferencias.IDS_AVISO), 'todos os avisos nascem ligados')
    ok('sistema' not in preferencias.IDS_AVISO and preferencias.aviso_ligado(ids['ana'], 'sistema'), 'aviso de sistema não entra na lista e nunca é desligado')

    p = pessoa('ana')
    ok(p.preferencias is None and preferencias.da_pessoa(p) == preferencias.PADRAO, 'quem nunca mexeu tem a coluna vazia e o padrão')
    novo = preferencias.aplicar(p, {'texto': 'gg', 'hora12': True}); db.session.commit()
    ok(json.loads(pessoa('ana').preferencias) == {'texto': 'gg', 'hora12': True}, 'a coluna só guarda o que difere do padrão')
    preferencias.aplicar(pessoa('ana'), {'texto': 'm', 'hora12': False}); db.session.commit()
    ok(pessoa('ana').preferencias is None, 'voltar ao padrão esvazia a coluna')
    pessoa('ana').preferencias = '{quebrado'; db.session.commit()
    ok(preferencias.da_pessoa(pessoa('ana')) == preferencias.PADRAO, 'JSON quebrado na coluna vira o padrão (nunca derruba)')
    pessoa('ana').preferencias = json.dumps({'texto': '"><script>alert(1)</script>', 'densidade': 'ampla'}); db.session.commit()
    ok(preferencias.da_pessoa(pessoa('ana'))['texto'] == 'm' and preferencias.da_pessoa(pessoa('ana'))['densidade'] == 'ampla', 'valor malicioso gravado na mão é descartado na leitura')
    html = fana.get('/chat').get_data(as_text=True)
    ok('<script>alert(1)</script>' not in html.split('</head>')[0] and 'data-texto="m"' in html and 'data-densidade="ampla"' in html, 'o <html> nasce com os atributos certos e o valor malicioso nunca chega ao HTML')
    pessoa('ana').preferencias = None; db.session.commit(); preferencias.esquecer(ids['ana'])

    # ---------------- 2. evento salvar_preferencias ----------------
    ana.get_received(); ana2.get_received(); beto.get_received()
    ana.emit('salvar_preferencias', {'texto': 'g', 'densidade': 'compacta', 'sublinhar': True, 'reduz_mov': True, 'hora12': True, 'n_dm': False, 'inventada': 'x', 'texto2': 1})
    rec_a, rec_a2, rec_b = ev(ana, 'preferencias_carregadas'), ev(ana2, 'preferencias_carregadas'), ev(beto, 'preferencias_carregadas')
    ok(rec_a and rec_a[0]['args'][0]['prefs']['texto'] == 'g' and rec_a[0]['args'][0]['prefs']['n_dm'] is False, 'salvar devolve o conjunto COMPLETO já validado')
    ok(rec_a2 and rec_a2[0]['args'][0]['prefs']['hora12'] is True, 'a OUTRA aba da mesma pessoa acompanha na hora (regra 6)')
    ok(not rec_b, 'outra pessoa não recebe nada')
    ok(json.loads(pessoa('ana').preferencias) == {'texto': 'g', 'densidade': 'compacta', 'sublinhar': True, 'reduz_mov': True, 'hora12': True, 'n_dm': False}, 'ficou na conta (e a chave inventada não)')
    ana.emit('salvar_preferencias', {'texto': 'enorme'}); ana.get_received()
    ok(pessoa('ana').preferencias and json.loads(pessoa('ana').preferencias)['texto'] == 'g', 'valor inválido é ignorado e não apaga o que já estava')
    ana.emit('salvar_preferencias', 'texto=g'); ana.emit('salvar_preferencias', ['a']); ana.emit('salvar_preferencias', None)
    ok(True, 'payload que não é objeto não derruba o servidor')
    ok(any(m['args'][0].get('prefs') for m in (lambda cl: (cl.emit('salvar_preferencias', {'texto': 'p'}), cl.get_received())[1])(ana2)) and json.loads(pessoa('ana').preferencias)['texto'] == 'p', 'qualquer aba da pessoa pode salvar')
    ana.get_received(); ana2.get_received()
    # valor inicial: o connect e o /chat já trazem as preferências (sem consulta nova)
    cn = socketio.test_client(app, flask_test_client=fana)
    conn_prefs = [m['args'][0] for m in cn.get_received() if m['name'] == 'preferencias_carregadas']
    ok(conn_prefs and conn_prefs[0].get('prefs', {}).get('texto') == 'p' and conn_prefs[0]['prefs']['sublinhar'] is True, 'no connect as preferências da conta chegam junto das outras')
    html = fana.get('/chat').get_data(as_text=True)
    ok('data-texto="p"' in html and 'data-densidade="compacta"' in html and ' data-sublinhar' in html and ' data-reduz-mov' in html and ' data-hora12' in html, '/chat já nasce com texto, densidade, sublinhar, movimento e hora12 (sem piscar)')
    anonimo = socketio.test_client(app)
    anonimo.emit('salvar_preferencias', {'texto': 'g'})
    ok(not anonimo.get_received(), 'sem login nada acontece')

    # ---------------- 3. notificações por tipo (servidor) ----------------
    import app.push as push
    enviados = []
    push.enviar_push = lambda destino_id, titulo, corpo, url='/chat', tag=None, extra=None: enviados.append((destino_id, titulo, (extra or {}).get('tipo'))) or True
    beto.get_received(); ana.get_received()
    beto.emit('visibilidade', {'visivel': False}); beto.get_received()

    ana.emit('enviar_mensagem_direta', {'target_id': ids['beto'], 'texto': 'oi beto, tudo bem?'}); ana.get_received(); beto.get_received()
    ok(Notificacao.query.filter_by(person_id=ids['beto'], tipo='dm').count() == 1 and any(e[0] == ids['beto'] for e in enviados), 'padrão: DM cria a entrada na caixa e manda push')
    Notificacao.query.delete(); db.session.commit(); enviados.clear()
    beto.emit('salvar_preferencias', {'n_dm': False}); beto.get_received()
    ana.emit('enviar_mensagem_direta', {'target_id': ids['beto'], 'texto': 'e agora, ainda recebe?'}); ana.get_received()
    rec_dm = ev(beto)
    ok(Notificacao.query.filter_by(person_id=ids['beto']).count() == 0, 'n_dm desligado: NÃO cria a entrada na caixa de entrada')
    ok(not enviados, '...nem manda push')
    ok(any(m['name'] == 'receber_mensagem_direta' for m in rec_dm), '...mas a mensagem continua chegando normalmente')
    ok(not any(m['name'] == 'notificacao_nova' for m in rec_dm), '...e a caixa de entrada não recebe aviso ao vivo')
    beto.emit('salvar_preferencias', {'n_dm': True}); beto.get_received()
    ana.emit('enviar_mensagem_direta', {'target_id': ids['beto'], 'texto': 'voltou?'}); ana.get_received(); beto.get_received()
    ok(Notificacao.query.filter_by(person_id=ids['beto'], tipo='dm').count() == 1, 'religar volta a notificar')

    # amizade: caio pede amizade a beto
    Notificacao.query.delete(); db.session.commit(); enviados.clear()
    beto.emit('salvar_preferencias', {'n_amizade': False}); beto.get_received()
    caio.emit('enviar_pedido_amizade', {'usuario_id': ids['beto']}); caio.get_received(); beto.get_received()
    ok(Notificacao.query.filter_by(person_id=ids['beto'], tipo='amizade').count() == 0, 'n_amizade desligado: pedido de amizade não vira entrada na caixa')
    ok(Friendship.query.filter_by(requester_id=ids['caio'], addressee_id=ids['beto'], status='pending').count() == 1, '...mas o pedido existe e aparece na tela de Amigos')

    # ligação: o push de "está te ligando" respeita n_ligacao
    ok(preferencias.aviso_ligado(ids['beto'], 'ligacao') and not preferencias.aviso_ligado(ids['beto'], 'amizade'), 'aviso_ligado lê a conta')
    enviados.clear()
    db.session.add(Friendship(requester_id=ids['ana'], addressee_id=ids['caio'], status='accepted')); db.session.commit()
    caio.emit('salvar_preferencias', {'n_ligacao': False}); caio.get_received()
    caio.emit('visibilidade', {'visivel': False})
    ana.emit('chamar_amigo', {'amigo_id': ids['caio'], 'tipo': 'voz'}); ana.get_received()
    ok(not any(e[0] == ids['caio'] for e in enviados), 'n_ligacao desligado: sem push de "está te ligando"')
    ok(any(m['name'] == 'chamada_recebida' for m in ev(caio)), 'a chamada em si continua tocando o cartão pra quem está com o app aberto')
    ana.emit('cancelar_chamada', {'para_id': ids['caio']}); ana.get_received()
    caio.emit('salvar_preferencias', {'n_ligacao': True}); caio.get_received(); enviados.clear()
    ana.emit('chamar_amigo', {'amigo_id': ids['caio'], 'tipo': 'voz'}); ana.get_received()
    ok(any(e[0] == ids['caio'] for e in enviados), 'religado: o push volta')
    ana.emit('cancelar_chamada', {'para_id': ids['caio']}); ana.get_received()

    # cache: quem está online não custa consulta; o cache vale pro offline até expirar e é refeito do banco
    preferencias.guardar_no_cache(pessoa('beto'))
    consultas.clear()
    for _ in range(20):
        preferencias.aviso_ligado(ids['beto'], 'dm')
    ok(not [q for q in consultas if 'FROM person' in q], 'aviso_ligado com o cache quente não faz nenhuma consulta')
    preferencias._CACHE.clear()
    db.session.expire_all()
    ok(preferencias.aviso_ligado(ids['beto'], 'amizade') is False and preferencias.aviso_ligado(ids['beto'], 'dm') is True, 'cache frio (reinício do servidor): lê da conta e acerta')

    # ---------------- 4. Cobrança: só da própria pessoa, sem o código do Pix ----------------
    lojaB = BazarLoja(owner_id=ids['beto'], nome='Doces do Beto', categoria='comida'); db.session.add(lojaB); db.session.commit()
    prod = BazarProduto(loja_id=lojaB.id, nome='Brigadeiro', preco_cent=450, estoque=10); db.session.add(prod); db.session.commit()
    ped = BazarPedido(produto_id=prod.id, loja_id=lojaB.id, comprador_id=ids['ana'], vendedor_id=ids['beto'], produto_nome='Caixa de Brigadeiros', quantidade=2,
                      preco_unit_cent=2500, total_cent=5000, status='confirmado', pagamento='app')
    db.session.add(ped); db.session.commit()
    db.session.add(Cobranca(provedor='simulado', ext_id='SIM-A', tipo='pedido', ref_id=ped.id, pessoa_id=ids['ana'], valor_cent=5000, status='paga', payload='PANTHEON-TESTE-SEGREDO-123',
                            criada_em=br_now() - timedelta(days=2), paga_em=br_now() - timedelta(days=2)))
    db.session.add(Cobranca(provedor='asaas', ext_id='ASAAS-B', tipo='olimpo', ref_id=ids['ana'], pessoa_id=ids['ana'], valor_cent=1990, status='aberta', payload='00020126-COPIA-E-COLA',
                            criada_em=br_now(), expira_em=br_now() - timedelta(hours=1)))
    db.session.add(Cobranca(provedor='asaas', ext_id='ASAAS-C', tipo='pedido', ref_id=ped.id + 999, pessoa_id=ids['caio'], valor_cent=777, status='paga', payload='X', criada_em=br_now()))
    for delta, motivo, ref in ((500, 'ajuste', None), (-350, 'compra', 'nome:neon'), (150, 'nivel', '4->5')):
        db.session.add(MovimentoDrc(person_id=ids['ana'], delta=delta, saldo_apos=300, motivo=motivo, ref=ref))
    db.session.add(MovimentoDrc(person_id=ids['caio'], delta=999, saldo_apos=999, motivo='ajuste'))
    db.session.commit()

    ana.get_received()
    ana.emit('cobranca_historico', {})
    h = [m['args'][0] for m in ev(ana, 'cobranca_historico')]
    ok(h and len(h[0]['drc']['itens']) == 3 and h[0]['drc']['ganho_total'] == 650 and h[0]['drc']['gasto_total'] == 350, 'Cobrança: movimentos de DRC e totais, só da Ana')
    ok(h and {x['titulo'] for x in h[0]['pix_pagos']} == {'Caixa de Brigadeiros ×2', f'Assinatura {olimpo.NOME}'}, 'Pix pagos: o pedido (com a quantidade) e a assinatura Brasa')
    st = {x['titulo']: x['status'] for x in h[0]['pix_pagos']}
    ok(st['Caixa de Brigadeiros ×2'] == 'paga' and st[f'Assinatura {olimpo.NOME}'] == 'expirada', 'cobrança aberta e vencida é mostrada como "expirada"')
    ok(h and h[0]['total_pago_cent'] == 0, 'valor de TESTE (provedor simulado) não entra no total pago de verdade')
    texto = json.dumps(h[0], ensure_ascii=False)
    ok('SEGREDO' not in texto and 'COPIA-E-COLA' not in texto and 'payload' not in texto and 'copia_cola' not in texto, 'o histórico NUNCA leva o código do Pix (copia e cola)')
    ok(h and not h[0]['pix_recebidos'], 'a Ana não vendeu nada: lista de recebidos vazia')
    ok('777' not in texto and 'ASAAS-C' not in texto, 'cobrança da Caio não aparece pra Ana')
    beto.get_received(); beto.emit('cobranca_historico', {})
    hb = [m['args'][0] for m in ev(beto, 'cobranca_historico')]
    ok(hb and len(hb[0]['pix_recebidos']) == 1 and hb[0]['pix_recebidos'][0]['titulo'] == 'Caixa de Brigadeiros ×2' and not hb[0]['pix_pagos'], 'o vendedor vê a venda paga pelo app (e nada do que não é dele)')
    ok(hb and hb[0]['drc']['ganho_total'] == 0 and 'SEGREDO' not in json.dumps(hb[0]), '...sem o DRC da Ana e sem o código do Pix do comprador')
    config_usuario_events._ultimo.clear()
    ana.get_received(); ana.emit('cobranca_historico', {'pessoa_id': ids['caio'], 'person_id': ids['caio']})
    h2 = [m['args'][0] for m in ev(ana, 'cobranca_historico')]
    ok(h2 and h2[0]['drc']['ganho_total'] == 650 and 'ASAAS-C' not in json.dumps(h2[0]), 'mandar o id de outra pessoa não muda nada (o id vem da sessão)')
    ok(olimpo.NOME == 'Brasa' and h[0]['brasa']['nome'] == 'Brasa', 'a assinatura aparece com o nome novo')
    anonimo.emit('cobranca_historico', {}); anonimo.emit('dados_privacidade', {})
    ok(not anonimo.get_received(), 'sem login o histórico não responde')

    # ---------------- 5. privacidade e cópia dos dados ----------------
    ana.get_received(); ana.emit('dados_privacidade', {})
    pv = [m['args'][0] for m in ev(ana, 'dados_privacidade')]
    ok(pv and pv[0]['termos_vigente'] and pv[0]['retencao_meses'] == 12 and 'guardiao_ligado' in pv[0] and 'termos_em_dia' in pv[0], 'resumo de privacidade: termos, retenção e Guardião')
    ok(fana.get('/api/meus-dados').status_code == 200, 'a cópia dos dados abre pra quem está logado')
    ok(app.test_client().get('/api/meus-dados').status_code == 401, '...e não abre sem login')
    import app.main.routes as rotas
    rotas._ultima_copia_de_dados.clear()
    srv = Server(name='Casa', owner_id=ids['ana']); db.session.add(srv); db.session.commit()
    canal = Channel(name='geral', server_id=srv.id, channel_type='text'); db.session.add(canal); db.session.commit()
    db.session.add(Message(text='SEGREDINHO-DA-ANA-NO-CANAL', person_id=ids['ana'], channel_id=canal.id)); db.session.commit()
    resp = fana.get('/api/meus-dados')
    corpo = resp.get_data(as_text=True)
    dados = json.loads(corpo)
    ok('attachment' in resp.headers.get('Content-Disposition', '') and 'no-store' in resp.headers.get('Cache-Control', ''), 'baixa como arquivo e não fica em cache')
    ok(dados['conta']['email'] == 'ana@x.com' and dados['conta']['usuario'] == 'ana', 'a cópia é da própria pessoa')
    ok('beto@x.com' not in corpo and 'caio@x.com' not in corpo, '...sem o e-mail de ninguém mais')
    ok('SEGREDINHO' not in corpo and 'SEGREDO' not in corpo and 'COPIA-E-COLA' not in corpo and 'payload' not in corpo, 'sem o texto das mensagens e sem o código do Pix')
    ok(dados['mensagens_enviadas']['em_canais'] == 1, 'só a CONTAGEM das mensagens vai na cópia')
    ok(all(k in dados for k in ('conta', 'preferencias', 'amigos', 'servidores', 'movimentos_drc', 'pedidos_do_bazar', 'cobrancas_pix', 'mensagens_enviadas', 'aviso')), 'tem as seções combinadas')
    ok(dados['preferencias']['texto'] == 'p' and len(dados['movimentos_drc']) == 3 and dados['amigos'][0]['usuario'] in ('beto', 'caio'), 'e o conteúdo bate com a conta')
    ok(fana.get('/api/meus-dados').status_code == 429, 'pedir de novo em seguida espera (1 a cada 20 s)')
    consultas.clear(); rotas._ultima_copia_de_dados.clear(); fana.get('/api/meus-dados')
    ok(len(consultas) < 40, f'a cópia dos dados faz poucas consultas ({len(consultas)})')

    # ---------------- 6. Brasa: o nome novo vale em todo texto, os ids internos ficam ----------------
    ok(CATALOGO[BADGE_OLIMPO]['nome'] == 'Brasa' and BADGE_OLIMPO == 'badge:olimpo', 'a insígnia se chama Brasa e o id interno segue olimpo')
    ok(olimpo.estado(pessoa('ana'))['nome'] == 'Brasa', 'o estado manda o nome Brasa')
    passe_js, olimpo_py, cosm_js, nov = leia('app', 'static', 'js', 'passe.js'), leia('app', 'olimpo.py'), leia('app', 'static', 'js', 'cosmeticos.js'), leia('app', 'novidades.py')
    fraseado = re.compile(r"(?<![A-Za-zÀ-ú_])(o|do|ao|no|seu|Ativar|ativar|renovar) Olimpo\b")
    ok(not fraseado.search(passe_js) and not fraseado.search(olimpo_py.split('"""', 2)[2]) and "nome: 'Olimpo'" not in cosm_js, 'nenhum texto pra pessoa chama o plano de Olimpo')
    ok('Brasa' in nov.split("'id': 35")[1].split("'id': 34")[0], 'a novidade antiga também foi renomeada')
    ok('abrirBrasa' in passe_js and 'estadoBrasa' in passe_js, 'o Passe expõe a janela da Brasa pras Configurações')

    # ---------------- 7. o que o chat.html e os arquivos prometem ----------------
    html = fana.get('/chat').get_data(as_text=True)
    abas = re.findall(r'<div class="set-tab[^"]*" data-target="(set-[a-z]+)">([^<]+)</div>', html)
    ok([a for a, _ in abas] == ['set-perfil', 'set-privacidade', 'set-notificacoes', 'set-inventario', 'set-cobranca', 'set-brasa', 'set-aparencia', 'set-acessibilidade',
                                 'set-voz', 'set-idioma', 'set-geral', 'set-conexoes'], 'o menu tem as abas, na ordem e nos grupos combinados')
    ok(all(f'id="{a}"' in html for a, _ in abas), 'toda aba tem a sua seção')
    for g in ('Configurações de usuário', 'Cobrança', 'Configurações do app', 'Apps'):
        ok(f'<div class="set-tab-header">{g}</div>' in html, f'grupo "{g}" no menu')
    ok('id="set-busca-campo"' in html and 'Buscar nas configurações' in html, 'campo de busca nas configurações')
    ok(('Apps conectados', 'set-conexoes') == (dict(abas)['set-conexoes'], 'set-conexoes') and '<h2 class="set-title">Apps conectados</h2>' in html, 'Conexões virou "Apps conectados"')
    ok('cx-aba-info' in html and html.count('cfg-detalhes') >= 3, 'a ajuda longa das Conexões ficou em caixinhas dobráveis')
    ok(all(f'data-sub="{s}"' in html for s in ('voz', 'avancado', 'sons', 'transmissao')), 'Voz e vídeo tem as 4 sub-abas')
    ok(all(i in html for i in ('id="modal-mic-select"', 'id="modal-speaker-select"', 'id="vol-saida"', 'id="som-vol"', 'id="tg-som-call"', 'id="tg-som-xp"', 'id="toggle-noise"', 'id="btn-modal-mic-test"')), 'os controles de Voz e vídeo existem')
    ok("getElementById('modal-mic-select').addEventListener('change'" in html and "getElementById('modal-speaker-select').addEventListener('change'" in html, 'os seletores de microfone e alto-falante agora fazem alguma coisa ao trocar')
    ok('ConfigUsuario.somPermitido(tipo)' in html and 'ConfigUsuario.volumeSons()' in html and "ConfigUsuario.avisa('dm')" in html, 'sons e avisos respeitam as preferências')
    ok(html.count('ConfigUsuario.horaFmt(') == 2 and 'a.volume = ConfigUsuario.volumeSaida()' in html, 'hora de 12/24 h nas mensagens e volume do áudio da call')
    ok(all(f"'{t}');" in html or f"'{t}')" in html for t in ('amizade', 'dm', 'mencao', 'ligacao')), 'cada aviso do navegador passa o seu tipo')
    ok('ConfigUsuario.iniciar(' in html and 'css/config_usuario.css' in html and 'js/config_usuario.js' in html, 'chat.html liga o módulo novo')
    ok(html.count('id="tg-push"') == 1 and html.count('id="tg-som"') == 1 and html.count('id="tg-aviso"') == 1 and html.index('id="tg-som"') > html.index('id="set-notificacoes"') and html.index('id="tg-som"') < html.index('id="set-cobranca"'), 'sons, aviso na área de trabalho e push moraram pra Notificações (um só de cada)')
    cfg_js, cfg_css = leia('app', 'static', 'js', 'config_usuario.js'), leia('app', 'static', 'css', 'config_usuario.css')
    padrao_js = re.search(r"const PADRAO = \{(.*?)\};", cfg_js, re.S).group(1)
    pares = dict(re.findall(r"(\w+): ('?[\w]+'?)", padrao_js))
    esperado = {k: ("'%s'" % v if isinstance(v, str) else str(v).lower()) for k, v in preferencias.PADRAO.items()}
    ok(pares == esperado, 'os padrões do JS são os do servidor')
    ok([t[0] for t in preferencias.TIPOS_AVISO] == re.findall(r"\['(\w+)', '[^']+', 'fa-[\w-]+', ", cfg_js), 'os tipos de aviso do JS são os do servidor, na mesma ordem')
    ok(all(s in cfg_css for s in ('html[data-texto="p"]', 'html[data-texto="g"]', 'html[data-texto="gg"]', 'html[data-densidade="compacta"]', 'html[data-densidade="ampla"]', 'html[data-sublinhar]', 'html[data-reduz-mov]')), 'o CSS tem todas as opções de acessibilidade')
    ok('width: min(1240px' in cfg_css and 'height: min(840px' in cfg_css, 'a janela de configurações ficou maior')
    ok("hasAttribute('data-reduz-mov')" in leia('app', 'static', 'js', 'cosmeticos.js') and "hasAttribute('data-reduz-mov')" in leia('app', 'static', 'js', 'efeitos.js'), 'os motores de canvas respeitam "reduzir movimento"')
    # XSS: todo `${...}` que carrega texto vindo do servidor passa por esc() (ou é número: num/brl/Number)
    campos = ('m.titulo', 'm.rotulo', 'm.hora', 'x.titulo', 'x.quando', 'x.status_rotulo', 'p.termos_versao', 'p.termos_aceitos_em', 'p.contato', 'b.ate', 'b.nome', 'brasa.nome', 'brasa.ate', 'i.titulo', 'i.aba', 'i.corpo')
    soltos = [e for e in re.findall(r'\$\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', cfg_js) if any(f in e for f in campos) and not re.search(r'esc\(|num\(|brl\(|Number\(', e)]
    ok(not soltos, 'todo texto do servidor passa por esc() antes de virar HTML' + (f' (soltos: {soltos[:3]})' if soltos else ''))
    ok('fetch(\'/api/meus-dados\'' in cfg_js and 'meus-dados-pantheon.json' in cfg_js, 'o botão baixa a cópia e dá nome ao arquivo')

print()
print('FALHAS:' if falhas else 'TUDO OK', *falhas, sep='\n' if falhas else ' ')
sys.exit(1 if falhas else 0)
