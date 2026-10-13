"""Eventos de Socket.IO do Passe de Batalha, dos títulos e da escolha das missões semanais (a regra mora em passe.py e utils.py).

Regra 6: o que a pessoa resgata/equipa/escolhe vale em TODAS as abas dela (`sala_pessoal`), e título equipado avisa quem convive
(`_difundir_aparencia`). Erro de regra volta como `passe_erro` (toast), erro inesperado como `erro_bazinga` (regra 3).
"""
import time

from flask_socketio import emit

from . import socketio, passe
from .passe import ErroPasse
from .models import db
from .utils import com_retry, missoes_do_usuario, escolher_semanal, ErroMissao
from .cosmeticos import posses_da_pessoa
from .events import usuario_logado, sala_pessoal, _estado_inventario, _payload_perfil, _difundir_aparencia

_ultimo = {}


def _freio(usuario, chave, intervalo=0.6):
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


def _estado_titulos(usuario, posses=None):
    posses = com_retry(lambda: posses_da_pessoa(usuario.id)) if posses is None else posses
    return {'lista': passe.titulos_da_pessoa(posses), 'equipado': usuario.titulo_id or None}


@socketio.on('passe_pedir')
def passe_pedir(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        emit('passe', passe.estado(usuario))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PASSE PEDIR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível abrir o passe: {e}'})


@socketio.on('passe_resgatar')
def passe_resgatar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    if _freio(usuario, 'resgatar'):
        return
    dados = dados or {}
    try:
        if dados.get('todos'):
            r = passe.resgatar(usuario)
        else:
            r = passe.resgatar(usuario, dados.get('nivel'), dados.get('trilha'))
    except ErroPasse as e:
        db.session.rollback()
        emit('passe_erro', {'msg': str(e)})
        emit('passe', passe.estado(usuario))        # a tela se corrige sozinha (ex.: já tinha resgatado em outra aba)
        return
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PASSE RESGATAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível resgatar: {e}'})
        return
    try:
        sala = sala_pessoal(usuario.id)
        posses = com_retry(lambda: posses_da_pessoa(usuario.id))
        emit('passe_resgatado', r, to=sala)
        emit('passe', passe.estado(usuario), to=sala)
        emit('saldo_atualizado', {'saldo': usuario.bazinga_coins or 0}, to=sala)
        emit('inventario', _estado_inventario(usuario, posses), to=sala)
        emit('titulos', _estado_titulos(usuario, posses), to=sala)
    except Exception as e:
        # o resgate JÁ foi feito e comitado; só a atualização da tela falhou (o próximo passe_pedir corrige)
        db.session.rollback()
        print(f"[ERRO PASSE RESGATAR: avisar abas] {e}")


@socketio.on('listar_titulos')
def listar_titulos(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        emit('titulos', _estado_titulos(usuario))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LISTAR TITULOS] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível abrir os títulos: {e}'})


@socketio.on('equipar_titulo')
def equipar_titulo(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    if _freio(usuario, 'titulo'):
        return
    tid = str((dados or {}).get('titulo_id') or '')[:24] or None
    try:
        passe.equipar_titulo(usuario, tid)
    except ErroPasse as e:
        db.session.rollback()
        emit('passe_erro', {'msg': str(e)})
        return
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EQUIPAR TITULO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível equipar o título: {e}'})
        return
    try:
        sala = sala_pessoal(usuario.id)
        emit('titulos', _estado_titulos(usuario), to=sala)
        emit('perfil_atualizado', _payload_perfil(usuario), to=sala)
        _difundir_aparencia(usuario)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EQUIPAR TITULO: avisar] {e}")


@socketio.on('escolher_missao_semanal')
def escolher_missao_semanal(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    if _freio(usuario, 'missao', 0.4):
        return
    dados = dados or {}
    codigo = str(dados.get('codigo') or '')[:40]
    try:
        escolher_semanal(usuario, codigo, escolher=dados.get('escolher') is not False)
    except ErroMissao as e:
        db.session.rollback()
        emit('passe_erro', {'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ESCOLHER MISSAO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível escolher a missão: {e}'})
    try:
        emit('missoes_atualizadas', missoes_do_usuario(usuario), to=sala_pessoal(usuario.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ESCOLHER MISSAO: avisar] {e}")
