"""Helpers compartilhados entre auth/routes.py, events.py e main/routes.py.

Antes cada um desses arquivos tinha a sua própria cópia de `com_retry()` -
mesma ideia, tempos de espera diferentes. Agora é só uma.
"""
import secrets
import string
import time

from sqlalchemy.exc import OperationalError

from .models import db, Channel, Server, br_now


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
# BATTLE PASS: nível/XP pessoal
# ==========================================
# Curva progressiva: subir do nível N pro N+1 custa XP_BASE + XP_CRESCIMENTO*(N-1).
# Nível 1->2 = 100 XP, 2->3 = 130, 3->4 = 160... Quem começa sobe rápido (dá
# vontade de continuar) e o topo exige constância. O XP é guardado TOTAL em
# Person.xp - trocar a curva aqui não precisa de migração, só muda o nível
# calculado.
XP_BASE = 100
XP_CRESCIMENTO = 30
NIVEL_MAXIMO = 100
COINS_POR_NIVEL = 50         # Bazinga Coins pagos ao subir de nível.
GANHO_XP_INTERVALO_SEGUNDOS = 30   # Sem isso, mandar mensagem vazia em loop
                                    # virava fábrica de XP infinita.
XP_POR_MENSAGEM = 5
XP_BONUS_DIARIO = 25         # Pago uma vez por dia, ao abrir o app.
XP_BONUS_SEQUENCIA = 5       # Extra por dia seguido (até SEQUENCIA_MAXIMA dias).
SEQUENCIA_MAXIMA = 7

# Título que a pessoa ostenta a partir de cada nível (o maior já alcançado vale).
TITULOS_POR_NIVEL = [
    (1, 'Novato'), (5, 'Explorador'), (10, 'Desbravador'), (15, 'Veterano'),
    (20, 'Lenda Local'), (30, 'Mestre do Radar'), (40, 'Elite Bazinga'),
    (50, 'Imortal'),
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
    # Janela de marcos: o que acabou de passar + os próximos 8, pra trilha.
    primeiro = max(nivel - 1, 1)
    marcos = [recompensa_do_nivel(n) for n in range(primeiro, min(primeiro + 9, NIVEL_MAXIMO) + 1)]
    return {
        'xp': usuario.xp or 0,
        'nivel': nivel,
        'xp_atual_nivel': xp_atual,
        'xp_por_nivel': xp_por_nivel,
        'titulo': titulo_do_nivel(nivel),
        'subiu_nivel': nivel > nivel_antes,
        'recompensas': [recompensa_do_nivel(n) for n in range(nivel_antes + 1, nivel + 1)],
        'marcos': marcos,
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
