"""Olimpo (Rodada 32): ativar de graça (padrão), renovar soma dias, a trilha Premium do Passe e a insígnia Ômega valem enquanto ativo e SOMEM no vencimento,
modo pago (cobrança Pix simulada, só confirma com pagamento), o que o código e a arte prometem."""
import os, sys
from datetime import timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
for k in ('RENDER', 'PAGAMENTOS', 'ASAAS_API_KEY', 'OLIMPO_GRATIS', 'OLIMPO_PRECO_CENT'):
    os.environ.pop(k, None)
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import olimpo, passe, pagamentos, olimpo_events
from app.cosmeticos import BADGE_OLIMPO, CATALOGO, posses_da_pessoa, posses_com_regras, badges_do_conjunto
from app.models import Role, Person, Posse, Cobranca, Notificacao, br_now

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
    for nome in ('Ana', 'Beto'):
        p = Person(name=nome, email=f'{nome.lower()}@x', role_id=r.id, username=nome.lower(), created_at=br_now() - timedelta(days=30))
        db.session.add(p); db.session.commit(); ids[nome.lower()] = p.id
    def pessoa(n):
        db.session.expire_all()      # os handlers do socket usam outra sessão: relê do banco
        return db.session.get(Person, ids[n])

    # temporada com uma recompensa só na trilha Premium
    t = passe.salvar_temporada({'nome': 'Teste', 'tema': 'neutro', 'niveis': 10, 'xp_por_nivel': 100})
    passe.salvar_recompensas(t, [{'nivel': 1, 'trilha': 'premium', 'tipo': 'moeda', 'quantidade': 77}, {'nivel': 1, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 5}])
    passe.ativar_temporada(t, True)
    db.session.execute(db.text("INSERT INTO passe_pessoa (person_id, temporada_id, xp, premium) VALUES (:p, :t, 500, 0)"), {'p': ids['ana'], 't': t}); db.session.commit()

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl

    ana, beto = cliente('ana'), cliente('beto')

    def emitir(cl, nome):
        olimpo_events._ultimo.clear()      # o freio de clique duplo não vale entre passos do teste
        cl.emit(nome, {})
        return ev(cl)

    # ---------------- 1. catálogo e arte ----------------
    it = CATALOGO[BADGE_OLIMPO]
    ok(it['tipo'] == 'badge' and it['valor'] == 'olimpo' and 'preco' not in it, 'a insígnia Brasa existe no catálogo e NÃO está à venda (só vem da assinatura)')
    raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    leia = lambda *p: open(os.path.join(raiz, *p), encoding='utf-8').read()
    js, css = leia('app', 'static', 'js', 'cosmeticos.js'), leia('app', 'static', 'css', 'cosmeticos.css')
    ok("olimpo:       { nome: 'Brasa'" in js and 'olimpo: () => {' in js, 'a arte da insígnia está registrada no cosmeticos.js (nome e desenho)')
    ok(js.count("class=\"om-pc om-pc") == 1 and 'om-crosta' in js and 'om-raio' in js and 'om-quente' in js, 'o desenho tem as peças, a crosta de lava, o clarão e os raios')
    ok(all(f'omPeca{k}' in css for k in range(5)) and all(n in css for n in ('omCrosta', 'omRaio', 'omQuente')) and 'prefers-reduced-motion' in css[css.index('Insígnia Olimpo'):], 'o CSS tem as 5 peças, a lava esfriando, os raios e respeita "reduzir movimento"')
    ok('.bd-wrap-olimpo:hover' in css and '.orb-grande .bd-svg.bd-olimpo' in css, 'a animação só roda no hover/zoom (parada é o Ômega inteiro e frio)')

    # ---------------- 2. grátis por enquanto ----------------
    ok(olimpo.gratis() and olimpo.estado(pessoa('ana'))['gratis'] and not olimpo.estado(pessoa('ana'))['ativo'], 'padrão: grátis, e ninguém começa com ele')
    ok(not passe.estado(pessoa('ana'))['premium'], 'sem Brasa a trilha Premium está trancada')
    rec = emitir(ana, 'olimpo_ativar')
    ana_p = pessoa('ana')
    ok(olimpo.ativo(ana_p) and 29 <= (ana_p.olimpo_ate - br_now()).days <= 30, 'ativar (grátis) liga a Brasa por 30 dias')
    ok(any(m['name'] == 'olimpo_estado' and m['args'][0].get('ativado') and m['args'][0]['estado']['ativo'] for m in rec), 'a pessoa recebe o estado novo (todas as abas)')
    ok(Cobranca.query.count() == 0, 'e nada foi cobrado')
    ok(BADGE_OLIMPO in posses_da_pessoa(ids['ana']) and 'olimpo' in badges_do_conjunto(posses_da_pessoa(ids['ana'])), 'a insígnia entra nas posses e no cartão')
    ok(passe.estado(ana_p)['premium'] is True and passe.estado(ana_p)['olimpo']['ativo'], 'a trilha Premium do Passe é liberada')
    res = passe.resgatar(ana_p, 1, 'premium')
    ok(res['moedas'] == 77, 'e dá pra resgatar a recompensa Premium (77 moedas)')
    antes = ana_p.olimpo_ate
    emitir(ana, 'olimpo_ativar')
    ana_p = pessoa('ana')
    ok(29 <= (ana_p.olimpo_ate - antes).days <= 30, 'renovar SOMA 30 dias ao fim do período atual (não perde os que sobravam)')
    ok(Posse.query.filter_by(person_id=ids['ana'], item_id=BADGE_OLIMPO).count() == 1, 'e não duplica a insígnia')
    ok(not olimpo.ativo(pessoa('beto')) and BADGE_OLIMPO not in posses_da_pessoa(ids['beto']), 'quem não ativou não tem nada')

    # ---------------- 3. vence: tudo volta ----------------
    ana_p.olimpo_ate = br_now() - timedelta(hours=1); db.session.commit()
    ok(BADGE_OLIMPO not in posses_da_pessoa(ids['ana']) and Posse.query.filter_by(person_id=ids['ana'], item_id=BADGE_OLIMPO).count() == 0, 'vencido: a insígnia some (e a linha é apagada)')
    ok('olimpo' not in badges_do_conjunto(posses_da_pessoa(ids['ana'])), '...do cartão também')
    ok(not passe.estado(pessoa('ana'))['premium'], '...e a trilha Premium tranca de novo (o que já foi resgatado fica)')
    ok(passe.estado(pessoa('ana'))['olimpo']['dias'] == 0, 'dias restantes = 0')
    emitir(ana, 'olimpo_ativar')
    ok(olimpo.ativo(pessoa('ana')) and BADGE_OLIMPO in posses_com_regras(pessoa('ana')), 'reativar depois de vencer funciona e a insígnia volta')

    # ---------------- 4. modo pago ----------------
    os.environ['OLIMPO_GRATIS'] = '0'; os.environ['OLIMPO_PRECO_CENT'] = '2490'
    ok(not olimpo.gratis() and olimpo.preco_cent() == 2490, 'OLIMPO_GRATIS=0 liga a cobrança; o preço vem da variável')
    os.environ['OLIMPO_PRECO_CENT'] = '5'; ok(olimpo.preco_cent() == 100, 'preço absurdo é limitado (mínimo R$ 1)')
    os.environ['OLIMPO_PRECO_CENT'] = '2490'
    antes = pessoa('beto').olimpo_ate
    rec = emitir(beto, 'olimpo_ativar')
    cob = [m['args'][0] for m in rec if m['name'] == 'olimpo_cobranca']
    ok(cob and cob[0]['valor_cent'] == 2490 and cob[0]['copia_cola'].startswith('PANTHEON-TESTE-') and cob[0]['simulada'], 'pago: ativar gera a cobrança (código de teste, valor certo)')
    ok(not olimpo.ativo(pessoa('beto')), '...e NÃO liga a Brasa antes de pagar')
    emitir(beto, 'olimpo_ativar')
    ok(Cobranca.query.filter_by(tipo='olimpo', ref_id=ids['beto']).count() == 1, 'pedir de novo reaproveita a cobrança em aberto')
    ok('Gere a cobrança' in str([m['args'] for m in emitir(ana, 'olimpo_simular') if m['name'] == 'erro_bazinga']), 'quem não tem cobrança não simula a dos outros')
    ok(not olimpo.ativo(pessoa('beto')), '...e a do Beto continua sem pagar')
    rec = emitir(beto, 'olimpo_simular')
    ok(olimpo.ativo(pessoa('beto')) and BADGE_OLIMPO in posses_da_pessoa(ids['beto']), 'só o pagamento (simulado) liga a Brasa e a insígnia')
    ok(any(m['name'] == 'olimpo_estado' and m['args'][0]['ativado'] for m in rec), 'e a pessoa é avisada na hora')
    ok(any('Brasa ativada' in n.titulo for n in Notificacao.query.filter_by(person_id=ids['beto']).all()), 'e recebe o aviso na caixa de entrada')
    ate = pessoa('beto').olimpo_ate
    emitir(beto, 'olimpo_simular')
    ok(pessoa('beto').olimpo_ate == ate, 'simular outra vez não soma de graça (a cobrança já está paga)')
    ok(pagamentos.estado()['provedor'] == 'simulado', 'a cobrança da Brasa usa o mesmo gateway dos pedidos')
    os.environ.pop('OLIMPO_GRATIS'); os.environ.pop('OLIMPO_PRECO_CENT')

    # produção sem gateway: nada de simular
    os.environ['RENDER'] = '1'; os.environ['OLIMPO_GRATIS'] = '0'; os.environ['EXIGIR_TERMOS'] = '0'   # (no Render os Termos são exigidos: aqui não é o assunto)
    ok('não está ligado' in str([m['args'] for m in emitir(beto, 'olimpo_ativar') if m['name'] == 'erro_bazinga']), 'no Render sem gateway a Brasa paga não gera cobrança de mentira')
    os.environ.pop('RENDER'); os.environ.pop('OLIMPO_GRATIS'); os.environ.pop('EXIGIR_TERMOS')

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
