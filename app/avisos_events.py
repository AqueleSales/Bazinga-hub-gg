"""Tempo real dos avisos de canal (Rodada 39). Regra em avisos.py.

* `canal_atividade` (servidor -> cliente): "chegou mensagem nova no canal X do servidor Y". Vai só pra quem enxerga o canal
  (canal público = sala do servidor; privado ou com permissão por cargo = uma pessoa por vez, depois de conferir). Não leva texto:
  só o suficiente pra acender a bolinha. Quem está com o canal aberto marca como lido de volta.
* `canal_lido` (cliente -> servidor): a pessoa abriu/leu o canal. Volta como `canal_lido` pras OUTRAS abas e aparelhos dela (regra 6).
"""
from .seguranca import emit
from . import avisos
from .events import socketio, usuario_logado, sala_pessoal, sala_servidor, com_retry, canal_permitido, pode_ver_canal, Server
from .models import db


def avisar_atividade(autor, canal, msg):
    """Chamado depois que a mensagem foi salva e entregue. Nunca quebra o envio."""
    try:
        if canal.server_id is None:
            return
        carga = {'server_id': canal.server_id, 'canal_id': canal.id, 'canal_nome': canal.name,
                 'msg_id': msg.id, 'autor_id': autor.id}
        if canal.is_private or canal.sobrescrita:
            srv = Server.query.get(canal.server_id)
            for membro in srv.members:
                if membro.id != autor.id and pode_ver_canal(membro, canal):
                    emit('canal_atividade', carga, to=sala_pessoal(membro.id))
        else:
            emit('canal_atividade', carga, to=sala_servidor(canal.server_id), include_self=False)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO AVISO CANAL] {e}")


@socketio.on('canal_lido')
def canal_lido(dados=None):
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    try:
        canal = canal_permitido(usuario, dados.get('canal_id'))
        if not canal or canal.server_id is None:
            return
        com_retry(lambda: avisos.marcar_lido(usuario.id, canal))
        emit('canal_lido', {'canal_id': canal.id, 'server_id': canal.server_id}, to=sala_pessoal(usuario.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CANAL LIDO] {e}")
