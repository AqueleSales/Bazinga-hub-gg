"""Eventos das Configurações do usuário (Rodada 34): preferências da conta, histórico de cobrança e resumo de privacidade.
Importado no FIM do events.py (precisa de usuario_logado e sala_pessoal de lá). Regra 6: salvar numa aba atualiza todas as abas da pessoa."""
import time

from flask_socketio import emit

from . import socketio, preferencias, config_usuario
from .models import db
from .events import usuario_logado, sala_pessoal
from .utils import com_retry, comitar_com_retry

_ultimo = {}


def _freio(usuario, chave, intervalo):
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


@socketio.on('salvar_preferencias')
def salvar_preferencias(dados=None):
    """`dados` = {chave: valor} só do que mudou. O servidor descarta chave desconhecida e valor fora da lista (app/preferencias.py) e
    devolve o conjunto COMPLETO já validado pra todas as abas da pessoa: é o que o cliente passa a mostrar."""
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    try:
        resultado = {}

        def preparar():
            resultado['prefs'] = preferencias.aplicar(usuario, dados)

        comitar_com_retry(preparar)
        preferencias.guardar_no_cache(usuario)
        emit('preferencias_carregadas', {'prefs': resultado['prefs']}, to=sala_pessoal(usuario.id))
    except Exception as e:
        db.session.rollback()
        preferencias.esquecer(usuario.id)
        print(f"[ERRO SALVAR PREFERENCIAS] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar a configuração: {e}'})


@socketio.on('cobranca_historico')
def cobranca_historico(dados=None):
    """A aba Cobrança: histórico em DRC e em Pix. Só da própria pessoa (o id vem da sessão, nunca do cliente)."""
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'cobranca', 1.0):
        return
    try:
        emit('cobranca_historico', com_retry(lambda: config_usuario.historico_cobranca(usuario)))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO COBRANCA HISTORICO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível carregar o histórico: {e}'})


@socketio.on('dados_privacidade')
def dados_privacidade(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        emit('dados_privacidade', config_usuario.resumo_privacidade(usuario))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO DADOS PRIVACIDADE] {e}")
