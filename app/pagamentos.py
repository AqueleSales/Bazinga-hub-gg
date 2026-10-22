"""Pagamentos pelo app (Rodada 32): cobrança Pix por um GATEWAY. Sem socket; quem chama é o Bazar (pedido), o Olimpo (assinatura) e a rota do webhook.

Regra de ouro: o Pantheon NUNCA guarda dinheiro de ninguém (isso é atividade regulada). Quem cobra é o gateway; no pedido do Bazar o valor é
DIVIDIDO (split) direto para a carteira da loja (`BazarLoja.wallet_id`), e sem carteira o pedido não é cobrado pelo app (volta pro Pix direto).

Provedores (`provedor()`):
- 'asaas'    : cobrança Pix de verdade no Asaas (sandbox por padrão: ASAAS_AMBIENTE=producao muda). Precisa de ASAAS_API_KEY e, pro webhook,
               de ASAAS_WEBHOOK_TOKEN (o mesmo valor que se põe no "authToken" do webhook lá, apontando pra /webhooks/asaas). Pra criar a carteira
               de cada loja (split) a conta-mãe no Asaas precisa ser de pessoa JURÍDICA (CNPJ): é exigência deles.
- 'simulado' : NÃO cobra nada. Gera um código de mentira ("PANTHEON-TESTE-...") e o comprador aperta "Simular pagamento". Serve pra testar o fluxo
               inteiro sem dinheiro. Só liga sozinho fora do Render; em produção só com PAGAMENTOS=simulado (de propósito: senão qualquer um
               "pagaria" de graça). As telas mostram o aviso de MODO TESTE.
- None       : pagamento pelo app desligado (PAGAMENTOS=desligado, ou produção sem chave): tudo segue no Pix direto.

O webhook não é confiado: o token confere (comparação em tempo constante) E o status e o valor são reconfirmados na API antes de dar o pedido como pago.
"""
import hmac
import os
import uuid
from datetime import date, timedelta

import requests

from sqlalchemy import update

from .models import db, Cobranca, br_now

URLS_ASAAS = {'sandbox': 'https://api-sandbox.asaas.com/v3', 'producao': 'https://api.asaas.com/v3'}
VALIDADE_MIN = 30
VALOR_MIN_CENT = 100            # R$ 1,00
VALOR_MAX_CENT = 5_000_000      # R$ 50.000,00
STATUS_ASAAS_PAGO = ('RECEIVED', 'CONFIRMED', 'RECEIVED_IN_CASH')
STATUS_ASAAS_MORTO = {'OVERDUE': 'expirada', 'REFUNDED': 'cancelada', 'REFUND_REQUESTED': 'cancelada', 'DELETED': 'cancelada'}
TIMEOUT = (4, 15)


class ErroPagamento(Exception):
    """Erro de regra/gateway com texto pronto pra mostrar à pessoa (nunca carrega chave nem detalhe interno)."""


def ambiente():
    return 'producao' if (os.getenv('ASAAS_AMBIENTE') or '').lower() == 'producao' else 'sandbox'


def provedor():
    pedido = (os.getenv('PAGAMENTOS') or '').strip().lower()
    if pedido == 'desligado':
        return None
    if pedido == 'simulado':
        return 'simulado'
    if pedido == 'asaas':
        return 'asaas' if os.getenv('ASAAS_API_KEY') else None
    if os.getenv('ASAAS_API_KEY'):
        return 'asaas'
    return None if os.getenv('RENDER') else 'simulado'


def modo_teste():
    p = provedor()
    return p == 'simulado' or (p == 'asaas' and ambiente() == 'sandbox')


def taxa_pct():
    """Fatia do Pantheon em cada pedido pago pelo app (0 a 30%). Hoje 0: o Pantheon ainda não cobra nada."""
    try:
        return max(0.0, min(30.0, float(os.getenv('TAXA_PLATAFORMA_PCT') or 0)))
    except ValueError:
        return 0.0


def estado():
    p = provedor()
    return {'provedor': p, 'modo_teste': modo_teste(), 'ambiente': ambiente() if p == 'asaas' else None, 'taxa_pct': taxa_pct(),
            'webhook_configurado': bool(os.getenv('ASAAS_WEBHOOK_TOKEN'))}


# ---------------------------------------------------------------------------
# Asaas
# ---------------------------------------------------------------------------
def _asaas(metodo, caminho, corpo=None, params=None):
    chave = os.getenv('ASAAS_API_KEY')
    if not chave:
        raise ErroPagamento('O pagamento pelo app não está configurado.')
    try:
        r = requests.request(metodo, URLS_ASAAS[ambiente()] + caminho, json=corpo, params=params, timeout=TIMEOUT,
                             headers={'access_token': chave, 'Content-Type': 'application/json', 'User-Agent': 'Pantheon'})
    except requests.RequestException:
        raise ErroPagamento('O gateway de pagamento não respondeu. Tente de novo em instantes.')
    try:
        dados = r.json()
    except ValueError:
        dados = {}
    if r.status_code >= 400:
        erros = dados.get('errors') if isinstance(dados, dict) else None
        motivo = (erros[0].get('description') if erros and isinstance(erros[0], dict) else '') or f'HTTP {r.status_code}'
        print(f'[PAGAMENTOS] Asaas {metodo} {caminho} -> {r.status_code}: {motivo}')
        raise ErroPagamento(f'O gateway recusou a cobrança: {str(motivo)[:160]}')
    return dados


def _cliente_asaas(pessoa):
    ref = f'pnt{pessoa.id}'
    achados = _asaas('GET', '/customers', params={'externalReference': ref}).get('data') or []
    if achados:
        return achados[0]['id']
    novo = _asaas('POST', '/customers', {'name': (pessoa.name or 'Cliente')[:100], 'email': pessoa.email, 'externalReference': ref,
                                          'notificationDisabled': True})
    return novo['id']


def _data_asaas(texto):
    from datetime import datetime
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(texto)[:19], fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Cobrança
# ---------------------------------------------------------------------------
def criar_cobranca(tipo, ref_id, valor_cent, pagador, descricao, wallet_id=None):
    """Cria a cobrança Pix e devolve a linha `Cobranca` (já gravada). `wallet_id` = pra onde o valor vai (pedido); sem carteira, o gateway real recusa."""
    from .utils import comitar_com_retry
    prov = provedor()
    if not prov:
        raise ErroPagamento('O pagamento pelo app não está ligado neste servidor.')
    valor_cent = int(valor_cent)
    if not VALOR_MIN_CENT <= valor_cent <= VALOR_MAX_CENT:
        raise ErroPagamento('Esse valor não pode ser cobrado pelo app.')
    expira = br_now() + timedelta(minutes=VALIDADE_MIN)
    if prov == 'simulado':
        ext = 'sim_' + uuid.uuid4().hex[:20]
        payload = f'PANTHEON-TESTE-{ext}'      # de propósito NÃO é um Pix válido: nenhum banco paga isso
    else:
        if tipo == 'pedido' and not wallet_id:
            raise ErroPagamento('Essa loja ainda não tem carteira no gateway. Pague combinando o Pix direto com o vendedor.')
        cliente = _cliente_asaas(pagador)
        taxa = int(round(valor_cent * taxa_pct() / 100)) if tipo == 'pedido' else 0
        corpo = {'customer': cliente, 'billingType': 'PIX', 'value': round(valor_cent / 100, 2), 'dueDate': (date.today() + timedelta(days=1)).isoformat(),
                 'description': (descricao or 'Pantheon')[:200], 'externalReference': f'{tipo}:{ref_id}'}
        if tipo == 'pedido':
            corpo['split'] = [{'walletId': wallet_id, 'fixedValue': round((valor_cent - taxa) / 100, 2)}]
        pg = _asaas('POST', '/payments', corpo)
        ext = pg['id']
        qr = _asaas('GET', f'/payments/{ext}/pixQrCode')
        payload = (qr.get('payload') or '')[:600]
        expira = _data_asaas(qr.get('expirationDate')) or expira
        if not payload:
            raise ErroPagamento('O gateway não devolveu o código Pix. Tente de novo.')

    def preparar():
        c = Cobranca(provedor=prov, ext_id=ext, tipo=tipo, ref_id=int(ref_id), pessoa_id=pagador.id, valor_cent=valor_cent, status='aberta',
                     payload=payload, expira_em=expira)
        db.session.add(c)
        return c
    return comitar_com_retry(preparar)


def cobranca_aberta(tipo, ref_id):
    """A cobrança ainda válida desse pedido/assinatura, ou None (a vencida vira 'expirada' aqui mesmo)."""
    agora = br_now()
    for c in Cobranca.query.filter_by(tipo=tipo, ref_id=int(ref_id), status='aberta').order_by(Cobranca.id.desc()).all():
        if c.expira_em and c.expira_em < agora:
            c.status = 'expirada'
            db.session.commit()
            continue
        return c
    return None


def cobranca_vigente(tipo, ref_id):
    """Só LÊ: a cobrança aberta e ainda válida (pro JSON do pedido; não escreve no banco)."""
    agora = br_now()
    for c in Cobranca.query.filter_by(tipo=tipo, ref_id=int(ref_id), status='aberta').order_by(Cobranca.id.desc()).all():
        if not c.expira_em or c.expira_em >= agora:
            return c
    return None


def cobranca_json(c):
    return {'ext_id': c.ext_id, 'valor_cent': c.valor_cent, 'copia_cola': c.payload or '', 'expira_em': c.expira_em.strftime('%H:%M') if c.expira_em else '',
            'simulada': c.provedor == 'simulado'}


def cancelar_cobrancas(tipo, ref_id):
    """O pedido foi cancelado/recusado: as cobranças em aberto deixam de valer (no gateway real, tenta apagar; falha lá não impede)."""
    for c in Cobranca.query.filter_by(tipo=tipo, ref_id=int(ref_id), status='aberta').all():
        c.status = 'cancelada'
        if c.provedor == 'asaas':
            try:
                _asaas('DELETE', f'/payments/{c.ext_id}')
            except ErroPagamento:
                pass
    db.session.commit()


def consultar(c):
    """Pergunta ao gateway como está a cobrança. Devolve {'status': aberta|paga|expirada|cancelada, 'valor_cent': int}."""
    if c.provedor == 'simulado':
        return {'status': c.status, 'valor_cent': c.valor_cent}
    pg = _asaas('GET', f'/payments/{c.ext_id}')
    st = pg.get('status')
    status = 'paga' if st in STATUS_ASAAS_PAGO else STATUS_ASAAS_MORTO.get(st, 'aberta')
    return {'status': status, 'valor_cent': int(round(float(pg.get('value') or 0) * 100))}


def marcar_paga(ext_id, valor_cent=None):
    """Marca como paga SE ainda estava aberta (UPDATE condicional: webhook repetido e clique duplo nunca aplicam duas vezes).
    Devolve (cobranca, nova). `nova` só é True na vez que de fato virou paga: quem recebe True aplica o efeito (liberar pedido/Olimpo)."""
    c = Cobranca.query.filter_by(ext_id=str(ext_id)).first()
    if not c:
        return None, False
    if valor_cent is not None and int(valor_cent) != c.valor_cent:
        print(f'[PAGAMENTOS] valor não bate na cobrança {c.id} (esperado {c.valor_cent}, veio {valor_cent}): ignorado')
        return c, False
    r = db.session.execute(update(Cobranca).where(Cobranca.id == c.id, Cobranca.status == 'aberta').values(status='paga', paga_em=br_now()))
    db.session.commit()
    db.session.refresh(c)
    return c, r.rowcount == 1


def simular_pagamento(pessoa_id, ext_id):
    """Só no provedor simulado, só quem foi cobrado. Devolve (cobranca, nova)."""
    c = Cobranca.query.filter_by(ext_id=str(ext_id)).first()
    if provedor() != 'simulado' or not c or c.provedor != 'simulado' or c.pessoa_id != pessoa_id:
        raise ErroPagamento('Essa cobrança não pode ser simulada.')
    if c.status != 'aberta':
        raise ErroPagamento('Essa cobrança não está mais aberta.')
    if c.expira_em and c.expira_em < br_now():
        raise ErroPagamento('Essa cobrança expirou. Gere outra.')
    return marcar_paga(c.ext_id, c.valor_cent)


def processar_webhook_asaas(token_recebido, dados):
    """Devolve (http_status, texto, cobranca_paga_agora_ou_None). 401 se o token não bate; o resto devolve 200 pra o Asaas não repetir à toa."""
    esperado = os.getenv('ASAAS_WEBHOOK_TOKEN') or ''
    if not esperado or not hmac.compare_digest(esperado.encode('utf-8'), (token_recebido or '').encode('utf-8')):
        return 401, 'token inválido', None
    if provedor() != 'asaas' or not isinstance(dados, dict):
        return 200, 'ignorado', None
    evento = dados.get('event')
    pg = dados.get('payment') if isinstance(dados.get('payment'), dict) else {}
    ext = str(pg.get('id') or '')
    c = Cobranca.query.filter_by(ext_id=ext).first() if ext else None
    if not c:
        return 200, 'cobrança desconhecida', None
    if evento in ('PAYMENT_RECEIVED', 'PAYMENT_CONFIRMED'):
        try:
            real = consultar(c)         # não confia só no aviso: pergunta ao gateway
        except ErroPagamento:
            return 500, 'não consegui confirmar no gateway', None      # 5xx = o Asaas tenta de novo
        if real['status'] != 'paga' or real['valor_cent'] != c.valor_cent:
            return 200, 'não confirmado', None
        c, nova = marcar_paga(ext, real['valor_cent'])
        return 200, 'ok', c if nova else None
    if evento in ('PAYMENT_OVERDUE', 'PAYMENT_DELETED') and c.status == 'aberta':
        c.status = 'expirada' if evento == 'PAYMENT_OVERDUE' else 'cancelada'
        db.session.commit()
    return 200, 'ok', None
