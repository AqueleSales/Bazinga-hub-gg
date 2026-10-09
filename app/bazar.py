"""Bazar da comunidade, modelo A (classificados): lojas e produtos de pessoas, pedido combinado no app,
pagamento por Pix DIRETO entre comprador e vendedor.

Só lógica e dados (sem socket; os handlers moram em bazar_events.py). O que este modelo é e NÃO é:
  * O Panteão NÃO toca no dinheiro, NÃO guarda saldo, NÃO retém pagamento (isso seria o "modelo B": gateway com
    split + retenção até a entrega, que exige CNPJ/KYC/termos). Aqui o app só monta o "Pix copia e cola" com a chave
    que o vendedor cadastrou e acompanha o estado do pedido. Sem proteção de escrow: o aviso na tela diz isso.
  * Regra 4: o servidor decide tudo (quem vê a chave Pix, quem pode aceitar/cancelar, estoque, preço). O cliente só
    manda "o que quer fazer"; preço e nome do pedido são COPIADOS do produto na hora de pedir.
  * Texto público (nome, descrição, propaganda, combo, conversa do pedido) não aceita link: golpe costuma vir por link.
    O link de entrega de produto digital vai no campo privado `entrega`, que só o comprador de um pedido já confirmado vê.
"""
import hashlib
import json
import re
import unicodedata

from sqlalchemy import func, update, or_, and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from datetime import datetime, timedelta

from .models import (db, br_now, Person, BazarLoja, BazarProduto, BazarPedido, BazarMensagem, BazarAvaliacao,
                     BazarFavorito, BazarAnuncio, BazarDisputa, BazarBanimento,
                     Denuncia, ConfigApp, Friendship, GeoNote, MapServer)
from .utils import (comitar_com_retry, url_de_imagem_ok, texto_tem_link, localizacao_ligada, MSG_LOCALIZACAO_DESLIGADA, distancia_m)


class ErroBazar(Exception):
    """Erro que a pessoa pode ler (vai pro toast): campo inválido, pedido que já mudou, limite..."""


# ==========================================
# CATÁLOGOS (ids validados no servidor; o cliente desenha a partir do que recebe daqui)
# ==========================================
CATEGORIAS = [('arte', 'Arte e ilustração'), ('digital', 'Digital e jogos'), ('comida', 'Comida'), ('moda', 'Moda e acessórios'),
              ('casa', 'Casa e artesanato'), ('servicos', 'Serviços'), ('outros', 'Outros')]
IDS_CATEGORIA = tuple(c for c, _ in CATEGORIAS)

# cor da loja (parede/acento) e toldo (as listras): só estes ids viram estilo no navegador de todo mundo
CORES = {'ambar': '#d9822b', 'vinho': '#a8323e', 'floresta': '#3f7d4e', 'oceano': '#2f6f9f', 'lavanda': '#7d6bb8',
         'tijolo': '#b5532f', 'petroleo': '#2f6670', 'mostarda': '#c9a227', 'rosa': '#c4577f', 'grafite': '#5a606b'}
TOLDOS = {'vermelho': ('#c0392b', '#fff4e6'), 'verde': ('#2f7d4a', '#f1f7ee'), 'azul': ('#2f5aa8', '#fdf3dc'),
          'amarelo': ('#d9a521', '#fff8e1'), 'roxo': ('#6f4fb0', '#f4effb'), 'laranja': ('#d9702b', '#fff1e3'), 'sem': None}
PORTES_LIVRES = ('micro', 'media')            # 'grande' (parceira) só um admin define (bazar_admin.py)
TIPOS_PRODUTO = ('fisico', 'digital', 'servico')

# limites (os mesmos números vão nos maxlength do HTML)
LIM_NOME_LOJA, LIM_DESC_LOJA, LIM_REGIAO = 40, 300, 40
LIM_ANUNCIO_TITULO, LIM_ANUNCIO_TEXTO = 60, 160
LIM_NOME_PROD, LIM_DESC_PROD, LIM_COMBO_ITEM, LIM_ENTREGA = 80, 600, 60, 500
LIM_IMAGENS, LIM_COMBO, MAX_PRODUTOS_ATIVOS = 5, 8, 40
PRECO_MIN_CENT, PRECO_MAX_CENT, ESTOQUE_MAX, QTD_MAX_PEDIDO = 100, 5_000_000, 9999, 20
LIM_MSG, MAX_MSGS_PEDIDO, LIM_NOTA_PEDIDO, LIM_AVALIACAO = 300, 80, 200, 200
MAX_PEDIDOS_ABERTOS_COMPRADOR = 10
ABERTOS = ('aguardando', 'aceito', 'pago', 'confirmado')
PIX_VISIVEL = ('aceito', 'pago', 'confirmado', 'concluido')
DENUNCIAS_PARA_OCULTAR = 3          # mesmo número do mapa (utils.DENUNCIAS_PARA_OCULTAR)

# ---- Rodada 18 ----
# Reputação: conta nova não abre loja de cara e loja nova não vende caro de cara (golpe de conta descartável).
IDADE_MIN_LOJA_DIAS = 3
VENDAS_PARA_LIBERAR, LIMITE_LOJA_NOVA_CENT = 3, 30_000       # até concluir 3 vendas, produto de no máximo R$ 300,00
VENDAS_CONFIAVEL, AVALIACOES_CONFIAVEL, NOTA_CONFIAVEL = 5, 3, 4.5
# Frete/entrega
FRETE_MAX_CENT, LIM_ENDERECO, MIN_ENDERECO = 50_000, 300, 10
MODOS_ENTREGA = ('envio', 'retirada', 'digital', 'combinar')
ROTULO_ENTREGA = {'envio': 'Envio', 'retirada': 'Retirada em mãos', 'digital': 'Entrega digital', 'combinar': 'A combinar na conversa'}
# Disputa: quem pode abrir com qual motivo, e até quando depois de concluído
MOTIVOS_DISPUTA = {'nao_recebi': ('Paguei e não recebi', 'comprador'), 'diferente': ('Veio diferente do anunciado', 'comprador'),
                   'nao_paguei': ('Disse que pagou e o Pix não caiu', 'vendedor'), 'sumiu': ('A outra pessoa sumiu', None), 'outro': ('Outro motivo', None)}
DISPUTA_STATUS_ABRE = ('aceito', 'pago', 'confirmado', 'concluido')
DISPUTA_DIAS_APOS_CONCLUIR = 14
LIM_DISPUTA_DETALHE, MIN_DISPUTA_DETALHE, LIM_NOTA_ADMIN, LIM_BAN_MOTIVO = 300, 10, 300, 200
# Feed
ORDENS = (('mix', 'Misturado (embaralhado)'), ('vendidos', 'Mais vendidos'), ('nota', 'Melhor avaliadas'), ('novas', 'Mais novas'),
          ('preco_menor', 'Menor preço'), ('preco_maior', 'Maior preço'), ('perto', 'Perto de mim'))
IDS_ORDEM = tuple(o for o, _ in ORDENS)
RAIO_PERTO_KM = 30
MAX_FAVORITOS = 200
LIM_ANUNCIO_CTA = 24
DESTINOS_ANUNCIO = ('loja', 'link', 'painel', 'aviso', 'armazem', 'nenhum')

# (status atual, quem age, ação) -> novo status. Qualquer outra combinação é recusada (o estado já mudou).
TRANSICOES = {
    ('aguardando', 'vendedor', 'aceitar'): 'aceito',
    ('aguardando', 'vendedor', 'recusar'): 'recusado',
    ('aguardando', 'comprador', 'cancelar'): 'cancelado',
    ('aceito', 'comprador', 'paguei'): 'pago',
    ('aceito', 'comprador', 'cancelar'): 'cancelado',
    ('aceito', 'vendedor', 'cancelar'): 'cancelado',
    ('pago', 'vendedor', 'confirmar'): 'confirmado',
    ('pago', 'vendedor', 'nao_recebi'): 'aceito',
    ('confirmado', 'comprador', 'recebi'): 'concluido',
}
ROTULO_STATUS = {'aguardando': 'Aguardando o vendedor', 'aceito': 'Aceito: pague por Pix', 'pago': 'Pagamento informado',
                 'confirmado': 'Pagamento confirmado', 'concluido': 'Concluído', 'recusado': 'Recusado', 'cancelado': 'Cancelado'}


# ==========================================
# VALIDAÇÃO
# ==========================================
def _texto(valor, maximo, nome, obrigatorio=False, links=False):
    t = re.sub(r'[ \t]+', ' ', str(valor or '').replace('\r', '')).strip()
    t = re.sub(r'\n{3,}', '\n\n', t)
    if obrigatorio and not t:
        raise ErroBazar(f'Preencha {nome}.')
    if len(t) > maximo:
        raise ErroBazar(f'{nome[:1].upper()}{nome[1:]} passa de {maximo} caracteres.')
    if t and not links and texto_tem_link(t):
        raise ErroBazar(f'{nome[:1].upper()}{nome[1:]}: links não são permitidos (golpe costuma vir por link). Escreva só o texto.')
    return t or None


def _inteiro(valor, minimo, maximo, nome, opcional=False):
    if valor in (None, ''):
        if opcional:
            return None
        raise ErroBazar(f'Preencha {nome}.')
    if isinstance(valor, bool):
        raise ErroBazar(f'{nome[:1].upper()}{nome[1:]} inválido.')
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ErroBazar(f'{nome[:1].upper()}{nome[1:]} inválido.')
    if n < minimo or n > maximo:
        raise ErroBazar(f'{nome[:1].upper()}{nome[1:]} precisa ficar entre {minimo} e {maximo}.')
    return n


_RE_URL_SEGURA = re.compile(r'''^[^\s'"()<>\\]+$''')    # sem aspas, parênteses, espaço, < > ou barra invertida: a URL pode ir num style="url(...)"


def _url_imagem(valor, nome):
    v = str(valor or '').strip()
    if not v:
        return None
    if not url_de_imagem_ok(v) or not _RE_URL_SEGURA.match(v):
        raise ErroBazar(f'{nome[:1].upper()}{nome[1:]}: use uma imagem enviada pelo próprio app.')
    return v


def _url_video(valor):
    v = str(valor or '').strip()
    if not v:
        return None
    if len(v) > 255 or not v.startswith('https://res.cloudinary.com/') or not _RE_URL_SEGURA.match(v):
        raise ErroBazar('Vídeo: use um vídeo enviado pelo próprio app.')
    return v


def _lista_json(texto, maximo=20):
    if not texto:
        return []
    try:
        v = json.loads(texto)
    except (TypeError, ValueError):
        return []
    return [str(x) for x in v][:maximo] if isinstance(v, list) else []


def _exigir_localizacao(usuario):
    # decisão do dono: comprar e vender no Bazar exigem a localização ligada (cliente adulterado ainda passa: é trava leve)
    if not localizacao_ligada(usuario):
        raise ErroBazar(MSG_LOCALIZACAO_DESLIGADA)


# ---- banimento: quem está suspenso não vende, não compra e a loja some do feed ----
def _banimento_ativo(pessoa_id):
    b = BazarBanimento.query.filter_by(person_id=pessoa_id).first()
    if b and (b.ate is None or b.ate > br_now()):
        return b
    return None


def _subq_banidos():
    """ids de quem está banido AGORA (usado pra esconder as lojas deles em qualquer lista)."""
    return select(BazarBanimento.person_id).where(or_(BazarBanimento.ate.is_(None), BazarBanimento.ate > br_now()))


def _exigir_nao_banido(usuario):
    b = _banimento_ativo(usuario.id)
    if b:
        quando = f' até {b.ate.strftime("%d/%m/%Y")}' if b.ate else ''
        raise ErroBazar(f'Sua conta está suspensa do Bazar{quando}.' + (f' Motivo: {b.motivo.rstrip(".! ")}.' if b.motivo else ''))


def banimento_json(pessoa_id):
    b = _banimento_ativo(pessoa_id)
    return {'motivo': b.motivo or '', 'ate': b.ate.strftime('%d/%m/%Y') if b.ate else None} if b else None


# ==========================================
# PIX (copia e cola estático, sem gateway: o dinheiro vai direto pra conta do vendedor)
# ==========================================
def cpf_valido(d):
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(d[n]):
            return False
    return True


_RE_EMAIL = re.compile(r'^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$')
_RE_EVP = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def normalizar_chave_pix(valor):
    """Devolve a chave no formato que o Pix exige (telefone com +55, CPF/CNPJ só números, e-mail minúsculo, chave aleatória)
    ou levanta ErroBazar. 11 números que são um CPF válido = CPF; senão, se parece celular = telefone."""
    v = str(valor or '').strip()
    if not v:
        return None
    baixo = v.lower()
    if _RE_EMAIL.match(baixo) and len(baixo) <= 77:
        return baixo
    if _RE_EVP.match(baixo):
        return baixo
    if re.search(r'[A-Za-z]', v):
        raise ErroBazar('Chave Pix inválida. Use CPF, CNPJ, telefone, e-mail ou chave aleatória.')
    d = re.sub(r'\D', '', v)
    if v.startswith('+'):
        if len(d) in (12, 13) and d.startswith('55'):
            return '+' + d
        raise ErroBazar('Telefone inválido. Use o formato +55 DDD número.')
    if len(d) == 14:
        return d
    if len(d) == 11:
        if cpf_valido(d):
            return d
        if d[2] == '9':
            return '+55' + d
    if len(d) == 10:
        return '+55' + d
    if len(d) in (12, 13) and d.startswith('55'):
        return '+' + d
    raise ErroBazar('Chave Pix inválida. Confira o CPF/telefone/e-mail que você digitou.')


def _ascii_pix(texto, maximo, padrao):
    t = unicodedata.normalize('NFKD', str(texto or ''))
    t = ''.join(c for c in t if not unicodedata.combining(c)).upper()
    t = re.sub(r'[^A-Z0-9 ]', '', t).strip()[:maximo].strip()
    return t or padrao


def _tlv(id_, valor):
    return f'{id_}{len(valor):02d}{valor}'


def crc16_pix(texto):
    """CRC16/CCITT-FALSE (poly 0x1021, início 0xFFFF): o que o BR Code do Pix exige no fim."""
    crc = 0xFFFF
    for b in texto.encode('ascii'):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def pix_copia_cola(chave, nome, cidade, valor_cent, txid):
    """Payload do "Pix copia e cola" (estático, com valor). Cole no app do banco ou leia o QR."""
    conta = _tlv('00', 'br.gov.bcb.pix') + _tlv('01', chave)
    corpo = (_tlv('00', '01') + _tlv('01', '11') + _tlv('26', conta) + _tlv('52', '0000') + _tlv('53', '986')
             + _tlv('54', f'{valor_cent / 100:.2f}') + _tlv('58', 'BR')
             + _tlv('59', _ascii_pix(nome, 25, 'VENDEDOR')) + _tlv('60', _ascii_pix(cidade, 15, 'BRASIL'))
             + _tlv('62', _tlv('05', re.sub(r'[^A-Za-z0-9]', '', txid)[:25] or '***')) + '6304')
    return corpo + f'{crc16_pix(corpo):04X}'


def chave_mascarada(chave):
    c = chave or ''
    if '@' in c:
        local, _, dominio = c.partition('@')
        return f'{local[:2]}***@{dominio}'
    return f'{c[:3]}***{c[-2:]}' if len(c) > 6 else '***'


# ==========================================
# SERIALIZAÇÃO
# ==========================================
def _hora(ts):
    return ts.strftime('%d/%m %H:%M') if ts else ''


def nota_media(loja):
    return round(loja.nota_soma / loja.nota_qtd, 1) if loja.nota_qtd else None


def modos_de_entrega(p):
    """Como o comprador pode receber ESTE produto (o servidor decide; o cliente só escolhe entre estes)."""
    if p.tipo == 'fisico':
        modos = (['envio'] if p.frete_cent is not None else []) + (['retirada'] if p.aceita_retirada else [])
        return modos or ['combinar']
    return ['digital'] if p.tipo == 'digital' else ['combinar']


def produto_json(p, dono=False):
    j = {'id': p.id, 'loja_id': p.loja_id, 'nome': p.nome, 'descricao': p.descricao or '', 'preco_cent': p.preco_cent,
         'tipo': p.tipo, 'imagens': _lista_json(p.imagens, LIM_IMAGENS), 'video_url': p.video_url, 'estoque': p.estoque,
         'combo_itens': _lista_json(p.combo_itens, LIM_COMBO), 'preco_avulso_cent': p.preco_avulso_cent,
         'ativo': p.ativo is not False, 'vendidos': p.vendidos or 0,
         'frete_cent': p.frete_cent, 'aceita_retirada': bool(p.aceita_retirada), 'entregas': modos_de_entrega(p)}
    if dono:
        j['entrega'] = p.entrega or ''
        j['oculta'] = bool(p.oculta)
    return j


def reputacao(l):
    """'verificada' (um admin deu o selo) · 'confiavel' (várias vendas e nota alta) · 'nova' (ainda pouco histórico: limite de valor) · 'comum'."""
    if l.verificada:
        return 'verificada'
    vendas = l.vendas or 0
    if vendas >= VENDAS_CONFIAVEL and (l.nota_qtd or 0) >= AVALIACOES_CONFIAVEL and l.nota_soma / l.nota_qtd >= NOTA_CONFIAVEL:
        return 'confiavel'
    return 'nova' if vendas < VENDAS_PARA_LIBERAR else 'comum'


def loja_json(l, produtos=None, dono=False, dist_km=None):
    j = {'id': l.id, 'nome': l.nome, 'descricao': l.descricao or '', 'categoria': l.categoria, 'porte': l.porte,
         'regiao': l.regiao or '', 'cor': l.cor, 'toldo': l.toldo, 'logo_url': l.logo_url, 'banner_url': l.banner_url,
         'anuncio_titulo': l.anuncio_titulo or '', 'anuncio_texto': l.anuncio_texto or '', 'aberta': l.aberta is not False,
         'nota': nota_media(l), 'nota_qtd': l.nota_qtd or 0, 'vendas': l.vendas or 0, 'dono_id': l.owner_id,
         'dono_nome': l.owner.name if l.owner else '', 'pix_configurado': bool(l.pix_chave),
         'verificada': bool(l.verificada), 'reputacao': reputacao(l), 'no_mapa': l.lat is not None}
    if dist_km is not None:
        j['distancia_km'] = dist_km
    if dono:
        j.update({'pix_chave': l.pix_chave or '', 'pix_nome': l.pix_nome or '', 'pix_cidade': l.pix_cidade or '', 'oculta': bool(l.oculta),
                  'limite_novo_cent': LIMITE_LOJA_NOVA_CENT if (l.vendas or 0) < VENDAS_PARA_LIBERAR else None})
    if produtos is not None:
        j['produtos'] = produtos
    return j


def catalogos_json():
    return {'categorias': [{'id': i, 'nome': n} for i, n in CATEGORIAS],
            'cores': CORES, 'toldos': {k: list(v) if v else None for k, v in TOLDOS.items()},
            'limites': {'nome_loja': LIM_NOME_LOJA, 'desc_loja': LIM_DESC_LOJA, 'regiao': LIM_REGIAO, 'anuncio_titulo': LIM_ANUNCIO_TITULO,
                        'anuncio_texto': LIM_ANUNCIO_TEXTO, 'nome_prod': LIM_NOME_PROD, 'desc_prod': LIM_DESC_PROD,
                        'combo_item': LIM_COMBO_ITEM, 'entrega': LIM_ENTREGA, 'imagens': LIM_IMAGENS, 'combo': LIM_COMBO,
                        'preco_min_cent': PRECO_MIN_CENT, 'preco_max_cent': PRECO_MAX_CENT, 'msg': LIM_MSG,
                        'nota_pedido': LIM_NOTA_PEDIDO, 'avaliacao': LIM_AVALIACAO, 'qtd_max': QTD_MAX_PEDIDO,
                        'frete_max_cent': FRETE_MAX_CENT, 'endereco': LIM_ENDERECO, 'endereco_min': MIN_ENDERECO,
                        'disputa_detalhe': LIM_DISPUTA_DETALHE, 'disputa_detalhe_min': MIN_DISPUTA_DETALHE, 'nota_admin': LIM_NOTA_ADMIN,
                        'ban_motivo': LIM_BAN_MOTIVO, 'anuncio_cta': LIM_ANUNCIO_CTA, 'limite_loja_nova_cent': LIMITE_LOJA_NOVA_CENT,
                        'vendas_para_liberar': VENDAS_PARA_LIBERAR, 'idade_min_loja_dias': IDADE_MIN_LOJA_DIAS, 'raio_perto_km': RAIO_PERTO_KM},
            'ordens': [{'id': i, 'nome': n} for i, n in ORDENS],
            'motivos_disputa': [{'id': k, 'nome': v[0], 'papel': v[1]} for k, v in MOTIVOS_DISPUTA.items()],
            'entregas': ROTULO_ENTREGA}


def _disputa_json(d, eu_id, admin=False):
    nome, _ = MOTIVOS_DISPUTA.get(d.motivo, (d.motivo, None))
    j = {'id': d.id, 'status': d.status, 'motivo': d.motivo, 'motivo_nome': nome, 'detalhe': d.detalhe or '', 'minha': d.aberta_por_id == eu_id,
         'resolucao': d.resolucao, 'nota_admin': d.nota_admin or '', 'aberta_em': _hora(d.created_at), 'resolvida_em': _hora(d.resolvido_em)}
    if admin:
        j['aberta_por_id'] = d.aberta_por_id
    return j


def _ultimas_disputas(pedido_ids):
    """pedido_id -> a disputa mais recente dele (uma consulta só pra uma lista inteira de pedidos)."""
    if not pedido_ids:
        return {}
    por_pedido = {}
    for d in BazarDisputa.query.filter(BazarDisputa.pedido_id.in_(pedido_ids)).order_by(BazarDisputa.id).all():
        por_pedido[d.pedido_id] = d
    return por_pedido


_SEM_MAPA = object()


def pedido_json(p, eu_id, com_mensagens=False, disputas=_SEM_MAPA):
    """O pedido do ponto de vista de UMA das duas pessoas. A chave Pix (copia e cola) só vai pro comprador e só depois de aceito;
    o link/instrução de entrega só vai pro comprador depois de o vendedor confirmar o Pix. O endereço só as duas pontas veem (e some no fim)."""
    papel = 'vendedor' if p.vendedor_id == eu_id else 'comprador'
    outro = p.comprador if papel == 'vendedor' else p.vendedor
    produto, loja = p.produto, p.loja
    imagens = _lista_json(produto.imagens, 1) if produto else []
    j = {'id': p.id, 'papel': papel, 'status': p.status, 'rotulo': ROTULO_STATUS.get(p.status, p.status),
         'produto_id': p.produto_id, 'produto_nome': p.produto_nome, 'imagem': imagens[0] if imagens else None,
         'loja_id': p.loja_id, 'loja_nome': loja.nome if loja else '', 'quantidade': p.quantidade or 1,
         'preco_unit_cent': p.preco_unit_cent, 'total_cent': p.total_cent, 'nota': p.nota or '',
         'criado_em': _hora(p.created_at), 'atualizado_em': _hora(p.atualizado_em),
         'contraparte': {'id': outro.id, 'nome': outro.name, 'avatar': outro.avatar} if outro else None,
         'tipo': produto.tipo if produto else None,
         'entrega_modo': p.entrega_modo or 'combinar', 'entrega_rotulo': ROTULO_ENTREGA.get(p.entrega_modo or 'combinar', ''),
         'frete_cent': p.frete_cent or 0, 'subtotal_cent': (p.preco_unit_cent or 0) * (p.quantidade or 1)}
    if p.endereco:
        j['endereco'] = p.endereco
    d = disputas.get(p.id) if disputas is not _SEM_MAPA else _ultimas_disputas([p.id]).get(p.id)
    j['disputa'] = _disputa_json(d, eu_id) if d else None
    em_aberto = bool(d and d.status == 'aberta')
    j['em_disputa'] = em_aberto
    j['pode_disputar'] = _pode_disputar(p, papel) and not em_aberto
    if papel == 'comprador' and p.status in PIX_VISIVEL and loja and loja.pix_chave:
        j['pix'] = {'nome': loja.pix_nome or '', 'chave_mascarada': chave_mascarada(loja.pix_chave), 'valor_cent': p.total_cent,
                    'copia_cola': pix_copia_cola(loja.pix_chave, loja.pix_nome or (loja.owner.name if loja.owner else ''),
                                                 loja.pix_cidade or '', p.total_cent, f'PNT{p.id}')}
    if produto and produto.entrega and (papel == 'vendedor' or p.status in ('confirmado', 'concluido')):
        j['entrega'] = produto.entrega
    jaavaliou = bool(BazarAvaliacao.query.filter_by(pedido_id=p.id).first()) if p.status == 'concluido' else False
    j['avaliado'] = jaavaliou
    j['pode_avaliar'] = papel == 'comprador' and p.status == 'concluido' and not jaavaliou
    if com_mensagens:
        msgs = BazarMensagem.query.filter_by(pedido_id=p.id).order_by(BazarMensagem.id.desc()).limit(40).all()
        j['mensagens'] = [_mensagem_json(m) for m in reversed(msgs)]
    return j


def _mensagem_json(m):
    return {'id': m.id, 'autor_id': m.autor_id, 'texto': m.texto or '', 'imagem': m.imagem_url, 'hora': _hora(m.created_at)}


def _pode_disputar(p, papel):
    """Disputa vale pra pedido já aceito (tem Pix em jogo); depois de concluído, só por alguns dias."""
    if p.status not in DISPUTA_STATUS_ABRE:
        return False
    if p.status == 'concluido' and (not p.atualizado_em or br_now() - p.atualizado_em > timedelta(days=DISPUTA_DIAS_APOS_CONCLUIR)):
        return False
    return True


# ==========================================
# VITRINE
# ==========================================
def _produtos_visiveis_de(loja_ids):
    if not loja_ids:
        return {}
    linhas = (BazarProduto.query.filter(BazarProduto.loja_id.in_(loja_ids), BazarProduto.ativo.isnot(False), BazarProduto.oculta.isnot(True))
              .order_by(BazarProduto.id.desc()).all())
    por_loja = {}
    for p in linhas:
        por_loja.setdefault(p.loja_id, []).append(p)
    return por_loja


PAGINA_FEED = 14                 # itens do feed por página (rolagem infinita pede a próxima)
MIN_AVALIACOES_DESTAQUE = 3      # "bem avaliadas" só entra com 3 avaliações ou mais (uma nota 5 sozinha não vira destaque)
MAX_LOJAS_FEED, MAX_ITENS_MICRO = 300, 600


def _sorteio(seed, chave):
    """Número estável por (seed, chave): a ordem do feed é um embaralhamento que NÃO muda enquanto a pessoa usa a mesma seed
    (então atualizar a tela não reorganiza tudo), e muda quando ela pede outro (ou ao abrir de novo)."""
    return int(hashlib.md5(f'{seed}:{chave}'.encode()).hexdigest()[:12], 16)


def _seed_limpa(seed):
    return re.sub(r'[^a-z0-9]', '', str(seed or '').lower())[:16] or 'x'


def _produto_do_feed(p, l, dist=None):
    j = produto_json(p)
    j.update(loja_nome=l.nome, loja_cor=l.cor, loja_nota=nota_media(l), dono_nome=l.owner.name if l.owner else '', loja_reputacao=reputacao(l))
    if dist is not None:
        j['distancia_km'] = dist
    return j


def _k_loja(ordem, l, prods, dist):
    """Chave de ordenação (menor primeiro) da LOJA no feed, conforme a ordem escolhida. 'mix' não ordena por nada (só pelo sorteio)."""
    if ordem == 'vendidos':
        return (-(l.vendas or 0),)
    if ordem == 'nota':
        qtd = l.nota_qtd or 0
        return (-(l.nota_soma / qtd if qtd else 0), -qtd)
    if ordem == 'novas':
        return (-l.id,)
    if ordem == 'preco_menor':
        return (min(p.preco_cent for p in prods),)
    if ordem == 'preco_maior':
        return (-max(p.preco_cent for p in prods),)
    if ordem == 'perto':
        return (dist,)
    return ()


def _k_prod(ordem, l, p, dist):
    """O mesmo, pra um ITEM de barraca pequena (os quadrados de 4)."""
    if ordem == 'vendidos':
        return (-(p.vendidos or 0),)
    if ordem == 'novas':
        return (-p.id,)
    if ordem == 'preco_menor':
        return (p.preco_cent,)
    if ordem == 'preco_maior':
        return (-p.preco_cent,)
    return _k_loja(ordem, l, [p], dist)


def feed(busca=None, categoria=None, tipo=None, seed='', pagina=0, ordem='mix', so_favoritas=False, pessoa_id=None, pos=None):
    """O FEED do Bazar: tudo misturado (loja grande em retângulo, loja média em caixa, e os itens das barracas pequenas
    juntados de 4 em 4 vindos de vendedores DIFERENTES), em ordem embaralhada por `seed`. Ninguém ganha posição fixa: quem quiser
    achar algo específico usa os filtros e a ORDEM (mais vendidos, melhor avaliadas, mais novas, preço, perto de mim); destaque e propaganda
    ficam em faixas separadas e identificadas (ver `destaques`/`propagandas`). Com ordem != 'mix' a ordem é a pedida e o sorteio só desempata.
    `pos` = (lat, lng) do APARELHO de quem pede (só 'perto'). Devolve a página `pagina` (PAGINA_FEED itens) e se há mais."""
    seed = _seed_limpa(seed)
    ordem = ordem if ordem in IDS_ORDEM else 'mix'
    if ordem == 'perto' and not pos:
        raise ErroBazar('Pra ver as lojas perto de você o app precisa da localização do aparelho (GPS ou Wi-Fi). Ligue em Configurações > Geral.')
    q = BazarLoja.query.filter(BazarLoja.aberta.isnot(False), BazarLoja.oculta.isnot(True), ~BazarLoja.owner_id.in_(_subq_banidos()))
    if categoria in IDS_CATEGORIA:
        q = q.filter(BazarLoja.categoria == categoria)
    if so_favoritas:
        q = q.filter(BazarLoja.id.in_(select(BazarFavorito.loja_id).where(BazarFavorito.person_id == int(pessoa_id or 0))))
    termo = (busca or '').strip().lower()[:40]
    if termo:
        nos_produtos = select(BazarProduto.loja_id).where(BazarProduto.ativo.isnot(False), BazarProduto.oculta.isnot(True),
                                                         func.lower(BazarProduto.nome).contains(termo, autoescape=True))
        q = q.filter(or_(func.lower(BazarLoja.nome).contains(termo, autoescape=True),
                         func.lower(BazarLoja.descricao).contains(termo, autoescape=True), BazarLoja.id.in_(nos_produtos)))
    lojas = q.options(joinedload(BazarLoja.owner)).order_by(BazarLoja.id).limit(MAX_LOJAS_FEED).all()
    por_loja = _produtos_visiveis_de([l.id for l in lojas])

    def ordenacao(chave, *k):
        s = _sorteio(seed, chave)
        return (s,) if ordem == 'mix' else tuple(k) + (s,)

    itens, micro = [], {}
    for l in lojas:
        prods = por_loja.get(l.id, [])
        if tipo in TIPOS_PRODUTO:
            prods = [p for p in prods if p.tipo == tipo]
        nome_bate = bool(termo) and (termo in (l.nome or '').lower() or termo in (l.descricao or '').lower())
        if termo and not nome_bate:
            prods = [p for p in prods if termo in p.nome.lower()]
        if not prods:
            continue                       # loja sem nada pra mostrar (ou que não bate com o filtro) não ocupa o feed
        dist = None
        if ordem == 'perto':
            if l.lat is None or l.lng is None:
                continue                   # só aparece em "perto de mim" quem pediu pra aparecer (e a posição é arredondada, ~1 km)
            km = distancia_m(pos[0], pos[1], l.lat, l.lng) / 1000
            if km > RAIO_PERTO_KM:
                continue
            dist = max(1, round(km))
        if l.porte == 'micro':
            micro[l.id] = [(p, l, dist) for p in prods]
            continue
        j = loja_json(l, [produto_json(p) for p in prods[:4]], dist_km=dist)
        j['total_produtos'] = len(prods)
        itens.append((f'l{l.id}', {'t': 'loja', 'loja': j}, ordenacao(f'l{l.id}', *_k_loja(ordem, l, prods, dist))))

    if ordem == 'mix':
        # barracas pequenas: cada passada tira UM item de cada vendedor (em ordem embaralhada), então cada "quadrado de 4"
        # junta vendedores diferentes e ninguém aparece mais que os outros.
        vendedores = sorted(micro, key=lambda lid: _sorteio(seed, f'v{lid}'))
        filas = {lid: sorted([_produto_do_feed(p, l, d) for (p, l, d) in micro[lid]], key=lambda j: _sorteio(seed, f'p{j["id"]}')) for lid in vendedores}
        quad, total_micro = [], 0
        while any(filas.values()) and total_micro < MAX_ITENS_MICRO:
            for lid in vendedores:
                if filas[lid]:
                    quad.append(filas[lid].pop(0)); total_micro += 1
                    if len(quad) == 4:
                        itens.append((f'q{quad[0]["id"]}', {'t': 'quad', 'produtos': quad}, ordenacao(f'q{quad[0]["id"]}'))); quad = []
        if quad:
            itens.append((f'q{quad[0]["id"]}', {'t': 'quad', 'produtos': quad}, ordenacao(f'q{quad[0]["id"]}')))
    else:
        # ordem pedida: os itens de TODAS as barracas pequenas entram na mesma fila e saem de 4 em 4 já na ordem
        todos = sorted(((ordenacao(f'p{p.id}', *_k_prod(ordem, l, p, d)), _produto_do_feed(p, l, d)) for lid in micro for (p, l, d) in micro[lid]), key=lambda t: t[0])
        for i in range(0, min(len(todos), MAX_ITENS_MICRO), 4):
            grupo = todos[i:i + 4]
            quad = [j for _, j in grupo]
            itens.append((f'q{quad[0]["id"]}', {'t': 'quad', 'produtos': quad}, grupo[0][0]))

    itens.sort(key=lambda t: t[2])
    pagina = max(int(pagina or 0), 0)
    ini = pagina * PAGINA_FEED
    return {'itens': [x for _, x, _o in itens[ini:ini + PAGINA_FEED]], 'tem_mais': ini + PAGINA_FEED < len(itens),
            'total': len(itens), 'pagina': pagina, 'seed': seed, 'ordem': ordem}


def propagandas(seed=''):
    """O carrossel do topo: as lojas parceiras (porte "grande", que só um admin define; o texto vem da própria propaganda da loja) MAIS os anúncios
    cadastrados por um admin (arte própria, janela de datas, contagem de cliques). A ordem rotaciona por seed: ninguém fica sempre em primeiro."""
    seed = _seed_limpa(seed)
    lojas = (BazarLoja.query.filter(BazarLoja.porte == 'grande', BazarLoja.aberta.isnot(False), BazarLoja.oculta.isnot(True),
                                    ~BazarLoja.owner_id.in_(_subq_banidos())).order_by(BazarLoja.id).limit(12).all())
    out = [{'tipo': 'parceira', 'loja_id': l.id, 'nome': l.nome, 'titulo': l.anuncio_titulo or l.nome,
            'texto': l.anuncio_texto or (l.descricao or '')[:140], 'banner_url': l.banner_url, 'logo_url': l.logo_url,
            'cor': l.cor, 'toldo': l.toldo} for l in lojas]
    agora = br_now()
    anuncios = (BazarAnuncio.query.filter(BazarAnuncio.ativo.isnot(False), or_(BazarAnuncio.inicio.is_(None), BazarAnuncio.inicio <= agora),
                                          or_(BazarAnuncio.fim.is_(None), BazarAnuncio.fim >= agora)).order_by(BazarAnuncio.id).limit(20).all())
    ids_loja = {a.loja_id for a in anuncios if a.destino == 'loja' and a.loja_id}
    visiveis = {l.id for l in BazarLoja.query.filter(BazarLoja.id.in_(ids_loja), BazarLoja.aberta.isnot(False), BazarLoja.oculta.isnot(True),
                                                     ~BazarLoja.owner_id.in_(_subq_banidos())).all()} if ids_loja else set()
    for a in anuncios:
        if a.destino == 'loja' and a.loja_id not in visiveis:
            continue                       # anúncio que leva a uma loja que sumiu/foi banida não aparece
        out.append(anuncio_json(a))
    out.sort(key=lambda x: _sorteio(seed, f'a{x["tipo"][0]}{x.get("id") or x.get("loja_id")}'))
    return out


def destaques():
    """Faixa "bem avaliadas": o critério é a nota (e o nº de avaliações), à vista de todos, não escolha de ninguém."""
    lojas = (BazarLoja.query.filter(BazarLoja.aberta.isnot(False), BazarLoja.oculta.isnot(True), BazarLoja.nota_qtd >= MIN_AVALIACOES_DESTAQUE,
                                    ~BazarLoja.owner_id.in_(_subq_banidos()))
             .options(joinedload(BazarLoja.owner)).all())
    lojas.sort(key=lambda l: (-(l.nota_soma / l.nota_qtd), -l.nota_qtd, -(l.vendas or 0), l.id))
    return [{'id': l.id, 'nome': l.nome, 'logo_url': l.logo_url, 'cor': l.cor, 'toldo': l.toldo, 'nota': nota_media(l),
             'nota_qtd': l.nota_qtd, 'porte': l.porte, 'categoria': l.categoria, 'verificada': bool(l.verificada), 'reputacao': reputacao(l)} for l in lojas[:8]]


# ---------------------------------------------------------------------------
# FAVORITOS (seguir loja)
# ---------------------------------------------------------------------------
def favoritos_de(pessoa_id):
    return [r[0] for r in db.session.query(BazarFavorito.loja_id).filter(BazarFavorito.person_id == pessoa_id).order_by(BazarFavorito.id).all()]


def alternar_favorito(usuario, loja_id, ativo):
    """Favorita ou desfavorita (valor EXPLÍCITO: duas abas clicando juntas não se anulam). Devolve a lista de favoritos da pessoa."""
    ativo = bool(ativo)

    def preparar():
        l = BazarLoja.query.get(int(loja_id)) if str(loja_id).isdigit() else None
        if not l or l.oculta:
            raise ErroBazar('Essa loja não está disponível.')
        if l.owner_id == usuario.id:
            raise ErroBazar('A sua própria loja não precisa ser favoritada.')
        atual = BazarFavorito.query.filter_by(person_id=usuario.id, loja_id=l.id).first()
        if ativo and not atual:
            if BazarFavorito.query.filter_by(person_id=usuario.id).count() >= MAX_FAVORITOS:
                raise ErroBazar(f'Você já tem {MAX_FAVORITOS} lojas favoritas. Tire alguma antes.')
            db.session.add(BazarFavorito(person_id=usuario.id, loja_id=l.id))
        elif not ativo and atual:
            db.session.delete(atual)

    try:
        comitar_com_retry(preparar)
    except IntegrityError:
        db.session.rollback()              # as duas abas favoritaram juntas: já está favoritada, é o que a pessoa queria
    return favoritos_de(usuario.id)


# ---------------------------------------------------------------------------
# ANÚNCIOS (carrossel): só admin cria; arte própria, janela de datas, contagem de cliques
# ---------------------------------------------------------------------------
_RE_LINK_ANUNCIO = re.compile(r'''^https://[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(:\d{1,5})?(/[^\s'"()<>\\]*)?$''', re.I)
ICONE_DESTINO = {'loja': 'fa-store', 'link': 'fa-arrow-up-right-from-square', 'painel': 'fa-store', 'aviso': 'fa-shield-halved', 'armazem': 'fa-wand-magic-sparkles', 'nenhum': 'fa-bullhorn'}
ANUNCIOS_PADRAO = [
    {'titulo': 'Monte a sua loja', 'texto': 'Abra a sua barraca em poucos minutos: escolha a cor e o toldo, cadastre os produtos e receba por Pix direto.', 'cor': 'lavanda', 'cta': 'Abrir a minha lojinha', 'destino': 'painel'},
    {'titulo': 'Pix direto, sem taxa do Panteão', 'texto': 'Confira o nome do recebedor antes de pagar e só pague depois que o vendedor aceitar o pedido.', 'cor': 'oceano', 'cta': 'Como funciona', 'destino': 'aviso'},
    {'titulo': 'Personalize o seu perfil', 'texto': 'Molduras, nomes e placas animadas, pagos em DRC. Combine com a sua loja.', 'cor': 'ambar', 'cta': 'Ir ao Armazém', 'destino': 'armazem'},
]


def anuncio_json(a, admin=False):
    j = {'tipo': 'anuncio', 'id': a.id, 'titulo': a.titulo, 'texto': a.texto or '', 'imagem_url': a.imagem_url, 'cor': a.cor or 'lavanda',
         'cta': a.cta or 'Saiba mais', 'destino': a.destino or 'nenhum', 'loja_id': a.loja_id, 'link_url': a.link_url if (a.destino == 'link') else None,
         'icone': ICONE_DESTINO.get(a.destino or 'nenhum', 'fa-bullhorn')}
    if admin:
        agora = br_now()
        estado = ('pausado' if a.ativo is False else 'agendado' if a.inicio and a.inicio > agora else 'encerrado' if a.fim and a.fim < agora else 'no ar')
        j.update({'ativo': a.ativo is not False, 'cliques': a.cliques or 0, 'estado': estado,
                  'inicio': a.inicio.strftime('%Y-%m-%d') if a.inicio else '', 'fim': a.fim.strftime('%Y-%m-%d') if a.fim else ''})
    return j


def anuncios_cadastrados():
    return BazarAnuncio.query.count()


def lista_anuncios(admin):
    _exigir_admin(admin)
    return [anuncio_json(a, True) for a in BazarAnuncio.query.order_by(BazarAnuncio.id.desc()).limit(100).all()]


def _data(valor, nome, fim=False):
    v = str(valor or '').strip()
    if not v:
        return None
    try:
        d = datetime.strptime(v, '%Y-%m-%d')
    except ValueError:
        raise ErroBazar(f'{nome[:1].upper()}{nome[1:]}: data inválida.')
    return d.replace(hour=23, minute=59, second=59) if fim else d


def salvar_anuncio(admin, dados):
    _exigir_admin(admin)
    dados = dados or {}
    titulo = _texto(dados.get('titulo'), LIM_ANUNCIO_TITULO, 'o título do anúncio', obrigatorio=True)
    texto = _texto(dados.get('texto'), LIM_ANUNCIO_TEXTO, 'o texto do anúncio')
    imagem = _url_imagem(dados.get('imagem_url'), 'a arte do anúncio')
    cor = dados.get('cor') if dados.get('cor') in CORES else 'lavanda'
    cta = _texto(dados.get('cta'), LIM_ANUNCIO_CTA, 'o texto do botão') or 'Saiba mais'
    destino = dados.get('destino') if dados.get('destino') in DESTINOS_ANUNCIO else 'nenhum'
    loja_id, link = None, None
    if destino == 'loja':
        loja_id = _inteiro(dados.get('loja_id'), 1, 2_000_000_000, 'o número da loja')
        if not db.session.get(BazarLoja, loja_id):
            raise ErroBazar('Não existe loja com esse número.')
    elif destino == 'link':
        link = str(dados.get('link_url') or '').strip()
        if len(link) > 255 or not _RE_LINK_ANUNCIO.match(link):
            raise ErroBazar('Link inválido: use um endereço https:// completo (sem aspas, espaços ou usuário@).')
    inicio, fim = _data(dados.get('inicio'), 'o início'), _data(dados.get('fim'), 'o fim', fim=True)
    if inicio and fim and fim < inicio:
        raise ErroBazar('O fim não pode ser antes do início.')
    ativo = bool(dados.get('ativo', True))
    aid = dados.get('id')

    def preparar():
        a = BazarAnuncio.query.get(int(aid)) if aid else BazarAnuncio(criado_por_id=admin.id)
        if not a:
            raise ErroBazar('Anúncio não encontrado.')
        a.titulo, a.texto, a.imagem_url, a.cor, a.cta, a.destino, a.loja_id, a.link_url = titulo, texto, imagem, cor, cta, destino, loja_id, link
        a.inicio, a.fim, a.ativo = inicio, fim, ativo
        if not aid:
            db.session.add(a)
        db.session.flush()
        return a.id

    try:
        comitar_com_retry(preparar)
    except (TypeError, ValueError):
        raise ErroBazar('Anúncio inválido.')


def apagar_anuncio(admin, anuncio_id):
    _exigir_admin(admin)

    def preparar():
        a = BazarAnuncio.query.get(int(anuncio_id)) if str(anuncio_id).isdigit() else None
        if a:
            db.session.delete(a)

    comitar_com_retry(preparar)


def criar_anuncios_padrao(admin):
    """Importa os 3 anúncios do Panteão (os que antes eram fixos no bazar.js) pra poder editar/apagar. Só se não houver nenhum anúncio ainda."""
    _exigir_admin(admin)

    def preparar():
        if BazarAnuncio.query.count():
            raise ErroBazar('Já existem anúncios cadastrados: edite os que há.')
        for d in ANUNCIOS_PADRAO:
            db.session.add(BazarAnuncio(criado_por_id=admin.id, ativo=True, **d))

    comitar_com_retry(preparar)


def registrar_clique(anuncio_id):
    """+1 atômico, só se o anúncio está no ar agora (clique em anúncio velho/pausado não conta)."""
    if not str(anuncio_id).isdigit():
        return False
    agora = br_now()

    def preparar():
        return db.session.execute(update(BazarAnuncio).where(
            BazarAnuncio.id == int(anuncio_id), BazarAnuncio.ativo.isnot(False), or_(BazarAnuncio.inicio.is_(None), BazarAnuncio.inicio <= agora),
            or_(BazarAnuncio.fim.is_(None), BazarAnuncio.fim >= agora)).values(cliques=func.coalesce(BazarAnuncio.cliques, 0) + 1)).rowcount == 1

    return comitar_com_retry(preparar)


def loja_completa(loja_id, eu):
    """A página de uma loja. Dono vê tudo dela (inclusive pausado/oculto); os outros só o que está à venda."""
    l = BazarLoja.query.get(loja_id)
    if not l:
        raise ErroBazar('Essa loja não existe mais.')
    dono = eu is not None and l.owner_id == eu.id
    if not dono and (l.oculta or l.aberta is False or _banimento_ativo(l.owner_id)):
        raise ErroBazar('Essa loja não está disponível agora.')
    q = BazarProduto.query.filter_by(loja_id=l.id)
    if not dono:
        q = q.filter(BazarProduto.ativo.isnot(False), BazarProduto.oculta.isnot(True))
    prods = q.order_by(BazarProduto.id.desc()).all()
    avals = (BazarAvaliacao.query.filter_by(loja_id=l.id).order_by(BazarAvaliacao.id.desc()).limit(8).all())
    j = loja_json(l, [produto_json(p, dono) for p in prods], dono)
    j['avaliacoes'] = [{'nota': a.nota, 'texto': a.texto or '', 'nome': a.avaliador.name if a.avaliador else '?', 'hora': _hora(a.created_at)} for a in avals]
    j['eh_dono'] = dono
    j['seguidores'] = BazarFavorito.query.filter_by(loja_id=l.id).count()
    j['favorita'] = bool(eu is not None and not dono and BazarFavorito.query.filter_by(person_id=eu.id, loja_id=l.id).first())
    return j


def estatisticas_da_loja(loja):
    """Números do painel do vendedor: pedidos por situação e quanto já foi concluído (só pra ele ver; o dinheiro não passa pelo app)."""
    por_status = dict(db.session.query(BazarPedido.status, func.count(BazarPedido.id)).filter(BazarPedido.loja_id == loja.id)
                      .group_by(BazarPedido.status).all())
    receita = db.session.query(func.coalesce(func.sum(BazarPedido.total_cent), 0)).filter(
        BazarPedido.loja_id == loja.id, BazarPedido.status == 'concluido').scalar() or 0
    return {'aguardando': por_status.get('aguardando', 0), 'abertos': sum(por_status.get(s, 0) for s in ABERTOS),
            'concluidos': por_status.get('concluido', 0), 'receita_cent': int(receita)}


def minha_loja(usuario):
    l = BazarLoja.query.filter_by(owner_id=usuario.id).first()
    if not l:
        return None
    prods = BazarProduto.query.filter_by(loja_id=l.id).order_by(BazarProduto.id.desc()).all()
    j = loja_json(l, [produto_json(p, True) for p in prods], True)
    j['stats'] = estatisticas_da_loja(l)
    return j


# ==========================================
# LOJA E PRODUTO (escrita)
# ==========================================
def salvar_loja(usuario, dados, pos=None):
    """Cria ou atualiza a loja da pessoa. Devolve o JSON de dono. `pos` = (lat, lng) do APARELHO (só serve pra "perto de mim")."""
    _exigir_localizacao(usuario)
    _exigir_nao_banido(usuario)
    dados = dados or {}
    nome = _texto(dados.get('nome'), LIM_NOME_LOJA, 'o nome da loja', obrigatorio=True)
    descricao = _texto(dados.get('descricao'), LIM_DESC_LOJA, 'a descrição')
    categoria = dados.get('categoria') if dados.get('categoria') in IDS_CATEGORIA else 'outros'
    porte = dados.get('porte') if dados.get('porte') in PORTES_LIVRES else 'micro'
    regiao = _texto(dados.get('regiao'), LIM_REGIAO, 'a região')
    cor = dados.get('cor') if dados.get('cor') in CORES else 'ambar'
    toldo = dados.get('toldo') if dados.get('toldo') in TOLDOS else 'vermelho'
    logo = _url_imagem(dados.get('logo_url'), 'o logo')
    banner = _url_imagem(dados.get('banner_url'), 'o banner')
    an_titulo = _texto(dados.get('anuncio_titulo'), LIM_ANUNCIO_TITULO, 'o título da propaganda')
    an_texto = _texto(dados.get('anuncio_texto'), LIM_ANUNCIO_TEXTO, 'o texto da propaganda')
    pix = normalizar_chave_pix(dados.get('pix_chave'))
    pix_nome = _texto(dados.get('pix_nome'), 25, 'o nome do Pix')
    pix_cidade = _texto(dados.get('pix_cidade'), 15, 'a cidade do Pix')
    aberta = bool(dados.get('aberta', True))
    no_mapa = bool(dados.get('no_mapa'))

    def preparar():
        l = BazarLoja.query.filter_by(owner_id=usuario.id).first()
        nova = l is None
        if nova:
            # conta recém-criada não abre loja: golpe costuma vir de conta descartável (Person.created_at NULL = conta antiga = vale)
            if usuario.created_at and br_now() - usuario.created_at < timedelta(days=IDADE_MIN_LOJA_DIAS):
                libera = (usuario.created_at + timedelta(days=IDADE_MIN_LOJA_DIAS)).strftime('%d/%m')
                raise ErroBazar(f'Contas novas esperam {IDADE_MIN_LOJA_DIAS} dias pra abrir loja (proteção contra golpe de conta descartável). Você poderá abrir a partir de {libera}.')
            l = BazarLoja(owner_id=usuario.id)
            db.session.add(l)
        l.nome, l.descricao, l.categoria, l.regiao, l.cor, l.toldo = nome, descricao, categoria, regiao, cor, toldo
        l.logo_url, l.banner_url, l.anuncio_titulo, l.anuncio_texto = logo, banner, an_titulo, an_texto
        l.pix_chave, l.pix_nome, l.pix_cidade, l.aberta = pix, pix_nome, pix_cidade, aberta
        if l.porte != 'grande':             # parceira só muda por um admin
            l.porte = porte
        # "aparecer em perto de mim": guarda a posição ARREDONDADA (0,01° ~ 1 km: nunca o endereço). Sem posição agora, mantém a que já tinha.
        if not no_mapa:
            l.lat = l.lng = None
        elif pos:
            l.lat, l.lng = round(pos[0], 2), round(pos[1], 2)
        elif l.lat is None:
            raise ErroBazar('Pra aparecer em "perto de mim" o app precisa da localização do aparelho (GPS ou Wi-Fi). Ligue em Configurações > Geral e tente de novo.')
        db.session.flush()
        return l

    l = comitar_com_retry(preparar)
    return minha_loja(usuario) if l else None


def _montar_produto(dados, p, loja=None):
    nome = _texto(dados.get('nome'), LIM_NOME_PROD, 'o nome do produto', obrigatorio=True)
    descricao = _texto(dados.get('descricao'), LIM_DESC_PROD, 'a descrição')
    preco = _inteiro(dados.get('preco_cent'), PRECO_MIN_CENT, PRECO_MAX_CENT, 'o preço')
    if loja is not None and (loja.vendas or 0) < VENDAS_PARA_LIBERAR and preco > LIMITE_LOJA_NOVA_CENT and (p.id is None or p.preco_cent != preco):
        raise ErroBazar(f'Loja nova vende produtos de até R$ {LIMITE_LOJA_NOVA_CENT / 100:.2f} até concluir {VENDAS_PARA_LIBERAR} vendas (proteção de quem compra). Faltam {VENDAS_PARA_LIBERAR - (loja.vendas or 0)}.'.replace('.', ',', 1))
    tipo = dados.get('tipo') if dados.get('tipo') in TIPOS_PRODUTO else 'fisico'
    frete = _inteiro(dados.get('frete_cent'), 0, FRETE_MAX_CENT, 'o frete', opcional=True) if tipo == 'fisico' else None
    retirada = bool(dados.get('aceita_retirada')) and tipo == 'fisico'
    imagens = []
    for u in (dados.get('imagens') or [])[:LIM_IMAGENS]:
        u = _url_imagem(u, 'a imagem')
        if u:
            imagens.append(u)
    video = _url_video(dados.get('video_url'))
    estoque = _inteiro(dados.get('estoque'), 0, ESTOQUE_MAX, 'o estoque', opcional=True)
    combo = [_texto(x, LIM_COMBO_ITEM, 'o item do combo') for x in (dados.get('combo_itens') or [])[:LIM_COMBO]]
    combo = [c for c in combo if c]
    avulso = _inteiro(dados.get('preco_avulso_cent'), preco, PRECO_MAX_CENT * 4, 'o preço dos itens avulsos', opcional=True) if combo else None
    entrega = _texto(dados.get('entrega'), LIM_ENTREGA, 'a instrução de entrega', links=True)
    ativo = bool(dados.get('ativo', True))
    p.nome, p.descricao, p.preco_cent, p.tipo, p.video_url, p.estoque = nome, descricao, preco, tipo, video, estoque
    p.imagens = json.dumps(imagens) if imagens else None
    p.combo_itens = json.dumps(combo, ensure_ascii=False) if combo else None
    p.preco_avulso_cent, p.entrega, p.ativo = avulso, entrega, ativo
    p.frete_cent, p.aceita_retirada = frete, retirada


def salvar_produto(usuario, dados):
    """Cria (sem `id`) ou edita um produto da loja da pessoa."""
    _exigir_localizacao(usuario)
    _exigir_nao_banido(usuario)
    dados = dados or {}
    pid = dados.get('id')

    def preparar():
        l = BazarLoja.query.filter_by(owner_id=usuario.id).first()
        if not l:
            raise ErroBazar('Abra a sua loja antes de cadastrar produtos.')
        if pid:
            p = BazarProduto.query.get(int(pid))
            if not p or p.loja_id != l.id:
                raise ErroBazar('Produto não encontrado.')
        else:
            p = BazarProduto(loja_id=l.id)
        _montar_produto(dados, p, l)
        if p.ativo:
            ativos = BazarProduto.query.filter(BazarProduto.loja_id == l.id, BazarProduto.ativo.isnot(False), BazarProduto.id != (p.id or 0)).count()
            if ativos >= MAX_PRODUTOS_ATIVOS:
                raise ErroBazar(f'Cada loja pode ter até {MAX_PRODUTOS_ATIVOS} produtos ativos. Pause ou apague algum.')
        if not pid:
            db.session.add(p)
        db.session.flush()
        return p

    try:
        comitar_com_retry(preparar)
    except (TypeError, ValueError):
        raise ErroBazar('Produto inválido.')
    return minha_loja(usuario)


def apagar_produto(usuario, produto_id):
    """Apaga o produto; se já teve pedido, só desativa (o histórico dos pedidos depende dele)."""
    def preparar():
        l = BazarLoja.query.filter_by(owner_id=usuario.id).first()
        p = BazarProduto.query.get(int(produto_id)) if l else None
        if not p or p.loja_id != l.id:
            raise ErroBazar('Produto não encontrado.')
        if BazarPedido.query.filter_by(produto_id=p.id).first():
            p.ativo = False
        else:
            db.session.delete(p)

    comitar_com_retry(preparar)
    return minha_loja(usuario)


# ==========================================
# PEDIDOS
# ==========================================
def _bloqueados(a_id, b_id):
    return Friendship.query.filter(Friendship.status == 'blocked', or_(
        and_(Friendship.requester_id == a_id, Friendship.addressee_id == b_id),
        and_(Friendship.requester_id == b_id, Friendship.addressee_id == a_id))).first() is not None


def abrir_pedido(usuario, produto_id, quantidade=1, nota=None, entrega=None, endereco=None):
    """`entrega` = um dos modos que o PRODUTO oferece (`modos_de_entrega`); 'envio' exige endereço e soma o frete do produto ao total."""
    _exigir_localizacao(usuario)
    _exigir_nao_banido(usuario)
    qtd = _inteiro(quantidade, 1, QTD_MAX_PEDIDO, 'a quantidade')
    nota = _texto(nota, LIM_NOTA_PEDIDO, 'o recado')
    resultado = {}

    def preparar():
        p = BazarProduto.query.get(int(produto_id)) if str(produto_id).isdigit() else None
        l = p.loja if p else None
        if not p or p.ativo is False or p.oculta or l.oculta or l.aberta is False or _banimento_ativo(l.owner_id):
            raise ErroBazar('Esse produto não está mais disponível.')
        if l.owner_id == usuario.id:
            raise ErroBazar('Você não pode comprar da sua própria loja.')
        if _bloqueados(usuario.id, l.owner_id):
            raise ErroBazar('Não foi possível abrir o pedido.')
        modos = modos_de_entrega(p)
        if entrega in modos:
            modo = entrega
        elif len(modos) == 1:
            modo = modos[0]
        else:
            raise ErroBazar('Escolha como quer receber: ' + ' ou '.join(ROTULO_ENTREGA[m].lower() for m in modos) + '.')
        frete, end = 0, None
        if modo == 'envio':
            end = _texto(endereco, LIM_ENDERECO, 'o endereço de entrega', obrigatorio=True)
            if len(end) < MIN_ENDERECO:
                raise ErroBazar('Preencha o endereço completo (rua, número, bairro, cidade e CEP).')
            frete = p.frete_cent or 0
        if p.estoque is not None and p.estoque < qtd:
            raise ErroBazar('Estoque insuficiente.' if p.estoque else 'Esgotado.')
        abertos = BazarPedido.query.filter(BazarPedido.comprador_id == usuario.id, BazarPedido.status.in_(ABERTOS))
        if abertos.filter(BazarPedido.produto_id == p.id).first():
            raise ErroBazar('Você já tem um pedido aberto desse produto. Acompanhe em "Meus pedidos".')
        if abertos.count() >= MAX_PEDIDOS_ABERTOS_COMPRADOR:
            raise ErroBazar(f'Você já tem {MAX_PEDIDOS_ABERTOS_COMPRADOR} pedidos abertos. Conclua ou cancele algum antes.')
        ped = BazarPedido(produto_id=p.id, loja_id=l.id, comprador_id=usuario.id, vendedor_id=l.owner_id, produto_nome=p.nome,
                          quantidade=qtd, preco_unit_cent=p.preco_cent, total_cent=p.preco_cent * qtd + frete, status='aguardando', nota=nota,
                          entrega_modo=modo, frete_cent=frete, endereco=end)
        db.session.add(ped)
        db.session.flush()
        resultado['id'] = ped.id

    comitar_com_retry(preparar)
    return BazarPedido.query.get(resultado['id'])


def _liberar_estoque(p):
    if p.estoque_reservado and p.produto and p.produto.estoque is not None:
        db.session.execute(update(BazarProduto).where(BazarProduto.id == p.produto_id, BazarProduto.estoque.isnot(None))
                           .values(estoque=BazarProduto.estoque + (p.quantidade or 1)))
    p.estoque_reservado = False


def agir_no_pedido(usuario, pedido_id, acao):
    """Aplica uma ação do vendedor/comprador. A troca de status é um UPDATE condicional (`WHERE status = atual`), então duas abas
    clicando juntas (ou o outro lado agindo ao mesmo tempo) nunca aplicam a mesma transição duas vezes."""
    def preparar():
        p = BazarPedido.query.get(int(pedido_id)) if str(pedido_id).isdigit() else None
        papel = None
        if p:
            papel = 'vendedor' if p.vendedor_id == usuario.id else 'comprador' if p.comprador_id == usuario.id else None
        if not papel:
            raise ErroBazar('Pedido não encontrado.')
        if BazarDisputa.query.filter_by(pedido_id=p.id, status='aberta').first():
            raise ErroBazar('Esse pedido está em disputa: um administrador está analisando. Você segue podendo conversar no pedido.')
        novo = TRANSICOES.get((p.status, papel, acao))
        if not novo:
            raise ErroBazar('Essa ação não vale mais: o pedido mudou de estado. A tela foi atualizada.')
        if acao == 'aceitar':
            _exigir_nao_banido(usuario)
            _exigir_localizacao(usuario)
            if not (p.loja and p.loja.pix_chave):
                raise ErroBazar('Cadastre a sua chave Pix na loja antes de aceitar pedidos.')
        r = db.session.execute(update(BazarPedido).where(BazarPedido.id == p.id, BazarPedido.status == p.status)
                               .values(status=novo, atualizado_em=br_now()))
        if r.rowcount != 1:
            raise ErroBazar('Essa ação não vale mais: o pedido mudou de estado. A tela foi atualizada.')
        db.session.refresh(p)
        qtd = p.quantidade or 1
        if acao == 'aceitar' and p.produto and p.produto.estoque is not None:
            ok = db.session.execute(update(BazarProduto).where(BazarProduto.id == p.produto_id, BazarProduto.estoque >= qtd)
                                    .values(estoque=BazarProduto.estoque - qtd)).rowcount == 1
            if not ok:
                raise ErroBazar('Estoque insuficiente para aceitar esse pedido.')
            p.estoque_reservado = True
        else:
            _efeitos_do_fim(p, novo)
        return p.id

    pid = comitar_com_retry(preparar)
    return BazarPedido.query.get(pid)


def _efeitos_do_fim(p, novo):
    """O que acontece quando o pedido TERMINA (por ação das pontas, por decisão de admin ou por banimento): estoque volta se cancelou/recusou,
    vendas contam se concluiu, e o endereço de entrega é apagado (acabou: ninguém precisa mais dele)."""
    qtd = p.quantidade or 1
    if novo in ('cancelado', 'recusado'):
        _liberar_estoque(p)
    elif novo == 'concluido':
        db.session.execute(update(BazarProduto).where(BazarProduto.id == p.produto_id)
                           .values(vendidos=func.coalesce(BazarProduto.vendidos, 0) + qtd))
        db.session.execute(update(BazarLoja).where(BazarLoja.id == p.loja_id).values(vendas=func.coalesce(BazarLoja.vendas, 0) + 1))
    if novo in ('cancelado', 'recusado', 'concluido'):
        p.endereco = None


def enviar_mensagem(usuario, pedido_id, texto, imagem_url=None):
    """Texto (sem link) e/ou uma imagem do próprio app (o comprovante do Pix, a foto do produto...). Pelo menos um dos dois."""
    texto = _texto(texto, LIM_MSG, 'a mensagem')
    imagem = _url_imagem(imagem_url, 'a imagem')
    if not texto and not imagem:
        raise ErroBazar('Escreva uma mensagem ou envie uma imagem.')

    def preparar():
        p = BazarPedido.query.get(int(pedido_id)) if str(pedido_id).isdigit() else None
        if not p or usuario.id not in (p.comprador_id, p.vendedor_id):
            raise ErroBazar('Pedido não encontrado.')
        if BazarMensagem.query.filter_by(pedido_id=p.id).count() >= MAX_MSGS_PEDIDO:
            raise ErroBazar('Essa conversa chegou ao limite de mensagens.')
        db.session.add(BazarMensagem(pedido_id=p.id, autor_id=usuario.id, texto=texto or '', imagem_url=imagem))
        return p.id

    return BazarPedido.query.get(comitar_com_retry(preparar))


def avaliar(usuario, pedido_id, nota, texto=None):
    nota = _inteiro(nota, 1, 5, 'a nota')
    texto = _texto(texto, LIM_AVALIACAO, 'o comentário')

    def preparar():
        p = BazarPedido.query.get(int(pedido_id)) if str(pedido_id).isdigit() else None
        if not p or p.comprador_id != usuario.id:
            raise ErroBazar('Pedido não encontrado.')
        if p.status != 'concluido':
            raise ErroBazar('Só dá pra avaliar depois de concluir o pedido.')
        db.session.add(BazarAvaliacao(pedido_id=p.id, loja_id=p.loja_id, avaliador_id=usuario.id, nota=nota, texto=texto))
        db.session.flush()           # a unicidade por pedido estoura aqui, antes de mexer na média
        db.session.execute(update(BazarLoja).where(BazarLoja.id == p.loja_id).values(
            nota_soma=func.coalesce(BazarLoja.nota_soma, 0) + nota, nota_qtd=func.coalesce(BazarLoja.nota_qtd, 0) + 1))
        return p.id

    try:
        pid = comitar_com_retry(preparar)
    except IntegrityError:
        db.session.rollback()
        raise ErroBazar('Você já avaliou esse pedido.')
    return BazarPedido.query.get(pid)


def contar_pendencias(pessoa_id):
    """Quantos pedidos esperam uma ação DESTA pessoa (vendedor: novo ou pago; comprador: aceito ou confirmado)."""
    return BazarPedido.query.filter(
        or_(and_(BazarPedido.vendedor_id == pessoa_id, BazarPedido.status.in_(('aguardando', 'pago'))),
            and_(BazarPedido.comprador_id == pessoa_id, BazarPedido.status.in_(('aceito', 'confirmado'))))).count()


def meus_pedidos(usuario, limite=40):
    lista = (BazarPedido.query.filter(or_(BazarPedido.comprador_id == usuario.id, BazarPedido.vendedor_id == usuario.id))
             .options(joinedload(BazarPedido.produto), joinedload(BazarPedido.loja).joinedload(BazarLoja.owner),
                      joinedload(BazarPedido.comprador), joinedload(BazarPedido.vendedor))
             .order_by(BazarPedido.atualizado_em.desc()).limit(limite).all())
    disputas = _ultimas_disputas([p.id for p in lista])         # uma consulta pra lista toda
    comprando = [pedido_json(p, usuario.id, disputas=disputas) for p in lista if p.comprador_id == usuario.id]
    vendendo = [pedido_json(p, usuario.id, disputas=disputas) for p in lista if p.vendedor_id == usuario.id]
    return {'comprando': comprando, 'vendendo': vendendo, 'precisam_de_voce': contar_pendencias(usuario.id)}


# ==========================================
# DISPUTA (uma das pontas pede a análise de um admin)
# ------------------------------------------------------------
# O Panteão não toca no dinheiro, então a decisão só muda o ESTADO do pedido (concluir / cancelar / arquivar) e fica registrada com a nota do
# admin, que as DUAS pontas leem. Reembolso, se houver, é combinado entre elas. Abrir a disputa libera o admin a ler a conversa DAQUELE pedido
# (a tela avisa antes); conversa de pedido sem disputa o admin não lê. Enquanto a disputa está aberta as ações do pedido ficam travadas.
# ==========================================
def abrir_disputa(usuario, pedido_id, motivo, detalhe):
    if motivo not in MOTIVOS_DISPUTA:
        raise ErroBazar('Escolha o motivo da disputa.')
    detalhe = _texto(detalhe, LIM_DISPUTA_DETALHE, 'o relato', obrigatorio=True)
    if len(detalhe) < MIN_DISPUTA_DETALHE:
        raise ErroBazar(f'Conte o que aconteceu (pelo menos {MIN_DISPUTA_DETALHE} caracteres).')

    def preparar():
        p = BazarPedido.query.get(int(pedido_id)) if str(pedido_id).isdigit() else None
        papel = None
        if p:
            papel = 'vendedor' if p.vendedor_id == usuario.id else 'comprador' if p.comprador_id == usuario.id else None
        if not papel:
            raise ErroBazar('Pedido não encontrado.')
        restrito = MOTIVOS_DISPUTA[motivo][1]
        if restrito and restrito != papel:
            raise ErroBazar('Esse motivo não vale pra você neste pedido.')
        if not _pode_disputar(p, papel):
            raise ErroBazar('Esse pedido não pode entrar em disputa agora (só depois de aceito e, se concluído, por ' + f'{DISPUTA_DIAS_APOS_CONCLUIR} dias).')
        if BazarDisputa.query.filter_by(pedido_id=p.id, status='aberta').first():
            raise ErroBazar('Já existe uma disputa aberta neste pedido.')
        db.session.add(BazarDisputa(pedido_id=p.id, aberta_por_id=usuario.id, motivo=motivo, detalhe=detalhe))
        return p.id

    return BazarPedido.query.get(comitar_com_retry(preparar))


def _pedido_resumo(p):
    return {'id': p.id, 'produto_nome': p.produto_nome, 'status': p.status, 'rotulo': ROTULO_STATUS.get(p.status, p.status), 'quantidade': p.quantidade or 1,
            'total_cent': p.total_cent, 'frete_cent': p.frete_cent or 0, 'entrega_rotulo': ROTULO_ENTREGA.get(p.entrega_modo or 'combinar', ''),
            'loja_id': p.loja_id, 'loja_nome': p.loja.nome if p.loja else '', 'atualizado_em': _hora(p.atualizado_em)}


def disputas_para_admin(admin, limite=40):
    """As disputas abertas (com a conversa do pedido) e as últimas decididas. Só admin."""
    _exigir_admin(admin)
    ds = BazarDisputa.query.filter_by(status='aberta').order_by(BazarDisputa.id).limit(limite).all()
    recentes = BazarDisputa.query.filter_by(status='resolvida').order_by(BazarDisputa.id.desc()).limit(10).all()
    ids = {d.pedido_id for d in ds} | {d.pedido_id for d in recentes}
    pedidos = {p.id: p for p in (BazarPedido.query.filter(BazarPedido.id.in_(ids)).options(
        joinedload(BazarPedido.loja), joinedload(BazarPedido.comprador), joinedload(BazarPedido.vendedor)).all())} if ids else {}
    abertas = []
    for d in ds:
        p = pedidos.get(d.pedido_id)
        if not p:
            continue
        msgs = BazarMensagem.query.filter_by(pedido_id=p.id).order_by(BazarMensagem.id.desc()).limit(40).all()
        outras = (BazarDisputa.query.join(BazarPedido, BazarPedido.id == BazarDisputa.pedido_id)
                  .filter(BazarPedido.loja_id == p.loja_id, BazarDisputa.id != d.id).count())
        abertas.append({'disputa': _disputa_json(d, admin.id, True), 'pedido': _pedido_resumo(p),
                        'comprador': {'id': p.comprador_id, 'nome': p.comprador.name if p.comprador else '?'},
                        'vendedor': {'id': p.vendedor_id, 'nome': p.vendedor.name if p.vendedor else '?'},
                        'aberta_por': 'vendedor' if d.aberta_por_id == p.vendedor_id else 'comprador',
                        'sou_parte': admin.id in (p.comprador_id, p.vendedor_id),      # admin que é parte do pedido não decide o próprio caso
                        'mensagens': [dict(_mensagem_json(m), autor='vendedor' if m.autor_id == p.vendedor_id else 'comprador') for m in reversed(msgs)],
                        'outras_disputas_da_loja': outras})
    resolvidas = [{'disputa': _disputa_json(d, admin.id, True), 'pedido': _pedido_resumo(pedidos[d.pedido_id])} for d in recentes if d.pedido_id in pedidos]
    return {'abertas': abertas, 'resolvidas': resolvidas}


def contar_disputas_abertas():
    return BazarDisputa.query.filter_by(status='aberta').count()


def resolver_disputa(admin, disputa_id, acao, nota):
    """acao: 'concluir' (dá como entregue: pedido com Pix informado/confirmado vira concluído), 'cancelar' (pedido em aberto vira cancelado e o
    estoque volta) ou 'arquivar' (só encerra a disputa e destrava o pedido). A nota é obrigatória: as duas pontas precisam saber o porquê."""
    _exigir_admin(admin)
    if acao not in ('concluir', 'cancelar', 'arquivar'):
        raise ErroBazar('Ação inválida.')
    nota = _texto(nota, LIM_NOTA_ADMIN, 'a nota da decisão', obrigatorio=True)

    def preparar():
        d = BazarDisputa.query.get(int(disputa_id)) if str(disputa_id).isdigit() else None
        if not d or d.status != 'aberta':
            raise ErroBazar('Essa disputa já foi resolvida.')
        p = BazarPedido.query.get(d.pedido_id)
        if admin.id in (p.comprador_id, p.vendedor_id):
            raise ErroBazar('Você é parte neste pedido: outro administrador precisa decidir esta disputa.')
        novo = None
        if acao == 'cancelar':
            if p.status not in ABERTOS:
                raise ErroBazar('Esse pedido já terminou: só dá pra arquivar a disputa.')
            novo = 'cancelado'
        elif acao == 'concluir':
            if p.status not in ('pago', 'confirmado'):
                raise ErroBazar('Só dá pra concluir um pedido com o Pix informado ou confirmado.')
            novo = 'concluido'
        if novo:
            r = db.session.execute(update(BazarPedido).where(BazarPedido.id == p.id, BazarPedido.status == p.status).values(status=novo, atualizado_em=br_now()))
            if r.rowcount != 1:
                raise ErroBazar('O pedido mudou enquanto você decidia. Abra a lista de novo.')
            db.session.refresh(p)
            _efeitos_do_fim(p, novo)
        d.status, d.resolucao, d.nota_admin, d.resolvido_por_id, d.resolvido_em = 'resolvida', acao, nota, admin.id, br_now()
        return p.id

    return BazarPedido.query.get(comitar_com_retry(preparar))


# ==========================================
# MODERAÇÃO (só admin)
# ------------------------------------------------------------
# Admin = id em config_app 'admin_ids' (lista separada por vírgula), definido POR ID uma vez (bazar_admin.py): se alguém
# trocar o @, o poder não passa pra quem pegar o @ antigo. Cobre denúncia de loja, produto, nota e servidor do mapa; pessoa
# denunciada pode ser BANIDA do Bazar (`banir`: suspende por prazo ou pra sempre), além de disputas, anúncios e o selo de loja verificada.
# ==========================================
def _ids_admin():
    c = ConfigApp.query.get('admin_ids')
    return {int(x) for x in (c.valor or '').split(',') if x.strip().isdigit()} if c else set()


def eh_admin(usuario):
    return usuario is not None and usuario.id in _ids_admin()


def _exigir_admin(usuario):
    if not eh_admin(usuario):
        raise ErroBazar('Só administradores fazem isso.')


def ids_dos_admins():
    return sorted(_ids_admin())


def definir_admin(person_id, ativo=True):
    ids = _ids_admin()
    (ids.add if ativo else ids.discard)(int(person_id))
    c = ConfigApp.query.get('admin_ids')
    if not c:
        c = ConfigApp(chave='admin_ids')
        db.session.add(c)
    c.valor = ','.join(str(i) for i in sorted(ids))
    db.session.commit()


def _resumo_alvo(tipo, a):
    # `pessoa_id` = quem seria banida do Bazar por causa desse item (o dono da loja/produto, ou a própria pessoa denunciada)
    if tipo == 'loja':
        return {'titulo': a.nome, 'sub': f'{a.owner.name if a.owner else "?"} · {a.porte}', 'oculta': bool(a.oculta), 'imagem': a.logo_url, 'pessoa_id': a.owner_id}
    if tipo == 'produto':
        imgs = _lista_json(a.imagens, 1)
        return {'titulo': a.nome, 'sub': f'{a.loja.nome if a.loja else "?"} · R$ {a.preco_cent / 100:.2f}'.replace('.', ','),
                'oculta': bool(a.oculta), 'imagem': imgs[0] if imgs else None, 'pessoa_id': a.loja.owner_id if a.loja else None}
    if tipo == 'nota':
        return {'titulo': (a.text or '')[:140], 'sub': 'Nota do mapa', 'oculta': bool(a.oculta), 'imagem': None, 'pessoa_id': None}
    if tipo == 'servidor':
        return {'titulo': a.name, 'sub': 'Servidor plantado no mapa', 'oculta': bool(a.oculta), 'imagem': None, 'pessoa_id': None}
    return {'titulo': a.name, 'sub': f'@{a.username}' if a.username else 'Pessoa', 'oculta': False, 'imagem': a.avatar, 'pessoa_id': a.id}


_MODELO_DENUNCIA = {'loja': BazarLoja, 'produto': BazarProduto, 'nota': GeoNote, 'servidor': MapServer, 'usuario': Person}


def fila_de_moderacao(limite=60):
    abertas = Denuncia.query.filter(Denuncia.resolvida.isnot(True)).order_by(Denuncia.id.desc()).limit(500).all()
    grupos = {}
    for d in abertas:
        grupos.setdefault((d.tipo, d.alvo_id), []).append(d)
    ids_por_tipo = {}
    for (tipo, alvo_id) in grupos:
        ids_por_tipo.setdefault(tipo, set()).add(alvo_id)
    alvos = {}
    for tipo, ids in ids_por_tipo.items():
        modelo = _MODELO_DENUNCIA.get(tipo)
        if modelo:
            for a in modelo.query.filter(modelo.id.in_(ids)).all():
                alvos[(tipo, a.id)] = a
    nomes = {p.id: p.name for p in Person.query.filter(Person.id.in_({d.denunciante_id for ds in grupos.values() for d in ds})).all()}
    fila = []
    for (tipo, alvo_id), ds in sorted(grupos.items(), key=lambda kv: -len(kv[1]))[:limite]:
        a = alvos.get((tipo, alvo_id))
        fila.append({'tipo': tipo, 'alvo_id': alvo_id, 'total': len(ds),
                     'alvo': _resumo_alvo(tipo, a) if a else {'titulo': '(já foi apagado)', 'sub': '', 'oculta': False, 'imagem': None},
                     'existe': a is not None,
                     'denuncias': [{'motivo': d.motivo, 'detalhe': d.detalhe or '', 'por': nomes.get(d.denunciante_id, '?')} for d in ds[:6]]})
    return fila


def moderar(admin, tipo, alvo_id, acao):
    """acao: 'restaurar' (denúncia sem fundamento: volta a aparecer e as denúncias são dispensadas) ou 'remover' (derruba e dispensa).
    Devolve o que mudou pra quem chama avisar os clientes."""
    if not eh_admin(admin):
        raise ErroBazar('Só administradores moderam.')
    if tipo not in _MODELO_DENUNCIA or acao not in ('restaurar', 'remover'):
        raise ErroBazar('Ação inválida.')
    alvo_id = int(alvo_id)
    info = {'tipo': tipo, 'alvo_id': alvo_id, 'acao': acao}

    def preparar():
        a = _MODELO_DENUNCIA[tipo].query.get(alvo_id)
        if a is not None:
            if acao == 'restaurar':
                if hasattr(a, 'oculta'):
                    a.oculta = False
            elif tipo == 'loja':
                a.oculta, a.aberta = True, False
            elif tipo == 'produto':
                if BazarPedido.query.filter_by(produto_id=a.id).first():
                    a.ativo, a.oculta = False, True
                else:
                    db.session.delete(a)
            elif tipo in ('nota', 'servidor'):
                db.session.delete(a)
            else:
                raise ErroBazar('Pessoa não se "remove": use "Banir do Bazar" (com motivo e prazo).')
        Denuncia.query.filter_by(tipo=tipo, alvo_id=alvo_id).update({'resolvida': True}, synchronize_session=False)

    comitar_com_retry(preparar)
    return info


# ---------------------------------------------------------------------------
# BANIMENTO (suspensão do Bazar) e SELO de loja verificada
# ---------------------------------------------------------------------------
def banir(admin, pessoa_id, motivo, dias=None, denuncia=None):
    """Suspende a pessoa do Bazar (`dias` vazio = pra sempre): não vende, não compra, a loja some do feed e os pedidos ainda em aberto dela são
    cancelados (estoque volta). Quem tem Pix já pago a ela precisa resolver fora (o Panteão não toca no dinheiro): as outras pontas são avisadas.
    `denuncia` = (tipo, alvo_id) opcional: dispensa as denúncias daquele alvo junto. Devolve (pessoa, [pedidos cancelados])."""
    _exigir_admin(admin)
    if not str(pessoa_id).isdigit():
        raise ErroBazar('Pessoa inválida.')
    pessoa_id = int(pessoa_id)
    if pessoa_id == admin.id:
        raise ErroBazar('Você não pode banir a si mesmo.')
    if pessoa_id in _ids_admin():
        raise ErroBazar('Administradores não podem ser banidos.')
    alvo = db.session.get(Person, pessoa_id)
    if not alvo:
        raise ErroBazar('Essa pessoa não existe.')
    motivo = _texto(motivo, LIM_BAN_MOTIVO, 'o motivo', obrigatorio=True)
    prazo = None if dias in (None, '', 0, '0') else _inteiro(dias, 1, 3650, 'o prazo em dias')
    ate = br_now() + timedelta(days=prazo) if prazo else None
    cancelados = []

    def preparar():
        del cancelados[:]
        b = BazarBanimento.query.filter_by(person_id=alvo.id).first()
        if not b:
            b = BazarBanimento(person_id=alvo.id)
            db.session.add(b)
        b.motivo, b.por_id, b.ate, b.created_at = motivo, admin.id, ate, br_now()
        for p in BazarPedido.query.filter(or_(BazarPedido.comprador_id == alvo.id, BazarPedido.vendedor_id == alvo.id), BazarPedido.status.in_(ABERTOS)).all():
            r = db.session.execute(update(BazarPedido).where(BazarPedido.id == p.id, BazarPedido.status == p.status).values(status='cancelado', atualizado_em=br_now()))
            if r.rowcount == 1:
                db.session.refresh(p)
                _efeitos_do_fim(p, 'cancelado')
                cancelados.append(p.id)
        if cancelados:
            BazarDisputa.query.filter(BazarDisputa.pedido_id.in_(cancelados), BazarDisputa.status == 'aberta').update(
                {'status': 'resolvida', 'resolucao': 'arquivar', 'nota_admin': 'Pedido cancelado porque uma das contas foi suspensa do Bazar.',
                 'resolvido_por_id': admin.id, 'resolvido_em': br_now()}, synchronize_session=False)
        if denuncia:
            Denuncia.query.filter_by(tipo=denuncia[0], alvo_id=int(denuncia[1])).update({'resolvida': True}, synchronize_session=False)

    comitar_com_retry(preparar)
    return alvo, list(cancelados)


def desbanir(admin, pessoa_id):
    _exigir_admin(admin)

    def preparar():
        b = BazarBanimento.query.filter_by(person_id=int(pessoa_id)).first() if str(pessoa_id).isdigit() else None
        if not b:
            raise ErroBazar('Essa pessoa não está banida.')
        db.session.delete(b)

    comitar_com_retry(preparar)


def lista_banidos(admin):
    _exigir_admin(admin)
    agora = br_now()
    linhas = (BazarBanimento.query.filter(or_(BazarBanimento.ate.is_(None), BazarBanimento.ate > agora)).options(joinedload(BazarBanimento.pessoa))
              .order_by(BazarBanimento.id.desc()).limit(100).all())
    return [{'pessoa_id': b.person_id, 'nome': b.pessoa.name if b.pessoa else '?', 'usuario': (b.pessoa.username if b.pessoa else '') or '',
             'motivo': b.motivo or '', 'ate': b.ate.strftime('%d/%m/%Y') if b.ate else None, 'desde': _hora(b.created_at)} for b in linhas]


def achar_pessoa(texto):
    """@usuario (ou só o nome da conta) -> Person, ou None. Só pelo @ (que é único), nunca pelo nome de exibição."""
    u = str(texto or '').strip().lstrip('@').lower()
    return Person.query.filter(func.lower(Person.username) == u).first() if u else None


def definir_verificada(admin, loja_id, ativo):
    """O selo "verificada" (um admin conferiu quem está por trás). Também sai por `python bazar_admin.py verificada <@usuario>`."""
    _exigir_admin(admin)

    def preparar():
        l = BazarLoja.query.get(int(loja_id)) if str(loja_id).isdigit() else None
        if not l:
            raise ErroBazar('Loja não encontrada.')
        l.verificada = bool(ativo)
        return l.id

    return comitar_com_retry(preparar)
