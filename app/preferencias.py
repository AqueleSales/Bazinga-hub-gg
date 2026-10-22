"""Preferências da CONTA (Configurações > Notificações, Acessibilidade, Idioma e horário). Rodada 34. Sem socket.

Guardadas em `Person.preferencias` (TEXT, JSON; NULL = tudo no padrão), pra acompanhar a pessoa em qualquer aparelho. O servidor valida contra uma
LISTA FECHADA (`CAMPOS`): chave desconhecida ou valor fora da lista é descartado, então o que vai parar num atributo do <html> ou numa classe CSS nunca é
texto livre. O que é do APARELHO (som ligado, aviso na área de trabalho, volume, push deste aparelho) continua no localStorage de propósito:
quem usa o PC com som e o celular sem som não quer uma preferência só pros dois.

Notificações por tipo (`n_<tipo>`): desligar um tipo faz o SERVIDOR não criar a entrada na caixa de entrada e não mandar push daquele tipo
(`aviso_ligado`), e o cliente não toca som nem mostra aviso daquele tipo. Os avisos de "sistema" (pagamento confirmado, caso do Guardião, loja
liberada...) não entram na lista: são o que a pessoa precisa saber e não dá pra desligar.
"""
import json
import time

# (id, rótulo, descrição) dos avisos que a pessoa pode desligar. Mesma ordem da tela.
TIPOS_AVISO = [
    ('dm', 'Mensagens diretas', 'Quando alguém te escreve numa conversa privada.'),
    ('mencao', 'Menções', 'Quando alguém cita você com @ num canal.'),
    ('amizade', 'Pedidos de amizade', 'Quando alguém quer ser seu amigo ou aceita o seu pedido.'),
    ('ligacao', 'Ligações', 'Quando um amigo te liga por voz ou vídeo.'),
    ('bazar', 'Bazar', 'Pedidos, pagamentos e conversas das suas compras e vendas.'),
    ('nota', 'Notas do mapa', 'Quando alguém responde a uma nota que você deixou.'),
]
IDS_AVISO = [t[0] for t in TIPOS_AVISO]

# chave -> (valores permitidos, padrão). Booleanos usam (True, False).
CAMPOS = {
    'texto': (('p', 'm', 'g', 'gg'), 'm'),                       # tamanho do texto do chat
    'densidade': (('compacta', 'padrao', 'ampla'), 'padrao'),    # espaço entre mensagens e itens das listas
    'sublinhar': ((True, False), False),                         # sublinhar links
    'reduz_mov': ((True, False), False),                         # reduzir animações
    'hora12': ((True, False), False),                            # relógio de 12 h (AM/PM)
}
for _id in IDS_AVISO:
    CAMPOS['n_' + _id] = ((True, False), True)

PADRAO = {k: v[1] for k, v in CAMPOS.items()}


def _valor_valido(chave, valor):
    """O valor, se estiver na lista da chave; senão None. Booleano só aceita bool de verdade (não 0/1/'true')."""
    opcoes = CAMPOS[chave][0]
    if opcoes == (True, False):
        return valor if isinstance(valor, bool) else None
    return valor if isinstance(valor, str) and valor in opcoes else None


def normalizar(dados):
    """Só as chaves conhecidas com valor válido. Entrada de qualquer tipo (JSON quebrado, lista, texto) vira {}."""
    if not isinstance(dados, dict):
        return {}
    saida = {}
    for chave in CAMPOS:
        if chave in dados:
            v = _valor_valido(chave, dados[chave])
            if v is not None:
                saida[chave] = v
    return saida


def guardadas(pessoa):
    """O que a pessoa já mexeu (JSON da coluna, normalizado)."""
    bruto = getattr(pessoa, 'preferencias', None)
    if not bruto:
        return {}
    try:
        return normalizar(json.loads(bruto))
    except (TypeError, ValueError):
        return {}


def da_pessoa(pessoa):
    """Todas as preferências, com o padrão onde a pessoa nunca mexeu."""
    return {**PADRAO, **guardadas(pessoa)}


def aplicar(pessoa, mudancas):
    """Mescla `mudancas` (só o que é válido) no que a pessoa já tinha e grava na coluna (sem commit). Devolve o dicionário completo novo."""
    novas = normalizar(mudancas)
    atual = {**guardadas(pessoa), **novas}
    # só guarda o que difere do padrão: a coluna fica pequena e mudar um padrão no futuro vale pra quem nunca mexeu
    diferentes = {k: v for k, v in atual.items() if v != PADRAO[k]}
    pessoa.preferencias = json.dumps(diferentes, separators=(',', ':')) if diferentes else None
    return {**PADRAO, **atual}


# ---------------------------------------------------------------------------
# Cache em memória (um processo só, -w 1): `aviso_ligado` roda a cada DM/menção/pedido, e quem recebe quase sempre está online (o connect já
# encheu o cache). Sem cache seria uma consulta a mais por notificação. Expira em 10 min pra consertar qualquer desvio.
# ---------------------------------------------------------------------------
_CACHE = {}
_TTL = 600
_MAX = 5000


def guardar_no_cache(pessoa):
    if len(_CACHE) >= _MAX:
        _CACHE.clear()
    _CACHE[pessoa.id] = (time.monotonic(), da_pessoa(pessoa))


def _do_cache_ou_banco(pessoa_id):
    achado = _CACHE.get(pessoa_id)
    if achado and time.monotonic() - achado[0] < _TTL:
        return achado[1]
    from .models import Person
    pessoa = Person.query.get(pessoa_id)       # mapa de identidade: se já foi carregada nesta requisição, não vai ao banco
    if pessoa is None:
        return dict(PADRAO)
    guardar_no_cache(pessoa)
    return _CACHE[pessoa_id][1]


def aviso_ligado(pessoa_id, tipo):
    """True se a pessoa quer ser avisada desse tipo (caixa de entrada, push). Tipo fora da lista (sistema, por exemplo) é sempre True."""
    if tipo not in IDS_AVISO:
        return True
    try:
        return bool(_do_cache_ou_banco(pessoa_id).get('n_' + tipo, True))
    except Exception as e:
        print(f"[ERRO PREFERENCIAS] {e}")
        return True


def esquecer(pessoa_id):
    _CACHE.pop(pessoa_id, None)
