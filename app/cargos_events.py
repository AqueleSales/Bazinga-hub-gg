"""Handlers de Socket.IO dos cargos, categorias, organização da lista de canais e palco (Rodada 29). A regra mora em cargos.py.

Padrão de todo handler: pega o servidor, calcula o `contexto` da pessoa NO BANCO (nunca confia no cliente), aplica dentro de `comitar_com_retry`
e, se deu certo, manda a cada membro a SUA versão do servidor (`avisar_servidor(..., 'servidor_estrutura')`, regra 6): cargo e categoria
mudam permissão, cor e quais canais cada um enxerga. Importado no FIM do events.py (usa daqui o usuario_logado e o avisar_servidor).
"""
from flask_socketio import emit

from . import socketio
from . import cargos
from .models import db, Server, Person
from .utils import com_retry, comitar_com_retry, canal_permitido
from .events import (usuario_logado, sala_pessoal, avisar_servidor, participantes_call, palco_convidados, _avisar_participantes)



def _dict(d):
    return d if isinstance(d, dict) else {}


def _servidor_da_pessoa(usuario, dados):
    """(srv, ctx) do servidor citado, ou (None, None) se não existe / a pessoa não é membro. Já avisa a pessoa."""
    try:
        srv = com_retry(lambda: Server.query.get(int(dados.get('server_id'))))
    except (TypeError, ValueError):
        srv = None
    ctx = cargos.contexto(usuario, srv) if srv else cargos.SEM_ACESSO
    if not srv or not ctx.membro:
        emit('erro_bazinga', {'msg': 'Você não está nesse servidor.'})
        return None, None
    return srv, ctx


def _aplicar(usuario, dados, rotulo, acao, depois=None):
    """Esqueleto comum: `acao(srv, ctx)` roda dentro da transação; ErroCargo vira toast; sucesso avisa todos os membros.
    Sem freio de clique de propósito: soltar o arquivo duas vezes seguidas nunca pode ser engolido em silêncio (a transação já protege)."""
    dados = _dict(dados)
    try:
        srv, ctx = _servidor_da_pessoa(usuario, dados)
        if not srv:
            return
        resultado = {}

        def preparar():
            resultado['valor'] = acao(srv, cargos.contexto(usuario, srv))   # o contexto é refeito a cada tentativa (nível pode ter mudado)
            return resultado['valor']

        comitar_com_retry(preparar)
        cargos.invalidar(srv.id)
        avisar_servidor(srv, 'servidor_estrutura')
        if depois:
            depois(srv, resultado.get('valor'))
        return resultado.get('valor')
    except cargos.ErroCargo as e:
        db.session.rollback()
        emit('erro_bazinga', {'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO {rotulo}] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível concluir: {e}'})


# ==========================================
# CARGOS
# ==========================================
@socketio.on('cargo_criar')
def cargo_criar(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CARGO CRIAR', lambda srv, ctx: cargos.criar_cargo(
        srv, ctx, d.get('nome'), d.get('cor'), d.get('permissoes'), d.get('destacar')),
        depois=lambda srv, r: emit('cargo_criado', {'server_id': srv.id, 'cargo_id': r.id}))


@socketio.on('cargo_editar')
def cargo_editar(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CARGO EDITAR', lambda srv, ctx: cargos.editar_cargo(srv, ctx, d.get('cargo_id'), d))


@socketio.on('cargo_apagar')
def cargo_apagar(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CARGO APAGAR', lambda srv, ctx: cargos.apagar_cargo(srv, ctx, d.get('cargo_id')))


@socketio.on('cargos_reordenar')
def cargos_reordenar(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CARGOS ORDEM', lambda srv, ctx: cargos.reordenar_cargos(srv, ctx, d.get('ordem')))


@socketio.on('cargo_membro')
def cargo_membro(dados):
    """Dá (ativo=true) ou tira (ativo=false) um cargo de um membro. O valor é EXPLÍCITO: duas abas clicando juntas não se anulam."""
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CARGO MEMBRO',
             lambda srv, ctx: cargos.atribuir_cargo(srv, ctx, d.get('person_id'), d.get('cargo_id'), bool(d.get('ativo')), usuario.id),
             depois=lambda srv, r: emit('cargos_dos_membros_mudou', {'server_id': srv.id}, to=f"srv_{srv.id}"))


@socketio.on('cargo_padrao')
def cargo_padrao(dados):
    """Permissões do cargo "Membro" (o que todo mundo tem)."""
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CARGO PADRAO', lambda srv, ctx: cargos.definir_perms_membro(srv, ctx, d.get('permissoes')))


# ==========================================
# CATEGORIAS E ORGANIZAÇÃO DA LISTA DE CANAIS
# ==========================================
@socketio.on('categoria_criar')
def categoria_criar(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CATEGORIA CRIAR', lambda srv, ctx: cargos.criar_categoria(srv, ctx, d.get('nome')))


@socketio.on('categoria_renomear')
def categoria_renomear(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CATEGORIA RENOMEAR', lambda srv, ctx: cargos.renomear_categoria(srv, ctx, d.get('categoria_id'), d.get('nome')))


@socketio.on('categoria_apagar')
def categoria_apagar(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CATEGORIA APAGAR', lambda srv, ctx: cargos.apagar_categoria(srv, ctx, d.get('categoria_id')))


@socketio.on('canais_organizar')
def canais_organizar(dados):
    """Arrastar e soltar: o cliente manda a lista inteira desejada; o servidor aplica só o que é válido (ids deste servidor e de canais que a pessoa enxerga)."""
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    _aplicar(usuario, d, 'CANAIS ORGANIZAR',
             lambda srv, ctx: cargos.organizar_canais(srv, ctx, usuario.id, d.get('categorias'), d.get('grupos')))


# ==========================================
# PALCO: chamar um ouvinte pro palco (ou mandar de volta)
# ==========================================
@socketio.on('palco_promover')
def palco_promover(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    try:
        canal = canal_permitido(usuario, d.get('canal_id'))
        if not canal or canal.channel_type != 'palco':
            emit('erro_bazinga', {'msg': 'Esse canal não é um palco.'})
            return
        srv = com_retry(lambda: Server.query.get(canal.server_id))
        if not cargos.pode(usuario, srv, 'falar_palco'):
            emit('erro_bazinga', {'msg': 'Só quem pode falar no palco chama outras pessoas pra falar.'})
            return
        chave = str(canal.id)
        try:
            alvo_id = int(d.get('person_id'))
        except (TypeError, ValueError):
            return
        entradas = [p for p in participantes_call.get(chave, []) if p.get('usuario_id') == alvo_id]
        if not entradas:
            emit('erro_bazinga', {'msg': 'Essa pessoa não está no palco agora.'})
            return
        alvo = com_retry(lambda: Person.query.get(alvo_id))
        convidados = palco_convidados.setdefault(chave, set())
        if d.get('ativo'):
            convidados.add(alvo_id)
        else:
            convidados.discard(alvo_id)
        ouvinte = not (cargos.pode(alvo, srv, 'falar_palco') or alvo_id in convidados)
        for p in entradas:
            p['ouvinte'] = ouvinte
        _avisar_participantes(chave, canal.server_id)
        emit('palco_papel', {'canal_id': chave, 'ouvinte': ouvinte, 'palco': True}, to=sala_pessoal(alvo_id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PALCO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível mexer no palco: {e}'})
