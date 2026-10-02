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

from .models import db, Channel, Server, MissaoProgresso, Person, br_now, server_members, channel_members


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
def eh_membro(usuario, server_id):
    """True se a pessoa é membro do servidor (uma consulta leve, sem carregar a lista de membros)."""
    return db.session.query(server_members.c.person_id).filter(
        server_members.c.server_id == server_id,
        server_members.c.person_id == usuario.id).first() is not None


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
    # Consultas pequenas e diretas (EXISTS) em vez de carregar a lista inteira de membros:
    # em servidor grande, `usuario in servidor.members` baixava todo mundo a cada mensagem.
    if not com_retry(lambda: eh_membro(usuario, canal.server_id)):
        return False

    if canal.is_private:
        servidor = com_retry(lambda: Server.query.get(canal.server_id))
        if servidor is None:
            return False
        if servidor.owner_id == usuario.id:
            return True
        return com_retry(lambda: db.session.query(channel_members.c.person_id).filter(
            channel_members.c.channel_id == canal.id,
            channel_members.c.person_id == usuario.id).first() is not None)

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


def missoes_do_usuario(usuario, linhas=None):
    """`linhas` = (diárias, semanais) já carregadas - evita reler o banco logo depois de registrar_eventos."""
    diarias, semanais = linhas if linhas else (_linhas_do_periodo(usuario, 'diaria'), _linhas_do_periodo(usuario, 'semanal'))
    return {
        'diarias': [_missao_para_json(l) for l in diarias],
        'semanais': [_missao_para_json(l) for l in semanais],
        'reseta_diarias': _segundos_ate_reset('diaria'),
        'reseta_semanais': _segundos_ate_reset('semanal'),
    }


def registrar_eventos(usuario, eventos, xp_extra=0, motivo=None):
    """Conta `eventos` ({'mensagem': 1, ...}) nas missões ativas da pessoa.

    Missão que completa paga o XP na hora. `xp_extra` é XP avulso (ex.: o do
    tempo ativo) somado na MESMA transação. Devolve None se nada mudou, ou
    {'missoes': payload, 'concluidas': [...], 'estado': estado_xp_ou_None}.
    """
    diarias = _linhas_do_periodo(usuario, 'diaria')
    semanais = _linhas_do_periodo(usuario, 'semanal')
    linhas = [l for l in (diarias + semanais)
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
        'missoes': missoes_do_usuario(usuario, (diarias, semanais)),
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
# Faixas animadas do perfil (guardadas em banner_color como 'anim:<id>'; vazio = arco-íris padrão)
FAIXAS_ANIMADAS = ('aurora', 'oceano', 'fogo', 'sakura', 'neon', 'galaxia', 'ouro', 'menta', 'cereja', 'gelo')

_RE_TEMA_COR = re.compile(r'^(grad:#[0-9a-fA-F]{6},#[0-9a-fA-F]{6}|solid:#[0-9a-fA-F]{6})$')
_RE_GIPHY = re.compile(r'^https://media\d*\.giphy\.com/')
_RE_USERNAME = re.compile(r'^[a-z0-9_.]{3,20}$')


def url_de_imagem_ok(url):
    """Só caminho do próprio site, Cloudinary ou Giphy (mesma regra dos anexos).
    Qualquer outro host seria um pixel de rastreio no navegador de todo mundo."""
    url = (url or '').strip()
    return bool(url) and len(url) <= 255 and (
        url.startswith('/') or url.startswith('https://res.cloudinary.com/') or bool(_RE_GIPHY.match(url)))


_RE_AJUSTE = re.compile(r'^-?\d{1,2}(\.\d{1,3})?,-?\d{1,2}(\.\d{1,3})?,\d{1,2}(\.\d{1,3})?,[01],[01]$')


def ajuste_de_imagem_valido(valor):
    """Enquadramento de GIF: 'x,y,zoom,espelhoH,espelhoV' (frações, ex.: '-0.2,-0.1,1.5,0,0').
    Vai parar num style="" no cliente de todo mundo, então só aceita esse formato."""
    valor = (valor or '').strip()
    return valor if valor and _RE_AJUSTE.match(valor) else None


def tema_perfil_valido(valor):
    """'' (sem tema), cor sólida, gradiente ou 'img:<url permitida>[|ajuste]'."""
    if not valor:
        return True
    if valor.startswith('img:'):
        url, _, ajuste = valor[4:].partition('|')
        if ajuste and not ajuste_de_imagem_valido(ajuste):
            return False
        return len(valor) <= 300 and url_de_imagem_ok(url)
    return bool(_RE_TEMA_COR.match(valor))


# ==========================================
# MAPA: raio de privacidade
# ------------------------------------------------------------
# Notas e servidores só aparecem (e só chegam ao navegador) dentro de um raio
# ao redor de quem está olhando. Servidores têm alcance maior que notas.
# O cliente recebe estes valores junto com os dados, então muda aqui e vale lá.
# ==========================================
RAIO_NOTAS_M = 2000
RAIO_SERVIDORES_M = 15000
MAX_NOTAS_ATIVAS_POR_PESSOA = 20
DENUNCIAS_PARA_OCULTAR = 3
MOTIVOS_DENUNCIA = ('+18', 'assedio', 'spam', 'ilegal', 'outro')


def distancia_m(lat1, lng1, lat2, lng2):
    """Distância em metros entre dois pontos (haversine)."""
    from math import radians, sin, cos, asin, sqrt
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lng2 - lng1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371000 * asin(sqrt(a))


def coordenada_valida(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def username_valido(nome):
    return bool(_RE_USERNAME.match(nome or '')) and '..' not in nome


def _slug(texto):
    ascii_ = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '.', ascii_.lower()).strip('.')


def gerar_username(nome, email=None):
    """'Aquele Sales' -> 'aquele.sales' (com sufixo numérico se já existir)."""
    base = _slug(nome) or _slug((email or '').split('@')[0]) or 'usuario'
    base = base[:16]          # sobra espaço pro sufixo numérico dentro do limite de 20
    if len(base) < 3:
        base = (base + '.usuario')[:16]
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


def dados_do_mapa_perto(lat, lng, amigos_ids=None):
    """Notas e servidores plantados dentro do raio de quem está olhando.

    Só o que está perto sai do servidor (privacidade); o resto nem chega ao
    navegador. Itens expirados ou escondidos por denúncia ficam de fora.
    Nota de AMIGO aparece no alcance grande (o mesmo dos servidores): senão duas pessoas a 5 km uma da outra
    nunca viam as notas uma da outra, mesmo sendo amigas.
    """
    from math import cos, radians
    from sqlalchemy import or_, and_
    from sqlalchemy.orm import joinedload
    from .models import GeoNote, MapServer

    agora = br_now()

    def caixa(r):
        dlat = r / 111000.0
        dlng = r / (111000.0 * max(0.2, cos(radians(lat))))
        return lat - dlat, lat + dlat, lng - dlng, lng + dlng

    amigos_ids = list(amigos_ids or [])
    a, b, c, d = caixa(RAIO_NOTAS_M)
    A, B, C, D = caixa(RAIO_SERVIDORES_M)
    perto = and_(GeoNote.lat.between(a, b), GeoNote.lng.between(c, d))
    if amigos_ids:
        perto = or_(perto, and_(GeoNote.author_id.in_(amigos_ids), GeoNote.lat.between(A, B), GeoNote.lng.between(C, D)))
    # Nota ANTIGA sem prazo (criada antes de a duração passar a valer) só vale por 24h desde que
    # nasceu - senão ficava eterna no mapa.
    notas_db = GeoNote.query.filter(
        perto,
        or_(GeoNote.expires_at > agora,
            and_(GeoNote.expires_at == None, GeoNote.timestamp > agora - timedelta(hours=24))),   # noqa: E711
        or_(GeoNote.oculta == None, GeoNote.oculta == False),            # noqa: E711,E712
    ).options(joinedload(GeoNote.author)).all()
    notas = [nota_para_json(n, agora) for n in notas_db
             if distancia_m(lat, lng, n.lat, n.lng) <= (RAIO_SERVIDORES_M if n.author_id in amigos_ids else RAIO_NOTAS_M)]

    a, b, c, d = caixa(RAIO_SERVIDORES_M)
    servers_db = MapServer.query.filter(
        MapServer.lat.between(a, b), MapServer.lng.between(c, d),
        or_(MapServer.expires_at == None, MapServer.expires_at > agora),  # noqa: E711
        or_(MapServer.oculta == None, MapServer.oculta == False),         # noqa: E711,E712
    ).options(joinedload(MapServer.server), joinedload(MapServer.owner)).all()
    servers = [servidor_mapa_para_json(s) for s in servers_db
               if distancia_m(lat, lng, s.lat, s.lng) <= RAIO_SERVIDORES_M]

    return {'notas': notas, 'servers': servers,
            'raio_notas_m': RAIO_NOTAS_M, 'raio_servidores_m': RAIO_SERVIDORES_M}


def nota_para_json(n, agora=None):
    agora = agora or br_now()
    restante = None
    if n.expires_at:
        restante = max(0, int((n.expires_at - agora).total_seconds()))
    elif n.timestamp:       # nota antiga sem prazo: 24h a partir de quando nasceu
        restante = max(0, int((n.timestamp + timedelta(hours=24) - agora).total_seconds()))
    # autor_id/owner_id vão junto porque o frontend decidia quem é dono
    # comparando o NOME - dois usuários com o mesmo nome do Google viam
    # os botões de editar/apagar um do outro.
    return {
        'id': n.id, 'lat': n.lat, 'lng': n.lng, 'texto': n.text,
        'autor': n.author.name if n.author else '???', 'autor_id': n.author_id,
        'cor': n.color, 'icone': n.icone, 'restante_s': restante
    }


def servidor_mapa_para_json(s):
    # Nome e ícone vêm do Servidor ligado, não da cópia feita na hora de plantar:
    # senão renomear o servidor não mudava nada no mapa.
    srv = s.server
    return {
        'id': s.id, 'lat': s.lat, 'lng': s.lng,
        'name': srv.name if srv else s.name,
        'icon_url': srv.icon_url if srv else None,
        'banner_color': srv.banner_color if srv else None,
        'description': srv.description if srv else None,
        'owner': s.owner.name if s.owner else '???', 'owner_id': s.owner_id,
        'vagas': s.max_tickets if s.max_tickets else 'ilimitado',
        'online': len(srv.members) if srv else 1,
        'server_id': s.server_id
    }


# ==========================================
# GIF/animação: recorte no servidor (mantém a animação)
# ------------------------------------------------------------
# O <canvas> do navegador só captura UM quadro, então recortar GIF lá mata a animação. Aqui cada
# quadro é espelhado/ampliado/recortado com o Pillow e o resultado sai como WebP animado (bem
# menor que GIF). Mesma conta do editor de foto parada: cobre a área ("cover"), com zoom e
# deslocamento em frações da área (ox/oy), pra que "o que eu vejo é o que sai".
# ==========================================
FORMATOS_ANIMADOS = {
    'circulo': (256, 256), 'quadrado': (256, 256),
    'faixa': (816, 260),      # mesma proporção da faixa do cartão (340x108)
    'painel': (480, 608),     # fundo do cartão (300x380)
}
MAX_QUADROS_ANIMACAO = 90


def recortar_animacao(dados, formato, escala=1.0, ox=0.0, oy=0.0, espelho_h=False, espelho_v=False):
    """Recorta/ajusta uma animação (GIF, WebP animado...) e devolve os bytes de um WebP animado."""
    from io import BytesIO
    from PIL import Image, ImageOps, ImageSequence

    SW, SH = FORMATOS_ANIMADOS.get(formato, FORMATOS_ANIMADOS['quadrado'])
    escala = min(4.0, max(1.0, float(escala)))
    ox, oy = min(10.0, max(-10.0, float(ox))), min(10.0, max(-10.0, float(oy)))

    im = Image.open(BytesIO(dados))
    total = getattr(im, 'n_frames', 1)
    passo = max(1, -(-total // MAX_QUADROS_ANIMACAO))     # ceil: no máximo ~90 quadros

    quadros, duracoes, acumulado = [], [], 0
    for i, quadro in enumerate(ImageSequence.Iterator(im)):
        acumulado += int(quadro.info.get('duration') or 100)
        if i % passo:
            continue
        f = quadro.convert('RGBA')
        if espelho_h:
            f = ImageOps.mirror(f)
        if espelho_v:
            f = ImageOps.flip(f)
        bw, bh = f.size
        s = max(SW / bw, SH / bh) * escala
        f = f.resize((max(1, round(bw * s)), max(1, round(bh * s))), Image.LANCZOS)
        tela = Image.new('RGBA', (SW, SH), (0, 0, 0, 0))
        tela.paste(f, (round(ox * SW), round(oy * SH)))
        quadros.append(tela)
        duracoes.append(max(20, acumulado))
        acumulado = 0

    saida = BytesIO()
    if len(quadros) == 1:
        quadros[0].save(saida, format='WEBP', quality=88)
    else:
        quadros[0].save(saida, format='WEBP', save_all=True, append_images=quadros[1:],
                        duration=duracoes, loop=0, quality=78, method=3)
    return saida.getvalue()


# ------------------------------------------------------------
# Vídeo -> animação SEM ffmpeg: o navegador decodifica o vídeo (ele já sabe), tira ~12 quadros por
# segundo num canvas e manda os JPEGs; aqui o Pillow só monta o WebP animado. O resultado entra no
# mesmo editor de GIF (arrastar/zoom/espelhar) e no mesmo /api/gif/recortar.
# ------------------------------------------------------------
MAX_LADO_QUADRO_VIDEO = 800
MAX_FPS_VIDEO = 15


def animar_quadros(lista_bytes, fps):
    """Junta quadros JPEG (na ordem) num WebP animado e devolve os bytes."""
    from io import BytesIO
    from PIL import Image

    fps = min(MAX_FPS_VIDEO, max(1, int(fps)))
    quadros, tamanho = [], None
    for dados in lista_bytes[:MAX_QUADROS_ANIMACAO]:
        im = Image.open(BytesIO(dados)).convert('RGB')
        im.thumbnail((MAX_LADO_QUADRO_VIDEO, MAX_LADO_QUADRO_VIDEO), Image.LANCZOS)
        if tamanho is None:
            tamanho = im.size
        elif im.size != tamanho:
            im = im.resize(tamanho, Image.LANCZOS)
        quadros.append(im)
    if len(quadros) < 2:
        raise ValueError('quadros insuficientes')

    saida = BytesIO()
    quadros[0].save(saida, format='WEBP', save_all=True, append_images=quadros[1:],
                    duration=round(1000 / fps), loop=0, quality=75, method=3)
    return saida.getvalue()
