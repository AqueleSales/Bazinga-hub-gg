"""Canal de LOJAS (tipo de canal `lojas`, Rodada 35): uma vitrine, dentro do servidor, com as lojas do Bazar das pessoas que estão nele
e as lojas PARCEIRAS do Pantheon (porte "grande", que só um admin define). Sem socket; os eventos moram em lojas_canal_events.py.

Regras:
  * Quem lista é quem PODE VER O CANAL (utils.canal_permitido: membro, canal privado só pra convidado, sobrescrita por cargo). O `canal_id` vem do
    cliente, mas só vale se for um canal do tipo `lojas` que a pessoa enxerga; o servidor da lista é sempre o do canal, nunca o que o cliente diz.
  * Só aparece loja que o Bazar já mostraria a qualquer um: aberta, não escondida pela moderação, dono não banido, com pelo menos um produto à
    vista (e que bata com a busca/filtro). Nada de Pix, carteira, endereço, e-mail: o mesmo `loja_json` do feed do Bazar.
  * Quem é membro do servidor aparece como lojista "do servidor". Isso só é dito a quem já está no servidor (quem lista é membro).
  * "Pedir" não existe aqui: o cliente abre a loja/produto no Bazar (Bazar.abrirLojaDe), onde valem todas as regras de pedido, localização e banimento.
"""
from sqlalchemy import select, func, or_

from . import bazar, cargos
from .models import db, BazarLoja, BazarProduto, server_members
from .utils import com_retry

MAX_LOJAS = 60
ORIGENS = ('todas', 'servidor', 'parceiras')


def listar(canal, busca='', categoria='', origem='todas', seed=''):
    """{itens, total, categorias, origem, ...} das lojas deste canal. `canal` já foi conferido (tipo lojas + a pessoa pode vê-lo)."""
    # Padrão: SÓ as lojas das pessoas do servidor. As parceiras do Pantheon só entram se quem gerencia o canal ligou "incluir lojas parceiras"
    # (Opções do canal, cargos.OPCOES_CANAL): um servidor que não quer propaganda de loja grande não tem que aguentar.
    parceiras = bool(cargos.opcoes_do_canal(canal).get('lojas_parceiras'))
    origem = origem if origem in ORIGENS else 'todas'
    if not parceiras:
        origem = 'servidor'
    termo = (busca or '').strip().lower()[:40]
    seed = bazar._seed_limpa(seed)
    do_servidor = select(server_members.c.person_id).where(server_members.c.server_id == canal.server_id)

    q = BazarLoja.query.filter(BazarLoja.aberta.isnot(False), BazarLoja.oculta.isnot(True), ~BazarLoja.owner_id.in_(bazar._subq_banidos()))
    if origem == 'servidor':
        q = q.filter(BazarLoja.owner_id.in_(do_servidor))
    elif origem == 'parceiras':
        q = q.filter(BazarLoja.porte == 'grande')
    else:
        q = q.filter(or_(BazarLoja.owner_id.in_(do_servidor), BazarLoja.porte == 'grande'))   # (só chega aqui com parceiras ligadas)
    if categoria in bazar.IDS_CATEGORIA:
        q = q.filter(BazarLoja.categoria == categoria)
    if termo:
        nos_produtos = select(BazarProduto.loja_id).where(BazarProduto.ativo.isnot(False), BazarProduto.oculta.isnot(True),
                                                         func.lower(BazarProduto.nome).contains(termo, autoescape=True))
        q = q.filter(or_(func.lower(BazarLoja.nome).contains(termo, autoescape=True),
                         func.lower(BazarLoja.descricao).contains(termo, autoescape=True), BazarLoja.id.in_(nos_produtos)))
    lojas = com_retry(lambda: q.limit(300).all())
    ids_servidor = {r[0] for r in com_retry(lambda: db.session.query(server_members.c.person_id)
                                            .filter(server_members.c.server_id == canal.server_id,
                                                    server_members.c.person_id.in_([l.owner_id for l in lojas] or [0])).all())}
    por_loja = com_retry(lambda: bazar._produtos_visiveis_de([l.id for l in lojas]))
    itens = []
    for l in lojas:
        prods = por_loja.get(l.id, [])
        if termo and termo not in (l.nome or '').lower() and termo not in (l.descricao or '').lower():
            prods = [p for p in prods if termo in p.nome.lower()]
        if not prods:
            continue                                       # loja sem nada à vista (ou sem nada que bata com a busca) não ocupa a vitrine
        j = bazar.loja_json(l, [bazar.produto_json(p) for p in prods[:4]])
        j['total_produtos'] = len(prods)
        j['origem'] = 'servidor' if l.owner_id in ids_servidor else 'parceira'
        itens.append((bazar._sorteio(seed, l.id), j))
    itens.sort(key=lambda t: t[0])
    resultado = [j for _, j in itens[:MAX_LOJAS]]
    cont = {}
    for _, j in itens:
        cont[j['categoria']] = cont.get(j['categoria'], 0) + 1
    return {'canal_id': canal.id, 'itens': resultado, 'total': len(itens), 'truncado': len(itens) > MAX_LOJAS, 'busca': termo, 'categoria': categoria if categoria in bazar.IDS_CATEGORIA else '',
            'origem': origem, 'parceiras': parceiras, 'seed': seed, 'categorias': [{'id': i, 'nome': n, 'qtd': cont.get(i, 0)} for i, n in bazar.CATEGORIAS]}
