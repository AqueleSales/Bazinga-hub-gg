"""Rodada 40: temas de personagem (Chainsaw Man, JoJo Vento Áureo, Homem-Aranha clássico, NERV) e SHADERS DE PÁGINA (slot `efeito_pagina`).
O que confere: o catálogo (tipo novo, preço, raridade), cada shader aponta pra um preset que EXISTE no motor, o motor não executa código de fora,
toda imagem que o CSS gerado pede existe em disco, todo áudio registrado existe, a insígnia da NERV só vem junto do PACOTE, e o slot equipa/valida certo."""
import json, os, re, subprocess, sys
RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, RAIZ)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db
from app import loja
from app import cosmeticos as cos
from app.models import Role, Person, Posse

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()


C = cos.CATALOGO
SHADERS_JS = ler('app/static/js/shaders.js')
GEN = json.loads(ler('app/cosm_gen.json'))

# ---------- 1. o tipo novo ----------
ok('efeito_pagina' in cos.TIPOS_JSON and 'efeito_pagina' in cos.TIPOS_EQUIPAVEIS, 'efeito_pagina é um slot em JSON equipável')
ok(all('efeito_pagina' in cos.PRECOS[r] for r in ('raro', 'epico', 'lendario')), 'A tabela de preços cobre o shader em raro, épico e lendário')
paginas = {i: d for i, d in C.items() if d['tipo'] == 'efeito_pagina'}
ok(len(paginas) >= 9, f'Há {len(paginas)} shaders de página no catálogo (9 ou mais)')
ok(all(d['preco'] == cos.PRECOS[d['raridade']]['efeito_pagina'] for d in paginas.values()), 'Cada shader custa o da tabela (raridade x tipo)')
ok('efeito_pagina' in cos.ROTULO_TIPO, 'O tipo tem rótulo')
ok('efeito_pagina' in dict((g, t) for g, _, ts in loja.GRUPOS for t in ts) or any('efeito_pagina' in ts for _, _, ts in loja.GRUPOS), 'A vitrine do Armazém tem o tipo em algum grupo do filtro')

# ---------- 2. cada shader aponta pra um preset que existe, com parâmetros sãos ----------
registro = {}
for arq in GEN['arquivos']:
    js = ler(f'app/static/js/cosm_{arq}.js')
    m = re.search(r'shaders:(\{.*?\})\}\);\}\)\(\);', js, re.S)
    if m:
        registro.update(json.loads(m.group(1)))
ids_pagina = {d['valor'] for d in paginas.values()}
ok(ids_pagina == set(registro), f'Todo shader do catálogo está registrado no JS gerado (e só eles): {sorted(ids_pagina ^ set(registro))}')
presets = set(re.findall(r'^\s*PRESETS\.([a-z_]+) = ', SHADERS_JS, re.M))
ok({'serra', 'aranha', 'eva', 'jojo_tempo', 'cyber', 'matrix', 'ondinhas', 'arcoiris', 'sapos'} <= presets, f'O motor tem os 9 presets ({sorted(presets)})')
ok(all(r['preset'] in presets for r in registro.values()), 'Todo shader registrado usa um preset que existe')
ok(all(re.match(r'^#[0-9a-fA-F]{6}$', r.get('cor', '#000000')) and all(isinstance(v, (str, int, float)) for v in r.values()) for r in registro.values()), 'Parâmetros dos shaders são cores hex e números/texto simples')
espera_ok = all(5 <= r.get('espera', 12) <= 60 for r in registro.values())
ok(espera_ok, 'Quem depende de ficar parado espera de 5 a 60 s (nem irritante, nem inútil)')
ok(registro['denji_serra_ligada'.replace('denji_serra_ligada', 'dnj_motosserra_ligada')]['preset'] == 'serra' if 'dnj_motosserra_ligada' in registro else False, 'Denji: a motosserra ligada é o preset "serra"')

# ---------- 3. o motor é fechado: nada de código vindo de fora ----------
ok(not re.search(r'\beval\s*\(|new\s+Function|\.innerHTML\s*=|document\.write|insertAdjacentHTML', SHADERS_JS), 'O motor não usa eval, new Function, innerHTML nem document.write')
ok("pointer-events:none" in SHADERS_JS.replace(' ', '').replace('pointer-events:none', 'pointer-events:none'), 'O canvas dos shaders não pega clique (pointer-events: none)')
ok('data-sem-shaders' in SHADERS_JS and 'data-reduz-mov' in SHADERS_JS and 'pointer: fine' in SHADERS_JS, 'O motor respeita a opção da conta, "reduzir movimento" e só liga com mouse de verdade')
ok(re.search(r'hooks\.somOk\(\)', SHADERS_JS) is not None, 'O som dos shaders respeita "Não perturbar" e o volume (somOk)')
r = subprocess.run(['node', '--check', os.path.join(RAIZ, 'app', 'static', 'js', 'shaders.js')], capture_output=True, text=True)
ok(r.returncode == 0, 'shaders.js passa no node --check' + (r.stderr[:200] if r.returncode else ''))
chat = ler('app/templates/chat.html')
ok("js/shaders.js" in chat and "css/shaders.css" in chat and 'Shaders.definir(eq.efeito_pagina)' in chat and 'Shaders.iniciar(' in chat, 'O chat carrega o motor e aplica o shader equipado')
ok('data-sem-shaders' in chat, 'O HTML nasce com data-sem-shaders quando a conta desligou')

# ---------- 4. a arte dos temas: só SÍMBOLOS por código; imagem de verdade só a Lança de Longinus e os ゴゴゴ ----------
PERMITIDAS = {'eva/lanca.png', 'eva/lanca_pin.png', 'jojo/gogogo.png'}
usadas_img, vars_usadas, vars_definidas, audios_faltam = set(), set(), set(), set()
for arq in GEN['arquivos']:
    css = ler(f'app/static/css/cosm_{arq}.css')
    usadas_img |= set(re.findall(r'/static/img/cosm/([a-z_]+/[a-z_]+\.png)', css))
    vars_usadas |= set(re.findall(r'var\((--img-[a-z0-9-]+)\)', css))
    vars_definidas |= set(re.findall(r'(--img-[a-z0-9-]+):url\("data:image/svg\+xml,', css))
    js = ler(f'app/static/js/cosm_{arq}.js')
    usadas_img |= set(re.findall(r'/static/img/cosm/([a-z_]+/[a-z_]+\.png)', js))
    for u in set(re.findall(r"/static/audio/[A-Za-z0-9_\-]+\.(?:mp3|ogg|wav)", js)):
        if not os.path.isfile(os.path.join(RAIZ, 'app', u.lstrip('/'))):
            audios_faltam.add(u)
ok(usadas_img <= PERMITIDAS, f'O CSS/JS gerado só pede as imagens permitidas (lança e ゴゴゴ): {sorted(usadas_img - PERMITIDAS)}')
ok(all(os.path.isfile(os.path.join(RAIZ, 'app/static/img/cosm', f)) for f in usadas_img), 'Toda imagem pedida existe em disco')
ok({'eva/lanca_pin.png', 'jojo/gogogo.png'} <= usadas_img, 'A lança (pin) e o ゴゴゴ de verdade são usados pelos temas')
ok(vars_usadas and vars_usadas <= vars_definidas, f'Toda peça usada (var(--img-...)) é definida no :root do mesmo arquivo: faltam {sorted(vars_usadas - vars_definidas)[:3]}')
ok(not audios_faltam, f'Todo áudio registrado existe em disco {sorted(audios_faltam)[:3]}')
resto = sorted(os.path.relpath(os.path.join(d, f), os.path.join(RAIZ, 'app/static/img/cosm')).replace(os.sep, '/') for d, _, fs in os.walk(os.path.join(RAIZ, 'app/static/img/cosm')) for f in fs)
ok(set(resto) == PERMITIDAS, f'A pasta de imagens guarda SÓ a lança, o pin da lança e os ゴゴゴ: {resto}')
arte = ler('tools/cosm/arte.js')
nomes_arte = re.findall(r"def\('([a-z_]+)', '([a-z_0-9]+)'", arte)
proibidos = [f'{t}/{n}' for t, n in nomes_arte if re.search(r'busto|pochita|stand_(gold|sticky|purple|spice|moody|sex)|^eva0|classico|swing|mascara|nyaako|raposa|reze$|reze_bomba', n)]
ok(len(nomes_arte) >= 25 and not proibidos, f'A biblioteca de arte só tem símbolos e objetos (sem busto, Stand, rosto ou boneco): {proibidos}')
ok(not os.path.exists(os.path.join(RAIZ, 'tools/cosm/arte_b.js')), 'O arquivo dos bustos/bonecos (arte_b.js) foi apagado')
temas_js = ''.join(ler('tools/cosm/temas/' + f) for f in os.listdir(os.path.join(RAIZ, 'tools/cosm/temas')) if f.startswith(('anime_chainsaw', 'anime_jojo', 'anime_eva', 'anime_edge', 'quadrinhos_aranha_classico')))
ok(not re.search(r"busto|pochita|'nyaako'|aki_raposa|'swing'|'classico'|reze_bomba|'eva0[012]'", temas_js), 'Nenhum tema de personagem pede busto, Stand-boneco, Pochita, Eva-cabeça ou Homem-Aranha-boneco')
ok(not re.search(r"https?://", ' '.join(re.findall(r"url\(\s*['\"]?https?://[^)]*\)", ''.join(ler(f'app/static/css/cosm_{a}.css') for a in GEN['arquivos'])))), 'Nenhuma imagem do CSS gerado vem de outro site (tudo é nosso)')
ok(sum(len(ler(f'app/static/css/cosm_{a}.css')) for a in GEN['arquivos']) < 4_500_000, 'O CSS gerado todo fica abaixo de 4,5 MB (a arte repetida vira variável)')

# ---------- 5. os temas novos estão completos ----------
novos = {'denji': 13, 'reze': 12, 'jj_giorno': 13, 'jj_bruno': 12, 'jj_mista': 12, 'jj_narancia': 12, 'jj_fugo': 12, 'jj_trish': 12, 'aranha_classico': 13, 'eva_nerv': 13, 'makima': 12, 'power': 12, 'aki': 12, 'jj_abba': 12, 'eva_zero': 12, 'eva_um': 12, 'eva_dois': 12, 'edg_david': 12, 'edg_lucy': 12, 'edg_rebecca': 12, 'edg_smasher': 12}
for t, minimo in novos.items():
    itens = [d for d in C.values() if d['tema'] == t and d['tipo'] not in ('pacote', 'badge')]
    ok(len(itens) >= minimo, f'Tema {t}: tem {len(itens)} itens (esperado {minimo}+)')
    tipos = {d['tipo'] for d in itens}
    ok({'moldura', 'nome', 'placa', 'faixa', 'efeito_avatar', 'efeito_perfil', 'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota', 'efeito_servidor'} <= tipos, f'Tema {t}: tem os 12 slots')
    ok(f'pacote:{t}' in C, f'Tema {t}: tem pacote')
ok(all(d['raridade'] == 'lendario' for t in ('denji', 'reze', 'makima', 'power', 'aki', 'jj_giorno', 'jj_bruno', 'jj_mista', 'jj_narancia', 'jj_fugo', 'jj_trish', 'jj_abba', 'aranha_classico') for d in C.values() if d['tema'] == t and d['tipo'] not in ('pacote',)), 'Chainsaw Man, JoJo e Homem-Aranha são lendários')
ok(all(d['raridade'] == 'epico' for d in C.values() if d['tema'] in ('eva_nerv', 'eva_zero', 'eva_um', 'eva_dois', 'edgerunners', 'edg_david', 'edg_lucy', 'edg_rebecca', 'edg_smasher') and d['tipo'] != 'pacote'), 'Evangelion e Cyberpunk são épicos')
ok(C['pacote:eva_nerv']['preco'] > 0, 'O pacote NERV tem preço')
ok(all(len(cos.PACOTES[t]) == 12 for t in ('denji', 'jj_giorno', 'aranha_classico', 'eva_nerv')), 'Os pacotes com shader equipam 12 itens (inclusive o shader)')
ids = [d['valor'] for d in C.values() if d['tema'] in novos]
ok(all(re.match(r'^[a-z_]{1,24}$', i) for i in ids), 'Todo id de item novo é [a-z_] até 24 (senão a prévia some)')

# ---------- 6. a insígnia da NERV só vem com o PACOTE ----------
with app.app_context():
    db.create_all()
    papel = Role(name='MEMBROS', color='#fff'); db.session.add(papel); db.session.commit()
    p = Person(name='Ana', email='ana@x.com', role_id=papel.id, bazinga_coins=50000); db.session.add(p)
    q = Person(name='Beto', email='beto@x.com', role_id=papel.id, bazinga_coins=50000); db.session.add(q)
    db.session.commit()
    loja._ULTIMA = {} if hasattr(loja, '_ULTIMA') else None
    ok('badge:nerv_marca' in C and C['badge:nerv_marca'].get('preco') is None, 'A insígnia da NERV existe e NÃO está à venda')
    avulso = next(i for i, d in C.items() if d['tema'] == 'eva_nerv' and d['tipo'] == 'nome')
    r1 = loja.comprar(p, avulso)
    posses = {x.item_id for x in Posse.query.filter_by(person_id=p.id)}
    ok(avulso in posses and 'badge:nerv_marca' not in posses, 'Item avulso do pacote NERV NÃO dá a insígnia')
    r2 = loja.comprar(q, 'pacote:eva_nerv')
    posses_q = {x.item_id for x in Posse.query.filter_by(person_id=q.id)}
    ok('badge:nerv_marca' in posses_q and 'pacote:eva_nerv' in posses_q, 'Comprar o PACOTE NERV entrega a insígnia')
    ok('badge:nerv_marca' in r2['entregues'], 'A resposta da compra lista a insígnia entre o que foi entregue')
    r3 = loja.comprar(p, 'pacote:eva_um')
    ok('badge:nerv_marca' in {x.item_id for x in Posse.query.filter_by(person_id=p.id)}, 'O PACOTE de uma unidade (Unidade-01) também entrega a insígnia da NERV')
    # comprar o pacote de novo não duplica (já tem)
    ok(len([x for x in Posse.query.filter_by(person_id=q.id, item_id='badge:nerv_marca')]) == 1, 'A insígnia é uma posse só')

    # ---------- 7. o slot equipa e valida ----------
    alvo = next(i for i, d in C.items() if d['tipo'] == 'efeito_pagina' and d['tema'] == 'eva_nerv')
    cos.definir_slot(q, 'efeito_pagina', C[alvo]['valor']); db.session.commit()
    ok(cos.equipados_da_pessoa(q).get('efeito_pagina') == C[alvo]['valor'], 'O shader equipado fica na conta')
    q.equipados = json.dumps({'efeito_pagina': 'inventado_x', 'efeito_chat': '<script>'})
    ok(cos.equipados_da_pessoa(q) == {}, 'Id inventado ou com HTML nunca vira equipado')
    cos.definir_slot(q, 'efeito_pagina', None)
    ok('efeito_pagina' not in cos.equipados_da_pessoa(q), 'Tirar o shader limpa o slot')

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
