"""Helpers compartilhados entre auth/routes.py, events.py e main/routes.py.

Antes cada um desses arquivos tinha a sua própria cópia de `com_retry()` -
mesma ideia, tempos de espera diferentes. Agora é só uma.
"""
import random
import re
import secrets
import unicodedata
import string
import time
from datetime import timedelta

from sqlalchemy.exc import OperationalError

from .models import db, Channel, Server, MissaoProgresso, Person, br_now


def com_retry(fn, tentativas=4, espera=1.0):
    """Roda fn() e tenta de novo se o Neon (banco serverless) estiver
    'acordando' de um cold start de verdade (compute desligado por
    inatividade) - o pool de conexões (app/config.py, pool_pre_ping +
    pool_recycle) já lida com conexão parada/velha sozinho, mas não existe
    pool que acelere o Neon ligando o compute do zero, então isso ainda pode
    acontecer em qualquer query, não só no login.

    A espera cresce a cada tentativa (1s, 2s, 3s...) porque o cold start do
    Neon às vezes passa de 3 segundos.
    """
    for tentativa in range(tentativas):
        try:
            return fn()
        except OperationalError:
            db.session.rollback()
            if tentativa == tentativas - 1:
                raise
            time.sleep(espera * (tentativa + 1))


def comitar_com_retry(preparar):
    """Igual ao com_retry, mas para escritas: `preparar` monta as alterações
    E comita, tudo dentro da função.

    Cuidado: não dá pra fazer `com_retry(db.session.commit)` direto - se o
    commit falha, o rollback do retry descarta as alterações e a tentativa
    seguinte comita uma sessão vazia. Por isso `preparar` precisa refazer as
    alterações a cada tentativa.
    """
    def executar():
        resultado = preparar()
        db.session.commit()
        return resultado

    return com_retry(executar)


# ==========================================
# PERMISSÕES
# ==========================================
def pode_ver_canal(usuario, canal):
    """True se o usuário pode ler/escrever neste canal.

    Canal com server_id nulo é um canal global antigo (legado, sem UI) e fica
    liberado pra qualquer logado. Canal de Servidor exige ser membro dele.

    Canal PRIVADO exige, além disso, estar na lista `allowed_members` - ou ser
    o dono do servidor, que sempre entra. Antes o `is_private` só escondia o
    canal na tela, e quem chutasse o id entrava do mesmo jeito.
    """
    if usuario is None or canal is None:
        return False
    if canal.server_id is None:
        return True

    # O com_retry() de cima (no Channel.query.get de canal_permitido) não
    # "esquenta" esta query aqui - cada uma pode pegar um cold start
    # diferente. Sem com_retry também, um cold start do Neon bem no meio de
    # pode_ver_canal
    # estourava OperationalError sem retry nenhum, e como quem chama esta
    # função (entrar_call, listar_participantes_call...) não tinha
    # try/except, o handler inteiro morria em silêncio - por isso às vezes
    # alguém "sumia" da call ou a prévia de quem já está nela não aparecia.
    servidor = com_retry(lambda: Server.query.get(canal.server_id))
    if servidor is None:
        return False
    if usuario not in servidor.members:
        return False

    if canal.is_private:
        if servidor.owner_id == usuario.id:
            return True
        return usuario in canal.allowed_members

    return True


def canal_permitido(usuario, canal_id):
    """Busca o canal e devolve ele só se o usuário puder acessar, senão None."""
    if usuario is None:
        return None
    try:
        canal = com_retry(lambda: Channel.query.get(int(canal_id)))
    except (TypeError, ValueError):
        return None
    return canal if pode_ver_canal(usuario, canal) else None


def pode_gerenciar_servidor(usuario, servidor):
    """Quem pode mexer nas configurações do servidor, canais, convites e eventos.

    Hoje é só o dono. Quando existir um sistema de cargos por servidor, é aqui
    que a checagem de permissão entra - todos os handlers já passam por esta
    função, então não vai ser preciso caçar cada um.
    """
    if usuario is None or servidor is None:
        return False
    return servidor.owner_id == usuario.id


def servidor_gerenciavel(usuario, server_id):
    """Busca o servidor e devolve ele só se o usuário puder administrá-lo."""
    if usuario is None:
        return None
    try:
        servidor = com_retry(lambda: Server.query.get(int(server_id)))
    except (TypeError, ValueError):
        return None
    return servidor if pode_gerenciar_servidor(usuario, servidor) else None


def gerar_codigo_convite(tamanho=8):
    """Código curto e único para o link/QR de convite.

    `secrets` e não `random`: o código é o que dá acesso ao servidor, então
    precisa ser imprevisível.
    """
    from .models import Invite
    alfabeto = string.ascii_lowercase + string.digits
    for _ in range(12):
        codigo = ''.join(secrets.choice(alfabeto) for _ in range(tamanho))
        if not Invite.query.filter_by(code=codigo).first():
            return codigo
    # Praticamente impossível chegar aqui, mas melhor que devolver um repetido.
    raise RuntimeError("Não foi possível gerar um código de convite único")


# ==========================================
# BATTLE PASS: nível/XP pessoal + missões
# ==========================================
# 100 níveis. Subir do nível N pro N+1 custa XP_BASE + XP_CRESCIMENTO*(N-1):
#   1->2 = 100 XP, 50->51 = 10.096 XP, 99->100 = 20.092 XP
# e chegar ao nível 100 soma 999.504 XP (~1 milhão). Quem começa sobe rápido
# (dá vontade de continuar) e o topo é coisa de meses. `Person.xp` guarda o
# TOTAL, então mexer na curva não precisa de migração, só muda o nível calculado.
XP_BASE = 100
XP_CRESCIMENTO = 204
NIVEL_MAXIMO = 100
COINS_POR_NIVEL = 50         # Dracmas pagas ao subir de nível.
GANHO_XP_INTERVALO_SEGUNDOS = 30   # Sem isso, mandar mensagem vazia em loop
                                    # virava fábrica de XP infinita.
XP_POR_MENSAGEM = 10
XP_BONUS_DIARIO = 50         # Pago uma vez por dia, ao abrir o app.
XP_BONUS_SEQUENCIA = 10      # Extra por dia seguido (até SEQUENCIA_MAXIMA dias).
SEQUENCIA_MAXIMA = 7
# Tempo ativo no app (mexendo de verdade - o cliente só manda o batimento se
# houve mouse/teclado no último minuto, com a aba visível). O servidor ainda
# limita por minuto e por dia, então um cliente adulterado não vira fábrica de XP.
XP_POR_MINUTO_ATIVO = 3
MINUTOS_ATIVOS_MAX_POR_DIA = 60      # = no máximo 180 XP/dia só por ficar
BATIMENTO_MIN_SEGUNDOS = 50

# Título que a pessoa ostenta a partir de cada nível (o maior já alcançado vale).
TITULOS_POR_NIVEL = [
    (1, 'Novato'), (5, 'Explorador'), (10, 'Desbravador'), (15, 'Veterano'),
    (20, 'Lenda Local'), (30, 'Mestre do Radar'), (40, 'Elite'),
    (50, 'Imortal'), (60, 'Semideus'), (75, 'Titã'), (90, 'Olimpiano'),
    (100, 'Panteão'),
]


def xp_do_nivel(nivel):
    """XP total necessário pra ALCANÇAR `nivel` (nível 1 = 0 XP)."""
    n = max(nivel, 1) - 1
    return XP_BASE * n + XP_CRESCIMENTO * n * (n - 1) // 2


def nivel_da_pessoa(xp):
    xp = xp or 0
    nivel = 1
    while nivel < NIVEL_MAXIMO and xp >= xp_do_nivel(nivel + 1):
        nivel += 1
    return nivel


def progresso_de_nivel(xp):
    """(xp dentro do nível atual, xp necessário pro próximo) - pra desenhar a barrinha."""
    xp = xp or 0
    nivel = nivel_da_pessoa(xp)
    if nivel >= NIVEL_MAXIMO:
        return 1, 1
    return xp - xp_do_nivel(nivel), xp_do_nivel(nivel + 1) - xp_do_nivel(nivel)


def titulo_do_nivel(nivel):
    titulo = TITULOS_POR_NIVEL[0][1]
    for minimo, nome in TITULOS_POR_NIVEL:
        if nivel >= minimo:
            titulo = nome
    return titulo


def recompensa_do_nivel(nivel):
    """O que ganha ao ALCANÇAR `nivel`. Marcos de 5/10 níveis pagam mais."""
    coins = COINS_POR_NIVEL
    if nivel % 10 == 0:
        coins = 300
    elif nivel % 5 == 0:
        coins = 150
    novo_titulo = next((nome for minimo, nome in TITULOS_POR_NIVEL if minimo == nivel and nivel > 1), None)
    return {'nivel': nivel, 'coins': coins, 'titulo': novo_titulo}


def _estado_xp(usuario, nivel_antes, ganho_xp=0, motivo=None, bonus_diario=False):
    nivel = nivel_da_pessoa(usuario.xp)
    xp_atual, xp_por_nivel = progresso_de_nivel(usuario.xp)
    return {
        'xp': usuario.xp or 0,
        'nivel': nivel,
        'xp_atual_nivel': xp_atual,
        'xp_por_nivel': xp_por_nivel,
        'titulo': titulo_do_nivel(nivel),
        'subiu_nivel': nivel > nivel_antes,
        'recompensas': [recompensa_do_nivel(n) for n in range(nivel_antes + 1, nivel + 1)],
        # A trilha inteira (100 marcos) - é pouca coisa e o cliente rola até o atual.
        'marcos': [recompensa_do_nivel(n) for n in range(1, NIVEL_MAXIMO + 1)],
        'coins': usuario.bazinga_coins,
        'ganho_xp': ganho_xp,
        'motivo': motivo,
        'bonus_diario': bonus_diario,
        'streak': usuario.streak_dias or 0,
        'nivel_maximo': nivel >= NIVEL_MAXIMO,
    }


def estado_battlepass(usuario):
    """Foto atual do Battle Pass, sem ganhar nada (usada ao conectar)."""
    return _estado_xp(usuario, nivel_da_pessoa(usuario.xp))


def _somar_xp(usuario, quantidade, nivel_antes):
    """Soma XP e paga as moedas dos níveis cruzados. Chamar DENTRO do preparar()
    de um comitar_com_retry (precisa refazer a soma a cada tentativa)."""
    usuario.xp = (usuario.xp or 0) + quantidade
    for n in range(nivel_antes + 1, nivel_da_pessoa(usuario.xp) + 1):
        usuario.bazinga_coins = (usuario.bazinga_coins or 0) + recompensa_do_nivel(n)['coins']


def conceder_xp_por_mensagem(usuario):
    """Dá XP por mandar mensagem, com cooldown pra não virar spam de XP.

    Devolve None se não ganhou XP agora (cooldown), ou um dict com o
    estado completo (pra montar o toast/evento de subiu de nível) se ganhou.
    Quem chama decide o que fazer com `subiu_nivel` (emitir evento, etc);
    esta função só mexe no usuário e comita.
    """
    agora = br_now()
    if usuario.xp_ganho_em and (agora - usuario.xp_ganho_em).total_seconds() < GANHO_XP_INTERVALO_SEGUNDOS:
        return None

    nivel_antes = nivel_da_pessoa(usuario.xp)

    def preparar():
        _somar_xp(usuario, XP_POR_MENSAGEM, nivel_antes)
        usuario.xp_ganho_em = agora

    comitar_com_retry(preparar)
    return _estado_xp(usuario, nivel_antes, XP_POR_MENSAGEM, 'mensagem')


def conceder_bonus_diario(usuario):
    """Bônus de quem abre o app no dia: XP + sequência de dias seguidos.

    Devolve None se hoje já foi pago. Falha em dia pulado volta a sequência
    pra 1 (só o dia de ontem mantém a corrente).
    """
    hoje = br_now().date()
    if usuario.streak_em == hoje:
        return None

    nivel_antes = nivel_da_pessoa(usuario.xp)
    seguiu = usuario.streak_em is not None and (hoje - usuario.streak_em).days == 1
    nova_sequencia = (usuario.streak_dias or 0) + 1 if seguiu else 1
    ganho = XP_BONUS_DIARIO + XP_BONUS_SEQUENCIA * (min(nova_sequencia, SEQUENCIA_MAXIMA) - 1)

    def preparar():
        _somar_xp(usuario, ganho, nivel_antes)
        usuario.streak_dias = nova_sequencia
        usuario.streak_em = hoje

    comitar_com_retry(preparar)
    return _estado_xp(usuario, nivel_antes, ganho, 'diario', bonus_diario=True)


# ==========================================
# MISSÕES (diárias e semanais)
# ------------------------------------------------------------
# Cada pessoa recebe 3 diárias e 3 semanais sorteadas de um pool. O sorteio é
# DETERMINÍSTICO (semente = pessoa + período), então a escolha não precisa ser
# guardada: só o progresso vai pro banco (MissaoProgresso).
# `evento` liga a missão a algo que o app já faz de verdade:
#   mensagem (canal), dm, reacao, nota (nota no mapa), plantar (servidor no
#   mapa), minutos (ativo no app), call_minutos (em call de voz), login
#   (abrir o app em dias diferentes).
# Concluiu = o XP cai na hora (sem botão de "resgatar").
# ==========================================
MISSOES = {
    # --- diárias ---
    'd_msg10':    {'periodo': 'diaria',  'evento': 'mensagem',     'meta': 10,  'xp': 150,  'icone': 'comment-dots', 'titulo': 'Bate-papo',          'desc': 'Envie 10 mensagens em canais'},
    'd_msg30':    {'periodo': 'diaria',  'evento': 'mensagem',     'meta': 30,  'xp': 350,  'icone': 'comments',     'titulo': 'Língua solta',       'desc': 'Envie 30 mensagens em canais'},
    'd_ativo15':  {'periodo': 'diaria',  'evento': 'minutos',      'meta': 15,  'xp': 150,  'icone': 'hourglass-half', 'titulo': 'De olho no Panteão', 'desc': 'Fique 15 minutos ativo no app'},
    'd_ativo45':  {'periodo': 'diaria',  'evento': 'minutos',      'meta': 45,  'xp': 350,  'icone': 'clock',        'titulo': 'Morador',            'desc': 'Fique 45 minutos ativo no app'},
    'd_reacao5':  {'periodo': 'diaria',  'evento': 'reacao',       'meta': 5,   'xp': 120,  'icone': 'face-smile',   'titulo': 'Reator',             'desc': 'Reaja a 5 mensagens'},
    'd_dm5':      {'periodo': 'diaria',  'evento': 'dm',           'meta': 5,   'xp': 150,  'icone': 'paper-plane',  'titulo': 'Papo reservado',     'desc': 'Envie 5 mensagens diretas'},
    'd_call10':   {'periodo': 'diaria',  'evento': 'call_minutos', 'meta': 10,  'xp': 300,  'icone': 'headset',      'titulo': 'Na voz',             'desc': 'Passe 10 minutos numa call de voz'},
    # --- semanais ---
    's_msg150':   {'periodo': 'semanal', 'evento': 'mensagem',     'meta': 150, 'xp': 1200, 'icone': 'comments',     'titulo': 'Voz da comunidade',  'desc': 'Envie 150 mensagens em canais'},
    's_ativo240': {'periodo': 'semanal', 'evento': 'minutos',      'meta': 240, 'xp': 1500, 'icone': 'clock',        'titulo': 'Cidadão fiel',       'desc': 'Some 4 horas ativo no app'},
    's_call90':   {'periodo': 'semanal', 'evento': 'call_minutos', 'meta': 90,  'xp': 1800, 'icone': 'headset',      'titulo': 'Rei da call',        'desc': 'Some 90 minutos em calls de voz'},
    's_nota3':    {'periodo': 'semanal', 'evento': 'nota',         'meta': 3,   'xp': 900,  'icone': 'map-pin',      'titulo': 'Cronista do mapa',   'desc': 'Deixe 3 notas no mapa'},
    's_plantar1': {'periodo': 'semanal', 'evento': 'plantar',      'meta': 1,   'xp': 1500, 'icone': 'location-dot', 'titulo': 'Fundador',           'desc': 'Plante um servidor no mapa'},
    's_reacao30': {'periodo': 'semanal', 'evento': 'reacao',       'meta': 30,  'xp': 800,  'icone': 'face-smile',   'titulo': 'Torcida organizada', 'desc': 'Reaja a 30 mensagens'},
    's_dm30':     {'periodo': 'semanal', 'evento': 'dm',           'meta': 30,  'xp': 900,  'icone': 'paper-plane',  'titulo': 'Rede de contatos',   'desc': 'Envie 30 mensagens diretas'},
    's_login5':   {'periodo': 'semanal', 'evento': 'login',        'meta': 5,   'xp': 1000, 'icone': 'calendar-check', 'titulo': 'Presença VIP',     'desc': 'Abra o app em 5 dias diferentes'},
}
POOL_DIARIAS = [c for c, m in MISSOES.items() if m['periodo'] == 'diaria']
POOL_SEMANAIS = [c for c, m in MISSOES.items() if m['periodo'] == 'semanal']
QTD_POR_PERIODO = 3
TEMPO_ATIVO_CODIGO = '_tempo_ativo'   # contador interno (não é missão)


def _chave_do_periodo(periodo, hoje=None):
    hoje = hoje or br_now().date()
    if periodo == 'diaria':
        return hoje.isoformat()
    return (hoje - timedelta(days=hoje.weekday())).isoformat()   # segunda-feira


def _segundos_ate_reset(periodo):
    agora = br_now()
    hoje = agora.date()
    alvo = hoje + timedelta(days=1) if periodo == 'diaria' else hoje + timedelta(days=7 - hoje.weekday())
    meia_noite = agora.replace(year=alvo.year, month=alvo.month, day=alvo.day, hour=0, minute=0, second=0, microsecond=0)
    return max(int((meia_noite - agora).total_seconds()), 0)


def _sortear_codigos(usuario_id, periodo, chave):
    pool = POOL_DIARIAS if periodo == 'diaria' else POOL_SEMANAIS
    return random.Random(f"{usuario_id}|{periodo}|{chave}").sample(pool, QTD_POR_PERIODO)


def _linhas_do_periodo(usuario, periodo, criar=True):
    """Linhas de progresso do período atual (cria as que faltam)."""
    chave = _chave_do_periodo(periodo)
    codigos = _sortear_codigos(usuario.id, periodo, chave)

    def existentes():
        return {r.codigo: r for r in MissaoProgresso.query.filter_by(
            person_id=usuario.id, periodo=periodo, chave=chave).all()}

    linhas = com_retry(existentes)
    if criar and any(c not in linhas for c in codigos):
        def preparar():
            ja = {r.codigo for r in MissaoProgresso.query.filter_by(
                person_id=usuario.id, periodo=periodo, chave=chave).all()}
            for c in codigos:
                if c not in ja:
                    db.session.add(MissaoProgresso(person_id=usuario.id, codigo=c, periodo=periodo, chave=chave))
        comitar_com_retry(preparar)
        linhas = com_retry(existentes)
    return [linhas[c] for c in codigos if c in linhas]


def _missao_para_json(linha):
    m = MISSOES[linha.codigo]
    return {
        'codigo': linha.codigo, 'titulo': m['titulo'], 'descricao': m['desc'], 'icone': m['icone'],
        'meta': m['meta'], 'progresso': min(linha.progresso, m['meta']), 'xp': m['xp'],
        'concluida': bool(linha.concluida),
    }


def missoes_do_usuario(usuario):
    return {
        'diarias': [_missao_para_json(l) for l in _linhas_do_periodo(usuario, 'diaria')],
        'semanais': [_missao_para_json(l) for l in _linhas_do_periodo(usuario, 'semanal')],
        'reseta_diarias': _segundos_ate_reset('diaria'),
        'reseta_semanais': _segundos_ate_reset('semanal'),
    }


def registrar_eventos(usuario, eventos, xp_extra=0, motivo=None):
    """Conta `eventos` ({'mensagem': 1, ...}) nas missões ativas da pessoa.

    Missão que completa paga o XP na hora. `xp_extra` é XP avulso (ex.: o do
    tempo ativo) somado na MESMA transação. Devolve None se nada mudou, ou
    {'missoes': payload, 'concluidas': [...], 'estado': estado_xp_ou_None}.
    """
    linhas = [l for l in (_linhas_do_periodo(usuario, 'diaria') + _linhas_do_periodo(usuario, 'semanal'))
              if not l.concluida and MISSOES[l.codigo]['evento'] in eventos]
    if not linhas and not xp_extra:
        return None

    nivel_antes = nivel_da_pessoa(usuario.xp)
    concluidas = []

    def preparar():
        concluidas.clear()
        ganho = xp_extra
        for l in linhas:
            m = MISSOES[l.codigo]
            l.progresso = min((l.progresso or 0) + eventos[m['evento']], m['meta'])
            if l.progresso >= m['meta'] and not l.concluida:
                l.concluida = True
                ganho += m['xp']
                concluidas.append({'titulo': m['titulo'], 'xp': m['xp']})
        if ganho:
            _somar_xp(usuario, ganho, nivel_antes)

    comitar_com_retry(preparar)

    ganho_total = xp_extra + sum(c['xp'] for c in concluidas)
    return {
        'missoes': missoes_do_usuario(usuario),
        'concluidas': concluidas,
        'estado': _estado_xp(usuario, nivel_antes, ganho_total, motivo or ('missao' if concluidas else 'tempo')) if ganho_total else None,
    }


def registrar_tempo_ativo(usuario, em_call=False):
    """1 minuto de atividade real: XP passivo (com teto diário) + missões de tempo."""
    chave = _chave_do_periodo('diaria')

    def contador():
        return MissaoProgresso.query.filter_by(
            person_id=usuario.id, codigo=TEMPO_ATIVO_CODIGO, periodo='diaria', chave=chave).first()

    linha = com_retry(contador)
    if linha is None:
        def criar():
            db.session.add(MissaoProgresso(person_id=usuario.id, codigo=TEMPO_ATIVO_CODIGO, periodo='diaria', chave=chave))
        comitar_com_retry(criar)
        linha = com_retry(contador)

    xp_passivo = 0
    if (linha.progresso or 0) < MINUTOS_ATIVOS_MAX_POR_DIA:
        def somar_minuto():
            linha.progresso = (linha.progresso or 0) + 1
        comitar_com_retry(somar_minuto)
        xp_passivo = XP_POR_MINUTO_ATIVO

    eventos = {'minutos': 1}
    if em_call:
        eventos['call_minutos'] = 1
    return registrar_eventos(usuario, eventos, xp_extra=xp_passivo, motivo='tempo')


# ==========================================
# Texto "Set. 2026" do "Membro desde" (cartão de perfil)
# ==========================================
MESES_ABREVIADOS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                    'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def membro_desde_texto(criado_em):
    """'Set. 2026', ou None se a conta é antiga e não tem essa data guardada."""
    if not criado_em:
        return None
    return f"{MESES_ABREVIADOS[criado_em.month - 1]}. {criado_em.year}"


# ==========================================
# PERFIL: catálogos validados no servidor + nome da conta (@)
# ------------------------------------------------------------
# Os ids abaixo precisam bater com o catálogo do chat.html (CSS .ne-*, .placa-*,
# .moldura-*). O servidor só guarda id conhecido - nunca texto livre num class="".
# ==========================================
ESTILOS_NOME = ('padrao', 'neon', 'ouro', 'fogo', 'gelo', 'arco', 'sakura', 'glitch', 'retro')
PLACAS = ('nenhuma', 'aurora', 'ouro', 'neon', 'oceano', 'sakura', 'lava', 'galaxia')
MOLDURAS = ('nenhuma', 'aurora', 'neon', 'ouro', 'fogo', 'gelo', 'arco')
STATUS_VALIDOS = ('online', 'idle', 'dnd', 'invisible', 'custom')

_RE_TEMA_COR = re.compile(r'^(grad:#[0-9a-fA-F]{6},#[0-9a-fA-F]{6}|solid:#[0-9a-fA-F]{6})$')
_RE_GIPHY = re.compile(r'^https://media\d*\.giphy\.com/')
_RE_USERNAME = re.compile(r'^[a-z0-9_.]{3,32}$')


def url_de_imagem_ok(url):
    """Só caminho do próprio site, Cloudinary ou Giphy (mesma regra dos anexos).
    Qualquer outro host seria um pixel de rastreio no navegador de todo mundo."""
    url = (url or '').strip()
    return bool(url) and len(url) <= 255 and (
        url.startswith('/') or url.startswith('https://res.cloudinary.com/') or bool(_RE_GIPHY.match(url)))


def tema_perfil_valido(valor):
    """'' (sem tema), cor sólida, gradiente ou 'img:<url permitida>'."""
    if not valor:
        return True
    if valor.startswith('img:'):
        return url_de_imagem_ok(valor[4:])
    return bool(_RE_TEMA_COR.match(valor))


def username_valido(nome):
    return bool(_RE_USERNAME.match(nome or '')) and '..' not in nome


def _slug(texto):
    ascii_ = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '.', ascii_.lower()).strip('.')


def gerar_username(nome, email=None):
    """'Aquele Sales' -> 'aquele.sales' (com sufixo numérico se já existir)."""
    base = _slug(nome) or _slug((email or '').split('@')[0]) or 'usuario'
    base = base[:26]
    if len(base) < 3:
        base = (base + '.usuario')[:26]
    candidato, n = base, 1
    while Person.query.filter_by(username=candidato).first():
        n += 1
        candidato = f"{base}{n}"
    return candidato


def garantir_username(usuario):
    """Conta antiga (de antes do @ existir) ganha um nome de conta automático."""
    if usuario.username:
        return

    def preparar():
        if not usuario.username:
            usuario.username = gerar_username(usuario.name, usuario.email)

    comitar_com_retry(preparar)
