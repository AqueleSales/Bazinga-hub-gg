"""Eventos dos DADOS PESSOAIS (Rodada 40). A regra (gramática fechada, limites, SystemRandom) está em dados.py.

  dados_rolar {tipo?: 'rolagem'|'moeda'|'sorteio', expr? | grupos?: [{dado, qtd}], mod?, qtd?, publico?: bool, canal_id?: int}
      -> dados_resultado {id, tipo, texto, expr, grupos, mod, total, moedas, quem, em, visivel: {call, canal, aviso}}   (SÓ pra quem pediu: este socket)
      -> dados_publico {mesmo resultado}                                                                              (a call, SÓ se `publico` e a pessoa está nela)
      -> uma mensagem normal no canal de texto `canal_id` (SÓ se `publico`), pelo MESMO caminho de `enviar_mensagem` (permissão, tipo de canal, Guardião)
  Erro de regra volta como `dados_erro {msg}`.

PRIVADO é o padrão. A rolagem sempre é sorteada AQUI (SystemRandom, nunca no navegador: o cliente só anima o número que o servidor devolveu), mas a resposta
vai só pro socket que pediu: sem sala, sem estado compartilhado, sem ocupar a vaga de atividade da call. Quem escolhe mostrar (o olho aberto no painel) manda
`publico: true`: a call vê um aviso curto com o resultado e, se a pessoa escolheu um canal, o resultado vira uma mensagem nele. Quem só ouve a call (plateia do
palco, ouvinte) rola à vontade mas não mostra pra call (igual ao soundboard e às atividades).
"""
import itertools
import time

from flask import request, session

from .seguranca import emit
from . import dados as regras, socketio
from .models import db
from .events import usuario_logado, _call_por_sid, _meta_call, participantes_call, lidar_com_mensagem, canal_permitido

FREIO_ROLAR_S = 0.3         # uma rolagem a cada 0,3 s por pessoa (o botão "Rolar" já espera a resposta)
FREIO_CANAL_S = 3.0         # e uma mensagem de rolagem no chat a cada 3 s
_ultimo = {}                # pessoa -> instante
_ultimo_canal = {}
_ids = itertools.count(1)   # id de cada rolagem: o painel não anima duas vezes a mesma


def _dict(d):
    return d if isinstance(d, dict) else {}


def _eu_na_call():
    """(chave, participante) se ESTE socket está de verdade numa call (e é a pessoa da sessão), senão (None, None). Não consulta o banco."""
    minha = _call_por_sid.get(request.sid)
    meta = _meta_call.get(minha) if minha else None
    if not meta or meta.get('usuario_id') != session.get('user_id'):
        return None, None
    eu = next((p for p in participantes_call.get(minha[0], []) if p['peer_id'] == minha[1]), None)
    return (minha[0], eu) if eu else (None, None)


def _poda(d, agora):
    if len(d) > 2000:
        for k in [k for k, v in d.items() if agora - v > 120]:
            d.pop(k, None)


@socketio.on('dados_rolar')
def dados_rolar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    agora = time.monotonic()
    if agora - _ultimo.get(usuario.id, 0) < FREIO_ROLAR_S:
        return
    _ultimo[usuario.id] = agora
    _poda(_ultimo, agora)
    try:
        chave, eu = _eu_na_call()
        if d.get('tipo') == 'sorteio':
            if not chave:
                raise regras.ErroRolagem('Entre numa call pra sortear alguém.')
            vistos, nomes = set(), []
            for p in participantes_call.get(chave, []):
                if p.get('usuario_id') not in vistos:
                    vistos.add(p.get('usuario_id'))
                    nomes.append(p.get('nome') or '')
            entrada = regras.sortear(nomes)
        else:
            entrada = regras.rolar(d)
    except regras.ErroRolagem as e:
        emit('dados_erro', {'msg': str(e)})
        return
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO DADOS] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível rolar agora: {e}'})
        return
    entrada['id'] = next(_ids)
    entrada['quem'] = {'id': usuario.id, 'nome': usuario.name, 'avatar': usuario.avatar}

    # --- quem vê ---
    publico = d.get('publico') is True
    visivel = {'call': False, 'canal': None, 'aviso': ''}
    publicar_na_call = False
    if publico:
        if chave and eu and d.get('na_call') is not False:       # `na_call: false` = a pessoa só quer postar no canal, sem o aviso na call
            if not eu.get('ouvinte'):
                publicar_na_call = True
                visivel['call'] = True
            else:
                visivel['aviso'] = 'Você só ouve esta call, então a rolagem ficou só pra você.'
        canal_id = d.get('canal_id')
        if canal_id is not None and not isinstance(canal_id, bool):
            visivel['canal'] = False
            try:
                canal = canal_permitido(usuario, canal_id)
            except Exception as e:
                canal = None
                print(f"[ERRO DADOS CANAL] {e}")
            if not canal:
                visivel['aviso'] = (visivel['aviso'] + ' ' if visivel['aviso'] else '') + 'Não deu pra postar no canal escolhido (sem acesso).'
            elif agora - _ultimo_canal.get(usuario.id, 0) < FREIO_CANAL_S:
                visivel['aviso'] = (visivel['aviso'] + ' ' if visivel['aviso'] else '') + 'Calma: a mensagem no canal só sai uma vez a cada poucos segundos.'
            else:
                _ultimo_canal[usuario.id] = agora
                _poda(_ultimo_canal, agora)
                visivel['canal'] = canal.id

    # 1) a resposta pra quem rolou vem primeiro (é o que ele está esperando)
    emit('dados_resultado', {**entrada, 'visivel': visivel}, to=request.sid)
    # 2) a call vê (um aviso curto; quem rolou já tem o resultado no painel)
    if publicar_na_call:
        socketio.emit('dados_publico', entrada, to=f"voz_{chave}", skip_sid=request.sid)
    # 3) o canal de texto: uma mensagem normal, pelo caminho de sempre (permissão do canal, tipo de canal, Guardião, @, XP com os mesmos freios)
    if visivel['canal']:
        try:
            enviar = getattr(lidar_com_mensagem, '__wrapped__', lidar_com_mensagem)      # o handler "cru": o limite de eventos já foi cobrado do dados_rolar
            enviar({'canal_id': visivel['canal'], 'texto': regras.texto_para_canal(usuario.name, entrada)})
        except Exception as e:
            db.session.rollback()
            print(f"[ERRO DADOS MENSAGEM] {e}")
