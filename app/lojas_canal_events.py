"""Eventos de Socket.IO do canal de lojas (a regra mora em lojas_canal.py).

`lojas_canal_pedir {canal_id, busca, categoria, origem, seed}` -> `lojas_canal` (só pra quem pediu). A permissão é conferida no servidor a cada pedido
(regra 4): o canal precisa ser do tipo `lojas` e a pessoa precisa poder vê-lo. Regra 6: não há escrita aqui; a vitrine muda quando o Bazar muda
(`bazar_mudou`, que já vai a todo mundo) e quando alguém entra/sai do servidor (`membro_entrou_servidor`): o cliente com o canal aberto pede de novo.
Erro de regra volta como `lojas_canal_erro`; erro inesperado como `erro_bazinga` (regra 3).
"""
import time

from .seguranca import emit

from . import socketio, lojas_canal
from .models import db
from .utils import canal_permitido
from .events import usuario_logado

_ultimo = {}


def _freio(usuario, intervalo=0.4):
    agora = time.monotonic()
    if agora - _ultimo.get(usuario.id, 0) < intervalo:
        return True
    _ultimo[usuario.id] = agora
    return False


@socketio.on('lojas_canal_pedir')
def lojas_canal_pedir(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario):
        return
    d = dados if isinstance(dados, dict) else {}
    try:
        canal = canal_permitido(usuario, d.get('canal_id'))
        if not canal or canal.channel_type != 'lojas' or canal.server_id is None:
            emit('lojas_canal_erro', {'msg': 'Esse canal de lojas não está disponível pra você.', 'canal_id': d.get('canal_id')})
            return
        emit('lojas_canal', lojas_canal.listar(canal, str(d.get('busca') or '')[:40], str(d.get('categoria') or '')[:20],
                                               str(d.get('origem') or 'todas')[:12], str(d.get('seed') or '')[:20]))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LOJAS CANAL] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível abrir a vitrine de lojas: {e}'})
