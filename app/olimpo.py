"""Olimpo: a assinatura do Pantheon (o "nitro"), Rodada 32. Sem socket; os eventos moram em olimpo_events.py.

O que dá hoje (só o que existe de verdade):
- a trilha PREMIUM do Passe de Batalha da temporada (liberada enquanto o Olimpo está ativo; o que já foi resgatado fica);
- a insígnia Ômega (`badge:olimpo`), uma letra Ômega de lava com raios correndo por dentro.
Fica pra depois (não prometer antes de existir): slots extras, upload maior, destaque de servidor, abrir caixinha de loja, desconto no Armazém.

Preço e gratuidade: POR ORA É GRÁTIS (OLIMPO_GRATIS padrão 1): qualquer pessoa ativa por 30 dias e renova quando quiser, sem cobrança nenhuma.
Quando for cobrar, OLIMPO_GRATIS=0: a ativação passa a gerar uma cobrança Pix pelo mesmo gateway dos pedidos (app/pagamentos.py, tipo
'olimpo', direto na conta do Pantheon: não há split) e o Olimpo só vale quando o pagamento é confirmado. OLIMPO_PRECO_CENT define o valor.
O nome é UMA constante (`NOME`): trocar é mexer aqui e no texto fixo do passe.js.
"""
import os
from datetime import timedelta

from .models import db, Person, Posse, br_now
from .cosmeticos import BADGE_OLIMPO

NOME = 'Olimpo'
DIAS = 30


class ErroOlimpo(Exception):
    pass


def gratis():
    return os.getenv('OLIMPO_GRATIS', '1') != '0'


def preco_cent():
    try:
        return max(100, min(50_000, int(os.getenv('OLIMPO_PRECO_CENT') or 1990)))
    except ValueError:
        return 1990


def ativo(pessoa):
    return bool(pessoa is not None and pessoa.olimpo_ate and pessoa.olimpo_ate > br_now())


def estado(pessoa):
    from . import pagamentos
    ate = pessoa.olimpo_ate
    return {'nome': NOME, 'ativo': ativo(pessoa), 'ate': ate.strftime('%d/%m/%Y') if ate and ativo(pessoa) else None,
            'dias': max(0, (ate - br_now()).days + 1) if ativo(pessoa) else 0, 'gratis': gratis(), 'preco_cent': preco_cent(), 'dias_por_periodo': DIAS,
            'pagamento_ligado': bool(pagamentos.provedor()), 'modo_teste': pagamentos.modo_teste()}


def conceder_dias(pessoa_id, dias=DIAS, origem='gratis'):
    """Soma `dias` ao Olimpo (a partir de hoje, ou do fim do período atual se ainda vale) e garante a insígnia. Comita."""
    from .utils import comitar_com_retry

    def preparar():
        p = Person.query.get(pessoa_id)
        base = p.olimpo_ate if p.olimpo_ate and p.olimpo_ate > br_now() else br_now()
        p.olimpo_ate = base + timedelta(days=int(dias))
        if not Posse.query.filter_by(person_id=p.id, item_id=BADGE_OLIMPO).first():
            db.session.add(Posse(person_id=p.id, item_id=BADGE_OLIMPO, origem='olimpo'))
        return p
    return comitar_com_retry(preparar)


def ativar_gratis(pessoa):
    if not gratis():
        raise ErroOlimpo('O Olimpo agora é pago.')
    return conceder_dias(pessoa.id, DIAS, 'gratis')


def cobrar(pessoa):
    """Quando NÃO é grátis: devolve a cobrança Pix (reaproveita a que está em aberto)."""
    from . import pagamentos
    if gratis():
        raise ErroOlimpo('O Olimpo está grátis por enquanto: é só ativar.')
    existente = pagamentos.cobranca_aberta('olimpo', pessoa.id)
    if existente:
        return existente
    try:
        return pagamentos.criar_cobranca('olimpo', pessoa.id, preco_cent(), pessoa, f'Assinatura {NOME} ({DIAS} dias)')
    except pagamentos.ErroPagamento as e:
        raise ErroOlimpo(str(e))


def aplicar_pagamento(c):
    """A cobrança do Olimpo foi PAGA (já confirmada pelo gateway): vale mais um período."""
    from .guardiao import notificar_fora_do_socket
    p = conceder_dias(c.ref_id, DIAS, 'pago')
    notificar_fora_do_socket(p.id, f'{NOME} ativado', f'Pagamento confirmado! O seu {NOME} vale até {p.olimpo_ate.strftime("%d/%m/%Y")}.')
    return p
