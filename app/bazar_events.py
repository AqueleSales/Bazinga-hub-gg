"""Eventos de Socket.IO do Bazar da comunidade (a lógica mora em bazar.py).

Regra 6: quando um pedido muda, as DUAS pontas recebem (`bazar_pedido` na sala pessoal de cada uma), não só quem agiu; quem
precisa fazer algo ganha o aviso na caixa de entrada. Loja/produto alterados avisam todo mundo com `bazar_mudou` (aviso
minúsculo: quem está olhando o Bazar pede a vitrine de novo).
Erro de regra volta como `bazar_erro` ({msg, ref}); erro inesperado, como `erro_bazinga` (regra 3: nunca em silêncio).
"""
import time

from flask_socketio import emit

from . import socketio, bazar
from .bazar import ErroBazar
from .models import db, BazarLoja, BazarPedido
from .utils import com_retry
from .events import usuario_logado, sala_pessoal, criar_notificacao

_ultimo = {}


def _freio(usuario, chave, intervalo=0.5):
    """True se a pessoa está repetindo a mesma ação rápido demais (clique duplo, script)."""
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


def _erro(msg, ref=None):
    emit('bazar_erro', {'msg': msg, 'ref': ref})


def _executar(rotulo, fn, ref=None, ao_errar=None):
    """Roda `fn` e traduz os erros: ErroBazar vira toast de regra (e `ao_errar`, se houver, corrige a tela); o resto, toast com o motivo real + log."""
    try:
        return fn()
    except ErroBazar as e:
        db.session.rollback()
        _erro(str(e), ref)
        if ao_errar:
            try:
                ao_errar()
            except Exception as e2:
                db.session.rollback()
                print(f"[ERRO BAZAR {rotulo}: corrigir tela] {e2}")
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO BAZAR {rotulo}] {e}")
        emit('erro_bazinga', {'msg': f'Bazar ({rotulo}): {e}'})
    return None


def _avisar_mudou(loja_id=None):
    emit('bazar_mudou', {'loja_id': loja_id}, broadcast=True)


def _avisar_pedido(p, agente, titulo, texto, agrupar=False):
    """Manda o pedido atualizado pras duas pontas e avisa a outra na caixa de entrada."""
    for pessoa_id in (p.comprador_id, p.vendedor_id):
        emit('bazar_pedido', bazar.pedido_json(p, pessoa_id, com_mensagens=True), to=sala_pessoal(pessoa_id))
        emit('bazar_pendencias', {'n': bazar.contar_pendencias(pessoa_id)}, to=sala_pessoal(pessoa_id))
    outro = p.vendedor_id if agente.id == p.comprador_id else p.comprador_id
    criar_notificacao(outro, 'bazar', titulo, texto, de_id=agente.id, ref=str(p.id), agrupar=agrupar)


# ---------------------------------------------------------------------------
# vitrine e lojas
# ---------------------------------------------------------------------------
@socketio.on('bazar_listar')
def bazar_listar(dados=None):
    """Feed do Bazar (embaralhado por `seed`, paginado). Página 0 leva também propagandas, destaques e os catálogos;
    as seguintes (rolagem infinita) só o feed, em `bazar_feed`."""
    usuario = usuario_logado()
    if not usuario:
        return
    dados = dados if isinstance(dados, dict) else {}
    try:
        pagina = max(int(dados.get('pagina') or 0), 0)
    except (TypeError, ValueError):
        pagina = 0
    seed = dados.get('seed')

    def tarefa():
        f = com_retry(lambda: bazar.feed(dados.get('busca'), dados.get('categoria'), dados.get('tipo'), seed, pagina))
        f['tag'] = str(dados.get('tag') or '')[:120]     # o cliente compara: resposta de filtro/seed que já não vale é ignorada
        if pagina > 0:
            emit('bazar_feed', f)
            return
        v = {'feed': f, 'propagandas': bazar.propagandas(seed), 'destaques': bazar.destaques(),
             'catalogos': bazar.catalogos_json(), 'eh_admin': bazar.eh_admin(usuario)}
        minha = BazarLoja.query.filter_by(owner_id=usuario.id).with_entities(BazarLoja.id).first()
        v['minha_loja_id'] = minha[0] if minha else None
        v['pendencias'] = bazar.contar_pendencias(usuario.id)
        emit('bazar_vitrine', v)

    _executar('listar', tarefa)


@socketio.on('bazar_abrir_loja')
def bazar_abrir_loja(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    lid = (dados or {}).get('loja_id')
    _executar('abrir loja', lambda: emit('bazar_loja', bazar.loja_completa(int(lid), usuario)), ref='loja')


@socketio.on('bazar_minha_loja')
def bazar_minha_loja(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    _executar('minha loja', lambda: emit('bazar_minha', {'loja': com_retry(lambda: bazar.minha_loja(usuario))}))


@socketio.on('bazar_salvar_loja')
def bazar_salvar_loja(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'loja', 0.8):
        return

    def tarefa():
        loja = bazar.salvar_loja(usuario, dados)
        emit('bazar_minha', {'loja': loja, 'salvo': 'loja'}, to=sala_pessoal(usuario.id))
        _avisar_mudou(loja['id'])

    _executar('salvar loja', tarefa, ref='loja')


@socketio.on('bazar_salvar_produto')
def bazar_salvar_produto(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'produto', 0.8):
        return

    def tarefa():
        loja = bazar.salvar_produto(usuario, dados)
        emit('bazar_minha', {'loja': loja, 'salvo': 'produto'}, to=sala_pessoal(usuario.id))
        _avisar_mudou(loja['id'])

    _executar('salvar produto', tarefa, ref='produto')


@socketio.on('bazar_apagar_produto')
def bazar_apagar_produto(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'produto', 0.8):
        return

    def tarefa():
        loja = bazar.apagar_produto(usuario, (dados or {}).get('id'))
        emit('bazar_minha', {'loja': loja, 'salvo': 'apagado'}, to=sala_pessoal(usuario.id))
        _avisar_mudou(loja['id'])

    _executar('apagar produto', tarefa, ref='produto')


# ---------------------------------------------------------------------------
# pedidos
# ---------------------------------------------------------------------------
@socketio.on('bazar_pedir')
def bazar_pedir(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'pedir', 1.0):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p = bazar.abrir_pedido(usuario, dados.get('produto_id'), dados.get('quantidade', 1), dados.get('nota'))
        _avisar_pedido(p, usuario, 'Novo pedido no Bazar', f'{usuario.name} quer {p.quantidade}x {p.produto_nome}')
        emit('bazar_pedido_aberto', {'pedido_id': p.id}, to=sala_pessoal(usuario.id))

    _executar('pedir', tarefa, ref='pedir')


@socketio.on('bazar_meus_pedidos')
def bazar_meus_pedidos(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    _executar('meus pedidos', lambda: emit('bazar_pedidos', com_retry(lambda: bazar.meus_pedidos(usuario))))


@socketio.on('bazar_abrir_pedido')
def bazar_abrir_pedido(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    def tarefa():
        pid = (dados or {}).get('pedido_id')
        p = com_retry(lambda: BazarPedido.query.get(int(pid)))
        if not p or usuario.id not in (p.comprador_id, p.vendedor_id):
            raise ErroBazar('Pedido não encontrado.')
        emit('bazar_pedido', bazar.pedido_json(p, usuario.id, com_mensagens=True))

    _executar('abrir pedido', tarefa)


_AVISOS = {   # ação -> (título, texto) da notificação pra OUTRA ponta
    'aceitar': ('Pedido aceito', 'O vendedor aceitou. Pague por Pix em "Meus pedidos".'),
    'recusar': ('Pedido recusado', 'O vendedor recusou o pedido.'),
    'cancelar': ('Pedido cancelado', 'O pedido foi cancelado.'),
    'paguei': ('Pagamento informado', 'O comprador diz que pagou. Confira o Pix e confirme.'),
    'confirmar': ('Pagamento confirmado', 'O vendedor confirmou o Pix. Veja a entrega em "Meus pedidos".'),
    'nao_recebi': ('Pix não encontrado', 'O vendedor não achou o seu Pix. Confira o valor e a chave.'),
    'recebi': ('Pedido concluído', 'O comprador confirmou que recebeu. Valeu!'),
}


@socketio.on('bazar_agir')
def bazar_agir(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'agir', 0.6):
        return
    dados = dados if isinstance(dados, dict) else {}
    acao = dados.get('acao')

    def tarefa():
        if acao not in _AVISOS:
            raise ErroBazar('Ação inválida.')
        p = bazar.agir_no_pedido(usuario, dados.get('pedido_id'), acao)
        titulo, texto = _AVISOS[acao]
        _avisar_pedido(p, usuario, titulo, f'{p.produto_nome}: {texto}')
        if acao == 'recebi' or acao in ('aceitar', 'cancelar', 'recusar'):
            _avisar_mudou(p.loja_id)       # estoque/vendas mudaram: quem olha a loja atualiza

    def aoerrar():
        # o estado pode ter mudado do outro lado: manda o pedido como ele está agora
        try:
            pid = int(dados.get('pedido_id'))
            p = BazarPedido.query.get(pid)
            if p and usuario.id in (p.comprador_id, p.vendedor_id):
                emit('bazar_pedido', bazar.pedido_json(p, usuario.id, com_mensagens=True))
        except Exception:
            db.session.rollback()

    _executar('agir', tarefa, ref=dados.get('pedido_id'), ao_errar=aoerrar)


@socketio.on('bazar_mensagem')
def bazar_mensagem(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'msg', 0.4):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p = bazar.enviar_mensagem(usuario, dados.get('pedido_id'), dados.get('texto'))
        _avisar_pedido(p, usuario, f'Mensagem sobre {p.produto_nome}', (dados.get('texto') or '')[:140], agrupar=True)

    _executar('mensagem', tarefa, ref=dados.get('pedido_id'))


@socketio.on('bazar_avaliar')
def bazar_avaliar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'avaliar', 1.0):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p = bazar.avaliar(usuario, dados.get('pedido_id'), dados.get('nota'), dados.get('texto'))
        _avisar_pedido(p, usuario, 'Nova avaliação na sua loja', f'{dados.get("nota")} de 5 em {p.produto_nome}')
        _avisar_mudou(p.loja_id)

    _executar('avaliar', tarefa, ref=dados.get('pedido_id'))


# ---------------------------------------------------------------------------
# moderação (só admin: o servidor confere a cada chamada)
# ---------------------------------------------------------------------------
@socketio.on('bazar_moderacao_listar')
def bazar_moderacao_listar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return

    def tarefa():
        if not bazar.eh_admin(usuario):
            raise ErroBazar('Só administradores moderam.')
        emit('bazar_moderacao', {'fila': bazar.fila_de_moderacao()})

    _executar('moderação', tarefa, ref='moderacao')


@socketio.on('bazar_moderar')
def bazar_moderar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'moderar', 0.5):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        info = bazar.moderar(usuario, dados.get('tipo'), dados.get('alvo_id'), dados.get('acao'))
        emit('bazar_moderacao', {'fila': bazar.fila_de_moderacao()})
        if info['tipo'] in ('loja', 'produto'):
            _avisar_mudou()
        elif info['acao'] == 'remover':
            emit('geonote_apagada' if info['tipo'] == 'nota' else 'servidor_mapa_apagado', {'id': info['alvo_id']}, broadcast=True)

    _executar('moderar', tarefa, ref='moderacao')
