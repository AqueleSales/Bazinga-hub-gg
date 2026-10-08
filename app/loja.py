"""Armazém: a loja do app, paga em DRC.

Só lógica e dados da vitrine; não fala com o socket (os handlers moram em events.py).

Regras que não se negociam (regra 4 do CLAUDE.md, e o motivo de este arquivo existir):
  * O servidor decide o preço, a posse e o saldo. O cliente só diz QUAL item quer (e, se quiser,
    que preço viu na tela, para o servidor recusar se o preço mudou no meio).
  * Comprar é UMA transação: debita, concede a posse e escreve o livro-razão juntos. Ou tudo
    acontece, ou nada. O débito é um `UPDATE ... WHERE saldo >= preço`, então dois cliques ao
    mesmo tempo (ou duas abas) nunca gastam o mesmo DRC duas vezes.
  * Não existe saque, transferência nem compra de DRC com dinheiro. DRC só se ganha no app.

O que está à venda é o catálogo de `cosmeticos.py` com campo `preco`. Tema novo da loja = itens
com `preco` + entrada em `TEMAS` com `loja: True` + CSS dos ids (ver "Criar item novo").
"""
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError

from .cosmeticos import CATALOGO, TEMAS, PACOTES, ROTULO_TIPO, posses_da_pessoa
from .models import db, Person, Posse, MovimentoDrc
from .utils import comitar_com_retry

# Ordem em que os tipos aparecem na vitrine e o nome da prateleira de cada um.
PRATELEIRAS = [
    ('moldura', 'Molduras'),
    ('nome', 'Estilos de nome'),
    ('placa', 'Placas'),
    ('faixa', 'Faixas de perfil'),
]

# Faixas grandes do topo da loja (carrossel). `tema` precisa existir em TEMAS com loja=True.
DESTAQUES = [
    {'tema': 'manga', 'selo': 'Novo', 'titulo': 'Mangá', 'sub': 'Preto, branco e uma cor só para o clímax: traço de tinta e linhas de velocidade.'},
    {'tema': 'mira', 'selo': 'Novo', 'titulo': 'Mira', 'sub': 'Travou o alvo: uma mira que fecha no seu avatar e um radar na faixa.'},
    {'tema': 'quadra', 'selo': 'Novo', 'titulo': 'Quadra', 'sub': 'Uma bola orbitando o avatar, rede na placa e a quadra inteira na faixa.'},
    {'tema': 'batida', 'selo': 'Novo', 'titulo': 'Batida', 'sub': 'Equalizador em volta da foto, vinil girando e um nome que acompanha o refrão.'},
    {'tema': 'cubos', 'selo': 'Novo', 'titulo': 'Cubos', 'sub': 'Um mundo inteiro feito de blocos: grama, terra, céu e nuvens quadradas.'},
    {'tema': 'dualidade', 'selo': 'Lançamento', 'titulo': 'Dualidade',
     'sub': 'Azul, vermelho... e o que nasce quando se encontram.'},
    {'tema': 'relojoaria', 'selo': 'Lançamento', 'titulo': 'Relojoaria',
     'sub': 'Latão, engrenagens e um relógio de bolso que abre e fecha no seu avatar.'},
]


class ErroLoja(Exception):
    """Erro que o usuário pode ler (vai pro toast): saldo curto, já tem o item, preço mudou..."""


def _a_venda(item_id):
    d = CATALOGO.get(item_id)
    return d if d and d.get('preco') else None


def itens_do_pacote(tema):
    """item_ids avulsos que o pacote do tema entrega (sem o próprio pacote)."""
    return [f'{t}:{v}' for t, v in PACOTES.get(tema, {}).items() if _a_venda(f'{t}:{v}')]


def preco_para(posses, item_id):
    """(preço final em DRC, ids que a compra entrega agora). Levanta ErroLoja se não dá pra comprar.

    Item avulso: o preço de tabela. Pacote: o preço de tabela, abatido em proporção do que a pessoa
    já tem avulso (ela não paga duas vezes pela mesma moldura). Se já tem tudo do pacote, ele sai
    de graça (só pra constar e poder "equipar tudo")."""
    d = _a_venda(item_id)
    if not d:
        raise ErroLoja('Este item não está à venda.')
    if item_id in posses:
        raise ErroLoja('Você já tem esse item.')

    if d['tipo'] != 'pacote':
        return d['preco'], [item_id]

    filhos = itens_do_pacote(d['tema'])
    total = sum(CATALOGO[i]['preco'] for i in filhos)
    faltam = [i for i in filhos if i not in posses]
    falta_total = sum(CATALOGO[i]['preco'] for i in faltam)
    preco = round(d['preco'] * falta_total / total) if total else d['preco']
    return preco, faltam + [item_id]


def _debitar(pessoa_id, preco):
    """Tira `preco` do saldo SE houver saldo, num UPDATE só. True se debitou."""
    saldo = func.coalesce(Person.bazinga_coins, 0)
    r = db.session.execute(update(Person).where(Person.id == pessoa_id, saldo >= preco)
                           .values(bazinga_coins=saldo - preco))
    return r.rowcount == 1


def comprar(pessoa, item_id, preco_esperado=None):
    """Compra `item_id` com DRC. Devolve {'item_id', 'nome', 'preco', 'entregues', 'saldo'}.

    Tudo dentro de `comitar_com_retry`: se o Neon estiver acordando e o commit falhar, a função
    inteira roda de novo do zero (relê a posse, refaz o débito), sem comitar sessão vazia."""
    resultado = {}

    def preparar():
        posses = posses_da_pessoa(pessoa.id)
        preco, entregues = preco_para(posses, item_id)
        if preco_esperado is not None and int(preco_esperado) != preco:
            raise ErroLoja(f'O preço mudou para {preco} DRC. Confira e tente de novo.')

        if preco > 0:
            if not _debitar(pessoa.id, preco):
                raise ErroLoja('Você não tem DRC suficiente.')
            db.session.refresh(pessoa, ['bazinga_coins'])
            db.session.add(MovimentoDrc(person_id=pessoa.id, delta=-preco, saldo_apos=pessoa.bazinga_coins,
                                        motivo='compra', ref=item_id))
        for i in entregues:
            db.session.add(Posse(person_id=pessoa.id, item_id=i, origem='loja'))
        resultado.update(item_id=item_id, nome=CATALOGO[item_id]['nome'], preco=preco, entregues=entregues)

    try:
        comitar_com_retry(preparar)
    except IntegrityError:
        # Dois cliques ao mesmo tempo: o outro pedido já entregou o item (posse é única por pessoa+item) e a
        # transação deste foi desfeita inteira, inclusive o débito.
        db.session.rollback()
        raise ErroLoja('Você já tem esse item.')

    db.session.refresh(pessoa, ['bazinga_coins'])
    resultado['saldo'] = pessoa.bazinga_coins or 0
    return resultado


# ==========================================
# VITRINE (o que o cliente desenha)
# ==========================================
def _item_json(d, posses):
    possui = d['id'] in posses
    j = {k: d[k] for k in ('id', 'tipo', 'valor', 'nome', 'desc', 'tema', 'raridade', 'preco')}
    j['possui'] = possui
    j['rotulo'] = ROTULO_TIPO.get(d['tipo'], d['tipo'])
    if d['tipo'] == 'pacote' and not possui:
        try:
            j['preco_final'] = preco_para(posses, d['id'])[0]
        except ErroLoja:
            j['preco_final'] = d['preco']
    else:
        j['preco_final'] = d['preco']
    return j


def vitrine_para_json(pessoa, posses=None):
    """A loja inteira, na medida de UMA pessoa (o que ela já tem, o preço do pacote pra ela)."""
    posses = posses_da_pessoa(pessoa.id) if posses is None else posses
    itens = [_item_json(d, posses) for d in CATALOGO.values() if d.get('preco')]
    temas = []
    for tid, t in TEMAS.items():
        if not t.get('loja'):
            continue
        avulsos = itens_do_pacote(tid)
        total = sum(CATALOGO[i]['preco'] for i in avulsos)
        pacote_id = f'pacote:{tid}'
        temas.append({
            'id': tid, 'nome': t['nome'], 'cor': t['cor'], 'cores': t['cores'], 'icone': t['icone'], 'lema': t['lema'],
            'desc': t['desc'], 'pacote': pacote_id if _a_venda(pacote_id) else None, 'itens': avulsos,
            'preco_soma': total, 'preco_pacote': (CATALOGO.get(pacote_id) or {}).get('preco'),
        })
    return {
        'saldo': pessoa.bazinga_coins or 0,
        'temas': temas, 'itens': itens,
        'prateleiras': [{'tipo': t, 'titulo': n} for t, n in PRATELEIRAS],
        'destaques': [x for x in DESTAQUES if TEMAS.get(x['tema'], {}).get('loja')],
    }


# ==========================================
# EXTRATO (histórico de DRC): o livro-razão visto pela própria pessoa
# ==========================================
ROTULO_MOTIVO = {'compra': 'Compra', 'nivel': 'Subiu de nível', 'ajuste': 'Ajuste'}


def extrato(pessoa, limite=60):
    """Os últimos movimentos de DRC da pessoa (mais novo primeiro) + o que ela já ganhou/gastou ao todo. Só dela: nunca de outra pessoa."""
    linhas = (MovimentoDrc.query.filter_by(person_id=pessoa.id).order_by(MovimentoDrc.id.desc()).limit(limite).all())
    itens = []
    for m in linhas:
        if m.motivo == 'compra':
            d = CATALOGO.get(m.ref or '')
            titulo = d['nome'] if d else 'Item da loja'
        elif m.motivo == 'nivel':
            de, _, ate = (m.ref or '').partition('->')
            titulo = f'Nível {ate}' if ate.isdigit() and de.isdigit() and int(ate) - int(de) == 1 else f'Níveis {int(de) + 1 if de.isdigit() else "?"} a {ate}'
        else:
            titulo = ROTULO_MOTIVO.get(m.motivo, m.motivo)
        itens.append({'delta': m.delta, 'saldo_apos': m.saldo_apos, 'motivo': m.motivo, 'rotulo': ROTULO_MOTIVO.get(m.motivo, m.motivo),
                      'titulo': titulo, 'hora': m.created_at.strftime('%d/%m %H:%M') if m.created_at else ''})
    ganho = db.session.query(func.coalesce(func.sum(MovimentoDrc.delta), 0)).filter(MovimentoDrc.person_id == pessoa.id, MovimentoDrc.delta > 0).scalar() or 0
    gasto = db.session.query(func.coalesce(func.sum(MovimentoDrc.delta), 0)).filter(MovimentoDrc.person_id == pessoa.id, MovimentoDrc.delta < 0).scalar() or 0
    return {'saldo': pessoa.bazinga_coins or 0, 'itens': itens, 'ganho_total': int(ganho), 'gasto_total': int(-gasto)}
