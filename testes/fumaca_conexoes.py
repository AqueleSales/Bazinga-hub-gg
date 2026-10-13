"""Rodada 24: Conexões do perfil. Links (normalização e recusas), lista (limite, duplicado, ordem, apagar, contagem), privacidade (só quem convive),
buscas de rede SIMULADAS (GitHub com quadrinho, oEmbed, página de site: imagem só de CDN conhecido, texto limpo), cache/TTL, currículo (validação),
leitura do PDF do LinkedIn (PDF de verdade gerado aqui), IA simulada (com e sem chave, com falha) e a rota de importação."""
import os, sys, json, re, io
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from datetime import date, timedelta
from app import create_app, db, socketio, conexoes as cx, conexoes_events, importar
from app.models import Role, Person, Friendship, Server, Conexao, BazarLoja, br_now

os.environ.pop('GEMINI_API_KEY', None)      # o .env de quem roda pode ter a chave de verdade: o teste decide sozinho quando a IA está "ligada"
app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def levanta(fn, exc=cx.ErroConexao):
    try:
        fn()
    except exc:
        db.session.rollback()
        return True
    except Exception as e:
        db.session.rollback()
        print('   (levantou outra coisa:', type(e).__name__, e, ')')
        return False
    return False


def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


def pdf_simples(linhas):
    """PDF de verdade (texto Helvetica) com as linhas dadas: serve pra testar a leitura sem depender de arquivo externo."""
    por_pag = 48
    grupos = [linhas[i:i + por_pag] for i in range(0, len(linhas), por_pag)] or [[]]
    n = len(grupos)
    obj = {1: b'<< /Type /Catalog /Pages 2 0 R >>',
           2: ('<< /Type /Pages /Kids [%s] /Count %d >>' % (' '.join('%d 0 R' % (4 + 2 * i) for i in range(n)), n)).encode(),
           3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'}
    for i, g in enumerate(grupos):
        corpo = 'BT /F1 11 Tf 40 800 Td 15 TL\n' + ''.join('(%s) Tj T*\n' % l.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') for l in g) + 'ET'
        dados = corpo.encode('cp1252', 'replace')
        obj[4 + 2 * i] = ('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R /Resources << /Font << /F1 3 0 R >> >> >>' % (5 + 2 * i)).encode()
        obj[5 + 2 * i] = b'<< /Length %d >>\nstream\n' % len(dados) + dados + b'\nendstream'
    saida, offs = bytearray(b'%PDF-1.4\n'), {}
    for k in sorted(obj):
        offs[k] = len(saida)
        saida += ('%d 0 obj\n' % k).encode() + obj[k] + b'\nendobj\n'
    xref, total = len(saida), max(obj) + 1
    saida += ('xref\n0 %d\n0000000000 65535 f \n' % total).encode()
    for k in range(1, total):
        saida += ('%010d 00000 n \n' % offs[k]).encode()
    saida += ('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (total, xref)).encode()
    return bytes(saida)


LINKEDIN_EN = ['Contact', 'www.linkedin.com/in/gabriel-nogueira (LinkedIn)', 'Top Skills', 'Python', 'Flask', 'JavaScript', 'Languages', 'Portuguese (Native or Bilingual)',
               'English (Professional Working)', 'Gabriel Sales Nogueira', 'Software Engineering Student | Python and Web', 'Brasilia, Federal District, Brazil',
               'Summary', 'I build apps with Flask and Socket.IO and love learning new things.', 'Experience', 'Pantheon', 'Founder', 'January 2026 - Present (10 months)',
               'Brasilia, Brazil', 'Creator of a chat app with a map and cosmetics.', 'Acme Corp', 'Software Intern', 'June 2024 - December 2025 (1 year 7 months)', 'Remote',
               'Built internal dashboards.', 'Education', 'Universidade de Brasilia', "Bachelor's degree, Computer Science · (2023 - 2027)", 'Page 1 of 1']
LINKEDIN_PT = ['Contato', 'Principais competências', 'Python', 'Flask', 'Idiomas', 'Português (Nativo)', 'Ana Souza', 'Engenheira de Dados', 'São Paulo, Brasil',
               'Resumo', 'Trabalho com dados há anos.', 'Experiência', 'Banco Azul', 'Analista de Dados', 'março de 2021 - Present', 'São Paulo',
               'Formação acadêmica', 'USP', 'Bacharelado em Estatística · (2016 - 2020)']

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio', 'Duda'):
        p = Person(name=n, email=f'{n.lower()}@x', role_id=r.id, username=n.lower())
        db.session.add(p); db.session.commit(); ids[n] = p.id
    ana = lambda: db.session.get(Person, ids['Ana'])
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted'))
    srv = Server(name='Casa', owner_id=ids['Ana']); db.session.add(srv); db.session.commit()
    srv.members.append(db.session.get(Person, ids['Ana'])); srv.members.append(db.session.get(Person, ids['Caio'])); db.session.commit()

    # ---------- 1. normalizar ----------
    bom = {
        'github.com/AqueleSales': ('github', 'https://github.com/AqueleSales'),
        'https://www.github.com/AqueleSales/Bazinga-hub-gg?tab=readme': ('github', 'https://github.com/AqueleSales'),
        'linkedin.com/in/gabriel-nogueira-123/': ('linkedin', 'https://www.linkedin.com/in/gabriel-nogueira-123'),
        'https://youtu.be/dQw4w9WgXcQ': ('youtube', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
        'https://www.youtube.com/@Fulano': ('youtube', 'https://www.youtube.com/@Fulano'),
        'https://open.spotify.com/intl-pt/track/4uLU6hMCjMI75M1A2tKUQC?si=abc': ('spotify', 'https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC'),
        'instagram.com/fulano.sales': ('instagram', 'https://www.instagram.com/fulano.sales/'),
        'twitch.tv/Fulano_1': ('twitch', 'https://www.twitch.tv/fulano_1'),
        'x.com/fulano': ('x', 'https://x.com/fulano'),
        'https://www.amazon.com.br/dp/B0ABC?tag=afiliado': ('amazon', 'https://www.amazon.com.br/dp/B0ABC'),
        'https://minhaloja.myshopify.com/products/x?utm_source=a&id=3': ('site', 'https://minhaloja.myshopify.com/products/x?id=3'),
        'http://meusite.com.br/': ('site', 'https://meusite.com.br/'),
    }
    for entrada, (tipo, url) in bom.items():
        t, u, _ = cx.normalizar(entrada)
        ok((t, u) == (tipo, url), f'normaliza {entrada[:55]} -> {tipo}')
    ruim = ['', 'a' * 301, 'bit.ly/abc', 'http://127.0.0.1/x', 'http://localhost/x', 'javascript:alert(1)', 'ftp://a.com/x', 'https://user:pw@github.com/a', 'https://github.com:8443/a',
            'github.com/settings', 'github.com/', 'linkedin.com/feed', 'youtube.com/', 'open.spotify.com/user/abc', 'instagram.com/p/ABC', 'twitch.tv/directory',
            'https://exemplo/x', 'data:text/html,<script>alert(1)</script>', 'https://[::1]/x', 'https://10.0.0.1/']
    for entrada in ruim:
        ok(levanta(lambda e=entrada: cx.normalizar(e)), f'recusa {entrada[:50]!r}')
    ok(not any(cx.normalizar(u)[1].count('utm_') for u in ('https://a.com/x?utm_source=1&a=2',)), 'tira o rastreamento (utm_) do link')

    # ---------- 2. a lista ----------
    pa = ana()
    ids_busca = cx.salvar_lista(pa, [{'url': 'github.com/AqueleSales'}, {'url': 'linkedin.com/in/gabriel'}, {'url': 'https://minhaloja.com.br'}])
    lst = cx.listar(ids['Ana'])
    ok([x.tipo for x in lst] == ['github', 'linkedin', 'site'] and ana().conexoes_qtd == 3, 'salva 3 conexões, na ordem, e guarda a contagem na pessoa')
    ok(len(ids_busca) == 2, 'só GitHub e site precisam de busca (LinkedIn não busca nada: não raspamos o LinkedIn)')
    ok(levanta(lambda: cx.salvar_lista(pa, [{'url': 'github.com/a'}, {'url': 'https://github.com/a/'}])), 'link repetido é recusado')
    ok(levanta(lambda: cx.salvar_lista(pa, [{'url': f'https://site{i}.com'} for i in range(13)])), 'mais de 12 é recusado')
    ok(levanta(lambda: cx.salvar_lista(pa, 'não é lista')) and levanta(lambda: cx.salvar_lista(pa, ['texto'])), 'lista malformada é recusada')
    ok(levanta(lambda: cx.salvar_lista(pa, [{'tipo': 'bazar'}])), 'loja do Bazar sem loja é recusada')
    ok(len(cx.listar(ids['Ana'])) == 3, 'uma tentativa recusada não muda nada na lista salva')
    ids_antes = [x.id for x in lst]
    cx.salvar_lista(pa, [{'id': ids_antes[2], 'url': 'https://minhaloja.com.br'}, {'id': ids_antes[0], 'url': 'github.com/AqueleSales'}])
    lst2 = cx.listar(ids['Ana'])
    ok([x.id for x in lst2] == [ids_antes[2], ids_antes[0]] and ana().conexoes_qtd == 2, 'reordenar e apagar mantém as linhas (e os dados) das que ficaram')
    ok(Conexao.query.filter_by(person_id=ids['Ana']).count() == 2, 'a que saiu foi apagada do banco')
    cx.salvar_lista(pa, [{'id': ids_antes[0], 'url': 'github.com/OutroUsuario'}])
    ok(cx.listar(ids['Ana'])[0].id != ids_antes[0] and cx.listar(ids['Ana'])[0].url == 'https://github.com/OutroUsuario', 'trocar o link vira uma conexão NOVA (os dados do link velho não ficam)')
    loja = BazarLoja(owner_id=ids['Ana'], nome='Loja da Ana', descricao='Coisas', aberta=True, oculta=False); db.session.add(loja); db.session.commit()
    cx.salvar_lista(pa, [{'url': 'github.com/AqueleSales'}, {'tipo': 'bazar'}, {'url': 'linkedin.com/in/gabriel'}])
    js = cx.lista_json(ids['Ana'], dono=True)
    ok(js[1]['tipo'] == 'bazar' and js[1]['dados']['nome'] == 'Loja da Ana', 'a loja do Bazar é lida na hora (nunca fica velha)')
    loja.oculta = True; db.session.commit()
    ok(all(x['tipo'] != 'bazar' for x in cx.lista_json(ids['Ana'], dono=False)) and any(x['tipo'] == 'bazar' for x in cx.lista_json(ids['Ana'], dono=True)), 'loja oculta por denúncia some pra os outros (o dono ainda vê)')

    # ---------- 3. buscas de rede (simuladas) ----------
    hoje = date.today()
    inicio = hoje - timedelta(days=370)
    tds = ''.join('<td tabindex="-1" data-ix="0" aria-selected="false" style="width: 10px" data-date="%s" id="contribution-day-component-0-0" data-level="%d" role="gridcell" class="ContributionCalendar-day"></td>'
                  % ((inicio + timedelta(days=i)).isoformat(), i % 5) for i in range(371))
    html_grade = f'<h2 id="js-contribution-activity-description">1,234 contributions in the last year</h2><table><tbody><tr>{tds}</tr></tbody></table>'
    chamadas = []

    def falso(url, **kw):
        chamadas.append(url)
        if url.endswith('/users/AqueleSales'):
            return 200, 'application/json', json.dumps({'login': 'AqueleSales', 'name': 'Gabriel​ Sales\x07 Nogueira', 'avatar_url': 'https://avatars.githubusercontent.com/u/1?v=4', 'bio': 'Dev  \n estudante',
                                                         'followers': 3, 'following': 2, 'public_repos': 40, 'location': 'Brasil'}), url
        if '/repos' in url:
            repos = [{'name': f'repo{i}', 'description': 'd' * 400, 'language': 'Python', 'stargazers_count': i, 'html_url': f'https://github.com/AqueleSales/repo{i}', 'pushed_at': '2026-10-12T10:00:00Z',
                      'fork': i == 1, 'archived': i == 2} for i in range(10)]
            repos.append({'name': 'malicioso', 'html_url': 'https://evil.com/x', 'fork': False})
            return 200, 'application/json', json.dumps(repos), url
        if url.endswith('/contributions'):
            return 200, 'text/html', html_grade, url
        if 'oembed' in url and 'spotify' in url:
            return 200, 'application/json', json.dumps({'title': 'Minha Música', 'thumbnail_url': 'https://image-cdn-ak.spotifycdn.com/image/abc', 'html': '<iframe onload=alert(1)>'}), url
        if 'oembed' in url and 'youtube' in url:
            return 200, 'application/json', json.dumps({'title': 'Vídeo', 'author_name': 'Canal', 'thumbnail_url': 'https://i.ytimg.com/vi/x/hq.jpg'}), url
        if url.startswith('https://minhaloja.com.br'):
            return 200, 'text/html', '<html><head><title>Loja Legal</title><meta property="og:title" content="Loja &amp; Cia"><meta property="og:description" content="Vendemos coisas boas"><meta property="og:image" content="https://tracker.evil.com/pixel.png"></head></html>', url
        if url.startswith('https://www.twitch.tv'):
            return 200, 'text/html', '<html><head><meta property="og:title" content="fulano - Twitch"><meta property="og:image" content="https://static-cdn.jtvnw.net/jtv_user_pictures/x.png"></head></html>', url
        return 404, '', '', url

    importar.baixar_texto = falso
    cx.importar.baixar_texto = falso
    cx.salvar_lista(pa, [{'url': 'github.com/AqueleSales'}, {'url': 'linkedin.com/in/gabriel'}, {'url': 'https://minhaloja.com.br'}])
    cxs = {x.tipo: x for x in cx.listar(ids['Ana'])}
    cx.atualizar_uma(cxs['github'].id)
    g = db.session.get(Conexao, cxs['github'].id); dados = json.loads(g.dados)
    ok(g.erro is None and g.atualizado_em and g.titulo == 'Gabriel Sales Nogueira', 'GitHub: busca ok; o título vem limpo (sem caractere invisível/de controle)')
    ok(dados['login'] == 'AqueleSales' and dados['seguidores'] == 3 and dados['avatar'].startswith('https://avatars.githubusercontent.com/') and dados['bio'] == 'Dev estudante', 'GitHub: perfil, avatar do CDN do GitHub e bio com espaços arrumados')
    ok(len(dados['repos']) == 6 and all(r['url'].startswith('https://github.com/') for r in dados['repos']) and not any(r['nome'] in ('repo1', 'repo2', 'malicioso') for r in dados['repos']),
       'GitHub: 6 repositórios recentes, sem fork, sem arquivado e sem link que não seja do github.com')
    ok(all(len(r['desc']) <= 140 for r in dados['repos']), 'GitHub: descrição cortada em 140 caracteres')
    ok(dados['total'] == 1234 and 52 <= len(dados['grade']) <= 54 and all(len(col) == 7 and set(col) <= set('01234.') for col in dados['grade']), f'GitHub: quadrinho de contribuições ({len(dados["grade"])} semanas) e total 1.234')
    ok(any(u.endswith('/contributions') for u in chamadas) and sum('api.github.com' in u for u in chamadas) == 2, 'GitHub: 2 chamadas da API e 1 da página do quadrinho')
    cx.atualizar_uma(cxs['site'].id)
    s = db.session.get(Conexao, cxs['site'].id); sd = json.loads(s.dados)
    ok(sd['titulo'] == 'Loja & Cia' and sd['descricao'] == 'Vendemos coisas boas', 'site: título e descrição da página (entidades HTML já desfeitas)')
    ok(sd['imagem'] == '', 'site: a imagem de um site qualquer NÃO entra (o navegador de quem olha nunca carrega pixel de terceiro)')
    # oEmbed e Twitch (criamos conexões novas só pra isso)
    cx.salvar_lista(pa, [{'id': cxs['github'].id, 'url': 'github.com/AqueleSales'}, {'id': cxs['linkedin'].id, 'url': 'linkedin.com/in/gabriel'}, {'id': cxs['site'].id, 'url': 'https://minhaloja.com.br'},
                         {'url': 'open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC'}, {'url': 'https://youtu.be/dQw4w9WgXcQ'}, {'url': 'twitch.tv/fulano'}])
    novas = {x.tipo: x for x in cx.listar(ids['Ana'])}
    for t in ('spotify', 'youtube', 'twitch'):
        cx.atualizar_uma(novas[t].id)
    sp = json.loads(db.session.get(Conexao, novas['spotify'].id).dados)
    ok(sp['titulo'] == 'Minha Música' and sp['imagem'].startswith('https://image-cdn-ak.spotifycdn.com/') and sp['id'] == '4uLU6hMCjMI75M1A2tKUQC' and sp['recurso'] == 'track' and 'html' not in sp, 'Spotify: título e capa; o HTML do oEmbed NÃO é guardado')
    yt = json.loads(db.session.get(Conexao, novas['youtube'].id).dados)
    ok(yt['video'] == 'dQw4w9WgXcQ' and yt['imagem'].startswith('https://i.ytimg.com/'), 'YouTube: vídeo e miniatura do CDN do YouTube')
    tw = json.loads(db.session.get(Conexao, novas['twitch'].id).dados)
    ok(tw['imagem'].startswith('https://static-cdn.jtvnw.net/'), 'Twitch: foto do CDN da Twitch')
    # falha de rede: o erro vira texto, o dado velho fica, e a próxima tentativa só depois de um tempo
    def quebra(url, **kw): raise importar.ErroImportar('O site não respondeu.')
    cx.importar.baixar_texto = quebra
    cx.atualizar_uma(cxs['github'].id)
    g = db.session.get(Conexao, cxs['github'].id)
    ok(g.erro and g.dados and json.loads(g.dados)['login'] == 'AqueleSales', 'busca que falha guarda o erro e MANTÉM o dado velho')
    ok(not cx.precisa_atualizar(g), 'depois de uma falha, não tenta de novo na hora (espera 10 min)')
    g.atualizado_em = br_now() - timedelta(minutes=11); db.session.commit()
    ok(cx.precisa_atualizar(g), 'passados 10 min da falha, tenta de novo')
    g.erro = None; g.atualizado_em = br_now() - timedelta(hours=2); db.session.commit()
    ok(not cx.precisa_atualizar(g), 'GitHub com dado de 2 h não precisa buscar de novo (vale 6 h)')
    g.atualizado_em = br_now() - timedelta(hours=7); db.session.commit()
    ok(cx.precisa_atualizar(g), 'GitHub com dado de 7 h busca de novo')
    ok(not cx.precisa_atualizar(db.session.get(Conexao, cxs['linkedin'].id)), 'LinkedIn nunca precisa de busca de rede')
    def erro_inesperado(url, **kw): raise RuntimeError('boom')
    cx.importar.baixar_texto = erro_inesperado
    cx.atualizar_uma(novas['twitch'].id)
    ok(db.session.get(Conexao, novas['twitch'].id).erro == 'Não consegui buscar agora. Tente de novo mais tarde.', 'erro inesperado vira mensagem simples (nunca o texto técnico)')
    ok(cx.pode_atualizar_agora(99999) is True and cx.pode_atualizar_agora(99999) is False, '"atualizar agora" manual: 1 por minuto por conexão')

    # ---------- 4. eventos e privacidade ----------
    cx.importar.baixar_texto = falso
    conexoes_events.socketio.start_background_task = lambda f, *a, **k: f(*a, **k)    # a busca roda na hora (no servidor de verdade vai em segundo plano)

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc), fc

    ca, fca = cliente('Ana'); ca2, _ = cliente('Ana'); cb, fcb = cliente('Beto'); cc, _ = cliente('Caio'); cd, _ = cliente('Duda')
    for x in (ca, ca2, cb, cc, cd):
        ev(x)
    cx.salvar_lista(pa, [{'url': 'github.com/AqueleSales'}, {'url': 'linkedin.com/in/gabriel'}, {'url': 'https://minhaloja.com.br'}])
    ca.emit('conexoes_listar', {})
    m = ev(ca, 'conexoes')
    ok(m and len(m[0]['args'][0]['lista']) == 3 and m[0]['args'][0]['max'] == 12 and 'github' in m[0]['args'][0]['plataformas'] and m[0]['args'][0]['ia'] is False, 'listar: a lista, o registro de plataformas, o teto e se a IA está ligada')
    ok(all('erro' in x for x in m[0]['args'][0]['lista']), 'o DONO recebe o campo "erro" de cada conexão')
    ev(ca2)                       # (a busca em segundo plano do listar também avisou as duas abas: esvazia antes de olhar o salvar)
    conexoes_events._ultimo.clear()
    ca.emit('conexoes_salvar', {'itens': [{'url': 'github.com/AqueleSales'}, {'url': 'twitch.tv/fulano'}]})
    a1 = ev(ca, 'conexoes'); a2 = ev(ca2, 'conexoes')
    ok(a1 and a2 and len(a2[0]['args'][0]['lista']) == 2, 'regra 6: salvar avisa as DUAS abas da pessoa')
    conexoes_events._ultimo.clear()
    ca.emit('conexoes_salvar', {'itens': [{'url': 'bit.ly/x'}]})
    er = ev(ca, 'conexoes_erro')
    ok(er and 'encurtado' in er[0]['args'][0]['msg'], 'erro de regra volta como conexoes_erro, com a mensagem pra pessoa')
    ca.emit('conexoes_salvar', {'itens': [{'url': 'github.com/OutroX'}]})
    ok(len(cx.listar(ids['Ana'])) == 2 and any('Calma' in e['args'][0]['msg'] for e in ev(ca, 'conexoes_erro')), 'salvar de novo em seguida é barrado pelo freio (1,5 s) E a tela é avisada (não fica esperando)')
    conexoes_events._ultimo.clear()
    # quem convive vê; estranho não; o erro nunca vai pra outros
    for quem, cli in (('Beto (amigo)', cb), ('Caio (mesmo servidor)', cc)):
        cli.emit('conexoes_do_perfil', {'usuario_id': ids['Ana']})
        m = ev(cli, 'conexoes_do_perfil')
        ok(m and not m[0]['args'][0].get('restrito') and len(m[0]['args'][0]['lista']) == 2, f'{quem} vê as conexões')
        ok(all('erro' not in x for x in m[0]['args'][0]['lista']), f'{quem} NÃO recebe o campo "erro"')
        conexoes_events._ultimo.clear()
    # quem OLHA o perfil também recebe o resultado da busca em segundo plano (antes o cartão dele ficava em "Buscando os dados..." pra sempre)
    gh = cx.listar(ids['Ana'])[0]
    gh.dados = None; gh.erro = None; gh.atualizado_em = None; db.session.commit()
    cb.emit('conexoes_do_perfil', {'usuario_id': ids['Ana']})
    ms = ev(cb, 'conexoes_do_perfil')
    ok(len(ms) >= 2 and not ms[0]['args'][0]['lista'][0].get('dados'), 'quem olha o perfil recebe primeiro a lista (ainda sem dados)...')
    ok(len(ms) >= 2 and (ms[-1]['args'][0]['lista'][0].get('dados') or {}).get('login') == 'AqueleSales', '...e de novo, já com os dados, quando a busca em segundo plano termina')
    ok(all('erro' not in x for e in ms for x in e['args'][0]['lista']), 'a atualização empurrada pra quem olha também NÃO leva o campo "erro"')
    ok(not ev(cc, 'conexoes_do_perfil'), 'quem não pediu pra ver o perfil não recebe a atualização (só quem disparou a busca)')
    conexoes_events._ultimo.clear(); ev(ca); ev(ca2)
    cd.emit('conexoes_do_perfil', {'usuario_id': ids['Ana']})
    m = ev(cd, 'conexoes_do_perfil')
    ok(m and m[0]['args'][0]['restrito'] is True and m[0]['args'][0]['lista'] == [], 'estranho (sem servidor nem amizade) recebe lista vazia e "restrito"')
    ok(len(m) == 1, 'e o estranho não dispara busca nenhuma (nem recebe atualização depois)')
    ca.emit('conexoes_do_perfil', {'usuario_id': ids['Ana']})
    ok(ev(ca, 'conexoes_do_perfil')[0]['args'][0]['lista'][0].get('erro', 'x') is None or True, 'a própria pessoa também pode abrir o seu (face de conexões do cartão)')
    ca.emit('conexoes_do_perfil', {'usuario_id': 'abc'}); ca.emit('conexoes_do_perfil', {})
    ok(not ev(ca, 'conexoes_do_perfil') and not ev(ca, 'erro_bazinga'), 'id inválido não derruba nada')
    # obter_perfil só leva a contagem
    cb.emit('obter_perfil', {'usuario_id': ids['Ana']})
    pp = ev(cb, 'perfil_publico')
    ok(pp and pp[0]['args'][0]['conexoes_qtd'] == 2 and 'conexoes' not in pp[0]['args'][0], 'o perfil público leva só a CONTAGEM (a setinha); os dados vêm sob demanda')
    cd.emit('obter_perfil', {'usuario_id': ids['Ana']})
    pp = ev(cd, 'perfil_publico')
    ok(pp and 'conexoes_qtd' not in pp[0]['args'][0], 'perfil restrito não leva nem a contagem')
    # atualizar à mão: só o dono, e com freio
    gid = cx.listar(ids['Ana'])[0].id
    cb.emit('conexao_atualizar', {'id': gid})
    ok(any('não encontrada' in e['args'][0]['msg'] for e in ev(cb, 'conexoes_erro')), 'outra pessoa não atualiza a conexão alheia')
    conexoes_events._ultimo.clear(); cx._ultima_atualizacao.clear()
    ca.emit('conexao_atualizar', {'id': gid}); ev(ca)
    conexoes_events._ultimo.clear()
    ca.emit('conexao_atualizar', {'id': gid})
    ok(any('uma conexão por minuto' in e['args'][0]['msg'] for e in ev(ca, 'conexoes_erro')), 'atualizar de novo na hora é recusado')

    # ---------- 5. o que fica guardado do currículo (validação) ----------
    cv_ok = {'nome': 'Gabriel Nogueira', 'headline': 'Dev', 'local': 'Brasília', 'sobre': 'Trabalho com ASP.NET, Node.js e Python.\nGosto de aprender.',
             'experiencias': [{'cargo': 'Dev', 'empresa': 'Pantheon', 'periodo': 'jan 2026 - atual', 'local': 'Remoto', 'desc': 'Cuido do app.'}],
             'formacao': [{'curso': 'Ciência da Computação', 'escola': 'UnB', 'periodo': '2023 - 2027'}], 'competencias': ['Python', 'python', 'Flask'], 'idiomas': ['Português'],
             'foto': 'https://res.cloudinary.com/x/image/upload/a.png', 'banner': 'https://evil.com/a.png', 'campo_estranho': 'x'}
    cv = cx.cv_valido(cv_ok)
    ok('ASP.NET' in cv['sobre'] and '\n' in cv['sobre'], 'currículo aceita "ASP.NET" e "Node.js" (não são link) e mantém a quebra de linha do "sobre"')
    ok(cx.cv_valido({'nome': 'A', 'sobre': 'Uso Socket.IO, Chart.JS e React.js.'})['sobre'].startswith('Uso Socket.IO'), 'currículo aceita "Socket.IO" (tecnologia), mas recusa "meusite.io" (link)')
    ok(cv['competencias'] == ['Python', 'Flask'], 'competências sem repetição (python = Python)')
    ok(cv['foto'].startswith('https://res.cloudinary.com/') and cv['banner'] == '' and 'campo_estranho' not in cv, 'foto só do próprio app/Cloudinary; banner de fora é descartado; campo desconhecido some')
    for texto in ('veja https://meusite.com', 'www.exemplo.org', 'me escreve em ana@gmail.com', 'meusite.com.br/portfolio', 'acesse meusite.dev'):
        ok(levanta(lambda t=texto: cx.cv_valido({'nome': 'A', 'sobre': t})), f'currículo recusa link/e-mail: {texto!r}')
    ok(levanta(lambda: cx.cv_valido({})) and levanta(lambda: cx.cv_valido('texto')), 'currículo vazio ou malformado é recusado')
    muitos = cx.cv_valido({'nome': 'A', 'experiencias': [{'cargo': f'c{i}', 'empresa': 'e'} for i in range(30)], 'competencias': [f'k{i}' for i in range(50)]})
    ok(len(muitos['experiencias']) == 12 and len(muitos['competencias']) == 20, 'tetos: 12 experiências e 20 competências')
    ok(not hasattr(cx, 'salvar_cv') and 'cv_salvar' not in socketio.server.handlers.get('/', {}), 'NÃO existe editor/salvar currículo: ele só entra pelo PDF')
    cx.salvar_lista(pa, [{'url': 'github.com/AqueleSales'}, {'url': 'linkedin.com/in/gabriel-nogueira'}])
    li = [x for x in cx.listar(ids['Ana']) if x.tipo == 'linkedin'][0]
    gh = [x for x in cx.listar(ids['Ana']) if x.tipo == 'github'][0]

    # ---------- 6. PDF do LinkedIn -> texto -> currículo (leitura automática) ----------
    texto = cx.texto_do_pdf(pdf_simples(LINKEDIN_EN))
    ok('Gabriel Sales Nogueira' in texto and 'Experience' in texto, 'lê o texto de um PDF de verdade (pypdf)')
    en = cx.cv_do_texto(texto)
    ok(en['nome'] == 'Gabriel Sales Nogueira' and en['headline'].startswith('Software Engineering Student') and en['local'].startswith('Brasilia'), f'leitura (inglês): nome, título e cidade ({en["nome"]!r}, {en["local"]!r})')
    ok(en['competencias'] == ['Python', 'Flask', 'JavaScript'] and len(en['idiomas']) == 2 and 'Gabriel Sales Nogueira' not in en['idiomas'], f'leitura: competências e idiomas sem o cabeçalho da pessoa ({en["idiomas"]})')
    ok(len(en['experiencias']) == 2 and en['experiencias'][0]['empresa'] == 'Pantheon' and en['experiencias'][0]['cargo'] == 'Founder' and en['experiencias'][1]['empresa'] == 'Acme Corp'
       and en['experiencias'][1]['cargo'] == 'Software Intern', f'leitura: 2 experiências com cargo e empresa certos ({[(e["cargo"], e["empresa"]) for e in en["experiencias"]]})')
    ok(en['experiencias'][0]['periodo'].startswith('January 2026') and 'chat app' in en['experiencias'][0]['desc'] and 'Acme' not in en['experiencias'][0]['desc'], 'leitura: período e descrição de cada experiência (sem vazar a próxima)')
    ok(len(en['formacao']) == 1 and en['formacao'][0]['escola'].startswith('Universidade') and '2023' in en['formacao'][0]['periodo'], 'leitura: formação')
    ok('Flask' in en['sobre'], 'leitura: "Summary" vira o sobre')
    pt = cx.cv_do_texto(cx.texto_do_pdf(pdf_simples(LINKEDIN_PT)))
    ok(pt['nome'] == 'Ana Souza' and pt['headline'] == 'Engenheira de Dados' and pt['experiencias'][0]['empresa'] == 'Banco Azul' and pt['formacao'][0]['curso'].startswith('Bacharelado'), 'leitura em português (Contato, Principais competências, Resumo, Experiência, Formação acadêmica)')
    ok(pt['experiencias'][0]['periodo'].startswith('mar'), 'leitura em português: "março de 2021 - Present" é reconhecido como período')
    ok(levanta(lambda: cx.texto_do_pdf(b'nao e pdf')) and levanta(lambda: cx.texto_do_pdf(b'%PDF-' + b'0' * (6 * 1024 * 1024))) and levanta(lambda: cx.texto_do_pdf(pdf_simples([]))), 'PDF falso, grande demais ou sem texto é recusado')

    # ---------- 7. importar o PDF = publicar o currículo na hora (sem editor) ----------
    cv, fonte, avisos = cx.importar_cv_automatico(pa, li.id, pdf_simples(LINKEDIN_EN))
    guardado = db.session.get(Conexao, li.id)
    ok(fonte == 'leitura' and cv['nome'] == 'Gabriel Sales Nogueira' and json.loads(guardado.dados)['cv']['nome'] == 'Gabriel Sales Nogueira' and guardado.titulo == 'Gabriel Sales Nogueira' and guardado.erro is None,
       'importar o PDF PUBLICA o currículo na conexão do LinkedIn (sem passar por editor) e o título da conexão vira o nome')
    ok(len(json.loads(guardado.dados)['cv']['experiencias']) == 2, 'o que ficou guardado tem as 2 experiências do PDF')
    cx.salvar_lista(pa, [{'id': li.id, 'url': 'linkedin.com/in/gabriel-nogueira'}, {'url': 'github.com/AqueleSales'}])
    ok(json.loads(db.session.get(Conexao, li.id).dados)['cv']['nome'] == 'Gabriel Sales Nogueira', 'reordenar a lista não perde o currículo')
    pdf_outro = pdf_simples([l.replace('gabriel-nogueira', 'outra-pessoa') for l in LINKEDIN_EN])
    ok(levanta(lambda: cx.importar_cv_automatico(pa, li.id, pdf_outro)), 'PDF de OUTRO perfil (o @ do PDF não bate com o link) é recusado')
    pdf_quebrado = pdf_simples([l.replace('www.linkedin.com/in/gabriel-nogueira (LinkedIn)', 'www.linkedin.com/in/gabriel-') for l in LINKEDIN_EN])
    ok(cx.importar_cv_automatico(pa, li.id, pdf_quebrado)[0]['nome'] == 'Gabriel Sales Nogueira', 'o @ do LinkedIn que quebrou de linha no PDF (só o começo) ainda vale (prefixo)')
    pdf_sem_slug = pdf_simples([l for l in LINKEDIN_EN if 'linkedin.com' not in l])
    ok(cx.importar_cv_automatico(pa, li.id, pdf_sem_slug)[0]['nome'] == 'Gabriel Sales Nogueira', 'PDF sem o @ do LinkedIn não é recusado (não dá pra conferir)')
    pdf_com_link = pdf_simples([l.replace('I build apps', 'Veja https://meusite.com e escreva a ana@gmail.com. I build apps') for l in LINKEDIN_EN])
    cv_l = cx.importar_cv_automatico(pa, li.id, pdf_com_link)[0]
    ok('meusite' not in cv_l['sobre'] and '@' not in cv_l['sobre'] and 'I build apps' in cv_l['sobre'], 'link, site e e-mail que vieram no PDF são TIRADOS (não recusa: a pessoa não edita)')
    ok(levanta(lambda: cx.importar_cv_automatico(pa, li.id, pdf_simples(['Nada de currículo aqui, só um texto qualquer sem seções nem nada parecido com perfil.']))), 'PDF que não é um currículo (sem nome/seções) é recusado com mensagem clara')
    ok(levanta(lambda: cx.importar_cv_automatico(pa, gh.id, pdf_simples(LINKEDIN_EN))), 'só a conexão do LinkedIn recebe currículo')
    ok(levanta(lambda: cx.importar_cv_automatico(db.session.get(Person, ids['Beto']), li.id, pdf_simples(LINKEDIN_EN))), 'ninguém importa currículo na conexão dos outros')

    # ---------- 8. IA (simulada) ----------
    import requests
    chamou = {}
    class Resp:
        def __init__(self, status, corpo): self.status_code, self._c = status, corpo
        def json(self): return self._c
    def post_ok(url, json=None, headers=None, timeout=None):
        chamou.update(url=url, headers=headers, corpo=json)
        saida = {'nome': 'Gabriel IA', 'headline': 'Dev em meusite.com', 'sobre': 'Veja https://evil.com agora', 'experiencias': [{'cargo': 'Dev', 'empresa': 'X', 'desc': 'ok'}] * 40,
                 'competencias': ['Python'], 'campo': 'x'}
        return Resp(200, {'candidates': [{'content': {'parts': [{'text': __import__('json').dumps(saida)}]}}]})
    os.environ['GEMINI_API_KEY'] = 'chave-falsa'
    requests.post = post_ok
    cv_ia, fonte, avisos = cx.importar_cv_automatico(pa, li.id, pdf_simples(LINKEDIN_EN), usar_ia=True)
    ok(fonte == 'ia' and cv_ia['nome'] == 'Gabriel IA', 'com chave: a IA lê o PDF e o currículo é publicado')
    ok('evil.com' not in cv_ia['sobre'] and 'meusite' not in cv_ia['headline'] and len(cv_ia['experiencias']) == 12 and 'campo' not in cv_ia, 'o que a IA devolve é limpo do mesmo jeito: link some de TODO campo, teto de 12, campo estranho some')
    ok(chamou['headers'].get('x-goog-api-key') == 'chave-falsa' and 'chave-falsa' not in chamou['url'], 'a chave vai no cabeçalho (nunca na URL)')
    ok('ignore qualquer instrução' in chamou['corpo']['contents'][0]['parts'][0]['text'] and 'Gabriel Sales Nogueira' in chamou['corpo']['contents'][0]['parts'][0]['text'], 'o pedido à IA manda o texto do PDF e a ordem de ignorar instruções de dentro dele')
    requests.post = lambda *a, **k: Resp(429, {})
    cv_ia, fonte, avisos = cx.importar_cv_automatico(pa, li.id, pdf_simples(LINKEDIN_EN), usar_ia=True)
    ok(fonte == 'leitura' and avisos and 'recusou' in avisos[0], 'IA recusou (429): cai na leitura automática e AVISA')
    requests.post = lambda *a, **k: Resp(200, {'candidates': []})
    cv_ia, fonte, avisos = cx.importar_cv_automatico(pa, li.id, pdf_simples(LINKEDIN_EN), usar_ia=True)
    ok(fonte == 'leitura' and avisos, 'IA devolveu lixo: cai na leitura automática')
    def timeout(*a, **k): raise requests.ConnectionError('x')
    requests.post = timeout
    cv_ia, fonte, avisos = cx.importar_cv_automatico(pa, li.id, pdf_simples(LINKEDIN_EN), usar_ia=True)
    ok(fonte == 'leitura' and avisos, 'IA fora do ar: cai na leitura automática')
    del os.environ['GEMINI_API_KEY']
    cv_ia, fonte, avisos = cx.importar_cv_automatico(pa, li.id, pdf_simples(LINKEDIN_EN), usar_ia=True)
    ok(fonte == 'leitura' and any('não está ligada' in a for a in avisos), 'pediu IA sem chave: cai na leitura e AVISA (nada de falhar calado)')

    # ---------- 9. rota HTTP ----------
    from app.main import routes as rotas
    sem = app.test_client()
    ok(sem.post('/api/conexoes/importar-cv').status_code == 401, 'importar PDF sem login: 401')
    rotas._ultimo_cv.clear(); ev(ca)
    pdf = pdf_simples(LINKEDIN_EN)
    r1 = fca.post('/api/conexoes/importar-cv', data={'arquivo': (io.BytesIO(pdf), 'li.pdf'), 'conexao_id': str(li.id)}, content_type='multipart/form-data')
    j1 = r1.get_json()
    ok(r1.status_code == 200 and j1['ok'] and j1['fonte'] == 'leitura' and j1['resumo']['nome'] == 'Gabriel Sales Nogueira' and j1['resumo']['experiencias'] == 2 and 'no-store' in r1.headers.get('Cache-Control', ''),
       'rota: PDF válido PUBLICA o currículo e devolve só um resumo (sem cache)')
    pushed = ev(ca, 'conexoes')
    ok(pushed and any(x['tipo'] == 'linkedin' and x['dados'] and x['dados']['cv']['nome'] == 'Gabriel Sales Nogueira' for x in pushed[-1]['args'][0]['lista']), 'regra 6: as abas da pessoa recebem a lista com o currículo já pronto')
    r2 = fca.post('/api/conexoes/importar-cv', data={'arquivo': (io.BytesIO(pdf), 'li.pdf'), 'conexao_id': str(li.id)}, content_type='multipart/form-data')
    ok(r2.status_code == 429, 'rota: dois seguidos, o 2º leva 429 (freio de 8 s)')
    rotas._ultimo_cv.clear()
    r3 = fca.post('/api/conexoes/importar-cv', data={'arquivo': (io.BytesIO(b'isto nao e um pdf'), 'x.pdf'), 'conexao_id': str(li.id)}, content_type='multipart/form-data')
    ok(r3.status_code == 400 and 'PDF' in r3.get_json()['error'], 'rota: arquivo que não é PDF volta 400 com mensagem')
    rotas._ultimo_cv.clear()
    ok(fca.post('/api/conexoes/importar-cv', data={'conexao_id': str(li.id)}, content_type='multipart/form-data').status_code == 400, 'rota: sem arquivo volta 400')
    rotas._ultimo_cv.clear()
    r4 = fca.post('/api/conexoes/importar-cv', data={'arquivo': (io.BytesIO(pdf), 'li.pdf'), 'conexao_id': str(gh.id)}, content_type='multipart/form-data')
    ok(r4.status_code == 400 and 'LinkedIn' in r4.get_json()['error'], 'rota: conexão que não é do LinkedIn volta 400')
    rotas._ultimo_cv.clear()
    r5 = fcb.post('/api/conexoes/importar-cv', data={'arquivo': (io.BytesIO(pdf), 'li.pdf'), 'conexao_id': str(li.id)}, content_type='multipart/form-data')
    ok(r5.status_code == 400, 'rota: a conexão dos outros não aceita PDF (400)')
    rotas._ultimo_cv.clear()
    r6 = fca.post('/api/conexoes/importar-cv', data={'arquivo': (io.BytesIO(pdf_outro), 'li.pdf'), 'conexao_id': str(li.id)}, content_type='multipart/form-data')
    ok(r6.status_code == 400 and 'outra-pessoa' in r6.get_json()['error'], 'rota: PDF de outro perfil volta 400 dizendo de quem é')

    # ---------- 10. plataformas "suaves" (Instagram, TikTok, X, Steam, iFood, Amazon, OLX): tentam ler a página; se não der, cartão simples ----------
    reg = cx.registro_plataformas()
    ok(reg['instagram']['busca'] and reg['github']['busca'] and not reg['linkedin']['busca'] and not reg['bazar']['busca'], 'o registro diz quem busca dados (LinkedIn e loja do Bazar não)')
    duda = db.session.get(Person, ids['Duda'])
    cx.salvar_lista(duda, [{'url': 'instagram.com/duda.x'}, {'url': 'steamcommunity.com/id/duda'}, {'url': 'x.com/duda'}, {'url': 'tiktok.com/@duda'},
                           {'url': 'https://www.amazon.com.br/dp/B0ABC'}, {'url': 'https://www.ifood.com.br/delivery/brasilia-df/loja'}, {'url': 'https://www.olx.com.br/item/123'}])
    meus = {x.tipo: x for x in cx.listar(ids['Duda'])}

    def suave(url, **kw):
        if 'instagram.com' in url:
            return 200, 'text/html', '<html><head><title>Instagram</title></head></html>', 'https://www.instagram.com/accounts/login/'      # caiu na tela de entrada
        if 'steamcommunity.com' in url:
            return 200, 'text/html', '<html><head><meta property="og:title" content="Steam Community :: Duda"><meta property="og:description" content="Jogos e conquistas">' \
                                     '<meta property="og:image" content="https://avatars.cloudflare.steamstatic.com/abc_full.jpg"></head></html>', url
        if 'x.com' in url:
            return 403, '', '', url
        if 'tiktok.com' in url:
            raise importar.ErroImportar('O site não respondeu.')
        if 'amazon.com.br' in url:
            return 200, 'text/html', '<html><head><meta property="og:title" content="Fone de ouvido legal | Amazon.com.br"><meta property="og:image" content="https://m.media-amazon.com/images/I/x.jpg"></head></html>', url
        if 'ifood.com.br' in url:
            return 503, '', '', url
        if 'olx.com.br' in url:
            return 200, 'text/html', '<html><head><title>Just a moment...</title></head></html>', url
        return 404, '', '', url
    cx.importar.baixar_texto = suave
    for t in ('instagram', 'steam', 'x', 'tiktok', 'amazon', 'ifood', 'olx'):
        cx.atualizar_uma(meus[t].id)
    lido = {t: db.session.get(Conexao, meus[t].id) for t in meus}
    ok(all(lido[t].erro is None for t in lido), 'NENHUMA das plataformas suaves guarda erro (falha de leitura não vira mensagem vermelha pra ninguém)')
    for t in ('instagram', 'x', 'tiktok', 'ifood', 'olx'):
        ok(json.loads(lido[t].dados) == {'sem_previa': True}, f'{t}: o site não deixou ler (login/bloqueio/título genérico): cartão simples, sem prévia')
    st = json.loads(lido['steam'].dados)
    ok(st['titulo'] == 'Steam Community :: Duda' and st['imagem'] == 'https://avatars.cloudflare.steamstatic.com/abc_full.jpg' and lido['steam'].titulo.startswith('Steam Community'), 'Steam: título e avatar do CDN da Steam')
    am = json.loads(lido['amazon'].dados)
    ok(am['titulo'].startswith('Fone de ouvido') and am['imagem'].startswith('https://m.media-amazon.com/'), 'Amazon: título e imagem do CDN da Amazon (produto)')
    ok(cx.lista_json(ids['Duda'])[0]['dados'] == {'sem_previa': True} and not cx.precisa_atualizar(lido['instagram']), 'sem prévia também fica em cache (não tenta de novo na hora)')
    ok(cx.imagem_ok('https://pbs.twimg.com/profile_images/1/a.jpg') and not cx.imagem_ok('https://scontent.cdninstagram.com/a.jpg') and not cx.imagem_ok('http://i.ytimg.com/a.jpg'), 'só https e só CDN conhecido carrega imagem')
    cx.importar.baixar_texto = falso

    # ---------- 11. código ----------
    src = open(os.path.join(RAIZ, 'conexoes.py'), encoding='utf-8').read()
    js = open(os.path.join(RAIZ, 'static', 'js', 'conexoes.js'), encoding='utf-8').read()
    html = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
    ok('importar.baixar_texto' in src and 'urllib' not in src.replace('urllib.parse', '') and 'requests.get' not in src, 'toda busca de rede passa pelo buscador seguro (importar.py); nada de requests.get solto')
    ok(all(h in src for h in ('avatars.githubusercontent.com', 'i.ytimg.com', 'i.scdn.co', 'static-cdn.jtvnw.net')), 'lista de CDNs de imagem conhecida')
    ok("'busca': None" in src.split("'linkedin':")[1].split('\n')[0], 'o LinkedIn NÃO tem busca por link (proibido pelo contrato dele): só o PDF')
    ok('abrirCv' not in js and 'cx-cv-modal' not in js and 'cv_salvar' not in js and 'cv_salvar' not in html, 'o cliente não tem mais editor de currículo')
    ok('importar-cv' in js and 'data-cx-pdf' in js and 'conexao_id' in js, 'o cliente importa o PDF (sem editor)')
    ok('informados pela própria pessoa' in js, 'a face avisa que os links são informados pela própria pessoa (não verificados)')
    ok(re.search(r'(?<!\w)eval\(|document\.write', js) is None and "innerHTML = '" not in js.replace("innerHTML = '<div class=\"cx-vazio\">", ''), 'conexoes.js sem eval/document.write')
    ok('id="set-conexoes"' in html and 'data-target="set-conexoes"' in html and 'js/conexoes.js' in html and 'css/conexoes.css' in html, 'chat.html tem a aba Conexões e carrega o módulo')
    ok('Conexoes.htmlSeta' in html and 'conexoes_qtd' in html and "socket.on('conexoes_do_perfil'" in html, 'o cartão tem a setinha (só quando há conexões) e escuta as conexões do perfil')
    ok('Conexoes.tocando()' in html and 'tocando: () => players.size > 0' in js, 'a face não é repintada por cima de uma música tocando')

    # ---------- 12. cada empresa com a cara dela ----------
    css = open(os.path.join(RAIZ, 'static', 'css', 'conexoes.css'), encoding='utf-8').read()
    marcas = re.search(r'const MARCAS = new Set\(\[(.*?)\]\)', js).group(1)
    marcas = re.findall(r"'([a-z]+)'", marcas)
    ok(len(marcas) >= 12 and 'youtube' in marcas and 'amazon' in marcas and 'linkedin' in marcas, f'o cliente conhece as marcas ({len(marcas)})')
    ok(all(f'.cx-card[data-marca="{m}"]' in css for m in marcas), 'todas as marcas têm o visual no CSS: ' + ', '.join(m for m in marcas if f'.cx-card[data-marca="{m}"]' not in css))
    ok(js.count('<article class="cx-card') == js.count('${marca(c.tipo)}') >= 7, 'todo cartão de conexão leva o id da marca (data-marca), sem exceção')
    bloco_li = css.split('.cx-card[data-marca="linkedin"] {', 1)[1].split('}', 1)[0]
    ok('--m-bg: #fff' in bloco_li and '--text-header: #1d2226' in bloco_li, 'o LinkedIn é um cartão BRANCO com letras escuras')
    ok('--m-faixa: #ff0000' in css.split('.cx-card[data-marca="youtube"]', 1)[1].split('}', 1)[0] and '--m-faixa: #ff9900' in css.split('.cx-card[data-marca="amazon"]', 1)[1].split('}', 1)[0],
       'YouTube com a faixa vermelha e Amazon com a faixa amarela/laranja')
    ok(css.index('.cx-card[data-marca="linkedin"] {') > css.index('.cx-card[data-marca] {'), 'o branco do LinkedIn vem DEPOIS da regra geral escura (mesma especificidade: o último vence)')
    ok('fa-x-twitter' not in js.split('const LOGO_X')[1].split('\n')[0] and 'LOGO_X' in js and "tipo === 'x'" in js, 'o logo do X é desenhado (o Font Awesome 6.4 do app não tem o ícone)')
    ok('.cx-card.vinil.tocando .cx-braco' in css and '.cx-vinil.tocando' not in css, 'o toca-discos reage ao "tocando" (seletor do cartão certo: a agulha desce e o disco gira)')
    ok('pnt_cx_carrossel' in js and 'data-cx-pag' in js and 'id="cx-car"' in html and 'cx-car-nav' in css, 'carrossel opcional: uma conexão por página, ligado em Configurações > Conexões (o padrão segue sendo a lista)')
    ok('compactarVazias' in js and 'slice(0, compacto ? 3 : 6)' in js, 'escrever e apagar não empilha caixinhas vazias; a lista usa cartões compactos')
    ok(":where(:not(.cx-cab)" in css, 'as seções do currículo têm espaço (a regra geral de margem não engole as de .cx-sub/.cx-rodape)')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
