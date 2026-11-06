"""DADOS PESSOAIS (Rodada 40, sem socket): rolar dado, cara ou coroa e sortear alguém da call.

Antes era uma atividade COMPARTILHADA da call (todo mundo recebia o estado e ela ocupava a única vaga de atividade, impedindo abrir o xadrez). Agora é um painel
PESSOAL: a rolagem é sua. O sorteio continua sendo do SERVIDOR (SystemRandom; o cliente só anima o número que o servidor devolveu), e `dados_events.py` decide
quem vê: só você (padrão) ou, se você escolher mostrar, a call e/ou um canal de texto.

Gramática fechada (nada de eval): `2d20kh1+1d6+5`. Dados d4 d6 d8 d10 d12 d20 d100; `kh<N>` fica com os N maiores, `kl<N>` com os N menores; no máximo
30 dados, modificador de -999 a +999, 10 moedas.
"""
import random
import re
import time

_alea = random.SystemRandom()        # sorteio de verdade (o que decide "quem vai?" ou "deu 20?" não pode ser previsível)

DADOS = {'d4': 4, 'd6': 6, 'd8': 8, 'd10': 10, 'd12': 12, 'd20': 20, 'd100': 100}
MAX_DADOS_NA_ROLAGEM = 30
MAX_GRUPOS = 8                       # tipos de dado diferentes numa rolagem montada pelos botões
MAX_MOEDAS = 10
MAX_MODIFICADOR = 999
_RE_TERMO = re.compile(r'^(\d{1,2})?d(4|6|8|10|12|20|100)(?:(kh|kl)(\d{1,2}))?$')


class ErroRolagem(Exception):
    """O pedido não vale: a mensagem vai pra quem rolou."""


def ler_expressao(expr):
    """"2d20kh1+1d6+5" -> ([{'dado': 'd20', 'qtd': 2, 'sinal': 1, 'manter': ('kh', 1)}, ...], modificador). Lista fechada de dados, no máximo
    MAX_DADOS_NA_ROLAGEM dados; kh<N> = fica com os N maiores (vantagem é 2d20kh1), kl<N> = os N menores (desvantagem é 2d20kl1)."""
    s = re.sub(r'\s+', '', str(expr or '')).lower()
    if not s or len(s) > 60:
        raise ErroRolagem('Escreva algo como 2d6+3 (até 60 caracteres).')
    termos = re.findall(r'[+-]?[^+-]+', s)
    if ''.join(termos) != s:
        raise ErroRolagem('Não entendi essa expressão.')
    grupos, mod, total = [], 0, 0
    for t in termos:
        sinal = -1 if t.startswith('-') else 1
        corpo = t.lstrip('+-')
        if corpo.isdigit():
            mod += sinal * int(corpo)
            continue
        m = _RE_TERMO.match(corpo)
        if not m:
            raise ErroRolagem(f'Não entendi "{corpo[:12]}". Dados aceitos: d4, d6, d8, d10, d12, d20 e d100.')
        qtd = int(m.group(1) or 1)
        if qtd < 1:
            raise ErroRolagem('Quantidade de dados inválida.')
        manter = None
        if m.group(3):
            n = int(m.group(4))
            if n < 1 or n > qtd:
                raise ErroRolagem(f'"{m.group(3)}{n}" precisa ficar entre 1 e a quantidade de dados ({qtd}).')
            manter = (m.group(3), n)
        total += qtd
        grupos.append({'dado': 'd' + m.group(2), 'qtd': qtd, 'sinal': sinal, 'manter': manter})
    if not grupos:
        raise ErroRolagem('Falta um dado na expressão (ex.: 1d20+4).')
    if total > MAX_DADOS_NA_ROLAGEM:
        raise ErroRolagem(f'No máximo {MAX_DADOS_NA_ROLAGEM} dados de uma vez.')
    if abs(mod) > MAX_MODIFICADOR:
        raise ErroRolagem(f'O modificador vai de -{MAX_MODIFICADOR} a +{MAX_MODIFICADOR}.')
    return grupos, mod


def expressao_de(dados):
    """Monta a expressão a partir do pedido dos BOTÕES: {'grupos': [{'dado': 'd6', 'qtd': 2}, ...], 'mod': 3}. Cada dado é conferido contra a lista fechada
    e o tipo repetido soma; o resultado ("2d6+1d20+3") passa pelo mesmo leitor da expressão escrita. (Aceita também o formato antigo de um grupo só:
    {'dado', 'qtd', 'mod', 'modo'} com `modo` normal | vantagem | desvantagem.)"""
    if 'grupos' not in dados:
        dado = dados.get('dado')
        if dado not in DADOS:
            raise ErroRolagem('Dado inválido.')
        try:
            qtd = int(dados.get('qtd') or 1)
            mod = int(dados.get('mod') or 0)
        except (TypeError, ValueError):
            raise ErroRolagem('Quantidade ou modificador inválido.')
        modo = dados.get('modo') or 'normal'
        if modo not in ('normal', 'vantagem', 'desvantagem'):
            raise ErroRolagem('Modo inválido.')
        corpo = f'{max(1, qtd)}{dado}'
        if modo != 'normal':
            corpo = f'2{dado}' + ('kh1' if modo == 'vantagem' else 'kl1')
        return corpo + (f'{mod:+d}' if mod else '')
    grupos = dados.get('grupos')
    if not isinstance(grupos, list) or not grupos:
        raise ErroRolagem('Escolha pelo menos um dado.')
    if len(grupos) > MAX_GRUPOS:
        raise ErroRolagem('Dados demais de tipos diferentes.')
    somados = {}
    for g in grupos:
        if not isinstance(g, dict) or g.get('dado') not in DADOS:
            raise ErroRolagem('Dado inválido.')
        try:
            qtd = 1 if g.get('qtd') is None else int(g['qtd'])          # sem quantidade = 1; zero e negativo são recusados (nada de "0 dados" virar 1)
        except (TypeError, ValueError, OverflowError):
            raise ErroRolagem('Quantidade de dados inválida.')
        if qtd < 1:
            raise ErroRolagem('Quantidade de dados inválida.')
        somados[g['dado']] = somados.get(g['dado'], 0) + qtd
    try:
        mod = int(dados.get('mod') or 0)
    except (TypeError, ValueError, OverflowError):
        raise ErroRolagem('Modificador inválido.')
    corpo = '+'.join(f'{q}{d}' for d, q in somados.items())
    return corpo + (f'{mod:+d}' if mod else '')


def rolar_grupos(grupos, mod):
    """Rola de verdade (SystemRandom). Devolve (total, lista de grupos com os valores e quais ficaram)."""
    saida, soma = [], 0
    for g in grupos:
        lados = DADOS[g['dado']]
        valores = [_alea.randint(1, lados) for _ in range(g['qtd'])]
        mantidos = list(range(len(valores)))
        if g['manter']:
            tipo, n = g['manter']
            ordem = sorted(range(len(valores)), key=lambda k: valores[k], reverse=(tipo == 'kh'))
            mantidos = sorted(ordem[:n])
        subtotal = sum(valores[k] for k in mantidos)
        soma += g['sinal'] * subtotal
        saida.append({'dado': g['dado'], 'valores': valores, 'mantidos': mantidos, 'sinal': g['sinal']})
    return soma + mod, saida


def _entrada(tipo, texto, **extra):
    return {'tipo': tipo, 'texto': texto, 'em': int(time.time()), **extra}


def rolar(dados):
    """O pedido `dados_rolar` -> a ENTRADA do resultado (sem id nem quem: `dados_events.py` põe). Levanta ErroRolagem.
      {'tipo': 'rolagem', 'expr': '2d20kh1+5'}            expressão escrita (gramática fechada)
      {'tipo': 'rolagem', 'grupos': [...], 'mod': 3}      montada pelos botões
      {'tipo': 'moeda', 'qtd': 3}                          cara ou coroa (1 a 10 moedas)
      {'tipo': 'sorteio', ...}                             decidido por `dados_events.py` (precisa de quem está na call)"""
    tipo = dados.get('tipo') or 'rolagem'
    if tipo == 'moeda':
        try:
            qtd = max(1, min(MAX_MOEDAS, int(dados.get('qtd') or 1)))
        except (TypeError, ValueError, OverflowError):
            raise ErroRolagem('Quantidade de moedas inválida.')
        faces = [_alea.choice(('Cara', 'Coroa')) for _ in range(qtd)]
        if qtd == 1:
            return _entrada('moeda', faces[0], moedas=faces)
        caras = faces.count('Cara')
        return _entrada('moeda', f'{caras} {"cara" if caras == 1 else "caras"} e {qtd - caras} {"coroa" if qtd - caras == 1 else "coroas"}', moedas=faces)
    if tipo != 'rolagem':
        raise ErroRolagem('Pedido inválido.')
    expr = re.sub(r'\s+', '', str(dados['expr'])).lower() if 'expr' in dados else expressao_de(dados)
    grupos, mod = ler_expressao(expr)
    total, detalhe = rolar_grupos(grupos, mod)
    return _entrada('rolagem', str(total), expr=expr, grupos=detalhe, mod=mod, total=total)


def sortear(nomes):
    """Sorteia um nome da lista (quem está na call). Levanta ErroRolagem se não há ninguém."""
    nomes = [n for n in nomes if n]
    if not nomes:
        raise ErroRolagem('Não tem ninguém pra sortear: entre numa call.')
    return _entrada('sorteio', _alea.choice(nomes))


def detalhe_dados(e):
    """Os dados de uma rolagem em uma linha curta: "[3, 5] + 2" (o que ficou de fora numa vantagem não aparece)."""
    partes = []
    for i, g in enumerate(e['grupos']):
        vals = ', '.join(str(g['valores'][k]) for k in g['mantidos'])
        sinal = '- ' if g['sinal'] < 0 else ('+ ' if i else '')
        partes.append(f'{sinal}[{vals}]')
    txt = ' '.join(partes)
    mod = e.get('mod') or 0
    return txt + (f' {"+" if mod > 0 else "-"} {abs(mod)}' if mod else '')


_RE_MARCAS = re.compile(r'[*_`~|>\[\]<]')


def texto_para_canal(nome, e):
    """A mensagem de chat de uma rolagem PÚBLICA (o markdown do app deixa o resultado em negrito e a expressão em código). Nomes não levam marcação."""
    quem = _RE_MARCAS.sub('', nome or 'Alguém')[:32].strip() or 'Alguém'
    if e['tipo'] == 'moeda':
        return f'🪙 **{quem}** jogou {"a moeda" if len(e["moedas"]) == 1 else str(len(e["moedas"])) + " moedas"}: **{e["texto"]}**'
    if e['tipo'] == 'sorteio':
        return f'🎯 **{quem}** sorteou: **{_RE_MARCAS.sub("", e["texto"])[:32]}**'
    return f'🎲 **{quem}** rolou `{e["expr"]}`: {detalhe_dados(e)} = **{e["texto"]}**'
