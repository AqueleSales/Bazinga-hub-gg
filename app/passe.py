"""Passe de Batalha (temporadas) e títulos. Só regra e dados; os handlers do socket moram em `passe_events.py` e o painel
do admin em `admin.py`.

O que o admin controla (tudo é DADO no banco, nada de código): a temporada (nome, tema visual, datas, quantos níveis, XP por
nível, catch-up), o que cada nível entrega na trilha GRÁTIS e na PREMIUM (moedas, item do catálogo, título ou tema do app) e a
lista de títulos. Regras que não se negociam (regra 4 do CLAUDE.md):
  * O servidor decide nível, direito à trilha premium e o que cai. O cliente só diz QUAL recompensa quer resgatar.
  * Resgatar é UMA transação: `PasseResgate` é único por pessoa+temporada+nível+trilha, então clique duplo/2 abas nunca pagam
    duas vezes (a 2ª tentativa dá IntegrityError e a transação inteira é desfeita).
  * O XP do passe é separado do nível da conta: todo XP ganho (mensagem, tempo, missão...) também vale pra temporada ativa,
    dentro da janela de datas (`somar_xp`, chamado de dentro do `_somar_xp` do utils, na mesma transação).
  * Só UMA temporada fica ativa por vez. Sem data (inicio/fim vazios) a temporada fica aberta até o admin encerrar.
"""
import re
from datetime import timedelta

from sqlalchemy import update, case
from sqlalchemy.exc import IntegrityError

from .cosmeticos import CATALOGO, ROTULO_TIPO, descritor, posses_da_pessoa
from .models import (db, br_now, Person, Posse, MovimentoDrc, PasseTemporada, PasseRecompensa, PassePessoa,
                     PasseResgate, Titulo)
from .utils import comitar_com_retry, com_retry, TEMAS_EXCLUSIVOS, CORES_TEMAS_EXCLUSIVOS, nome_do_tema


class ErroPasse(Exception):
    """Erro de regra (mostrado como toast). Passa direto pelo com_retry (só OperationalError é refeito)."""


# Identidade visual de cada temporada (a página do passe ganha as cores/ícone/lema; o CSS é `[data-passe="<id>"]`).
TEMAS_PASSE = {
    'deuses': {'nome': 'Deuses', 'cor': '#d4a24c', 'cor2': '#e9d9a6', 'icone': 'fa-landmark', 'lema': 'Do mármore ao trovão: suba até o Olimpo.'},
    'neutro': {'nome': 'Neutro', 'cor': '#8ea0ba', 'cor2': '#cbd5e1', 'icone': 'fa-ranking-star', 'lema': 'Uma nova temporada começa.'},
}
ANIMACOES_TITULO = ('brilho', 'chama', 'onda', 'glitch')          # `.titulo-anim-<id>` no CSS
RARIDADES_TITULO = ('comum', 'raro', 'epico', 'lendario')
TRILHAS = ('gratis', 'premium')
TIPOS_RECOMPENSA = ('moeda', 'item', 'titulo', 'tema')
MAX_NIVEIS = 200
MAX_MOEDAS_RECOMPENSA = 100000
_RE_ID_TITULO = re.compile(r'^[a-z_]{2,24}$')

ROTULO_TIPO_RECOMPENSA = {'moeda': 'Moedas', 'item': 'Item', 'titulo': 'Título', 'tema': 'Tema do app'}


# ==========================================
# CACHE (o passe é lido a cada mensagem que dá XP; recompensas e títulos mudam só quando o admin mexe)
# ==========================================
_TTL = 20
_cache = {'quando': None, 'snap': None}
_cache_titulos = {'quando': None, 'por_id': {}}


def invalidar_cache():
    _cache['quando'] = None
    _cache_titulos['quando'] = None


def _fresco(c):
    return c['quando'] is not None and (br_now() - c['quando']).total_seconds() < _TTL


def _montar_snapshot():
    t = PasseTemporada.query.filter_by(ativa=True).order_by(PasseTemporada.id.desc()).first()
    if not t:
        return None
    recs = {}
    for r in PasseRecompensa.query.filter_by(temporada_id=t.id).all():
        recs[(r.nivel, r.trilha)] = {'tipo': r.tipo, 'valor': r.valor, 'quantidade': r.quantidade or 0}
    return {'id': t.id, 'nome': t.nome, 'subtitulo': t.subtitulo, 'tema': t.tema, 'inicio': t.inicio, 'fim': t.fim,
            'niveis': t.niveis, 'xp_por_nivel': t.xp_por_nivel, 'catchup_dias': t.catchup_dias or 0,
            'catchup_pct': t.catchup_pct or 0, 'recs': recs}


def temporada_ativa():
    """Foto (dict) da temporada ativa ou None. Em cache por ~20 s; o painel do admin invalida na hora."""
    if not _fresco(_cache):
        _cache['snap'] = com_retry(_montar_snapshot)
        _cache['quando'] = br_now()
    return _cache['snap']


def _na_janela(snap, agora=None):
    agora = agora or br_now()
    return bool(snap) and (snap['inicio'] is None or snap['inicio'] <= agora) and (snap['fim'] is None or snap['fim'] > agora)


def _com_catchup(snap, quantidade, agora):
    """Nos últimos `catchup_dias` antes do fim o XP do passe rende `catchup_pct`% a mais (quem entrou tarde alcança)."""
    if snap['fim'] and snap['catchup_pct'] and snap['catchup_dias'] and 0 < (snap['fim'] - agora).total_seconds() <= snap['catchup_dias'] * 86400:
        return quantidade * (100 + snap['catchup_pct']) // 100
    return quantidade


def _catchup_ativo(snap, agora):
    return _com_catchup(snap, 100, agora) != 100


def _tetoxp(snap):
    return snap['niveis'] * snap['xp_por_nivel']


# ==========================================
# XP DO PASSE
# ==========================================
def somar_xp(pessoa, quantidade):
    """Soma `quantidade` de XP no passe da temporada ativa. Chamar DENTRO de um preparar() de `comitar_com_retry`
    (é o `_somar_xp` do utils que chama). Nunca levanta por falta de temporada: sem ela, não faz nada."""
    if quantidade <= 0:
        return
    snap = temporada_ativa()
    agora = br_now()
    if not _na_janela(snap, agora):
        return
    q = _com_catchup(snap, int(quantidade), agora)
    teto = _tetoxp(snap)
    novo = PassePessoa.xp + q
    alvo = (PassePessoa.person_id == pessoa.id) & (PassePessoa.temporada_id == snap['id'])
    r = db.session.execute(update(PassePessoa).where(alvo).values(xp=case((novo > teto, teto), else_=novo)))
    if r.rowcount:
        return
    try:
        with db.session.begin_nested():
            db.session.add(PassePessoa(person_id=pessoa.id, temporada_id=snap['id'], xp=min(q, teto), premium=False))
            db.session.flush()
    except IntegrityError:
        # duas somas ao mesmo tempo na 1ª vez da temporada: a outra criou a linha, agora é só somar
        db.session.execute(update(PassePessoa).where(alvo).values(xp=case((novo > teto, teto), else_=novo)))


# ==========================================
# TÍTULOS
# ==========================================
def _titulos_por_id():
    if not _fresco(_cache_titulos):
        _cache_titulos['por_id'] = com_retry(lambda: {t.id: _titulo_json(t) for t in Titulo.query.all()})
        _cache_titulos['quando'] = br_now()
    return _cache_titulos['por_id']


def _titulo_json(t):
    return {'id': t.id, 'texto': t.texto, 'anim': t.animacao or '', 'raridade': t.raridade or 'raro', 'descricao': t.descricao or ''}


def titulo_publico(titulo_id):
    """O título pronto pra ir num payload de perfil ({id, texto, anim, raridade}) ou None."""
    return _titulos_por_id().get(titulo_id) if titulo_id else None


def titulos_da_pessoa(posses):
    """Todos os títulos que a pessoa tem (posse 'titulo:<id>'), na ordem de raridade."""
    ordem = {r: i for i, r in enumerate(RARIDADES_TITULO)}
    lista = [t for tid, t in _titulos_por_id().items() if f'titulo:{tid}' in posses]
    return sorted(lista, key=lambda t: (ordem.get(t['raridade'], 0), t['texto']))


def equipar_titulo(pessoa, titulo_id):
    """Equipa (ou tira, com None) um título. Só vale o que a pessoa possui (regra 4)."""
    if titulo_id:
        if titulo_id not in _titulos_por_id():
            raise ErroPasse('Esse título não existe.')
        if f'titulo:{titulo_id}' not in posses_da_pessoa(pessoa.id):
            raise ErroPasse('Você ainda não ganhou esse título.')

    def preparar():
        pessoa.titulo_id = titulo_id or None

    comitar_com_retry(preparar)


def _validar_titulo(dados):
    tid = str(dados.get('id') or '').strip().lower()
    if not _RE_ID_TITULO.match(tid):
        raise ErroPasse('O id do título usa só letras minúsculas e _ (2 a 24 caracteres).')
    texto = str(dados.get('texto') or '').strip()
    if not 2 <= len(texto) <= 32:
        raise ErroPasse('O texto do título tem de 2 a 32 caracteres.')
    anim = (dados.get('animacao') or '').strip() or None
    if anim and anim not in ANIMACOES_TITULO:
        raise ErroPasse('Animação de título desconhecida.')
    rar = dados.get('raridade') or 'raro'
    if rar not in RARIDADES_TITULO:
        raise ErroPasse('Raridade desconhecida.')
    return tid, texto, anim, rar, (str(dados.get('descricao') or '').strip()[:120] or None)


def salvar_titulo(dados):
    tid, texto, anim, rar, desc = _validar_titulo(dados)

    def preparar():
        t = Titulo.query.get(tid)
        if not t:
            t = Titulo(id=tid)
            db.session.add(t)
        t.texto, t.animacao, t.raridade, t.descricao = texto, anim, rar, desc

    comitar_com_retry(preparar)
    invalidar_cache()
    return tid


def apagar_titulo(tid):
    """Apaga o título, tira de quem o usa e remove a posse. Recompensas que ainda o citam ficam sem efeito até o admin trocar."""
    def preparar():
        Titulo.query.filter_by(id=tid).delete()
        Posse.query.filter_by(item_id=f'titulo:{tid}').delete()
        Person.query.filter_by(titulo_id=tid).update({'titulo_id': None})

    comitar_com_retry(preparar)
    invalidar_cache()


def lista_de_titulos():
    return sorted(_titulos_por_id().values(), key=lambda t: t['texto'])


# ==========================================
# O QUE O CLIENTE VÊ
# ==========================================
def _recompensa_json(r):
    """Descreve uma recompensa pra tela (nome, ícone, raridade, e os campos do item pra prévia animada). Nada de preço/posse aqui."""
    if not r:
        return None
    tipo = r['tipo']
    if tipo == 'moeda':
        return {'tipo': 'moeda', 'nome': f"{r['quantidade']}", 'quantidade': r['quantidade'], 'rotulo': 'Moedas'}
    if tipo == 'item':
        d = descritor(r['valor'])
        if not d:
            return {'tipo': 'item', 'nome': 'Item removido', 'invalido': True, 'rotulo': 'Item'}
        item = {k: d[k] for k in ('id', 'tipo', 'valor', 'nome', 'desc', 'tema', 'raridade')}
        return {'tipo': 'item', 'nome': d['nome'], 'rotulo': ROTULO_TIPO.get(d['tipo'], d['tipo']), 'item': item, 'raridade': d['raridade']}
    if tipo == 'titulo':
        t = _titulos_por_id().get(r['valor'])
        if not t:
            return {'tipo': 'titulo', 'nome': 'Título removido', 'invalido': True, 'rotulo': 'Título'}
        return {'tipo': 'titulo', 'nome': t['texto'], 'titulo': t, 'rotulo': 'Título', 'raridade': t['raridade']}
    if tipo == 'tema':
        nome = nome_do_tema(r['valor'])
        return {'tipo': 'tema', 'nome': nome or 'Tema', 'tema': r['valor'], 'rotulo': 'Tema do app', 'cores': CORES_TEMAS_EXCLUSIVOS.get(r['valor'], [])}
    return None


def estado(pessoa):
    """O passe inteiro na medida de UMA pessoa. Sem temporada ativa: {'ativa': False}."""
    snap = temporada_ativa()
    if not snap:
        from .bazar import eh_admin
        return {'ativa': False, 'admin': eh_admin(pessoa)}
    agora = br_now()
    pp = com_retry(lambda: PassePessoa.query.filter_by(person_id=pessoa.id, temporada_id=snap['id']).first())
    xp = pp.xp if pp else 0
    premium = bool(pp and pp.premium)
    feitos = com_retry(lambda: {(r.nivel, r.trilha) for r in PasseResgate.query.filter_by(person_id=pessoa.id, temporada_id=snap['id']).all()})
    por_nivel = max(snap['xp_por_nivel'], 1)
    nivel = min(xp // por_nivel, snap['niveis'])
    niveis = []
    for n in range(1, snap['niveis'] + 1):
        linha = {'n': n}
        for trilha in TRILHAS:
            rec = _recompensa_json(snap['recs'].get((n, trilha)))
            if rec:
                rec['resgatado'] = (n, trilha) in feitos
                rec['liberado'] = nivel >= n and (trilha == 'gratis' or premium)
            linha[trilha] = rec
        niveis.append(linha)
    resta = int((snap['fim'] - agora).total_seconds()) if snap['fim'] else None
    from .bazar import eh_admin
    return {
        'admin': eh_admin(pessoa),
        'ativa': True, 'id': snap['id'], 'nome': snap['nome'], 'subtitulo': snap['subtitulo'] or '',
        'tema': snap['tema'], 'visual': TEMAS_PASSE.get(snap['tema'], TEMAS_PASSE['neutro']),
        'janela_aberta': _na_janela(snap, agora), 'comeca_em': int((snap['inicio'] - agora).total_seconds()) if snap['inicio'] and snap['inicio'] > agora else None,
        'segundos_restantes': max(resta, 0) if resta is not None else None, 'catchup': _catchup_ativo(snap, agora), 'catchup_pct': snap['catchup_pct'],
        'xp': xp, 'nivel': nivel, 'niveis_total': snap['niveis'], 'xp_por_nivel': por_nivel,
        'xp_no_nivel': 0 if nivel >= snap['niveis'] else xp - nivel * por_nivel,
        'premium': premium, 'niveis': niveis,
        'pendentes': sum(1 for l in niveis for t in TRILHAS if l.get(t) and l[t]['liberado'] and not l[t]['resgatado'] and not l[t].get('invalido')),
    }


# ==========================================
# RESGATE
# ==========================================
def _entregar(pessoa, rec, nivel, resultado):
    """Entrega UMA recompensa dentro da transação aberta (quem chama comita)."""
    tipo = rec['tipo']
    if tipo == 'moeda':
        q = int(rec['quantidade'] or 0)
        if q > 0:
            db.session.execute(update(Person).where(Person.id == pessoa.id).values(bazinga_coins=db.func.coalesce(Person.bazinga_coins, 0) + q))
            db.session.refresh(pessoa, ['bazinga_coins'])
            db.session.add(MovimentoDrc(person_id=pessoa.id, delta=q, saldo_apos=pessoa.bazinga_coins, motivo='passe', ref=f'nivel {nivel}'))
            resultado['moedas'] += q
        return
    if tipo == 'item':
        item_id = rec['valor']
        if item_id not in CATALOGO:
            return
        nome = CATALOGO[item_id]['nome']
    elif tipo == 'titulo':
        t = _titulos_por_id().get(rec['valor'])
        if not t:
            return
        item_id, nome = f"titulo:{t['id']}", t['texto']
    elif tipo == 'tema':
        if rec['valor'] not in TEMAS_EXCLUSIVOS:
            return
        item_id, nome = f"tema:{rec['valor']}", nome_do_tema(rec['valor'])
    else:
        return
    if not Posse.query.filter_by(person_id=pessoa.id, item_id=item_id).first():
        db.session.add(Posse(person_id=pessoa.id, item_id=item_id, origem='passe'))
        resultado['itens'].append({'tipo': tipo, 'nome': nome, 'item_id': item_id})


def resgatar(pessoa, nivel=None, trilha=None):
    """Resgata uma recompensa (nivel+trilha) ou, sem argumentos, TUDO o que está liberado e ainda não foi pego.
    Devolve {'moedas', 'itens', 'qtd'}."""
    snap = temporada_ativa()
    if not snap:
        raise ErroPasse('Não há temporada ativa.')
    if trilha is not None and trilha not in TRILHAS:
        raise ErroPasse('Trilha inválida.')
    resultado = {'moedas': 0, 'itens': [], 'qtd': 0}

    def preparar():
        resultado.update(moedas=0, itens=[], qtd=0)
        pp = PassePessoa.query.filter_by(person_id=pessoa.id, temporada_id=snap['id']).first()
        xp = pp.xp if pp else 0
        atual = min(xp // max(snap['xp_por_nivel'], 1), snap['niveis'])
        premium = bool(pp and pp.premium)
        feitos = {(r.nivel, r.trilha) for r in PasseResgate.query.filter_by(person_id=pessoa.id, temporada_id=snap['id']).all()}
        if nivel is not None:
            alvos = [(int(nivel), trilha)]
        else:
            alvos = sorted((n, t) for (n, t) in snap['recs'] if n <= atual)
        for n, t in alvos:
            rec = snap['recs'].get((n, t))
            if not rec:
                if nivel is not None:
                    raise ErroPasse('Esse nível não tem recompensa nessa trilha.')
                continue
            if n > atual:
                raise ErroPasse('Você ainda não chegou nesse nível.')
            if t == 'premium' and not premium:
                if nivel is not None:
                    raise ErroPasse('Essa recompensa é da trilha Premium.')
                continue
            if (n, t) in feitos:
                if nivel is not None:
                    raise ErroPasse('Você já resgatou essa recompensa.')
                continue
            db.session.add(PasseResgate(person_id=pessoa.id, temporada_id=snap['id'], nivel=n, trilha=t))
            _entregar(pessoa, rec, n, resultado)
            resultado['qtd'] += 1

    try:
        comitar_com_retry(preparar)
    except IntegrityError:
        db.session.rollback()
        raise ErroPasse('Você já resgatou essa recompensa.')
    if not resultado['qtd'] and nivel is None:
        raise ErroPasse('Não há nada novo pra resgatar.')
    db.session.refresh(pessoa, ['bazinga_coins'])
    return resultado


def definir_premium(person_id, ativo=True):
    """Libera/tira a trilha premium da temporada ativa (hoje só o admin; depois, a assinatura)."""
    snap = temporada_ativa()
    if not snap:
        raise ErroPasse('Não há temporada ativa.')

    def preparar():
        pp = PassePessoa.query.filter_by(person_id=person_id, temporada_id=snap['id']).first()
        if not pp:
            pp = PassePessoa(person_id=person_id, temporada_id=snap['id'], xp=0)
            db.session.add(pp)
        pp.premium = bool(ativo)

    comitar_com_retry(preparar)


# ==========================================
# ADMIN: temporadas e recompensas
# ==========================================
def _data(v):
    """'2026-10-15T20:00' (do <input type=datetime-local>) ou vazio -> datetime sem fuso (horário de Brasília) ou None."""
    from datetime import datetime
    v = (v or '').strip() if isinstance(v, str) else v
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        raise ErroPasse('Data inválida.')


def temporada_para_json(t):
    return {'id': t.id, 'nome': t.nome, 'subtitulo': t.subtitulo or '', 'tema': t.tema, 'ativa': bool(t.ativa),
            'inicio': t.inicio.strftime('%Y-%m-%dT%H:%M') if t.inicio else '', 'fim': t.fim.strftime('%Y-%m-%dT%H:%M') if t.fim else '',
            'niveis': t.niveis, 'xp_por_nivel': t.xp_por_nivel, 'catchup_dias': t.catchup_dias or 0, 'catchup_pct': t.catchup_pct or 0}


def listar_temporadas():
    return [temporada_para_json(t) for t in PasseTemporada.query.order_by(PasseTemporada.id.desc()).all()]


def salvar_temporada(dados, tid=None):
    nome = str(dados.get('nome') or '').strip()
    if not 2 <= len(nome) <= 60:
        raise ErroPasse('O nome da temporada tem de 2 a 60 caracteres.')
    tema = dados.get('tema') or 'deuses'
    if tema not in TEMAS_PASSE:
        raise ErroPasse('Tema visual desconhecido.')
    try:
        niveis = int(dados.get('niveis') or 100)
        xpn = int(dados.get('xp_por_nivel') or 800)
        cdias = int(dados.get('catchup_dias') or 0)
        cpct = int(dados.get('catchup_pct') or 0)
    except (TypeError, ValueError):
        raise ErroPasse('Os números da temporada estão inválidos.')
    if not 1 <= niveis <= MAX_NIVEIS:
        raise ErroPasse(f'A temporada tem de 1 a {MAX_NIVEIS} níveis.')
    if not 50 <= xpn <= 100000:
        raise ErroPasse('O XP por nível tem de ficar entre 50 e 100.000.')
    if not (0 <= cdias <= 90 and 0 <= cpct <= 300):
        raise ErroPasse('Catch-up: de 0 a 90 dias e de 0 a 300%.')
    inicio, fim = _data(dados.get('inicio')), _data(dados.get('fim'))
    if inicio and fim and fim <= inicio:
        raise ErroPasse('O fim tem de ser depois do início.')
    sub = str(dados.get('subtitulo') or '').strip()[:120] or None
    saida = {}

    def preparar():
        t = PasseTemporada.query.get(tid) if tid else None
        if tid and not t:
            raise ErroPasse('Temporada não encontrada.')
        if not t:
            t = PasseTemporada(ativa=False)
            db.session.add(t)
        t.nome, t.subtitulo, t.tema, t.niveis, t.xp_por_nivel = nome, sub, tema, niveis, xpn
        t.catchup_dias, t.catchup_pct, t.inicio, t.fim = cdias, cpct, inicio, fim
        if tid:
            # encolher a temporada apaga as recompensas dos níveis que deixaram de existir
            PasseRecompensa.query.filter(PasseRecompensa.temporada_id == t.id, PasseRecompensa.nivel > niveis).delete()
        db.session.flush()
        saida['id'] = t.id

    comitar_com_retry(preparar)
    invalidar_cache()
    return saida['id']


def ativar_temporada(tid, ativa=True):
    """Ativa (desativando as outras) ou encerra uma temporada."""
    def preparar():
        t = PasseTemporada.query.get(tid)
        if not t:
            raise ErroPasse('Temporada não encontrada.')
        if ativa:
            PasseTemporada.query.filter(PasseTemporada.id != tid).update({'ativa': False})
        t.ativa = bool(ativa)

    comitar_com_retry(preparar)
    invalidar_cache()


def apagar_temporada(tid):
    """Só apaga temporada SEM progresso de ninguém (senão perderia o histórico do que as pessoas pegaram)."""
    def preparar():
        t = PasseTemporada.query.get(tid)
        if not t:
            raise ErroPasse('Temporada não encontrada.')
        if t.ativa:
            raise ErroPasse('Encerre a temporada antes de apagar.')
        if PassePessoa.query.filter(PassePessoa.temporada_id == tid, PassePessoa.xp > 0).first() or PasseResgate.query.filter_by(temporada_id=tid).first():
            raise ErroPasse('Essa temporada já tem gente jogando. Encerre em vez de apagar.')
        PassePessoa.query.filter_by(temporada_id=tid).delete()
        PasseRecompensa.query.filter_by(temporada_id=tid).delete()
        db.session.delete(t)

    comitar_com_retry(preparar)
    invalidar_cache()


def recompensas_da_temporada(tid):
    return [{'nivel': r.nivel, 'trilha': r.trilha, 'tipo': r.tipo, 'valor': r.valor or '', 'quantidade': r.quantidade or 0}
            for r in PasseRecompensa.query.filter_by(temporada_id=tid).order_by(PasseRecompensa.nivel).all()]


def _validar_recompensa(r, niveis):
    try:
        n = int(r.get('nivel'))
    except (TypeError, ValueError):
        raise ErroPasse('Nível inválido.')
    if not 1 <= n <= niveis:
        raise ErroPasse(f'O nível {n} está fora da temporada (1 a {niveis}).')
    trilha, tipo = r.get('trilha'), r.get('tipo')
    if trilha not in TRILHAS:
        raise ErroPasse('Trilha inválida.')
    if tipo is None or tipo == '':
        return n, trilha, None, None, 0                       # slot vazio: apaga
    if tipo not in TIPOS_RECOMPENSA:
        raise ErroPasse('Tipo de recompensa inválido.')
    valor, qtd = None, 0
    if tipo == 'moeda':
        try:
            qtd = int(r.get('quantidade'))
        except (TypeError, ValueError):
            raise ErroPasse('Quantidade de moedas inválida.')
        if not 1 <= qtd <= MAX_MOEDAS_RECOMPENSA:
            raise ErroPasse(f'Moedas: de 1 a {MAX_MOEDAS_RECOMPENSA}.')
    else:
        valor = str(r.get('valor') or '').strip()
        if tipo == 'item':
            d = CATALOGO.get(valor)
            if not d or d['tipo'] == 'pacote':
                raise ErroPasse(f'Item "{valor}" não existe no catálogo (ou é um pacote).')
        elif tipo == 'titulo':
            if valor not in _titulos_por_id():
                raise ErroPasse(f'Título "{valor}" não existe.')
        elif tipo == 'tema':
            if valor not in TEMAS_EXCLUSIVOS:
                raise ErroPasse(f'Tema "{valor}" não é um tema de temporada.')
    return n, trilha, tipo, valor, qtd


def salvar_recompensas(tid, lista, substituir=False):
    """Grava (por nível+trilha) uma lista de recompensas. Item com `tipo` vazio apaga o slot. Com `substituir`, limpa a temporada antes."""
    if not isinstance(lista, list) or len(lista) > MAX_NIVEIS * 2:
        raise ErroPasse('Lista de recompensas inválida.')

    def preparar():
        t = PasseTemporada.query.get(tid)
        if not t:
            raise ErroPasse('Temporada não encontrada.')
        validas = [_validar_recompensa(r, t.niveis) for r in lista]
        if substituir:
            PasseRecompensa.query.filter_by(temporada_id=tid).delete()
            db.session.flush()
        for n, trilha, tipo, valor, qtd in validas:
            atual = PasseRecompensa.query.filter_by(temporada_id=tid, nivel=n, trilha=trilha).first()
            if tipo is None:
                if atual:
                    db.session.delete(atual)
                continue
            if not atual:
                atual = PasseRecompensa(temporada_id=tid, nivel=n, trilha=trilha)
                db.session.add(atual)
            atual.tipo, atual.valor, atual.quantidade = tipo, valor, qtd

    comitar_com_retry(preparar)
    invalidar_cache()


# ------------------------------------------------------------
# MODELO: a Temporada 1 "Deuses" (100 níveis). Moedas em todo nível, e a cada marco um prêmio de verdade.
# Só usa ids que existem (itens do catálogo, títulos que o próprio modelo cria, temas de temporada).
# ------------------------------------------------------------
TITULOS_MODELO = [
    {'id': 'aspirante_olimpo', 'texto': 'Aspirante ao Olimpo', 'raridade': 'comum', 'descricao': 'Temporada Deuses, nível 5'},
    {'id': 'mortal_ilustre', 'texto': 'Mortal Ilustre', 'raridade': 'raro', 'descricao': 'Temporada Deuses, nível 15'},
    {'id': 'heroi_de_atenas', 'texto': 'Herói de Atenas', 'raridade': 'raro', 'descricao': 'Temporada Deuses, nível 35'},
    {'id': 'favorito_dos_deuses', 'texto': 'Favorito dos Deuses', 'raridade': 'epico', 'animacao': 'brilho', 'descricao': 'Temporada Deuses, nível 55'},
    {'id': 'filho_do_trovao', 'texto': 'Filho do Trovão', 'raridade': 'epico', 'animacao': 'brilho', 'descricao': 'Temporada Deuses, trilha Premium'},
    {'id': 'senhor_do_olimpo', 'texto': 'Senhor do Olimpo', 'raridade': 'lendario', 'animacao': 'chama', 'descricao': 'Temporada Deuses, nível 100 Premium'},
]


def modelo_deuses(tid):
    """Preenche a temporada `tid` com o modelo "Deuses" (apaga o que tinha). Cria os títulos que faltam."""
    from .cosmeticos import CATALOGO as C
    for t in TITULOS_MODELO:
        if not Titulo.query.get(t['id']):
            salvar_titulo(t)
    existe = lambda i: i in C
    marcos_gratis = {5: ('titulo', 'aspirante_olimpo'), 10: ('item', 'moldura:louros'), 15: ('titulo', 'mortal_ilustre'),
                     20: ('item', 'efeito_perfil:olimpo'), 30: ('item', 'placa:marmore'), 35: ('titulo', 'heroi_de_atenas'),
                     45: ('tema', 'templo'), 55: ('titulo', 'favorito_dos_deuses'), 70: ('item', 'faixa:partenon'),
                     100: ('item', 'nome:olimpo')}
    marcos_premium = {10: ('item', 'moldura:coroa_zeus'), 20: ('item', 'nome:ambrosia'), 30: ('titulo', 'filho_do_trovao'),
                      40: ('tema', 'tartaro'), 60: ('item', 'efeito_avatar:relampago'), 80: ('item', 'efeito_perfil:tempestade'),
                      100: ('titulo', 'senhor_do_olimpo')}
    lista = []
    for n in range(1, 101):
        for trilha, marcos, base in (('gratis', marcos_gratis, 50), ('premium', marcos_premium, 120)):
            marco = marcos.get(n)
            if marco and (marco[0] != 'item' or existe(marco[1])):
                lista.append({'nivel': n, 'trilha': trilha, 'tipo': marco[0], 'valor': marco[1]})
            else:
                moedas = base * (3 if n % 10 == 0 else 2 if n % 5 == 0 else 1)
                lista.append({'nivel': n, 'trilha': trilha, 'tipo': 'moeda', 'quantidade': moedas})
    salvar_recompensas(tid, lista, substituir=True)
    return len(lista)


def criar_temporada_modelo():
    """Cria (inativa) a Temporada 1 'Deuses' já com as 100 recompensas. Devolve o id."""
    tid = salvar_temporada({'nome': 'Temporada 1: Deuses', 'subtitulo': 'Do mármore ao trovão: suba até o Olimpo.', 'tema': 'deuses',
                            'niveis': 100, 'xp_por_nivel': 800, 'catchup_dias': 14, 'catchup_pct': 50})
    modelo_deuses(tid)
    return tid


def jogadores_da_temporada(tid, limite=50):
    """Quem já jogou a temporada (pro admin liberar o Premium): maior XP primeiro."""
    linhas = (db.session.query(PassePessoa, Person).join(Person, Person.id == PassePessoa.person_id)
              .filter(PassePessoa.temporada_id == tid).order_by(PassePessoa.xp.desc()).limit(limite).all())
    return [{'id': p.id, 'nome': p.name, 'username': p.username or '', 'xp': pp.xp, 'premium': bool(pp.premium)} for pp, p in linhas]
