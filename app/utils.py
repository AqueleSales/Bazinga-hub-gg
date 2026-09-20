"""Helpers compartilhados entre auth/routes.py, events.py e main/routes.py.

Antes cada um desses arquivos tinha a sua própria cópia de `com_retry()` -
mesma ideia, tempos de espera diferentes. Agora é só uma.
"""
import secrets
import string
import time

from sqlalchemy.exc import OperationalError

from .models import db, Channel, Server


def com_retry(fn, tentativas=4, espera=1.0):
    """Roda fn() e tenta de novo se o Neon (banco serverless) estiver
    'acordando' de um cold start - com NullPool, toda operação abre uma
    conexão nova, então isso pode acontecer em qualquer query, não só no login.

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
    """
    if usuario is None or canal is None:
        return False
    if canal.server_id is None:
        return True
    servidor = Server.query.get(canal.server_id)
    if servidor is None:
        return False
    return usuario in servidor.members


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
