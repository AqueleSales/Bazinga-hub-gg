"""Menções especiais nas mensagens de canal (Rodada 39). Regra, sem socket; quem avisa de verdade é o events.py (`_notificar_mencoes`).

No texto guardado a menção é um token, nunca o nome (o nome muda e a mensagem continua certa):
    <@123>        uma pessoa                       (já existia)
    <@todos>      todo mundo que enxerga o canal   (@todos, @everyone, @all)          precisa de "Mencionar todos e cargos"
    <@aqui>       quem está online agora           (@aqui, @here, @online)             precisa de "Mencionar todos e cargos"
    <@&7>         quem tem o cargo 7               (@NomeDoCargo, com a cor do cargo)  precisa de "Mencionar todos e cargos"
    <@staff>      a moderação (dono + quem gerencia o servidor ou remove membros)      qualquer um, 1 vez a cada 2 min
    <@dono>       o dono do servidor                                                   qualquer um, 1 vez a cada 2 min
    <@amigos>     só os SEUS amigos que estão neste servidor                           qualquer um, 1 vez a cada 45 s
    <@alguem>     sorteia UMA pessoa online e vira <@id> na hora (a escolha é do servidor, ninguém "escolhe" quem)

Regras que valem sempre (regra 4: o cliente só sugere, o servidor decide):
  * Só chama quem é MEMBRO do servidor e enxerga o canal (menção não vaza canal privado nem "chama" gente de fora).
  * Sem a permissão (ou antes do intervalo), o token vira texto simples ("@todos") e a mensagem sai SEM chamar ninguém; a pessoa recebe o motivo.
  * No máximo 3 menções especiais por mensagem e MAX_DESTINOS pessoas chamadas por mensagem (o resto simplesmente não é avisado).
"""
import random
import re
import time

from sqlalchemy import or_

from . import cargos
from .models import db, ServerRole, MemberRole, Friendship

RE_TOKEN = re.compile(r'<@(todos|aqui|staff|dono|alguem|amigos|&(\d{1,10}))>')
ESPECIAIS = ('todos', 'aqui', 'staff', 'dono', 'alguem', 'amigos')
MAX_ESPECIAIS_POR_MENSAGEM = 3
MAX_DESTINOS = 80

# segundos entre duas menções do mesmo tipo da mesma pessoa no mesmo servidor
INTERVALO_S = {'todos': 60, 'aqui': 60, 'cargo': 30, 'staff': 120, 'dono': 120, 'amigos': 45, 'alguem': 15}
PRECISA_PERMISSAO = ('todos', 'aqui', 'cargo')
_ultimo = {}          # (pessoa, servidor, tipo) -> instante
_ROTULO = {'todos': 'todos', 'aqui': 'aqui', 'staff': 'staff', 'dono': 'dono', 'amigos': 'amigos', 'alguem': 'alguém'}

# frase do aviso na caixa de entrada: "<nome> {frase} em #canal"
FRASE = {'todos': 'chamou todo mundo', 'aqui': 'chamou quem está online', 'staff': 'chamou a moderação', 'dono': 'chamou o dono',
         'amigos': 'chamou os amigos', 'alguem': 'te sorteou', 'cargo': 'chamou o cargo', 'pessoa': 'te citou'}


class Resultado:
    __slots__ = ('texto', 'destinos', 'avisos')

    def __init__(self, texto):
        self.texto = texto
        self.destinos = {}      # pessoa_id -> tipo ('todos', 'aqui', 'cargo', ...)
        self.avisos = []        # frases pra quem escreveu (menção que não valeu)


def tem_especial(texto):
    return bool(texto) and bool(RE_TOKEN.search(texto))


def _freio(pessoa_id, srv_id, tipo, agora):
    chave = (pessoa_id, srv_id, tipo)
    falta = INTERVALO_S.get(tipo, 30) - (agora - _ultimo.get(chave, 0))
    if falta > 0:
        return int(falta) + 1
    return 0


def _marca(pessoa_id, srv_id, tipo, agora):
    _ultimo[(pessoa_id, srv_id, tipo)] = agora
    if len(_ultimo) > 5000:                       # limpeza barata: some o que já passou do maior intervalo
        corte = agora - max(INTERVALO_S.values()) - 1
        for k in [k for k, t in _ultimo.items() if t < corte]:
            _ultimo.pop(k, None)


def _ids_dos_cargos(srv, perm_ids):
    """Quem tem algum cargo com uma das permissões (por consulta no banco, nunca por cache)."""
    mascara = 0
    for p in perm_ids:
        mascara |= cargos.BIT[p]
    cargos_ok = [r.id for r in ServerRole.query.filter(ServerRole.server_id == srv.id).all() if (r.permissoes or 0) & mascara]
    if not cargos_ok:
        return set()
    return {m.person_id for m in MemberRole.query.filter(MemberRole.role_id.in_(cargos_ok)).all()}


def _amigos_de(pessoa_id):
    linhas = Friendship.query.filter(Friendship.status == 'accepted',
                                     or_(Friendship.requester_id == pessoa_id, Friendship.addressee_id == pessoa_id)).all()
    return {(l.addressee_id if l.requester_id == pessoa_id else l.requester_id) for l in linhas}


def preparar(usuario, srv, canal, texto, esta_online, pode_ver, agora=None):
    """Confere e resolve as menções especiais de `texto`. Devolve um `Resultado` com o texto FINAL (o que vai ser guardado) e quem chamar.
    `esta_online(pessoa)` e `pode_ver(pessoa, canal)` vêm do events.py (presença e permissão do canal). Texto sem token especial não custa nada."""
    r = Resultado(texto or '')
    if srv is None or not tem_especial(texto):
        return r
    agora = agora if agora is not None else time.monotonic()
    membros = list(srv.members)
    privado = bool(canal.is_private or canal.sobrescrita)
    candidatos = {m.id: m for m in membros if m.id != usuario.id and (not privado or pode_ver(m, canal))}
    contexto = cargos.contexto(usuario, srv)
    pode_mencionar = contexto.tem('mencionar_todos')
    cargos_do_servidor = {c.id: c for c in ServerRole.query.filter_by(server_id=srv.id).all()}
    vistos = 0

    def sub(m):
        nonlocal vistos
        token, rid = m.group(1), m.group(2)
        tipo = 'cargo' if rid else token
        rotulo = ('@' + cargos_do_servidor[int(rid)].nome) if rid and int(rid) in cargos_do_servidor else '@' + _ROTULO.get(token, 'cargo')
        vistos += 1
        if vistos > MAX_ESPECIAIS_POR_MENSAGEM:
            r.avisos.append(f'No máximo {MAX_ESPECIAIS_POR_MENSAGEM} menções especiais por mensagem: o resto virou texto.')
            return rotulo
        if tipo in PRECISA_PERMISSAO and not pode_mencionar:
            r.avisos.append(f'Você não tem a permissão "Mencionar todos e cargos" aqui: {rotulo} virou texto e ninguém foi chamado.')
            return rotulo
        if rid and int(rid) not in cargos_do_servidor:
            return rotulo                                    # cargo de outro servidor / apagado: só texto
        espera = _freio(usuario.id, srv.id, tipo, agora)
        if espera:
            r.avisos.append(f'Calma: {rotulo} só pode de novo daqui {espera} s. Ficou como texto.')
            return rotulo

        if tipo == 'todos':
            alvos = set(candidatos)
        elif tipo == 'aqui':
            alvos = {i for i, p in candidatos.items() if esta_online(p)}
        elif tipo == 'staff':
            alvos = ({srv.owner_id} | _ids_dos_cargos(srv, ('administrador', 'gerenciar_servidor', 'expulsar'))) & set(candidatos)
        elif tipo == 'dono':
            alvos = {srv.owner_id} & set(candidatos)
        elif tipo == 'amigos':
            alvos = _amigos_de(usuario.id) & set(candidatos)
        elif tipo == 'alguem':
            online = [i for i, p in candidatos.items() if esta_online(p)]
            pool = online or list(candidatos)
            if not pool:
                r.avisos.append('Não achei ninguém pra sortear agora.')
                return '@alguém'
            escolhido = random.choice(pool)
            _marca(usuario.id, srv.id, tipo, agora)
            r.destinos[escolhido] = 'alguem'
            return f'<@{escolhido}>'                         # vira uma menção comum a quem foi sorteado
        else:                                                # cargo
            dono_do_cargo = {x.person_id for x in MemberRole.query.filter_by(role_id=int(rid)).all()}
            alvos = dono_do_cargo & set(candidatos)

        _marca(usuario.id, srv.id, tipo, agora)
        for i in list(alvos)[:MAX_DESTINOS]:
            r.destinos.setdefault(i, tipo)
        if len(alvos) > MAX_DESTINOS:
            r.avisos.append(f'{rotulo}: só avisei as primeiras {MAX_DESTINOS} pessoas (o resto vê na conversa).')
        return m.group(0)

    r.texto = RE_TOKEN.sub(sub, r.texto)
    return r


def titulo_do_aviso(autor_nome, tipo, canal_nome):
    return f'{autor_nome} {FRASE.get(tipo, FRASE["pessoa"])} em #{canal_nome}'


def trecho_legivel(texto, nomes, servidor_cargos=None):
    """O texto da mensagem pro aviso: <@id> vira @nome, os especiais viram @palavra. Sem HTML (o cliente escapa)."""
    def sub(m):
        token, rid = m.group(1), m.group(2)
        if rid:
            c = (servidor_cargos or {}).get(int(rid))
            return '@' + (c.nome if c else 'cargo')
        return '@' + _ROTULO.get(token, token)
    t = RE_TOKEN.sub(sub, texto or '')
    return re.sub(r'<@(\d{1,10})>', lambda m: '@' + nomes.get(int(m.group(1)), 'alguém'), t)[:140]


def sem_especiais_novos(antigo, novo):
    """Edição: o token especial que JÁ estava na mensagem continua (não chama ninguém de novo); o que apareceu agora vira texto simples.
    Assim editar uma mensagem nunca vira um jeito de dar @todos sem permissão nem sem o intervalo."""
    if not novo or not RE_TOKEN.search(novo):
        return novo
    tinha = {m.group(0) for m in RE_TOKEN.finditer(antigo or '')}
    return RE_TOKEN.sub(lambda m: m.group(0) if m.group(0) in tinha else '@' + (_ROTULO.get(m.group(1), 'cargo')), novo)
