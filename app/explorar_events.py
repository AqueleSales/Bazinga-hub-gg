"""Eventos de Socket.IO do Explorar servidores (a regra mora em explorar.py).

Regra 6: quem entra num servidor público recebe o servidor em TODAS as abas dele (`sala_pessoal`) e os membros que já estavam lá são avisados
(`membro_entrou_servidor`). Dono que publica/despublica o servidor avisa os membros (o servidor volta com o novo estado).
Erro de regra volta como `explorar_erro`; erro inesperado como `erro_bazinga` (regra 3).
"""
import time

from flask_socketio import emit, join_room

from . import socketio, explorar
from .explorar import ErroExplorar
from .models import db
from .utils import com_retry, servidor_gerenciavel
from .events import (usuario_logado, sala_pessoal, sala_servidor, servidor_para_json, avisar_servidor)

_ultimo = {}


def _freio(usuario, chave, intervalo=0.4):
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


def _seguro(rotulo, fn):
    try:
        fn()
    except ErroExplorar as e:
        db.session.rollback()
        emit('explorar_erro', {'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EXPLORAR {rotulo}] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível {rotulo}: {e}'})


@socketio.on('explorar_pedir')
def explorar_pedir(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'pedir'):
        return
    d = dados or {}

    def fazer():
        emit('explorar', explorar.lista(usuario, str(d.get('busca') or '')[:40], str(d.get('tema') or '')[:20], str(d.get('seed') or '')[:20]))
    _seguro('abrir o Explorar', fazer)


@socketio.on('explorar_previa')
def explorar_previa(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'previa', 0.25):
        return
    _seguro('abrir a prévia', lambda: emit('explorar_previa', explorar.previa(usuario, (dados or {}).get('server_id'))))


@socketio.on('explorar_surpresa')
def explorar_surpresa(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'surpresa', 0.6):
        return
    _seguro('sortear um servidor', lambda: emit('explorar_previa', explorar.surpresa(usuario, str((dados or {}).get('tema') or '')[:20])))


@socketio.on('explorar_entrar')
def explorar_entrar(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entrar', 1.0):
        return

    def fazer():
        srv, ja_era = explorar.entrar(usuario, (dados or {}).get('server_id'))
        join_room(sala_servidor(srv.id))
        sala = sala_pessoal(usuario.id)
        emit('servidor_discord_criado', servidor_para_json(srv, usuario), to=sala)       # todas as abas da pessoa
        emit('entrou_por_convite', {'server_id': srv.id, 'server_name': srv.name})        # a aba que clicou abre o servidor
        if not ja_era:
            emit('membro_entrou_servidor', {'server_id': srv.id, 'membro': {'id': usuario.id, 'nome': usuario.name, 'avatar': usuario.avatar}},
                 to=sala_servidor(srv.id), include_self=False)
    _seguro('entrar no servidor', fazer)


@socketio.on('definir_explorar')
def definir_explorar(dados=None):
    """Só o DONO liga/desliga o servidor no Explorar e escolhe o tema."""
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'definir', 0.8):
        return
    d = dados or {}

    def fazer():
        srv = servidor_gerenciavel(usuario, d.get('server_id'))
        if not srv:
            raise ErroExplorar('Só o dono pode mexer nisso.')
        explorar.definir_publico(srv, bool(d.get('publico')), str(d.get('tema') or '')[:20])
        avisar_servidor(srv)
        emit('explorar_definido', {'server_id': srv.id, 'publico': bool(srv.publico), 'tema': srv.tema_explorar})
    _seguro('mudar o Explorar do servidor', fazer)
