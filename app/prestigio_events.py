"""Eventos de Socket.IO do Prestígio (impulso) de servidor (a regra mora em prestigio.py).

Regra 4: quem pode pedir o estado e impulsionar é MEMBRO do servidor (conferido aqui, no servidor); impulsionar também exige a Brasa ativa
(prestigio.impulsionar). O `server_id` vem do cliente, mas só vale se a pessoa é membro.
Regra 6: impulsionou/tirou -> `prestigio_estado` pra TODAS as abas de quem agiu, `prestigio_mudou` pra sala do servidor inteiro (todo membro vê
o novo nível) e, se o servidor está plantado no mapa, o pino é reenviado a quem está dentro do NOVO alcance (e retirado de quem saiu dele).
Erro de regra volta como `prestigio_erro`; erro inesperado como `erro_bazinga` (regra 3).
"""
import time

from flask_socketio import emit

from . import socketio, prestigio
from .prestigio import ErroPrestigio
from .models import db, Server, MapServer, br_now
from .utils import com_retry, eh_membro, distancia_m
from .events import usuario_logado, sala_pessoal, sala_servidor, centros_mapa, _emitir_pino

_ultimo = {}


def _freio(usuario, chave, intervalo=0.5):
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


def _servidor_do_membro(usuario, server_id):
    """O servidor, se ele existe e a pessoa é membro; senão levanta (a mensagem é a mesma pros dois casos: não revela servidor alheio)."""
    try:
        sid = int(server_id)
    except (TypeError, ValueError):
        raise ErroPrestigio('Servidor não encontrado.')
    srv = com_retry(lambda: Server.query.get(sid))
    if not srv or not com_retry(lambda: eh_membro(usuario, srv.id)):
        raise ErroPrestigio('Servidor não encontrado.')
    return srv


def _pino_ativo(srv_id):
    pino = com_retry(lambda: MapServer.query.filter_by(server_id=srv_id).first())
    if not pino or pino.oculta or (pino.expires_at and pino.expires_at <= br_now()):
        return None
    return pino


def _reajustar_mapa(srv, nivel_antes, nivel_depois):
    """O alcance do pino mudou: quem entrou no alcance recebe o pino; quem saiu dele (e está além do raio normal) recebe a retirada."""
    pino = _pino_ativo(srv.id)
    if not pino or nivel_antes == nivel_depois:
        return
    alcance_antes, alcance_depois = prestigio.alcance_m(nivel_antes), prestigio.alcance_m(nivel_depois)
    if alcance_depois >= alcance_antes:
        _emitir_pino('novo_servidor_mapa', pino)        # quem já tem o pino ignora; quem não tinha passa a ver
        _emitir_pino('servidor_mapa_editado', pino)     # quem já tem atualiza o nível no cartão
    else:
        _emitir_pino('servidor_mapa_editado', pino)
        for sid, (la, ln) in list(centros_mapa.items()):
            d = distancia_m(pino.lat, pino.lng, la, ln)
            if alcance_depois < d <= alcance_antes:
                emit('servidor_mapa_apagado', {'id': pino.id}, to=sid)


def _seguro(rotulo, fn):
    try:
        fn()
    except ErroPrestigio as e:
        db.session.rollback()
        emit('prestigio_erro', {'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PRESTIGIO {rotulo}] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível {rotulo}: {e}'})


@socketio.on('prestigio_pedir')
def prestigio_pedir(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'pedir', 0.3):
        return

    def fazer():
        srv = _servidor_do_membro(usuario, (dados or {}).get('server_id'))
        emit('prestigio_estado', prestigio.estado(usuario, srv))
    _seguro('abrir o prestígio do servidor', fazer)


@socketio.on('prestigio_impulsionar')
def prestigio_impulsionar(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'impulsionar', 0.6):
        return
    d = dados or {}

    def fazer():
        srv = _servidor_do_membro(usuario, d.get('server_id'))
        antes = prestigio.info(srv.id)['nivel']
        mudou = prestigio.impulsionar(usuario, srv, bool(d.get('ativo')))
        depois_info = prestigio.info(srv.id)
        emit('prestigio_estado', prestigio.estado(usuario, srv), to=sala_pessoal(usuario.id))
        if not mudou:
            return
        emit('prestigio_mudou', {'server_id': srv.id, 'nivel': depois_info['nivel'], 'nome': depois_info['nome'], 'pontos': depois_info['pontos'],
                                 'impulsos': depois_info['impulsos'], 'alcance_m': depois_info['alcance_m'], 'subiu': depois_info['nivel'] > antes,
                                 'por': usuario.name if d.get('ativo') else None}, to=sala_servidor(srv.id))
        _reajustar_mapa(srv, antes, depois_info['nivel'])
    _seguro('impulsionar o servidor', fazer)
