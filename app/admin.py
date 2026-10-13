"""Painel do administrador criador do app (`/admin`).

Uma página só, só pra quem é admin (id em config_app 'admin_ids', o mesmo poder da moderação do Bazar; definido por ID com
`python bazar_admin.py admin <@usuario>`). Quem não é admin recebe 404 (a página nem confirma que existe) e a API devolve 403.
Cada rota confere o admin NO SERVIDOR (regra 4); esconder o botão no cliente não protege nada.

Proteção contra requisição forjada de outro site: toda rota que ALTERA algo exige o cabeçalho `X-Requested-With: fetch`, que um
formulário/imagem de outro site não consegue mandar sem passar pela checagem de CORS (que este app não libera).

Por enquanto o painel cuida de: Passe de Batalha (temporadas, 100 níveis x 2 trilhas), Títulos, Missões (leitura) e Administradores.
Armazém, Bazar, denúncias, servidores, selos e notas do mapa seguem nas telas que já existem e entram aqui nas próximas etapas.
"""
from functools import wraps

from flask import Blueprint, abort, jsonify, render_template, request, session
from sqlalchemy import or_

from . import passe, efeitos, explorar, admin_dados
from .bazar import eh_admin, ids_dos_admins, definir_admin
from .cosmeticos import CATALOGO, ROTULO_TIPO, RARIDADES
from .models import db, Person, Posse
from .passe import ErroPasse
from .utils import com_retry, comitar_com_retry, MISSOES, DRC_POR_MISSAO, QTD_DIARIAS, OFERTA_SEMANAIS, ESCOLHAS_SEMANAIS, TEMAS_EXCLUSIVOS

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _admin_atual():
    uid = session.get('user_id')
    if not uid:
        return None
    pessoa = com_retry(lambda: Person.query.get(uid))
    return pessoa if eh_admin(pessoa) else None


def so_admin(rota):
    @wraps(rota)
    def envolta(*a, **kw):
        pessoa = _admin_atual()
        if not pessoa:
            if request.path.startswith('/admin/api/'):
                return jsonify({'erro': 'Só administradores.'}), 403
            abort(404)
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH') and request.headers.get('X-Requested-With') != 'fetch':
            return jsonify({'erro': 'Requisição inválida.'}), 400
        return rota(pessoa, *a, **kw)
    return envolta


def _json():
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def _tratar(fn):
    """Roda `fn` e devolve JSON: ErroPasse vira 400 com a mensagem de regra; o resto vira 500 com o motivo (regra 3: nunca em silêncio)."""
    try:
        r = fn()
        return jsonify({'ok': True, **(r if isinstance(r, dict) else {})})
    except ErroPasse as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ADMIN] {e}")
        return jsonify({'erro': f'Erro inesperado: {e}'}), 500


@admin_bp.route('')
@so_admin
def pagina(pessoa):
    resp = render_template('admin.html', eu={'id': pessoa.id, 'nome': pessoa.name, 'username': pessoa.username or ''})
    return resp, 200, {'Cache-Control': 'no-store'}


# ------------------------------------------------------------
# catálogo (pra os seletores) e pessoas
# ------------------------------------------------------------
@admin_bp.route('/api/catalogo')
@so_admin
def catalogo(pessoa):
    itens = [{'id': d['id'], 'tipo': d['tipo'], 'rotulo': ROTULO_TIPO.get(d['tipo'], d['tipo']), 'nome': d['nome'], 'tema': d['tema'],
              'raridade': d['raridade'], 'preco': d.get('preco') or 0}
             for d in CATALOGO.values() if d['tipo'] != 'pacote']
    return jsonify({'itens': itens, 'titulos': passe.lista_de_titulos(),
                    'temas_app': [{'id': k, 'nome': v} for k, v in TEMAS_EXCLUSIVOS.items()],
                    'temas_passe': [{'id': k, **v} for k, v in passe.TEMAS_PASSE.items()],
                    'animacoes_titulo': list(passe.ANIMACOES_TITULO), 'raridades_titulo': list(passe.RARIDADES_TITULO),
                    'raridades': RARIDADES})


@admin_bp.route('/api/pessoas')
@so_admin
def pessoas(pessoa):
    q = (request.args.get('q') or '').strip().lstrip('@').lower()
    if len(q) < 2:
        return jsonify({'pessoas': []})
    like = f'%{q.replace("%", "").replace("_", "")}%'
    linhas = com_retry(lambda: Person.query.filter(or_(Person.username.ilike(like), Person.name.ilike(like))).limit(15).all())
    return jsonify({'pessoas': [{'id': p.id, 'nome': p.name, 'username': p.username or ''} for p in linhas]})


# ------------------------------------------------------------
# visão geral
# ------------------------------------------------------------
@admin_bp.route('/api/geral')
@so_admin
def geral(pessoa):
    """Números e séries da Visão geral. `?dias=7|30|90` escolhe a janela dos gráficos por dia (os outros números são de agora)."""
    try:
        dias = int(request.args.get('dias') or 30)
    except ValueError:
        dias = 30
    snap = passe.temporada_ativa()
    admins = com_retry(lambda: Person.query.filter(Person.id.in_(ids_dos_admins() or [0])).all())
    try:
        dados = admin_dados.resumo(dias)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ADMIN GERAL] {e}")
        return jsonify({'erro': f'Não foi possível montar os números: {e}'}), 500
    dados.update({
        'temporada': {'id': snap['id'], 'nome': snap['nome'], 'fim': snap['fim'].isoformat() if snap['fim'] else None} if snap else None,
        'admins': [{'id': p.id, 'nome': p.name, 'username': p.username or ''} for p in admins],
    })
    return jsonify(dados), 200, {'Cache-Control': 'no-store'}


@admin_bp.route('/api/pessoas/lista')
@so_admin
def pessoas_lista(pessoa):
    """Todas as contas (nome, @, e-mail, nível, online), 25 por página, com busca e ordem. DADO PESSOAL: só admin, nunca em cache."""
    try:
        dados = admin_dados.lista_pessoas(request.args.get('q'), request.args.get('pagina'), request.args.get('ordem'))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ADMIN PESSOAS] {e}")
        return jsonify({'erro': f'Não foi possível listar as pessoas: {e}'}), 500
    return jsonify(dados), 200, {'Cache-Control': 'no-store'}


@admin_bp.route('/api/admins', methods=['POST'])
@so_admin
def admins(pessoa):
    d = _json()

    def fazer():
        alvo = com_retry(lambda: Person.query.get(int(d.get('person_id') or 0)))
        if not alvo:
            raise ErroPasse('Pessoa não encontrada.')
        ativo = d.get('ativo') is not False
        if not ativo and alvo.id == pessoa.id:
            raise ErroPasse('Você não pode tirar o próprio acesso por aqui (use bazar_admin.py).')
        definir_admin(alvo.id, ativo)

    return _tratar(fazer)


# ------------------------------------------------------------
# passe: temporadas e recompensas
# ------------------------------------------------------------
@admin_bp.route('/api/passe/temporadas')
@so_admin
def passe_temporadas(pessoa):
    return jsonify({'temporadas': com_retry(passe.listar_temporadas)})


@admin_bp.route('/api/passe/temporada', methods=['POST'])
@so_admin
def passe_salvar_temporada(pessoa):
    d = _json()
    return _tratar(lambda: {'id': passe.salvar_temporada(d, int(d['id']) if d.get('id') else None)})


@admin_bp.route('/api/passe/temporada/<int:tid>/ativar', methods=['POST'])
@so_admin
def passe_ativar(pessoa, tid):
    return _tratar(lambda: passe.ativar_temporada(tid, _json().get('ativa') is not False))


@admin_bp.route('/api/passe/temporada/<int:tid>', methods=['DELETE'])
@so_admin
def passe_apagar(pessoa, tid):
    return _tratar(lambda: passe.apagar_temporada(tid))


@admin_bp.route('/api/passe/temporada/<int:tid>/recompensas')
@so_admin
def passe_recompensas(pessoa, tid):
    return jsonify({'recompensas': com_retry(lambda: passe.recompensas_da_temporada(tid))})


@admin_bp.route('/api/passe/temporada/<int:tid>/recompensas', methods=['POST'])
@so_admin
def passe_salvar_recompensas(pessoa, tid):
    d = _json()
    return _tratar(lambda: passe.salvar_recompensas(tid, d.get('lista'), substituir=bool(d.get('substituir'))))


@admin_bp.route('/api/passe/temporada/<int:tid>/modelo', methods=['POST'])
@so_admin
def passe_modelo(pessoa, tid):
    return _tratar(lambda: {'qtd': passe.modelo_deuses(tid)})


@admin_bp.route('/api/passe/modelo', methods=['POST'])
@so_admin
def passe_criar_modelo(pessoa):
    return _tratar(lambda: {'id': passe.criar_temporada_modelo()})


@admin_bp.route('/api/passe/temporada/<int:tid>/jogadores')
@so_admin
def passe_jogadores(pessoa, tid):
    return jsonify({'jogadores': com_retry(lambda: passe.jogadores_da_temporada(tid))})


@admin_bp.route('/api/passe/premium', methods=['POST'])
@so_admin
def passe_premium(pessoa):
    d = _json()
    return _tratar(lambda: passe.definir_premium(int(d.get('person_id') or 0), d.get('ativo') is not False))


# ------------------------------------------------------------
# títulos
# ------------------------------------------------------------
@admin_bp.route('/api/titulos')
@so_admin
def titulos(pessoa):
    return jsonify({'titulos': passe.lista_de_titulos()})


@admin_bp.route('/api/titulos', methods=['POST'])
@so_admin
def titulos_salvar(pessoa):
    return _tratar(lambda: {'id': passe.salvar_titulo(_json())})


@admin_bp.route('/api/titulos/<tid>', methods=['DELETE'])
@so_admin
def titulos_apagar(pessoa, tid):
    return _tratar(lambda: passe.apagar_titulo(tid))


@admin_bp.route('/api/titulos/conceder', methods=['POST'])
@so_admin
def titulos_conceder(pessoa):
    """Dá (ou tira, com ativo=false) um título a alguém, direto: pra conquistas e brindes."""
    d = _json()

    def fazer():
        tid = str(d.get('titulo_id') or '')
        if tid not in {t['id'] for t in passe.lista_de_titulos()}:
            raise ErroPasse('Título não existe.')
        alvo = com_retry(lambda: Person.query.get(int(d.get('person_id') or 0)))
        if not alvo:
            raise ErroPasse('Pessoa não encontrada.')
        item = f'titulo:{tid}'

        def preparar():
            if d.get('ativo') is False:
                Posse.query.filter_by(person_id=alvo.id, item_id=item).delete()
                if alvo.titulo_id == tid:
                    alvo.titulo_id = None
            elif not Posse.query.filter_by(person_id=alvo.id, item_id=item).first():
                db.session.add(Posse(person_id=alvo.id, item_id=item, origem='admin'))

        comitar_com_retry(preparar)

    return _tratar(fazer)


# ------------------------------------------------------------
# missões (leitura: os valores ainda moram em utils.MISSOES)
# ------------------------------------------------------------
@admin_bp.route('/api/missoes')
@so_admin
def missoes(pessoa):
    return jsonify({'missoes': [{'codigo': c, **m, 'drc': DRC_POR_MISSAO[m['periodo']]} for c, m in MISSOES.items()],
                    'regras': {'diarias': QTD_DIARIAS, 'oferta_semanais': OFERTA_SEMANAIS, 'escolhas_semanais': ESCOLHAS_SEMANAIS}})


# ------------------------------------------------------------
# Estúdio de efeitos (app/efeitos.py): receitas validadas, efeito entra no catálogo e é avisado a todo mundo conectado
# ------------------------------------------------------------
# (efeitos.salvar/apagar já avisam todo mundo sozinhos: efeitos.difundir)


def _tratar_efeito(fn):
    """Igual a `_tratar`, mas o erro de regra aqui é ErroEfeito."""
    try:
        r = fn()
        return jsonify({'ok': True, **(r if isinstance(r, dict) else {})})
    except efeitos.ErroEfeito as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ADMIN EFEITOS] {e}")
        return jsonify({'erro': f'Erro inesperado: {e}'}), 500


@admin_bp.route('/api/efeitos')
@so_admin
def efeitos_listar(pessoa):
    return jsonify({'efeitos': efeitos.listar(), 'esquema': efeitos.esquema_para_cliente(), 'raridades': list(efeitos.RARIDADES),
                    'max_camadas': efeitos.MAX_CAMADAS})


@admin_bp.route('/api/efeitos', methods=['POST'])
@so_admin
def efeitos_salvar(pessoa):
    d = _json()

    def fazer():
        eid = efeitos.salvar(d)
        return {'id': eid}
    return _tratar_efeito(fazer)


@admin_bp.route('/api/efeitos/<eid>', methods=['DELETE'])
@so_admin
def efeitos_apagar(pessoa, eid):
    def fazer():
        efeitos.apagar(eid)
    return _tratar_efeito(fazer)


@admin_bp.route('/api/itens/conceder', methods=['POST'])
@so_admin
def itens_conceder(pessoa):
    """Dá (ou tira, com ativo=false) QUALQUER item do catálogo a alguém: brinde, teste, compensação."""
    d = _json()

    def fazer():
        item = str(d.get('item_id') or '')
        if item not in CATALOGO or CATALOGO[item]['tipo'] == 'pacote':
            raise ErroPasse('Item não existe no catálogo (ou é um pacote).')
        alvo = com_retry(lambda: Person.query.get(int(d.get('person_id') or 0)))
        if not alvo:
            raise ErroPasse('Pessoa não encontrada.')

        def preparar():
            if d.get('ativo') is False:
                Posse.query.filter_by(person_id=alvo.id, item_id=item).delete()
            elif not Posse.query.filter_by(person_id=alvo.id, item_id=item).first():
                db.session.add(Posse(person_id=alvo.id, item_id=item, origem='admin'))

        comitar_com_retry(preparar)

    return _tratar(fazer)


# ------------------------------------------------------------
# Servidores públicos (Explorar): o admin vê e pode tirar do ar
# ------------------------------------------------------------
@admin_bp.route('/api/servidores')
@so_admin
def servidores_publicos(pessoa):
    return jsonify({'servidores': explorar.listar_publicos_admin()})


@admin_bp.route('/api/servidores/<int:sid>/despublicar', methods=['POST'])
@so_admin
def servidores_despublicar(pessoa, sid):
    def fazer():
        s = explorar.despublicar(sid)
        try:
            from . import socketio
            from .events import servidor_para_json, sala_pessoal
            for m in list(s.members):      # os membros recebem o servidor com o estado novo (fora de um handler: socketio.emit, não emit)
                socketio.emit('servidor_discord_criado', servidor_para_json(s, m), to=sala_pessoal(m.id))
        except Exception as e:
            print(f"[ERRO ADMIN: avisar servidor] {e}")
    try:
        fazer()
        return jsonify({'ok': True})
    except explorar.ErroExplorar as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ADMIN SERVIDORES] {e}")
        return jsonify({'erro': f'Erro inesperado: {e}'}), 500
