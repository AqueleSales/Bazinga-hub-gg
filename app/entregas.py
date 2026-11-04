"""Entrega acompanhada no mapa (Rodada 36): o pedido de ENVIO ganha "a caminho" e "entregue", um entregador (a própria loja ou uma pessoa
que se cadastrou), a posição dele ao vivo SÓ durante a entrega, e um tempo estimado. Sem socket aqui (os eventos moram em entregas_events.py).

Decisões que o código sustenta (leia antes de mexer):
- O Pantheon não guarda dinheiro nem intermedeia pagamento de entregador. O frete já faz parte do total do pedido (Rodada 18) e o que o
  vendedor combina com um entregador de fora é entre os dois. O acompanhamento vale tanto no Pix direto quanto no pagamento pelo app.
- A posição ao vivo NUNCA vai pro banco: fica em memória (`_ativas`) e chega só ao comprador, ao vendedor e ao próprio entregador. Não entra
  no radar, nos pinos de amigo nem em `ultimas_posicoes`, e o Modo Fantasma continua escondendo a pessoa do mapa de todo o resto: o
  consentimento de "Sair para entrega" é por pedido, explícito, e acaba quando a entrega acaba (entregue, parar, pedido encerrado, 4 h).
- A posição vem do mesmo caminho do mapa (`atualizar_localizacao`): só vale a do APARELHO (GPS/Wi-Fi); a por IP e a "suspeita" (salto
  impossível) não são repassadas. Zero consulta nova por posição: o hook só olha um dicionário em memória.
- O destino é o ponto que o comprador marcou (a posição do aparelho dele lida PELO SERVIDOR, nunca coordenada que o cliente afirma) e some
  quando o pedido termina, igual ao endereço escrito.
- Tempo estimado = distância em linha reta x fator de rota / velocidade do transporte. Sem serviço de rotas de fora: mandar a casa do
  comprador pra um servidor público de rotas seria vazar o endereço dele.
"""
import re
import time

from sqlalchemy import update, or_

from .bazar import ErroBazar, _exigir_nao_banido, _banimento_ativo, _bloqueados
from .models import db, br_now, BazarPedido, BazarEntregador, BazarDisputa, Person
from .utils import comitar_com_retry, distancia_m, localizacao_ligada, coordenada_valida, MSG_LOCALIZACAO_DESLIGADA

# transporte -> (rótulo, km/h médios na cidade, ícone Font Awesome)
TRANSPORTES = {'a_pe': ('A pé', 5.0, 'fa-person-walking'), 'bicicleta': ('Bicicleta', 14.0, 'fa-bicycle'),
               'moto': ('Moto', 28.0, 'fa-motorcycle'), 'carro': ('Carro', 24.0, 'fa-car-side')}
TRANSPORTE_PADRAO = 'moto'
FATOR_ROTA = 1.35               # a rua nunca é uma linha reta: sem serviço de rotas, soma 35% à distância em linha reta
CHEGOU_M = 60                   # a menos disso do destino = "chegando"
INTERVALO_RELE_S = 2.0          # no máximo uma posição a cada 2 s por entrega, não importa quantas o aparelho mande
INTERVALO_SINAL_S = 10.0        # aviso de "sem GPS do aparelho" ao entregador, no máximo a cada 10 s
MAX_SEGUNDOS = 4 * 3600         # passou disso a caminho, o compartilhamento acaba sozinho (esqueceram aberto)
MSG_CONSENTIMENTO = 'Confirme que você entendeu: durante a entrega o comprador e o vendedor veem a sua posição ao vivo.'
ESTADOS_ABERTOS = ('convidado', 'aceita', 'a_caminho')
PODE_MARCAR_DESTINO = ('aguardando', 'aceito', 'pago', 'confirmado', 'a_caminho')


# ---------------------------------------------------------------------------
# conta: distância e tempo (função pura, testada à parte)
# ---------------------------------------------------------------------------
def transporte_valido(valor, padrao=TRANSPORTE_PADRAO):
    v = str(valor or '').strip()
    if not v:
        return padrao
    if v not in TRANSPORTES:
        raise ErroBazar('Escolha um transporte da lista.')
    return v


def estimar(lat, lng, destino, transporte):
    """(distância em metros em linha reta, segundos estimados). Sem destino: (None, None)."""
    if not destino:
        return None, None
    dist = distancia_m(lat, lng, destino[0], destino[1])
    if dist <= CHEGOU_M:
        return round(dist), 0
    kmh = TRANSPORTES.get(transporte or TRANSPORTE_PADRAO, TRANSPORTES[TRANSPORTE_PADRAO])[1]
    return round(dist), max(60, round(dist * FATOR_ROTA / (kmh / 3.6)))


# ---------------------------------------------------------------------------
# memória: quem está compartilhando posição agora (processo único, como o resto do tempo real)
# ---------------------------------------------------------------------------
_ativas = {}                    # pedido_id -> {'entregador', 'comprador', 'vendedor', 'dest', 'transporte', 'inicio', 'rele', 'sinal', 'ultima'}
_por_entregador = {}            # pessoa_id -> {pedido_id, ...}


def _registrar(p, agora=None):
    destino = (p.destino_lat, p.destino_lng) if p.destino_lat is not None and p.destino_lng is not None else None
    _ativas[p.id] = {'entregador': p.entregador_id, 'comprador': p.comprador_id, 'vendedor': p.vendedor_id, 'dest': destino,
                     'transporte': p.transporte or TRANSPORTE_PADRAO, 'inicio': agora or time.time(), 'rele': 0.0, 'sinal': 0.0, 'ultima': None}
    _por_entregador.setdefault(p.entregador_id, set()).add(p.id)


def encerrar(pedido_id):
    """Para de compartilhar (idempotente). Devolve o id do entregador que estava compartilhando, ou None."""
    rec = _ativas.pop(pedido_id, None)
    if not rec:
        return None
    conj = _por_entregador.get(rec['entregador'])
    if conj:
        conj.discard(pedido_id)
        if not conj:
            _por_entregador.pop(rec['entregador'], None)
    return rec['entregador']


def esta_compartilhando(pessoa_id):
    return bool(_por_entregador.get(pessoa_id))


def ultima(pedido_id):
    """A última posição repassada (com a idade em segundos: o navegador não confia no relógio do aparelho pra saber se o sinal está velho)."""
    rec = _ativas.get(pedido_id)
    if not rec or not rec['ultima']:
        return None
    u = dict(rec['ultima'])
    u['idade_s'] = max(0, round(time.time() - u['ts']))
    return u


def atualizar_destino_ao_vivo(pedido_id, destino):
    rec = _ativas.get(pedido_id)
    if rec:
        rec['dest'] = destino


def repassar(pessoa_id, pos, fonte, agora=None):
    """Chamado a CADA posição que o aparelho da pessoa manda. Só trabalha se ela está compartilhando (um dicionário, zero consulta).
    Devolve (envios, sinais, expirados): envios = [(pedido_id, [pessoas que recebem], payload)], sinais = [(pedido_id, payload pro entregador)],
    expirados = [pedido_id] (passaram de MAX_SEGUNDOS: quem chama volta o pedido pra 'aceita')."""
    ids = _por_entregador.get(pessoa_id)
    if not ids:
        return [], [], []
    agora = agora or time.time()
    envios, sinais, expirados = [], [], []
    for pid in list(ids):
        rec = _ativas.get(pid)
        if not rec:
            continue
        if agora - rec['inicio'] > MAX_SEGUNDOS:
            expirados.append(pid)
            continue
        if fonte != 'aparelho':
            if agora - rec['sinal'] >= INTERVALO_SINAL_S:
                rec['sinal'] = agora
                motivo = ('Sua posição veio só do endereço de internet (aproximada demais). Ligue o GPS do aparelho: sem ele ninguém te vê no mapa.'
                          if fonte == 'ip' else 'Sua posição mudou rápido demais pra ser verdade. Espere alguns segundos parado.')
                sinais.append((pid, {'pedido_id': pid, 'ok': False, 'motivo': motivo}))
            continue
        if agora - rec['rele'] < INTERVALO_RELE_S:
            continue
        rec['rele'] = agora
        dist, eta = estimar(pos[0], pos[1], rec['dest'], rec['transporte'])
        payload = {'pedido_id': pid, 'lat': round(pos[0], 6), 'lng': round(pos[1], 6), 'ts': round(agora), 'dist_m': dist, 'eta_s': eta,
                   'chegando': dist is not None and dist <= CHEGOU_M, 'transporte': rec['transporte']}
        rec['ultima'] = {k: payload[k] for k in ('lat', 'lng', 'ts', 'dist_m', 'eta_s', 'chegando')}
        quem = {rec['comprador'], rec['vendedor'], rec['entregador']}
        envios.append((pid, sorted(q for q in quem if q), payload))
    return envios, sinais, expirados


# ---------------------------------------------------------------------------
# cadastro de entregador
# ---------------------------------------------------------------------------
def cadastrar_entregador(usuario, ativo, consentimento=False):
    """Liga/desliga o papel. Ligar exige o aceite explícito (valor `consentimento` verdadeiro); desligar vale sempre e cancela convites abertos."""
    _exigir_nao_banido(usuario)
    ativo = bool(ativo)
    if ativo and not consentimento:
        raise ErroBazar('Marque que você entendeu como funciona o compartilhamento de posição antes de se cadastrar.')
    if ativo and not localizacao_ligada(usuario):
        raise ErroBazar(MSG_LOCALIZACAO_DESLIGADA)

    def preparar():
        e = db.session.get(BazarEntregador, usuario.id)
        if not e:
            e = BazarEntregador(person_id=usuario.id, ativo=ativo, entregas=0)
            db.session.add(e)
        e.ativo = ativo
        if not ativo:
            # convites que ainda não viraram aceite caem; entrega que já está a caminho continua (terminar é o certo)
            db.session.execute(update(BazarPedido).where(BazarPedido.entregador_id == usuario.id, BazarPedido.entrega_estado == 'convidado',
                                                         BazarPedido.vendedor_id != usuario.id).values(entrega_estado='recusada'))
        return e
    return comitar_com_retry(preparar)


def eh_entregador(pessoa_id):
    e = db.session.get(BazarEntregador, pessoa_id)
    return bool(e and e.ativo)


def meu_cadastro(pessoa_id):
    e = db.session.get(BazarEntregador, pessoa_id)
    return {'ativo': bool(e and e.ativo), 'entregas': (e.entregas or 0) if e else 0}


# ---------------------------------------------------------------------------
# regras do pedido
# ---------------------------------------------------------------------------
def _pedido_de(pedido_id):
    return db.session.get(BazarPedido, int(pedido_id)) if str(pedido_id).isdigit() else None


def _sem_disputa(p):
    if BazarDisputa.query.filter_by(pedido_id=p.id, status='aberta').first():
        raise ErroBazar('Esse pedido está em disputa: um administrador está analisando. A entrega fica parada até a decisão.')


def _exigir_envio(p):
    if p.entrega_modo != 'envio':
        raise ErroBazar('Só pedidos com envio têm entrega acompanhada no mapa.')


def marcar_destino(usuario, pedido_id, pos, limpar=False):
    """O COMPRADOR marca (ou apaga) o ponto onde quer receber. `pos` é a posição do aparelho dele lida pelo servidor, nunca do cliente."""
    _exigir_nao_banido(usuario)
    if not limpar:
        if not localizacao_ligada(usuario):
            raise ErroBazar(MSG_LOCALIZACAO_DESLIGADA)
        if not pos:
            raise ErroBazar('Preciso da localização do seu aparelho (GPS ou Wi-Fi) pra marcar o ponto de entrega. Espere ela chegar e tente de novo.')

    def preparar():
        p = _pedido_de(pedido_id)
        if not p or p.comprador_id != usuario.id:
            raise ErroBazar('Pedido não encontrado.')
        _exigir_envio(p)
        if p.status not in PODE_MARCAR_DESTINO:
            raise ErroBazar('Esse pedido já terminou.')
        _sem_disputa(p)
        if limpar:
            p.destino_lat = p.destino_lng = None
        else:
            p.destino_lat, p.destino_lng = round(pos[0], 5), round(pos[1], 5)
        p.atualizado_em = br_now()
        return p
    p = comitar_com_retry(preparar)
    atualizar_destino_ao_vivo(p.id, None if limpar else (p.destino_lat, p.destino_lng))
    return p


_RE_ID = re.compile(r'^\d{1,10}$')


def _achar_entregador(alvo):
    t = str(alvo or '').strip().lstrip('@').lower()
    if not t:
        raise ErroBazar('Diga o @ de quem vai entregar.')
    from sqlalchemy import func
    if _RE_ID.match(t):
        return db.session.get(Person, int(t))
    return Person.query.filter(func.lower(Person.username) == t).first()


def designar(usuario, pedido_id, quem, alvo=None, transporte=None):
    """O VENDEDOR escolhe quem entrega: 'eu' (a própria loja) ou outra pessoa cadastrada como entregador (vira convite). Devolve (pedido, antigo_id)."""
    _exigir_nao_banido(usuario)
    quem = 'eu' if quem == 'eu' else 'outro'
    transporte = transporte_valido(transporte)
    if quem == 'eu' and not localizacao_ligada(usuario):
        raise ErroBazar(MSG_LOCALIZACAO_DESLIGADA)
    resultado = {}

    def preparar():
        p = _pedido_de(pedido_id)
        if not p or p.vendedor_id != usuario.id:
            raise ErroBazar('Pedido não encontrado.')
        _exigir_envio(p)
        if p.status != 'confirmado':
            raise ErroBazar('A entrega só começa depois que o pagamento é confirmado.' if p.status in ('aguardando', 'aceito', 'pago')
                            else 'Esse pedido já saiu para entrega ou terminou.')
        _sem_disputa(p)
        if quem == 'eu':
            novo_id, estado = usuario.id, 'aceita'
        else:
            e = _achar_entregador(alvo)
            if not e or not eh_entregador(e.id):
                raise ErroBazar('Essa pessoa não está cadastrada como entregadora. Peça pra ela ligar "Quero fazer entregas" no painel do Bazar.')
            if e.id == p.comprador_id:
                raise ErroBazar('O comprador não pode entregar o próprio pedido.')
            if e.id == usuario.id:
                novo_id, estado = usuario.id, 'aceita'
            else:
                if _banimento_ativo(e.id):
                    raise ErroBazar('Essa pessoa está suspensa do Bazar.')
                if _bloqueados(e.id, p.comprador_id) or _bloqueados(e.id, usuario.id):
                    raise ErroBazar('Não dá pra chamar essa pessoa para esse pedido.')
                novo_id, estado = e.id, 'convidado'
        antigo = p.entregador_id
        r = db.session.execute(update(BazarPedido).where(
            BazarPedido.id == p.id, BazarPedido.status == 'confirmado',
            or_(BazarPedido.entrega_estado.is_(None), BazarPedido.entrega_estado.in_(('convidado', 'aceita', 'recusada'))))
            .values(entregador_id=novo_id, entrega_estado=estado, transporte=transporte, atualizado_em=br_now()))
        if r.rowcount != 1:
            raise ErroBazar('A entrega mudou enquanto você escolhia. A tela foi atualizada.')
        db.session.refresh(p)
        resultado['antigo'] = antigo
        return p.id
    pid = comitar_com_retry(preparar)
    return _pedido_de(pid), resultado.get('antigo')


def responder_convite(usuario, pedido_id, aceitar):
    _exigir_nao_banido(usuario)
    if aceitar and not localizacao_ligada(usuario):
        raise ErroBazar(MSG_LOCALIZACAO_DESLIGADA)

    def preparar():
        p = _pedido_de(pedido_id)
        if not p or p.entregador_id != usuario.id or p.entrega_estado != 'convidado':
            raise ErroBazar('Esse convite não vale mais.')
        _sem_disputa(p)
        novo = 'aceita' if aceitar else 'recusada'
        r = db.session.execute(update(BazarPedido).where(BazarPedido.id == p.id, BazarPedido.entrega_estado == 'convidado',
                                                         BazarPedido.entregador_id == usuario.id, BazarPedido.status == 'confirmado')
                               .values(entrega_estado=novo, atualizado_em=br_now()))
        if r.rowcount != 1:
            raise ErroBazar('Esse convite não vale mais.')
        db.session.refresh(p)
        return p.id
    return _pedido_de(comitar_com_retry(preparar))


def sair_para_entrega(usuario, pedido_id, transporte=None, consentimento=False):
    """O ENTREGADOR sai: pedido vira 'a_caminho' e a posição dele passa a chegar ao comprador e ao vendedor. Consentimento explícito, por pedido."""
    _exigir_nao_banido(usuario)
    if not consentimento:
        raise ErroBazar(MSG_CONSENTIMENTO)
    if not localizacao_ligada(usuario):
        raise ErroBazar(MSG_LOCALIZACAO_DESLIGADA)

    def preparar():
        p = _pedido_de(pedido_id)
        if not p or p.entregador_id != usuario.id:
            raise ErroBazar('Pedido não encontrado.')
        _exigir_envio(p)
        _sem_disputa(p)
        t = transporte_valido(transporte, padrao=p.transporte or TRANSPORTE_PADRAO)
        r = db.session.execute(update(BazarPedido).where(
            BazarPedido.id == p.id, BazarPedido.status == 'confirmado', BazarPedido.entrega_estado == 'aceita', BazarPedido.entregador_id == usuario.id)
            .values(status='a_caminho', entrega_estado='a_caminho', transporte=t, saida_em=br_now(), atualizado_em=br_now()))
        if r.rowcount != 1:
            raise ErroBazar('Esse pedido não está pronto pra sair (precisa estar com o pagamento confirmado e a entrega aceita).')
        db.session.refresh(p)
        return p.id
    p = _pedido_de(comitar_com_retry(preparar))
    _registrar(p)
    return p


def parar_entrega(usuario, pedido_id):
    """O entregador desiste de compartilhar antes de chegar (revogar o consentimento vale a qualquer hora): volta pra 'confirmado'/'aceita'."""
    def preparar():
        p = _pedido_de(pedido_id)
        if not p or p.entregador_id != usuario.id:
            raise ErroBazar('Pedido não encontrado.')
        r = db.session.execute(update(BazarPedido).where(
            BazarPedido.id == p.id, BazarPedido.status == 'a_caminho', BazarPedido.entregador_id == usuario.id)
            .values(status='confirmado', entrega_estado='aceita', saida_em=None, atualizado_em=br_now()))
        if r.rowcount != 1:
            raise ErroBazar('Essa entrega não está a caminho.')
        db.session.refresh(p)
        return p.id
    pid = comitar_com_retry(preparar)
    encerrar(int(pid))
    return _pedido_de(pid)


def marcar_entregue(usuario, pedido_id):
    def preparar():
        p = _pedido_de(pedido_id)
        if not p or p.entregador_id != usuario.id:
            raise ErroBazar('Pedido não encontrado.')
        r = db.session.execute(update(BazarPedido).where(
            BazarPedido.id == p.id, BazarPedido.status == 'a_caminho', BazarPedido.entregador_id == usuario.id)
            .values(status='entregue', entrega_estado='entregue', entregue_em=br_now(), atualizado_em=br_now()))
        if r.rowcount != 1:
            raise ErroBazar('Essa entrega não está a caminho.')
        if p.vendedor_id != usuario.id:
            db.session.execute(update(BazarEntregador).where(BazarEntregador.person_id == usuario.id).values(entregas=BazarEntregador.entregas + 1))
        db.session.refresh(p)
        return p.id
    pid = comitar_com_retry(preparar)
    encerrar(int(pid))
    return _pedido_de(pid)


def retomar(usuario, pedido_id):
    """O servidor reiniciou (ou a aba recarregou) no meio da entrega: o entregador reabre o compartilhamento do pedido que JÁ estava a caminho."""
    p = _pedido_de(pedido_id)
    if not p or p.entregador_id != usuario.id or p.status != 'a_caminho' or p.entrega_estado != 'a_caminho':
        raise ErroBazar('Essa entrega não está a caminho.')
    if not localizacao_ligada(usuario):
        raise ErroBazar(MSG_LOCALIZACAO_DESLIGADA)
    if p.id not in _ativas:
        _registrar(p)
    return p


def expirar(pedido_id):
    """Esqueceram a entrega aberta: volta pra 'aceita' (o entregador pode sair de novo) e o compartilhamento acaba."""
    def preparar():
        r = db.session.execute(update(BazarPedido).where(BazarPedido.id == pedido_id, BazarPedido.status == 'a_caminho')
                               .values(status='confirmado', entrega_estado='aceita', saida_em=None, atualizado_em=br_now()))
        return r.rowcount == 1
    mudou = comitar_com_retry(preparar)
    encerrar(pedido_id)
    return _pedido_de(pedido_id) if mudou else None


# ---------------------------------------------------------------------------
# o que cada ponta vê
# ---------------------------------------------------------------------------
def _loja_xy(p):
    l = p.loja
    if l and l.pino_lat is not None and l.pino_lng is not None:
        return {'lat': l.pino_lat, 'lng': l.pino_lng, 'aprox': bool(l.pino_aprox)}
    return None


def _quem(pessoa):
    return {'id': pessoa.id, 'nome': pessoa.name, 'avatar': pessoa.avatar} if pessoa else None


def _entregador_de(p):
    if not p.entregador_id:
        return None
    if p.entregador_id == p.vendedor_id:
        return p.vendedor
    return db.session.get(Person, p.entregador_id)


def _hora(ts):
    return ts.strftime('%H:%M') if ts else ''


def mapa_json(p, papel, eu_id):
    """O bloco `entrega_mapa` do pedido, do ponto de vista de UMA das duas pontas. Pedido que terminou já não tem destino nem posição."""
    estado = p.entrega_estado
    terminou = p.status in ('concluido', 'cancelado', 'recusado')
    ent = _entregador_de(p)
    sou_entregador = p.entregador_id == eu_id
    ativo = p.status in ('confirmado', 'a_caminho')
    j = {'estado': estado, 'entregador': _quem(ent), 'eu_entrego': sou_entregador, 'proprio': bool(p.entregador_id and p.entregador_id == p.vendedor_id),
         'transporte': p.transporte, 'saida_em': _hora(p.saida_em), 'entregue_em': _hora(p.entregue_em),
         'destino': ({'lat': p.destino_lat, 'lng': p.destino_lng} if p.destino_lat is not None and p.destino_lng is not None and not terminou else None),
         'loja': _loja_xy(p), 'ultima': ultima(p.id) if estado == 'a_caminho' else None,
         'pode_destino': papel == 'comprador' and p.status in PODE_MARCAR_DESTINO,
         'pode_designar': papel == 'vendedor' and p.status == 'confirmado' and estado in (None, 'convidado', 'aceita', 'recusada'),
         'pode_sair': sou_entregador and p.status == 'confirmado' and estado == 'aceita',
         'pode_parar': sou_entregador and p.status == 'a_caminho', 'pode_entregar': sou_entregador and p.status == 'a_caminho',
         'ativo': ativo}
    if j['pode_designar'] or j['pode_sair']:
        j['transportes'] = [{'id': k, 'nome': v[0], 'icone': v[2], 'kmh': v[1]} for k, v in TRANSPORTES.items()]
    return j


def entrega_json(p, eu_id):
    """A entrega do ponto de vista do ENTREGADOR (que pode não ser parte do pedido): só o que ele precisa pra entregar. Sem preço, Pix, conversa
    ou chave. O endereço e o ponto do comprador só aparecem DEPOIS de ele aceitar, e somem quando o pedido termina."""
    estado = p.entrega_estado
    ve_destino = estado in ('aceita', 'a_caminho') and p.status in ('confirmado', 'a_caminho')
    loja = _loja_xy(p)
    dist_km = None
    if loja and p.destino_lat is not None and p.destino_lng is not None:
        dist_km = round(distancia_m(loja['lat'], loja['lng'], p.destino_lat, p.destino_lng) / 1000.0, 1)
    j = {'pedido_id': p.id, 'estado': estado, 'status': p.status, 'produto_nome': p.produto_nome, 'quantidade': p.quantidade or 1,
         'loja_id': p.loja_id, 'loja_nome': p.loja.nome if p.loja else '', 'loja': loja, 'transporte': p.transporte or TRANSPORTE_PADRAO,
         'dist_km': dist_km, 'vendedor': _quem(p.vendedor), 'proprio': p.entregador_id == p.vendedor_id, 'saida_em': _hora(p.saida_em),
         'ultima': ultima(p.id) if estado == 'a_caminho' else None}
    if ve_destino:
        j['comprador'] = _quem(p.comprador)
        j['endereco'] = p.endereco
        j['destino'] = {'lat': p.destino_lat, 'lng': p.destino_lng} if p.destino_lat is not None and p.destino_lng is not None else None
    return j


def minhas_entregas(pessoa_id):
    """O painel do entregador: convites, entregas aceitas e a que está a caminho (as do próprio vendedor entram também, é o mesmo botão)."""
    lista = (BazarPedido.query.filter(BazarPedido.entregador_id == pessoa_id, BazarPedido.entrega_estado.in_(ESTADOS_ABERTOS),
                                      BazarPedido.status.in_(('confirmado', 'a_caminho')))
             .order_by(BazarPedido.atualizado_em.desc()).limit(30).all())
    return {'cadastro': meu_cadastro(pessoa_id), 'entregas': [entrega_json(p, pessoa_id) for p in lista],
            'transportes': [{'id': k, 'nome': v[0], 'icone': v[2], 'kmh': v[1]} for k, v in TRANSPORTES.items()]}
