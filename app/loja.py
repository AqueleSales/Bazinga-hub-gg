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
import random
from datetime import timedelta

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError

from .cosmeticos import CATALOGO, TEMAS, PACOTES, COLECOES, ROTULO_TIPO, RARIDADES, posses_da_pessoa
from .models import db, br_now, Person, Posse, MovimentoDrc, LojaEstoque
from .utils import comitar_com_retry, MISSOES

# Ordem em que os tipos aparecem na vitrine e o nome da prateleira de cada um.
PRATELEIRAS = [
    ('moldura', 'Molduras'),
    ('nome', 'Estilos de nome'),
    ('placa', 'Placas'),
    ('faixa', 'Faixas de perfil'),
]

# Grupos do filtro "tipo" da vitrine: (id, título, tipos do catálogo que entram). A ordem é a dos chips.
GRUPOS = [
    ('moldura', 'Molduras', ('moldura',)),
    ('nome', 'Nomes', ('nome',)),
    ('placa', 'Placas', ('placa',)),
    ('faixa', 'Faixas', ('faixa',)),
    ('efeito', 'Efeitos', ('efeito_avatar', 'efeito_perfil', 'efeito_fala', 'efeito_radar', 'efeito_chat', 'pin_nota', 'efeito_servidor')),
    ('som', 'Sons', ('som_call',)),
    ('pacote', 'Pacotes', ('pacote',)),
]
GRUPO_DO_TIPO = {t: g for g, _, tipos in GRUPOS for t in tipos}

# Faixas grandes do topo da loja (carrossel). `tema` precisa existir em TEMAS com loja=True.
DESTAQUES = [
    {'tema': 'gojo', 'selo': 'Lendário', 'titulo': 'Gojo', 'sub': 'Infinito, Seis Olhos e a Expansão de Domínio: o Vazio Ilimitado que enche o cartão, e o Azul e o Vermelho que viram Roxo. 12 itens.'},
    {'tema': 'sukuna', 'selo': 'Lendário', 'titulo': 'Sukuna', 'sub': 'Aura maldita, o seu nome em brasa, as marcas do rosto e montes de cortes pretos. 12 itens.'},
    {'tema': 'mahoraga', 'selo': 'Lendário', 'titulo': 'Mahoraga', 'sub': 'O timão dourado da Roda Divina: brilha, gira um pouco e para duro, e se adapta. 12 itens.'},
    {'tema': 'cyber', 'selo': 'Premium', 'titulo': 'Cyber Neon', 'sub': 'Scanlines, letreiro holográfico, chuva de dados e um "sistema online" ao entrar na call. 12 itens.'},
    {'tema': 'eldoria', 'selo': 'Premium', 'titulo': 'Eldoria', 'sub': 'Coroa de carvalho, pergaminho de runas, poeira mágica e um cristal no mapa. 12 itens.'},
    {'tema': 'arcade', 'selo': 'Premium', 'titulo': 'Arcade 8-bit', 'sub': 'Corações de vida, moedas girando, chuva de pixels e o som de uma moeda. 12 itens.'},
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


# ==========================================
# RELÍQUIA DA SEMANA: um item de tema da loja com desconto, trocando toda segunda-feira (horário de Brasília)
# ------------------------------------------------------------
# Determinístico (nada é guardado): a ordem das relíquias é um embaralhamento fixo do catálogo e a semana absoluta escolhe a vez.
# Assim ninguém repete antes de todo mundo ter passado, e o servidor e o cliente sempre concordam sem tabela nem agendador.
# ==========================================
DESCONTO_RELIQUIA = 0.25


def _segunda_de(agora):
    dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    return dia - timedelta(days=dia.weekday())


def _candidatas_reliquia():
    return sorted(i for i, d in CATALOGO.items() if d.get('preco') and d['tipo'] != 'pacote' and d['raridade'] != 'comum' and TEMAS.get(d['tema'], {}).get('loja'))


def reliquia_da_semana(agora=None):
    """item_id da relíquia desta semana (None se a loja não tem item de tema)."""
    pool = _candidatas_reliquia()
    if not pool:
        return None
    agora = agora or br_now()
    ordem = pool[:]
    random.Random('reliquias-do-armazem').shuffle(ordem)
    semana = (_segunda_de(agora).date() - _segunda_de(agora.replace(year=2026, month=1, day=5)).date()).days // 7
    return ordem[semana % len(ordem)]


def segundos_ate_trocar(agora=None):
    agora = agora or br_now()
    return max(int((_segunda_de(agora) + timedelta(days=7) - agora).total_seconds()), 0)


def _preco_com_reliquia(d, agora):
    """Preço de tabela, ou com o desconto da semana se este for o item da vez."""
    if d['tipo'] != 'pacote' and d['id'] == reliquia_da_semana(agora):
        return max(5, round(d['preco'] * (1 - DESCONTO_RELIQUIA) / 5) * 5)
    return d['preco']


# ==========================================
# EDIÇÕES LIMITADAS: por prazo (`ate`) e/ou por estoque (tabela loja_estoque, atômica)
# ==========================================
def _limites(agora=None):
    """{item_id: {...}} de tudo que é limitado, com quantas unidades já saíram (1 query)."""
    agora = agora or br_now()
    limitados = {i: d['limitado'] for i, d in CATALOGO.items() if d.get('limitado')}
    vendidos = {}
    if limitados:
        vendidos = {r.item_id: r.vendidos for r in LojaEstoque.query.filter(LojaEstoque.item_id.in_(list(limitados))).all()}
    saida = {}
    for i, lim in limitados.items():
        estoque, ate = lim.get('estoque'), lim.get('ate')
        restam = None if estoque is None else max(estoque - vendidos.get(i, 0), 0)
        encerrado = bool(ate and agora > ate)
        saida[i] = {'estoque': estoque, 'restam': restam, 'termina_em': max(int((ate - agora).total_seconds()), 0) if ate and not encerrado else None,
                    'encerrado': encerrado, 'esgotado': restam == 0}
    return saida


def _garantir_linha_estoque(item_id):
    if db.session.get(LojaEstoque, item_id) is None:
        try:
            with db.session.begin_nested():
                db.session.add(LojaEstoque(item_id=item_id, vendidos=0))
        except IntegrityError:
            pass          # outro pedido criou a linha junto: tudo bem, o UPDATE abaixo é quem decide


def _reservar_unidade(item_id, lim, agora):
    """Pega UMA unidade da edição limitada, ou levanta ErroLoja. Roda dentro da transação da compra: se o débito falhar
    depois, o rollback devolve a unidade."""
    if lim.get('ate') and agora > lim['ate']:
        raise ErroLoja('Essa edição já foi encerrada.')
    if lim.get('estoque') is None:
        return
    _garantir_linha_estoque(item_id)
    r = db.session.execute(update(LojaEstoque).where(LojaEstoque.item_id == item_id, LojaEstoque.vendidos < lim['estoque'])
                           .values(vendidos=LojaEstoque.vendidos + 1))
    if r.rowcount != 1:
        raise ErroLoja('Esgotado! Alguém levou a última unidade.')


# ==========================================
# COLEÇÃO: comprar itens do Armazém (os pacotes não contam, só o que eles entregam) desbloqueia prêmios que não se vendem
# ==========================================
def itens_comprados(person_id):
    """Quantos itens avulsos a pessoa JÁ comprou no Armazém (origem 'loja', fora os pacotes)."""
    return Posse.query.filter(Posse.person_id == person_id, Posse.origem == 'loja', ~Posse.item_id.like('pacote:%')).count()


def _conceder_premios(pessoa_id, posses_apos):
    """Dentro da transação da compra: dá os prêmios de coleção cuja meta foi batida. Devolve os item_ids novos."""
    db.session.flush()
    n = itens_comprados(pessoa_id)
    novos = []
    for c in COLECOES:
        if n >= c['meta'] and c['item_id'] not in posses_apos:
            try:
                with db.session.begin_nested():
                    db.session.add(Posse(person_id=pessoa_id, item_id=c['item_id'], origem='colecao'))
                novos.append(c['item_id'])
            except IntegrityError:
                pass
    return novos


def itens_do_pacote(tema):
    """item_ids avulsos que o pacote do tema entrega (sem o próprio pacote)."""
    return [f'{t}:{v}' for t, v in PACOTES.get(tema, {}).items() if _a_venda(f'{t}:{v}')]


def preco_para(posses, item_id, agora=None):
    """(preço final em DRC, ids que a compra entrega agora). Levanta ErroLoja se não dá pra comprar.

    Item avulso: o preço de tabela (ou o da relíquia da semana). Pacote: o preço de tabela, abatido em proporção do que a pessoa
    já tem avulso (ela não paga duas vezes pela mesma moldura). Se já tem tudo do pacote, ele sai
    de graça (só pra constar e poder "equipar tudo")."""
    d = _a_venda(item_id)
    if not d:
        raise ErroLoja('Este item não está à venda.')
    if item_id in posses:
        raise ErroLoja('Você já tem esse item.')

    if d['tipo'] != 'pacote':
        return _preco_com_reliquia(d, agora or br_now()), [item_id]

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
        resultado.clear()
        agora = br_now()
        posses = posses_da_pessoa(pessoa.id)
        preco, entregues = preco_para(posses, item_id, agora)
        if preco_esperado is not None and int(preco_esperado) != preco:
            raise ErroLoja(f'O preço mudou para {preco} DRC. Confira e tente de novo.')
        for i in entregues:
            lim = CATALOGO[i].get('limitado')
            if lim:
                _reservar_unidade(i, lim, agora)

        if preco > 0:
            if not _debitar(pessoa.id, preco):
                raise ErroLoja('Você não tem DRC suficiente.')
            db.session.refresh(pessoa, ['bazinga_coins'])
            db.session.add(MovimentoDrc(person_id=pessoa.id, delta=-preco, saldo_apos=pessoa.bazinga_coins,
                                        motivo='compra', ref=item_id))
        for i in entregues:
            db.session.add(Posse(person_id=pessoa.id, item_id=i, origem='loja'))
        premios = _conceder_premios(pessoa.id, posses | set(entregues))
        resultado.update(item_id=item_id, nome=CATALOGO[item_id]['nome'], preco=preco, entregues=entregues + premios,
                         premios=[{'item_id': x, 'nome': CATALOGO[x]['nome']} for x in premios])

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
def _item_json(d, posses, limites, agora, reliquia):
    possui = d['id'] in posses
    j = {k: d[k] for k in ('id', 'tipo', 'valor', 'nome', 'desc', 'tema', 'raridade', 'preco')}
    j['possui'] = possui
    j['rotulo'] = ROTULO_TIPO.get(d['tipo'], d['tipo'])
    j['grupo'] = GRUPO_DO_TIPO.get(d['tipo'], d['tipo'])
    j['animado'] = d.get('animado', True)
    if d['tipo'] == 'pacote' and not possui:
        try:
            j['preco_final'] = preco_para(posses, d['id'], agora)[0]
        except ErroLoja:
            j['preco_final'] = d['preco']
    else:
        j['preco_final'] = d['preco']
    if d['id'] == reliquia and not possui:
        j['preco_final'] = _preco_com_reliquia(d, agora)
        j['reliquia'] = True
    if d['id'] in limites:
        j['limitado'] = limites[d['id']]
    return j


def _premio_json(c, posses, comprados):
    d = CATALOGO[c['item_id']]
    item = {k: d[k] for k in ('id', 'tipo', 'valor', 'nome', 'desc', 'tema', 'raridade')}
    item['rotulo'] = ROTULO_TIPO.get(d['tipo'], d['tipo'])
    return {'meta': c['meta'], 'item': item, 'ganho': c['item_id'] in posses, 'faltam': max(c['meta'] - comprados, 0)}


def vitrine_para_json(pessoa, posses=None):
    """A loja inteira, na medida de UMA pessoa (o que ela já tem, o preço do pacote pra ela)."""
    posses = posses_da_pessoa(pessoa.id) if posses is None else posses
    agora = br_now()
    reliquia = reliquia_da_semana(agora)
    limites = _limites(agora)
    itens = [_item_json(d, posses, limites, agora, reliquia) for d in CATALOGO.values() if d.get('preco')]
    comprados = itens_comprados(pessoa.id)
    temas = []
    for tid, t in TEMAS.items():
        if not t.get('loja'):
            continue
        avulsos = itens_do_pacote(tid)
        total = sum(CATALOGO[i]['preco'] for i in avulsos)
        pacote_id = f'pacote:{tid}'
        temas.append({
            'id': tid, 'nome': t['nome'], 'cor': t['cor'], 'cores': t['cores'], 'icone': t['icone'], 'lema': t['lema'],
            'premium': bool(t.get('premium')), 'sem_hero': bool(t.get('sem_hero')),
            'desc': t['desc'], 'pacote': pacote_id if _a_venda(pacote_id) else None, 'itens': avulsos,
            'preco_soma': total, 'preco_pacote': (CATALOGO.get(pacote_id) or {}).get('preco'),
        })
    return {
        'saldo': pessoa.bazinga_coins or 0,
        'temas': temas, 'itens': itens,
        'prateleiras': [{'tipo': t, 'titulo': n} for t, n in PRATELEIRAS],
        'grupos': [{'id': g, 'titulo': n} for g, n, _ in GRUPOS],
        'raridades': RARIDADES,
        'destaques': [x for x in DESTAQUES if TEMAS.get(x['tema'], {}).get('loja')],
        'reliquia': {'item_id': reliquia, 'desconto': int(DESCONTO_RELIQUIA * 100), 'termina_em': segundos_ate_trocar(agora)} if reliquia else None,
        'colecao': {'comprados': comprados, 'premios': [_premio_json(c, posses, comprados) for c in COLECOES]},
    }


# ==========================================
# EXTRATO (histórico de DRC): o livro-razão visto pela própria pessoa
# ==========================================
ROTULO_MOTIVO = {'compra': 'Compra', 'nivel': 'Subiu de nível', 'missao': 'Missão', 'ajuste': 'Ajuste'}


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
        elif m.motivo == 'missao':
            nomes = [MISSOES[c]['titulo'] for c in (m.ref or '').split(',') if c in MISSOES]
            titulo = 'Missão: ' + ' + '.join(nomes) if nomes else 'Missão concluída'
        else:
            titulo = ROTULO_MOTIVO.get(m.motivo, m.motivo)
        itens.append({'delta': m.delta, 'saldo_apos': m.saldo_apos, 'motivo': m.motivo, 'rotulo': ROTULO_MOTIVO.get(m.motivo, m.motivo),
                      'titulo': titulo, 'hora': m.created_at.strftime('%d/%m %H:%M') if m.created_at else ''})
    ganho = db.session.query(func.coalesce(func.sum(MovimentoDrc.delta), 0)).filter(MovimentoDrc.person_id == pessoa.id, MovimentoDrc.delta > 0).scalar() or 0
    gasto = db.session.query(func.coalesce(func.sum(MovimentoDrc.delta), 0)).filter(MovimentoDrc.person_id == pessoa.id, MovimentoDrc.delta < 0).scalar() or 0
    return {'saldo': pessoa.bazinga_coins or 0, 'itens': itens, 'ganho_total': int(ganho), 'gasto_total': int(-gasto)}
