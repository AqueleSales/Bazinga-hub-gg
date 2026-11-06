"""Defesas contra abuso (Rodada 38, auditoria "20 verificações de segurança"). Sem dependência do resto do app (só Flask/Flask-SocketIO), então qualquer
módulo pode importar daqui.

1. CSRF: `verificar_origem()` barra POST/PUT/DELETE vindo de OUTRO site (o cookie de sessão é `SameSite=Lax`, o que já cobre o navegador moderno; isto é a
   segunda camada, pra navegador antigo e pra quem um dia trocar o cookie pra `SameSite=None`).
2. Erro que não vaza: `emit()` (no lugar do `flask_socketio.emit`) e `mensagem_publica()` trocam o texto de erro de BANCO (nome de tabela, trecho do SQL,
   usuário do Postgres) por "erro interno (código X)" e deixam o texto inteiro só no log do servidor. A regra 3 do CLAUDE.md (mostrar `{e}` pra poder
   diagnosticar) continua valendo pra erro comum; o que muda é que o erro de banco não chega mais a quem fez o ataque.
3. Flood no socket (o app tem ~190 eventos e nenhum teto geral): balde de fichas por CONEXÃO e por PESSOA (somando todas as abas), balde só de mensagens
   (a mensagem é a que se espalha pra sala inteira), teto de conexões simultâneas (pessoa logada e sem login), conexões novas por minuto por IP e uma
   PUNIÇÃO (derruba a conexão e recusa a pessoa/IP por 2 min) pra quem insiste depois de barrado. Tudo em memória (o app roda com `-w 1`).
   `instalar(socketio)` embrulha o `socketio.on` ANTES de os handlers serem registrados: nenhum handler precisa mudar.
4. Erro de handler: `socketio.on_error_default` (log com o rastro, `rollback`, resposta genérica) no lugar do rastro cru subindo pro engine.
Desligar: `LIMITE_EVENTOS=0` (só o item 3; os outros são sempre ligados).
"""
import functools
import inspect
import os
import re
import threading
import time
import traceback
import uuid
from collections import deque
from urllib.parse import urlparse

import flask_socketio
from flask import request, session, jsonify, redirect

from . import limites

# ---------------------------------------------------------------------------------------------------------------------
# 1. CSRF: a origem do pedido tem que ser o próprio app
# ---------------------------------------------------------------------------------------------------------------------
_METODOS_SEGUROS = ('GET', 'HEAD', 'OPTIONS')
_SEM_ORIGEM = ('/webhooks/',)          # quem chama é o servidor do gateway: não é navegador, não manda Origin


def _hosts_permitidos():
    extras = [urlparse(o.strip()).netloc for o in (os.getenv('ORIGENS_PERMITIDAS') or '').split(',') if o.strip()]
    return {request.host.lower(), *[e.lower() for e in extras if e]}


def verificar_origem():
    """`before_request`. Devolve None (deixa passar) ou a resposta de recusa.

    - POST/PUT/PATCH/DELETE com `Origin` de outro endereço: recusado. `Origin: null` (iframe sandbox, arquivo local, redirecionamento entre sites) também.
    - Sem `Origin` mas com `Sec-Fetch-Site: cross-site`/`same-site`: recusado (o navegador avisa de onde veio mesmo quando omite o Origin).
    - Sem nenhum dos dois: não é navegador de gente (curl, o gateway, um script): sem cookie ambiente não há o que forjar, passa.
    - `/auth/logout` é GET (o app inteiro linka pra ele): vindo de outro site (`<img src>` num fórum) a pessoa NÃO é deslogada."""
    if request.method in _METODOS_SEGUROS:
        if request.path == '/auth/logout' and request.headers.get('Sec-Fetch-Site') == 'cross-site':
            return redirect('/entrar')
        return None
    if request.path.startswith(_SEM_ORIGEM):
        return None
    origem = request.headers.get('Origin')
    if origem is not None:
        if (urlparse(origem).netloc or '').lower() in _hosts_permitidos():
            return None
        return _recusar()
    if request.headers.get('Sec-Fetch-Site') in ('cross-site', 'same-site'):
        return _recusar()
    return None


def _recusar():
    return jsonify({'erro': 'Origem não permitida.', 'error': 'Origem não permitida.'}), 403


# ---------------------------------------------------------------------------------------------------------------------
# 2. Erro que não vaza
# ---------------------------------------------------------------------------------------------------------------------
# Marcas de erro de banco/infra: SQLAlchemy sempre escreve `[SQL: ...]` e `Background on this error at: https://sqlalche.me`; o driver escreve o nome da
# tabela e da coluna; o Neon, o endereço do servidor. Nada disso é da conta de quem está do outro lado da tela.
_RE_VAZAMENTO = re.compile(
    r'\(psycopg2|\(sqlite3|\(pymysql|\[SQL:|\[parameters:|sqlalche\.me|Traceback|File ".*", line \d+|DETAIL:|HINT:|'
    r'relation ".*" does not exist|no such (table|column)|column .* (does not exist|of relation)|violates (unique|foreign key|not-null|check) constraint|'
    r'OperationalError|ProgrammingError|IntegrityError|DataError|InternalError|InvalidRequestError|PendingRollbackError|'
    r'connection to server|could not connect|SSL (SYSCALL|error)|password authentication|neon\.tech|postgres(ql)?://|sqlite:///|'
    r'[A-Za-z]:\\|/(home|opt|usr|app|var|srv)/[\w./-]+\.py', re.I)


def mensagem_publica(texto, registrar=True):
    """O texto que PODE ir pra tela. Se tiver cara de erro de banco/caminho de arquivo, vira `<começo da frase>: erro interno (código XXXXXX)` e o
    original fica no log com o mesmo código (é como o dono acha a causa no Render sem mostrar nada pra ninguém)."""
    texto = '' if texto is None else str(texto)
    if not _RE_VAZAMENTO.search(texto):
        return texto
    codigo = uuid.uuid4().hex[:6].upper()
    if registrar:
        print(f'[ERRO PUBLICO {codigo}] {texto[:1500]}')
    inicio = texto.split(': ', 1)[0] if ': ' in texto else ''
    if not inicio or len(inicio) > 120 or _RE_VAZAMENTO.search(inicio):
        inicio = 'Algo deu errado'
    return f'{inicio}: erro interno (código {codigo}).'


def erro_publico(e, prefixo='Algo deu errado'):
    """Pra `jsonify({'erro': ...})` nas rotas HTTP: `erro_publico(e, 'Não consegui enviar o arquivo')`."""
    return mensagem_publica(f'{prefixo}: {e}')


def emit(evento, *args, **kw):
    """`flask_socketio.emit` que passa o `erro_bazinga` pelo `mensagem_publica`. Os outros eventos seguem inalterados."""
    if evento == 'erro_bazinga' and args and isinstance(args[0], dict) and isinstance(args[0].get('msg'), str):
        args = ({**args[0], 'msg': mensagem_publica(args[0]['msg'])},) + args[1:]
    return flask_socketio.emit(evento, *args, **kw)


# ---------------------------------------------------------------------------------------------------------------------
# 3. Flood no socket
# ---------------------------------------------------------------------------------------------------------------------
CAP_CONEXAO, REPOE_CONEXAO = 100, 40.0         # fichas por conexão (aba): rajada de 100, 40 por segundo depois (o app abre com ~20 pedidos de uma vez)
CAP_PESSOA, REPOE_PESSOA = 220, 80.0           # a pessoa inteira (todas as abas)
CAP_MENSAGEM, REPOE_MENSAGEM = 10, 2.0         # só mensagem: rajada de 10, depois 2 por segundo (ninguém digita mais rápido, e a mensagem vai pra sala toda)
MAX_CONEXOES_PESSOA = 40                       # abas + aparelhos de UMA conta. Folgado de propósito: celular com rede ruim reconecta a cada poucos segundos e a conexão velha só some do servidor quando o ping vence (~45 s)
MAX_CONEXOES_SEM_LOGIN_IP = 40                 # sockets sem login (que não fazem nada) por IP
MAX_CONEXOES_SEM_LOGIN_TOTAL = 500             # e no total (o worker aguenta ~1000)
CONEXOES_NOVAS_POR_MINUTO = 90                 # por IP (esquerda); a ponta direita ganha FATOR_BORDA vezes isso
ESTOURO_PARA_PUNIR = 250                       # eventos barrados em 15 s antes de derrubar a conexão e recusar a volta
PUNICAO_SEGUNDOS = 120

EVENTOS_DE_MENSAGEM = frozenset({'enviar_mensagem', 'enviar_mensagem_direta', 'bazar_mensagem', 'editar_mensagem', 'editar_mensagem_direta'})
_PREFIXOS_CAROS = ('criar_', 'plantar_', 'copiar_', 'denunciar', 'enviar_pedido', 'aplicar_', 'comprar_', 'transferir_')      # criam coisa no banco: pesam 6
_PREFIXOS_MEDIOS = ('bazar_', 'entrega', 'musica_', 'explorar', 'conexoes_', 'fila_', 'atividade_', 'cargo', 'canal_', 'prestigio_')      # pesam 3
_RE_TEMP_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')

_baldes = {}                    # chave -> [fichas, último uso]
_estouros = {}                  # sid -> [quantos barrados, início da janela]
_punidos = {}                   # 'u<id>' / 'ip<ip>' -> até quando
_aviso_em = {}                  # sid -> último aviso "calma" mostrado
_conexoes = {}                  # sid -> (uid ou None, ip esquerdo)
_trava = threading.Lock()
ULTIMOS_ERROS = deque(maxlen=60)    # (evento, tipo do erro, texto): os testes leem daqui; o log do servidor mostra o rastro inteiro


def ligado():
    return os.getenv('LIMITE_EVENTOS', '1') != '0'


def _custo(evento):
    if evento.startswith(_PREFIXOS_CAROS):
        return 6
    if evento.startswith(_PREFIXOS_MEDIOS):
        return 3
    return 1


def _gastar(chave, custo, capacidade, reposicao, agora):
    b = _baldes.get(chave)
    if b is None:
        b = _baldes[chave] = [float(capacidade), agora]
    else:
        b[0] = min(float(capacidade), b[0] + (agora - b[1]) * reposicao)
        b[1] = agora
    if b[0] >= custo:
        b[0] -= custo
        return True
    return False


def _podar_baldes(agora):
    if len(_baldes) > 20000:
        for k in [k for k, b in _baldes.items() if agora - b[1] > 120]:
            _baldes.pop(k, None)
        if len(_baldes) > 40000:
            _baldes.clear()
    if len(_punidos) > 5000:
        for k in [k for k, ate in _punidos.items() if ate < agora]:
            _punidos.pop(k, None)


def punir(chave, segundos=PUNICAO_SEGUNDOS, agora=None):
    agora = time.time() if agora is None else agora
    with _trava:
        _punidos[chave] = agora + segundos


def esta_punido(uid, ip, agora=None):
    agora = time.time() if agora is None else agora
    with _trava:
        for chave in ((f'u{uid}' if uid else None), f'ip{ip}'):
            if chave and _punidos.get(chave, 0) > agora:
                return True
    return False


def admitir_conexao(agora=None):
    """Chamado no começo do `connect`. False = recusa a conexão (nenhum handler roda)."""
    if not ligado():
        return True
    agora = time.time() if agora is None else agora
    uid = session.get('user_id')
    esq, dir_ = limites.ips_do_cliente()
    if esta_punido(uid, esq, agora):
        return False
    ok, _ = limites.permitido(limites._IDX_CONEXAO_SOCKET, f'ip{esq}', CONEXOES_NOVAS_POR_MINUTO, 60, agora)
    if ok:
        ok, _ = limites.permitido(limites._IDX_CONEXAO_SOCKET, f'bd{dir_}', CONEXOES_NOVAS_POR_MINUTO * limites.FATOR_BORDA, 60, agora)
    if not ok:
        return False
    with _trava:
        if uid:
            if sum(1 for u, _i in _conexoes.values() if u == uid) >= MAX_CONEXOES_PESSOA:
                return False
        else:
            if sum(1 for u, i in _conexoes.values() if u is None and i == esq) >= MAX_CONEXOES_SEM_LOGIN_IP:
                return False
            if sum(1 for u, _i in _conexoes.values() if u is None) >= MAX_CONEXOES_SEM_LOGIN_TOTAL:
                return False
    return True


def registrar_conexao(sid):
    uid = session.get('user_id')
    with _trava:
        _conexoes[sid] = (uid, limites.ips_do_cliente()[0])


def liberar_conexao(sid):
    with _trava:
        _conexoes.pop(sid, None)
        _estouros.pop(sid, None)
        _aviso_em.pop(sid, None)
        _baldes.pop(('sid', sid), None)


def conexoes_abertas():
    with _trava:
        return len(_conexoes)


def evento_permitido(evento, agora=None):
    """Gasta as fichas do evento. Devolve 'ok', 'barrado' (descarta este evento) ou 'punir' (derruba a conexão). Chamado antes de cada handler."""
    if not ligado():
        return 'ok'
    agora = time.monotonic() if agora is None else agora
    sid = getattr(request, 'sid', None) or '?'
    uid = session.get('user_id')
    custo = _custo(evento)
    with _trava:
        _podar_baldes(agora)
        bom = _gastar(('sid', sid), custo, CAP_CONEXAO, REPOE_CONEXAO, agora)
        if bom and uid:
            bom = _gastar(('pessoa', uid), custo, CAP_PESSOA, REPOE_PESSOA, agora)
        if bom and evento in EVENTOS_DE_MENSAGEM:
            bom = _gastar(('msg', uid or sid), 1, CAP_MENSAGEM, REPOE_MENSAGEM, agora)
        if bom:
            return 'ok'
        e = _estouros.get(sid)
        if e is None or agora - e[1] > 15:
            e = _estouros[sid] = [0, agora]
        e[0] += 1
        return 'punir' if e[0] >= ESTOURO_PARA_PUNIR else 'barrado'


def _avisar_calma(evento, dados):
    """Um aviso a cada 4 s por conexão (senão o aviso vira o próprio flood) e, se era uma mensagem, desfaz a bolha otimista do cliente."""
    sid = getattr(request, 'sid', None)
    agora = time.monotonic()
    with _trava:
        if agora - _aviso_em.get(sid, -99) < 4:
            return
        _aviso_em[sid] = agora
    try:
        if evento in EVENTOS_DE_MENSAGEM and isinstance(dados, dict) and _RE_TEMP_ID.match(str(dados.get('temp_id') or '')):
            flask_socketio.emit('mensagem_recusada', {'temp_id': str(dados['temp_id'])}, to=sid)
        flask_socketio.emit('erro_bazinga', {'msg': 'Calma! Você está fazendo coisa demais em pouco tempo. Espere um instante.'}, to=sid)
    except Exception:
        pass


def _no_flood():
    """A conexão estourou de vez: derruba e recusa a volta (pessoa e IP) por `PUNICAO_SEGUNDOS`."""
    uid = session.get('user_id')
    if uid:
        punir(f'u{uid}')
    punir(f'ip{limites.ips_do_cliente()[0]}')
    print(f'[SEGURANCA] flood no socket: conexão {getattr(request, "sid", "?")} derrubada (pessoa {uid}, ip {limites.ips_do_cliente()[0]})')
    try:
        flask_socketio.disconnect()
    except Exception:
        pass


def _embrulhar_evento(evento, f):
    params = list(inspect.signature(f).parameters.values())
    posicionais = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    aceita_varios = any(p.kind == p.VAR_POSITIONAL for p in params)
    n = len(posicionais)

    @functools.wraps(f)
    def embrulho(*args, **kw):
        veredito = evento_permitido(evento)
        if veredito == 'ok':
            # Todo handler do app recebe UM dict (`dados`). Texto, lista, número ou nada no lugar dele derrubava o handler no primeiro `.get`; e
            # argumento a mais (um cliente que manda 5 em vez de 1) dava TypeError. Aqui vira `{}` / é cortado: o handler responde como a "pedido vazio".
            if not aceita_varios:
                args = args[:n]
            if n >= 1 and (not args or not isinstance(args[0], dict)):
                args = ({},) + args[1:]
            return f(*args, **kw)
        if veredito == 'punir':
            _no_flood()
            return None
        _avisar_calma(evento, args[0] if args else None)
        return None
    return embrulho


def _embrulhar_conexao(f):
    aceita = len(inspect.signature(f).parameters) > 0

    @functools.wraps(f)
    def embrulho(auth=None):
        if not admitir_conexao():
            return False
        registrar_conexao(request.sid)
        try:
            ret = f(auth) if aceita else f()
        except BaseException:
            liberar_conexao(request.sid)
            raise
        if ret is False:
            liberar_conexao(request.sid)
        return ret
    return embrulho


def _embrulhar_desconexao(f):
    aceita = len(inspect.signature(f).parameters) > 0

    @functools.wraps(f)
    def embrulho(*args):
        sid = getattr(request, 'sid', None)
        try:
            return f(*args) if aceita else f()
        finally:
            liberar_conexao(sid)
    return embrulho


def _erro_de_handler(e):
    """Qualquer exceção que escape de um handler: log com o rastro (pra o dono achar), `rollback` (uma sessão suja contaminaria o próximo handler), uma
    resposta genérica pra pessoa e NADA do texto da exceção na tela."""
    evento = ((getattr(request, 'event', None) or {}).get('message')) or '?'
    if evento == 'disconnect' and isinstance(e, TypeError):
        # O python-socketio chama o handler de `disconnect` com um argumento a mais (o motivo) e, se der TypeError, repete SEM ele (modo legado). Esse
        # TypeError TEM que subir até lá: engolir aqui fazia o `handle_disconnect` nunca rodar (presença, call e posição no mapa ficavam presas).
        raise e
    ULTIMOS_ERROS.append((evento, type(e).__name__, str(e)[:300]))
    print(f'[ERRO EVENTO {evento}] {type(e).__name__}: {e}')
    traceback.print_exception(type(e), e, e.__traceback__)
    try:
        from .models import db
        db.session.rollback()
    except Exception:
        pass
    if not session.get('user_id'):
        return          # quem não está logado não recebe resposta nenhuma (nem sequer "deu erro": confirmaria que o evento existe)
    try:
        flask_socketio.emit('erro_bazinga', {'msg': 'Algo deu errado do nosso lado. Tente de novo em instantes.'}, to=getattr(request, 'sid', None))
    except Exception:
        pass


HANDSHAKES_POR_MINUTO = 600     # abrir conexão nova (sem `sid` na URL) por IP: generoso (uma faculdade inteira atrás do mesmo IP reconecta de uma vez depois de um deploy)


class LimiteDeHandshake:
    """Middleware WSGI por FORA do Socket.IO. O Flask-SocketIO atende `/socket.io/` antes do Flask, então `before_request` nunca vê esses pedidos e
    quem abre conexão em massa (sem nem logar) passava reto. Só o handshake (URL sem `sid`) é contado: o resto da conversa de uma conexão já aberta
    não pesa. Estourou: 429 seco, que o cliente do Socket.IO trata como erro de conexão e tenta de novo depois."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if (ligado() and limites.ligado() and (environ.get('PATH_INFO') or '').startswith('/socket.io')
                and 'sid=' not in (environ.get('QUERY_STRING') or '') and environ.get('REQUEST_METHOD') != 'OPTIONS'):
            esq, dir_ = limites.ips_de(environ.get('HTTP_X_FORWARDED_FOR'), environ.get('REMOTE_ADDR'))
            ok, espera = limites.permitido(limites._IDX_HANDSHAKE, f'ip{esq}', HANDSHAKES_POR_MINUTO, 60)
            if ok:
                ok, espera = limites.permitido(limites._IDX_HANDSHAKE, f'bd{dir_}', HANDSHAKES_POR_MINUTO * limites.FATOR_BORDA, 60)
            if not ok:
                corpo = b'Muitas conexoes em pouco tempo.'
                start_response('429 Too Many Requests', [('Content-Type', 'text/plain'), ('Content-Length', str(len(corpo))), ('Retry-After', str(espera))])
                return [corpo]
        return self.app(environ, start_response)


def instalar(socketio):
    """Liga tudo no `socketio`. TEM QUE rodar antes de `from . import events` (é lá que os handlers se registram pelo `socketio.on`). Idempotente."""
    if getattr(socketio, '_seguranca_instalada', False):
        return socketio
    socketio._seguranca_instalada = True
    original = socketio.on

    def on(message, namespace=None):
        registrar = original(message, namespace)

        def decorador(f):
            if message == 'connect':
                return registrar(_embrulhar_conexao(f))
            if message == 'disconnect':
                return registrar(_embrulhar_desconexao(f))
            return registrar(_embrulhar_evento(message, f))
        return decorador

    socketio.on = on
    socketio.on_error_default(_erro_de_handler)
    return socketio
