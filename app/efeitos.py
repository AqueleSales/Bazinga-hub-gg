"""Estúdio de efeitos: efeitos de perfil e de avatar criados NO PAINEL (/admin), sem escrever código.

Como funciona: o efeito é DADO (uma "receita" em JSON guardada na tabela `efeito_custom`). Um motor único no navegador
(`static/js/efeitos.js`, objeto `Efeitos`) lê a receita e desenha. Ao salvar, o efeito entra no `CATALOGO` de cosméticos como
um item comum (tema "estudio", sem preço), então tudo que já existe funciona sozinho: inventário, equipar (com posse),
recompensa do passe, "dar a alguém" e, depois, venda no Armazém.

Segurança (regra 4/5 do CLAUDE.md): a receita NUNCA vira CSS/JS livre. `normalizar_receita` só aceita camadas e parâmetros do
`ESQUEMA` (números limitados, cores `#rrggbb`, opções de listas fechadas); qualquer outra coisa é descartada. O cliente ainda
limita os números de novo ao desenhar. Id do efeito: `[a-z_]{2,24}` (o cliente descarta qualquer outro id).

O ESQUEMA abaixo é a ÚNICA definição das camadas: o validador, o editor do admin e o motor do navegador seguem ele.
Camada nova = entrada aqui + o desenho em `efeitos.js` (função em `CAMADAS`).
"""
import json
import re

from .cosmeticos import CATALOGO, TEMAS, _item
from .models import db, br_now, EfeitoCustom, Posse, Person
from .utils import com_retry, comitar_com_retry

SLOTS = ('efeito_perfil', 'efeito_avatar')
RARIDADES = ('raro', 'epico', 'lendario')
MAX_CAMADAS = 6
_RE_ID = re.compile(r'^[a-z_]{2,24}$')
_RE_COR = re.compile(r'^#[0-9a-fA-F]{6}$')

# Parâmetro: ('num', minimo, maximo, padrao, rotulo) | ('cor', padrao, rotulo) | ('opcao', [opções], padrao, rotulo)
ESQUEMA = {
    'particulas': {
        'nome': 'Partículas', 'slots': ('efeito_perfil',),
        'dica': 'Pontinhos de luz que sobem, descem ou cruzam o cartão.',
        'params': {
            'cor': ('cor', '#f2c14e', 'Cor'), 'cor2': ('cor', '#ffffff', 'Segunda cor'),
            'qtd': ('num', 3, 40, 16, 'Quantidade'), 'tam': ('num', 2, 12, 5, 'Tamanho'),
            'dur': ('num', 2, 14, 6, 'Duração da subida (s)'),
            'dir': ('opcao', ['cima', 'baixo', 'esq', 'dir'], 'cima', 'Direção'),
            'forma': ('opcao', ['circulo', 'quadrado', 'losango', 'estrela'], 'circulo', 'Forma'),
            'brilho': ('num', 0, 100, 60, 'Brilho (halo)'),
        }},
    'brilho': {
        'nome': 'Brilho', 'slots': ('efeito_perfil', 'efeito_avatar'),
        'dica': 'Uma luz suave que pulsa.',
        'params': {
            'cor': ('cor', '#7cc4ff', 'Cor'),
            'pos': ('opcao', ['topo', 'centro', 'base'], 'topo', 'Onde'),
            'forca': ('num', 10, 100, 55, 'Força'), 'dur': ('num', 2, 14, 5, 'Duração do pulso (s)'),
        }},
    'raios': {
        'nome': 'Raios', 'slots': ('efeito_perfil',),
        'dica': 'Relâmpagos que caem pelo cartão.',
        'params': {
            'cor': ('cor', '#bfe3ff', 'Cor'), 'qtd': ('num', 1, 8, 4, 'Quantidade'),
            'dur': ('num', 3, 12, 5, 'Intervalo entre raios (s)'),
        }},
    'anel': {
        'nome': 'Anel', 'slots': ('efeito_avatar',),
        'dica': 'Um anel que se expande a partir da foto, como uma onda.',
        'params': {
            'cor': ('cor', '#f2c14e', 'Cor'), 'esp': ('num', 1, 6, 2, 'Espessura'), 'dur': ('num', 1, 8, 2.4, 'Duração (s)'),
        }},
    'orbita': {
        'nome': 'Órbita', 'slots': ('efeito_avatar',),
        'dica': 'Pontinhos de luz girando em volta da foto.',
        'params': {
            'cor': ('cor', '#ffffff', 'Cor'), 'qtd': ('num', 1, 6, 3, 'Quantidade'), 'tam': ('num', 2, 10, 4, 'Tamanho'),
            'dur': ('num', 1, 12, 4, 'Uma volta (s)'),
        }},
}


def esquema_para_cliente():
    """O mesmo esquema, em JSON, pro editor do admin montar os controles (um lugar só define o que existe)."""
    saida = {}
    for tipo, c in ESQUEMA.items():
        params = {}
        for nome, p in c['params'].items():
            if p[0] == 'num':
                params[nome] = {'t': 'num', 'min': p[1], 'max': p[2], 'padrao': p[3], 'rotulo': p[4]}
            elif p[0] == 'cor':
                params[nome] = {'t': 'cor', 'padrao': p[1], 'rotulo': p[2]}
            else:
                params[nome] = {'t': 'opcao', 'opcoes': p[1], 'padrao': p[2], 'rotulo': p[3]}
        saida[tipo] = {'nome': c['nome'], 'slots': list(c['slots']), 'dica': c['dica'], 'params': params}
    return saida


class ErroEfeito(Exception):
    pass


def _num(v, mn, mx, padrao):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return padrao
    if x != x:           # NaN
        return padrao
    x = max(mn, min(mx, x))
    return int(x) if float(x).is_integer() else round(x, 2)


def normalizar_receita(slot, receita):
    """Receita crua do cliente -> receita limpa. Só camadas/params do ESQUEMA e válidas para o slot; o resto some."""
    if slot not in SLOTS:
        raise ErroEfeito('Tipo de efeito inválido.')
    if not isinstance(receita, dict):
        raise ErroEfeito('Receita inválida.')
    camadas_in = receita.get('camadas')
    if not isinstance(camadas_in, list) or not camadas_in:
        raise ErroEfeito('Adicione pelo menos uma camada.')
    camadas = []
    for c in camadas_in[:MAX_CAMADAS]:
        if not isinstance(c, dict) or c.get('tipo') not in ESQUEMA:
            continue
        esq = ESQUEMA[c['tipo']]
        if slot not in esq['slots']:
            raise ErroEfeito(f'A camada "{esq["nome"]}" não vale pra esse tipo de efeito.')
        limpa = {'tipo': c['tipo']}
        for nome, p in esq['params'].items():
            v = c.get(nome)
            if p[0] == 'num':
                limpa[nome] = _num(v, p[1], p[2], p[3])
            elif p[0] == 'cor':
                limpa[nome] = v.lower() if isinstance(v, str) and _RE_COR.match(v) else p[1]
            else:
                limpa[nome] = v if v in p[1] else p[2]
        camadas.append(limpa)
    if not camadas:
        raise ErroEfeito('Nenhuma camada válida.')
    return {'pausa': _num(receita.get('pausa'), 0, 15, 0), 'camadas': camadas}


def _validar_meta(dados, novo):
    eid = str(dados.get('id') or '').strip().lower()
    if not _RE_ID.match(eid):
        raise ErroEfeito('O id usa só letras minúsculas e _ (2 a 24 caracteres).')
    nome = str(dados.get('nome') or '').strip()
    if not 2 <= len(nome) <= 40:
        raise ErroEfeito('O nome tem de 2 a 40 caracteres.')
    slot = dados.get('tipo')
    if slot not in SLOTS:
        raise ErroEfeito('Escolha se é efeito de perfil ou de avatar.')
    rar = dados.get('raridade') or 'epico'
    if rar not in RARIDADES:
        raise ErroEfeito('Raridade inválida.')
    desc = str(dados.get('descricao') or '').strip()[:120]
    return eid, nome, slot, rar, desc


def _registrar(e):
    """Põe (ou atualiza) o efeito no CATALOGO em memória."""
    TEMAS.setdefault('estudio', {'nome': 'Estúdio', 'cor': '#d4a24c', 'desc': 'Efeitos criados no Estúdio.'})
    _item(e.tipo, e.id, e.nome, e.descricao or 'Efeito criado no Estúdio.', 'estudio', e.raridade or 'epico', custom=True)


def _desregistrar(tipo, eid):
    CATALOGO.pop(f'{tipo}:{eid}', None)


_carregado = False


def _invalidar():
    global _cache_mapa
    _cache_mapa = None


def carregar():
    """Lê os efeitos do banco e registra todos no catálogo. Idempotente."""
    global _carregado
    for e in com_retry(lambda: EfeitoCustom.query.all()):
        _registrar(e)
    _carregado = True


def garantir_carregados():
    """Chamado em pontos de entrada (conexão, /chat): se o banco estava dormindo no boot, tenta de novo agora."""
    if not _carregado:
        try:
            carregar()
        except Exception as ex:
            db.session.rollback()
            print(f"[EFEITOS] não consegui carregar ainda: {ex}")


def para_json(e):
    try:
        receita = json.loads(e.receita)
    except (TypeError, ValueError):
        receita = {'pausa': 0, 'camadas': []}
    return {'id': e.id, 'tipo': e.tipo, 'nome': e.nome, 'descricao': e.descricao or '', 'raridade': e.raridade or 'epico', 'receita': receita}


_cache_mapa = None


def mapa_para_cliente():
    """{id: {tipo, receita}}: o que o motor do navegador precisa pra desenhar (vai no HTML do /chat e no evento `efeitos_custom`).
    Em cache (zero query a cada conexão); salvar/apagar invalidam."""
    global _cache_mapa
    garantir_carregados()
    if _cache_mapa is None:
        _cache_mapa = {e.id: {'tipo': e.tipo, 'receita': para_json(e)['receita']} for e in com_retry(lambda: EfeitoCustom.query.all())}
    return _cache_mapa


def listar():
    return [para_json(e) for e in com_retry(lambda: EfeitoCustom.query.order_by(EfeitoCustom.criado_em.desc()).all())]


def salvar(dados):
    eid, nome, slot, rar, desc = _validar_meta(dados, True)
    receita = normalizar_receita(slot, dados.get('receita'))
    existente = com_retry(lambda: EfeitoCustom.query.get(eid))
    item_id = f'{slot}:{eid}'
    if item_id in CATALOGO and not (existente and existente.tipo == slot):
        raise ErroEfeito('Já existe um item com esse id nesse tipo. Escolha outro id.')
    if existente and existente.tipo != slot:
        raise ErroEfeito('Não dá pra mudar o tipo de um efeito já criado. Crie outro.')

    def preparar():
        e = EfeitoCustom.query.get(eid)
        if not e:
            e = EfeitoCustom(id=eid, tipo=slot, criado_em=br_now())
            db.session.add(e)
        e.nome, e.raridade, e.descricao = nome, rar, desc or None
        e.receita = json.dumps(receita, separators=(',', ':'))
        return e

    e = comitar_com_retry(preparar)
    _registrar(e)
    _invalidar()
    return eid


def apagar(eid):
    e = com_retry(lambda: EfeitoCustom.query.get(eid))
    if not e:
        raise ErroEfeito('Efeito não encontrado.')
    item_id, tipo = f'{e.tipo}:{e.id}', e.tipo

    def preparar():
        Posse.query.filter_by(item_id=item_id).delete()
        for p in Person.query.filter(Person.equipados.like(f'%"{eid}"%')).all():
            try:
                d = json.loads(p.equipados or '{}')
            except ValueError:
                continue
            if d.get(tipo) == eid:
                d.pop(tipo)
                p.equipados = json.dumps(d, separators=(',', ':')) if d else None
        EfeitoCustom.query.filter_by(id=eid).delete()

    comitar_com_retry(preparar)
    _desregistrar(tipo, eid)
    _invalidar()
