"""Eventos de Socket.IO das atividades da call (xadrez). As regras do jogo moram em `atividades.py`; aqui fica quem pode o quê
e quem recebe cada aviso.

Regras (o SERVIDOR decide, o navegador só pede):
- só quem está DE VERDADE na call (o socket dele está registrado nela em `_call_por_sid`) vê ou mexe na atividade;
- ouvinte (sem "falar" no canal, ou plateia do palco) assiste mas não inicia nem senta;
- cada lance é conferido pelo motor: ilegal, fora da vez ou de quem não é aquele lado é recusado;
- a atividade é da call: quando a call esvazia, ela some; quem sai no meio de uma partida deixa a cadeira marcada como ausente.
Regra 6: toda mudança vai pra sala `voz_<chave>` inteira (quem joga e quem assiste), nunca só pra quem agiu.
"""
import time

from flask import request

from . import socketio, atividades
from .events import usuario_logado, participantes_call, _call_por_sid, _meta_call

_ultimo_lance = {}        # sid -> hora do último lance (freio de 0,15 s, só pra não afogar o servidor)
_ultima_acao = {}         # (sid) -> hora da última ação que não é lance


def _chave(canal_id):
    if isinstance(canal_id, str) and canal_id.startswith('dm_'):
        return canal_id
    if isinstance(canal_id, bool) or not isinstance(canal_id, (int, str)):
        return None
    return str(canal_id)


def _participante(chave, usuario):
    """A entrada da pessoa na call `chave` se este socket está mesmo nela, senão None."""
    atual = _call_por_sid.get(request.sid)
    if not atual or atual[0] != chave:
        return None
    meta = _meta_call.get(atual)
    if not meta or meta['usuario_id'] != usuario.id:
        return None
    return next((p for p in participantes_call.get(chave, []) if p['peer_id'] == atual[1] and p['usuario_id'] == usuario.id), None)


def _presentes(chave):
    return {p['usuario_id'] for p in participantes_call.get(chave, [])}


def montar_estado(chave):
    """Estado pronto pra mandar ao cliente (ou `ativa: False` se não há atividade)."""
    atv = atividades.da_call(chave)
    if not atv:
        return {'canal_id': chave, 'ativa': False}
    est = atv.estado()
    presentes = _presentes(chave)
    for cor, j in est['jogadores'].items():
        if j:
            j['presente'] = j['id'] in presentes
    est['canal_id'] = chave
    est['ativa'] = True
    return est


def avisar(chave):
    """Manda o estado a TODOS que estão na call."""
    socketio.emit('atividade_estado', montar_estado(chave), to=f"voz_{chave}")


def enviar_estado(chave, sid):
    """Só pra um socket (quem acabou de entrar na call, ou pediu de novo depois de reconectar)."""
    if atividades.da_call(chave):
        socketio.emit('atividade_estado', montar_estado(chave), to=sid)


def ao_sair_da_call(chave, usuario_id, avisar_todos=True):
    """Chamado por `_tirar_da_call`: call vazia apaga a atividade; senão libera a cadeira de quem saiu antes do jogo começar."""
    atv = atividades.da_call(chave)
    if not atv:
        return
    if not participantes_call.get(chave):
        atividades.encerrar(chave)
        return
    if usuario_id is not None and atv.lado_de(usuario_id) and atv.partida is None:
        atv.levantar(usuario_id)
    if avisar_todos:
        avisar(chave)


def _recusar(chave, msg):
    socketio.emit('atividade_erro', {'canal_id': chave, 'msg': msg}, to=request.sid)
    enviar_estado(chave, request.sid)


def _podar(d, agora):
    """Os freios guardam uma hora por socket; esquece os velhos pra o dicionário não crescer pra sempre."""
    if len(d) > 500:
        for k in [k for k, v in d.items() if agora - v > 60]:
            d.pop(k, None)


FREIO_ACAO_S = 0.3        # uma ação (iniciar, sentar) por socket a cada 0,3 s
FREIO_LANCE_S = 0.15      # lances: um a cada 0,15 s


def _freio(segundos=None):
    agora = time.time()
    if agora - _ultima_acao.get(request.sid, 0) < (FREIO_ACAO_S if segundos is None else segundos):
        return True
    _ultima_acao[request.sid] = agora
    _podar(_ultima_acao, agora)
    return False


@socketio.on('atividade_pedir')
def atividade_pedir(dados=None):
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    chave = _chave(dados.get('canal_id'))
    if chave is None or not _participante(chave, usuario):
        return
    socketio.emit('atividade_estado', montar_estado(chave), to=request.sid)


@socketio.on('atividade_iniciar')
def atividade_iniciar(dados=None):
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    chave = _chave(dados.get('canal_id'))
    tipo = dados.get('tipo')
    if chave is None or tipo not in atividades.TIPOS_ATIVIDADE or _freio():
        return
    eu = _participante(chave, usuario)
    if not eu:
        return
    if eu.get('ouvinte'):
        return _recusar(chave, 'Quem só ouve a call não pode iniciar uma atividade.')
    if atividades.da_call(chave):
        return _recusar(chave, 'Já tem uma atividade rolando nesta call. Termine ela antes de começar outra.')
    atv = atividades.iniciar(chave, tipo, usuario.id)
    atv.sentar(usuario.id, usuario.name, usuario.avatar)      # quem começa já senta (lado sorteado)
    avisar(chave)


@socketio.on('atividade_sentar')
def atividade_sentar(dados=None):
    """lado: 'w' | 'b' | 'qualquer' (sorteia entre os livres) | 'sair' (levanta, só antes da partida começar)."""
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    chave = _chave(dados.get('canal_id'))
    lado = dados.get('lado')
    if chave is None or lado not in ('w', 'b', 'qualquer', 'sair') or _freio():
        return
    eu = _participante(chave, usuario)
    atv = atividades.da_call(chave) if eu else None
    if not atv:
        return
    if lado == 'sair':
        ok, motivo = atv.levantar(usuario.id)
    else:
        if eu.get('ouvinte'):
            return _recusar(chave, 'Quem só ouve a call não pode jogar.')
        ok, motivo = atv.sentar(usuario.id, usuario.name, usuario.avatar, None if lado == 'qualquer' else lado)
    if not ok and motivo:
        return _recusar(chave, motivo)
    avisar(chave)


@socketio.on('atividade_acao')
def atividade_acao(dados=None):
    """Ações da partida: lance (de, para, promocao), desistir, empate (propor), empate_aceitar, empate_recusar, revanche."""
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    chave = _chave(dados.get('canal_id'))
    acao = dados.get('acao')
    if chave is None or acao not in ('lance', 'desistir', 'empate', 'empate_aceitar', 'empate_recusar', 'revanche'):
        return
    if not _participante(chave, usuario):
        return
    atv = atividades.da_call(chave)
    if not atv or atv.tipo != 'xadrez':
        return
    cor = atv.lado_de(usuario.id)
    partida = atv.partida
    if not cor or partida is None:
        return _recusar(chave, 'Você não está jogando esta partida.')

    if acao == 'lance':
        agora = time.time()
        if agora - _ultimo_lance.get(request.sid, 0) < FREIO_LANCE_S:
            return
        _ultimo_lance[request.sid] = agora
        _podar(_ultimo_lance, agora)
        if partida.resultado:
            return _recusar(chave, 'A partida já acabou.')
        if partida.pos.vez != cor:
            return _recusar(chave, 'Não é a sua vez.')
        lance = atividades.lance_de_texto(dados.get('de'), dados.get('para'), dados.get('promocao'))
        if lance is None:
            return _recusar(chave, 'Lance inválido.')
        peca = partida.pos.tab[lance[0]]
        if peca == '.' or (peca.isupper() != (cor == atividades.COR_BRANCA)):
            return _recusar(chave, 'Essa peça não é sua.')
        ok, motivo = partida.jogar(*lance)
        if not ok:
            return _recusar(chave, motivo)
    elif acao == 'desistir':
        if partida.resultado:
            return
        partida.desistir(cor)
    elif acao == 'empate':
        if partida.resultado or partida.empate_de:
            return
        partida.empate_de = cor
    elif acao == 'empate_aceitar':
        if partida.resultado or not partida.empate_de or partida.empate_de == cor:
            return
        partida.empatar()
    elif acao == 'empate_recusar':
        if partida.resultado or not partida.empate_de or partida.empate_de == cor:
            return
        partida.empate_de = None
    elif acao == 'revanche':
        if not atv.revanche():
            return
    atv.seq += 1
    avisar(chave)


@socketio.on('atividade_encerrar')
def atividade_encerrar(dados=None):
    """Fecha a atividade pra todos. Pode: quem iniciou, quem está sentado, ou qualquer um da call se nenhum deles está mais nela."""
    usuario = usuario_logado()
    if not usuario or not isinstance(dados, dict):
        return
    chave = _chave(dados.get('canal_id'))
    if chave is None or not _participante(chave, usuario):
        return
    atv = atividades.da_call(chave)
    if not atv:
        return
    donos = {atv.iniciador_id} | {uid for uid in atv.lados.values() if uid}
    if usuario.id not in donos and donos & _presentes(chave):
        return _recusar(chave, 'Só quem começou ou quem está jogando pode encerrar.')
    atividades.encerrar(chave)
    avisar(chave)
