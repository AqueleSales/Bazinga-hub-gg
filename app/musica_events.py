"""Eventos de Socket.IO da Música (a regra mora em musica.py).

`musica_estado` -> `musica_estado` (a pesquisa está ligada? quantas buscas a pessoa ainda tem hoje) e `musica_buscar` -> `musica_resultados` / `musica_erro`.
O que a pessoa digita pode ser uma PESQUISA ou um LINK do YouTube/YouTube Music (música ou playlist): link não gasta cota. A fila de tocar fica no navegador
da própria pessoa (é dela e some junto com a aba); o que vale pra todo mundo ver (a playlist do perfil) mora nas Conexões (`fila_adicionar`).
Erro de regra volta como `musica_erro`; erro inesperado como `erro_bazinga` (regra 3). Sem login, nada responde.
"""
import re
import time

from flask_socketio import emit

from . import socketio, musica
from .musica import ErroMusica
from .events import usuario_logado

_ultimo = {}


def _freio(usuario, chave, intervalo):
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


def _dict(dados):
    return dados if isinstance(dados, dict) else {}                      # um cliente adulterado pode mandar texto/lista em vez do objeto


def _tag(dados):
    """Etiqueta que o cliente manda pra reconhecer a resposta da SUA pesquisa (a resposta de uma pesquisa antiga é ignorada lá). Só letras/números."""
    return re.sub(r'[^\w-]', '', str(_dict(dados).get('tag') or ''))[:40]


@socketio.on('musica_estado')
def musica_estado(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    emit('musica_estado', musica.estado_para(usuario.id))


@socketio.on('musica_buscar')
def musica_buscar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    dados = _dict(dados)
    tag = _tag(dados)
    if _freio(usuario, 'buscar', 1.2):
        emit('musica_erro', {'msg': 'Calma: espere um instante e pesquise de novo.', 'tag': tag})
        return
    texto = str(dados.get('q') or '').strip()[:300]
    try:
        if musica.parece_link(texto):
            r = musica.resolver_link(texto)
            emit('musica_resultados', {'tag': tag, 'q': '', 'itens': r['itens'], 'origem': 'playlist' if r['playlist'] else 'link', 'cache': False,
                                       'restantes': musica.restantes_pessoa(usuario.id)})
        else:
            r = musica.buscar(usuario.id, texto, dados.get('so_musica') is not False)
            emit('musica_resultados', {'tag': tag, 'q': texto[:musica.MAX_CONSULTA], 'itens': r['itens'], 'origem': 'busca', 'cache': r['cache'],
                                       'restantes': musica.restantes_pessoa(usuario.id)})
    except ErroMusica as e:
        emit('musica_erro', {'msg': str(e), 'tag': tag})
    except Exception as e:
        print(f"[ERRO MUSICA] {type(e).__name__}: {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível pesquisar a música: {e}'})
        emit('musica_erro', {'msg': 'Não consegui pesquisar agora. Tente de novo.', 'tag': tag})
