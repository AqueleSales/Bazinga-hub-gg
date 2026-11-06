"""Call híbrida (Rodada 39): o pedido de TOKEN do SFU e o aviso de "esta call mudou de transporte". Veja `app/sfu.py` e `docs/PLANO_SFU.md`.

Quem decide é o servidor: só quem está DE VERDADE nessa call recebe token, a sala vem da chave da call (nunca do que o cliente escreve), o ouvinte do palco
recebe um token que não publica, e num canal de stream só o apresentador recebe a permissão de transmitir tela. Nada daqui roda sem `CALL_MODE` + LIVEKIT_*."""
import time

from flask import request

from . import socketio, sfu
from .seguranca import emit
from .events import usuario_logado, participantes_call, _call_por_sid, _meta_call

ESPERA_TOKEN_S = 2.0
_ultimo = {}                   # usuario_id -> hora do último token (freio: o token é barato, mas não há motivo pra pedir em rajada)


def _quantos(chave):
    return len({p['usuario_id'] for p in participantes_call.get(chave, [])})


def ao_entrar_na_call(chave):
    """Gancho do `entrar_call`: a call passou do limite do P2P? Todo mundo da sala é avisado UMA vez (o cliente sem adaptador ignora)."""
    try:
        transporte, mudou = sfu.ao_entrar(chave, _quantos(chave), dm=str(chave).startswith('dm_'))
        if mudou:
            socketio.emit('call_transporte', {'canal_id': str(chave), 'transporte': transporte}, to=f'voz_{chave}')
        return transporte
    except Exception as e:
        print(f"[ERRO SFU AO ENTRAR] {e}")
        return 'p2p'


def ao_sair_da_call(chave):
    try:
        sfu.ao_sair(chave, _quantos(chave))
    except Exception as e:
        print(f"[ERRO SFU AO SAIR] {e}")


@socketio.on('sfu_pedir_token')
def sfu_pedir_token(dados=None):
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    chave = str(dados.get('canal_id'))
    if not sfu.ativo():
        emit('sfu_token', {'ok': False, 'canal_id': chave, 'motivo': 'desligado'})
        return
    atual = _call_por_sid.get(request.sid)
    meta = _meta_call.get(atual) if atual else None
    if not atual or atual[0] != chave or not meta or meta['usuario_id'] != usuario.id:
        emit('sfu_token', {'ok': False, 'canal_id': chave, 'motivo': 'fora_da_call'})           # só quem está nessa call recebe a chave da sala dela
        return
    if sfu.transporte_da_call(chave) != 'sfu':
        emit('sfu_token', {'ok': False, 'canal_id': chave, 'motivo': 'p2p'})                    # esta call ainda é (ou sempre será) P2P
        return
    agora = time.time()
    if agora - _ultimo.get(usuario.id, 0) < ESPERA_TOKEN_S:
        emit('sfu_token', {'ok': False, 'canal_id': chave, 'motivo': 'calma'})
        return
    _ultimo[usuario.id] = agora
    if len(_ultimo) > 500:
        for k in [k for k, v in _ultimo.items() if agora - v > 60]:
            _ultimo.pop(k, None)
    try:
        eu = next((p for p in participantes_call.get(chave, []) if p['peer_id'] == atual[1]), None) or {}
        publicar = not eu.get('ouvinte')
        tela = publicar
        from . import stream_events
        if stream_events._canal_stream(chave):                                                  # canal de transmissão: só o apresentador manda tela
            ap = stream_events.apresentador_de(chave)
            tela = bool(publicar and ap and ap['usuario_id'] == usuario.id)
        token = sfu.emitir_token(usuario.id, usuario.name, chave, publicar=publicar, tela=tela)
        emit('sfu_token', {'ok': True, 'canal_id': chave, 'url': sfu.url_publica(), 'token': token, 'sala': sfu.sala_do_sfu(chave),
                           'identidade': f'u{usuario.id}', 'expira_em': sfu.TOKEN_TTL_S, 'publica': publicar, 'tela': tela})
    except Exception as e:
        print(f"[ERRO SFU TOKEN] {type(e).__name__}")                                           # nunca imprime o texto: poderia citar a configuração
        emit('sfu_token', {'ok': False, 'canal_id': chave, 'motivo': 'erro'})
