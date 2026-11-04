"""Pantheon Estúdio (/estudio) e a biblioteca de arquivos (Rodada 36b): Lottie, imagem e vídeo enviados pelo admin viram camada "Arquivo" de um efeito.
Confere: validação PELO CONTEÚDO (Lottie sem expressão/imagem/texto, imagem de verdade e leve, vídeo com assinatura e capa), SVG/executável/HTML barrados,
o mesmo arquivo vira um só, limites da biblioteca, só admin envia/apaga, arquivo servido a qualquer logado com cache imutável + ETag + Range, a receita guarda só
o id (o endereço nunca vem do cliente), arquivo em uso não apaga, efeitos sumiram do /admin, e o que o motor/editor do navegador prometem.
Banco SQLite em memória; nada de rede."""
import io, os, re, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from PIL import Image
from app import create_app, db, efeitos, estudio_arquivos as ea
from app.bazar import definir_admin
from app.models import Role, Person, EfeitoCustom, EstudioArquivo

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')
H = {'X-Requested-With': 'fetch'}


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def erra(fn, trecho=None):
    try:
        fn()
    except ea.ErroArquivo as e:
        db.session.rollback()
        return trecho is None or trecho.lower() in str(e).lower()
    return False


# ---------- geradores de arquivo ----------
def png(w=32, h=32, cor=(255, 0, 0, 255), formato='PNG'):
    b = io.BytesIO(); Image.new('RGBA', (w, h), cor).save(b, formato); return b.getvalue()


def quadros(n, w=32, h=32):
    return [Image.new('RGBA', (w, h), ((i * 37) % 256, (i * 91) % 256, 120, 255)) for i in range(n)]


def animado(formato, n=4, w=32, h=32, ms=100):
    fs = quadros(n, w, h); b = io.BytesIO()
    fs[0].save(b, formato, save_all=True, append_images=fs[1:], duration=ms, loop=0)
    return b.getvalue()


def lottie(**mud):
    base = {'v': '5.7.0', 'fr': 30, 'ip': 0, 'op': 60, 'w': 200, 'h': 200, 'nm': 't', 'ddd': 0, 'assets': [], 'layers': [
        {'ddd': 0, 'ind': 1, 'ty': 4, 'nm': 'forma', 'sr': 1, 'ip': 0, 'op': 60, 'st': 0, 'bm': 0,
         'ks': {'o': {'a': 1, 'k': [{'i': {'x': [0.833], 'y': [0.833]}, 'o': {'x': [0.167], 'y': [0.167]}, 't': 0, 's': [0]}, {'t': 30, 's': [100]}]},
                'r': {'a': 0, 'k': 0}, 'p': {'a': 0, 'k': [100, 100, 0]}, 'a': {'a': 0, 'k': [0, 0, 0]}, 's': {'a': 0, 'k': [100, 100, 100]}},
         'shapes': [{'ty': 'el', 'p': {'a': 0, 'k': [0, 0]}, 's': {'a': 0, 'k': [50, 50]}}, {'ty': 'fl', 'c': {'a': 0, 'k': [1, 0, 0, 1]}, 'o': {'a': 0, 'k': 100}}]}]}
    base.update(mud)
    return json.dumps(base).encode()


def mp4(extra=2000):
    return b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2' + b'\x00' * extra


def webm(extra=2000):
    return b'\x1a\x45\xdf\xa3' + b'\x9f\x42\x86\x81\x01' + b'\x00' * extra


MED = {'w': 320, 'h': 240, 'dur': 2500}
CAPA = png(64, 48)

with app.app_context():
    db.create_all()
    r = Role(name='M', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('adm', 'ana'):
        p = Person(name=nome, email=f'{nome}@x', role_id=r.id, username=nome, bazinga_coins=500); db.session.add(p); db.session.commit(); ids[nome] = p.id
    definir_admin(ids['adm'])

    def cli(nome=None):
        fc = app.test_client()
        if nome:
            with fc.session_transaction() as s:
                s['user_id'] = ids[nome]
        return fc

    fadm, fana, fanon = cli('adm'), cli('ana'), cli()

    # =============== Lottie ===============
    dados, info = ea.validar_lottie(lottie())
    ok(info == {'w': 200, 'h': 200, 'dur_ms': 2000, 'quadros': 60}, 'Lottie bom: mede largura, altura, duração (2 s) e quadros')
    ok(b' ' not in dados[:20] and json.loads(dados)['layers'], 'O Lottie é guardado compacto (reserializado), não como veio')
    ok(erra(lambda: ea.validar_lottie(lottie(layers=[{'ty': 4, 'ks': {'o': {'a': 0, 'k': 100, 'x': 'var $bm_rt = time;'}}}])), 'expressões'), 'Lottie com EXPRESSÃO (código): recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(layers=[{'ty': 5, 'nm': 't'}])), 'texto'), 'Lottie com camada de TEXTO: recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(layers=[{'ty': 2, 'refId': 'img_0'}])), 'imagem'), 'Lottie com camada de IMAGEM: recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(layers=[{'ty': 6}]))), 'Lottie com camada de ÁUDIO: recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(assets=[{'id': 'img_0', 'w': 4, 'h': 4, 'u': '', 'p': 'data:image/png;base64,AAAA', 'e': 1}])), 'embutido'), 'Lottie com imagem EMBUTIDA nos assets: recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(assets=[{'id': 'comp_0', 'layers': [{'ty': 5}]}]))), 'Camada proibida escondida DENTRO de uma pré-composição: recusada')
    ok(not erra(lambda: ea.validar_lottie(lottie(assets=[{'id': 'comp_0', 'layers': [{'ty': 4, 'ks': {}, 'shapes': []}]}]))), 'Pré-composição só com formas: aceita')
    ok(erra(lambda: ea.validar_lottie(lottie(op=2000)), 'dura mais'), 'Lottie de mais de 20 s: recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(fr=120))), 'Taxa de quadros absurda: recusada')
    ok(erra(lambda: ea.validar_lottie(lottie(op=0))), 'Sem duração (op <= ip): recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(w=999999))), 'Tamanho absurdo: recusado')
    ok(erra(lambda: ea.validar_lottie(json.dumps({'v': '5', 'fr': 30}).encode()), 'campo'), 'Lottie sem os campos básicos: recusado')
    ok(erra(lambda: ea.validar_lottie(b'{"quebrado": ')), 'JSON quebrado: recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(nm='x' * (ea.LIM_LOTTIE + 10)), ), 'pesado'), 'Lottie acima do limite de peso: recusado')
    ok(erra(lambda: ea.validar_lottie(lottie(layers=[{'ty': 3}] * (ea.MAX_CAMADAS_LOTTIE + 5)), ), 'camadas'), 'Lottie com camadas demais: recusado')
    fundo = b'{"v":"5","fr":30,"ip":0,"op":30,"w":10,"h":10,"layers":[{"ty":3}],"x":' + b'[' * 5000 + b']' * 5000 + b'}'
    ok(erra(lambda: ea.validar_lottie(fundo)), 'JSON aninhado fundo demais: recusado sem derrubar o servidor')

    # =============== detecção pelo conteúdo ===============
    ok(erra(lambda: ea.guardar(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', 'a.png', 1), 'SVG'), 'SVG (mesmo chamado de .png): recusado')
    ok(erra(lambda: ea.guardar(b'<!doctype html><script>alert(1)</script>', 'a.gif', 1)), 'HTML disfarçado: recusado')
    ok(erra(lambda: ea.guardar(b'MZ\x90\x00' + b'\x00' * 500, 'a.png', 1)), 'Executável disfarçado de imagem: recusado')
    ok(erra(lambda: ea.guardar(b'', 'a.png', 1), 'vazio'), 'Arquivo vazio: recusado')
    ok(erra(lambda: ea.guardar(b'\x89PNG\r\n\x1a\n' + b'lixo' * 50, 'a.png', 1)), 'PNG só no cabeçalho, corpo lixo: recusado (a imagem tem que abrir de verdade)')
    ok(erra(lambda: ea.guardar(b'\x00\x00\x00\x18ftypqt  ' + b'\x00' * 100, 'a.mov', 1, capa=CAPA, medidas=MED), '.mov'), 'MOV (QuickTime): recusado com a dica de exportar em MP4')

    # =============== imagem ===============
    a_png = ea.guardar(png(), 'bola.png', ids['adm'])
    ok(a_png.tipo == 'imagem' and a_png.mime == 'image/png' and not a_png.tem_capa and a_png.dur_ms is None and (a_png.w, a_png.h) == (32, 32), 'PNG parado: imagem, sem capa, sem duração')
    a_webp = ea.guardar(animado('WEBP', 4, 32, 32, 100), 'chuva.webp', ids['adm'])
    ok(a_webp.tipo == 'imagem' and a_webp.mime == 'image/webp' and a_webp.quadros == 4 and a_webp.tem_capa and a_webp.dur_ms == 400, 'WebP animado: 4 quadros, 400 ms, ganha capa parada')
    a_gif = ea.guardar(animado('GIF', 5, 40, 30, 80), 'faisca.gif', ids['adm'])
    ok(a_gif.mime == 'image/gif' and a_gif.quadros == 5 and a_gif.tem_capa and a_gif.dur_ms == 400, 'GIF animado: 5 quadros, 400 ms, com capa')
    a_apng = ea.guardar(animado('PNG', 3, 32, 32, 100), 'orbita.apng', ids['adm'])
    ok(a_apng.mime == 'image/png' and a_apng.quadros == 3 and a_apng.tem_capa, 'APNG: entendido como animação (3 quadros)')
    b = io.BytesIO(); Image.new('RGB', (40, 40), (10, 200, 10)).save(b, 'JPEG')
    a_jpg = ea.guardar(b.getvalue(), 'foto.jpg', ids['adm'])
    ok(a_jpg.mime == 'image/jpeg' and not a_jpg.tem_capa, 'JPEG parado: aceito')
    ok(erra(lambda: ea.guardar(png(3000, 10), 'larga.png', 1), 'grande demais'), 'Imagem com lado maior que o limite: recusada')
    ok(erra(lambda: ea.guardar(png(4, 4), 'mini.png', 1), 'pequena'), 'Imagem minúscula: recusada')
    ok(erra(lambda: ea.guardar(animado('WEBP', ea.MAX_QUADROS + 10, 8, 8), 'longa.webp', 1), 'quadros'), 'Animação com quadros demais: recusada')
    ok(erra(lambda: ea.guardar(animado('WEBP', 5, 16, 16, 5000), 'lenta.webp', 1), 'dura mais'), 'Animação de mais de 20 s: recusada')
    ant = ea.MAX_PIXELS_ANIMADOS; ea.MAX_PIXELS_ANIMADOS = 1000
    ok(erra(lambda: ea.guardar(animado('WEBP', 4, 32, 32), 'pesada.webp', 1), 'pesada'), 'Animação pesada demais (largura x altura x quadros): recusada')
    ea.MAX_PIXELS_ANIMADOS = ant
    ant = ea.LIM_IMAGEM; ea.LIM_IMAGEM = 1000
    ruido = [Image.frombytes('RGBA', (64, 64), os.urandom(64 * 64 * 4)) for _ in range(3)]
    bruido = io.BytesIO(); ruido[0].save(bruido, 'WEBP', save_all=True, append_images=ruido[1:], duration=100, lossless=True)
    ok(len(bruido.getvalue()) > 1000 and erra(lambda: ea.guardar(bruido.getvalue(), 'peso.webp', 1), 'pesada'), 'Imagem acima do peso máximo: recusada')
    ea.LIM_IMAGEM = ant
    b = io.BytesIO(); Image.new('RGB', (20, 20)).save(b, 'BMP')
    ok(erra(lambda: ea.guardar(b.getvalue(), 'x.bmp', 1)), 'Formato que não é dos aceitos (BMP): recusado')

    # =============== vídeo ===============
    a_mp4 = ea.guardar(mp4(), 'brasa.mp4', ids['adm'], capa=CAPA, medidas=MED)
    ok(a_mp4.tipo == 'video' and a_mp4.mime == 'video/mp4' and a_mp4.tem_capa and a_mp4.dur_ms == 2500 and (a_mp4.w, a_mp4.h) == (320, 240), 'MP4: guarda com a capa e as medidas do navegador')
    a_webm = ea.guardar(webm(), 'aura.webm', ids['adm'], capa=CAPA, medidas=MED)
    ok(a_webm.mime == 'video/webm', 'WebM: aceito pela assinatura')
    ok(erra(lambda: ea.guardar(mp4(3000), 'a.mp4', 1, medidas=MED), 'capa'), 'Vídeo sem capa: recusado')
    ok(erra(lambda: ea.guardar(mp4(3001), 'a.mp4', 1, capa=b'nao e imagem', medidas=MED), 'imagem'), 'Capa que não é imagem: recusada')
    ok(erra(lambda: ea.guardar(mp4(3002), 'a.mp4', 1, capa=CAPA, medidas={'w': 10, 'h': 10, 'dur': 999999})), 'Vídeo de mais de 20 s (medida do navegador): recusado')
    ok(erra(lambda: ea.guardar(mp4(3003), 'a.mp4', 1, capa=CAPA, medidas=None)), 'Vídeo sem medida nenhuma: recusado')
    ok(erra(lambda: ea.guardar(mp4(ea.LIM_VIDEO + 10), 'grande.mp4', 1, capa=CAPA, medidas=MED), 'pesado'), 'Vídeo acima de 6 MB: recusado')
    capa_db = ea.conteudo_capa(a_mp4.id)
    ok(capa_db and capa_db[0][:4] == b'RIFF' and capa_db[0][8:12] == b'WEBP', 'A capa do vídeo é reencodada em WebP (o que o navegador mandou não é guardado cru)')

    # =============== biblioteca ===============
    de_novo = ea.guardar(png(), 'outro-nome.png', ids['adm'])
    ok(de_novo.id == a_png.id and EstudioArquivo.query.filter_by(sha=a_png.sha).count() == 1, 'O mesmo arquivo enviado duas vezes vira um só')
    ok(re.fullmatch(r'[0-9a-f]{12}', a_png.id), 'O id é aleatório de 12 hex (o cliente não escolhe)')
    antigo = (ea.MAX_ARQUIVOS, ea.LIM_TOTAL)
    ea.MAX_ARQUIVOS = EstudioArquivo.query.count()
    ok(erra(lambda: ea.guardar(png(33, 33), 'extra.png', 1), 'limite') or erra(lambda: ea.guardar(png(33, 33), 'extra.png', 1), 'arquivos'), 'Biblioteca cheia (quantidade): recusa novo arquivo')
    ea.MAX_ARQUIVOS = antigo[0]
    ea.LIM_TOTAL = ea.uso_total()['bytes'] + 10
    ok(erra(lambda: ea.guardar(png(34, 34), 'extra2.png', 1), 'limite'), 'Biblioteca cheia (peso total): recusa novo arquivo')
    ea.LIM_TOTAL = antigo[1]
    ok(ea.guardar(png(33, 33), 'cabe.png', ids['adm']).id, 'Com espaço, volta a aceitar')
    ok(ea.listar() and all(set(i) >= {'id', 'k', 'url', 'capa', 'dur', 'w', 'h', 'nome', 'bytes'} for i in ea.listar()), 'A lista da biblioteca traz o que o editor precisa (sem os bytes)')
    ok(all(i['url'] == f"/estudio/arquivo/{i['id']}" for i in ea.listar()), 'Os endereços são montados pelo servidor a partir do id')

    # =============== API: só admin ===============
    def enviar(cl, dados, nome='a.png', capa=None, med=None, headers=H):
        data = {'file': (io.BytesIO(dados), nome)}
        if capa is not None:
            data['capa'] = (io.BytesIO(capa), 'capa.webp')
        if med:
            data.update({k: str(v) for k, v in med.items()})
        return cl.post('/estudio/api/arquivos', data=data, content_type='multipart/form-data', headers=headers)

    ok(fana.get('/estudio/api/arquivos').status_code == 403 and fanon.get('/estudio/api/arquivos').status_code == 403, 'Não-admin e deslogado: a biblioteca dá 403')
    ok(enviar(fana, png(35, 35)).status_code == 403, 'Não-admin não envia arquivo')
    ok(enviar(fadm, png(35, 35), headers={}).status_code == 400, 'Sem o cabeçalho anti-forja: recusado')
    ok(fana.get('/estudio').status_code == 404 and fanon.get('/estudio').status_code == 404, 'A página /estudio dá 404 pra quem não é admin (nem confirma que existe)')
    pg = fadm.get('/estudio')
    ok(pg.status_code == 200 and b'Biblioteca de arquivos' in pg.data and b'js/estudio.js' in pg.data and b'js/efeitos.js' in pg.data, 'Admin abre o Estúdio (com o motor e o editor)')
    rr = enviar(fadm, png(35, 35), 'novo.png')
    j = rr.get_json()
    ok(rr.status_code == 200 and j['arquivo']['k'] == 'imagem' and j['uso']['qtd'] >= 1, 'Admin envia um arquivo (multipart) e recebe os dados')
    ok(enviar(fadm, b'<svg/>', 'x.png').status_code == 400 and 'SVG' in enviar(fadm, b'<svg/>', 'x.png').get_json()['erro'], 'Upload de SVG: 400 com o motivo em português')
    rv = enviar(fadm, mp4(2100), 'v.mp4', capa=CAPA, med=MED)
    ok(rv.status_code == 200 and rv.get_json()['arquivo']['capa'].endswith('/capa'), 'Upload de vídeo com capa e medidas pelo formulário')
    ok(enviar(fadm, mp4(2101), 'v.mp4', med=MED).status_code == 400, 'Upload de vídeo sem capa: 400')
    grande = fadm.post('/estudio/api/arquivos', data={'file': (io.BytesIO(b'\x00' * (11 * 1024 * 1024)), 'g.mp4')}, content_type='multipart/form-data', headers=H)
    ok(grande.status_code == 413 and 'erro' in grande.get_json(), 'Requisição enorme: 413 com a mensagem do Estúdio (não a de "imagem de 5 MB")')
    ok(fadm.post('/estudio/api/arquivos', data={}, content_type='multipart/form-data', headers=H).status_code == 400, 'Sem arquivo: 400')

    # =============== servir o arquivo ===============
    url = f'/estudio/arquivo/{a_webp.id}'
    ok(fanon.get(url).status_code == 401, 'Sem login: 401 (a arte só sai pra quem está no app)')
    g = fana.get(url)
    ok(g.status_code == 200 and g.mimetype == 'image/webp' and g.data == a_webp.dados, 'Qualquer logado (não só admin) baixa o arquivo, com o mime pelo CONTEÚDO')
    cc = g.headers.get('Cache-Control', '')
    ok('immutable' in cc and 'private' in cc and 'max-age=31536000' in cc, 'Cache imutável de um ano, privado (a rota exige login)')
    ok(g.headers.get('ETag') and g.headers.get('X-Content-Type-Options') == 'nosniff', 'ETag do conteúdo e nosniff')
    ok(fana.get(url, headers={'If-None-Match': g.headers['ETag']}).status_code == 304, 'Pedido condicional (If-None-Match): 304, sem baixar de novo')
    rg = fana.get(url, headers={'Range': 'bytes=0-9'})
    ok(rg.status_code == 206 and len(rg.data) == 10 and rg.headers.get('Content-Range', '').startswith('bytes 0-9/'), 'Range funciona (o Safari só toca vídeo assim)')
    vv = fana.get(f'/estudio/arquivo/{a_mp4.id}')
    ok(vv.status_code == 200 and vv.mimetype == 'video/mp4', 'MP4 sai como video/mp4')
    ct = fana.get(f'/estudio/arquivo/{a_webp.id}/capa')
    ok(ct.status_code == 200 and ct.mimetype == 'image/webp' and ct.data[:4] == b'RIFF' and ct.headers.get('ETag') != g.headers.get('ETag'), 'A capa sai como WebP, com ETag próprio')
    ok(fanon.get(f'/estudio/arquivo/{a_webp.id}/capa').status_code == 401, 'A capa também exige login')
    ok(fana.get(f'/estudio/arquivo/{a_png.id}/capa').status_code == 404, 'Imagem parada não tem capa: 404')
    a_lot = ea.guardar(lottie(), 'estrela.json', ids['adm'])
    lj = fana.get(f'/estudio/arquivo/{a_lot.id}')
    ok(lj.status_code == 200 and lj.mimetype == 'application/json' and json.loads(lj.data)['fr'] == 30, 'Lottie sai como application/json (o que o motor lê)')
    ok(fana.get('/estudio/arquivo/naoexiste00').status_code == 404 and fana.get('/estudio/arquivo/../../etc/passwd').status_code == 404 and fana.get('/estudio/arquivo/ZZZZZZZZZZZZ').status_code == 404,
       'Id inexistente ou fora do formato: 404')

    # =============== camada "Arquivo" na receita ===============
    base = {'id': 'chuva_estrelas', 'nome': 'Chuva de Estrelas', 'tipo': 'efeito_perfil', 'raridade': 'epico',
            'receita': {'pausa': 2, 'mistura': 'tela', 'camadas': [{'tipo': 'arquivo', 'arq': a_webp.id, 'escala': 150, 'x': 10, 'y': -10, 'giro': 15, 'espelho': 'horizontal', 'opac': 80, 'vel': 1.5, 'ini': 10, 'fim': 90, 'ajuste': 'cobrir', 'lugar': 'atras'}]}}
    rs = fadm.post('/estudio/api/efeitos', json=base, headers=H)
    ok(rs.status_code == 200, 'Efeito com camada Arquivo: criado')
    salvo = json.loads(EfeitoCustom.query.get('chuva_estrelas').receita)
    cam = salvo['camadas'][0]
    ok(cam['arq'] == a_webp.id and cam['escala'] == 150 and cam['espelho'] == 'horizontal' and cam['ajuste'] == 'cobrir' and salvo['mistura'] == 'tela', 'A receita guarda o id e os ajustes (e a mistura do efeito)')
    ok('a' not in cam and 'url' not in json.dumps(salvo), 'A receita GUARDADA não tem endereço nenhum (só o id do arquivo)')
    forjada = json.loads(json.dumps(base)); forjada['id'] = 'forjado'
    forjada['receita']['camadas'][0]['a'] = {'k': 'imagem', 'url': 'https://evil.example/x.gif', 'capa': None}
    fadm.post('/estudio/api/efeitos', json=forjada, headers=H)
    ok('evil' not in EfeitoCustom.query.get('forjado').receita, 'Endereço mandado pelo cliente (campo "a") é jogado fora: o servidor monta pelo id')
    lista = fadm.get('/estudio/api/efeitos').get_json()['efeitos']
    ef = [e for e in lista if e['id'] == 'chuva_estrelas'][0]
    a_res = ef['receita']['camadas'][0]['a']
    ok(a_res['url'] == f'/estudio/arquivo/{a_webp.id}' and a_res['k'] == 'imagem' and a_res['dur'] == 400 and a_res['capa'].endswith('/capa'), 'O servidor resolve o arquivo (endereço, tipo, duração, capa) pro editor e pro motor')
    mapa = efeitos.mapa_para_cliente()
    ok(mapa['chuva_estrelas']['receita']['camadas'][0]['a']['url'] == a_res['url'] and mapa['chuva_estrelas']['receita']['mistura'] == 'tela', 'O mapa que vai a todo mundo traz o arquivo resolvido e a mistura')
    ok(fadm.get('/estudio/api/efeitos').get_json()['misturas'] == ['normal', 'tela', 'somar'], 'A API informa as misturas aceitas')

    ok(fadm.post('/estudio/api/efeitos', json={**base, 'id': 'sem_arq', 'receita': {'camadas': [{'tipo': 'arquivo'}]}}, headers=H).status_code == 400, 'Camada Arquivo sem arquivo: recusada')
    ok(fadm.post('/estudio/api/efeitos', json={**base, 'id': 'arq_fantasma', 'receita': {'camadas': [{'tipo': 'arquivo', 'arq': 'abcdef012345'}]}}, headers=H).status_code == 400, 'Id de arquivo que não existe na biblioteca: recusado')
    ok(fadm.post('/estudio/api/efeitos', json={**base, 'id': 'arq_url', 'receita': {'camadas': [{'tipo': 'arquivo', 'arq': 'https://evil.example/a.gif'}]}}, headers=H).status_code == 400, 'URL no lugar do id: recusada')
    ok(fadm.post('/estudio/api/efeitos', json={**base, 'id': 'arq_sql', 'receita': {'camadas': [{'tipo': 'arquivo', 'arq': "x' OR '1'='1"}]}}, headers=H).status_code == 400, 'Id com cara de injeção: recusado')
    lim = efeitos.normalizar_receita('efeito_perfil', {'mistura': 'screen; background:url(x)', 'camadas': [{'tipo': 'arquivo', 'arq': a_png.id, 'escala': 9999, 'x': -500, 'giro': 'abc', 'espelho': '<b>', 'opac': -5, 'vel': 99, 'ajuste': 'x', 'lugar': 'topo', 'ini': 90, 'fim': 91}]})
    cl = lim['camadas'][0]
    ok(lim['mistura'] == 'normal', 'Mistura fora da lista volta pra normal')
    ok(cl['escala'] == 400 and cl['x'] == -100 and cl['giro'] == 0 and cl['espelho'] == 'nao' and cl['opac'] == 0 and cl['vel'] == 3 and cl['ajuste'] == 'conter' and cl['lugar'] == 'atras', 'Ajustes da camada Arquivo limitados (máximo, mínimo, lista fechada)')
    ok(cl['fim'] - cl['ini'] >= 5 and cl['fim'] <= 100 and cl['ini'] >= 0, 'O trecho aparado fica com pelo menos 5%')
    ok(set(cl) == {'tipo', *efeitos.ESQUEMA['arquivo']['params']}, 'A camada sai só com os parâmetros do esquema')
    av = {'id': 'aura_por_cima', 'nome': 'Aura por cima', 'tipo': 'efeito_avatar', 'receita': {'camadas': [{'tipo': 'arquivo', 'arq': a_lot.id, 'lugar': 'sobre'}, {'tipo': 'anel'}]}}
    ok(fadm.post('/estudio/api/efeitos', json=av, headers=H).status_code == 200, 'Efeito de avatar com Lottie por cima da foto + anel: criado')
    ok(fadm.post('/estudio/api/efeitos', json={**av, 'id': 'aura_ruim', 'tipo': 'efeito_avatar', 'receita': {'camadas': [{'tipo': 'raios'}]}}, headers=H).status_code == 400, 'As regras de slot de antes continuam valendo')

    # =============== apagar arquivo ===============
    rd = fadm.delete(f'/estudio/api/arquivos/{a_webp.id}', headers=H)
    ok(rd.status_code == 400 and 'chuva_estrelas' in rd.get_json()['erro'], 'Arquivo em uso por um efeito: não apaga, e diz qual efeito usa')
    ok(fana.delete(f'/estudio/api/arquivos/{a_png.id}', headers=H).status_code == 403, 'Não-admin não apaga arquivo')
    ok(fadm.delete(f'/estudio/api/arquivos/{a_png.id}').status_code == 400, 'Apagar sem o cabeçalho anti-forja: recusado')
    ok(fadm.delete(f'/estudio/api/arquivos/{a_png.id}', headers=H).status_code == 200 and not ea.existe(a_png.id), 'Arquivo sem uso: apaga')
    ok(fadm.delete('/estudio/api/arquivos/naoexiste00', headers=H).status_code == 400, 'Apagar o que não existe: erro de regra')
    fadm.delete('/estudio/api/efeitos/chuva_estrelas', headers=H); fadm.delete('/estudio/api/efeitos/forjado', headers=H)
    ok(fadm.delete(f'/estudio/api/arquivos/{a_webp.id}', headers=H).status_code == 200, 'Tirado o efeito, o arquivo apaga')
    # arquivo que some por fora (banco mexido à mão): o motor recebe a:null e pula a camada
    db.session.query(EstudioArquivo).filter_by(id=a_lot.id).delete(); db.session.commit(); efeitos._invalidar()
    ok(efeitos.mapa_para_cliente()['aura_por_cima']['receita']['camadas'][0]['a'] is None, 'Arquivo que sumiu da biblioteca vira a:null (o motor pula a camada em vez de quebrar)')

    # =============== o /admin não tem mais efeitos ===============
    ok(fadm.get('/admin/api/efeitos').status_code in (404, 405) and fadm.post('/admin/api/efeitos', json=base, headers=H).status_code in (404, 405), 'As rotas de efeitos saíram do /admin')
    adm_html = fadm.get('/admin').data
    ok(b'href="/estudio"' in adm_html and b'data-v="efeitos"' not in adm_html and b'js/efeitos.js' not in adm_html, 'O /admin só tem o atalho pro Estúdio (sem aba de efeitos nem o motor)')
    adm_js = open(os.path.join(RAIZ, 'static', 'js', 'admin.js'), encoding='utf-8').read()
    ok('vEfeitos' not in adm_js and 'darItem' not in adm_js, 'O admin.js não carrega mais o editor de efeitos')

    # =============== o que o navegador promete ===============
    js = open(os.path.join(RAIZ, 'static', 'js', 'efeitos.js'), encoding='utf-8').read()
    est = open(os.path.join(RAIZ, 'static', 'js', 'estudio.js'), encoding='utf-8').read()
    css = open(os.path.join(RAIZ, 'static', 'css', 'estudio.css'), encoding='utf-8').read()
    ok(re.search(r'(?<!\w)eval\(|new Function|document\.write', js + est) is None, 'Motor e Estúdio sem eval/new Function')
    ok(all(re.search(r'[pc]\.' + n + r'(?![A-Za-z0-9_])', js) for n in efeitos.ESQUEMA['arquivo']['params'] if n != 'arq'), 'O motor usa todo parâmetro do esquema da camada Arquivo')
    ok('RE_ARQ' in js and r'\/estudio\/arquivo\/[0-9a-f]{12}' in js, 'O motor só aceita endereço do próprio servidor (/estudio/arquivo/<id>)')
    ok("'/static/js/vendor/lottie_light.min.js" in js and os.path.isfile(os.path.join(RAIZ, 'static', 'js', 'vendor', 'lottie_light.min.js')), 'O Lottie vem do próprio servidor (versão "light", sem CDN)')
    lib = open(os.path.join(RAIZ, 'static', 'js', 'vendor', 'lottie_light.min.js'), encoding='utf-8').read()
    ok(re.search(r'(?<![\w.])eval\(|new Function', lib) is None, 'A biblioteca de Lottie não tem eval nem new Function (não roda código de expressão)')
    ok('MAX_MIDIAS_ANIMADAS' in js and 'LARGURA_MIN_ANIMADA' in js and 'pausarMidias' in js and "'rolando'" in js, 'O motor limita quantas animações tocam juntas, usa imagem parada em lugar pequeno e pausa na rolagem')
    ok('reduz()' in js.split('function montar')[1][:1800], 'Com "reduzir movimento" a montagem não desenha nada')
    ok('data-parte="sobre"' in js and 'ef-av-sobre' in js, 'O avatar tem a 2ª parte (por cima da foto)')
    ok("Efeitos.previa" in est and 'FormData' in est and 'esc(' in est and 'lerVideo' in est, 'O Estúdio faz upload por FormData, tira a capa do vídeo e escapa o texto')
    ok(all(f'.{k}' in css for k in ('es-solta', 'es-arqs', 'es-arq-zona', 'es-arq-img')), 'O CSS do Estúdio tem as zonas de soltar e a biblioteca')
    ok(not re.search(r'[.#](ad|ads)-', css + est), 'Nenhuma classe do Estúdio começa com ad-/ads- (bloqueador de anúncio esconde)')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
