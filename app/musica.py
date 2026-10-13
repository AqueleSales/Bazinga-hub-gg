"""Música (Rodada 25, parte B): pesquisar música e tocar dentro do Pantheon, sem sair do app.

Como funciona e por que é assim:
  * O YouTube Music NÃO tem API oficial (as bibliotecas "não oficiais" usam o cookie da conta da pessoa e violam os termos do Google). O que existe de oficial é o
    YouTube: a API de dados (pesquisa) e o player embutido (iframe). Então a pesquisa aqui é a do YouTube e o som vem do player oficial, SEMPRE visível (os termos
    do player proíbem esconder o vídeo e tocar só o áudio). Quase tudo do YouTube Music é um vídeo do YouTube, então a pessoa acha o que procura.
  * A chave da API (`YOUTUBE_API_KEY`, ambiente do Render) fica SÓ no servidor e vai num cabeçalho (nunca na URL, que pode aparecer em erro/log).
  * **Cota**: o projeto tem 10.000 unidades por dia; cada pesquisa custa 100 (+1 da leitura de duração/embed) e abrir playlist por link custa ~2. Defesas:
    cache de 12 h por texto pesquisado (repetir não gasta nada), teto de unidades do app inteiro (`YOUTUBE_UNIDADES_DIA`, padrão 9.500 pra sobrar margem),
    teto por pessoa por dia e bloqueio temporário quando o Google responde 403/429/400. O dia da cota vira à meia-noite do horário do Pacífico.
  * Colar o LINK de uma música não gasta cota (oEmbed público): continua funcionando quando a pesquisa estiver sem cota ou desligada.
  * Só entra resultado que pode tocar fora do youtube.com (`videoEmbeddable`/`videoSyndicated` e `status.embeddable` conferido de novo na leitura de duração).
  * O que vem do YouTube é texto não confiável: entidades HTML desfeitas, caracteres de controle fora, tamanho limitado; o cliente ainda passa por esc().
Toda chamada de rede passa por `importar.baixar_texto` (anti-SSRF), como as Conexões.
"""
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import quote, urlencode

from . import importar
from .conexoes import ErroConexao, faixa_de_link, _limpo, _RE_YT_ID
from .importar import ErroImportar

API = 'https://www.googleapis.com/youtube/v3'
CUSTO_BUSCA = 100                  # unidades de cota por search.list
CUSTO_LEITURA = 1                  # videos.list / playlistItems.list
TTL_CACHE = 12 * 3600
MAX_CACHE = 400
MAX_RESULTADOS = 25
MAX_PLAYLIST = 50
MAX_BUSCAS_PESSOA_DIA = 30
MAX_CONSULTA = 80

try:
    from zoneinfo import ZoneInfo
    _PACIFICO = ZoneInfo('America/Los_Angeles')
except Exception:                  # sem banco de fusos (Windows sem tzdata): usa o horário de inverno do Pacífico
    _PACIFICO = timezone(timedelta(hours=-8))

_RE_LINK = re.compile(r'^\s*(?:https?://|www\.|(?:music\.)?youtube\.com|youtu\.be)', re.I)
_RE_DURACAO = re.compile(r'^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$')

_vagas = threading.BoundedSemaphore(4)
_trava = threading.Lock()
_cache = {}                        # (consulta, so_musica) -> (instante, itens)
_estado = {'dia': None, 'unidades': 0, 'bloqueado_ate': 0.0}
_por_pessoa = {}                   # pessoa_id -> [dia, buscas]


MSG_PLAYLIST = 'Não consegui abrir essa playlist. Só funcionam as públicas ou não listadas (as suas curtidas e os mixes automáticos ficam de fora).'


class ErroMusica(Exception):
    """Erro que a pessoa pode ler (já em português)."""


def chave():
    return (os.environ.get('YOUTUBE_API_KEY') or '').strip()


def disponivel():
    return bool(chave())


def parece_link(texto):
    return bool(_RE_LINK.match(texto or ''))


def _dia():
    return datetime.now(_PACIFICO).date().isoformat()


def _virar_dia():
    dia = _dia()
    if _estado['dia'] != dia:
        _estado.update(dia=dia, unidades=0)
        _por_pessoa.clear()
    return dia


def _limite_unidades():
    try:
        return max(0, int(os.environ.get('YOUTUBE_UNIDADES_DIA', '9500')))
    except ValueError:
        return 9500


def unidades_hoje():
    with _trava:
        _virar_dia()
        return _estado['unidades']


def _gastar(unidades):
    with _trava:
        _virar_dia()
        _estado['unidades'] += unidades


def restantes_pessoa(pessoa_id):
    with _trava:
        dia = _virar_dia()
        d = _por_pessoa.get(pessoa_id)
        usadas = d[1] if d and d[0] == dia else 0
    return max(0, MAX_BUSCAS_PESSOA_DIA - usadas)


def _bloquear(segundos):
    with _trava:
        _estado['bloqueado_ate'] = max(_estado['bloqueado_ate'], time.time() + segundos)


def _liberar_ou_levantar(pessoa_id, custo):
    """Confere (e reserva) o direito de gastar `custo` unidades numa pesquisa nova. Levanta ErroMusica com a razão."""
    with _trava:
        dia = _virar_dia()
        if time.time() < _estado['bloqueado_ate']:
            raise ErroMusica('A pesquisa de músicas está indisponível agora. Tente de novo mais tarde ou cole o link de uma música do YouTube.')
        if _estado['unidades'] + custo + CUSTO_LEITURA > _limite_unidades():         # (+ a leitura de duração que vem junto)
            raise ErroMusica('As pesquisas de hoje acabaram (o YouTube limita por dia). Volte amanhã, ou cole o link de uma música do YouTube.')
        d = _por_pessoa.get(pessoa_id)
        if not d or d[0] != dia:
            d = _por_pessoa[pessoa_id] = [dia, 0]
        if d[1] >= MAX_BUSCAS_PESSOA_DIA:
            raise ErroMusica(f'Você já fez as {MAX_BUSCAS_PESSOA_DIA} pesquisas de hoje. Amanhã tem mais (ou cole o link de uma música do YouTube).')
        d[1] += 1
        _estado['unidades'] += custo


def segundos_da_duracao(texto):
    """'PT3M33S' -> 213. Transmissão ao vivo ('P0D') e lixo -> None."""
    m = _RE_DURACAO.match(texto or '')
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    total = d * 86400 + h * 3600 + mi * 60 + s
    return total if total > 0 else None


def _consulta(texto):
    return re.sub(r'\s+', ' ', re.sub(r'[\x00-\x1f\x7f]', ' ', str(texto or ''))).strip()[:MAX_CONSULTA]


def _chamar(rota, params, custo, msg404=None):
    """Uma chamada à API do YouTube (a chave vai no cabeçalho). Devolve o JSON; levanta ErroMusica. Status do Google: 400 = chave inválida, 403 = cota
    estourada/chave restrita/API desligada, 429 = devagar."""
    if not chave():
        raise ErroMusica('A pesquisa de músicas ainda não foi ligada neste servidor.')
    url = f'{API}/{rota}?{urlencode(params)}'
    try:
        st, _tp, txt, _ = importar.baixar_texto(url, aceita='application/json', extra={'x-goog-api-key': chave()})
    except ErroImportar:
        raise ErroMusica('O YouTube não respondeu agora. Tente de novo daqui a pouco.')
    if st == 200:
        try:
            j = json.loads(txt)
        except ValueError:
            raise ErroMusica('A resposta do YouTube veio estranha. Tente de novo.')
        if isinstance(j, dict):
            return j
        raise ErroMusica('A resposta do YouTube veio estranha. Tente de novo.')
    print(f'[MUSICA] a API do YouTube respondeu {st} em {rota}')
    if st == 400:
        _bloquear(3600)
    elif st == 403:
        _bloquear(1800)
    elif st == 429:
        _bloquear(300)
    if st == 404 and msg404:
        raise ErroMusica(msg404)
    if st in (400, 403, 429):
        raise ErroMusica('A pesquisa de músicas está indisponível agora. Tente de novo mais tarde ou cole o link de uma música do YouTube.')
    raise ErroMusica('O YouTube respondeu com erro. Tente de novo mais tarde.')


def _item(vid, titulo, autor, duracao=None):
    return {'v': vid, 't': _limpo(unescape(str(titulo or '')), 100) or 'Sem título', 'a': _limpo(unescape(str(autor or '')), 60), 'd': duracao}


def _completar(itens):
    """Duração e conferência final de embed (1 unidade pra até 50 vídeos). Se falhar, devolve sem duração (não derruba a pesquisa)."""
    if not itens:
        return itens
    try:
        j = _chamar('videos', {'part': 'contentDetails,status', 'id': ','.join(i['v'] for i in itens[:MAX_PLAYLIST]), 'maxResults': MAX_PLAYLIST,
                               'fields': 'items(id,contentDetails/duration,status/embeddable)'}, CUSTO_LEITURA)
    except ErroMusica:
        return itens
    _gastar(CUSTO_LEITURA)
    info = {}
    for x in j.get('items') or []:
        if isinstance(x, dict) and isinstance(x.get('id'), str):
            info[x['id']] = x
    saida = []
    for i in itens:
        x = info.get(i['v'])
        if x is not None:
            if (x.get('status') or {}).get('embeddable') is False:
                continue
            i['d'] = segundos_da_duracao((x.get('contentDetails') or {}).get('duration'))
        saida.append(i)
    return saida


def _pesquisar_api(consulta, so_musica):
    params = {'part': 'snippet', 'type': 'video', 'maxResults': MAX_RESULTADOS, 'q': consulta, 'videoEmbeddable': 'true', 'videoSyndicated': 'true',
              'safeSearch': 'moderate', 'regionCode': 'BR', 'relevanceLanguage': 'pt', 'fields': 'items(id/videoId,snippet(title,channelTitle))'}
    if so_musica:
        params['videoCategoryId'] = '10'
    j = _chamar('search', params, CUSTO_BUSCA)
    itens = []
    for x in j.get('items') or []:
        if not isinstance(x, dict):
            continue
        vid = (x.get('id') or {}).get('videoId') if isinstance(x.get('id'), dict) else None
        if not isinstance(vid, str) or not _RE_YT_ID.match(vid):
            continue
        sn = x.get('snippet') if isinstance(x.get('snippet'), dict) else {}
        itens.append(_item(vid, sn.get('title'), sn.get('channelTitle')))
    return _completar(itens)


def _guardar_cache(chave_cache, itens):
    with _trava:
        if len(_cache) >= MAX_CACHE:
            for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][0])[:MAX_CACHE // 4]:
                _cache.pop(k, None)
        _cache[chave_cache] = (time.time(), itens)


def buscar(pessoa_id, texto, so_musica=True):
    """Pesquisa por texto. Devolve {'itens': [...], 'cache': bool}. Repetir a mesma pesquisa (12 h) não gasta cota nem conta no limite da pessoa."""
    consulta = _consulta(texto)
    if len(consulta) < 2:
        raise ErroMusica('Digite pelo menos 2 letras pra pesquisar.')
    k = (consulta.lower(), bool(so_musica))
    with _trava:
        achou = _cache.get(k)
    if achou and time.time() - achou[0] < TTL_CACHE:
        return {'itens': [dict(i) for i in achou[1]], 'cache': True}
    if not chave():
        raise ErroMusica('A pesquisa de músicas ainda não foi ligada neste servidor. Você pode colar o link de uma música do YouTube.')
    _liberar_ou_levantar(pessoa_id, CUSTO_BUSCA)
    with _vagas:
        itens = _pesquisar_api(consulta, so_musica)
    _guardar_cache(k, itens)
    return {'itens': [dict(i) for i in itens], 'cache': False}


def _oembed(vid):
    url = f'https://www.youtube.com/oembed?format=json&url=' + quote(f'https://www.youtube.com/watch?v={vid}', safe='')
    try:
        st, _tp, txt, _ = importar.baixar_texto(url, aceita='application/json')
    except ErroImportar:
        raise ErroMusica('O YouTube não respondeu agora. Tente de novo daqui a pouco.')
    if st in (400, 401, 404):
        raise ErroMusica('Esse vídeo não existe, é privado ou o dono não deixa tocar fora do YouTube.')
    if st != 200:
        raise ErroMusica('O YouTube respondeu com erro. Tente de novo mais tarde.')
    try:
        j = json.loads(txt)
    except ValueError:
        raise ErroMusica('A resposta do YouTube veio estranha. Tente de novo.')
    if not isinstance(j, dict):
        raise ErroMusica('A resposta do YouTube veio estranha. Tente de novo.')
    return _item(vid, j.get('title'), j.get('author_name'))


def _faixas_da_playlist(lista_id):
    """Até 50 músicas de uma playlist pública/não listada (1 unidade). Vídeo privado/apagado fica de fora."""
    j = _chamar('playlistItems', {'part': 'snippet', 'playlistId': lista_id, 'maxResults': MAX_PLAYLIST,
                                  'fields': 'items(snippet(title,videoOwnerChannelTitle,resourceId/videoId))'}, CUSTO_LEITURA, msg404=MSG_PLAYLIST)
    _gastar(CUSTO_LEITURA)
    itens = []
    for x in j.get('items') or []:
        sn = x.get('snippet') if isinstance(x, dict) and isinstance(x.get('snippet'), dict) else {}
        vid = (sn.get('resourceId') or {}).get('videoId') if isinstance(sn.get('resourceId'), dict) else None
        titulo = str(sn.get('title') or '')
        if not isinstance(vid, str) or not _RE_YT_ID.match(vid) or titulo.strip().lower() in ('private video', 'deleted video', 'vídeo privado', 'vídeo excluído'):
            continue
        itens.append(_item(vid, titulo, re.sub(r' - Topic$', '', str(sn.get('videoOwnerChannelTitle') or ''))))
    return _completar(itens)


def resolver_link(texto):
    """Link de música (oEmbed: sem cota, sem chave) ou de playlist (precisa da chave; 1-2 unidades). Devolve {'itens': [...], 'playlist': bool}."""
    try:
        f = faixa_de_link(str(texto or '').strip())
    except ErroConexao as e:
        raise ErroMusica(str(e))
    if f.get('v'):
        return {'itens': [_oembed(f['v'])], 'playlist': False}
    if not chave():
        raise ErroMusica('Abrir uma playlist por link precisa da pesquisa ligada neste servidor. Cole o link de uma música.')
    with _trava:
        if time.time() < _estado['bloqueado_ate']:
            raise ErroMusica('A pesquisa de músicas está indisponível agora. Tente de novo mais tarde ou cole o link de uma música do YouTube.')
    with _vagas:
        itens = _faixas_da_playlist(f['l'])
    if not itens:
        raise ErroMusica(MSG_PLAYLIST)
    return {'itens': itens, 'playlist': True}


def estado_para(pessoa_id):
    return {'disponivel': disponivel(), 'restantes': restantes_pessoa(pessoa_id)}
