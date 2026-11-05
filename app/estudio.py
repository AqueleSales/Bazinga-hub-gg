"""Pantheon Estúdio (`/estudio`): a página de CRIAÇÃO de conteúdo do app (efeitos hoje; pacotes, molduras, faixas, nomes, shaders... nas próximas fases).

Fica separada do `/admin` (que é gestão: passe, títulos, denúncias, lojas, moderação). Aqui o admin monta efeitos por camadas OU arrasta uma
animação feita fora do site (Lottie, GIF, WebP, APNG, MP4, WebM), ajusta tamanho, posição e velocidade, e publica: o efeito entra no catálogo
(inventário, passe, "dar a alguém", loja) sem tocar em código.

Quem pode: só admin (o mesmo poder do /admin: `config_app 'admin_ids'`, `python bazar_admin.py admin <@usuario>`). Quem não é admin recebe 404 na página
e 403 na API. Rota que ALTERA algo exige o cabeçalho `X-Requested-With: fetch` (anti-forja de outro site). Os arquivos de arte são servidos pra QUALQUER
pessoa logada (o efeito aparece no perfil de todo mundo), com cache imutável.
"""
import io
from functools import wraps

from flask import Blueprint, Response, abort, jsonify, render_template, request, session
from sqlalchemy import or_
from werkzeug.exceptions import HTTPException

from . import efeitos, estudio_arquivos, pacotes
from .admin import _admin_atual
from .cosmeticos import CATALOGO, CATEGORIAS, DESCONTO_PACOTE, itens_para_conceder
from .estudio_arquivos import ErroArquivo
from .pacotes import ErroPacote
from .models import db, Person, Posse
from .utils import com_retry, comitar_com_retry

estudio_bp = Blueprint('estudio', __name__, url_prefix='/estudio')

TETO_ENVIO = 10 * 1024 * 1024        # requisição do upload: vídeo (6 MB) + capa + folga


class ErroEstudio(Exception):
    """Erro de regra com mensagem que o admin pode ler."""


def so_criador(rota):
    @wraps(rota)
    def envolta(*a, **kw):
        pessoa = _admin_atual()
        if not pessoa:
            if request.path.startswith('/estudio/api/'):
                return jsonify({'erro': 'Só administradores.'}), 403
            abort(404)
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH') and request.headers.get('X-Requested-With') != 'fetch':
            return jsonify({'erro': 'Requisição inválida.'}), 400
        return rota(pessoa, *a, **kw)
    return envolta


@estudio_bp.before_request
def _teto_do_upload():
    # O teto global (5 MB, config.py) barraria um vídeo/GIF maior ANTES da rota rodar. A rota confere o peso de cada tipo.
    if request.method == 'POST' and request.path == '/estudio/api/arquivos':
        request.max_content_length = TETO_ENVIO


def _json():
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def _tratar(fn):
    """Roda `fn` e devolve JSON: erro de regra vira 400 com a mensagem; o resto vira 500 com o motivo (regra 3: nunca em silêncio)."""
    try:
        r = fn()
        return jsonify({'ok': True, **(r if isinstance(r, dict) else {})})
    except HTTPException:
        raise                        # 413 (requisição enorme) etc.: o handler do app responde com JSON e o status certo
    except (efeitos.ErroEfeito, ErroArquivo, ErroPacote, ErroEstudio) as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ESTUDIO] {e}")
        return jsonify({'erro': f'Erro inesperado: {e}'}), 500


@estudio_bp.route('')
@so_criador
def pagina(pessoa):
    resp = render_template('estudio.html', eu={'id': pessoa.id, 'nome': pessoa.name, 'username': pessoa.username or ''})
    return resp, 200, {'Cache-Control': 'no-store'}


# ------------------------------------------------------------
# efeitos (a mesma lógica que morava no /admin; app/efeitos.py valida tudo)
# ------------------------------------------------------------
@estudio_bp.route('/api/efeitos')
@so_criador
def efeitos_listar(pessoa):
    return jsonify({'efeitos': efeitos.listar(), 'esquema': efeitos.esquema_para_cliente(), 'raridades': list(efeitos.RARIDADES),
                    'max_camadas': efeitos.MAX_CAMADAS, 'misturas': list(efeitos.MISTURAS),
                    'precos': {r: {s: efeitos.preco_de_venda(s, r) for s in efeitos.SLOTS} for r in efeitos.RARIDADES}})


@estudio_bp.route('/api/efeitos', methods=['POST'])
@so_criador
def efeitos_salvar(pessoa):
    d = _json()
    return _tratar(lambda: {'id': efeitos.salvar(d)})


@estudio_bp.route('/api/efeitos/<eid>', methods=['DELETE'])
@so_criador
def efeitos_apagar(pessoa, eid):
    return _tratar(lambda: efeitos.apagar(eid))


# ------------------------------------------------------------
# pacotes (bundles): app/pacotes.py valida e põe no catálogo
# ------------------------------------------------------------
@estudio_bp.route('/api/pacotes')
@so_criador
def pacotes_listar(pessoa):
    efeitos.garantir_carregados()
    return jsonify({'pacotes': pacotes.listar(), 'catalogo': pacotes.catalogo_para_ui(), 'estados': list(pacotes.ESTADOS), 'icones': list(pacotes.ICONES),
                    'categorias': [{'id': c['id'], 'nome': c['nome']} for c in CATEGORIAS], 'desconto': int(DESCONTO_PACOTE * 100), 'min_itens': pacotes.MIN_ITENS})


@estudio_bp.route('/api/pacotes', methods=['POST'])
@so_criador
def pacotes_salvar(pessoa):
    d = _json()
    return _tratar(lambda: {'id': pacotes.salvar(d)})


@estudio_bp.route('/api/pacotes/<pid>', methods=['DELETE'])
@so_criador
def pacotes_apagar(pessoa, pid):
    return _tratar(lambda: pacotes.apagar(pid))


# ------------------------------------------------------------
# biblioteca de arquivos (Lottie, imagem, vídeo)
# ------------------------------------------------------------
@estudio_bp.route('/api/arquivos')
@so_criador
def arquivos_listar(pessoa):
    return jsonify({'arquivos': estudio_arquivos.listar(), 'uso': estudio_arquivos.uso_total(),
                    'limites': {'lottie': estudio_arquivos.LIM_LOTTIE, 'imagem': estudio_arquivos.LIM_IMAGEM, 'video': estudio_arquivos.LIM_VIDEO,
                                'duracao_s': estudio_arquivos.MAX_DURACAO_S, 'lado': estudio_arquivos.MAX_LADO}})


@estudio_bp.route('/api/arquivos', methods=['POST'])
@so_criador
def arquivos_enviar(pessoa):
    def fazer():
        f = request.files.get('file')
        if not f:
            raise ErroArquivo('Nenhum arquivo enviado.')
        dados = f.stream.read(estudio_arquivos.LIM_VIDEO + 1)
        if len(dados) > estudio_arquivos.LIM_VIDEO:
            raise ErroArquivo('Arquivo pesado demais (o máximo é 6 MB, e só vídeo chega nisso).')
        c = request.files.get('capa')
        capa = c.stream.read(estudio_arquivos.LIM_CAPA + 1) if c else None
        medidas = {'w': request.form.get('w'), 'h': request.form.get('h'), 'dur': request.form.get('dur')}
        a = estudio_arquivos.guardar(dados, f.filename, pessoa.id, capa=capa, medidas=medidas)
        return {'arquivo': estudio_arquivos.biblioteca_para_json(a), 'uso': estudio_arquivos.uso_total()}
    return _tratar(fazer)


@estudio_bp.route('/api/arquivos/<aid>', methods=['DELETE'])
@so_criador
def arquivos_apagar(pessoa, aid):
    def fazer():
        estudio_arquivos.apagar(aid)
        return {'uso': estudio_arquivos.uso_total()}
    return _tratar(fazer)


def _entrega(corpo, mime, sha):
    """Resposta de arquivo imutável: ETag = hash do conteúdo, cache de um ano (o id nunca aponta pra outro conteúdo) e suporte a Range
    (o Safari só toca vídeo se o servidor aceitar Range)."""
    resp = Response(corpo, mimetype=mime)
    resp.set_etag(sha)
    resp.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
    resp.headers['Content-Disposition'] = 'inline'
    return resp.make_conditional(request.environ, accept_ranges=True, complete_length=len(corpo))


@estudio_bp.route('/arquivo/<aid>')
def arquivo_bytes(aid):
    if not session.get('user_id'):
        abort(401)
    c = estudio_arquivos.conteudo(aid)
    if not c:
        abort(404)
    mime, dados, sha = c
    return _entrega(dados, mime, sha)


@estudio_bp.route('/arquivo/<aid>/capa')
def arquivo_capa(aid):
    if not session.get('user_id'):
        abort(401)
    c = estudio_arquivos.conteudo_capa(aid)
    if not c:
        abort(404)
    capa, sha = c
    return _entrega(capa, 'image/webp', sha + '-capa')


# ------------------------------------------------------------
# dar item a alguém (o mesmo botão "Dar a alguém" do editor)
# ------------------------------------------------------------
@estudio_bp.route('/api/pessoas')
@so_criador
def pessoas(pessoa):
    q = (request.args.get('q') or '').strip().lstrip('@').lower()
    if len(q) < 2:
        return jsonify({'pessoas': []})
    like = f'%{q.replace("%", "").replace("_", "")}%'
    linhas = com_retry(lambda: Person.query.filter(or_(Person.username.ilike(like), Person.name.ilike(like))).limit(15).all())
    return jsonify({'pessoas': [{'id': p.id, 'nome': p.name, 'username': p.username or ''} for p in linhas]})


@estudio_bp.route('/api/itens/conceder', methods=['POST'])
@so_criador
def itens_conceder(pessoa):
    """Dá (ou tira, com ativo=false) um item do catálogo a alguém: brinde, teste, compensação. Dar um PACOTE dá o pacote e cada item dele (vendido avulso ou não);
    tirar um pacote tira o pacote e os itens dele que foram dados pelo admin (o que a pessoa comprou ou ganhou de outro jeito fica)."""
    d = _json()

    def fazer():
        item = str(d.get('item_id') or '')
        if item not in CATALOGO:
            raise ErroEstudio('Item não existe no catálogo (um pacote em rascunho ainda não existe pro app: publique como "só dar" ou "à venda").')
        try:
            alvo_id = int(d.get('person_id') or 0)
        except (TypeError, ValueError):
            alvo_id = 0
        alvo = com_retry(lambda: Person.query.get(alvo_id))
        if not alvo:
            raise ErroEstudio('Pessoa não encontrada.')
        ids = itens_para_conceder(item)
        eh_pacote = CATALOGO[item]['tipo'] == 'pacote'

        def preparar():
            if d.get('ativo') is False:
                if eh_pacote:
                    Posse.query.filter(Posse.person_id == alvo.id, Posse.item_id.in_(ids), or_(Posse.item_id == item, Posse.origem == 'admin')).delete(synchronize_session=False)
                else:
                    Posse.query.filter_by(person_id=alvo.id, item_id=item).delete()
                return
            tem = {p[0] for p in db.session.query(Posse.item_id).filter(Posse.person_id == alvo.id, Posse.item_id.in_(ids)).all()}
            for i in ids:
                if i not in tem:
                    db.session.add(Posse(person_id=alvo.id, item_id=i, origem='admin'))

        comitar_com_retry(preparar)
    return _tratar(fazer)
