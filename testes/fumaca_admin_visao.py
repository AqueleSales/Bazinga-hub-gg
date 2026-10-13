"""Rodada 24: Visão geral do Estúdio (/admin): números, séries por dia, faixas de nível e a lista de pessoas (nome, @, e-mail).
Dados pessoais: só admin (403/404 pra o resto), nunca em cache; busca sem curinga; páginas; ordem; e os arquivos do cliente escapam tudo."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from datetime import timedelta
from app import create_app, db, events, admin_dados
from app.bazar import definir_admin
from app.models import Role, Person, Message, DirectMessage, Server, Channel, BazarLoja, br_now
from app.utils import xp_do_nivel

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    dados = [('Adm', 'adm', 'adm@gmail.com', 0), ('Ana', 'ana', 'ana@gmail.com', 0), ('Beto', 'beto', 'beto@gmail.com', xp_do_nivel(5)),
             ('Caio %_', 'caio', 'caio_x@gmail.com', xp_do_nivel(10)), ('Duda', 'duda', 'duda@gmail.com', xp_do_nivel(50)), ('Eli', 'eli', 'eli@gmail.com', xp_do_nivel(120))]
    for nome, user, email, xp in dados:
        p = Person(name=nome, email=email, role_id=r.id, username=user, xp=xp)
        db.session.add(p); db.session.commit(); ids[user] = p.id
    definir_admin(ids['adm'])
    # contas: uma antiga SEM data de entrada, uma de ontem, uma de 20 dias atrás
    db.session.get(Person, ids['ana']).created_at = None
    db.session.get(Person, ids['beto']).created_at = br_now() - timedelta(days=1)
    db.session.get(Person, ids['caio']).created_at = br_now() - timedelta(days=20)
    db.session.commit()
    srv = Server(name='Casa', owner_id=ids['adm'], publico=True); db.session.add(srv); db.session.commit()
    ch = Channel(name='geral', server_id=srv.id, channel_type='text'); db.session.add(ch); db.session.commit()
    for d, n in ((0, 3), (1, 2), (5, 4), (40, 9)):
        for _ in range(n):
            db.session.add(Message(text='x', person_id=ids['adm'], channel_id=ch.id, timestamp=br_now() - timedelta(days=d, minutes=1)))
    db.session.add(DirectMessage(sender_id=ids['adm'], receiver_id=ids['ana'], content='oi', timestamp=br_now() - timedelta(minutes=1)))
    db.session.add(BazarLoja(owner_id=ids['beto'], nome='Loja')); db.session.commit()

    def web(user):
        fc = app.test_client()
        if user:
            with fc.session_transaction() as s:
                s['user_id'] = ids[user]
        return fc

    # ---------- 1. quem pode ver ----------
    for quem in (None, 'ana'):
        c = web(quem)
        ok(c.get('/admin/api/geral').status_code == 403 and c.get('/admin/api/pessoas/lista').status_code == 403, f'{"sem login" if not quem else "usuário comum"}: números e lista de pessoas dão 403')
        ok(c.get('/admin').status_code == 404, f'{"sem login" if not quem else "usuário comum"}: a página nem confirma que existe (404)')
    adm = web('adm')
    g = adm.get('/admin/api/geral?dias=30')
    ok(g.status_code == 200 and 'no-store' in (g.headers.get('Cache-Control') or ''), 'admin recebe os números, sem cache')
    lp = adm.get('/admin/api/pessoas/lista')
    ok(lp.status_code == 200 and 'no-store' in (lp.headers.get('Cache-Control') or ''), 'admin recebe a lista de pessoas (dado pessoal), sem cache')

    # ---------- 2. números e séries ----------
    d = g.get_json()
    ok(d['pessoas'] == 6 and d['contas_sem_data'] == 1, f'conta o total e as contas sem data de entrada ({d["pessoas"]}, {d["contas_sem_data"]})')
    ok(d['novas_7d'] >= 2 and d['novas_periodo'] >= 4, f'novas em 7 dias / no período (os 4 criados agora ou ontem; {d["novas_7d"]}, {d["novas_periodo"]})')
    ok(len(d['contas_por_dia']) == 30 and d['contas_por_dia'][-1]['dia'] == br_now().strftime('%Y-%m-%d'), 'série de 30 dias completa, terminando hoje (dia sem nada = 0)')
    ok(sum(x['n'] for x in d['contas_por_dia']) == d['novas_periodo'], 'a soma da série bate com o número do período')
    ok(len(d['mensagens_por_dia']) == 30 and d['mensagens_por_dia'][-1]['canais'] == 3 and d['mensagens_por_dia'][-1]['dms'] == 1 and d['mensagens_por_dia'][-1]['n'] == 4, 'mensagens do dia = canais + diretas')
    ok(sum(x['canais'] for x in d['mensagens_por_dia']) == 9 and d['mensagens_hoje'] == 4, 'o que passou da janela (40 dias atrás) fica de fora; "hoje" soma as duas')
    ok(d['servidores'] == 1 and d['servidores_publicos'] == 1 and d['lojas'] == 1, 'servidores, públicos e lojas')
    ok(sum(f['n'] for f in d['niveis']) == d['pessoas'] and [f['n'] for f in d['niveis']] == [2, 1, 1, 0, 1, 1], f'faixas de nível somam o total e cada um caiu na faixa certa ({[f["n"] for f in d["niveis"]]})')
    ok(len(adm.get('/admin/api/geral?dias=7').get_json()['contas_por_dia']) == 7 and len(adm.get('/admin/api/geral?dias=90').get_json()['contas_por_dia']) == 90, 'janelas de 7 e 90 dias')
    ok(len(adm.get('/admin/api/geral?dias=3').get_json()['contas_por_dia']) == 30 and len(adm.get('/admin/api/geral?dias=abc').get_json()['contas_por_dia']) == 30, 'janela inválida cai nos 30 dias (nada de pedir 5 anos)')
    ok(d['online_agora'] == 0, 'ninguém conectado: 0 online')
    events.usuarios_conectados[ids['beto']] = 2; events.usuarios_conectados[ids['eli']] = 0
    ok(adm.get('/admin/api/geral').get_json()['online_agora'] == 1, 'online agora conta pessoas (não abas) e ignora quem já saiu')

    # ---------- 3. lista de pessoas ----------
    L = adm.get('/admin/api/pessoas/lista').get_json()
    ok(L['total'] == 6 and L['pagina'] == 1 and len(L['pessoas']) == 6, 'sem busca: todas as 6')
    p0 = L['pessoas'][0]
    ok(set(p0.keys()) == {'id', 'nome', 'username', 'email', 'avatar', 'criado_em', 'nivel', 'online'}, 'cada pessoa traz só: nome, @, e-mail, foto, data, nível e se está online')
    ok(L['pessoas'][0]['nome'] == 'Eli' and L['pessoas'][-1]['nome'] == 'Adm', 'ordem padrão: mais recentes primeiro (pelo id)')
    por_nome = {p['username']: p for p in L['pessoas']}
    ok(por_nome['ana']['criado_em'] is None and por_nome['beto']['criado_em'] and por_nome['beto']['online'] is True and por_nome['eli']['online'] is False, 'conta antiga sem data = null; online reflete a conexão')
    ok(por_nome['eli']['nivel'] >= 120 and por_nome['ana']['nivel'] == 1, 'o nível vem do XP')
    ok([p['nome'] for p in adm.get('/admin/api/pessoas/lista?ordem=nome').get_json()['pessoas']][:2] == ['Adm', 'Ana'], 'ordem por nome')
    ok(adm.get('/admin/api/pessoas/lista?ordem=nivel').get_json()['pessoas'][0]['nome'] == 'Eli', 'ordem por maior nível')
    ok(adm.get('/admin/api/pessoas/lista?q=gmail').get_json()['total'] == 6, 'a busca acha pelo e-mail')
    ok([p['username'] for p in adm.get('/admin/api/pessoas/lista?q=%40duda').get_json()['pessoas']] == ['duda'], 'a busca aceita @conta')
    ok(adm.get('/admin/api/pessoas/lista?q=%25').get_json()['total'] == 6, 'curinga % sozinho não vira "tudo que casa" (a busca de 1 caractere é ignorada)')
    ok(adm.get('/admin/api/pessoas/lista?q=a%25a').get_json()['total'] == 0 and adm.get('/admin/api/pessoas/lista?q=a_a').get_json()['total'] == 0,
       'curingas dentro da busca são removidos: "a%a" e "a_a" viram "aa" (se valessem como curinga casariam "ana")')
    ok(adm.get('/admin/api/pessoas/lista?q=zzzz').get_json()['total'] == 0, 'busca sem resultado volta vazia')
    for i in range(30):
        db.session.add(Person(name=f'Extra {i:02d}', email=f'e{i}@x.com', role_id=r.id, username=f'extra{i}'))
    db.session.commit()
    p1 = adm.get('/admin/api/pessoas/lista?pagina=1').get_json(); p2 = adm.get('/admin/api/pessoas/lista?pagina=2').get_json()
    ok(p1['total'] == 36 and p1['paginas'] == 2 and len(p1['pessoas']) == 25 and len(p2['pessoas']) == 11, 'paginação de 25 em 25')
    ok(adm.get('/admin/api/pessoas/lista?pagina=99').get_json()['pagina'] == 2 and adm.get('/admin/api/pessoas/lista?pagina=-3').get_json()['pagina'] == 1, 'página fora do intervalo é ajustada')

    # ---------- 4. arquivos do cliente ----------
    adm_js = open(os.path.join(RAIZ, 'static', 'js', 'admin.js'), encoding='utf-8').read()
    gr = open(os.path.join(RAIZ, 'static', 'js', 'admin_graficos.js'), encoding='utf-8').read()
    css = open(os.path.join(RAIZ, 'static', 'css', 'admin.css'), encoding='utf-8').read()
    html = open(os.path.join(RAIZ, 'templates', 'admin.html'), encoding='utf-8').read()
    ok('admin_graficos.js' in html and html.index('admin_graficos.js') < html.index('js/admin.js'), 'admin.html carrega os gráficos antes do admin.js')
    ok('innerHTML' not in gr and re.search(r'(?<!\w)eval\(|document\.write', gr) is None, 'os gráficos NUNCA usam innerHTML (nome de pessoa/servidor entra por textContent), sem eval')
    ok(all(f'esc(p.{k})' in adm_js for k in ('nome', 'email', 'username')) and 'fotoOk(' in adm_js, 'a lista escapa nome, @ e e-mail, e só aceita foto https ou do site')
    ok('Ver como tabela' in gr and 'es-g-tabela' in gr, 'todo gráfico tem a versão em tabela')
    ok('tabindex' in gr and 'focus' in gr and 'ArrowLeft' in gr, 'a dica também abre pelo teclado (foco e setas)')
    ok('linear-gradient' not in css.split('VISÃO GERAL')[1], 'gráficos sem gradiente decorativo (cor chapada)')
    ok(not re.search(r'class="[^"]*\bad[s]?-', html + adm_js + gr) and not re.search(r"['\"]ad[s]?-", gr), 'nada de classe com prefixo "ad-"/"ads-" (bloqueador de anúncio esconde)')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
