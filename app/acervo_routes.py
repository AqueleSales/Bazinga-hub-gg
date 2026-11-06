"""Rotas HTTP do ACERVO (figurinhas e sons): enviar arquivo e servir arquivo. A regra está em acervo.py.

  POST /api/acervo/upload          (login) multipart: arquivo, tipo (figurinha|som), escopo (pessoa|servidor), server_id, nome, emoji, dur_ms
  GET  /api/acervo/<id>/arquivo    (login) os bytes. Só entrega o que está APROVADO (quem enviou e os responsáveis veem o que está em análise).
"""
from flask import Blueprint, Response, abort, jsonify, request, session
from sqlalchemy.orm import undefer

from . import acervo, socketio
from .models import db, AcervoItem, Person
from .utils import com_retry

acervo_bp = Blueprint('acervo', __name__)
TETO_ENVIO = acervo.MAX_FIG_ENVIO + 64 * 1024      # a maior coisa que alguém pode mandar (figurinha); o som é bem menor (a regra confere)


def _pessoa():
    uid = session.get('user_id')
    return com_retry(lambda: Person.query.get(uid)) if uid else None


@acervo_bp.route('/api/acervo/upload', methods=['POST'])
def acervo_upload():
    usuario = _pessoa()
    if not usuario:
        return jsonify({'erro': 'Entre na sua conta pra enviar.'}), 401
    arq = request.files.get('arquivo')
    if not arq:
        return jsonify({'erro': 'Nenhum arquivo enviado.'}), 400
    dados = arq.stream.read(TETO_ENVIO + 1)
    if len(dados) > TETO_ENVIO:
        return jsonify({'erro': 'Arquivo grande demais.'}), 413
    f = request.form
    try:
        item, aviso = acervo.criar(usuario, (f.get('tipo') or '').strip(), (f.get('escopo') or 'pessoa').strip(), f.get('server_id'),
                                   f.get('nome'), f.get('emoji'), dados, f.get('dur_ms'))
    except acervo.ErroAcervo as e:
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f'[ERRO ACERVO UPLOAD] {e}')
        from .seguranca import erro_publico
        return jsonify({'erro': erro_publico(e, 'Não consegui guardar o arquivo')}), 500
    # as abas de quem enviou (e, se é do servidor, quem está nele) atualizam a lista
    from .events import sala_pessoal, sala_servidor
    socketio.emit('acervo_mudou', {'server_id': item.server_id}, to=sala_servidor(item.server_id) if item.server_id else sala_pessoal(usuario.id))
    return jsonify({'ok': True, 'item': acervo.item_json(item, usuario.id), 'aviso': aviso})


def _entrega(item):
    resp = Response(item.dados, mimetype=item.mime)
    resp.set_etag(item.sha)
    resp.headers['Cache-Control'] = 'private, max-age=31536000, immutable' if item.status == 'aprovado' else 'private, no-store'
    resp.headers['Content-Disposition'] = 'inline'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp.make_conditional(request.environ, accept_ranges=True, complete_length=len(item.dados))


@acervo_bp.route('/api/acervo/<int:item_id>/arquivo')
def acervo_arquivo(item_id):
    usuario = _pessoa()
    if not usuario:
        abort(401)
    item = com_retry(lambda: AcervoItem.query.options(undefer(AcervoItem.dados)).get(item_id))
    if not item or not item.dados:
        abort(404)
    if item.status != 'aprovado':
        from .bazar import ids_dos_admins
        if item.status == 'recusado' or (item.person_id != usuario.id and usuario.id not in ids_dos_admins()):
            abort(404)
    return _entrega(item)
