"""Eventos da Brasa (id interno olimpo; a assinatura, a regra mora em olimpo.py). Ativar de graça enquanto OLIMPO_GRATIS não for 0; senão gera a cobrança Pix."""
import time

from flask_socketio import emit

from . import socketio, olimpo, pagamentos
from .models import db
from .events import usuario_logado, sala_pessoal

_ultimo = {}


def _freio(usuario, chave, intervalo=1.0):
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


@socketio.on('olimpo_estado')
def olimpo_estado(dados=None):
    usuario = usuario_logado()
    if usuario:
        emit('olimpo_estado', {'estado': olimpo.estado(usuario)})


@socketio.on('olimpo_ativar')
def olimpo_ativar(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'ativar', 1.5):
        return
    try:
        if olimpo.gratis():
            p = olimpo.ativar_gratis(usuario)
            emit('olimpo_estado', {'estado': olimpo.estado(p), 'ativado': True}, to=sala_pessoal(usuario.id))
            return
        c = olimpo.cobrar(usuario)
        emit('olimpo_cobranca', {**pagamentos.cobranca_json(c), 'modo_teste': pagamentos.modo_teste()})
    except olimpo.ErroOlimpo as e:
        emit('erro_bazinga', {'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO OLIMPO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível ativar a {olimpo.NOME}: {e}'})


@socketio.on('olimpo_simular')
def olimpo_simular(dados=None):
    """MODO TESTE: "paga" a cobrança da Brasa sem dinheiro (só no provedor simulado e só quem foi cobrado: pagamentos.simular_pagamento confere)."""
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'simular', 1.0):
        return
    try:
        c = pagamentos.cobranca_vigente('olimpo', usuario.id)
        if not c:
            emit('erro_bazinga', {'msg': 'Gere a cobrança primeiro.'})
            return
        c, nova = pagamentos.simular_pagamento(usuario.id, c.ext_id)
        if nova:
            from .bazar_events import aplicar_pagamento_confirmado
            aplicar_pagamento_confirmado(c)
    except pagamentos.ErroPagamento as e:
        emit('erro_bazinga', {'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO OLIMPO SIMULAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível simular o pagamento: {e}'})
