"""Eventos de Socket.IO do ACERVO (figurinhas e sons). A regra está em acervo.py; o arquivo entra por HTTP (acervo_routes.py).

  acervo_listar {server_id?}           -> acervo {meus, servidor, cotas, presets, som_entrada}  (só pra quem pediu)
  acervo_apagar {id} · acervo_renomear {id, nome, emoji}   -> acervo_mudou {server_id}       (pras abas de quem mexeu, ou o servidor, regra 6)
  som_entrada_definir {valor}          -> som_entrada_ok {valor}                               (todas as abas de quem mudou)
  soundboard_tocar {canal_id, item_id} -> soundboard_tocou {...}                               (a call inteira ouve; ZERO consulta ao banco)
  soundboard_aquecer {canal_id, ids}   -> soundboard_precarregar {por_id, ids}                 (o resto da call baixa esses sons antes do 1º toque)
Erro de regra volta como `acervo_erro {msg}`; erro inesperado, como `erro_bazinga` (regra 3).

Soundboard (o servidor decide, regra 4): só toca quem está de verdade na call (e não de ouvinte); o som tem que ser APROVADO e ser do próprio
acervo da pessoa ou do servidor DESSA call; intervalo de 0,7 s por pessoa e no máximo 20 sons a cada 20 s na call inteira.
O áudio é entregue pelo arquivo (/api/acervo/<id>/arquivo) e cada cliente toca no próprio volume, ou cala (por pessoa e por aparelho).
"""
import time

from flask import request, session

from .seguranca import emit
from . import acervo, socketio
from .models import db
from .events import usuario_logado, sala_pessoal, sala_servidor, _call_por_sid, _meta_call, participantes_call

INTERVALO_PESSOA_S = 0.7          # um som a cada 0,7 s por pessoa (antes 2,5 s: parecia que o botão tinha parado de funcionar)
TETO_CALL = (20, 20.0)            # 20 sons a cada 20 s na call inteira
INTERVALO_AQUECER_S = 8.0         # a lista de sons que os outros baixam: no máximo uma vez a cada 8 s por pessoa
MAX_AQUECER = 36                  # 12 sons pessoais + 24 do servidor é tudo que cabe no painel
_ultimo = {}                      # pessoa -> instante
_ultimo_aquecer = {}              # pessoa -> instante
_historico = {}                   # chave da call -> [instantes]


def _dict(d):
    return d if isinstance(d, dict) else {}


def _avisar_mudou(item_ou_servidor, usuario):
    server_id = getattr(item_ou_servidor, 'server_id', item_ou_servidor)
    emit('acervo_mudou', {'server_id': server_id}, to=sala_servidor(server_id) if server_id else sala_pessoal(usuario.id))


@socketio.on('acervo_listar')
def acervo_listar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        emit('acervo', acervo.listar(usuario, _dict(dados).get('server_id')))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ACERVO LISTAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível abrir o acervo: {e}'})


@socketio.on('acervo_apagar')
def acervo_apagar(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        item = acervo.AcervoItem.query.get(int(_dict(dados).get('id')))
        server_id = item.server_id if item else None
        acervo.apagar(usuario, _dict(dados).get('id'))
        _avisar_mudou(server_id, usuario)
    except acervo.ErroAcervo as e:
        emit('acervo_erro', {'msg': str(e)})
    except (TypeError, ValueError):
        return
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ACERVO APAGAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar: {e}'})


@socketio.on('acervo_renomear')
def acervo_renomear(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    d = _dict(dados)
    try:
        item = acervo.renomear(usuario, d.get('id'), d.get('nome'), d.get('emoji'))
        _avisar_mudou(item, usuario)
    except acervo.ErroAcervo as e:
        emit('acervo_erro', {'msg': str(e)})
    except (TypeError, ValueError):
        return
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ACERVO RENOMEAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível renomear: {e}'})


@socketio.on('som_entrada_definir')
def som_entrada_definir(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    if 'valor' not in _dict(dados):
        return                                   # payload quebrado não pode zerar o som: pra voltar ao padrão o cliente manda valor null de propósito
    try:
        novo = acervo.definir_som_entrada(usuario, _dict(dados).get('valor'))
        # quem já está numa call leva o som novo na próxima vez que alguém entrar depois dele; a lista da call guarda o valor
        for (chave, peer), meta in list(_meta_call.items()):
            if meta['usuario_id'] == usuario.id:
                for p in participantes_call.get(chave, []):
                    if p['peer_id'] == peer:
                        p['som_entrada'] = novo
        emit('som_entrada_ok', {'valor': novo}, to=sala_pessoal(usuario.id))
    except acervo.ErroAcervo as e:
        emit('acervo_erro', {'msg': str(e)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO SOM ENTRADA] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível trocar o som de entrada: {e}'})


def _na_call(d):
    """(chave, meta, participante) se ESTE socket está de verdade na call pedida e é a pessoa da sessão; senão None. Não toca no banco: a entrada na call já
    conferiu quem é a pessoa e se ela podia entrar (é por isso que o toque do soundboard não precisa reler a conta)."""
    chave = str(d.get('canal_id'))
    minha = _call_por_sid.get(request.sid)
    if not minha or minha[0] != chave:
        return None
    meta = _meta_call.get(minha)
    if not meta or meta.get('usuario_id') != session.get('user_id'):
        return None
    eu = next((p for p in participantes_call.get(chave, []) if p['peer_id'] == minha[1]), None)
    return (chave, meta, eu) if eu else None


@socketio.on('soundboard_tocar')
def soundboard_tocar(dados=None):
    """Toca um som pra call inteira. É o caminho QUENTE: nenhuma consulta ao banco (o som vem do cache de `acervo.som_info`, o nome de quem toca vem da lista
    da call) e a resposta sai direto pra sala da call. Em produção cada consulta era uma ida ao Neon antes de o som sair."""
    d = _dict(dados)
    try:
        achou = _na_call(d)
        if not achou:
            return
        chave, meta, eu = achou
        pessoa_id = meta['usuario_id']
        if eu.get('ouvinte'):
            emit('acervo_erro', {'msg': 'Você está só ouvindo nesta call, então não pode tocar sons.'})
            return
        agora = time.monotonic()
        if agora - _ultimo.get(pessoa_id, 0) < INTERVALO_PESSOA_S:
            return                                              # clique duplo/insistência: ignora em silêncio
        recentes = [t for t in _historico.get(chave, []) if agora - t < TETO_CALL[1]]
        if len(recentes) >= TETO_CALL[0]:
            emit('acervo_erro', {'msg': 'Muitos sons ao mesmo tempo nesta call. Espere um pouco.'})
            return
        info = acervo.som_info(d.get('item_id'))
        if info and info['escopo'] == 'servidor' and info['server_id'] != meta.get('server_id'):
            emit('acervo_erro', {'msg': 'Os sons de um servidor só tocam nas calls dele.'})
            return
        if not info or not acervo._usavel_na_call(info, pessoa_id, meta.get('server_id')):
            emit('acervo_erro', {'msg': 'Esse som não está disponível (ainda em análise, apagado ou de outro servidor).'})
            return
        _ultimo[pessoa_id] = agora
        recentes.append(agora)
        _historico[chave] = recentes
        if len(_ultimo) > 2000:
            for k in [k for k, v in _ultimo.items() if agora - v > 120]:
                _ultimo.pop(k, None)
        socketio.emit('soundboard_tocou', {'canal_id': chave, 'item_id': info['id'], 'nome': info['nome'], 'emoji': info['emoji'], 'dur_ms': info['dur_ms'],
                                           'por_id': pessoa_id, 'por_nome': eu.get('nome') or 'Alguém'}, to=f"voz_{chave}")
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO SOUNDBOARD] {e}")


@socketio.on('soundboard_aquecer')
def soundboard_aquecer(dados=None):
    """Quem abre o soundboard diz quais sons está mostrando; o servidor confere (uma consulta só pros que não estão no cache) e avisa o resto da call, que já
    baixa e decodifica esses sons em segundo plano. Assim o 1º toque de cada som é instantâneo pra todo mundo (antes o ouvinte baixava o arquivo NA HORA)."""
    d = _dict(dados)
    try:
        achou = _na_call(d)
        if not achou:
            return
        chave, meta, eu = achou
        pessoa_id = meta['usuario_id']
        agora = time.monotonic()
        if eu.get('ouvinte') or agora - _ultimo_aquecer.get(pessoa_id, 0) < INTERVALO_AQUECER_S:
            return
        ids = d.get('ids') if isinstance(d.get('ids'), list) else []
        validos = acervo.sons_para_call(pessoa_id, ids, meta.get('server_id'), limite=MAX_AQUECER)
        _ultimo_aquecer[pessoa_id] = agora
        if len(_ultimo_aquecer) > 2000:
            for k in [k for k, v in _ultimo_aquecer.items() if agora - v > 300]:
                _ultimo_aquecer.pop(k, None)
        if validos:
            socketio.emit('soundboard_precarregar', {'canal_id': chave, 'por_id': pessoa_id, 'ids': validos}, to=f"voz_{chave}", skip_sid=request.sid)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO SOUNDBOARD AQUECER] {e}")
