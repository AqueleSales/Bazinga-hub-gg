"""Canal de STREAM (tipo `stream`, Rodada 39): uma voz com chat ao lado, onde UMA pessoa por vez transmite a tela e o resto assiste e conversa.

Quem pode transmitir é decidido aqui, no servidor (regra 4):
  * `stream_pedir_tela {canal_id}`: só quem está de verdade na call desse canal e não está de ouvinte. Se já tem alguém transmitindo, é negado e a
    resposta diz quem é. Se pode, vira o APRESENTADOR e todo mundo da call recebe `stream_apresentador` (com o `peer_id`, que é como o cliente sabe de quem
    aceitar a tela). A prévia de fora da call (lista do servidor) só recebe o nome.
  * `stream_liberar_tela {canal_id, forcar?}`: o próprio apresentador solta; quem gerencia canais (ou o dono) pode tirar o apresentador do ar com `forcar`
    (ele recebe `stream_tela_cortada` e o cliente dele para de transmitir).
  * O apresentador sai sozinho quando sai da call, cai da rede (depois da graça de reconexão) ou a call esvazia (`ao_sair_da_call`, chamado por events._tirar_da_call).
Limite assumido: o vídeo da call é P2P, então o servidor não corta a mídia; os clientes é que ignoram tela de quem não é o apresentador
(trava leve, igual ao ouvinte do palco). O que o servidor garante é a vez e o aviso a todos.
"""
from flask import request

from .seguranca import emit
from . import socketio, cargos
from .models import db, Channel, Server
from .events import usuario_logado, _call_por_sid, _meta_call, participantes_call, _destinos_da_call, com_retry

_apresentador = {}        # chave da call -> {'usuario_id', 'nome', 'peer_id', 'server_id', 'sid'}


def apresentador_de(chave):
    return _apresentador.get(str(chave))


def _publico(chave, ap):
    return {'canal_id': chave, 'usuario_id': ap['usuario_id'], 'nome': ap['nome']} if ap else {'canal_id': chave, 'usuario_id': None}


def _avisar(chave):
    """Diz a todos quem está transmitindo (só com apresentador: pra liberar a vez o aviso é montado à parte)."""
    ap = _apresentador.get(chave)
    if not ap:
        return
    socketio.emit('stream_apresentador', dict(_publico(chave, ap), peer_id=ap['peer_id']), to=f"voz_{chave}")   # na call: com o peer_id (é por ele que aceita a tela)
    for sala in _destinos_da_call(chave, ap['server_id']):                                                    # só olhando o servidor: só o nome
        socketio.emit('stream_apresentador', _publico(chave, ap), to=sala)


def avisar_quem_chegou(chave):
    """Quem entra no meio de uma transmissão recebe quem é o apresentador (vai pra sala inteira: barato e idempotente no cliente)."""
    if _apresentador.get(chave):
        _avisar(chave)


def ao_sair_da_call(chave, usuario_id):
    """O apresentador saiu (ou a call esvaziou): libera a vez e avisa. Chamado por events._tirar_da_call; nunca quebra quem chamou."""
    try:
        ap = _apresentador.get(chave)
        if not ap:
            return
        if ap['usuario_id'] == usuario_id or chave not in participantes_call:
            server_id = ap['server_id']
            _apresentador.pop(chave, None)
            socketio.emit('stream_apresentador', _publico(chave, None), to=f"voz_{chave}")
            for sala in _destinos_da_call(chave, server_id):
                socketio.emit('stream_apresentador', _publico(chave, None), to=sala)
    except Exception as e:
        print(f"[ERRO STREAM AO SAIR] {e}")


def _canal_stream(chave):
    try:
        canal = com_retry(lambda: Channel.query.get(int(chave)))
    except (TypeError, ValueError):
        return None
    return canal if canal and canal.channel_type == 'stream' and canal.server_id is not None else None


@socketio.on('stream_pedir_tela')
def stream_pedir_tela(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    d = dados if isinstance(dados, dict) else {}
    chave = str(d.get('canal_id'))
    try:
        minha = _call_por_sid.get(request.sid)
        if not minha or minha[0] != chave:
            emit('stream_tela_negada', {'canal_id': chave, 'motivo': 'Você precisa estar na call deste canal pra transmitir.'})
            return
        canal = _canal_stream(chave)
        if not canal:
            emit('stream_tela_negada', {'canal_id': chave, 'motivo': 'Este canal não é de transmissão.'})
            return
        eu = next((p for p in participantes_call.get(chave, []) if p['peer_id'] == minha[1]), None)
        if not eu or eu.get('ouvinte'):
            emit('stream_tela_negada', {'canal_id': chave, 'motivo': 'Você está só ouvindo neste canal (sem a permissão de falar), então não pode transmitir.'})
            return
        atual = _apresentador.get(chave)
        if atual and atual['usuario_id'] != usuario.id:
            emit('stream_tela_negada', {'canal_id': chave, 'motivo': f"{atual['nome']} já está transmitindo. Espere ele terminar.", 'por': atual['nome']})
            return
        _apresentador[chave] = {'usuario_id': usuario.id, 'nome': usuario.name, 'peer_id': minha[1], 'server_id': canal.server_id, 'sid': request.sid}
        emit('stream_tela_ok', {'canal_id': chave})
        _avisar(chave)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO STREAM PEDIR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível pedir a vez de transmitir: {e}'})


@socketio.on('stream_liberar_tela')
def stream_liberar_tela(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    d = dados if isinstance(dados, dict) else {}
    chave = str(d.get('canal_id'))
    try:
        ap = _apresentador.get(chave)
        if not ap:
            return
        if ap['usuario_id'] != usuario.id:
            # tirar OUTRA pessoa do ar: só com permissão de gerenciar canais (o dono sempre pode) e estando na call
            minha = _call_por_sid.get(request.sid)
            canal = _canal_stream(chave)
            srv = com_retry(lambda: Server.query.get(canal.server_id)) if canal else None
            if not d.get('forcar') or not minha or minha[0] != chave or not srv or not cargos.pode(usuario, srv, 'gerenciar_canais'):
                return
            socketio.emit('stream_tela_cortada', {'canal_id': chave, 'por': usuario.name}, to=ap['sid'])
        _apresentador.pop(chave, None)
        socketio.emit('stream_apresentador', _publico(chave, None), to=f"voz_{chave}")
        for sala in _destinos_da_call(chave, ap['server_id']):
            socketio.emit('stream_apresentador', _publico(chave, None), to=sala)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO STREAM LIBERAR] {e}")
