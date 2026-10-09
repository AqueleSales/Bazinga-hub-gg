"""Eventos de Socket.IO do Bazar da comunidade (a lógica mora em bazar.py).

Regra 6: quando um pedido muda, as DUAS pontas recebem (`bazar_pedido` na sala pessoal de cada uma), não só quem agiu; quem
precisa fazer algo ganha o aviso na caixa de entrada. Loja/produto alterados avisam todo mundo com `bazar_mudou` (aviso
minúsculo: quem está olhando o Bazar pede a vitrine de novo). Favoritos vão pra TODAS as abas da pessoa (`bazar_favoritos`).
Erro de regra volta como `bazar_erro` ({msg, ref}); erro inesperado, como `erro_bazinga` (regra 3: nunca em silêncio).
Tudo que é de admin (anúncios, disputas, banimento, selo, moderação) confere `eh_admin` NO SERVIDOR a cada chamada.
"""
import time

from flask import request
from flask_socketio import emit

from . import socketio, bazar
from .bazar import ErroBazar
from .models import db, BazarLoja, BazarPedido
from .utils import com_retry
from .events import usuario_logado, sala_pessoal, criar_notificacao, centros_mapa, fontes_mapa

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


def _pos_aparelho():
    """(lat, lng) deste socket SE veio do aparelho (GPS/Wi-Fi): posição só por IP, 'suspeita' ou 'explorada' não vale pra "perto de mim"."""
    pos = centros_mapa.get(request.sid)
    return pos if pos and fontes_mapa.get(request.sid, 'aparelho') == 'aparelho' else None


def _avisar_pedido(p, agente, titulo, texto, agrupar=False):
    """Manda o pedido atualizado pras duas pontas e avisa a outra na caixa de entrada."""
    for pessoa_id in (p.comprador_id, p.vendedor_id):
        emit('bazar_pedido', bazar.pedido_json(p, pessoa_id, com_mensagens=True), to=sala_pessoal(pessoa_id))
        emit('bazar_pendencias', {'n': bazar.contar_pendencias(pessoa_id)}, to=sala_pessoal(pessoa_id))
    outro = p.vendedor_id if agente.id == p.comprador_id else p.comprador_id
    criar_notificacao(outro, 'bazar', titulo, texto, de_id=agente.id, ref=str(p.id), agrupar=agrupar)


def _avisar_as_duas_pontas(p, titulo, texto):
    """Mudança que NÃO veio de nenhuma das duas pontas (decisão de admin, banimento): as duas recebem o pedido e o aviso, sem remetente."""
    for pessoa_id in (p.comprador_id, p.vendedor_id):
        emit('bazar_pedido', bazar.pedido_json(p, pessoa_id, com_mensagens=True), to=sala_pessoal(pessoa_id))
        emit('bazar_pendencias', {'n': bazar.contar_pendencias(pessoa_id)}, to=sala_pessoal(pessoa_id))
        criar_notificacao(pessoa_id, 'bazar', titulo, texto, ref=str(p.id))


# ---------------------------------------------------------------------------
# vitrine e lojas
# ---------------------------------------------------------------------------
@socketio.on('bazar_listar')
def bazar_listar(dados=None):
    """Feed do Bazar (embaralhado por `seed` ou na ordem pedida, paginado). Página 0 leva também propagandas, destaques, favoritos e os catálogos;
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
        f = com_retry(lambda: bazar.feed(dados.get('busca'), dados.get('categoria'), dados.get('tipo'), seed, pagina,
                                         ordem=dados.get('ordem') or 'mix', so_favoritas=bool(dados.get('favoritas')),
                                         pessoa_id=usuario.id, pos=_pos_aparelho()))
        f['tag'] = str(dados.get('tag') or '')[:160]     # o cliente compara: resposta de filtro/seed que já não vale é ignorada
        if pagina > 0:
            emit('bazar_feed', f)
            return
        admin = bazar.eh_admin(usuario)
        v = {'feed': f, 'propagandas': bazar.propagandas(seed), 'destaques': bazar.destaques(),
             'catalogos': bazar.catalogos_json(), 'eh_admin': admin, 'favoritos': bazar.favoritos_de(usuario.id),
             'banido': bazar.banimento_json(usuario.id)}
        v['casa_padrao'] = not any(a['tipo'] == 'anuncio' for a in v['propagandas']) and bazar.anuncios_cadastrados() == 0
        minha = BazarLoja.query.filter_by(owner_id=usuario.id).with_entities(BazarLoja.id).first()
        v['minha_loja_id'] = minha[0] if minha else None
        v['pendencias'] = bazar.contar_pendencias(usuario.id)
        if admin:
            v['disputas_abertas'] = bazar.contar_disputas_abertas()
        emit('bazar_vitrine', v)

    _executar('listar', tarefa, ref='feed')


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
    _executar('minha loja', lambda: emit('bazar_minha', {'loja': com_retry(lambda: bazar.minha_loja(usuario)), 'banido': bazar.banimento_json(usuario.id)}))


@socketio.on('bazar_salvar_loja')
def bazar_salvar_loja(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'loja', 0.8):
        return

    def tarefa():
        loja = bazar.salvar_loja(usuario, dados, pos=_pos_aparelho())
        emit('bazar_minha', {'loja': loja, 'salvo': 'loja', 'banido': None}, to=sala_pessoal(usuario.id))
        _avisar_mudou(loja['id'])

    _executar('salvar loja', tarefa, ref='loja')


@socketio.on('bazar_salvar_produto')
def bazar_salvar_produto(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'produto', 0.8):
        return

    def tarefa():
        loja = bazar.salvar_produto(usuario, dados)
        emit('bazar_minha', {'loja': loja, 'salvo': 'produto', 'banido': None}, to=sala_pessoal(usuario.id))
        _avisar_mudou(loja['id'])

    _executar('salvar produto', tarefa, ref='produto')


@socketio.on('bazar_apagar_produto')
def bazar_apagar_produto(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'produto', 0.8):
        return

    def tarefa():
        loja = bazar.apagar_produto(usuario, (dados or {}).get('id'))
        emit('bazar_minha', {'loja': loja, 'salvo': 'apagado', 'banido': None}, to=sala_pessoal(usuario.id))
        _avisar_mudou(loja['id'])

    _executar('apagar produto', tarefa, ref='produto')


# ---------------------------------------------------------------------------
# favoritos (seguir loja): vai pra TODAS as abas da pessoa
# ---------------------------------------------------------------------------
@socketio.on('bazar_favoritar')
def bazar_favoritar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'fav', 0.4):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        ids = bazar.alternar_favorito(usuario, dados.get('loja_id'), dados.get('ativo'))
        emit('bazar_favoritos', {'ids': ids}, to=sala_pessoal(usuario.id))

    _executar('favoritar', tarefa, ref='favorito')


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
        p = bazar.abrir_pedido(usuario, dados.get('produto_id'), dados.get('quantidade', 1), dados.get('nota'),
                               entrega=dados.get('entrega'), endereco=dados.get('endereco'))
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
        p = bazar.enviar_mensagem(usuario, dados.get('pedido_id'), dados.get('texto'), dados.get('imagem_url'))
        resumo = (dados.get('texto') or '')[:140] or 'Enviou uma imagem.'
        _avisar_pedido(p, usuario, f'Mensagem sobre {p.produto_nome}', resumo, agrupar=True)

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
# disputa (qualquer ponta abre; só admin decide)
# ---------------------------------------------------------------------------
@socketio.on('bazar_disputar')
def bazar_disputar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'disputar', 2.0):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p = bazar.abrir_disputa(usuario, dados.get('pedido_id'), dados.get('motivo'), dados.get('detalhe'))
        _avisar_pedido(p, usuario, 'Disputa aberta no pedido', f'{p.produto_nome}: {usuario.name} pediu a análise de um administrador. As ações do pedido ficam travadas até a decisão.')
        for admin_id in bazar.ids_dos_admins():
            if admin_id not in (p.comprador_id, p.vendedor_id):
                criar_notificacao(admin_id, 'bazar', 'Nova disputa no Bazar', f'{p.produto_nome}: {bazar.MOTIVOS_DISPUTA[dados.get("motivo")][0]}', ref='disputa')
                emit('bazar_admin_aviso', {'disputas': bazar.contar_disputas_abertas()}, to=sala_pessoal(admin_id))

    _executar('disputar', tarefa, ref=dados.get('pedido_id'))


@socketio.on('bazar_disputas_listar')
def bazar_disputas_listar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    _executar('disputas', lambda: emit('bazar_disputas', com_retry(lambda: bazar.disputas_para_admin(usuario))), ref='moderacao')


@socketio.on('bazar_disputa_resolver')
def bazar_disputa_resolver(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'resolver', 0.8):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        p = bazar.resolver_disputa(usuario, dados.get('disputa_id'), dados.get('acao'), dados.get('nota'))
        texto = {'concluir': 'Decisão: pedido dado como entregue e concluído.', 'cancelar': 'Decisão: pedido cancelado (o reembolso, se houver, se combina entre vocês).',
                 'arquivar': 'Decisão: disputa encerrada sem mudar o pedido.'}[dados.get('acao')]
        _avisar_as_duas_pontas(p, 'Disputa resolvida', f'{p.produto_nome}: {texto} {dados.get("nota")}'[:300])
        emit('bazar_disputas', com_retry(lambda: bazar.disputas_para_admin(usuario)))
        _avisar_mudou(p.loja_id)

    _executar('resolver disputa', tarefa, ref='moderacao')


# ---------------------------------------------------------------------------
# anúncios do carrossel (só admin) + clique (qualquer pessoa)
# ---------------------------------------------------------------------------
@socketio.on('bazar_anuncio_clique')
def bazar_anuncio_clique(dados):
    usuario = usuario_logado()
    aid = (dados or {}).get('id') if isinstance(dados, dict) else None
    if not usuario or _freio(usuario, f'clique{aid}', 5.0):
        return
    _executar('clique do anúncio', lambda: bazar.registrar_clique(aid))


@socketio.on('bazar_anuncios_listar')
def bazar_anuncios_listar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    _executar('anúncios', lambda: emit('bazar_anuncios', {'lista': com_retry(lambda: bazar.lista_anuncios(usuario))}), ref='moderacao')


@socketio.on('bazar_anuncio_salvar')
def bazar_anuncio_salvar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'anuncio', 0.8):
        return

    def tarefa():
        bazar.salvar_anuncio(usuario, dados)
        emit('bazar_anuncios', {'lista': bazar.lista_anuncios(usuario), 'salvo': True})
        _avisar_mudou()

    _executar('salvar anúncio', tarefa, ref='anuncio')


@socketio.on('bazar_anuncio_apagar')
def bazar_anuncio_apagar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'anuncio', 0.8):
        return

    def tarefa():
        bazar.apagar_anuncio(usuario, (dados or {}).get('id'))
        emit('bazar_anuncios', {'lista': bazar.lista_anuncios(usuario)})
        _avisar_mudou()

    _executar('apagar anúncio', tarefa, ref='anuncio')


@socketio.on('bazar_anuncios_padrao')
def bazar_anuncios_padrao(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'anuncio', 0.8):
        return

    def tarefa():
        bazar.criar_anuncios_padrao(usuario)
        emit('bazar_anuncios', {'lista': bazar.lista_anuncios(usuario), 'salvo': True})
        _avisar_mudou()

    _executar('anúncios padrão', tarefa, ref='anuncio')


# ---------------------------------------------------------------------------
# banimento e selo (só admin)
# ---------------------------------------------------------------------------
@socketio.on('bazar_banidos_listar')
def bazar_banidos_listar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    _executar('banidos', lambda: emit('bazar_banidos', {'lista': com_retry(lambda: bazar.lista_banidos(usuario))}), ref='moderacao')


@socketio.on('bazar_banir')
def bazar_banir(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'banir', 0.8):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        alvo_id = dados.get('pessoa_id')
        if not alvo_id and dados.get('usuario'):              # pelo @ (único)
            achada = bazar.achar_pessoa(dados.get('usuario'))
            if not achada:
                raise ErroBazar('Não achei ninguém com esse @.')
            alvo_id = achada.id
        den = None
        if dados.get('denuncia_tipo') and dados.get('denuncia_alvo'):
            den = (str(dados['denuncia_tipo'])[:12], int(dados['denuncia_alvo']))
        alvo, cancelados = bazar.banir(usuario, alvo_id, dados.get('motivo'), dados.get('dias'), den)
        for pid in cancelados:
            p = BazarPedido.query.get(pid)
            if p:
                _avisar_as_duas_pontas(p, 'Pedido cancelado no Bazar', f'{p.produto_nome}: uma das contas foi suspensa do Bazar. Se você já pagou, converse com a outra pessoa ou denuncie.')
        emit('bazar_banidos', {'lista': bazar.lista_banidos(usuario), 'feito': alvo.name})
        emit('bazar_moderacao', {'fila': bazar.fila_de_moderacao()})
        emit('bazar_admin_aviso', {'disputas': bazar.contar_disputas_abertas()})       # banir arquiva as disputas dos pedidos cancelados
        emit('bazar_vitrine_banido', {'banido': bazar.banimento_json(alvo.id)}, to=sala_pessoal(alvo.id))
        _avisar_mudou()

    _executar('banir', tarefa, ref='moderacao')


@socketio.on('bazar_desbanir')
def bazar_desbanir(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'banir', 0.8):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        bazar.desbanir(usuario, dados.get('pessoa_id'))
        emit('bazar_banidos', {'lista': bazar.lista_banidos(usuario)})
        emit('bazar_vitrine_banido', {'banido': None}, to=sala_pessoal(int(dados.get('pessoa_id'))))
        _avisar_mudou()

    _executar('desbanir', tarefa, ref='moderacao')


@socketio.on('bazar_verificar')
def bazar_verificar(dados):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'verificar', 0.8):
        return
    dados = dados if isinstance(dados, dict) else {}

    def tarefa():
        lid = bazar.definir_verificada(usuario, dados.get('loja_id'), dados.get('ativo'))
        emit('bazar_loja', bazar.loja_completa(lid, usuario))
        _avisar_mudou(lid)

    _executar('verificar loja', tarefa, ref='loja')


# ---------------------------------------------------------------------------
# moderação de denúncias (só admin: o servidor confere a cada chamada)
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
