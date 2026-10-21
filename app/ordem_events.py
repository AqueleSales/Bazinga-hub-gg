"""Eventos de Socket.IO da ordem dos servidores (com pastinhas) e das DMs fixadas (a validação mora em ordem.py).

`salvar_ordem_servidores {layout}` e `salvar_ordem_dms {fixas}` gravam na CONTA e avisam TODAS as abas da pessoa com
`preferencias_carregadas` (regra 6): quem arrastou em um aparelho vê o mesmo nos outros. O valor que volta é o que o servidor
LIMPOU (id alheio, pasta repetida e nome fora do formato foram descartados), então a tela de quem arrastou também se corrige.
Erro de banco não é silencioso (regra 3): vira `erro_bazinga` com o motivo.
"""
from flask_socketio import emit
from sqlalchemy import or_

from . import socketio, ordem
from .models import db, Friendship
from .utils import comitar_com_retry
from .events import usuario_logado, sala_pessoal


def _dados(dados, chave):
    """O valor de `chave` se o payload é um objeto com uma lista nela; senão None (payload inválido é ignorado, nunca quebra)."""
    if not isinstance(dados, dict) or not isinstance(dados.get(chave), list):
        return None
    return dados[chave]


@socketio.on('salvar_ordem_servidores')
def salvar_ordem_servidores(dados=None):
    usuario = usuario_logado()
    bruto = _dados(dados, 'layout')
    if not usuario or bruto is None:
        return
    try:
        ids = [s.id for s in usuario.servers]                       # só servidor de que a pessoa é membro vale
        novo = ordem.completar_layout(ordem.normalizar_layout(bruto, ids), ids)
        atual = ordem.layout_da_pessoa(usuario, ids)
        if novo == atual:
            emit('preferencias_carregadas', {'ordem_servidores': atual})   # nada a gravar; só corrige a tela de quem mandou
            return
        texto = ordem.serializar(novo)

        def preparar():
            usuario.ordem_servidores = texto

        comitar_com_retry(preparar)
        emit('preferencias_carregadas', {'ordem_servidores': novo}, to=sala_pessoal(usuario.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ORDEM SERVIDORES] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar a ordem dos servidores: {e}'})


@socketio.on('salvar_ordem_dms')
def salvar_ordem_dms(dados=None):
    usuario = usuario_logado()
    bruto = _dados(dados, 'fixas')
    if not usuario or bruto is None:
        return
    try:
        aceitas = Friendship.query.filter(
            Friendship.status == 'accepted',
            or_(Friendship.requester_id == usuario.id, Friendship.addressee_id == usuario.id)).all()
        amigos = [f.addressee_id if f.requester_id == usuario.id else f.requester_id for f in aceitas]
        novo = ordem.normalizar_fixas(bruto, amigos)               # só amigo de verdade pode ficar fixado
        if novo == ordem.fixas_da_pessoa(usuario):
            emit('preferencias_carregadas', {'ordem_dms': novo})
            return
        texto = ordem.serializar(novo)

        def preparar():
            usuario.ordem_dms = texto

        comitar_com_retry(preparar)
        emit('preferencias_carregadas', {'ordem_dms': novo}, to=sala_pessoal(usuario.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ORDEM DMS] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar a ordem das conversas: {e}'})
