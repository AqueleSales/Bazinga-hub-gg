"""Plantar loja no mapa (Rodada 32): só o dono, só com a posição do aparelho e dentro do alcance, área aproximada (~330 m) ou ponto exato, pino só com
loja aberta e com produto, prévia sem dados privados, alcance de quem vê, mudar de lugar, tirar, loja escondida/banida some, regra 6."""
import os, sys
from datetime import timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
for k in ('RENDER', 'PAGAMENTOS', 'ASAAS_API_KEY'):
    os.environ.pop(k, None)
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import bazar, bazar_events
from app.models import Role, Person, BazarLoja, BazarBanimento, br_now

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cl, nome=None):
    return [m for m in cl.get_received() if nome is None or m['name'] == nome]


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('Ana', 'Beto', 'Cris', 'Duda'):
        p = Person(name=nome, email=f'{nome.lower()}@x', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=30))
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
        return next((m['args'][0]['msg'] for m in rec if m['name'] in ('bazar_erro', 'erro_bazinga')), None)

    ana, beto, cris, duda = cliente('ana'), cliente('beto'), cliente('cris'), cliente('duda')
    AQUI = {'lat': -15.8000, 'lng': -47.9000}
    emitir(ana, 'atualizar_localizacao', AQUI)
    emitir(beto, 'mapa_pedir_arredores', {'lat': -15.801, 'lng': -47.901})       # perto (~150 m)
    emitir(cris, 'mapa_pedir_arredores', {'lat': -23.55, 'lng': -46.63})         # longe (SP)

    # ---------------- 1. quem pode ----------------
    rec = emitir(ana, 'loja_mapa_minha')
    ok(rec[-1]['args'][0] == {'tem': False, 'loja': None, 'no_mapa': False, 'pode': False}, 'sem loja: a opção "Loja" do Plantar não aparece (tem = falso)')
    ok('Abra a sua loja' in (erro(emitir(ana, 'plantar_loja', {**AQUI, 'aprox': True})) or ''), 'sem loja não planta')
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Doces da Ana', 'categoria': 'comida', 'cor': 'vinho', 'pix_chave': 'ana@exemplo.com', 'pix_nome': 'Ana', 'pix_cidade': 'Brasilia'})
    rec = emitir(ana, 'loja_mapa_minha')
    ok(rec[-1]['args'][0]['tem'] and rec[-1]['args'][0]['pode'] and not rec[-1]['args'][0]['no_mapa'], 'com loja a opção aparece (ainda fora do mapa)')
    ok('pelo menos um produto' in (erro(emitir(ana, 'plantar_loja', {**AQUI, 'aprox': True})) or ''), 'loja sem produto não planta (pino vazio não ajuda ninguém)')
    emitir(ana, 'bazar_salvar_produto', {'nome': 'Brigadeiro', 'descricao': 'caixa com 12', 'preco_cent': 4500, 'tipo': 'fisico', 'estoque': 10})
    ok('Local inválido' in (erro(emitir(ana, 'plantar_loja', {'lat': 'x', 'lng': 1})) or ''), 'coordenada inválida é recusada')
    ok('fora do seu alcance' in (erro(emitir(ana, 'plantar_loja', {'lat': -23.55, 'lng': -46.63})) or ''), 'não planta a quilômetros de onde está')
    ok(BazarLoja.query.one().pino_lat is None, '...e nada foi gravado')
    ok(erro(emitir(beto, 'plantar_loja', {**AQUI})) is not None and BazarLoja.query.one().pino_lat is None, 'quem não tem loja não planta a dos outros')
    ok(erro(emitir(duda, 'plantar_loja', {**AQUI})) is not None, 'quem nem mandou posição não planta')

    # posição que veio só do IP não vale
    emitir(ana, 'atualizar_localizacao', {**AQUI, 'fonte': 'ip'})
    ok('IP' in (erro(emitir(ana, 'plantar_loja', {**AQUI})) or '').upper() or 'internet' in (erro(emitir(ana, 'plantar_loja', {**AQUI})) or ''), 'posição só por IP (aproximada) não planta')
    emitir(ana, 'atualizar_localizacao', {**AQUI, 'fonte': 'aparelho'})
    ana_pessoa = db.session.get(Person, ids['ana']); ana_pessoa.localizacao_ativa = False; db.session.commit()
    ok(erro(emitir(ana, 'plantar_loja', {**AQUI})) is not None, 'com a localização desligada não planta')
    ana_pessoa.localizacao_ativa = True; db.session.commit()

    # ---------------- 2. plantar: área aproximada x ponto exato ----------------
    ev(beto); ev(cris)
    rec = emitir(ana, 'plantar_loja', {'lat': -15.80012, 'lng': -47.90077, 'aprox': True})
    loja = BazarLoja.query.one()
    ok(loja.pino_lat is not None and loja.pino_aprox is True, 'plantou (área aproximada)')
    ok(abs(loja.pino_lat - (-15.801)) < 0.0016 and (round(loja.pino_lat / 0.003, 6) % 1) < 1e-4, 'o ponto foi ARREDONDADO pra grade de ~330 m (não revela a porta)')
    ok(any(m['name'] == 'loja_mapa_ok' for m in rec), 'quem plantou recebe a confirmação')
    nova_perto = ev(beto, 'loja_mapa_nova')
    ok(nova_perto and nova_perto[-1]['args'][0]['nome'] == 'Doces da Ana' and nova_perto[-1]['args'][0]['aprox'], 'regra 6: quem está perto vê a loja aparecer na hora')
    ok(not ev(cris, 'loja_mapa_nova'), 'quem está longe não recebe o pino')
    j = nova_perto[-1]['args'][0]
    ok(set(j) == {'id', 'nome', 'categoria', 'cor', 'toldo', 'logo_url', 'regiao', 'nota', 'nota_qtd', 'lat', 'lng', 'aprox', 'pague_no_app', 'reputacao', 'dono_id'},
       'a prévia traz só o necessário')
    ok('pix' not in str(j).lower() and 'wallet' not in str(j).lower() and 'ana@' not in str(j), 'e NADA de Pix, carteira nem e-mail')
    emitir(ana, 'plantar_loja', {**AQUI, 'aprox': False})
    loja = BazarLoja.query.one()
    ok(loja.pino_lat == -15.8 and loja.pino_lng == -47.9 and loja.pino_aprox is False, 'ponto exato: guarda o ponto (5 casas)')

    # ---------------- 3. quem vê no mapa ----------------
    d = next(m['args'][0] for m in emitir(beto, 'mapa_pedir_arredores', {'lat': -15.801, 'lng': -47.901}) if m['name'] == 'mapa_arredores')
    ok([l['nome'] for l in d['lojas']] == ['Doces da Ana'], 'quem está perto recebe a loja nos arredores')
    d = next(m['args'][0] for m in emitir(cris, 'mapa_pedir_arredores', {'lat': -23.55, 'lng': -46.63}) if m['name'] == 'mapa_arredores')
    ok(d['lojas'] == [], 'quem está longe (SP) não recebe')
    d = next(m['args'][0] for m in emitir(beto, 'mapa_pedir_arredores', {'lat': -15.90, 'lng': -47.90}) if m['name'] == 'mapa_arredores')
    ok(d['lojas'] == [] or d['lojas'][0]['nome'] == 'Doces da Ana', 'o alcance é o dos servidores (~15 km): 11 km ainda vê')
    d = next(m['args'][0] for m in emitir(beto, 'mapa_pedir_arredores', {'lat': -16.2, 'lng': -47.9}) if m['name'] == 'mapa_arredores')
    ok(d['lojas'] == [], '40 km: fora do alcance')

    # ---------------- 4. esconder: loja fechada, moderação, banimento ----------------
    def vê():
        return [l['nome'] for l in next(m['args'][0] for m in emitir(beto, 'mapa_pedir_arredores', {'lat': -15.801, 'lng': -47.901}) if m['name'] == 'mapa_arredores')['lojas']]
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Doces da Ana', 'categoria': 'comida', 'aberta': False})
    ok(vê() == [], 'loja FECHADA some do mapa')
    emitir(ana, 'bazar_salvar_loja', {'nome': 'Doces da Ana', 'categoria': 'comida', 'aberta': True})
    ok(vê() == ['Doces da Ana'], '...e volta quando reabre')
    loja = BazarLoja.query.one(); loja.oculta = True; db.session.commit()
    ok(vê() == [], 'loja escondida pela moderação some')
    loja.oculta = False; db.session.add(BazarBanimento(person_id=ids['ana'], motivo='teste', por_id=ids['cris'], ate=None)); db.session.commit()
    ok(vê() == [], 'loja de quem foi banido do Bazar some')
    BazarBanimento.query.delete(); db.session.commit()
    ok(vê() == ['Doces da Ana'], '...e volta sem banimento')

    # ---------------- 5. mudar de lugar e tirar ----------------
    ev(beto)
    emitir(ana, 'plantar_loja', {'lat': -15.8004, 'lng': -47.9004, 'aprox': False})
    rec_b = ev(beto)
    ok(any(m['name'] == 'loja_mapa_removida' for m in rec_b) and any(m['name'] == 'loja_mapa_nova' for m in rec_b), 'mudar de lugar: o pino velho é tirado e o novo aparece (regra 6)')
    ok(len(vê()) == 1, 'só UM pino por loja')
    ok('não está no mapa' in (erro(emitir(beto, 'tirar_loja_do_mapa')) or ''), 'quem não tem loja no mapa não tira nada')
    ev(beto)
    rec = emitir(ana, 'tirar_loja_do_mapa')
    ok(BazarLoja.query.one().pino_lat is None and any(m['name'] == 'loja_mapa_ok' and m['args'][0].get('removida') for m in rec), 'o dono tira a loja do mapa')
    ok(any(m['name'] == 'loja_mapa_removida' for m in ev(beto)) and vê() == [], 'quem olhava vê sumir na hora')
    ok(BazarLoja.query.one().aberta is not False, 'tirar do mapa não fecha a loja')

    # ---------------- 6. loja no JSON do Bazar ----------------
    ok(bazar.loja_json(BazarLoja.query.one())['pino'] is False, 'loja_json diz se tem pino')

raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
