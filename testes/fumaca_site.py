"""Rodada 39: atividade "Mesa de RPG e sites" (uma página que a call inteira abre junto).

Servidor: o endereço só vale se for https, sem usuário:senha, porta 443 e de um site da LISTA FECHADA (`jogos.SITES`); tudo é conferido por texto, sem pedido de
rede; só quem abriu a atividade troca a página; quem só ouve a call não troca; o estado leva `embute` (iframe ou aba) e chega a quem assiste (regra 6).
Cliente: o iframe só existe pra site que deixa embutir, sempre com `sandbox`, e o botão de abrir só aceita https."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import events, atividades, jogos, atividades_events
from app.models import Role, Person, Channel, Server

falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()


# ------------------------------------------------------------------ a lista fechada ----------------------------------------
bom, info = jogos.escolher_site('https://excalidraw.com/#room=abc123,chave456')
ok(bom and info['host'] == 'excalidraw.com' and info['embute'] is True and info['url'].endswith('#room=abc123,chave456'), 'Excalidraw: aceita e guarda o #fragmento da sala (é nele que vai a chave)')
bom, info = jogos.escolher_site('HTTPS://WWW.Owlbear.Rodeo/game/xyz?a=1')
ok(bom and info['host'] == 'www.owlbear.rodeo' and info['embute'] is False and info['url'] == 'https://www.owlbear.rodeo/game/xyz?a=1', 'Owlbear: host em minúsculas, mantém caminho e query, e NÃO embute (abre em aba)')
ok(jogos.escolher_site('https://tldraw.com')[1]['url'] == 'https://tldraw.com/', 'sem caminho vira "/"')
for ruim, motivo in [
    ('http://excalidraw.com/', 'sem https'), ('//excalidraw.com/', 'sem esquema'), ('javascript:alert(1)', 'javascript:'), ('data:text/html,<b>x</b>', 'data:'),
    ('ftp://excalidraw.com/', 'ftp'), ('https://evil.com/', 'site fora da lista'), ('https://excalidraw.com.evil.com/', 'domínio que só começa igual'),
    ('https://evil.com/excalidraw.com', 'nome do site só no caminho'), ('https://evil.com?x=excalidraw.com', 'nome do site só na query'),
    ('https://excalidraw.com@evil.com/', 'truque do arroba'), ('https://user:senha@excalidraw.com/', 'usuário e senha'), ('https://excalidraw.com:8443/', 'porta diferente'),
    ('https://excalidraw.com:80/', 'porta 80'), ('https://excalidraw.com/ x', 'espaço'), ('https://excalidraw.com/"onload=x', 'aspas'), ("https://excalidraw.com/'x", 'aspa simples'),
    ('https://excalidraw.com/<x>', 'sinais de menor/maior'), ('https://excalidraw.com/\\evil', 'barra invertida'), ('https://excalidraw.com/a\nb', 'quebra de linha no meio'), ('https://excalidraw.com/a\tb', 'tabulação'),
    ('https://127.0.0.1/', 'IP'), ('https://localhost/', 'localhost'), ('https://[::1]/', 'IPv6'), ('', 'vazio'), (None, 'nada'), (123, 'número'), (['https://excalidraw.com'], 'lista'),
    ('https://excalidraw.com/' + 'a' * 400, 'comprido demais'), ('https://', 'sem host'), ('https:///excalidraw.com', 'host vazio')]:
    r = jogos.escolher_site(ruim)
    ok(r[0] is False and isinstance(r[1], str), f'recusa {motivo}')
ok(all(k == k.lower() and '/' not in k and ':' not in k for k in jogos.SITES), 'a lista só tem hosts em minúsculas, sem caminho nem porta')
ok(all(isinstance(v, tuple) and len(v) == 3 and isinstance(v[2], bool) for v in jogos.SITES.values()), 'cada site da lista tem nome, descrição e a marca "embute"')

# ------------------------------------------------------------------ a mesa -------------------------------------------------
m = jogos.SiteCompartilhado(7)
ok(m.TIPO == 'site' and 'site' in jogos.JOGOS and 'site' in atividades.TIPOS_ATIVIDADE, 'o tipo "site" está nas listas fechadas')
ok(m.estado()['site']['url'] == '' and m.estado()['situacao'] == 'jogando', 'a mesa nasce sem página e já valendo (jogo aberto)')
m.definir(jogos.escolher_site('https://excalidraw.com/#room=a,b')[1])
ok(m.estado()['site']['nome'] == 'Excalidraw' and m.estado()['seq'] >= 1, 'definir guarda a página e sobe o seq (o cliente ignora estado velho)')
ok(m.acao(8, 'Beto', None, {'acao': 'trocar', 'url': 'https://tldraw.com/'})[0] is False, 'quem NÃO abriu a atividade não troca a página')
ok(m.acao(7, 'Ana', None, {'acao': 'trocar', 'url': 'https://tldraw.com/'}, ouvinte=True)[0] is False, 'quem só ouve a call não troca')
ok(m.acao(7, 'Ana', None, {'acao': 'trocar', 'url': 'https://evil.com/'})[0] is False and m.estado()['site']['host'] == 'excalidraw.com', 'trocar por site fora da lista é recusado e nada muda')
ok(m.acao(7, 'Ana', None, {'acao': 'trocar', 'url': 'https://tldraw.com/'}) == (True, '') and m.estado()['site']['host'] == 'tldraw.com', 'quem abriu troca a página')
ok(m.acao(7, 'Ana', None, {'acao': 'qualquer'})[0] is False and m.acao(7, 'Ana', None, {})[0] is False, 'ação desconhecida é recusada')
ok(m.estado().get('site', {}).keys() == {'url', 'host', 'nome', 'desc', 'embute'}, 'o estado só leva url, host, nome, descrição e embute')
ok(m.terminou() is False, 'a mesa de sites não "termina" sozinha')
ok(isinstance(atividades.iniciar('chave-site', 'site', 1), jogos.SiteCompartilhado), 'iniciar("site") cria a mesa certa')
atividades.encerrar('chave-site')

# ------------------------------------------------------------------ eventos ------------------------------------------------
app = create_app()
events.GRACA_CALL_SEGUNDOS = 0.3
for nome in ('FREIO_ACAO_S', 'FREIO_LANCE_S', 'FREIO_CONVITE_S', 'FREIO_JOGADA_S', 'FREIO_CONVIDAR_S'):
    setattr(atividades_events, nome, 0)


def ev(cli, nome=None):
    r = cli.get_received()
    return [x for x in r if nome is None or x['name'] == nome]


def ultimo(cli, nome):
    r = ev(cli, nome)
    return r[-1]['args'][0] if r else None


with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio'):
        pe = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower())
        db.session.add(pe); db.session.commit(); ids[n] = pe.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc)

    ana = cliente('Ana'); ev(ana)
    ana.emit('criar_servidor_discord', {'nome': 'Mesa'}); ev(ana)
    srv = Server.query.filter_by(name='Mesa').first()
    v1 = Channel(name='voz1', channel_type='voice', server_id=srv.id)
    db.session.add(v1); db.session.commit()
    ana.emit('criar_convite', {'server_id': srv.id}); cod = ev(ana, 'convite_criado')[-1]['args'][0]['code']
    for n in ('Beto', 'Caio'):
        cl = cliente(n); ev(cl); cl.emit('entrar_por_convite', {'code': cod}); ev(cl)
    ana = cliente('Ana'); beto = cliente('Beto'); caio = cliente('Caio')
    for cl in (ana, beto, caio):
        ev(cl)
    V = v1.id
    for cl, pid in ((ana, 'p-ana'), (beto, 'p-beto'), (caio, 'p-caio')):
        cl.emit('entrar_call', {'canal_id': V, 'peer_id': pid})
    for cl in (ana, beto, caio):
        ev(cl)

    # --- abrir sem endereço ou com endereço ruim: recusa e NÃO cria atividade ---
    for payload in ({}, {'url': ''}, {'url': 'http://excalidraw.com/'}, {'url': 'https://evil.com/'}, {'url': 'javascript:alert(1)'}, {'url': ['x']}, {'url': 5}):
        ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'site', **payload})
        ok(atividades.da_call(str(V)) is None, f'atividade_iniciar com {payload!r} não cria nada')
        ok(ev(ana, 'atividade_erro') != [], f'  ...e Ana recebe o motivo ({payload!r})')

    # --- abrir de verdade ---
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'site', 'url': 'https://excalidraw.com/#room=aaa,bbb'})
    est = ultimo(ana, 'atividade_estado')
    ok(est and est['tipo'] == 'site' and est['site']['host'] == 'excalidraw.com' and est['site']['embute'] is True, 'Ana abre o Excalidraw na call')
    ok(est['iniciador_id'] == ids['Ana'] and {p['nome'] for p in est['presentes']} == {'Ana', 'Beto', 'Caio'}, 'o estado diz quem abriu e quem está na call')
    est_b = ultimo(beto, 'atividade_estado')
    ok(est_b and est_b['site']['url'] == 'https://excalidraw.com/#room=aaa,bbb', 'Beto (que não abriu) recebe a mesma página ao vivo (regra 6)')
    ok(ultimo(caio, 'atividade_estado') is not None, 'Caio também')

    # --- trocar: só quem abriu ---
    beto.emit('atividade_acao', {'canal_id': V, 'acao': 'trocar', 'url': 'https://tldraw.com/'})
    ok(ev(beto, 'atividade_erro') and atividades.da_call(str(V)).info['host'] == 'excalidraw.com', 'Beto NÃO troca a página de quem abriu')
    ana.emit('atividade_acao', {'canal_id': V, 'acao': 'trocar', 'url': 'https://www.owlbear.rodeo/game/zzz'})
    est_c = ultimo(caio, 'atividade_estado')
    ok(est_c and est_c['site']['host'] == 'www.owlbear.rodeo' and est_c['site']['embute'] is False, 'Ana troca para o Owlbear e a call inteira vê (e agora abre em aba, sem iframe)')
    ana.emit('atividade_acao', {'canal_id': V, 'acao': 'trocar', 'url': 'https://evil.com/'})
    ok(atividades.da_call(str(V)).info['host'] == 'www.owlbear.rodeo', 'trocar para fora da lista não muda nada')

    # --- quem chega no meio recebe a página ---
    dani_pe = Person(name='Dani', email='Dani@x', role_id=r.id, username='dani'); db.session.add(dani_pe); db.session.commit(); ids['Dani'] = dani_pe.id
    dani = cliente('Dani'); ev(dani); dani.emit('entrar_por_convite', {'code': cod}); ev(dani)
    dani = cliente('Dani'); ev(dani)
    dani.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-dani'})
    est_d = ultimo(dani, 'atividade_estado')
    ok(est_d and est_d['tipo'] == 'site' and est_d['site']['host'] == 'www.owlbear.rodeo', 'quem entra na call depois já recebe a página aberta')

    # --- só uma atividade por vez, e encerrar ---
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'velha'}); ev(ana)
    ok(atividades.da_call(str(V)).tipo == 'site', 'não abre outra atividade por cima da mesa de sites')
    ana.emit('atividade_encerrar', {'canal_id': V})
    ok(atividades.da_call(str(V)) is None and (ultimo(beto, 'atividade_estado') or {}).get('ativa') is False, 'quem abriu encerra e todo mundo vê a mesa fechar')

# ------------------------------------------------------------------ o que o cliente promete --------------------------------
aj = ler('app/static/js/atividades_jogos.js'); ati = ler('app/static/js/atividades.js'); css = ler('app/static/css/atividades.css')
trecho = aj[aj.index('function corpoSite'):aj.index('const CORPOS')]
ok('site: corpoSite' in aj and "site: { nome: 'Mesa de RPG e sites'" in aj, 'o corpo da mesa de sites está registrado')
ok(trecho.count('<iframe') == 1 and 'if (s.embute && url)' in trecho, 'o iframe só existe quando o site deixa embutir')
ok('sandbox="' in trecho and 'allow-top-navigation' not in trecho and 'allow-top-navigation-by-user-activation' not in trecho, 'o iframe tem sandbox e NÃO pode navegar a página do Pantheon')
ok('referrerpolicy="no-referrer"' in trecho, 'o iframe não manda o endereço do Pantheon como referência')
ok('h.escUrl(' in trecho and 'h.esc(' in trecho and trecho.count('${s.') <= 2, 'url e nomes passam por escUrl/esc')
ok("/^https:\\/\\//.test(u || '')" in aj and "'noopener,noreferrer'" in aj, 'o botão de abrir só aceita https e abre com noopener')
ok('data-at="site-form"' in ati and "tipo: 'site'" in ati and 'site-ir' in ati, 'o seletor tem o cartão e o formulário da mesa de sites')
ok('https://excalidraw.com/' in ati and 'owlbear' in ati.lower(), 'o formulário oferece quadros prontos e cita o Owlbear')
ok('.aj-site' in css and '.at-site-form' in css and '.at-grande' in css, 'CSS do iframe, do formulário e do modo grande')
ok('eval(' not in trecho and 'innerHTML' not in trecho, 'o corpo da mesa não usa eval nem innerHTML solto')

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
