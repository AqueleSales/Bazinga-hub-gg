"""Eventos de Socket.IO da entrega acompanhada no mapa (a regra mora em entregas.py; leia o cabeçalho dela).

Regra 6: toda mudança chega às TRÊS pontas (comprador, vendedor e entregador, que pode ser a mesma pessoa que vende) em todas as abas delas.
A posição ao vivo (`entrega_ao_vivo`) só vai pra elas e nunca é gravada. Erro de regra volta como `bazar_erro` ({msg, ref}), igual ao Bazar.
"""
from .seguranca import emit

from . import socketio, bazar, entregas
from .bazar import ErroBazar
from .events import usuario_logado, sala_pessoal, criar_notificacao


# bazar_events e este módulo se importam pelo fim do events.py: pegar as ferramentas do Bazar só na hora de usar evita o import circular
def _freio(usuario, chave, intervalo=0.5):
    from . import bazar_events
    return bazar_events._freio(usuario, chave, intervalo)


def _executar(rotulo, fn, ref=None, ao_errar=None):
    from . import bazar_events
    return bazar_events._executar(rotulo, fn, ref=ref, ao_errar=ao_errar)


def _pos_aparelho():
    from . import bazar_events
    return bazar_events._pos_aparelho()


def _estado_do_entregador(pessoa_id):
    return entregas.minhas_entregas(pessoa_id)


def avisar_entregador(pessoa_id):
    """Manda o painel do entregador atualizado pra todas as abas dele (convite novo, entrega cancelada, pedido concluído...)."""
    try:
        socketio.emit('entregador_estado', _estado_do_entregador(pessoa_id), to=sala_pessoal(pessoa_id))
    except Exception as e:
        bazar.db.session.rollback()
        print(f"[ERRO ENTREGA: avisar entregador] {e}")


def _avisar_pontas(p, notificar=(), titulo=None, texto=None, de_id=None):
    """O pedido atualizado pras duas pontas + o painel do entregador (se for uma terceira pessoa) + notificação pra quem precisa saber."""
    for pessoa_id in (p.comprador_id, p.vendedor_id):
        socketio.emit('bazar_pedido', bazar.pedido_json(p, pessoa_id, com_mensagens=True), to=sala_pessoal(pessoa_id))
        socketio.emit('bazar_pendencias', {'n': bazar.contar_pendencias(pessoa_id)}, to=sala_pessoal(pessoa_id))
    if p.entregador_id:
        avisar_entregador(p.entregador_id)
    for destino in notificar:
        if destino and destino != de_id:
            criar_notificacao(destino, 'bazar', titulo, f'{p.produto_nome}: {texto}', de_id=de_id, ref=str(p.id))


def _emitir_repasse(envios, sinais):
    for _pid, quem, payload in envios:
        for pessoa_id in quem:
            socketio.emit('entrega_ao_vivo', payload, to=sala_pessoal(pessoa_id))
    for pid, payload in sinais:
        rec = entregas._ativas.get(pid)
        if rec:
            socketio.emit('entrega_sinal', payload, to=sala_pessoal(rec['entregador']))


def ao_mover(usuario, pos, fonte):
    """Chamado pelo `atualizar_localizacao` a cada posição. Só faz algo se a pessoa está levando um pedido (um dicionário em memória)."""
    if not entregas.esta_compartilhando(usuario.id):
        return
    envios, sinais, expirados = entregas.repassar(usuario.id, pos, fonte)
    _emitir_repasse(envios, sinais)
    for pid in expirados:
        p = entregas.expirar(pid)
        if p:
            _avisar_pontas(p, notificar=(p.comprador_id, p.vendedor_id, p.entregador_id), titulo='Entrega pausada',
                           texto='a entrega ficou aberta por tempo demais e o compartilhamento da posição foi encerrado. O entregador pode sair de novo.')


def _pedido_id(dados):
    return (dados if isinstance(dados, dict) else {}).get('pedido_id')


# ---------------------------------------------------------------------------
# entregador: cadastro e painel
# ---------------------------------------------------------------------------
@socketio.on('entregador_meu_estado')
def entregador_meu_estado(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    _executar('entregas', lambda: emit('entregador_estado', _estado_do_entregador(usuario.id)))


@socketio.on('entregador_cadastrar')
def entregador_cadastrar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entregador_cad', 1.0):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        entregas.cadastrar_entregador(usuario, dados.get('ativo'), bool(dados.get('consentimento')))
        socketio.emit('entregador_estado', _estado_do_entregador(usuario.id), to=sala_pessoal(usuario.id))
    _executar('cadastrar entregador', tarefa, ref='entregador')


# ---------------------------------------------------------------------------
# vendedor: quem entrega
# ---------------------------------------------------------------------------
@socketio.on('entrega_designar')
def entrega_designar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entrega_designar', 0.8):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p, antigo = entregas.designar(usuario, dados.get('pedido_id'), dados.get('quem'), dados.get('alvo'), dados.get('transporte'))
        if p.entregador_id != usuario.id:
            _avisar_pontas(p, notificar=(p.entregador_id,), titulo='Convite de entrega', texto=f'{usuario.name} quer que você entregue. Veja em Bazar > Entregas.', de_id=usuario.id)
        else:
            _avisar_pontas(p)
        if antigo and antigo != p.entregador_id and antigo != usuario.id:
            avisar_entregador(antigo)          # trocaram de entregador: o antigo perde o convite/acesso
    _executar('designar entregador', tarefa, ref=_pedido_id(dados))


@socketio.on('entrega_responder')
def entrega_responder(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entrega_responder', 0.8):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        aceitar = bool(dados.get('aceitar'))
        p = entregas.responder_convite(usuario, dados.get('pedido_id'), aceitar)
        _avisar_pontas(p, notificar=(p.vendedor_id,), titulo='Entregador aceitou' if aceitar else 'Entregador recusou',
                       texto=(f'{usuario.name} vai entregar.' if aceitar else f'{usuario.name} não pode entregar. Escolha outra pessoa.'), de_id=usuario.id)
    _executar('responder convite de entrega', tarefa, ref=_pedido_id(dados))


# ---------------------------------------------------------------------------
# entregador: sair, parar, entregar, retomar
# ---------------------------------------------------------------------------
@socketio.on('entrega_sair')
def entrega_sair(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entrega_sair', 1.0):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        if not dados.get('consentimento'):
            raise ErroBazar(entregas.MSG_CONSENTIMENTO)           # o aceite vem antes de qualquer outra checagem
        pos = _pos_aparelho()
        if not pos:
            raise ErroBazar('Preciso da localização do seu aparelho (GPS ou Wi-Fi) pra acompanhar a entrega. Espere ela chegar e tente de novo.')
        p = entregas.sair_para_entrega(usuario, dados.get('pedido_id'), dados.get('transporte'), bool(dados.get('consentimento')))
        envios, sinais, _ = entregas.repassar(usuario.id, pos, 'aparelho')      # a primeira posição sai na hora (o mapa não espera 45 s)
        _avisar_pontas(p, notificar=(p.comprador_id, p.vendedor_id), titulo='Saiu para entrega',
                       texto='o pedido está a caminho. Acompanhe pelo mapa no pedido.', de_id=usuario.id)
        _emitir_repasse(envios, sinais)
    _executar('sair para entrega', tarefa, ref=_pedido_id(dados))


@socketio.on('entrega_parar')
def entrega_parar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entrega_parar', 0.8):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p = entregas.parar_entrega(usuario, dados.get('pedido_id'))
        _avisar_pontas(p, notificar=(p.comprador_id, p.vendedor_id), titulo='Entrega pausada',
                       texto='o entregador parou de compartilhar a posição. Combinem pela conversa do pedido.', de_id=usuario.id)
    _executar('parar entrega', tarefa, ref=_pedido_id(dados))


@socketio.on('entrega_entregue')
def entrega_entregue(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entrega_entregue', 0.8):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p = entregas.marcar_entregue(usuario, dados.get('pedido_id'))
        _avisar_pontas(p, notificar=(p.comprador_id, p.vendedor_id), titulo='Pedido entregue',
                       texto='o entregador diz que entregou. Confirme o recebimento no pedido.', de_id=usuario.id)
    _executar('marcar entregue', tarefa, ref=_pedido_id(dados))


@socketio.on('entrega_retomar')
def entrega_retomar(dados):
    """Servidor reiniciou ou a aba recarregou no meio da entrega: o app do entregador pede pra voltar a compartilhar o que já estava a caminho."""
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entrega_retomar', 1.0):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p = entregas.retomar(usuario, dados.get('pedido_id'))
        emit('entregador_estado', _estado_do_entregador(usuario.id))
        if usuario.id in (p.comprador_id, p.vendedor_id):
            emit('bazar_pedido', bazar.pedido_json(p, usuario.id, com_mensagens=True))
    _executar('retomar entrega', tarefa, ref=_pedido_id(dados))


# ---------------------------------------------------------------------------
# comprador: o ponto de entrega
# ---------------------------------------------------------------------------
@socketio.on('entrega_destino')
def entrega_destino(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'entrega_destino', 1.0):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        limpar = bool(dados.get('limpar'))
        pos = None if limpar else _pos_aparelho()
        p = entregas.marcar_destino(usuario, dados.get('pedido_id'), pos, limpar)
        _avisar_pontas(p)
    _executar('marcar destino', tarefa, ref=_pedido_id(dados))
