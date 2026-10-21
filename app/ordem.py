"""Ordem dos servidores na barra lateral, pastinhas e conversas fixadas na lista de DMs (Rodada 29).

Tudo mora na CONTA (`Person.ordem_servidores` e `Person.ordem_dms`, TEXT com JSON), não no navegador: vale em qualquer aparelho.
Este módulo só valida e normaliza (sem socket, sem consulta): quem chama passa os ids que a pessoa PODE ter.

Formato do layout dos servidores (lista na ordem de cima pra baixo):
    [12, {"pasta": "k3f9x2ab", "nome": "Jogos", "cor": "#5865f2", "ids": [3, 7]}, 5]
  - inteiro = servidor solto;  dict = pasta com 2+ servidores (pasta com 0 ou 1 se desfaz: o sobrevivente fica no lugar dela).
Formato das DMs fixadas: lista de ids de amigos, na ordem de cima pra baixo ([4, 9]). Quem não está na lista segue a ordem de
mensagem recente. Detalhes e a conta de como a mensagem nova convive com a ordem escolhida: CLAUDE.md, Rodada 29.

Regra 4 (permissão no servidor): id de servidor que a pessoa não integra, id de amigo que não é amigo, nome/cor fora do formato,
pasta repetida e excesso de tamanho são DESCARTADOS aqui; o que o cliente manda nunca vira dado sem passar por estas funções.
"""
import json
import re
import unicodedata

MAX_SERVIDORES = 300          # entradas de topo lidas (servidor solto ou pasta)
MAX_PASTAS = 30
MAX_POR_PASTA = 60
MAX_NOME_PASTA = 24
MAX_FIXAS = 50
PASTA_NOME_PADRAO = 'Pasta'
COR_PASTA_PADRAO = '#5865f2'

_RE_COR = re.compile(r'^#[0-9a-fA-F]{6}$')
_RE_ID_PASTA = re.compile(r'^[a-z0-9]{4,12}$')


def _inteiro(v):
    """Só inteiro de verdade (bool é int em Python e não vale; texto numérico também não: o cliente manda número)."""
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    return v if 0 < v < 2 ** 31 else None


def nome_de_pasta(valor):
    """Nome limpo: sem caractere de controle/invisível (inclui os que invertem o texto), espaços colapsados, até 24 caracteres."""
    if not isinstance(valor, str):
        return PASTA_NOME_PADRAO
    limpo = ''.join(c for c in valor if unicodedata.category(c) not in ('Cc', 'Cf', 'Cs', 'Co', 'Cn'))
    limpo = re.sub(r'\s+', ' ', limpo).strip()[:MAX_NOME_PASTA].strip()
    return limpo or PASTA_NOME_PADRAO


def cor_de_pasta(valor):
    """`#rrggbb` em minúsculas (a cor vai dentro de um `style=""` no navegador de quem tem a pasta); o resto vira a cor padrão."""
    if isinstance(valor, str) and _RE_COR.match(valor):
        return valor.lower()
    return COR_PASTA_PADRAO


def carregar_json(texto):
    """O JSON guardado na coluna, ou None se estiver vazio/quebrado (coluna anulável: NULL = nunca mexeu)."""
    if not texto or not isinstance(texto, str):
        return None
    try:
        return json.loads(texto)
    except (ValueError, TypeError):
        return None


def serializar(valor):
    return json.dumps(valor, ensure_ascii=False, separators=(',', ':'))


def normalizar_layout(bruto, ids_validos):
    """Layout limpo a partir do que veio (lista, ou o texto JSON da coluna). `ids_validos` = ids dos servidores de que a pessoa é membro.
    Descarta o que não conhece, remove repetidos (um servidor aparece uma vez só, solto OU numa pasta) e desfaz pasta com menos de 2."""
    if isinstance(bruto, str):
        bruto = carregar_json(bruto)
    if not isinstance(bruto, list):
        return []
    validos = set(ids_validos)
    vistos, pastas_vistas, saida = set(), set(), []
    n_pastas = 0
    for item in bruto[:MAX_SERVIDORES]:
        n = _inteiro(item)
        if n is not None:
            if n in validos and n not in vistos:
                vistos.add(n)
                saida.append(n)
            continue
        if not isinstance(item, dict) or n_pastas >= MAX_PASTAS:
            continue
        pid = item.get('pasta')
        brutos = item.get('ids')
        if not isinstance(pid, str) or not _RE_ID_PASTA.match(pid) or pid in pastas_vistas or not isinstance(brutos, list):
            continue
        pastas_vistas.add(pid)
        ids = []
        for x in brutos[:MAX_POR_PASTA]:
            m = _inteiro(x)
            if m in validos and m not in vistos:
                vistos.add(m)
                ids.append(m)
        if len(ids) >= 2:
            n_pastas += 1
            saida.append({'pasta': pid, 'nome': nome_de_pasta(item.get('nome')), 'cor': cor_de_pasta(item.get('cor')), 'ids': ids})
        else:
            saida.extend(ids)       # pasta com 1 servidor (ou nenhum) se desfaz
    return saida


def completar_layout(layout, ids_na_ordem_padrao):
    """Servidor que não está no layout salvo (entrou depois, ou a pessoa nunca ordenou) vai pro FIM, na ordem padrão."""
    presentes = set()
    for item in layout:
        if isinstance(item, dict):
            presentes.update(item['ids'])
        else:
            presentes.add(item)
    return list(layout) + [i for i in ids_na_ordem_padrao if i not in presentes]


def layout_da_pessoa(pessoa, ids_na_ordem_padrao):
    """O layout pronto pra mandar ao cliente: o salvo, limpo contra os servidores de agora, com os que faltam no fim."""
    return completar_layout(normalizar_layout(pessoa.ordem_servidores, ids_na_ordem_padrao), ids_na_ordem_padrao)


def normalizar_fixas(bruto, ids_validos=None):
    """Lista limpa de DMs fixadas. `ids_validos` None = só o formato (leitura barata no /chat); com a lista de amigos, descarta quem não é amigo."""
    if isinstance(bruto, str):
        bruto = carregar_json(bruto)
    if not isinstance(bruto, list):
        return []
    validos = None if ids_validos is None else set(ids_validos)
    vistos, saida = set(), []
    for x in bruto[:MAX_FIXAS * 2]:
        n = _inteiro(x)
        if n is None or n in vistos or (validos is not None and n not in validos):
            continue
        vistos.add(n)
        saida.append(n)
        if len(saida) >= MAX_FIXAS:
            break
    return saida


def fixas_da_pessoa(pessoa):
    return normalizar_fixas(pessoa.ordem_dms)


def ordenar_amigos(amigos, fixas):
    """Amigos com as fixadas primeiro, na ordem escolhida; o resto mantém a ordem que veio. Devolve (lista, ids das fixadas que existem)."""
    por_id = {a.id: a for a in amigos}
    topo = [por_id[i] for i in fixas if i in por_id]
    ids_topo = {a.id for a in topo}
    return topo + [a for a in amigos if a.id not in ids_topo], [a.id for a in topo]
