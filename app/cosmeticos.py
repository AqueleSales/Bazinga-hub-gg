"""Catálogo único de cosméticos, patentes de nível, insígnias e posse.

Fonte da verdade dos itens que NÃO são livres. Os itens livres (moldura "neon", placa
"ouro"...) continuam nas tuplas de `utils.py` e nos catálogos do `chat.html`; aqui
moram os que exigem posse - o servidor só aceita equipar o que a pessoa TEM.

Convenções:
  * `item_id` = "<tipo>:<id>" (ex.: "moldura:gogeta", "badge:criador", "pacote:sasuke").
    É o que vai na tabela `Posse` e nos eventos do socket.
  * O `<id>` sozinho é o que vai pro banco/CSS: `Person.moldura = 'gogeta'` -> classe
    `.moldura-gogeta`. Por isso o id nunca é texto livre: só entra o que está aqui.
  * Nada neste arquivo toca o banco no import (models só é importado dentro das funções).
"""
import json

# ==========================================
# TEMAS DO LABORATÓRIO (só o dono e o amigo beta tester)
# ==========================================
TEMAS = {
    'gogeta': {'nome': 'Gogeta', 'cor': '#ff9d2e', 'desc': 'Fusão, aura dourada e a Punição de Alma.'},
    'sasuke': {'nome': 'Sasuke', 'cor': '#8b5cf6', 'desc': 'Chidori, Sharingan e a chama negra.'},
    'fusao': {'nome': 'Fusão', 'cor': '#e879f9', 'desc': 'Duas chamas, uma só. Só nós dois.'},
}

# ==========================================
# PATENTES (substituem Novato/Explorador/...)
# ------------------------------------------------------------
# O nível vai de 1 a 1000+ (XP total, nunca zera - ver utils.py). A patente é a
# "faixa" do nível; cada uma tem 3 subníveis visuais (I, II, III), repartidos em
# terços da faixa. `anim` (0-4) diz quanto o ícone se mexe: quanto maior a patente,
# mais animação. O desenho do ícone mora no chat.html (`svgPatente`), por id.
# `de`/`ate` incluem os dois extremos; `ate=None` = sem teto (Panteão).
# ==========================================
PATENTES = [
    {'id': 'iniciado',    'nome': 'Iniciado',    'de': 1,   'ate': 9,    'anim': 0, 'cor': '#d98a4a'},
    {'id': 'aprendiz',    'nome': 'Aprendiz',    'de': 10,  'ate': 24,   'anim': 0, 'cor': '#a78bfa'},
    {'id': 'explorador',  'nome': 'Explorador',  'de': 25,  'ate': 49,   'anim': 1, 'cor': '#f5c542'},
    {'id': 'desbravador', 'nome': 'Desbravador', 'de': 50,  'ate': 89,   'anim': 1, 'cor': '#2dd4bf'},
    {'id': 'veterano',    'nome': 'Veterano',    'de': 90,  'ate': 149,  'anim': 2, 'cor': '#60a5fa'},
    {'id': 'heroi',       'nome': 'Herói',       'de': 150, 'ate': 229,  'anim': 2, 'cor': '#38bdf8'},
    {'id': 'lenda',       'nome': 'Lenda',       'de': 230, 'ate': 329,  'anim': 3, 'cor': '#fb923c'},
    {'id': 'campeao',     'nome': 'Campeão',     'de': 330, 'ate': 449,  'anim': 3, 'cor': '#a5f3fc'},
    {'id': 'semideus',    'nome': 'Semideus',    'de': 450, 'ate': 599,  'anim': 3, 'cor': '#fbbf24'},
    {'id': 'tita',        'nome': 'Titã',        'de': 600, 'ate': 749,  'anim': 4, 'cor': '#f97316'},
    {'id': 'olimpiano',   'nome': 'Olimpiano',   'de': 750, 'ate': 899,  'anim': 4, 'cor': '#fef3c7'},
    {'id': 'panteao',     'nome': 'Panteão',     'de': 900, 'ate': None, 'anim': 4, 'cor': '#e879f9'},
]
ROMANOS = ('I', 'II', 'III')


def _limites_sub(p):
    """Níveis em que começa o subnível I, II e III da patente."""
    if p['ate'] is None:
        return [p['de'], p['de'] + 50, p['de'] + 100]        # Panteão: 900 / 950 / 1000+
    tam = p['ate'] - p['de'] + 1
    return [p['de'], p['de'] + tam // 3, p['de'] + (tam * 2) // 3]


for _i, _p in enumerate(PATENTES):
    _p['idx'] = _i + 1
    _p['limites'] = _limites_sub(_p)


def patente_do_nivel(nivel):
    """Tudo o que a interface precisa saber da patente de um nível (o cliente só desenha)."""
    nivel = max(int(nivel or 1), 1)
    pos = 0
    for i, p in enumerate(PATENTES):
        if nivel >= p['de']:
            pos = i
    p = PATENTES[pos]
    sub = 1
    for k, inicio in enumerate(p['limites']):
        if nivel >= inicio:
            sub = k + 1
    nome_completo = f"{p['nome']} {ROMANOS[sub - 1]}"

    # Próxima vez que o ícone muda: o próximo subnível ou a próxima patente.
    if sub < 3:
        proximo = {'nivel': p['limites'][sub], 'nome': f"{p['nome']} {ROMANOS[sub]}", 'nova_patente': False}
    elif pos + 1 < len(PATENTES):
        seguinte = PATENTES[pos + 1]
        proximo = {'nivel': seguinte['de'], 'nome': f"{seguinte['nome']} I", 'nova_patente': True}
    else:
        proximo = None
    return {'id': p['id'], 'idx': p['idx'], 'nome': p['nome'], 'sub': sub, 'romano': ROMANOS[sub - 1],
            'nome_completo': nome_completo, 'de': p['de'], 'ate': p['ate'], 'anim': p['anim'], 'cor': p['cor'],
            'proximo': proximo}


def patentes_para_json():
    """A tabela inteira (galeria do inventário): `de`, `ate` e os limites dos subníveis."""
    return [{k: p[k] for k in ('id', 'idx', 'nome', 'de', 'ate', 'anim', 'cor', 'limites')} for p in PATENTES]


def patente_comeca_em(nivel):
    """Nome da patente que COMEÇA exatamente neste nível (None se não começa nenhuma, ou se é a 1ª)."""
    for p in PATENTES[1:]:
        if p['de'] == nivel:
            return p['nome']
    return None


# ==========================================
# CATÁLOGO DE ITENS COM POSSE
# ==========================================
# Tipos que ocupam uma coluna do Person (ids validados também em utils.py):
TIPOS_COLUNA = {'moldura': 'moldura', 'placa': 'placa', 'nome': 'nome_estilo', 'faixa': 'banner_color'}
# Tipos guardados no JSON `Person.equipados` (um slot por tipo):
TIPOS_JSON = ('efeito_avatar', 'efeito_perfil', 'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota')
TIPOS_EQUIPAVEIS = tuple(TIPOS_COLUNA) + TIPOS_JSON
ROTULO_TIPO = {
    'badge': 'Insígnia', 'moldura': 'Moldura', 'placa': 'Placa', 'nome': 'Estilo de nome', 'faixa': 'Faixa do perfil',
    'efeito_avatar': 'Efeito de avatar', 'efeito_perfil': 'Efeito de perfil', 'efeito_fala': 'Efeito de fala',
    'efeito_radar': 'Efeito do radar', 'efeito_chat': 'Efeito do chat', 'som_call': 'Som de entrada', 'pin_nota': 'Pin de nota',
    'efeito_servidor': 'Efeito de servidor',
    'pacote': 'Pacote de tema',
}

CATALOGO = {}   # item_id -> descritor


def _item(tipo, id_, nome, desc, tema=None, raridade='lendario', **extra):
    CATALOGO[f'{tipo}:{id_}'] = {'id': f'{tipo}:{id_}', 'tipo': tipo, 'valor': id_, 'nome': nome, 'desc': desc,
                                 'tema': tema, 'raridade': raridade, 'exclusivo': True, **extra}


# ---- Insígnias (aparecem no cartão de perfil, ao lado do nome) ----
# A ordem aqui é a ordem em que aparecem no cartão. Regras de quem recebe cada uma:
#   criador / coder / so_nos  -> manual (LABORATORIO abaixo ou conceder_item.py)
#   alpha_tester              -> lista de pessoas (ALPHA_NOMES, concedida por atualizar_banco.py / conceder_item.py)
#   beta_tester               -> TODO MUNDO (o app inteiro está no beta): garantir_insignias_automaticas()
#   bazinga                   -> quem é membro do servidor Bazinga (id em config_app 'servidor_bazinga_id')
_item('badge', 'criador', 'Criador', 'Quem construiu o Panteão do zero, tijolo por tijolo.', raridade='unico')
_item('badge', 'alpha_tester', 'Alpha Tester', 'Esteve aqui antes de todo mundo e viu o Panteão nascer.', raridade='unico')
_item('badge', 'beta_tester', 'Beta Tester', 'Está no beta. Cada bug achado acorda a Medusa.', raridade='lendario')
_item('badge', 'bazinga', 'BAZINGA', 'on top!', raridade='lendario')
_item('badge', 'coder', 'Coder', 'Mexeu no código por baixo do capô.', raridade='unico')
_item('badge', 'so_nos', 'Só nós', 'Uma sarça que arde e não se consome. Só quem começou isso tem.', raridade='unico', tema='fusao')

# ---- Laboratório: itens do tema Gogeta ----
_item('moldura', 'gogeta', 'Aura Dourada', 'Anel de ki dourado com chamas subindo.', 'gogeta')
_item('placa', 'gogeta', 'Em Chamas', 'A placa pega fogo: brasas sobem atrás do seu nome.', 'gogeta')
_item('nome', 'gogeta', 'Super Saiyajin', 'Ouro e laranja pulsando, com um clarão de energia.', 'gogeta')
_item('faixa', 'gogeta', 'Aura Saiyajin', 'Energia dourada subindo pela faixa do perfil.', 'gogeta')
_item('efeito_avatar', 'gogeta', 'Aura Super Saiyajin', 'Uma aura de chamas douradas atrás da sua foto.', 'gogeta')
_item('efeito_perfil', 'gogeta', 'Poeira Cósmica e Punição de Alma', 'Poeira de ki dourada sobe pelo cartão e, de vez em quando, partículas giram até formar a bolha colorida da Punição de Alma, que estoura.', 'gogeta')
_item('efeito_fala', 'gogeta', 'Ki ao Falar', 'Quando você fala na call, o ki explode em volta da sua foto.', 'gogeta')
_item('efeito_radar', 'gogeta', 'Ondas de Ki', 'As ondas do seu radar viram ondas de energia dourada.', 'gogeta')
_item('efeito_chat', 'gogeta', 'Ki no Teclado', 'A barra de mensagem brilha enquanto você digita e solta faíscas ao enviar.', 'gogeta')
_item('som_call', 'gogeta', 'Teleporte', 'Um som de teletransporte toca quando você entra numa call.', 'gogeta')
_item('pin_nota', 'gogeta', 'Esfera de Estrelas', 'Suas notas no mapa viram uma esfera laranja de estrelas.', 'gogeta')

# ---- Laboratório: itens do tema Sasuke ----
_item('moldura', 'sasuke', 'Sharingan', 'Anel vermelho de Sharingan com três tomoe, pulsando.', 'sasuke')
_item('placa', 'sasuke', 'Cinzas Roxas', 'Cinza e poeira subindo, com um brilho roxo por trás.', 'sasuke')
_item('nome', 'sasuke', 'Mangekyō', 'Roxo e preto com um tremor vermelho de Sharingan.', 'sasuke')
_item('faixa', 'sasuke', 'Tempestade Roxa', 'Nuvens roxas e relâmpagos na faixa do perfil.', 'sasuke')
_item('efeito_avatar', 'sasuke', 'Olho Brilhante', 'O Sharingan brilha em vermelho de tempos em tempos e volta ao normal.', 'sasuke')
_item('efeito_perfil', 'sasuke', 'Raios e Amaterasu', 'Raios caindo pelo cartão e uma chama negra de Amaterasu que sobe de leve da base e some.', 'sasuke')
_item('efeito_fala', 'sasuke', 'Chidori ao Falar', 'Quando você fala na call, relâmpagos estalam em volta da sua foto.', 'sasuke')
_item('efeito_radar', 'sasuke', 'Ondas Roxas', 'As ondas do seu radar viram ondas roxas com um estalo de raio.', 'sasuke')
_item('efeito_chat', 'sasuke', 'Raio no Teclado', 'A barra de mensagem crepita enquanto você digita e solta um raio ao enviar.', 'sasuke')
_item('som_call', 'sasuke', 'Sharingan', 'O som do Sharingan despertando toca quando você entra numa call.', 'sasuke')
_item('pin_nota', 'sasuke', 'Kunai Roxa', 'Suas notas no mapa viram uma kunai roxa.', 'sasuke')

# ---- Laboratório: itens do tema Fusão (só nós dois) ----
_item('moldura', 'fusao', 'Fusão', 'Laranja e roxo girando juntos num anel só.', 'fusao')
_item('placa', 'fusao', 'Duas Chamas', 'Uma chama laranja e uma roxa disputando a placa.', 'fusao')
_item('nome', 'fusao', 'Fusão', 'O nome muda do laranja pro roxo e volta.', 'fusao')
_item('faixa', 'fusao', 'Fusão', 'Chamas laranja e roxa se misturando na faixa.', 'fusao')

# ---- Efeito de servidor: o DONO aplica a um servidor dele (Server.efeito); todo membro vê no ícone da barra, no
# cabeçalho e no pino do mapa. Não entra nos pacotes (não é um slot da pessoa, é do servidor). ----
_item('efeito_servidor', 'gogeta', 'Chamas do Servidor', 'O ícone do servidor ganha uma aura de chamas douradas (barra, cabeçalho e mapa).', 'gogeta')
_item('efeito_servidor', 'sasuke', 'Tempestade do Servidor', 'O ícone do servidor crepita com relâmpagos roxos (barra, cabeçalho e mapa).', 'sasuke')
_item('efeito_servidor', 'fusao', 'Fusão do Servidor', 'Laranja e roxo disputando o ícone do servidor (barra, cabeçalho e mapa).', 'fusao')

# ---- Pacotes (equipam o tema inteiro de uma vez; o conteúdo está em PACOTES) ----
_item('pacote', 'gogeta', 'Gogeta completo', 'Equipa tudo do tema Gogeta de uma vez.', 'gogeta')
_item('pacote', 'sasuke', 'Sasuke completo', 'Equipa tudo do tema Sasuke de uma vez.', 'sasuke')
_item('pacote', 'fusao', 'Fusão completa', 'Equipa a moldura, a placa, o nome e a faixa da Fusão.', 'fusao')


def _pacote(tema):
    """tipo -> id de cada item do tema (só os equipáveis)."""
    escolhas = {}
    for d in CATALOGO.values():
        # o 1º item de cada tipo é o "principal" do tema; os extras são opcionais
        if d['tema'] == tema and d['tipo'] in TIPOS_EQUIPAVEIS:
            escolhas.setdefault(d['tipo'], d['valor'])
    return escolhas


# Calculado depois que todos os itens existem. Se um tipo novo entrar no catálogo, o pacote já o pega.
PACOTES = {}


def recalcular_pacotes():
    for tema in TEMAS:
        PACOTES[tema] = _pacote(tema)


recalcular_pacotes()


def ids_do_tipo(tipo):
    """Ids (sem o prefixo do tipo) dos itens EXCLUSIVOS desse tipo."""
    return tuple(d['valor'] for d in CATALOGO.values() if d['tipo'] == tipo)


def item_exclusivo(tipo, valor):
    return f'{tipo}:{valor}' in CATALOGO


def efeito_servidor_valido(valor):
    """O id do efeito de servidor se o catálogo conhece; senão None (nunca chega um id solto no class="" de ninguém)."""
    return valor if valor and item_exclusivo('efeito_servidor', valor) else None


def descritor(item_id):
    return CATALOGO.get(item_id)


# ==========================================
# O QUE CADA PESSOA RECEBE NO LABORATÓRIO
# ------------------------------------------------------------
# Identidade resolvida UMA VEZ, na hora de conceder (por @username -> person_id), e dali
# em diante a posse é por id: se a pessoa trocar o @, nada muda; se outra pessoa pegar o
# @ antigo, não herda nada. Por isso conceder é um ato explícito (`atualizar_banco.py` ou
# `conceder_item.py`), nunca algo que roda sozinho no boot.
# ==========================================
def _itens_do_tema(tema):
    return [i for i, d in CATALOGO.items() if d['tema'] == tema and d['tipo'] != 'badge']


LABORATORIO = {
    'aquele.sales': (['badge:criador', 'badge:beta_tester', 'badge:coder', 'badge:so_nos']
                     + _itens_do_tema('gogeta') + _itens_do_tema('fusao')),
    'filippo.chiarion': (['badge:criador', 'badge:beta_tester', 'badge:coder', 'badge:so_nos']
                         + _itens_do_tema('sasuke') + _itens_do_tema('fusao')),
}


# ==========================================
# INSÍGNIAS POR REGRA (não precisam de concessão manual)
# ==========================================
BADGE_BETA = 'badge:beta_tester'
BADGE_BAZINGA = 'badge:bazinga'
ALPHA_NOMES = ['filippo', 'fernando albernaz', 'gabriel alves santana', 'gabriel silva', 'arthur neves fiorotti', 'juarez']
_cache_bazinga = {}


def _normalizar(texto):
    import unicodedata
    t = unicodedata.normalize('NFKD', texto or '')
    return ' '.join(''.join(c for c in t if not unicodedata.combining(c)).lower().split())


def id_servidor_bazinga():
    """Id do servidor Bazinga (config_app 'servidor_bazinga_id', ou a env BAZINGA_SERVER_ID). Por ID, nunca por nome:
    qualquer um pode criar um servidor chamado "Bazinga". None se ainda não foi definido."""
    import os
    if 'id' in _cache_bazinga:
        return _cache_bazinga['id']
    from .models import ConfigApp
    valor = os.environ.get('BAZINGA_SERVER_ID')
    if not valor:
        c = ConfigApp.query.get('servidor_bazinga_id')
        valor = c.valor if c else None
    if valor and str(valor).isdigit():
        _cache_bazinga['id'] = int(valor)   # só guarda quando existe: se ainda não foi definido, olha de novo da próxima vez
        return _cache_bazinga['id']
    return None


def garantir_insignias_automaticas(pessoa, posses):
    """Beta pra todo mundo; BAZINGA pra quem está no servidor Bazinga. Mexe em `posses` e devolve True se concedeu algo
    (quem chama comita). Só consulta o servidor quando a pessoa ainda NÃO tem a insígnia."""
    mudou = False
    if BADGE_BETA not in posses and conceder_item(pessoa.id, BADGE_BETA, 'beta'):
        posses.add(BADGE_BETA); mudou = True
    if BADGE_BAZINGA not in posses:
        sid = id_servidor_bazinga()
        if sid:
            from .utils import eh_membro
            if eh_membro(pessoa, sid) and conceder_item(pessoa.id, BADGE_BAZINGA, 'bazinga'):
                posses.add(BADGE_BAZINGA); mudou = True
    return mudou


def posses_com_regras(pessoa):
    """posses_da_pessoa + insígnias automáticas (1 escrita só na primeira vez de cada insígnia). Nunca quebra o /chat."""
    from .models import db
    posses = posses_da_pessoa(pessoa.id)
    try:
        if garantir_insignias_automaticas(pessoa, posses):
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'[ERRO INSIGNIAS AUTOMATICAS] {e}')
        posses = posses_da_pessoa(pessoa.id)
    return posses


def conceder_insignias_iniciais(log=print):
    """Passo único do atualizar_banco.py (idempotente): beta pra todos, define o servidor Bazinga e dá a insígnia aos
    membros, e alpha pra lista ALPHA_NOMES (por nome de exibição; avisa se não achar ou se tiver nome repetido)."""
    from sqlalchemy import func
    from .models import db, Person, Server, ConfigApp
    todas = Person.query.all()
    novos = sum(1 for p in todas if conceder_item(p.id, BADGE_BETA, 'beta'))
    log(f'✅ Beta Tester: {novos} pessoa(s) receberam agora (de {len(todas)}).')

    srv_cfg = ConfigApp.query.get('servidor_bazinga_id')
    if not (srv_cfg and srv_cfg.valor):
        srv = Server.query.filter(func.lower(Server.name) == 'bazinga').order_by(Server.id).first()
        if srv:
            db.session.add(ConfigApp(chave='servidor_bazinga_id', valor=str(srv.id)))
            db.session.flush()
            log(f'✅ Servidor Bazinga definido: id {srv.id} ("{srv.name}", dono id {srv.owner_id}). Confira se é o certo.')
    srv_cfg = ConfigApp.query.get('servidor_bazinga_id')
    if srv_cfg and srv_cfg.valor and srv_cfg.valor.isdigit():
        srv = Server.query.get(int(srv_cfg.valor))
        if srv:
            n = sum(1 for m in srv.members if conceder_item(m.id, BADGE_BAZINGA, 'bazinga'))
            log(f'✅ BAZINGA: {n} membro(s) do servidor "{srv.name}" receberam agora (de {len(srv.members)}).')
    else:
        log('ℹ️ Não achei um servidor chamado "Bazinga". Defina com a env BAZINGA_SERVER_ID ou insira em config_app.')

    por_nome = {}
    for p in todas:
        por_nome.setdefault(_normalizar(p.name), []).append(p)
    for nome in ALPHA_NOMES:
        achados = por_nome.get(nome, [])
        if len(achados) == 1:
            ok = conceder_item(achados[0].id, 'badge:alpha_tester', 'alpha')
            log(f'✅ Alpha Tester: {achados[0].name} (id {achados[0].id}, @{achados[0].username}) {"recebeu" if ok else "já tinha"}.')
        elif not achados:
            log(f'⚠️ Alpha Tester: não achei "{nome}". Use: python conceder_item.py <@usuario> badge:alpha_tester')
        else:
            log(f'⚠️ Alpha Tester: "{nome}" bate com {len(achados)} contas ({", ".join("@" + str(a.username) for a in achados)}). '
                f'Use conceder_item.py na certa.')
    db.session.commit()


# ==========================================
# POSSE (banco)
# ==========================================
def posses_da_pessoa(person_id):
    """Conjunto de item_id que a pessoa possui. UMA query."""
    from .models import Posse
    return {p.item_id for p in Posse.query.filter_by(person_id=person_id).all()}


def pessoa_tem(person_id, item_id, posses=None):
    if item_id not in CATALOGO:
        return True            # item livre: todo mundo tem
    if posses is None:
        posses = posses_da_pessoa(person_id)
    return item_id in posses


def conceder_item(person_id, item_id, origem='sistema'):
    """Dá o item à pessoa. Idempotente. Só faz `add` (quem chama comita)."""
    from .models import db, Posse
    if item_id not in CATALOGO:
        raise ValueError(f'Item desconhecido: {item_id}')
    if Posse.query.filter_by(person_id=person_id, item_id=item_id).first():
        return False
    db.session.add(Posse(person_id=person_id, item_id=item_id, origem=origem))
    return True


def revogar_item(person_id, item_id):
    from .models import Posse
    return Posse.query.filter_by(person_id=person_id, item_id=item_id).delete(synchronize_session=False)


def conceder_laboratorio(log=print):
    """Concede o pacote inicial do laboratório aos dois testers (por @username)."""
    from .models import db, Person
    total = 0
    for username, itens in LABORATORIO.items():
        pessoa = Person.query.filter_by(username=username).first()
        if not pessoa:
            log(f'ℹ️ Laboratório: não achei @{username} (ainda não entrou, ou mudou o @). '
                f'Use "python conceder_item.py {username} tudo" depois.')
            continue
        novos = sum(1 for i in itens if conceder_item(pessoa.id, i, 'laboratorio'))
        total += novos
        log(f'✅ Laboratório: @{username} (id {pessoa.id}) recebeu {novos} item(ns) novo(s) de {len(itens)}.')
    db.session.commit()
    return total


# ==========================================
# EQUIPADOS (JSON em Person.equipados)
# ==========================================
def equipados_da_pessoa(pessoa):
    """Dict {tipo: id} dos slots em JSON. Só devolve o que o catálogo conhece (defensivo:
    o que vai parar num class="" no navegador de todo mundo nunca vem do banco cru)."""
    bruto = getattr(pessoa, 'equipados', None)
    if not bruto:
        return {}
    try:
        dados = json.loads(bruto)
    except (TypeError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}
    return {t: v for t, v in dados.items() if t in TIPOS_JSON and isinstance(v, str) and item_exclusivo(t, v)}


def guardar_equipados(pessoa, equipados):
    limpo = {t: v for t, v in equipados.items() if t in TIPOS_JSON and v and item_exclusivo(t, v)}
    pessoa.equipados = json.dumps(limpo, separators=(',', ':')) if limpo else None


def valor_atual_do_slot(pessoa, tipo):
    """O que a pessoa tem equipado em um slot (tipo), qualquer que seja o jeito de guardar."""
    if tipo == 'faixa':
        cor = pessoa.banner_color or ''
        return cor[5:] if cor.startswith('anim:') else None
    if tipo in TIPOS_COLUNA:
        return getattr(pessoa, TIPOS_COLUNA[tipo]) or None
    return equipados_da_pessoa(pessoa).get(tipo)


def definir_slot(pessoa, tipo, valor):
    """Grava o valor no slot (None limpa). NÃO valida posse - quem chama valida."""
    if tipo == 'faixa':
        pessoa.banner_color = f'anim:{valor}' if valor else None
        if valor:
            pessoa.banner_url = None
            pessoa.banner_ajuste = None
    elif tipo in TIPOS_COLUNA:
        setattr(pessoa, TIPOS_COLUNA[tipo], valor or None)
    elif tipo in TIPOS_JSON:
        atuais = equipados_da_pessoa(pessoa)
        if valor:
            atuais[tipo] = valor
        else:
            atuais.pop(tipo, None)
        guardar_equipados(pessoa, atuais)


def badges_do_conjunto(posses):
    """Insígnias que uma pessoa mostra, na ordem do catálogo."""
    return [d['valor'] for d in CATALOGO.values() if d['tipo'] == 'badge' and d['id'] in posses]


def catalogo_para_json(posses):
    """Os itens exclusivos que a pessoa possui, com tudo que o inventário precisa."""
    return [{k: d[k] for k in ('id', 'tipo', 'valor', 'nome', 'desc', 'tema', 'raridade')}
            for d in CATALOGO.values() if d['id'] in posses]
