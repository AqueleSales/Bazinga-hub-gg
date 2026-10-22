"""Dados das Configurações do usuário que não são só "ler e gravar uma preferência" (Rodada 34). Sem socket.

- `historico_cobranca`: a aba Cobrança. Movimentos de DRC (MovimentoDrc) e Pix cobrados pelo app (Cobranca), SEMPRE só da própria pessoa.
  Nunca carrega o código do Pix (copia e cola) nem dado do gateway: quem precisa pagar abre o pedido; aqui é só histórico.
- `exportar_dados`: a "cópia dos meus dados" (LGPD art. 18). É um JSON com o que o Pantheon guarda DA CONTA da própria pessoa. Fica de fora, de
  propósito e dito na tela: o texto das mensagens (canais e DMs; entram só as contagens), chave Pix e dados de outras pessoas.
- `resumo_privacidade`: o que a aba Dados e privacidade mostra e que não está no navegador (aceite dos termos, retenção, contato).
"""
import json

from sqlalchemy import func

from .models import (db, Person, MovimentoDrc, Cobranca, BazarPedido, BazarLoja, Friendship, Conexao, Posse, GuardiaoCaso, Message,
                     DirectMessage, Silenciado, server_members, Server, br_now)
from . import loja as armazem
from . import olimpo, pagamentos, preferencias, termos

MAX_COBRANCAS = 60
ROTULO_STATUS = {'aberta': 'Aguardando pagamento', 'paga': 'Pago', 'expirada': 'Venceu', 'cancelada': 'Cancelado'}


def _dt(valor):
    return valor.strftime('%d/%m/%Y %H:%M') if valor else ''


def _linha_pix(c, titulo, papel):
    status = c.status or 'aberta'
    if status == 'aberta' and c.expira_em and c.expira_em < br_now():
        status = 'expirada'               # a vencida só vira "expirada" no banco quando alguém mexe no pedido; aqui só desenhamos como tal
    return {'id': c.id, 'tipo': c.tipo, 'papel': papel, 'titulo': titulo, 'valor_cent': int(c.valor_cent or 0), 'status': status,
            'status_rotulo': ROTULO_STATUS.get(status, status), 'quando': _dt(c.paga_em if status == 'paga' else c.criada_em),
            'teste': c.provedor == 'simulado'}


def historico_cobranca(pessoa):
    """Tudo da aba Cobrança. DRC: os últimos 100 movimentos e os totais. Pix: o que a pessoa PAGOU (pedidos e assinatura) e o que as compras
    nas lojas dela renderam (só o pedido, o valor e o estado: o repasse é do gateway)."""
    drc = armazem.extrato(pessoa, limite=100)

    pagos = []
    cobrancas = (Cobranca.query.filter_by(pessoa_id=pessoa.id).order_by(Cobranca.id.desc()).limit(MAX_COBRANCAS).all())
    pedidos_ids = [c.ref_id for c in cobrancas if c.tipo == 'pedido']
    pedidos = {p.id: p for p in BazarPedido.query.filter(BazarPedido.id.in_(pedidos_ids)).all()} if pedidos_ids else {}
    for c in cobrancas:
        if c.tipo == 'olimpo':
            titulo = f'Assinatura {olimpo.NOME}'
        else:
            p = pedidos.get(c.ref_id)
            titulo = (f'{p.produto_nome}' + (f' ×{p.quantidade}' if (p.quantidade or 1) > 1 else '')) if p else 'Pedido no Bazar'
        pagos.append(_linha_pix(c, titulo, 'pagou'))

    recebidos = []
    vendas = (db.session.query(Cobranca, BazarPedido).join(BazarPedido, BazarPedido.id == Cobranca.ref_id)
              .filter(Cobranca.tipo == 'pedido', BazarPedido.vendedor_id == pessoa.id)
              .order_by(Cobranca.id.desc()).limit(MAX_COBRANCAS).all())
    for c, p in vendas:
        recebidos.append(_linha_pix(c, f'{p.produto_nome}' + (f' ×{p.quantidade}' if (p.quantidade or 1) > 1 else ''), 'recebeu'))

    total_pago = sum(x['valor_cent'] for x in pagos if x['status'] == 'paga' and not x['teste'])
    total_recebido = sum(x['valor_cent'] for x in recebidos if x['status'] == 'paga' and not x['teste'])
    est = pagamentos.estado()
    return {
        'drc': drc, 'pix_pagos': pagos, 'pix_recebidos': recebidos,
        'total_pago_cent': total_pago, 'total_recebido_cent': total_recebido,
        'gateway': {'ligado': bool(est['provedor']), 'modo_teste': est['modo_teste'], 'provedor': est['provedor']},
        'moeda': {'sigla': 'DRC'},
        'brasa': olimpo.estado(pessoa),
    }


def resumo_privacidade(pessoa):
    from . import guardiao
    return {
        'termos_versao': pessoa.termos_versao or '', 'termos_aceitos_em': _dt(pessoa.termos_aceitos_em),
        'termos_vigente': termos.VERSAO, 'termos_em_dia': termos.aceitou(pessoa), 'contato': termos.contato(),
        'guardiao_ligado': bool(guardiao.ligado()), 'retencao_meses': 12,
    }


def exportar_dados(pessoa):
    """O JSON da "cópia dos meus dados". Só a conta de quem pede; nada de conteúdo de conversa (só contagens)."""
    pid = pessoa.id
    amizades = Friendship.query.filter(Friendship.status == 'accepted',
                                       (Friendship.requester_id == pid) | (Friendship.addressee_id == pid)).all()
    ids_amigos = [f.addressee_id if f.requester_id == pid else f.requester_id for f in amizades]
    nomes = {p.id: p for p in Person.query.filter(Person.id.in_(ids_amigos)).all()} if ids_amigos else {}
    bloqueados = Friendship.query.filter(Friendship.status == 'blocked', Friendship.requester_id == pid).count()
    servidores = (db.session.query(Server.id, Server.name, Server.owner_id, server_members.c.joined_at)
                  .join(server_members, server_members.c.server_id == Server.id).filter(server_members.c.person_id == pid).all())
    loja = BazarLoja.query.filter_by(owner_id=pid).first()
    pedidos = BazarPedido.query.filter((BazarPedido.comprador_id == pid) | (BazarPedido.vendedor_id == pid)).order_by(BazarPedido.id.desc()).limit(200).all()
    movimentos = MovimentoDrc.query.filter_by(person_id=pid).order_by(MovimentoDrc.id.desc()).limit(1000).all()
    cobrancas = Cobranca.query.filter_by(pessoa_id=pid).order_by(Cobranca.id.desc()).limit(200).all()
    casos = GuardiaoCaso.query.filter_by(person_id=pid).order_by(GuardiaoCaso.id.desc()).limit(200).all()
    n_canal = db.session.query(func.count(Message.id)).filter(Message.person_id == pid).scalar() or 0
    n_dm = db.session.query(func.count(DirectMessage.id)).filter(DirectMessage.sender_id == pid).scalar() or 0
    n_silenciados = Silenciado.query.filter_by(person_id=pid).count()

    return {
        'aviso': ('Esta é a cópia dos dados da SUA conta no Pantheon. Não inclui o texto das suas mensagens (canais e conversas privadas; só quantas '
                  'você enviou), a chave Pix da sua loja nem dados de outras pessoas. Pra pedir o resto, fale com o contato indicado nos Termos.'),
        'gerado_em': _dt(br_now()),
        'conta': {
            'id': pessoa.id, 'nome_de_exibicao': pessoa.name, 'usuario': pessoa.username, 'email': pessoa.email, 'pronomes': pessoa.pronomes,
            'bio': pessoa.bio, 'status': pessoa.status, 'status_personalizado': pessoa.custom_status, 'pensando': pessoa.pensando,
            'avatar': pessoa.avatar, 'faixa': pessoa.banner_url or pessoa.banner_color, 'criada_em': _dt(pessoa.created_at),
            'xp': pessoa.xp, 'saldo_drc': pessoa.bazinga_coins, 'modo_fantasma': bool(pessoa.ghost_mode),
            'localizacao_ativa': pessoa.localizacao_ativa is not False, 'radar_de_pessoas': pessoa.radar_estranhos is True,
            'tema': pessoa.tema, 'brasa_ate': _dt(pessoa.olimpo_ate),
            'termos': {'versao_aceita': pessoa.termos_versao, 'aceitos_em': _dt(pessoa.termos_aceitos_em)},
        },
        'preferencias': preferencias.da_pessoa(pessoa),
        'amigos': [{'usuario': nomes[i].username, 'nome': nomes[i].name} for i in ids_amigos if i in nomes],
        'pessoas_bloqueadas_qtd': bloqueados, 'pessoas_silenciadas_qtd': n_silenciados,
        'servidores': [{'id': s.id, 'nome': s.name, 'sou_dono': s.owner_id == pid, 'entrei_em': _dt(s.joined_at)} for s in servidores],
        'mensagens_enviadas': {'em_canais': int(n_canal), 'em_conversas_privadas': int(n_dm)},
        'conexoes': [{'tipo': c.tipo, 'link': c.url, 'titulo': c.titulo} for c in Conexao.query.filter_by(person_id=pid).order_by(Conexao.ordem).all()],
        'itens_do_inventario': [{'item': p.item_id, 'origem': p.origem, 'desde': _dt(p.created_at)} for p in Posse.query.filter_by(person_id=pid).all()],
        'movimentos_drc': [{'quando': _dt(m.created_at), 'valor': m.delta, 'saldo_depois': m.saldo_apos, 'motivo': m.motivo, 'ref': m.ref} for m in movimentos],
        'loja_do_bazar': ({'nome': loja.nome, 'descricao': loja.descricao, 'categoria': loja.categoria, 'porte': loja.porte} if loja else None),
        'pedidos_do_bazar': [{'id': p.id, 'produto': p.produto_nome, 'quantidade': p.quantidade, 'total_centavos': p.total_cent, 'estado': p.status,
                              'papel': 'comprador' if p.comprador_id == pid else 'vendedor', 'quando': _dt(p.created_at)} for p in pedidos],
        'cobrancas_pix': [{'quando': _dt(c.criada_em), 'tipo': c.tipo, 'valor_centavos': c.valor_cent, 'estado': c.status,
                           'teste': c.provedor == 'simulado'} for c in cobrancas],
        'analises_de_seguranca': [{'quando': _dt(c.criado_em), 'origem': c.origem, 'categoria': c.categoria, 'estado': c.status} for c in casos],
    }


def exportar_json(pessoa):
    return json.dumps(exportar_dados(pessoa), ensure_ascii=False, indent=2, default=str)
