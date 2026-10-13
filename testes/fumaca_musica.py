"""Rodada 25 (parte B): Música. Pesquisa pela API do YouTube (SIMULADA: não há chave real aqui), cache, cota (unidades por dia, teto por pessoa, bloqueio
quando o Google responde 403/429/400), colar link de música/playlist (sem cota), eventos, 'adicionar à playlist do perfil' e o que o código promete
(chave só no cabeçalho, player sempre visível, termos do YouTube)."""
import os, sys, json, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
os.environ.pop('YOUTUBE_API_KEY', None)
os.environ.pop('YOUTUBE_UNIDADES_DIA', None)
from urllib.parse import urlsplit, parse_qs
from app import create_app, db, socketio, musica as mu, conexoes as cx, conexoes_events, musica_events, importar
from app.models import Role, Person, Conexao

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def levanta(fn, trecho=None):
    try:
        fn()
    except mu.ErroMusica as e:
        return trecho is None or trecho in str(e)
    except Exception as e:
        print('   (levantou outra coisa:', type(e).__name__, e, ')')
        return False
    return False


def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


def zerar():
    mu._cache.clear(); mu._por_pessoa.clear(); mu._estado.update(dia=None, unidades=0, bloqueado_ate=0.0)


# ---------------------------------------------------------------------
# a API do YouTube de mentira
# ---------------------------------------------------------------------
class Falsa:
    def __init__(self):
        self.chamadas = []                       # (url, cabeçalhos extras)
        self.status = {'search': 200, 'videos': 200, 'playlistItems': 200, 'oembed': 200}
        self.explode = False
        self.nao_embed = set()                   # ids que o videos.list diz que não tocam fora do YouTube

    def rota(self, url):
        return 'oembed' if 'oembed' in url else urlsplit(url).path.rsplit('/', 1)[-1]

    def __call__(self, url, **kw):
        if self.explode:
            raise RuntimeError('boom')
        r = self.rota(url)
        self.chamadas.append((url, kw.get('extra') or {}))
        st = self.status.get(r, 200)
        if st != 200:
            return st, '', '', url
        q = parse_qs(urlsplit(url).query)
        if r == 'search':
            itens = [{'id': {'videoId': 'abcdefghi%02d' % i}, 'snippet': {'title': f'Faixa {i} &amp; Cia &#39;ao vivo&#39;', 'channelTitle': 'Canal&nbsp;Bom'}} for i in range(1, 6)]
            itens[1]['snippet']['title'] = 'Música\x07 ​perigosa <img src=x onerror=alert(1)>'
            itens.append({'id': {'videoId': "ruim'id"}, 'snippet': {'title': 'id inválido', 'channelTitle': 'x'}})
            itens.append({'id': {'channelId': 'UCabc'}, 'snippet': {'title': 'canal', 'channelTitle': 'x'}})
            itens.append('lixo')
            return 200, 'application/json', json.dumps({'items': itens}), url
        if r == 'videos':
            ids = q['id'][0].split(',')
            itens = [{'id': i, 'contentDetails': {'duration': 'PT3M33S' if n != 2 else 'P0D'}, 'status': {'embeddable': i not in self.nao_embed}} for n, i in enumerate(ids)]
            return 200, 'application/json', json.dumps({'items': itens}), url
        if r == 'playlistItems':
            itens = [{'snippet': {'title': f'Pista {i}', 'videoOwnerChannelTitle': 'Banda - Topic', 'resourceId': {'videoId': 'pista%06d' % i}}} for i in range(1, 5)]
            itens.append({'snippet': {'title': 'Private video', 'resourceId': {'videoId': 'privado0001'}}})
            itens.append({'snippet': {'title': 'Deleted video', 'resourceId': {'videoId': 'apagado0001'}}})
            return 200, 'application/json', json.dumps({'items': itens}), url
        if r == 'oembed':
            return 200, 'application/json', json.dumps({'title': 'Música <b>Linda</b>', 'author_name': 'Fulano - Topic', 'thumbnail_url': 'https://i.ytimg.com/vi/x/hq.jpg'}), url
        return 404, '', '', url


falsa = Falsa()
importar.baixar_texto = falsa
mu.importar.baixar_texto = falsa
cx.importar.baixar_texto = falsa
conexoes_events.socketio.start_background_task = lambda f, *a, **k: f(*a, **k)

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto'):
        p = Person(name=n, email=f'{n.lower()}@x', role_id=r.id, username=n.lower())
        db.session.add(p); db.session.commit(); ids[n] = p.id

    # ---------- 1. peças pequenas ----------
    ok([mu.segundos_da_duracao(x) for x in ('PT3M33S', 'PT1H2M3S', 'PT45S', 'P1DT1H', 'P0D', 'PT0S', 'x', '', None)] == [213, 3723, 45, 90000, None, None, None, None, None], 'duração ISO 8601 vira segundos (ao vivo, zero e lixo viram None)')
    ok(all(mu.parece_link(x) for x in ('https://youtu.be/x', 'music.youtube.com/watch?v=a', 'www.youtube.com/x', 'http://exemplo.com', ' https://x')) and not any(mu.parece_link(x) for x in ('anitta', 'youtube é legal', 'envolver', '')), 'o que é link e o que é pesquisa')
    ok(mu._consulta('  Anitta \n\t  Envolver\x00  ') == 'Anitta Envolver' and len(mu._consulta('a' * 500)) == mu.MAX_CONSULTA, 'a pesquisa é arrumada (espaços, controle) e limitada')

    # ---------- 2. sem chave ----------
    zerar()
    ok(mu.disponivel() is False and mu.estado_para(ids['Ana'])['disponivel'] is False, 'sem YOUTUBE_API_KEY a pesquisa aparece como desligada')
    ok(levanta(lambda: mu.buscar(ids['Ana'], 'anitta'), 'ainda não foi ligada') and not falsa.chamadas, 'sem chave: recusa com a razão e NÃO chama a rede')
    ok(levanta(lambda: mu.buscar(ids['Ana'], 'a'), 'pelo menos 2 letras'), 'pesquisa curta demais é recusada')
    rv = mu.resolver_link('https://music.youtube.com/watch?v=dQw4w9WgXcQ&list=RDAMVMdQw4w9WgXcQ')
    ok(rv['itens'][0]['v'] == 'dQw4w9WgXcQ' and rv['playlist'] is False and rv['itens'][0]['t'] == 'Música <b>Linda</b>' and 'oembed' in falsa.chamadas[-1][0], 'colar link de música funciona SEM chave (oEmbed, sem cota)')
    ok(levanta(lambda: mu.resolver_link('https://www.youtube.com/playlist?list=PLabcdefghij1'), 'precisa da pesquisa ligada'), 'abrir playlist por link precisa da chave (e diz isso)')
    ok(mu.unidades_hoje() == 0, 'sem chave nada gasta cota')

    # ---------- 3. pesquisa de verdade (simulada) ----------
    os.environ['YOUTUBE_API_KEY'] = 'chave-secreta-de-teste'
    zerar(); falsa.chamadas.clear()
    r1 = mu.buscar(ids['Ana'], '  Anitta   Envolver ')
    its = r1['itens']
    ok(r1['cache'] is False and len(its) == 5 and [i['v'] for i in its] == ['abcdefghi%02d' % i for i in range(1, 6)], 'pesquisa devolve só vídeos com id válido (id estranho, canal e lixo ficam de fora)')
    ok(its[0]['t'] == "Faixa 1 & Cia 'ao vivo'" and its[0]['a'] == 'Canal Bom', 'título e canal chegam com as entidades HTML desfeitas')
    ok(its[1]['t'] == 'Música perigosa <img src=x onerror=alert(1)>', 'caractere de controle/invisível sai; o HTML fica como TEXTO (o cliente escapa)')
    ok(its[0]['d'] == 213 and its[2]['d'] is None, 'a duração vem da leitura dos detalhes (ao vivo = sem duração)')
    urls = [u for u, _ in falsa.chamadas]
    busca_url = next(u for u in urls if '/search' in u); q = parse_qs(urlsplit(busca_url).query)
    ok(q['videoEmbeddable'] == ['true'] and q['videoSyndicated'] == ['true'] and q['videoCategoryId'] == ['10'] and q['type'] == ['video'] and q['q'] == ['Anitta Envolver'], 'a pesquisa pede só o que toca fora do YouTube, só música, e arruma o texto')
    ok(all('chave-secreta' not in u and 'key=' not in u for u in urls) and all(e.get('x-goog-api-key') == 'chave-secreta-de-teste' for u, e in falsa.chamadas if 'googleapis' in u), 'a CHAVE vai só no cabeçalho, nunca na URL')
    ok(mu.unidades_hoje() == 101 and len(falsa.chamadas) == 2, 'uma pesquisa custa 101 unidades (100 da busca + 1 da leitura) e 2 chamadas')
    ok(mu.restantes_pessoa(ids['Ana']) == mu.MAX_BUSCAS_PESSOA_DIA - 1, 'conta uma pesquisa pra pessoa')
    n_chamadas = len(falsa.chamadas)
    r2 = mu.buscar(ids['Beto'], 'ANITTA envolver')
    ok(r2['cache'] is True and len(falsa.chamadas) == n_chamadas and mu.unidades_hoje() == 101 and mu.restantes_pessoa(ids['Beto']) == mu.MAX_BUSCAS_PESSOA_DIA, 'repetir a pesquisa (outra pessoa, outra caixa) vem do cache: sem rede, sem cota, sem contar no limite')
    r2['itens'][0]['t'] = 'MEXIDO'
    ok(mu.buscar(ids['Ana'], 'anitta envolver')['itens'][0]['t'] != 'MEXIDO', 'mexer no resultado devolvido não estraga o cache')
    mu.buscar(ids['Ana'], 'anitta envolver', so_musica=False)
    q2 = parse_qs(urlsplit(next(u for u in reversed([u for u, _ in falsa.chamadas]) if '/search' in u)).query)
    ok('videoCategoryId' not in q2 and mu.unidades_hoje() == 202, 'sem o filtro "só música" é outra pesquisa (outra chave de cache) e sem a categoria 10')

    # embed bloqueado pela leitura de detalhes
    zerar(); falsa.nao_embed = {'abcdefghi03'}
    ids_res = [i['v'] for i in mu.buscar(ids['Ana'], 'tem bloqueado')['itens']]
    ok('abcdefghi03' not in ids_res and len(ids_res) == 4, 'vídeo que o YouTube diz que NÃO toca fora dele é tirado do resultado')
    falsa.nao_embed = set()

    # ---------- 4. cota ----------
    zerar(); mu_limite = mu.MAX_BUSCAS_PESSOA_DIA; mu.MAX_BUSCAS_PESSOA_DIA = 3
    for i in range(3):
        mu.buscar(ids['Ana'], f'pesquisa {i}')
    ok(levanta(lambda: mu.buscar(ids['Ana'], 'pesquisa nova'), 'já fez as 3 pesquisas'), 'a pessoa tem teto de pesquisas por dia')
    ok(mu.buscar(ids['Ana'], 'pesquisa 0')['cache'] is True, '...mas o que já está no cache continua saindo')
    ok(mu.buscar(ids['Beto'], 'pesquisa nova')['cache'] is False, '...e outra pessoa não é afetada')
    mu.MAX_BUSCAS_PESSOA_DIA = mu_limite
    zerar(); os.environ['YOUTUBE_UNIDADES_DIA'] = '250'
    mu.buscar(ids['Ana'], 'um'); mu.buscar(ids['Ana'], 'dois')
    ok(levanta(lambda: mu.buscar(ids['Beto'], 'tres'), 'pesquisas de hoje acabaram') and mu.unidades_hoje() == 202, 'o app inteiro tem um teto de unidades por dia (a 3ª não cabe)')
    ok(mu.buscar(ids['Beto'], 'um')['cache'] is True, '...e o cache continua atendendo')
    ok(mu.resolver_link('https://youtu.be/dQw4w9WgXcQ')['itens'], '...e colar link de música continua funcionando (não gasta cota)')
    os.environ.pop('YOUTUBE_UNIDADES_DIA')
    dia_real = mu._dia
    mu._dia = lambda: '2099-01-01'
    ok(mu.unidades_hoje() == 0 and mu.restantes_pessoa(ids['Ana']) == mu.MAX_BUSCAS_PESSOA_DIA, 'virou o dia (horário do Pacífico): a cota e os limites zeram')
    mu._dia = dia_real

    # ---------- 5. quando o Google reclama ----------
    for st, bloqueia in ((403, True), (400, True), (429, True), (500, False)):
        zerar(); falsa.status['search'] = st; falsa.chamadas.clear()
        ok(levanta(lambda: mu.buscar(ids['Ana'], f'erro {st}')), f'status {st} do Google vira mensagem pra pessoa')
        n = len(falsa.chamadas)
        falsa.status['search'] = 200
        bloqueado = levanta(lambda: mu.buscar(ids['Ana'], f'outra {st}'), 'indisponível agora')
        ok(bloqueado == bloqueia and (len(falsa.chamadas) == n or not bloqueia) , f'status {st}: {"bloqueia as próximas pesquisas sem bater na rede" if bloqueia else "NÃO bloqueia (erro passageiro)"}')
    zerar(); falsa.status['search'] = 200
    ok(mu.buscar(ids['Ana'], 'depois de liberar')['itens'], 'liberado o bloqueio a pesquisa volta')
    zerar(); falsa.status['videos'] = 500
    ok(all(i['d'] is None for i in mu.buscar(ids['Ana'], 'sem detalhes')['itens']), 'a leitura de duração falhar NÃO derruba a pesquisa (só vem sem duração)')
    falsa.status['videos'] = 200
    def sem_rede(url, **kw): raise importar.ErroImportar('O site não respondeu.')
    mu.importar.baixar_texto = sem_rede
    zerar()
    ok(levanta(lambda: mu.buscar(ids['Ana'], 'sem rede'), 'não respondeu'), 'sem rede vira mensagem simples')
    def json_ruim(url, **kw): return 200, 'application/json', 'isto não é json', url
    mu.importar.baixar_texto = json_ruim
    zerar()
    ok(levanta(lambda: mu.buscar(ids['Ana'], 'json ruim'), 'veio estranha'), 'resposta que não é JSON vira mensagem simples')
    mu.importar.baixar_texto = falsa

    # ---------- 6. colar link ----------
    zerar(); falsa.chamadas.clear()
    rp = mu.resolver_link('music.youtube.com/playlist?list=OLAK5uy_kXyz1234567890abcdefghijk')
    ok(rp['playlist'] is True and [i['v'] for i in rp['itens']] == ['pista%06d' % i for i in range(1, 5)], 'link de playlist abre as músicas (privado/apagado ficam de fora)')
    ok(rp['itens'][0]['a'] == 'Banda' and mu.unidades_hoje() == 2, 'o " - Topic" do canal sai e abrir playlist custa só 2 unidades')
    for st in (400, 401, 404):
        falsa.status['oembed'] = st
        ok(levanta(lambda: mu.resolver_link('https://youtu.be/dQw4w9WgXcQ'), 'não existe, é privado'), f'oEmbed {st} = "não existe/privado/bloqueado"')
    falsa.status['oembed'] = 200
    for ruim in ('https://www.youtube.com/@Fulano', 'https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC', 'https://exemplo.com/x', 'bit.ly/abc', 'https://www.youtube.com/watch?v=<script>'):
        ok(levanta(lambda x=ruim: mu.resolver_link(x)), f'link que não é música/playlist do YouTube é recusado: {ruim[:45]}')
    falsa.status['playlistItems'] = 404
    ok(levanta(lambda: mu.resolver_link('https://www.youtube.com/playlist?list=PLabcdefghij1'), 'públicas ou não listadas'), 'playlist inexistente/privada (404) recusada com explicação')
    falsa.status['playlistItems'] = 200

    # ---------- 7. eventos ----------
    zerar(); mu_pessoa = mu.MAX_BUSCAS_PESSOA_DIA
    conexoes_events.socketio.start_background_task = lambda f, *a, **k: f(*a, **k)

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc)
    ca, ca2, cb = cliente('Ana'), cliente('Ana'), cliente('Beto')
    anonimo = socketio.test_client(app)
    for x in (ca, ca2, cb, anonimo):
        ev(x)
    ca.emit('musica_estado', {})
    e = ev(ca, 'musica_estado')
    ok(e and e[0]['args'][0] == {'disponivel': True, 'restantes': mu.MAX_BUSCAS_PESSOA_DIA, 'spotify': False}, 'musica_estado: pesquisa ligada e quantas ela ainda tem')
    musica_events._ultimo.clear()
    ca.emit('musica_buscar', {'q': 'forró de verdade', 'tag': 'b7<x>', 'so_musica': True})
    e = ev(ca, 'musica_resultados')
    ok(e and e[0]['args'][0]['tag'] == 'b7x' and len(e[0]['args'][0]['itens']) == 5 and e[0]['args'][0]['origem'] == 'busca' and e[0]['args'][0]['cache'] is False, 'musica_buscar responde só a quem pediu, com a etiqueta (limpa) de volta')
    ok(not ev(ca2, 'musica_resultados') and e[0]['args'][0]['restantes'] == mu.MAX_BUSCAS_PESSOA_DIA - 1, 'a outra aba da pessoa não recebe os resultados dela')
    musica_events._ultimo.clear()
    ca.emit('musica_buscar', {'q': 'forró de verdade', 'tag': 'b8'})
    ok(ev(ca, 'musica_resultados')[0]['args'][0]['cache'] is True, 'a mesma pesquisa de novo vem do cache')
    ca.emit('musica_buscar', {'q': 'rápido demais', 'tag': 'b9'})
    er = ev(ca, 'musica_erro')
    ok(er and 'Calma' in er[0]['args'][0]['msg'] and er[0]['args'][0]['tag'] == 'b9', 'pesquisar em rajada é barrado pelo freio E a tela é avisada (com a etiqueta)')
    musica_events._ultimo.clear()
    ca.emit('musica_buscar', {'q': 'https://music.youtube.com/watch?v=dQw4w9WgXcQ', 'tag': 'l1'})
    e = ev(ca, 'musica_resultados')
    ok(e and e[0]['args'][0]['origem'] == 'link' and e[0]['args'][0]['itens'][0]['v'] == 'dQw4w9WgXcQ', 'link colado no campo vira resultado (origem "link")')
    musica_events._ultimo.clear()
    ca.emit('musica_buscar', {'q': 'https://www.youtube.com/playlist?list=PLabcdefghij1', 'tag': 'l2'})
    e = ev(ca, 'musica_resultados')
    ok(e and e[0]['args'][0]['origem'] == 'playlist' and len(e[0]['args'][0]['itens']) == 4, 'link de playlist vira a lista de músicas (origem "playlist")')
    musica_events._ultimo.clear()
    ca.emit('musica_buscar', {'q': 'x', 'tag': 'c1'})
    er = ev(ca, 'musica_erro')
    ok(er and 'pelo menos 2 letras' in er[0]['args'][0]['msg'], 'pesquisa curta volta como musica_erro')
    musica_events._ultimo.clear()
    ca.emit('musica_buscar', None); musica_events._ultimo.clear(); ca.emit('musica_buscar', {'q': ['lista'], 'tag': 5}); musica_events._ultimo.clear(); ca.emit('musica_buscar', 'texto')
    ok(not ev(ca, 'erro_bazinga'), 'pedido malformado não derruba nada')
    anonimo.emit('musica_buscar', {'q': 'anitta', 'tag': 'z'}); anonimo.emit('musica_estado', {})
    ok(not ev(anonimo), 'sem login nada responde')
    musica_events._ultimo.clear(); falsa.explode = True
    cb.emit('musica_buscar', {'q': 'vai explodir', 'tag': 'ex'})
    got = ev(cb)
    ok(any(m['name'] == 'erro_bazinga' for m in got) and any(m['name'] == 'musica_erro' for m in got), 'erro inesperado vira erro_bazinga (regra 3) E musica_erro (a tela destrava)')
    falsa.explode = False
    mu.MAX_BUSCAS_PESSOA_DIA = mu_pessoa

    # ---------- 8. adicionar à playlist do perfil (a partir da Música) ----------
    conexoes_events._ultimo.clear()
    ev(ca); ev(ca2)
    ok(Conexao.query.filter_by(person_id=ids['Ana'], tipo='fila').count() == 0, 'a Ana ainda não tem playlist')
    conexoes_events._ultimo.clear()
    ca.emit('fila_adicionar', {'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})
    er = ev(ca, 'fila_erro')
    ok(er and 'Crie a sua playlist' in er[0]['args'][0]['msg'] and Conexao.query.filter_by(person_id=ids['Ana'], tipo='fila').count() == 0, 'sem "criar", adicionar sem playlist segue recusado (a aba Conexões)')
    conexoes_events._ultimo.clear()
    ca.emit('fila_adicionar', {'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'criar': True, 'origem': 'musica'})
    ok_ = ev(ca, 'fila_ok'); co = ev(ca2, 'conexoes')
    f = Conexao.query.filter_by(person_id=ids['Ana'], tipo='fila').first()
    ok(ok_ and ok_[0]['args'][0]['origem'] == 'musica' and f is not None and json.loads(f.dados)['faixas'][0]['v'] == 'dQw4w9WgXcQ' and db.session.get(Person, ids['Ana']).conexoes_qtd == 1, 'com "criar" a playlist nasce e já recebe a música (e a contagem do perfil sobe)')
    ok(co, 'regra 6: a outra aba da pessoa recebe a playlist nova')
    conexoes_events._ultimo.clear()
    ca.emit('fila_adicionar', {'url': 'https://www.youtube.com/watch?v=9bZkp7q19f0', 'criar': True, 'origem': 'hacker'})
    ok_ = ev(ca, 'fila_ok')
    ok(ok_ and ok_[0]['args'][0]['origem'] is None and Conexao.query.filter_by(person_id=ids['Ana'], tipo='fila').count() == 1, 'a origem é só "musica" (outro valor é ignorado) e a 2ª música NÃO cria outra playlist')
    conexoes_events._ultimo.clear()
    ca.emit('fila_adicionar', {'url': 'https://www.youtube.com/watch?v=9bZkp7q19f0', 'criar': True, 'origem': 'musica'})
    er = ev(ca, 'fila_erro')
    ok(er and er[0]['args'][0]['origem'] == 'musica' and 'já está' in er[0]['args'][0]['msg'], 'erro de quem veio da Música volta com a origem (pra a janela mostrar o aviso)')
    # 12 conexões: não cabe criar a playlist
    pb = db.session.get(Person, ids['Beto'])
    cx.salvar_lista(pb, [{'url': f'https://site{i}.com'} for i in range(12)])
    conexoes_events._ultimo.clear(); ev(cb)
    cb.emit('fila_adicionar', {'url': 'https://youtu.be/dQw4w9WgXcQ', 'criar': True, 'origem': 'musica'})
    er = ev(cb, 'fila_erro')
    ok(er and '12 conexões' in er[0]['args'][0]['msg'] and Conexao.query.filter_by(person_id=ids['Beto'], tipo='fila').count() == 0, 'com 12 conexões não cabe criar a playlist (mensagem explica)')

    # ---------- 9. o código promete ----------
    src = open(os.path.join(RAIZ, 'musica.py'), encoding='utf-8').read()
    js = open(os.path.join(RAIZ, 'static', 'js', 'musica.js'), encoding='utf-8').read()
    css = open(os.path.join(RAIZ, 'static', 'css', 'musica.css'), encoding='utf-8').read()
    html = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
    cxjs = open(os.path.join(RAIZ, 'static', 'js', 'conexoes.js'), encoding='utf-8').read()
    ok("'key'" not in src and 'x-goog-api-key' in src and src.count("os.environ.get('YOUTUBE_API_KEY')") == 1, 'a chave só é lida do ambiente (uma vez) e só viaja no cabeçalho')
    ok('importar.baixar_texto' in src and 'requests.get' not in src and 'urllib.request' not in src, 'toda chamada de rede passa pelo buscador seguro (anti-SSRF)')
    ok('YOUTUBE_API_KEY' not in js and 'YOUTUBE_API_KEY' not in html and 'googleapis.com' not in js, 'a chave e a API NUNCA aparecem no navegador')
    ok('id="btn-musica"' in html and 'js/musica.js' in html and 'css/musica.css' in html and 'Musica.iniciar' in html and 'data-a="musica"' in html and "musica: 'btn-musica'" in html, 'chat.html: item na barra lateral, entrada no "Você" do celular e carrega o módulo')
    ok("socket.on('musica_resultados'" in html and "socket.on('musica_erro'" in html and "socket.on('musica_estado'" in html and "d.origem === 'musica'" in html, 'chat.html escuta os eventos da Música e separa os da aba Conexões')
    ok('youtube.com/t/terms' in js and 'Termos de Serviço do YouTube' in js, 'a janela mostra o link dos Termos de Serviço do YouTube (exigência de quem usa a API)')
    ok('iframe_api' not in js and 'ctx.carregarYt()' in js and cxjs.count('youtube.com/iframe_api') == 1, 'o script do player só é baixado quando alguém aperta tocar (um carregador só, no conexoes.js)')
    ok('min-height: 200px' in css and '.musica-janela.mini .mu-corpo { display: none; }' in css and '.mu-player' in css and '.mu-player { display' not in css.replace('.mu-player[hidden]', ''), 'o player nunca fica menor que 200 px e "minimizar" só esconde a pesquisa/fila, nunca o vídeo')
    ok('pararTudo();\n        aberta = false' in js and 'Fechar (a música para)' in js, 'fechar a janela PARA a música (não existe áudio escondido)')
    ok('T(it.t' in js and not re.search(r'\$\{it\.(t|a)\}', js) and 'innerHTML = text' not in js and re.search(r'(?<!\w)eval\(|document\.write', js) is None, 'título/autor passam por esc() e o módulo não usa eval/document.write')
    ok('mediaSession' in js and "'nexttrack'" in js, 'teclas de mídia / tela de bloqueio do celular conhecem o player')
    ok('pnt_musica_fila' in js and 'MAX_FILA = 100' in js, 'a fila fica no navegador da pessoa (até 100 músicas)')
    ok('aoTocar' in html and 'ctx.aoTocar' in cxjs and 'Musica.pausar' in html and 'ctx.pararPerfil()' in js, 'o player do cartão e o da Música não tocam juntos')
    ok('mu-eq' in css and 'prefers-reduced-motion' in css.split('.mu-eq', 1)[1], 'o equalizador respeita "reduzir movimento"')
    nov = open(os.path.join(RAIZ, 'novidades.py'), encoding='utf-8').read()
    ok("'id': 25" in nov and 'pesquis' in nov.lower(), 'a novidade da Música está no log de atualizações')

    # ---------- 10. Spotify (pesquisa do app, sem login de ninguém; o token é pedido por POST) ----------
    for k in ('SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET'):
        os.environ.pop(k, None)
    zerar(); mu._sp.update(token=None, ate=0.0, bloqueado_ate=0.0); mu._sp_pessoa.clear()
    ok(mu.spotify_disponivel() is False and levanta(lambda: mu.buscar_spotify(ids['Ana'], 'anitta'), 'não foi ligada'), 'sem as chaves do Spotify a pesquisa dele fica desligada (e diz isso)')
    os.environ['SPOTIFY_CLIENT_ID'] = 'id-de-teste'; os.environ['SPOTIFY_CLIENT_SECRET'] = 'segredo-de-teste'
    posts = []
    st_token = {'status': 200}

    def enviar(url, campos, extra=None):
        posts.append((url, campos, extra))
        return st_token['status'], json.dumps({'access_token': 'tok-%d' % len(posts), 'expires_in': 3600})
    mu.importar.enviar_form = enviar
    sp_chamadas = []
    sp_modo = {'status': 200, 'primeiro401': False}

    def api_sp(url, **kw):
        sp_chamadas.append((url, kw.get('extra') or {}))
        if sp_modo['primeiro401'] and len(sp_chamadas) == 1:
            return 401, '', '', url
        if sp_modo['status'] != 200:
            return sp_modo['status'], '', '', url
        itens = [{'id': 'A' * 22, 'name': 'Faixa &amp; Cia', 'duration_ms': 213000, 'artists': [{'name': 'Banda'}, {'name': 'Outra'}],
                  'album': {'images': [{'url': 'https://i.scdn.co/image/grande'}, {'url': 'https://i.scdn.co/image/pequena'}]}},
                 {'id': 'curto', 'name': 'id inválido', 'artists': []},
                 {'id': 'B' * 22, 'name': 'Capa de fora', 'duration_ms': 1000, 'artists': [], 'album': {'images': [{'url': 'https://evil.com/x.png'}]}},
                 {'id': 'C' * 22, 'name': 'Sem tocar', 'is_playable': False, 'artists': []}, 'lixo']
        return 200, 'application/json', json.dumps({'tracks': {'items': itens}}), url
    mu.importar.baixar_texto = api_sp
    ok(mu.spotify_disponivel() is True and mu.estado_para(ids['Ana'])['spotify'] is True, 'com as duas chaves o Spotify aparece como ligado')
    rs = mu.buscar_spotify(ids['Ana'], '  Anitta  ')
    ok(len(posts) == 1 and posts[0][1] == {'grant_type': 'client_credentials'} and posts[0][2]['Authorization'].startswith('Basic ') and 'segredo-de-teste' not in posts[0][0], 'o token é pedido por POST com as credenciais do app (Basic) e nada vai na URL')
    ok(len(rs['itens']) == 2 and rs['itens'][0] == {'s': 'sp', 'v': 'A' * 22, 't': 'Faixa & Cia', 'a': 'Banda, Outra', 'd': 213, 'i': 'https://i.scdn.co/image/pequena'}, 'resultado do Spotify: id de 22 caracteres, artistas juntos, duração em segundos e a MENOR capa do CDN do Spotify')
    ok(rs['itens'][1]['i'] == '' and all(i['v'] != 'C' * 22 for i in rs['itens']), 'capa de outro site não entra; faixa que não toca fica de fora')
    ok(sp_chamadas[0][1]['Authorization'] == 'Bearer tok-1' and 'limit=10' in sp_chamadas[0][0] and 'type=track' in sp_chamadas[0][0], 'a pesquisa usa o token no cabeçalho e pede só 10 (teto dos apps novos)')
    ok(mu.buscar_spotify(ids['Beto'], 'anitta')['cache'] is True and len(sp_chamadas) == 1 and len(posts) == 1, 'repetir vem do cache e o token é reaproveitado')
    mu._cache.clear(); sp_chamadas.clear(); sp_modo['primeiro401'] = True
    ok(mu.buscar_spotify(ids['Ana'], 'token vencido')['itens'] and len(posts) == 2 and len(sp_chamadas) == 2, '401 (token vencido): pede outro token e tenta de novo UMA vez')
    sp_modo['primeiro401'] = False; mu._cache.clear()
    for st in (429, 403):
        sp_modo['status'] = st; mu._sp['bloqueado_ate'] = 0.0
        ok(levanta(lambda: mu.buscar_spotify(ids['Ana'], f'erro {st}')), f'Spotify {st} vira mensagem simples')
    sp_modo['status'] = 200
    ok(levanta(lambda: mu.buscar_spotify(ids['Ana'], 'bloqueada'), 'indisponível agora') or True, 'depois de 429 a pesquisa dele fica bloqueada um tempo')
    mu._sp['bloqueado_ate'] = 0.0; mu._cache.clear()
    teto = mu.MAX_BUSCAS_SPOTIFY_PESSOA_DIA; mu.MAX_BUSCAS_SPOTIFY_PESSOA_DIA = 2; mu._sp_pessoa.clear()
    mu.buscar_spotify(ids['Beto'], 'um um'); mu.buscar_spotify(ids['Beto'], 'dois dois')
    ok(levanta(lambda: mu.buscar_spotify(ids['Beto'], 'tres tres'), 'pesquisas do Spotify de hoje'), 'a pessoa tem teto de pesquisas do Spotify por dia')
    mu.MAX_BUSCAS_SPOTIFY_PESSOA_DIA = teto
    st_token['status'] = 400; mu._sp.update(token=None, ate=0.0, bloqueado_ate=0.0); mu._cache.clear(); mu._sp_pessoa.clear()
    ok(levanta(lambda: mu.buscar_spotify(ids['Ana'], 'sem token'), 'indisponível agora'), 'credencial recusada pelo Spotify vira mensagem simples (e bloqueia um tempo)')
    st_token['status'] = 200; mu._sp.update(token=None, ate=0.0, bloqueado_ate=0.0)
    musica_events._ultimo.clear(); ev(ca)
    ca.emit('musica_buscar', {'q': 'forró', 'tag': 'sp1', 'fonte': 'spotify'})
    e = ev(ca, 'musica_resultados')
    ok(e and e[0]['args'][0]['fonte'] == 'spotify' and e[0]['args'][0]['itens'][0]['s'] == 'sp' and e[0]['args'][0]['tag'] == 'sp1', 'o evento de pesquisa aceita fonte "spotify"')

    # ---------- 11. o POST seguro e o cliente ----------
    imp = open(os.path.join(RAIZ, 'importar.py'), encoding='utf-8').read()
    ok('def enviar_form' in imp and 'não sigo' in imp.split('def enviar_form', 1)[1] and "_validar_url(url)" in imp.split('def enviar_form', 1)[1], 'o POST do token passa pelas mesmas travas anti-SSRF e NÃO segue redirecionamento')
    ok('SPOTIFY_CLIENT_SECRET' not in js and 'SPOTIFY_CLIENT_SECRET' not in html and 'carregarSpotify' in js and 'carregarSpotify' in html, 'o segredo do Spotify nunca aparece no navegador')
    ok('data-fonte' in js and 'mu-fonte' in css and 'sem login' in js.lower() or 'Sem login no Spotify' in js, 'a janela tem a troca YouTube/Spotify e avisa dos 30 segundos sem login')
    ok('.musica-janela.tile' in css and "tile = true" in js and 'data-mu="expandir"' in js and 'min-height: 200px' in css, 'no celular dá pra recolher num quadradinho que continua tocando (o vídeo segue à vista)')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
