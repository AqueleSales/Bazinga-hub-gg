"""Eventos de Socket.IO das Conexões do perfil (a regra mora em conexoes.py).

Regra 6: salvar/atualizar avisa TODAS as abas da pessoa (`sala_pessoal`), e a busca em segundo plano avisa de novo quando termina (o cartão
da própria pessoa se completa sozinho). Quem olha o perfil dos outros pede `conexoes_do_perfil` ao virar o cartão (sob demanda: nada disso vai
no `connect` nem no `obter_perfil`, que só leva a contagem). Erro de regra volta como `conexoes_erro`; erro inesperado como `erro_bazinga` (regra 3).
Visibilidade (regra 4): as conexões de alguém só saem pra quem convive com a pessoa (mesmo servidor ou amizade), a MESMA regra da bio no cartão.
"""
import time

from flask import current_app, request
from flask_socketio import emit

from . import socketio, conexoes
from .conexoes import ErroConexao
from .models import db, Person, Conexao
from .utils import com_retry
from .events import usuario_logado, sala_pessoal, sao_amigos

_ultimo = {}


def _freio(usuario, chave, intervalo=1.0):
    agora = time.monotonic()
    k = (usuario.id, chave)
    if agora - _ultimo.get(k, 0) < intervalo:
        return True
    _ultimo[k] = agora
    return False


def _freio_avisa(usuario, chave, intervalo, evento='conexoes_erro'):
    """Como _freio, mas AVISA a tela quando barra (senão o botão ficava esperando uma resposta que nunca vem)."""
    if _freio(usuario, chave, intervalo):
        emit(evento, {'msg': 'Calma: espere um instante e tente de novo.', 'indice': None})
        return True
    return False


def _seguro(rotulo, fn, evento='conexoes_erro', extra=None):
    try:
        fn()
    except ErroConexao as e:
        db.session.rollback()
        emit(evento, {'msg': str(e), 'indice': getattr(e, 'indice', None), **(extra or {})})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CONEXOES {rotulo}] {type(e).__name__}: {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível {rotulo}: {e}'})


def carga_do_dono(pessoa_id, linhas=None):
    return {'lista': conexoes.lista_json(pessoa_id, dono=True, linhas=linhas), 'plataformas': conexoes.registro_plataformas(),
            'max': conexoes.MAX_CONEXOES, 'max_faixas': conexoes.MAX_FAIXAS, 'ia': conexoes.ia_disponivel(), 'imagens_ok': list(conexoes.IMAGENS_OK)}


def carga_do_perfil(alvo_id, eu, linhas=None):
    """O que quem OLHA o perfil recebe (o dono vê também o campo `erro`; os outros nunca)."""
    return {'usuario_id': alvo_id, 'lista': conexoes.lista_json(alvo_id, dono=eu, linhas=linhas), 'plataformas': conexoes.registro_plataformas(),
            'imagens_ok': list(conexoes.IMAGENS_OK)}


def _buscar_em_segundo_plano(pessoa_id, ids, espectador_sid=None):
    """Busca (rede) fora do clique: cada conexão que terminar avisa as abas da pessoa com a lista nova e, se foi alguém olhando o perfil que
    disparou a busca, também a quem está olhando (senão o cartão dele ficava em "Buscando..." pra sempre)."""
    if not ids:
        return
    app = current_app._get_current_object()

    def tarefa():
        with app.app_context():
            for cid in ids:
                try:
                    dono = conexoes.atualizar_uma(cid)
                    if dono:
                        socketio.emit('conexoes', carga_do_dono(dono), to=sala_pessoal(dono))
                        if espectador_sid:
                            socketio.emit('conexoes_do_perfil', carga_do_perfil(dono, False), to=espectador_sid)
                except Exception as e:
                    db.session.rollback()
                    print(f"[ERRO CONEXOES tarefa] {type(e).__name__}: {e}")
    socketio.start_background_task(tarefa)


@socketio.on('conexoes_listar')
def conexoes_listar(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'listar', 0.4):
        return

    def fazer():
        linhas = conexoes.listar(usuario.id)
        emit('conexoes', carga_do_dono(usuario.id, linhas))
        _buscar_em_segundo_plano(usuario.id, [c.id for c in linhas if conexoes.precisa_atualizar(c)])
    _seguro('abrir as conexões', fazer)


@socketio.on('conexoes_salvar')
def conexoes_salvar(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio_avisa(usuario, 'salvar', 1.5):
        return

    def fazer():
        ids = conexoes.salvar_lista(usuario, (dados or {}).get('itens'))
        emit('conexoes', carga_do_dono(usuario.id), to=sala_pessoal(usuario.id))
        emit('conexoes_salvas', {'qtd': usuario.conexoes_qtd or 0}, to=sala_pessoal(usuario.id))
        _buscar_em_segundo_plano(usuario.id, ids)
    _seguro('salvar as conexões', fazer)


@socketio.on('conexao_atualizar')
def conexao_atualizar(dados=None):
    usuario = usuario_logado()
    if not usuario or _freio_avisa(usuario, 'atualizar', 0.8):
        return

    def fazer():
        try:
            cid = int((dados or {}).get('id'))
        except (TypeError, ValueError):
            return
        c = com_retry(lambda: Conexao.query.get(cid))
        if not c or c.person_id != usuario.id:
            raise ErroConexao('Conexão não encontrada.')
        if not conexoes.PLATAFORMAS.get(c.tipo, {}).get('busca'):
            return
        if not conexoes.pode_atualizar_agora(cid):
            raise ErroConexao('Calma: dá pra atualizar uma conexão por minuto.')
        _buscar_em_segundo_plano(usuario.id, [cid])
    _seguro('atualizar a conexão', fazer)


def _avisar_fila_mudou(usuario, buscar=True):
    """Regra 6: a playlist mudou, todas as abas da pessoa recebem a lista nova; e se faltam títulos, a busca roda em segundo plano (e avisa de novo no fim)."""
    linhas = conexoes.listar(usuario.id)
    emit('conexoes', carga_do_dono(usuario.id, linhas), to=sala_pessoal(usuario.id))
    if buscar:
        _buscar_em_segundo_plano(usuario.id, [c.id for c in linhas if c.tipo == 'fila' and conexoes.precisa_atualizar(c)])


@socketio.on('fila_adicionar')
def fila_adicionar(dados=None):
    dados = dados if isinstance(dados, dict) else {}                      # (cliente adulterado pode mandar texto/lista)
    """Cola um ou vários links de música/playlist do YouTube (ou YouTube Music) na playlist do perfil."""
    usuario = usuario_logado()
    if not usuario or _freio_avisa(usuario, 'fila', 1.0, 'fila_erro'):
        return

    origem = 'musica' if (dados or {}).get('origem') == 'musica' else None       # de onde veio o pedido (a tela da Música e a aba Conexões ouvem os mesmos eventos)

    def fazer():
        r = conexoes.adicionar_faixas(usuario, (dados or {}).get('url'), criar=bool((dados or {}).get('criar')))
        emit('fila_ok', {'adicionadas': r['adicionadas'], 'avisos': r['avisos'], 'origem': origem})
        _avisar_fila_mudou(usuario)
    _seguro('adicionar à playlist', fazer, 'fila_erro', {'origem': origem})


@socketio.on('fila_remover')
def fila_remover(dados=None):
    dados = dados if isinstance(dados, dict) else {}                      # (cliente adulterado pode mandar texto/lista)
    usuario = usuario_logado()
    if not usuario or _freio_avisa(usuario, 'fila_rm', 0.15, 'fila_erro'):
        return

    def fazer():
        conexoes.remover_faixa(usuario, (dados or {}).get('chave'))
        _avisar_fila_mudou(usuario, buscar=False)
    _seguro('tirar da playlist', fazer, 'fila_erro')


@socketio.on('fila_mover')
def fila_mover(dados=None):
    dados = dados if isinstance(dados, dict) else {}                      # (cliente adulterado pode mandar texto/lista)
    usuario = usuario_logado()
    if not usuario or _freio_avisa(usuario, 'fila_mv', 0.15, 'fila_erro'):
        return

    def fazer():
        conexoes.mover_faixa(usuario, (dados or {}).get('chave'), (dados or {}).get('delta'))
        _avisar_fila_mudou(usuario, buscar=False)
    _seguro('mover na playlist', fazer, 'fila_erro')


@socketio.on('conexoes_do_perfil')
def conexoes_do_perfil(dados=None):
    """As conexões de OUTRA pessoa (ou de si mesma), pro cartão virar de face. Só pra quem convive com ela."""
    usuario = usuario_logado()
    if not usuario or _freio(usuario, 'perfil', 0.3):
        return

    def fazer():
        try:
            alvo_id = int((dados or {}).get('usuario_id'))
        except (TypeError, ValueError):
            return
        alvo = com_retry(lambda: Person.query.get(alvo_id))
        if not alvo:
            return
        eu = alvo.id == usuario.id
        convive = eu or sao_amigos(usuario.id, alvo.id) or bool({s.id for s in usuario.servers} & {s.id for s in alvo.servers})
        if not convive:
            emit('conexoes_do_perfil', {'usuario_id': alvo.id, 'lista': [], 'plataformas': {}, 'restrito': True})
            return
        linhas = conexoes.listar(alvo.id)
        emit('conexoes_do_perfil', carga_do_perfil(alvo.id, eu, linhas))
        velhas = [c.id for c in linhas if conexoes.precisa_atualizar(c)]
        if velhas:
            _buscar_em_segundo_plano(alvo.id, velhas[:4], None if eu else request.sid)     # quem olha também recebe quando terminar (a TTL impede de repetir à toa)
    _seguro('abrir as conexões desse perfil', fazer)
