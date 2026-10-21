"""Cargos por servidor, categorias/separadores e tipos de canal (Rodada 29). Sem socket aqui: os handlers moram em cargos_events.py.

COMO AS PERMISSÕES FUNCIONAM
- `PERMISSOES` é a lista fechada (id, nome, descrição). Cada id é um bit; a ORDEM é o número do bit, então nunca reordene nem apague: só acrescente no fim.
- O dono do servidor pode tudo e está acima de todos os cargos. "Administrador" também pode tudo, menos o que é só do dono (apagar o servidor e passar a posse).
- Todo membro tem o cargo padrão "Membro" (`Server.perms_membro`, NULL = `PERMS_MEMBRO_PADRAO`, que repete o que qualquer membro já podia antes dos cargos).
  Os cargos de verdade (`ServerRole`) somam permissões em cima disso. `posicao` maior = cargo mais alto.
- HIERARQUIA: ninguém cria/edita/apaga/dá cargo igual ou acima do seu, nem concede permissão que não tem, nem remove/mexe em quem está no seu nível ou acima. O dono não é expulso.
- `Server.estrutura` (True quando existe algum cargo ou categoria) evita consultar essas tabelas em servidor que nunca as usou (o caso comum): o /chat e o connect
  não ganham query nenhuma. Nos que usam, a estrutura é carregada em 3 queries de uma vez e fica em memória (`_CACHE`, invalidada em TODA escrita daqui). O cache
  só alimenta o que é DESENHADO na tela; quem decide se uma ação vale (`contexto`) sempre lê o banco.
"""
import re
import time
import unicodedata

from sqlalchemy import func

from .models import db, Server, Channel, ServerRole, MemberRole, ChannelCategory, server_members, channel_members


class ErroCargo(Exception):
    """Regra de negócio recusada: a mensagem vai pro toast da pessoa."""


# ==========================================
# PERMISSÕES
# ==========================================
PERMISSOES = [
    ('administrador', 'Administrador', 'Pode tudo, menos apagar o servidor e passar a posse. Dê só a quem você confia como a você.'),
    ('gerenciar_servidor', 'Gerenciar o servidor', 'Mudar nome, ícone, descrição, banner, boas-vindas, Explorar e efeitos, e revogar convites.'),
    ('gerenciar_canais', 'Gerenciar canais', 'Criar, editar, apagar e organizar canais, categorias e separadores.'),
    ('gerenciar_cargos', 'Gerenciar cargos', 'Criar e editar cargos abaixo do seu e dá-los aos membros.'),
    ('expulsar', 'Remover membros', 'Tirar do servidor quem está abaixo do seu cargo.'),
    ('gerenciar_eventos', 'Gerenciar eventos', 'Criar, editar e apagar eventos do calendário.'),
    ('criar_convite', 'Criar convites', 'Gerar links de convite (sem Gerenciar o servidor, vale no máximo 7 dias e 25 usos).'),
    ('apagar_mensagens', 'Apagar mensagens dos outros', 'Apagar mensagem de qualquer pessoa nos canais que enxerga.'),
    ('fixar_mensagens', 'Fixar mensagens', 'Fixar e desafixar mensagens.'),
    ('ver_canais_privados', 'Ver canais privados', 'Enxergar todos os canais privados, mesmo sem ter sido convidado a eles.'),
    ('falar_voz', 'Falar nos canais de voz', 'Sem isso a pessoa entra em voz só como ouvinte (microfone travado).'),
    ('enviar_anuncios', 'Publicar em anúncios e regras', 'Escrever em canais de anúncios e de regras (todo mundo pode ler).'),
    ('falar_palco', 'Falar no palco', 'Ser orador em canal de palco e chamar ouvintes ao palco.'),
]
BIT = {p[0]: 1 << i for i, p in enumerate(PERMISSOES)}
TODAS = (1 << len(PERMISSOES)) - 1
IDS_PERMISSAO = tuple(BIT)
# O que qualquer membro já podia antes dos cargos existirem (convidar com teto, fixar, falar em voz). O dono pode mudar em Cargos > Membro.
PERMS_MEMBRO_PADRAO = BIT['criar_convite'] | BIT['fixar_mensagens'] | BIT['falar_voz']
NIVEL_DONO = 10 ** 9

MAX_CARGOS = 25
MAX_CATEGORIAS = 20
MAX_CANAIS = 120           # linhas de Channel por servidor, separadores incluídos
LIM_NOME_CARGO = 24
LIM_NOME_CATEGORIA = 32
LIM_NOME_SEPARADOR = 32

_RE_COR = re.compile(r'^#[0-9a-fA-F]{6}$')


def mascara_de(ids):
    """Lista de ids de permissão -> máscara. Id desconhecido é ignorado (cliente adulterado não inventa bit)."""
    m = 0
    for i in (ids if isinstance(ids, (list, tuple, set)) else []):
        if isinstance(i, str) and i in BIT:
            m |= BIT[i]
    return m


def ids_da_mascara(m):
    m = m or 0
    return [i for i, b in BIT.items() if m & b]


# ==========================================
# TIPOS DE CANAL (lista fechada: o servidor só aceita estes ids)
# ==========================================
TIPOS_CANAL = {
    'text': {'familia': 'texto', 'nome': 'Texto', 'desc': 'Conversa livre, com mensagens, fotos e GIFs.'},
    'anuncios': {'familia': 'texto', 'nome': 'Anúncios', 'desc': 'Todo mundo lê; só quem tem "Publicar em anúncios e regras" escreve.'},
    'regras': {'familia': 'texto', 'nome': 'Regras', 'desc': 'Somente leitura, pra regras e avisos fixos. Mesma permissão dos anúncios.'},
    'midia': {'familia': 'texto', 'nome': 'Mídia', 'desc': 'Só vale mensagem com foto, vídeo ou GIF (o texto vira legenda).'},
    'voice': {'familia': 'voz', 'nome': 'Voz', 'desc': 'Conversa por voz e vídeo, com limite de pessoas opcional.'},
    'palco': {'familia': 'voz', 'nome': 'Palco', 'desc': 'Poucos falam e o resto escuta. Quem fala é quem tem "Falar no palco" ou foi chamado ao palco.'},
    'separador': {'familia': 'estrutura', 'nome': 'Separador', 'desc': 'Uma linha na lista de canais, com título ou sem. Não guarda mensagens.'},
}
TIPOS_TEXTO = tuple(t for t, i in TIPOS_CANAL.items() if i['familia'] == 'texto')
TIPOS_VOZ = tuple(t for t, i in TIPOS_CANAL.items() if i['familia'] == 'voz')
TIPOS_SO_LEITURA = ('anuncios', 'regras')
LIMITE_VOZ_MAX = 99


def familia_do_tipo(tipo):
    return (TIPOS_CANAL.get(tipo) or {}).get('familia')


def tipo_valido(tipo, familia=None):
    """Devolve o id do tipo se ele existir (e, se `familia` foi pedida, for dela); senão None."""
    if not isinstance(tipo, str) or tipo not in TIPOS_CANAL:
        return None
    if familia and TIPOS_CANAL[tipo]['familia'] != familia:
        return None
    return tipo


_ESPECIAIS_EMOJI = ('‍', '️', '⃣')


def emoji_valido(valor):
    """Emoji do canal: só caractere de emoji/símbolo (nunca letra, número, aspa ou sinal), até 12 caracteres. Vazio -> None."""
    if not isinstance(valor, str):
        return None
    s = valor.strip()
    if not s or len(s) > 12:
        return None
    for ch in s:
        if ch in _ESPECIAIS_EMOJI:
            continue
        if ord(ch) < 0x2190 or unicodedata.category(ch) not in ('So', 'Sk', 'Sm'):
            return None
    return s


def limpar_nome(valor, limite):
    """Nome de cargo/categoria/separador: sem caractere de controle, espaços colapsados, até `limite`."""
    if not isinstance(valor, str):
        return ''
    s = ''.join(ch for ch in valor if unicodedata.category(ch) not in ('Cc', 'Cs') and ch not in ('​', '‮', '‭'))
    return re.sub(r'\s+', ' ', s).strip()[:limite]


def cor_valida(valor):
    if isinstance(valor, str) and _RE_COR.match(valor.strip()):
        return valor.strip().lower()
    return None


def limite_de_voz(valor):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= LIMITE_VOZ_MAX else None


LIM_BOAS_VINDAS = 500
_RE_URL_SEGURA = re.compile(r'^[^\s\'"()<>\\]+$')   # a URL do banner vai num style="background-image:url('...')": nada que feche aspa/parêntese


def limpar_texto(valor, limite):
    """Texto de várias linhas (boas-vindas): sem caractere de controle (menos a quebra de linha), até `limite`. Vazio -> None."""
    if not isinstance(valor, str):
        return None
    s = ''.join(ch for ch in valor.replace('\r', '') if ch == '\n' or unicodedata.category(ch) not in ('Cc', 'Cs'))
    s = re.sub(r'\n{3,}', '\n\n', s).strip()[:limite]
    return s or None


def url_de_banner(valor, imagem_ok):
    """Banner do servidor: mesma regra das outras imagens do app (`imagem_ok` = utils.url_de_imagem_ok) e sem nada que escape do CSS. Vazio -> None."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    v = valor.strip()
    return v if imagem_ok(v) and _RE_URL_SEGURA.match(v) else None


def canal_de_texto_do_servidor(srv, ref):
    """Id de um canal de TEXTO público do servidor (o que abre primeiro / leva o cartão de boas-vindas), ou None. Canal privado não serve:
    ele não aparece pra todo mundo."""
    try:
        cid = int(ref)
    except (TypeError, ValueError):
        return None
    c = Channel.query.get(cid)
    if c and c.server_id == srv.id and c.channel_type in TIPOS_TEXTO and not c.is_private:
        return c.id
    return None


# ==========================================
# CONTEXTO: o que ESTA pessoa pode NESTE servidor (sempre lido do banco)
# ==========================================
class Contexto:
    __slots__ = ('perms', 'nivel', 'dono', 'membro')

    def __init__(self, perms=0, nivel=0, dono=False, membro=False):
        self.perms, self.nivel, self.dono, self.membro = perms, nivel, dono, membro

    def tem(self, perm):
        return bool(self.perms & BIT[perm])


SEM_ACESSO = Contexto()


def _fechar(perms, nivel, membro=True):
    """Administrador vira 'todas as permissões'."""
    if perms & BIT['administrador']:
        perms = TODAS
    return Contexto(perms, nivel, False, membro)


def _base(srv):
    return srv.perms_membro if srv.perms_membro is not None else PERMS_MEMBRO_PADRAO


def _retry(fn):
    from .utils import com_retry   # import tardio: utils importa este módulo
    return com_retry(fn)


def contexto(usuario, srv):
    """Permissões e nível hierárquico da pessoa no servidor. Dono = tudo e nível máximo; quem não é membro não tem nada."""
    if usuario is None or srv is None:
        return SEM_ACESSO
    if srv.owner_id == usuario.id:
        return Contexto(TODAS, NIVEL_DONO, True, True)

    def ler():
        membro = db.session.query(server_members.c.person_id).filter(
            server_members.c.server_id == srv.id, server_members.c.person_id == usuario.id).first() is not None
        if not membro:
            return None
        perms, nivel = _base(srv), 0
        if srv.estrutura:
            for p, pos in db.session.query(ServerRole.permissoes, ServerRole.posicao).join(
                    MemberRole, MemberRole.role_id == ServerRole.id).filter(
                    MemberRole.person_id == usuario.id, MemberRole.server_id == srv.id).all():
                perms |= (p or 0)
                nivel = max(nivel, pos or 0)
        return perms, nivel

    lido = _retry(ler)
    return SEM_ACESSO if lido is None else _fechar(lido[0], lido[1])


def pode(usuario, srv, perm):
    """True se a pessoa tem a permissão `perm` (id de PERMISSOES) no servidor. `perm='dono'` = só o dono."""
    if usuario is None or srv is None:
        return False
    if perm == 'dono':
        return srv.owner_id == usuario.id
    return contexto(usuario, srv).tem(perm)


def nivel_do_membro(srv, pessoa_id):
    """Posição do cargo mais alto da pessoa (o dono vale NIVEL_DONO; sem cargo, 0)."""
    if srv.owner_id == pessoa_id:
        return NIVEL_DONO
    if not srv.estrutura:
        return 0
    pos = _retry(lambda: db.session.query(func.max(ServerRole.posicao)).join(
        MemberRole, MemberRole.role_id == ServerRole.id).filter(
        MemberRole.person_id == pessoa_id, MemberRole.server_id == srv.id).scalar())
    return pos or 0


def eh_membro(srv_id, pessoa_id):
    return _retry(lambda: db.session.query(server_members.c.person_id).filter(
        server_members.c.server_id == srv_id, server_members.c.person_id == pessoa_id).first() is not None)


# ==========================================
# ESTRUTURA EM MEMÓRIA (só pra desenhar; a decisão de poder ou não lê o banco)
# ==========================================
_CACHE = {}          # server_id -> (expira_em, estrutura)
_TTL_S = 600


def invalidar(server_id):
    _CACHE.pop(int(server_id), None)


def limpar_cache():
    _CACHE.clear()


def carregar_estruturas(servidores):
    """{server_id: estrutura} dos servidores que têm `estrutura`. Nenhuma query se nenhum tem ou se já está em cache;
    senão 3 queries pro lote inteiro (cargos, categorias, quem tem qual cargo)."""
    agora = time.time()
    saida, faltam = {}, []
    for s in servidores:
        if not s.estrutura:
            continue
        c = _CACHE.get(s.id)
        if c and c[0] > agora:
            saida[s.id] = c[1]
        else:
            faltam.append(s.id)
    if faltam:
        novos = {i: {'cargos': [], 'categorias': [], 'membros': {}} for i in faltam}
        for r in ServerRole.query.filter(ServerRole.server_id.in_(faltam)).order_by(ServerRole.posicao.desc(), ServerRole.id.asc()).all():
            novos[r.server_id]['cargos'].append({'id': r.id, 'nome': r.nome, 'cor': r.cor, 'permissoes': r.permissoes or 0,
                                                 'posicao': r.posicao or 0, 'destacar': bool(r.destacar)})
        for c in ChannelCategory.query.filter(ChannelCategory.server_id.in_(faltam)).order_by(ChannelCategory.posicao.asc(), ChannelCategory.id.asc()).all():
            novos[c.server_id]['categorias'].append({'id': c.id, 'nome': c.nome, 'pos': c.posicao or 0})
        for sid, pid, rid in db.session.query(MemberRole.server_id, MemberRole.person_id, MemberRole.role_id).filter(MemberRole.server_id.in_(faltam)).all():
            novos[sid]['membros'].setdefault(pid, []).append(rid)
        for i, est in novos.items():
            _CACHE[i] = (agora + _TTL_S, est)
            saida[i] = est
    return saida


def perms_em_memoria(srv, pessoa_id, est):
    """Mesma conta do `contexto`, mas em cima da estrutura já carregada (zero query). (máscara, nível)."""
    if srv.owner_id == pessoa_id:
        return TODAS, NIVEL_DONO
    perms, nivel = _base(srv), 0
    if est:
        por_id = {c['id']: c for c in est['cargos']}
        for rid in est['membros'].get(pessoa_id, ()):
            c = por_id.get(rid)
            if c:
                perms |= c['permissoes']
                nivel = max(nivel, c['posicao'])
    return (TODAS if perms & BIT['administrador'] else perms), nivel


def extras_do_servidor(srv, est, usuario, visiveis):
    """Campos que entram no JSON do servidor DE QUEM está olhando (cada membro recebe o seu).
    `visiveis` = os canais (em dict) que essa pessoa enxerga: categoria sem nenhum canal visível não aparece pra quem não gerencia canais
    (senão o nome de uma categoria só de canais privados vazaria)."""
    if usuario is None:       # caminho do dono (sem destinatário): vê tudo
        perms, nivel, meus = TODAS, NIVEL_DONO, []
    else:
        perms, nivel = perms_em_memoria(srv, usuario.id, est)
        meus = list((est or {}).get('membros', {}).get(usuario.id, []))
    gerencia_cargos = bool(perms & BIT['gerenciar_cargos'])
    gerencia_canais = bool(perms & BIT['gerenciar_canais'])
    cats = []
    if est:
        com_canal = {c.get('categoria_id') for c in visiveis if c.get('categoria_id')}
        cats = [dict(c) for c in est['categorias'] if gerencia_canais or c['id'] in com_canal]
    cargos = []
    for c in (est or {}).get('cargos', []):
        item = {'id': c['id'], 'nome': c['nome'], 'cor': c['cor'], 'pos': c['posicao'], 'destacar': c['destacar']}
        if gerencia_cargos:
            item['perms'] = ids_da_mascara(c['permissoes'])
        cargos.append(item)
    out = {
        'categorias': cats, 'cargos': cargos, 'meusCargos': meus, 'minhasPerms': ids_da_mascara(perms),
        'meuNivel': min(nivel, NIVEL_DONO), 'boasVindas': srv.boas_vindas, 'canalBoasVindas': srv.canal_boas_vindas_id,
        'bannerUrl': srv.banner_url,
    }
    if gerencia_cargos:
        out['permsMembro'] = ids_da_mascara(_base(srv))
    return out


def cargos_dos_membros(srv):
    """{pessoa_id: [ids de cargo]} do servidor (da estrutura em cache; vazio em servidor sem cargos)."""
    est = carregar_estruturas([srv]).get(srv.id)
    return (est or {}).get('membros', {})


# ==========================================
# CARGOS: escrever (tudo dentro do `preparar` de comitar_com_retry; quem chama faz rollback no erro e `invalidar` depois do commit)
# ==========================================
def _exigir(ctx, perm, msg):
    if not ctx.tem(perm):
        raise ErroCargo(msg)


def _marcar_estrutura(srv):
    if not srv.estrutura:
        srv.estrutura = True


def _cargo_do_servidor(srv, cargo_id):
    try:
        cid = int(cargo_id)
    except (TypeError, ValueError):
        raise ErroCargo('Esse cargo não existe.')
    r = ServerRole.query.get(cid)
    if not r or r.server_id != srv.id:
        raise ErroCargo('Esse cargo não existe.')
    return r


def _alcance(ctx, cargo):
    """Cargo igual ou acima do meu: não mexo."""
    if not ctx.dono and (cargo.posicao or 0) >= ctx.nivel:
        raise ErroCargo('Você só mexe em cargos abaixo do seu.')


def _sem_escalar(ctx, mascara, antiga=0):
    """Não dá pra conceder permissão que você mesmo não tem (mexer só nos bits que são seus)."""
    if ctx.dono:
        return
    if (mascara ^ antiga) & ~ctx.perms:
        raise ErroCargo('Você não pode dar ou tirar uma permissão que você mesmo não tem.')


def criar_cargo(srv, ctx, nome, cor=None, permissoes=None, destacar=False):
    _exigir(ctx, 'gerenciar_cargos', 'Você não pode gerenciar cargos.')
    nome = limpar_nome(nome, LIM_NOME_CARGO)
    if not nome:
        raise ErroCargo('Dê um nome ao cargo.')
    if ServerRole.query.filter_by(server_id=srv.id).count() >= MAX_CARGOS:
        raise ErroCargo(f'Cada servidor tem no máximo {MAX_CARGOS} cargos.')
    mascara = mascara_de(permissoes)
    _sem_escalar(ctx, mascara)
    # O cargo novo nasce no fundo da lista: sobe todo mundo uma casa (ninguém muda de posição relativa).
    ServerRole.query.filter_by(server_id=srv.id).update({ServerRole.posicao: ServerRole.posicao + 1}, synchronize_session=False)
    r = ServerRole(server_id=srv.id, nome=nome, cor=cor_valida(cor), permissoes=mascara, posicao=1, destacar=bool(destacar))
    db.session.add(r)
    _marcar_estrutura(srv)
    return r


def editar_cargo(srv, ctx, cargo_id, campos):
    _exigir(ctx, 'gerenciar_cargos', 'Você não pode gerenciar cargos.')
    r = _cargo_do_servidor(srv, cargo_id)
    _alcance(ctx, r)
    if 'nome' in campos:
        nome = limpar_nome(campos.get('nome'), LIM_NOME_CARGO)
        if not nome:
            raise ErroCargo('O cargo precisa de um nome.')
        r.nome = nome
    if 'cor' in campos:
        r.cor = cor_valida(campos.get('cor'))
    if 'destacar' in campos:
        r.destacar = bool(campos.get('destacar'))
    if 'permissoes' in campos:
        nova = mascara_de(campos.get('permissoes'))
        _sem_escalar(ctx, nova, r.permissoes or 0)
        r.permissoes = nova
    return r


def apagar_cargo(srv, ctx, cargo_id):
    _exigir(ctx, 'gerenciar_cargos', 'Você não pode gerenciar cargos.')
    r = _cargo_do_servidor(srv, cargo_id)
    _alcance(ctx, r)
    db.session.delete(r)     # as ligações com os membros saem junto (cascade)
    return r


def reordenar_cargos(srv, ctx, ordem):
    """`ordem` = ids do mais alto pro mais baixo, SÓ dos cargos que a pessoa pode mexer (os abaixo dela; o dono mexe em todos).
    Os cargos dela e acima ficam onde estão: as posições que os mexíveis ocupam são só redistribuídas entre eles."""
    _exigir(ctx, 'gerenciar_cargos', 'Você não pode gerenciar cargos.')
    todos = ServerRole.query.filter_by(server_id=srv.id).all()
    mexiveis = [r for r in todos if ctx.dono or (r.posicao or 0) < ctx.nivel]
    por_id = {r.id: r for r in mexiveis}
    pedida, vistos = [], set()
    for i in (ordem if isinstance(ordem, list) else []):
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if i in por_id and i not in vistos:
            vistos.add(i)
            pedida.append(por_id[i])
    pedida += [r for r in sorted(mexiveis, key=lambda x: -(x.posicao or 0)) if r.id not in vistos]
    posicoes = sorted((r.posicao or 0 for r in mexiveis), reverse=True)
    for r, p in zip(pedida, posicoes):
        r.posicao = p


def atribuir_cargo(srv, ctx, pessoa_id, cargo_id, ativo, eu_id):
    """Dá ou tira um cargo. O cargo precisa estar abaixo do meu e dentro das minhas permissões; o alvo também precisa estar abaixo
    de mim (exceção: eu mesmo, que posso me dar/tirar cargos abaixo do meu)."""
    _exigir(ctx, 'gerenciar_cargos', 'Você não pode gerenciar cargos.')
    r = _cargo_do_servidor(srv, cargo_id)
    _alcance(ctx, r)
    _sem_escalar(ctx, r.permissoes or 0)
    try:
        pessoa_id = int(pessoa_id)
    except (TypeError, ValueError):
        raise ErroCargo('Essa pessoa não está no servidor.')
    if pessoa_id == srv.owner_id and eu_id != srv.owner_id:
        raise ErroCargo('O dono já pode tudo.')
    if not eh_membro(srv.id, pessoa_id):
        raise ErroCargo('Essa pessoa não está no servidor.')
    if pessoa_id != eu_id and not ctx.dono and nivel_do_membro(srv, pessoa_id) >= ctx.nivel:
        raise ErroCargo('Você só mexe nos cargos de quem está abaixo de você.')
    existente = MemberRole.query.filter_by(person_id=pessoa_id, role_id=r.id).first()
    if ativo and not existente:
        db.session.add(MemberRole(server_id=srv.id, person_id=pessoa_id, role_id=r.id))
    elif not ativo and existente:
        db.session.delete(existente)
    return r


def definir_perms_membro(srv, ctx, permissoes):
    """Permissões do cargo padrão "Membro" (vale pra todo mundo). Só quem gerencia cargos, sem conceder o que não tem."""
    _exigir(ctx, 'gerenciar_cargos', 'Você não pode gerenciar cargos.')
    nova = mascara_de(permissoes)
    if nova & BIT['administrador']:
        raise ErroCargo('Todo mundo como administrador? Dê esse poder por um cargo.')
    _sem_escalar(ctx, nova, _base(srv))
    srv.perms_membro = nova


def limpar_membro(srv_id, pessoa_id):
    """A pessoa saiu ou foi removida: perde os cargos que tinha neste servidor."""
    MemberRole.query.filter_by(server_id=srv_id, person_id=pessoa_id).delete(synchronize_session=False)


# ==========================================
# CATEGORIAS, SEPARADORES E ORGANIZAÇÃO DOS CANAIS
# ==========================================
PADRAO_TEXTO = 'padrao_text'      # ids "virtuais" das duas seções que todo servidor antigo mostra sem terem linha no banco
PADRAO_VOZ = 'padrao_voice'
_NOMES_PADRAO = {PADRAO_TEXTO: 'CANAIS DE TEXTO', PADRAO_VOZ: 'CANAIS DE VOZ'}


def materializar_padrao(srv):
    """Servidor sem nenhuma categoria mostra duas seções 'virtuais' (CANAIS DE TEXTO/VOZ). Na primeira vez que alguém organiza a lista,
    elas viram categorias de verdade e os canais soltos entram na do seu tipo. Devolve {PADRAO_TEXTO: id, PADRAO_VOZ: id}. Idempotente."""
    existentes = ChannelCategory.query.filter_by(server_id=srv.id).order_by(ChannelCategory.posicao, ChannelCategory.id).all()
    if existentes:
        return {}
    texto = ChannelCategory(server_id=srv.id, nome=_NOMES_PADRAO[PADRAO_TEXTO], posicao=0)
    voz = ChannelCategory(server_id=srv.id, nome=_NOMES_PADRAO[PADRAO_VOZ], posicao=1)
    db.session.add_all([texto, voz])
    db.session.flush()
    for c in Channel.query.filter_by(server_id=srv.id).filter(Channel.category_id.is_(None)).all():
        c.category_id = voz.id if familia_do_tipo(c.channel_type) == 'voz' else texto.id
    _marcar_estrutura(srv)
    return {PADRAO_TEXTO: texto.id, PADRAO_VOZ: voz.id}


def resolver_categoria(srv, ref):
    """Aceita id real (int ou texto numérico) ou um dos ids virtuais; devolve a ChannelCategory do servidor, ou None se `ref` for vazio/0."""
    if ref in (None, '', 0, '0'):
        return None
    if ref in _NOMES_PADRAO:
        ids = materializar_padrao(srv)
        if ids:
            return ChannelCategory.query.get(ids[ref])
        raise ErroCargo('A lista de canais mudou. Atualize a tela e tente de novo.')
    try:
        cid = int(ref)
    except (TypeError, ValueError):
        raise ErroCargo('Essa categoria não existe.')
    cat = ChannelCategory.query.get(cid)
    if not cat or cat.server_id != srv.id:
        raise ErroCargo('Essa categoria não existe.')
    return cat


def criar_categoria(srv, ctx, nome):
    _exigir(ctx, 'gerenciar_canais', 'Você não pode gerenciar canais.')
    nome = limpar_nome(nome, LIM_NOME_CATEGORIA)
    if not nome:
        raise ErroCargo('Dê um nome à categoria.')
    materializar_padrao(srv)      # a 1ª categoria de um servidor antigo leva junto as duas seções que ele já mostrava
    if ChannelCategory.query.filter_by(server_id=srv.id).count() >= MAX_CATEGORIAS:
        raise ErroCargo(f'Cada servidor tem no máximo {MAX_CATEGORIAS} categorias.')
    ultima = db.session.query(func.max(ChannelCategory.posicao)).filter_by(server_id=srv.id).scalar()
    cat = ChannelCategory(server_id=srv.id, nome=nome, posicao=(ultima if ultima is not None else -1) + 1)
    db.session.add(cat)
    _marcar_estrutura(srv)
    return cat


def renomear_categoria(srv, ctx, ref, nome):
    _exigir(ctx, 'gerenciar_canais', 'Você não pode gerenciar canais.')
    nome = limpar_nome(nome, LIM_NOME_CATEGORIA)
    if not nome:
        raise ErroCargo('A categoria precisa de um nome.')
    cat = resolver_categoria(srv, ref)
    if cat is None:
        raise ErroCargo('Essa categoria não existe.')
    cat.nome = nome
    return cat


def apagar_categoria(srv, ctx, ref):
    """Os canais da categoria não somem: ficam soltos no topo da lista."""
    _exigir(ctx, 'gerenciar_canais', 'Você não pode gerenciar canais.')
    cat = resolver_categoria(srv, ref)
    if cat is None:
        raise ErroCargo('Essa categoria não existe.')
    Channel.query.filter_by(server_id=srv.id, category_id=cat.id).update({Channel.category_id: None}, synchronize_session=False)
    db.session.delete(cat)
    return cat


def _canais_que_a_pessoa_ve(srv, ctx, pessoa_id):
    """{id: Channel} dos canais do servidor que ESSA pessoa enxerga (privado só com convite, dono ou 'Ver canais privados')."""
    canais = Channel.query.filter_by(server_id=srv.id).all()
    if ctx.dono or ctx.tem('ver_canais_privados'):
        return {c.id: c for c in canais}
    privados = [c.id for c in canais if c.is_private]
    liberados = set()
    if privados:
        liberados = {cid for (cid,) in db.session.query(channel_members.c.channel_id).filter(
            channel_members.c.person_id == pessoa_id, channel_members.c.channel_id.in_(privados)).all()}
    return {c.id: c for c in canais if not c.is_private or c.id in liberados}


def organizar_canais(srv, ctx, pessoa_id, ordem_categorias, grupos):
    """Arrastar e soltar: o cliente manda a lista inteira desejada e o servidor só aplica o que for válido.
    `ordem_categorias` = ids de categoria na ordem nova; `grupos` = {'0': [canais soltos], '<categoria>': [canais na ordem]}.
    Id que não é deste servidor (ou de canal que a pessoa não enxerga) é ignorado; canal não citado fica como está."""
    _exigir(ctx, 'gerenciar_canais', 'Você não pode gerenciar canais.')
    if not isinstance(grupos, dict):
        grupos = {}
    # Servidor antigo (seções virtuais): materializa primeiro e traduz os ids virtuais que o cliente mandou.
    traducao = materializar_padrao(srv) if (PADRAO_TEXTO in grupos or PADRAO_VOZ in grupos
                                           or PADRAO_TEXTO in (ordem_categorias or []) or PADRAO_VOZ in (ordem_categorias or [])) else {}
    cats = {c.id: c for c in ChannelCategory.query.filter_by(server_id=srv.id).all()}

    def id_cat(ref):
        if ref in traducao:
            return traducao[ref]
        try:
            return int(ref)
        except (TypeError, ValueError):
            return None

    # ordem das categorias
    vistos, nova_ordem = set(), []
    for ref in (ordem_categorias if isinstance(ordem_categorias, list) else []):
        cid = id_cat(ref)
        if cid in cats and cid not in vistos:
            vistos.add(cid)
            nova_ordem.append(cid)
    nova_ordem += [c.id for c in sorted(cats.values(), key=lambda c: ((c.posicao or 0), c.id)) if c.id not in vistos]
    for i, cid in enumerate(nova_ordem):
        cats[cid].posicao = i
    # canais
    visiveis = _canais_que_a_pessoa_ve(srv, ctx, pessoa_id)
    usados = set()
    for chave, lista in grupos.items():
        if chave in ('0', 0, '', None):
            destino = None
        else:
            destino = id_cat(chave)
            if destino not in cats:
                continue
        for i, ref in enumerate(lista if isinstance(lista, list) else []):
            try:
                canal_id = int(ref)
            except (TypeError, ValueError):
                continue
            c = visiveis.get(canal_id)
            if c is None or canal_id in usados:
                continue
            usados.add(canal_id)
            c.category_id = destino
            c.position = i


def categoria_para_novo_canal(srv, familia):
    """Categoria onde um canal novo cai quando ninguém escolheu: a primeira que já guarda canais da mesma família (texto/voz)."""
    tipos = TIPOS_VOZ if familia == 'voz' else TIPOS_TEXTO
    usadas = {cid for (cid,) in db.session.query(Channel.category_id).filter(
        Channel.server_id == srv.id, Channel.channel_type.in_(tipos), Channel.category_id.isnot(None)).distinct().all()}
    if not usadas:
        return None
    primeira = ChannelCategory.query.filter(ChannelCategory.server_id == srv.id, ChannelCategory.id.in_(usadas)).order_by(
        ChannelCategory.posicao, ChannelCategory.id).first()
    return primeira.id if primeira else None


def proxima_posicao(srv_id, categoria_id):
    q = db.session.query(func.max(Channel.position)).filter(Channel.server_id == srv_id)
    q = q.filter(Channel.category_id == categoria_id) if categoria_id else q.filter(Channel.category_id.is_(None))
    ultimo = q.scalar()
    return (ultimo if ultimo is not None else -1) + 1


# ==========================================
# REGRAS POR TIPO DE CANAL
# ==========================================
def checar_envio(usuario, srv, canal, tem_anexo):
    """(ok, mensagem). Canal de texto normal passa direto SEM consulta nenhuma; anúncios/regras exigem a permissão; mídia exige anexo."""
    tipo = canal.channel_type or 'text'
    if tipo in TIPOS_SO_LEITURA:
        if srv is None or not pode(usuario, srv, 'enviar_anuncios'):
            nome = 'anúncios' if tipo == 'anuncios' else 'regras'
            return False, f'Só quem tem permissão publica em canais de {nome}.'
    elif tipo == 'midia' and not tem_anexo:
        return False, 'Esse canal é só de mídia: mande uma foto, um vídeo ou um GIF (o texto vai como legenda).'
    return True, ''


def regras_de_voz(usuario, srv, canal, participantes, convidados=()):
    """Entrada numa call de servidor. Devolve (ok, mensagem, ouvinte). `participantes` = quem já está (lista de dicts do events).
    Lotação (limite do canal) é recusa de verdade; 'ouvinte' (sem falar_voz, ou no palco sem falar_palco e sem convite) tranca o microfone no cliente
    e fica marcado pra todo mundo: o áudio é P2P, então o servidor não corta a mídia (trava leve, como a localização)."""
    if srv is None:
        return True, '', False
    ctx = contexto(usuario, srv)
    limite = canal.user_limit
    if limite and (canal.channel_type or 'voice') in TIPOS_VOZ:
        dentro = {p.get('usuario_id') for p in participantes if p.get('usuario_id') != usuario.id}
        if len(dentro) >= limite:
            return False, f'Esse canal está lotado ({limite}/{limite}).', False
    if canal.channel_type == 'palco':
        ouvinte = not (ctx.tem('falar_palco') or usuario.id in convidados)
    else:
        ouvinte = not ctx.tem('falar_voz')
    return True, '', ouvinte
