from flask import session, request
from flask_socketio import emit, join_room, leave_room
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import joinedload
from datetime import timedelta
import re
import time
from . import socketio, APP_VERSAO
from .models import (db, br_now, Message, Person, DirectMessage, Server, Channel,
                     GeoNote, MapServer, Reaction, Invite, Event, Friendship, Product,
                     Denuncia, Notificacao, Silenciado, server_members, channel_members)
from .utils import (com_retry, comitar_com_retry, canal_permitido, pode_ver_canal,
                    servidor_gerenciavel, pode_gerenciar_servidor, gerar_codigo_convite,
                    conceder_xp_por_mensagem, conceder_bonus_diario, estado_battlepass,
                    registrar_eventos, registrar_tempo_ativo, missoes_do_usuario,
                    BATIMENTO_MIN_SEGUNDOS, nivel_da_pessoa, titulo_do_nivel, membro_desde_texto,
                    ESTILOS_NOME, PLACAS, MOLDURAS, STATUS_VALIDOS, FAIXAS_ANIMADAS, url_de_imagem_ok,
                    tema_perfil_valido, username_valido, ajuste_de_imagem_valido,
                    distancia_m, coordenada_valida, localizacao_ligada, MSG_LOCALIZACAO_DESLIGADA, dados_do_mapa_perto, nota_para_json,
                    servidor_mapa_para_json, RAIO_NOTAS_M, RAIO_SERVIDORES_M,
                    MAX_NOTAS_ATIVAS_POR_PESSOA, DENUNCIAS_PARA_OCULTAR, MOTIVOS_DENUNCIA, eh_membro)
from .cosmeticos import (CATALOGO, PACOTES, TIPOS_COLUNA, TIPOS_JSON, TIPOS_EQUIPAVEIS, item_exclusivo, efeito_servidor_valido,
                         posses_da_pessoa, equipados_da_pessoa, definir_slot, badges_do_conjunto,
                         catalogo_para_json, patentes_para_json, patente_do_nivel, valor_atual_do_slot)


def usuario_logado():
    """Busca a Person da sessão atual, ou None se não estiver logado."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    try:
        return com_retry(lambda: Person.query.options(joinedload(Person.role)).get(user_id))
    except SQLAlchemyError as e:
        db.session.rollback()
        # Se isso aparecer, o banco provavelmente está com colunas faltando -
        # rode `python atualizar_banco.py` para atualizar o schema.
        print(f"[ERRO BANCO] Falha ao buscar usuário da sessão (rode atualizar_banco.py se for erro de coluna): {e}")
        return None


def sala_pessoal(user_id):
    """Sala privada de um usuário. Serve para DMs e notificações direcionadas
    sem precisar de uma sala por par de usuários."""
    return f"user_{int(user_id)}"


def sala_servidor(server_id):
    """Sala de todos os membros conectados de um Servidor. Usada para coisas
    que só interessam a quem está no servidor (ex: posição no radar)."""
    return f"srv_{int(server_id)}"


_TEMP_ID_VALIDO = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


# Quem está numa call agora, pra mostrar uma prévia (tipo Discord) de quem já
# está na call ANTES de entrar - antes só quem já tinha entrado descobria
# quem mais estava lá, e só depois de entrar. Chave é a mesma string usada em
# sala_call ("<canal_id>" ou "dm_<menorId>_<maiorId>").
participantes_call = {}
# sid -> (chave_da_call, peer_id), só pra limpar certo se a conexão cair sem
# passar por sair_call (fechar o navegador manda sair_call via beforeunload,
# mas queda de rede não).
_call_por_sid = {}
# (chave, peer_id) -> {'sid', 'usuario_id', 'server_id'}: de quem é cada entrada de `participantes_call`. É o que
# deixa (a) uma pessoa estar em UMA call só (entrar numa nova tira ela da velha - o "fantasma em 3 calls"), (b) só o
# dono mexer na própria entrada e (c) limpar sem ir ao banco quando o socket cai.
_meta_call = {}
# (chave, peer_id) -> token. Socket que caiu NÃO sai da call na hora: fica uma graça pra reconectar (a mídia WebRTC
# segue viva, só a sinalização piscou). Se voltar com o mesmo peer_id, o token é invalidado e nada some.
_graca_call = {}
GRACA_CALL_SEGUNDOS = 12


def _destinos_da_call(chave, server_id):
    """Quem acompanha a prévia dessa call: os dois da DM, ou o servidor inteiro."""
    if isinstance(chave, str) and chave.startswith('dm_'):
        try:
            _, a, b = chave.split('_')
            return [sala_pessoal(int(a)), sala_pessoal(int(b))]
        except ValueError:
            return []
    return [sala_servidor(server_id)] if server_id else []


def _avisar_participantes(chave, server_id):
    payload = {'canal_id': chave, 'participantes': participantes_call.get(chave, [])}
    for sala in _destinos_da_call(chave, server_id):
        socketio.emit('participantes_call_mudou', payload, to=sala)


def _tirar_da_call(chave, peer_id, avisar=True):
    """Remove UMA entrada (e só ela) da call e avisa quem está dentro e quem só olha a prévia. Serve ao sair_call,
    ao fim da graça do disconnect e ao 'entrou em outra call'. Não depende de contexto de request."""
    meta = _meta_call.pop((chave, peer_id), None)
    _graca_call.pop((chave, peer_id), None)
    lista = participantes_call.get(chave)
    if lista is not None:
        lista[:] = [p for p in lista if p['peer_id'] != peer_id]
        if not lista:
            participantes_call.pop(chave, None)
    if meta and _call_por_sid.get(meta['sid']) == (chave, peer_id):
        _call_por_sid.pop(meta['sid'], None)
    if avisar:
        socketio.emit('usuario_saiu_call', {'peer_id': peer_id}, to=f"voz_{chave}")
        _avisar_participantes(chave, meta['server_id'] if meta else None)
    return meta


def _sair_apos_graca(chave, peer_id, token):
    socketio.sleep(GRACA_CALL_SEGUNDOS)
    if _graca_call.get((chave, peer_id)) is token:   # ninguém voltou com esse peer: saiu de verdade
        _tirar_da_call(chave, peer_id)


def _entrar_em_call(chave, peer_id, usuario, server_id=None):
    """Registra a entrada. Devolve True se é uma REENTRADA (mesmo peer voltando depois de uma queda do socket)."""
    chave_atual = (chave, peer_id)
    reentrada = chave_atual in _meta_call
    _graca_call.pop(chave_atual, None)

    # Uma pessoa só pode estar numa call: qualquer outra entrada dela (outra call, outra aba, peer velho de um F5)
    # sai agora. Antes cada socket só lembrava UMA call, e a anterior ficava pra sempre na lista de todo mundo.
    for (ch, pid), meta in list(_meta_call.items()):
        if meta['usuario_id'] != usuario.id or (ch, pid) == chave_atual:
            continue
        sid_velho = meta['sid']
        try:
            socketio.server.leave_room(sid_velho, f"voz_{ch}", namespace='/')
        except Exception:
            pass
        _tirar_da_call(ch, pid)
        if sid_velho != request.sid:
            socketio.emit('call_substituida', {'canal_id': ch, 'peer_id': pid}, to=sid_velho)

    # Se este socket tinha outra call registrada (troca direta de canal), ela sai também.
    anterior = _call_por_sid.get(request.sid)
    if anterior and anterior != chave_atual:
        try:
            leave_room(f"voz_{anterior[0]}")
        except Exception:
            pass
        _tirar_da_call(*anterior)

    lista = participantes_call.setdefault(chave, [])
    lista[:] = [p for p in lista if p['peer_id'] != peer_id]
    lista.append({'peer_id': peer_id, 'usuario_id': usuario.id, 'nome': usuario.name, 'avatar': usuario.avatar,
                  'moldura': usuario.moldura, 'nome_estilo': usuario.nome_estilo, 'equipados': equipados_da_pessoa(usuario)})
    _meta_call[chave_atual] = {'sid': request.sid, 'usuario_id': usuario.id, 'server_id': server_id}
    _call_por_sid[request.sid] = chave_atual
    return reentrada


def _sair_de_call(chave, peer_id):
    """Saída pedida pelo próprio cliente (sair_call). Só vale pra entrada que é dele."""
    meta = _meta_call.get((chave, peer_id))
    if meta and meta['sid'] != request.sid and meta['usuario_id'] != session.get('user_id'):
        return None
    return _tirar_da_call(chave, peer_id)


# Limites de texto: nome grande quebrava listas/sidebar (e o marquee rolava sem parar). O cliente usa os mesmos
# números em `maxlength` - mudou aqui, mude lá.
LIM_NOME_EXIBICAO = 24
LIM_USERNAME = 20
LIM_NOME_SERVIDOR = 100
LIM_NOME_CANAL = 32
LIM_NOTA = 140
LIM_STATUS = 25        # status personalizado
LIM_PENSANDO = 50      # "pensando agora"
LIM_PRONOMES = 15


def temp_id_seguro(dados):
    """Valida o temp_id que o cliente manda pra reconciliar a bolha otimista.

    Nunca ecoa de volta um valor cru do cliente pro resto do canal - um
    temp_id malicioso (aspas, colchetes) quebraria o querySelector no
    receber_mensagem de todo mundo que está no canal, não só de quem mandou.
    """
    valor = dados.get('temp_id')
    if isinstance(valor, str) and _TEMP_ID_VALIDO.match(valor):
        return valor
    return None


# ==========================================
# PRESENÇA: quem está com socket aberto agora
# ------------------------------------------------------------
# Em memória, não banco - é efêmero por natureza (reinicia zerado a cada
# deploy, o que é aceitável). Conta sockets por pessoa em vez de um booleano
# pra não "piscar" offline quando ela só fecha uma aba/dispositivo e continua
# conectada em outro.
# ==========================================
usuarios_conectados = {}


def esta_online(person_id):
    return usuarios_conectados.get(person_id, 0) > 0


def status_visivel(p):
    """Status que OS OUTROS enxergam: 'offline' se não está conectado OU se
    escolheu Invisível (senão Invisível só mudava a bolinha de quem escolheu)."""
    if not esta_online(p.id) or (p.status or 'online') == 'invisible':
        return 'offline'
    return p.status or 'online'


def texto_do_status(p):
    """Texto do status Personalizado (ex.: "Jogando Valorant"); só vale nesse modo."""
    return (p.custom_status or None) if (p.status or 'online') == 'custom' else None


def emoji_do_status(p):
    """Emoji que substitui a bolinha (só no status Personalizado)."""
    return (p.status_emoji or None) if (p.status or 'online') == 'custom' else None


def amigos_de(pessoa):
    """Lista de Person que são amizade aceita com `pessoa` (nos dois sentidos -
    quem pediu e quem recebeu viram "amigos" iguais depois do aceite)."""
    aceitas = Friendship.query.filter(
        Friendship.status == 'accepted',
        or_(Friendship.requester_id == pessoa.id, Friendship.addressee_id == pessoa.id)
    ).all()
    ids = [f.addressee_id if f.requester_id == pessoa.id else f.requester_id for f in aceitas]
    if not ids:
        return []
    return Person.query.filter(Person.id.in_(ids)).all()


def sao_amigos(id1, id2):
    return Friendship.query.filter(
        Friendship.status == 'accepted',
        or_(and_(Friendship.requester_id == id1, Friendship.addressee_id == id2),
            and_(Friendship.requester_id == id2, Friendship.addressee_id == id1))
    ).first() is not None


def sala_dm(id1, id2):
    """Sala de call 1-a-1, sempre com o menor id primeiro pra ficar igual dos
    dois lados sem precisar combinar quem liga pra quem."""
    a, b = sorted([int(id1), int(id2)])
    return f"dm_{a}_{b}"


def hora_formatada(ts):
    """Formata o timestamp de uma mensagem para exibição.

    `br_now()` já devolve horário de Brasília, então NÃO subtraia 3 horas aqui -
    isso era um bug antigo que fazia toda mensagem aparecer 3h no passado.
    """
    if ts is None:
        ts = br_now()
    return f"Hoje às {ts.strftime('%H:%M')}"


def canal_para_json(c):
    return {
        'id': c.id,
        'name': c.name,
        'type': c.channel_type,
        'topic': c.topic,
        'is_private': bool(c.is_private),
        'membros': [p.id for p in c.allowed_members] if c.is_private else []
    }


def _dados_de_servidores(servidores):
    """Canais, quem pode ver cada canal privado e contagem de membros de VÁRIOS servidores
    em 3 consultas no total (antes eram ~5 por servidor, e carregava todos os membros)."""
    servidores = list(servidores)
    ids = [s.id for s in servidores]
    if not ids:
        return {}, {}, {}
    canais = Channel.query.filter(Channel.server_id.in_(ids)).order_by(
        Channel.server_id.asc(), Channel.position.asc(), Channel.id.asc()).all()
    privados = [c.id for c in canais if c.is_private]
    permitidos = {}
    if privados:
        for cid, pid in db.session.query(channel_members.c.channel_id, channel_members.c.person_id).filter(
                channel_members.c.channel_id.in_(privados)).all():
            permitidos.setdefault(cid, set()).add(pid)
    contagem = dict(db.session.query(server_members.c.server_id, func.count(server_members.c.person_id)).filter(
        server_members.c.server_id.in_(ids)).group_by(server_members.c.server_id).all())
    return canais, permitidos, contagem


def _json_de_servidor(srv, dados, usuario=None):
    canais, permitidos, contagem = dados
    visiveis = []
    for c in canais:
        if c.server_id != srv.id:
            continue
        # mesma regra do pode_ver_canal para quem já é membro: canal privado só pro dono e convidados
        if usuario is not None and c.is_private and usuario.id != srv.owner_id and usuario.id not in permitidos.get(c.id, ()):
            continue
        visiveis.append({
            'id': c.id, 'name': c.name, 'type': c.channel_type, 'topic': c.topic,
            'is_private': bool(c.is_private),
            'membros': sorted(permitidos.get(c.id, ())) if c.is_private else []
        })
    return {
        'id': srv.id,
        'name': srv.name,
        'iconUrl': srv.icon_url,
        'description': srv.description,
        'bannerColor': srv.banner_color,
        'efeito': efeito_servidor_valido(srv.efeito),
        'owner_id': srv.owner_id,
        'membros': contagem.get(srv.id, 0),
        'channels': visiveis
    }


def servidores_para_json(servidores, usuario=None):
    """Vários servidores de uma vez (barra lateral, conexão). Canal privado só entra
    na lista de quem tem acesso; sem `usuario` devolve todos os canais (só pro dono)."""
    servidores = list(servidores)
    dados = _dados_de_servidores(servidores)
    return [_json_de_servidor(s, dados, usuario) for s in servidores]


def servidor_para_json(srv, usuario=None):
    """Servidor + canais. Canal privado só entra na lista de quem tem acesso.

    Sem o `usuario`, devolve todos os canais - use só quando o destinatário
    for o próprio dono.
    """
    return servidores_para_json([srv], usuario)[0]


def avisar_servidor(srv):
    """Reenvia o servidor inteiro para todos os membros conectados.

    Usado depois de qualquer mudança estrutural (nome, ícone, canais). Cada
    membro recebe a sua própria versão, porque a lista de canais depende de
    quais canais privados a pessoa pode ver.
    """
    dados = _dados_de_servidores([srv])
    for membro in srv.members:
        emit('servidor_discord_criado', _json_de_servidor(srv, dados, membro),
             to=sala_pessoal(membro.id))


# ==========================================
# MISSÕES: todo progresso passa por aqui
# ------------------------------------------------------------
# Nunca pode quebrar a ação que originou o evento (mandar mensagem, reagir...):
# se o banco falhar, só loga - a missão perde 1 ponto, a mensagem segue.
# ==========================================
_ultimo_batimento = {}   # user_id -> epoch do último batimento aceito


def _emitir_resultado(usuario, r):
    if not r:
        return
    sala = sala_pessoal(usuario.id)
    emit('missoes_atualizadas', r['missoes'], to=sala)
    for c in r['concluidas']:
        emit('missao_concluida', c, to=sala)
    if r['estado']:
        emit('xp_atualizado', r['estado'], to=sala)


def _emitir_progresso(usuario, eventos):
    try:
        _emitir_resultado(usuario, registrar_eventos(usuario, eventos))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MISSOES] {e}")


@socketio.on('batimento_atividade')
def batimento_atividade(dados=None):
    """O cliente manda 1x por minuto SÓ se a pessoa mexeu (mouse/teclado) com a
    aba visível. O servidor não confia nisso: limita a frequência e o XP diário."""
    usuario = usuario_logado()
    if not usuario:
        return

    agora = time.time()
    if agora - _ultimo_batimento.get(usuario.id, 0) < BATIMENTO_MIN_SEGUNDOS:
        return
    _ultimo_batimento[usuario.id] = agora

    try:
        _emitir_resultado(usuario, registrar_tempo_ativo(usuario, em_call=request.sid in _call_por_sid))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO BATIMENTO] {e}")


# ==========================================
# CONEXÃO: Carrega os servidores do usuário e entra na sala pessoal
# (para DMs em tempo real) e nas salas dos servidores dele.
# ==========================================
@socketio.on('garantir_salas')
def garantir_salas(dados=None):
    """Rede de segurança do connect: se o banco estava acordando quando o socket conectou, `handle_connect` desistiu
    antes de entrar nas salas (sem sala pessoal não chega toque de chamada, DM ao vivo, pedido de amizade...). O cliente
    chama isto quando não recebeu o 'versao_app' (a 1ª coisa que o connect completo manda)."""
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        join_room(sala_pessoal(usuario.id))
        for srv in list(usuario.servers):
            join_room(sala_servidor(srv.id))
        if usuario.id not in usuarios_conectados:
            usuarios_conectados[usuario.id] = 1
        emit('versao_app', {'versao': APP_VERSAO})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO GARANTIR SALAS] {e}")


@socketio.on('connect')
def handle_connect():
    usuario = usuario_logado()
    if not usuario and session.get('user_id'):
        # banco ainda acordando (Neon): tenta de novo antes de desistir, senão o socket fica sem salas
        for _ in range(3):
            socketio.sleep(1.2)
            usuario = usuario_logado()
            if usuario:
                break
    if not usuario:
        return

    emit('versao_app', {'versao': APP_VERSAO})

    try:
        join_room(sala_pessoal(usuario.id))

        meus_servidores = list(usuario.servers)
        servidores = servidores_para_json(meus_servidores, usuario)
        for srv in meus_servidores:
            join_room(sala_servidor(srv.id))

        emit('carregar_meus_servidores', servidores)

        emit('xp_atualizado', estado_battlepass(usuario))

        # Preferências que moram na conta (não no navegador): o cliente aplica
        # ao conectar, então valem em qualquer aparelho/rede.
        emit('preferencias_carregadas', {'ghost_mode': bool(usuario.ghost_mode), 'tema': usuario.tema or 'dark',
                                         'localizacao_ativa': localizacao_ligada(usuario),
                                         'localizacao_ip': usuario.localizacao_ip is not False})

        # Bônus diário: a primeira conexão do dia paga XP e mantém a sequência.
        # Em try próprio: falhar aqui não pode derrubar presença/amigos abaixo.
        try:
            bonus = conceder_bonus_diario(usuario)
            if bonus:
                emit('xp_atualizado', bonus)
                _emitir_progresso(usuario, {'login': 1})   # missão "abra o app em N dias"
        except Exception as e:
            db.session.rollback()
            print(f"[ERRO BONUS DIARIO] {e}")

        try:
            emit('missoes_atualizadas', missoes_do_usuario(usuario))
        except Exception as e:
            db.session.rollback()
            print(f"[ERRO MISSOES CONNECT] {e}")

        # Amizades (amigos, pedidos de 24h, bloqueados), DMs não lidas e caixa de entrada
        # já na conexão: a tela de Amigos e os badges nascem certos, em qualquer aparelho.
        # O retrato das amizades também serve pra avisar presença (abaixo): uma consulta só.
        snap_amizades = None
        try:
            snap_amizades = montar_amizades(usuario)
            emit('amizades', snap_amizades)
            emit('dms_nao_lidas', contagem_dms_nao_lidas(usuario))
            enviar_notificacoes(usuario)
        except Exception as e:
            db.session.rollback()
            print(f"[ERRO CONNECT SOCIAL] {e}")

        # Só avisa quem divide servidor com ela quando é o PRIMEIRO socket
        # dela (outra aba/dispositivo já conectado não deve gerar aviso de novo).
        era_offline = not esta_online(usuario.id)
        usuarios_conectados[usuario.id] = usuarios_conectados.get(usuario.id, 0) + 1
        amigos_snap = (snap_amizades or {}).get('amigos', [])
        if era_offline and (usuario.status or 'online') != 'invisible':
            aviso = {'usuario_id': usuario.id, 'status': usuario.status or 'online', 'emoji': emoji_do_status(usuario),
                     'texto': texto_do_status(usuario)}
            for srv in meus_servidores:
                emit('usuario_ficou_online', aviso, to=sala_servidor(srv.id), include_self=False)
            for a in amigos_snap:
                emit('usuario_ficou_online', aviso, to=sala_pessoal(a['id']))

        # Snapshot de quem já tá online agora, pra corrigir a lista de amigos
        # que a página carregou "todo mundo offline" por padrão. Quem está
        # Invisível fica de fora (e o status de cada um vai junto).
        on = [a for a in amigos_snap if a['online']]
        emit('status_amigos_ao_conectar', {
            'online_ids': [a['id'] for a in on],
            'status_por_id': {str(a['id']): a['status'] for a in on},
            'emoji_por_id': {str(a['id']): a['emoji'] for a in on if a['emoji']},
            'texto_por_id': {str(a['id']): a['status_texto'] for a in on if a['status_texto']}
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CONNECT] {e}")


@socketio.on('disconnect')
def handle_disconnect():
    # Queda de rede/aba fechada à força não passa por sair_call (só o
    # beforeunload do navegador manda isso, e ele nem sempre roda a tempo) -
    # sem isso, quem caiu ficava "fantasma" na prévia de participantes da
    # call pro resto da sessão de todo mundo.
    centros_mapa.pop(request.sid, None)
    call_info = _call_por_sid.pop(request.sid, None)
    if call_info and _meta_call.get(call_info, {}).get('sid') == request.sid:
        # Não tira da call na hora: o socket costuma só piscar (Render, troca de rede) e a mídia WebRTC segue viva.
        # Se o cliente voltar com o mesmo peer_id dentro da graça, nada some; senão sai de verdade.
        token = object()
        _graca_call[call_info] = token
        socketio.start_background_task(_sair_apos_graca, call_info[0], call_info[1], token)
    # Ligação tocando que eu fiz e ninguém atendeu: avisa quem estava recebendo que eu sumi.
    for de_para, info in list(_chamadas_pendentes.items()):
        if info['sid'] == request.sid:
            _chamadas_pendentes.pop(de_para, None)
            emit('chamada_cancelada', {}, to=sala_pessoal(de_para[1]))

    usuario = usuario_logado()
    if not usuario or usuario.id not in usuarios_conectados:
        return

    try:
        usuarios_conectados[usuario.id] -= 1
        if usuarios_conectados[usuario.id] <= 0:
            del usuarios_conectados[usuario.id]
            if ultimas_posicoes.pop(usuario.id, None):
                for sala in _salas_da_posicao(usuario):
                    emit('posicao_amigo_removida', {'usuario_id': usuario.id}, to=sala)
            for srv in usuario.servers:
                emit('usuario_ficou_offline', {'usuario_id': usuario.id}, to=sala_servidor(srv.id), include_self=False)
            for amigo in amigos_de(usuario):
                emit('usuario_ficou_offline', {'usuario_id': usuario.id}, to=sala_pessoal(amigo.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO DISCONNECT] {e}")


@socketio.on('entrar_canal')
def handle_join(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    canal = canal_permitido(usuario, dados.get('canal_id'))
    if not canal:
        emit('erro_bazinga', {'msg': 'Você não tem acesso a esse canal.'})
        return

    join_room(str(canal.id))


@socketio.on('sair_canal')
def handle_leave(dados):
    canal_id = dados.get('canal_id')
    if canal_id is not None:
        leave_room(str(canal_id))


_RE_MENCAO = re.compile(r'<@(\d{1,10})>')


def _notificar_mencoes(autor, canal, msg):
    """Avisa quem foi citado (`<@id>` no texto). Só vale pra quem é membro do
    servidor E enxerga o canal - citar não pode vazar canal privado nem
    "chamar" quem não tem acesso. Nunca quebra o envio da mensagem."""
    try:
        ids = {int(i) for i in _RE_MENCAO.findall(msg.text or '')}
        ids.discard(autor.id)
        if not ids or canal.server_id is None:
            return
        srv = Server.query.get(canal.server_id)
        alvos = Person.query.filter(Person.id.in_(list(ids)[:10])).all()
        nomes = {p.id: p.name for p in alvos}
        trecho = _RE_MENCAO.sub(lambda m: '@' + nomes.get(int(m.group(1)), 'alguém'), msg.text or '')[:140]
        for alvo in alvos:
            if alvo in srv.members and pode_ver_canal(alvo, canal):
                emit('mencao_recebida', {
                    'canal_id': canal.id, 'canal_nome': canal.name, 'server_id': canal.server_id,
                    'autor': autor.name, 'trecho': trecho, 'msg_id': msg.id
                }, to=sala_pessoal(alvo.id))
                criar_notificacao(alvo.id, 'mencao', f'{autor.name} te citou em #{canal.name}', trecho,
                                  de_id=autor.id, ref=f'{canal.server_id}:{canal.id}')
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MENCOES] {e}")


@socketio.on('enviar_mensagem')
def lidar_com_mensagem(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    canal = canal_permitido(usuario, dados.get('canal_id'))
    if not canal:
        emit('erro_bazinga', {'msg': 'Você não tem acesso a esse canal.'})
        return

    texto = (dados.get('texto') or '').strip()[:2000]

    # Anexo (foto/vídeo/gif) já subiu por /api/upload e chega aqui só como URL.
    # GIF escolhido no painel de busca (/api/gifs) manda direto o link do
    # CDN do Giphy, sem passar pelo upload - por isso o domínio deles também
    # entra na lista de permitidos.
    anexo_url = dados.get('anexo_url')
    anexo_tipo = dados.get('anexo_tipo') if dados.get('anexo_tipo') in ('image', 'video') else None
    anexo_nome = (dados.get('anexo_nome') or '').strip()[:255] or None
    anexo_url_str = str(anexo_url) if anexo_url else ''
    if anexo_url and not (
        anexo_url_str.startswith('/')
        or anexo_url_str.startswith('https://res.cloudinary.com/')
        or re.match(r'^https://media\d*\.giphy\.com/', anexo_url_str)
    ):
        anexo_url = None  # só aceita caminho do próprio site, Cloudinary ou Giphy
    if not anexo_url:
        anexo_tipo = anexo_nome = None

    # Mensagem vazia sem anexo não vale
    if not texto and not anexo_url:
        return

    try:
        def preparar():
            nova = Message(text=texto or None, person_id=usuario.id, channel_id=canal.id,
                           attachment_url=anexo_url, attachment_type=anexo_tipo,
                           attachment_name=anexo_nome)
            db.session.add(nova)
            return nova

        nova_msg = comitar_com_retry(preparar)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CHAT GERAL] Não foi possível salvar: {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível enviar a mensagem: {e}'})
        return

    cor = usuario.role.color if usuario.role else '#23a559'

    payload_msg = {
        'id': nova_msg.id,
        'canal_id': canal.id,
        'usuario': usuario.name,
        'usuario_id': usuario.id,
        'avatar': usuario.avatar,
        'nome_estilo': usuario.nome_estilo, 'moldura': usuario.moldura, 'equipados': equipados_da_pessoa(usuario),
        'texto': nova_msg.text or '',
        'anexo_url': nova_msg.attachment_url,
        'anexo_tipo': nova_msg.attachment_type,
        'anexo_nome': nova_msg.attachment_name,
        'hora': hora_formatada(nova_msg.timestamp),
        'cor': cor,
        # Ecoa de volta pra quem mandou trocar a bolha otimista pela real
        # sem duplicar (ver enviarMensagemOtimista() no chat.html).
        'temp_id': temp_id_seguro(dados)
    }
    emit('receber_mensagem', payload_msg, to=str(canal.id))
    # Quem mandou recebe a confirmação mesmo que o socket dele tenha saído da sala do canal
    # (reconexão, troca de aba): sem isso a bolha ficava "pendente" até o F5. O cliente
    # ignora a repetição pelo id da mensagem.
    emit('receber_mensagem', payload_msg, to=request.sid)

    # Battle Pass: XP por mensagem (com cooldown - ver conceder_xp_por_mensagem).
    # Só pra quem mandou, não pra sala inteira - ninguém mais precisa saber.
    resultado_xp = conceder_xp_por_mensagem(usuario)
    if resultado_xp:
        emit('xp_atualizado', resultado_xp, to=sala_pessoal(usuario.id))
    _emitir_progresso(usuario, {'mensagem': 1})
    _notificar_mencoes(usuario, canal, nova_msg)


@socketio.on('editar_mensagem')
def editar_mensagem(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        msg = com_retry(lambda: Message.query.get(dados.get('msg_id')))
        if not msg:
            return

        canal = Channel.query.get(msg.channel_id)
        if not pode_ver_canal(usuario, canal):
            return

        # Editar é só do autor - nem o dono do servidor pode reescrever
        # o que outra pessoa disse (apagar ele pode).
        if msg.person_id != usuario.id:
            emit('erro_bazinga', {'msg': 'Você só pode editar as suas próprias mensagens.'})
            return

        texto = (dados.get('texto') or '').strip()[:2000]
        if not texto and not msg.attachment_url:
            return

        def preparar():
            msg.text = texto or None
            msg.edited_at = br_now()

        comitar_com_retry(preparar)

        emit('mensagem_editada', {
            'msg_id': msg.id,
            'texto': msg.text or '',
            'editada': True
        }, to=str(msg.channel_id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EDITAR MENSAGEM] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível editar a mensagem: {e}'})


# ==========================================
# REAÇÕES DE EMOJI
# ==========================================
def reacoes_para_json(msg_id):
    """Agrupa as reações de uma mensagem em {emoji, total, quem}."""
    agrupado = {}
    for r in Reaction.query.filter_by(message_id=msg_id).all():
        item = agrupado.setdefault(r.emoji, {'emoji': r.emoji, 'total': 0, 'quem': []})
        item['total'] += 1
        item['quem'].append(r.person_id)
    return list(agrupado.values())


@socketio.on('reagir_mensagem')
def reagir_mensagem(dados):
    """Liga/desliga a reação: se a pessoa já reagiu com aquele emoji, remove."""
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        msg = com_retry(lambda: Message.query.get(dados.get('msg_id')))
        if not msg:
            return

        canal = Channel.query.get(msg.channel_id)
        if not pode_ver_canal(usuario, canal):
            return

        emoji = (dados.get('emoji') or '').strip()[:16]
        if not emoji:
            return

        adicionou = []

        def preparar():
            adicionou.clear()
            existente = Reaction.query.filter_by(
                message_id=msg.id, person_id=usuario.id, emoji=emoji).first()
            if existente:
                db.session.delete(existente)
            else:
                db.session.add(Reaction(message_id=msg.id, person_id=usuario.id, emoji=emoji))
                adicionou.append(1)

        comitar_com_retry(preparar)

        # Primeiro mostra a reação pra todo mundo; o XP/missão (várias queries) vem depois e nunca atrasa a tela.
        emit('reacoes_atualizadas', {
            'msg_id': msg.id,
            'reacoes': reacoes_para_json(msg.id)
        }, to=str(msg.channel_id))
        if adicionou:   # tirar a reação não conta (senão ligar/desligar viraria XP)
            _emitir_progresso(usuario, {'reacao': 1})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO REAGIR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível reagir: {e}'})


@socketio.on('apagar_mensagem')
def lidar_com_exclusao(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        msg = com_retry(lambda: Message.query.get(dados.get('msg_id')))
        if not msg:
            return

        canal = Channel.query.get(msg.channel_id)
        if not pode_ver_canal(usuario, canal):
            return

        # Pode apagar quem escreveu a mensagem ou o dono do servidor do canal.
        dono_do_servidor = False
        if canal.server_id is not None:
            servidor = Server.query.get(canal.server_id)
            dono_do_servidor = servidor is not None and servidor.owner_id == usuario.id

        if msg.person_id != usuario.id and not dono_do_servidor:
            emit('erro_bazinga', {'msg': 'Você só pode apagar as suas próprias mensagens.'})
            return

        msg_id = msg.id
        canal_id = str(msg.channel_id)

        def preparar():
            db.session.delete(msg)

        comitar_com_retry(preparar)
        emit('mensagem_apagada', {'msg_id': msg_id}, to=canal_id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO AO APAGAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar a mensagem: {e}'})


@socketio.on('fixar_mensagem')
def fixar_mensagem(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        msg = com_retry(lambda: Message.query.get(dados.get('msg_id')))
        if not msg:
            return

        canal = Channel.query.get(msg.channel_id)
        if not pode_ver_canal(usuario, canal):
            return

        nova_fixada = not msg.is_pinned

        def preparar():
            msg.is_pinned = nova_fixada

        comitar_com_retry(preparar)
        emit('mensagem_fixada', {'msg_id': msg.id, 'fixada': nova_fixada}, to=str(msg.channel_id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO FIXAR MENSAGEM] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível fixar a mensagem: {e}'})


@socketio.on('listar_fixadas')
def listar_fixadas(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        canal_id = dados.get('canal_id')
        canal = Channel.query.get(canal_id)
        if not canal or not pode_ver_canal(usuario, canal):
            return

        fixadas = com_retry(lambda: Message.query.filter_by(
            channel_id=canal_id, is_pinned=True)
            .options(joinedload(Message.author))
            .order_by(Message.timestamp.desc()).all())

        emit('fixadas_do_canal', {
            'canal_id': canal_id,
            'mensagens': [{
                'id': m.id, 'autor': m.author.name, 'avatar': m.author.avatar,
                'texto': m.text or '', 'anexo_url': m.attachment_url, 'anexo_tipo': m.attachment_type
            } for m in fixadas]
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LISTAR FIXADAS] {e}")


@socketio.on('entrar_call')
def lidar_entrar_call(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    peer_id = dados.get('peer_id')
    if not peer_id or not isinstance(peer_id, str) or len(peer_id) > 80:
        return

    canal_id_bruto = dados.get('canal_id')

    try:
        # Chamada 1-a-1 por DM: a "sala" é "dm_<menorId>_<maiorId>", não um
        # Channel de verdade - checa amizade em vez de canal_permitido.
        server_id = None
        if isinstance(canal_id_bruto, str) and canal_id_bruto.startswith('dm_'):
            try:
                _, id_a, id_b = canal_id_bruto.split('_')
                id_a, id_b = int(id_a), int(id_b)
            except ValueError:
                return
            if usuario.id not in (id_a, id_b):
                return
            outro_id = id_b if usuario.id == id_a else id_a
            if not sao_amigos(usuario.id, outro_id):
                return
            chave = canal_id_bruto
        else:
            canal = canal_permitido(usuario, canal_id_bruto)
            if not canal:
                emit('erro_bazinga', {'msg': 'Você não tem acesso a esse canal de voz.'})
                return
            chave = str(canal.id)
            server_id = canal.server_id

        sala_call = f"voz_{chave}"
        join_room(sala_call)
        reentrada = _entrar_em_call(chave, peer_id, usuario, server_id)

        # Quem já está na call liga pra quem chegou (só quem JÁ estava dentro disca). Na reentrada (o socket piscou) o
        # aviso vai de novo: o cliente só refaz a ligação se a antiga morreu de verdade.
        emit('novo_usuario_call', {
            'peer_id': peer_id, 'usuario': usuario.name, 'avatar': usuario.avatar,
            'moldura': usuario.moldura, 'nome_estilo': usuario.nome_estilo, 'equipados': equipados_da_pessoa(usuario),
            'canal_id': chave, 'reentrada': reentrada
        }, to=sala_call, include_self=False)

        # Prévia pra quem está com o servidor/DM aberto mas ainda não entrou, e a lista oficial pra quem chegou
        # (o cliente usa pra limpar card de gente que já saiu e pra pedir a ligação de quem não conectou).
        _avisar_participantes(chave, server_id)
        emit('participantes_call_mudou', {'canal_id': chave, 'participantes': participantes_call.get(chave, [])})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ENTRAR CALL] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível entrar na call: {e}'})


@socketio.on('pedir_ligacao')
def lidar_pedir_ligacao(dados):
    """Quem entrou e não conseguiu conectar com alguém que está na lista pede pra ESSA pessoa ligar de novo. Só a
    pessoa que já estava dentro disca (o PeerJS não renegocia), então o pedido passa pelo servidor."""
    usuario = usuario_logado()
    if not usuario:
        return
    canal_id = (dados or {}).get('canal_id')
    alvo_peer = (dados or {}).get('peer_id')
    if canal_id is None or not alvo_peer:
        return
    chave = canal_id if (isinstance(canal_id, str) and canal_id.startswith('dm_')) else str(canal_id)
    meu = _call_por_sid.get(request.sid)
    if not meu or meu[0] != chave:
        return
    alvo = _meta_call.get((chave, alvo_peer))
    if not alvo:
        return
    eu = next((p for p in participantes_call.get(chave, []) if p['peer_id'] == meu[1]), None)
    if not eu:
        return
    socketio.emit('novo_usuario_call', {
        'peer_id': eu['peer_id'], 'usuario': eu['nome'], 'avatar': eu['avatar'], 'moldura': eu.get('moldura'),
        'nome_estilo': eu.get('nome_estilo'), 'equipados': eu.get('equipados') or {}, 'canal_id': chave,
        'reentrada': True
    }, to=alvo['sid'])


@socketio.on('listar_participantes_call')
def listar_participantes_call(dados):
    """Prévia sob demanda: chamado ao abrir um servidor/DM, sem esperar
    alguém entrar ou sair de uma call pra saber quem já está nela."""
    usuario = usuario_logado()
    if not usuario:
        return

    canal_id_bruto = dados.get('canal_id')
    try:
        if isinstance(canal_id_bruto, str) and canal_id_bruto.startswith('dm_'):
            try:
                _, id_a, id_b = canal_id_bruto.split('_')
                id_a, id_b = int(id_a), int(id_b)
            except ValueError:
                return
            if usuario.id not in (id_a, id_b):
                return
            chave = canal_id_bruto
        else:
            canal = canal_permitido(usuario, canal_id_bruto)
            if not canal:
                return
            chave = str(canal.id)

        emit('participantes_call_mudou', {'canal_id': chave, 'participantes': participantes_call.get(chave, [])})
    except Exception as e:
        db.session.rollback()
        # Sem toast aqui de propósito - isso roda em silêncio ao abrir um
        # servidor, pra cada canal de voz. Um erro pontual não deve encher a
        # tela de toast vermelho; só a prévia daquele canal fica vazia até a
        # próxima tentativa (entrar/sair de alguém dispara de novo).
        print(f"[ERRO LISTAR PARTICIPANTES CALL] {e}")


@socketio.on('sair_call')
def lidar_sair_call(dados):
    canal_id = dados.get('canal_id')
    peer_id = dados.get('peer_id')
    if canal_id is None:
        return

    chave = str(canal_id) if not (isinstance(canal_id, str) and canal_id.startswith('dm_')) else canal_id
    sala_call = f"voz_{chave}"
    leave_room(sala_call)
    if peer_id:
        _sair_de_call(chave, peer_id)
    else:
        # sem peer_id (saiu antes do PeerJS abrir): tira o que este socket tinha nessa call
        atual = _call_por_sid.get(request.sid)
        if atual and atual[0] == chave:
            _tirar_da_call(*atual)


# ==========================================
# CHAMADA 1-A-1 POR DM (toque + aceitar, igual Discord)
# ------------------------------------------------------------
# Só o "toque": avisa o amigo e espera ele aceitar/recusar. A call em si (depois
# de aceita) reaproveita entrar_call/sair_call de cima, com canal_id no formato
# "dm_<menorId>_<maiorId>" (ver sala_dm()).
#
# `_chamadas_pendentes[(quem_ligou, quem_recebe)] = {'sid', 'ts', 'tipo'}` guarda de QUAL aba saiu a ligação: o
# `chamada_aceita` volta só pra essa aba (antes ia pra todas as abas de quem ligou, e cada uma entrava na call -
# era a "pessoa duplicada" na chamada). As outras abas de quem recebia também fecham o toque quando uma atende.
# ==========================================
_chamadas_pendentes = {}
CHAMADA_VALE_SEGUNDOS = 60


def _limpar_chamadas_velhas():
    agora = time.time()
    for k, v in list(_chamadas_pendentes.items()):
        if agora - v['ts'] > CHAMADA_VALE_SEGUNDOS:
            _chamadas_pendentes.pop(k, None)


@socketio.on('chamar_amigo')
def chamar_amigo(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        amigo_id = int(dados.get('amigo_id'))
    except (TypeError, ValueError):
        return

    tipo = dados.get('tipo') if dados.get('tipo') in ('voz', 'video') else 'voz'

    if not sao_amigos(usuario.id, amigo_id):
        emit('erro_bazinga', {'msg': 'Vocês precisam ser amigos pra poder se ligar.'})
        return

    # Antes quem ligava ficava "chamando..." pra sempre se a outra pessoa estivesse offline.
    if not esta_online(amigo_id):
        emit('chamada_recusada', {'por_nome': 'A pessoa', 'offline': True})
        return

    _limpar_chamadas_velhas()
    _chamadas_pendentes[(usuario.id, amigo_id)] = {'sid': request.sid, 'ts': time.time(), 'tipo': tipo}
    emit('chamada_recebida', {
        'de_id': usuario.id, 'de_nome': usuario.name, 'de_avatar': usuario.avatar, 'tipo': tipo
    }, to=sala_pessoal(amigo_id))


@socketio.on('aceitar_chamada')
def aceitar_chamada(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        de_id = int(dados.get('de_id'))
    except (TypeError, ValueError):
        return

    info = _chamadas_pendentes.pop((de_id, usuario.id), None)
    if not info:
        # já foi atendida em outra aba, cancelada ou expirou: não entra em call nenhuma
        emit('chamada_resolvida', {})
        return

    sala = sala_dm(usuario.id, de_id)
    tipo = info.get('tipo', 'voz')
    # Quem atendeu (esta aba) e quem ligou (a aba de onde saiu a ligação). As outras abas só fecham o toque.
    emit('chamada_aceita', {'com_id': de_id, 'sala': sala, 'tipo': tipo})
    emit('chamada_aceita', {'com_id': usuario.id, 'sala': sala, 'tipo': tipo}, to=info['sid'])
    emit('chamada_resolvida', {}, to=sala_pessoal(usuario.id), include_self=False)


@socketio.on('recusar_chamada')
def recusar_chamada(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        de_id = int(dados.get('de_id'))
    except (TypeError, ValueError):
        return
    info = _chamadas_pendentes.pop((de_id, usuario.id), None)
    emit('chamada_recusada', {'por_nome': usuario.name}, to=(info['sid'] if info else sala_pessoal(de_id)))
    emit('chamada_resolvida', {}, to=sala_pessoal(usuario.id), include_self=False)


@socketio.on('cancelar_chamada')
def cancelar_chamada(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        para_id = int(dados.get('para_id'))
    except (TypeError, ValueError):
        return
    _chamadas_pendentes.pop((usuario.id, para_id), None)
    emit('chamada_cancelada', {}, to=sala_pessoal(para_id))


@socketio.on('estado_camera')
def lidar_estado_camera(dados):
    """Câmera ligou/desligou: avisa a sala da call pra mostrar o vídeo ou o avatar. Antes o outro lado dependia do
    evento `mute` do WebRTC, que no navegador demora (ou nunca vem) quando a faixa é trocada por null."""
    usuario = usuario_logado()
    if not usuario:
        return
    canal_id = dados.get('canal_id')
    peer_id = dados.get('peer_id')
    if canal_id is None or not peer_id:
        return
    chave = canal_id if (isinstance(canal_id, str) and canal_id.startswith('dm_')) else str(canal_id)
    # Só quem está de verdade nessa call (com esse peer_id) pode mexer no estado dela.
    if not any(p.get('peer_id') == peer_id and p.get('usuario_id') == usuario.id for p in participantes_call.get(chave, [])):
        return
    emit('estado_camera', {'peer_id': peer_id, 'ligada': bool(dados.get('ligada'))},
         to=f"voz_{chave}", include_self=False)


# Só avisa quem mais está na call - não grava nada no servidor. A gravação em
# si acontece 100% no navegador de quem clicou (ver iniciarGravacao no chat.html).
@socketio.on('iniciar_gravacao')
def lidar_iniciar_gravacao(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    canal = canal_permitido(usuario, dados.get('canal_id'))
    if not canal:
        return
    emit('usuario_gravando', {'usuario': usuario.name}, to=f"voz_{canal.id}", include_self=False)


@socketio.on('parar_gravacao')
def lidar_parar_gravacao(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    canal = canal_permitido(usuario, dados.get('canal_id'))
    if not canal:
        return
    emit('usuario_parou_gravacao', {'usuario': usuario.name}, to=f"voz_{canal.id}", include_self=False)


# ==========================================
# SERVIDORES BAZINGA (Criar / Criar Canal / Entrar por Pino do Mapa)
# ==========================================
@socketio.on('criar_servidor_discord')
def criar_servidor(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        nome = (dados.get('nome') or f"Servidor de {usuario.name}").strip()[:LIM_NOME_SERVIDOR]
        icon_url = dados.get('icon_url')
        # Um blob: local do navegador não sobrevive fora da aba que o criou.
        if icon_url and icon_url.startswith('blob:'):
            icon_url = None

        def preparar():
            novo_srv = Server(name=nome, owner_id=usuario.id, icon_url=icon_url)
            novo_srv.members.append(usuario)
            db.session.add(novo_srv)
            db.session.flush()  # gera o novo_srv.id sem precisar comitar ainda

            db.session.add(Channel(name="geral", channel_type="text", server_id=novo_srv.id))
            db.session.add(Channel(name="Geral", channel_type="voice", server_id=novo_srv.id))
            return novo_srv

        novo_srv = comitar_com_retry(preparar)
        join_room(sala_servidor(novo_srv.id))
        emit('servidor_discord_criado', servidor_para_json(novo_srv, usuario))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRIAR SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível criar o servidor: {e}'})


@socketio.on('criar_canal')
def criar_canal(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        server_id = int(dados.get('server_id'))
        nome = (dados.get('nome') or '').strip().lower().replace(' ', '-')[:LIM_NOME_CANAL]
        tipo = 'voice' if dados.get('tipo') == 'voice' else 'text'
        if not nome:
            return

        srv = com_retry(lambda: Server.query.get(server_id))
        if not srv or srv.owner_id != usuario.id:
            emit('erro_bazinga', {'msg': 'Só o dono do servidor pode criar canais (por enquanto).'})
            return

        topico = (dados.get('topico') or '').strip()[:255] or None
        privado = bool(dados.get('privado'))
        escolhidos = _membros_escolhidos(srv, dados.get('membros'))

        def preparar():
            ultimo = Channel.query.filter_by(server_id=srv.id).count()
            novo = Channel(name=nome, channel_type=tipo, server_id=srv.id,
                           topic=topico, is_private=privado, position=ultimo)
            if privado:
                novo.allowed_members = escolhidos
            db.session.add(novo)
            return novo

        novo_canal = comitar_com_retry(preparar)

        # Canal privado não pode ser anunciado pra sala inteira do servidor -
        # quem não tem acesso nem deve saber que ele existe.
        _anunciar_canal('canal_criado', srv, novo_canal)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRIAR CANAL] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível criar o canal: {e}'})


def _membros_escolhidos(srv, ids):
    """Converte a lista de ids que veio do cliente em Persons.

    Só aceita quem já é membro do servidor - senão dava pra "adicionar"
    qualquer usuário do banco a um canal mandando um id qualquer.
    """
    if not ids:
        return []
    try:
        pedidos = {int(i) for i in ids}
    except (TypeError, ValueError):
        return []
    return [p for p in srv.members if p.id in pedidos]


def _anunciar_canal(evento, srv, canal):
    """Manda o canal só pra quem pode vê-lo.

    Canal privado não pode ir pra sala do servidor inteiro: quem não tem
    acesso nem deveria saber que ele existe.
    """
    payload = canal_para_json(canal)
    payload['server_id'] = srv.id
    for membro in srv.members:
        if pode_ver_canal(membro, canal):
            emit(evento, payload, to=sala_pessoal(membro.id))


@socketio.on('listar_membros_servidor')
def listar_membros_servidor(dados):
    """Lista de membros, pra montar o seletor de quem entra num canal privado."""
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = com_retry(lambda: Server.query.get(int(dados.get('server_id'))))
        if not srv or usuario not in srv.members:
            return

        emit('membros_do_servidor', {
            'server_id': srv.id,
            'membros': [{
                'id': m.id, 'nome': m.name, 'avatar': m.avatar,
                'dono': m.id == srv.owner_id,
                # Pra mim mesmo vale o status real; pros outros, o que eles
                # escolheram mostrar (Invisível aparece como offline).
                'status': (m.status or 'online') if m.id == usuario.id else status_visivel(m),
                'online': True if m.id == usuario.id else status_visivel(m) != 'offline',
                'emoji': emoji_do_status(m), 'status_texto': texto_do_status(m),
                'pensando': m.pensando, 'username': m.username,
                'placa': m.placa, 'nome_estilo': m.nome_estilo
            } for m in srv.members]
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LISTAR MEMBROS] {e}")


@socketio.on('editar_canal')
def editar_canal(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        canal = com_retry(lambda: Channel.query.get(dados.get('canal_id')))
        if not canal or canal.server_id is None:
            return

        srv = servidor_gerenciavel(usuario, canal.server_id)
        if not srv:
            emit('erro_bazinga', {'msg': 'Só o dono do servidor pode editar canais.'})
            return

        # Quem via o canal ANTES da mudança: se ele virar privado (ou alguém
        # for removido), essas pessoas precisam ser avisadas que o canal sumiu.
        viam_antes = {m.id for m in srv.members if pode_ver_canal(m, canal)}

        def preparar():
            if 'nome' in dados:
                nome = (dados.get('nome') or '').strip().lower().replace(' ', '-')[:LIM_NOME_CANAL]
                if nome:
                    canal.name = nome
            if 'topico' in dados:
                canal.topic = (dados.get('topico') or '').strip()[:255] or None
            if 'privado' in dados:
                canal.is_private = bool(dados.get('privado'))
            if 'membros' in dados or 'privado' in dados:
                canal.allowed_members = (_membros_escolhidos(srv, dados.get('membros'))
                                         if canal.is_private else [])

        comitar_com_retry(preparar)

        _anunciar_canal('canal_editado', srv, canal)

        # Pra quem perdeu o acesso, o canal simplesmente desaparece da lista.
        for membro in srv.members:
            if membro.id in viam_antes and not pode_ver_canal(membro, canal):
                emit('canal_apagado', {'server_id': srv.id, 'canal_id': canal.id},
                     to=sala_pessoal(membro.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EDITAR CANAL] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível editar o canal: {e}'})


@socketio.on('apagar_canal')
def apagar_canal(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        canal = com_retry(lambda: Channel.query.get(dados.get('canal_id')))
        if not canal or canal.server_id is None:
            return

        srv = servidor_gerenciavel(usuario, canal.server_id)
        if not srv:
            emit('erro_bazinga', {'msg': 'Só o dono do servidor pode apagar canais.'})
            return

        # Não deixa o servidor ficar sem nenhum canal de texto.
        if canal.channel_type == 'text':
            restantes = Channel.query.filter_by(server_id=srv.id, channel_type='text').count()
            if restantes <= 1:
                emit('erro_bazinga', {'msg': 'O servidor precisa de pelo menos um canal de texto.'})
                return

        canal_id = canal.id

        def preparar():
            db.session.delete(canal)  # as mensagens somem junto (cascade)

        comitar_com_retry(preparar)
        emit('canal_apagado', {'server_id': srv.id, 'canal_id': canal_id},
             to=sala_servidor(srv.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR CANAL] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar o canal: {e}'})


# ==========================================
# CONFIGURAÇÕES DO SERVIDOR
# ==========================================
@socketio.on('editar_servidor')
def editar_servidor(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = servidor_gerenciavel(usuario, dados.get('server_id'))
        if not srv:
            emit('erro_bazinga', {'msg': 'Só o dono pode mexer nas configurações do servidor.'})
            return

        def preparar():
            if 'nome' in dados:
                nome = (dados.get('nome') or '').strip()[:LIM_NOME_SERVIDOR]
                if nome:
                    srv.name = nome
            if 'descricao' in dados:
                srv.description = (dados.get('descricao') or '').strip()[:1000] or None
            if 'banner_color' in dados:
                srv.banner_color = dados.get('banner_color') or None
            if 'icon_url' in dados:
                icone = dados.get('icon_url')
                # blob: só existe na aba que criou - nunca salvar isso no banco.
                if icone and not str(icone).startswith('blob:'):
                    srv.icon_url = icone
                elif icone == '':
                    srv.icon_url = None  # removeu a foto

        comitar_com_retry(preparar)
        avisar_servidor(srv)

        # O pino no mapa mostra o nome e a foto do servidor, então precisa
        # acompanhar a mudança - antes só atualizava depois de dar F5.
        pino = MapServer.query.filter_by(server_id=srv.id).first()
        if pino:
            emit('servidor_mapa_editado', {
                'id': pino.id,
                'nome': srv.name,
                'icon_url': srv.icon_url,
                'efeito': efeito_servidor_valido(srv.efeito),
                'vagas': pino.max_tickets if pino.max_tickets else 'ilimitado',
                'online': len(srv.members)
            }, broadcast=True)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EDITAR SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar o servidor: {e}'})


@socketio.on('aplicar_efeito_servidor')
def aplicar_efeito_servidor(dados):
    """O dono aplica (ou tira, com valor vazio) um efeito cosmético do inventário num servidor dele.

    Duas checagens no servidor (regra 4): a pessoa administra o servidor E possui o item. Depois, todos os
    membros recebem o servidor de novo (`avisar_servidor`) e o pino do mapa é atualizado (regra 6)."""
    usuario = usuario_logado()
    if not usuario:
        return
    dados = dados or {}

    try:
        srv = servidor_gerenciavel(usuario, dados.get('server_id'))
        if not srv:
            emit('erro_bazinga', {'msg': 'Só o dono pode mexer nos efeitos do servidor.'})
            return
        valor = (dados.get('valor') or '').strip()
        if valor:
            if not efeito_servidor_valido(valor):
                emit('erro_bazinga', {'msg': 'Efeito de servidor inválido.'})
                return
            if f'efeito_servidor:{valor}' not in com_retry(lambda: posses_da_pessoa(usuario.id)):
                emit('erro_bazinga', {'msg': 'Você ainda não tem esse efeito.'})
                return

        def preparar():
            srv.efeito = valor or None

        comitar_com_retry(preparar)
        avisar_servidor(srv)
        pino = MapServer.query.filter_by(server_id=srv.id).first()
        if pino:
            emit('servidor_mapa_editado', {
                'id': pino.id, 'nome': srv.name, 'icon_url': srv.icon_url,
                'efeito': efeito_servidor_valido(srv.efeito),
                'vagas': pino.max_tickets if pino.max_tickets else 'ilimitado', 'online': len(srv.members)
            }, broadcast=True)
        emit('efeito_servidor_aplicado', {'server_id': srv.id, 'efeito': efeito_servidor_valido(srv.efeito)})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EFEITO SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível aplicar o efeito: {e}'})


@socketio.on('apagar_servidor')
def apagar_servidor(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = servidor_gerenciavel(usuario, dados.get('server_id'))
        if not srv:
            emit('erro_bazinga', {'msg': 'Só o dono pode apagar o servidor.'})
            return

        server_id = srv.id

        def preparar():
            # O pino no mapa aponta pro servidor; some junto pra não ficar
            # um marcador levando a um servidor que não existe mais.
            MapServer.query.filter_by(server_id=server_id).delete()
            db.session.delete(srv)

        comitar_com_retry(preparar)
        emit('servidor_apagado', {'server_id': server_id}, to=sala_servidor(server_id))
        emit('servidor_mapa_apagado', {'server_id': server_id}, broadcast=True)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar o servidor: {e}'})


@socketio.on('expulsar_membro')
def expulsar_membro(dados):
    """Tira alguém do servidor. Só o dono, e o dono não pode se expulsar."""
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = servidor_gerenciavel(usuario, dados.get('server_id'))
        if not srv:
            emit('erro_bazinga', {'msg': 'Só o dono pode remover membros.'})
            return

        alvo = com_retry(lambda: Person.query.get(int(dados.get('person_id'))))
        if not alvo or alvo not in srv.members:
            return
        if alvo.id == srv.owner_id:
            emit('erro_bazinga', {'msg': 'O dono não pode se remover do próprio servidor.'})
            return

        def preparar():
            srv.members.remove(alvo)
            # Também sai dos canais privados em que estava liberado
            for canal in srv.channels:
                if canal.is_private and alvo in canal.allowed_members:
                    canal.allowed_members.remove(alvo)

        comitar_com_retry(preparar)

        # Some da sidebar de quem foi removido, na hora
        emit('servidor_apagado', {'server_id': srv.id}, to=sala_pessoal(alvo.id))
        emit('membro_removido', {'server_id': srv.id, 'person_id': alvo.id},
             to=sala_servidor(srv.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EXPULSAR MEMBRO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível remover o membro: {e}'})


@socketio.on('transferir_posse')
def transferir_posse(dados):
    """Passa a posse do servidor pra outro membro."""
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = servidor_gerenciavel(usuario, dados.get('server_id'))
        if not srv:
            emit('erro_bazinga', {'msg': 'Só o dono pode passar a posse.'})
            return

        novo_dono = com_retry(lambda: Person.query.get(int(dados.get('person_id'))))
        if not novo_dono or novo_dono not in srv.members:
            emit('erro_bazinga', {'msg': 'Essa pessoa não está no servidor.'})
            return
        if novo_dono.id == srv.owner_id:
            return

        def preparar():
            srv.owner_id = novo_dono.id

        comitar_com_retry(preparar)
        avisar_servidor(srv)
        emit('posse_transferida', {'server_id': srv.id, 'novo_dono': novo_dono.name},
             to=sala_servidor(srv.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO TRANSFERIR POSSE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível passar a posse: {e}'})


@socketio.on('sair_do_servidor')
def sair_do_servidor(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = com_retry(lambda: Server.query.get(int(dados.get('server_id'))))
        if not srv:
            return
        if srv.owner_id == usuario.id:
            emit('erro_bazinga', {'msg': 'O dono não pode sair - apague o servidor ou passe a posse.'})
            return

        def preparar():
            if usuario in srv.members:
                srv.members.remove(usuario)

        comitar_com_retry(preparar)
        leave_room(sala_servidor(srv.id))
        emit('servidor_apagado', {'server_id': srv.id})  # some da sidebar de quem saiu
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO SAIR DO SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível sair do servidor: {e}'})


@socketio.on('entrar_servidor_pin')
def entrar_servidor_pin(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    if not localizacao_ligada(usuario):
        emit('erro_bazinga', {'msg': MSG_LOCALIZACAO_DESLIGADA})
        return

    try:
        server_id = int(dados.get('server_id'))

        srv = com_retry(lambda: Server.query.get(server_id))
        if not srv:
            emit('erro_bazinga', {'msg': 'Esse servidor não existe mais.'})
            return

        if usuario not in srv.members:
            # Respeita o limite de vagas do pino plantado no mapa, se existir.
            pino = MapServer.query.filter_by(server_id=srv.id).first()
            if pino and pino.max_tickets is not None and len(srv.members) >= pino.max_tickets:
                emit('erro_bazinga', {'msg': 'Esse servidor já está lotado - sem mais ingressos.'})
                return

            def preparar():
                srv.members.append(usuario)

            comitar_com_retry(preparar)

        join_room(sala_servidor(srv.id))
        emit('servidor_discord_criado', servidor_para_json(srv, usuario))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ENTRAR SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível entrar no servidor: {e}'})


# ==========================================
# MAPA: Notas HQ (GeoNote) e Servidores Plantados (MapServer)
# ------------------------------------------------------------
# PRIVACIDADE POR RAIO: nota e servidor só chegam ao navegador de quem está perto
# (RAIO_NOTAS_M / RAIO_SERVIDORES_M em utils.py; servidor tem alcance maior).
# `centros_mapa` guarda, em memória, onde cada socket está olhando - é o que decide
# quem recebe cada aviso ao vivo. Nunca é repassado a ninguém (vale também no Modo
# Fantasma: a posição só serve pro servidor filtrar, não aparece pra outros).
# ==========================================
centros_mapa = {}   # sid -> (lat, lng)
# Última posição de quem NÃO está no Fantasma (usuario_id -> payload). É o que faltava pra amigo aparecer assim que
# você abre o mapa: antes a posição só existia no instante em que a pessoa se mexia, e quem chegava depois via mapa vazio.
ultimas_posicoes = {}
POSICAO_VALE_SEGUNDOS = 180
_cache_contatos = {}   # usuario_id -> (ts, amigos_ids, colegas_ids, servidores_ids)


def contatos_do_mapa(usuario):
    """(amigos, colegas de servidor, servidores) de uma pessoa, com cache curto: a posição chega a cada movimento
    e não pode custar 3 idas ao banco toda vez."""
    agora = time.time()
    c = _cache_contatos.get(usuario.id)
    if c and agora - c[0] < 60:
        return c[1], c[2], c[3]
    linhas = Friendship.query.filter(
        Friendship.status == 'accepted',
        or_(Friendship.requester_id == usuario.id, Friendship.addressee_id == usuario.id)).all()
    amigos = {f.addressee_id if f.requester_id == usuario.id else f.requester_id for f in linhas}
    srv_ids = [s.id for s in usuario.servers]
    colegas = set()
    if srv_ids:
        colegas = {r[0] for r in db.session.query(server_members.c.person_id)
                   .filter(server_members.c.server_id.in_(srv_ids)).all()} - {usuario.id}
    _cache_contatos[usuario.id] = (agora, amigos, colegas, srv_ids)
    return amigos, colegas, srv_ids


def _salas_da_posicao(usuario):
    """Quem pode ver o pino: salas dos servidores dela E a sala pessoal de cada amigo (antes só servidor: amigo sem
    servidor em comum nunca aparecia no mapa do outro)."""
    amigos, _colegas, srv_ids = contatos_do_mapa(usuario)
    return [sala_servidor(i) for i in srv_ids] + [sala_pessoal(i) for i in amigos]


def _emitir_perto(evento, payload, lat, lng, raio_m, tambem_sid=None):
    """Manda só pra quem está dentro do raio (mais quem fez a ação)."""
    alvos = {sid for sid, (la, ln) in list(centros_mapa.items()) if distancia_m(lat, lng, la, ln) <= raio_m}
    if tambem_sid:
        alvos.add(tambem_sid)
    for sid in alvos:
        emit(evento, payload, to=sid)


def _avisar_amigos(evento, payload, usuario):
    """Nota de amigo vale no alcance grande: o aviso vai pra sala pessoal de cada amigo e o navegador dele filtra por
    distância. Falha aqui nunca derruba a criação da nota."""
    try:
        amigos, _c, _s = contatos_do_mapa(usuario)
        for fid in amigos:
            emit(evento, payload, to=sala_pessoal(fid))
    except Exception as e:
        print(f"[ERRO AVISAR AMIGOS] {e}")


def _parse_ilimitado(valor):
    """Converte 'ilimitado'/'permanente'/vazio em None, senão retorna int."""
    if valor is None:
        return None
    if isinstance(valor, str) and valor.lower() in ('ilimitado', 'permanente', ''):
        return None
    try:
        n = int(valor)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _dentro_do_alcance(pos, raio_m):
    """True se `pos` está dentro do raio do que este socket está olhando.
    Sem centro conhecido (ainda não mandou posição) não dá pra checar: deixa passar."""
    centro = centros_mapa.get(request.sid)
    return centro is None or distancia_m(centro[0], centro[1], pos[0], pos[1]) <= raio_m * 1.15


@socketio.on('mapa_pedir_arredores')
def mapa_pedir_arredores(dados):
    """O cliente avisa onde está olhando e recebe SÓ o que está no raio."""
    usuario = usuario_logado()
    if not usuario:
        return
    if not localizacao_ligada(usuario):
        return   # sem localização não vê o radar (nem notas/servidores ao redor)
    pos = coordenada_valida((dados or {}).get('lat'), (dados or {}).get('lng'))
    if not pos:
        return
    centros_mapa[request.sid] = pos
    try:
        amigos, colegas, _srv = com_retry(lambda: contatos_do_mapa(usuario))
        d = com_retry(lambda: dados_do_mapa_perto(pos[0], pos[1], amigos))
        d['centro'] = {'lat': pos[0], 'lng': pos[1]}
        emit('mapa_arredores', d)
        # E onde cada amigo/colega está agora (sem esperar a pessoa se mexer).
        agora = time.time()
        for uid in (amigos | colegas):
            p = ultimas_posicoes.get(uid)
            # quem parou de mandar sinal (o cliente reenvia a cada ~45s) não é "ao vivo": não mostra pino fantasma
            if p and agora - p.get('_t', agora) <= POSICAO_VALE_SEGUNDOS:
                emit('posicao_amigo_atualizada', {k: v for k, v in p.items() if not k.startswith('_')})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MAPA ARREDORES] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível carregar o mapa: {e}'})


def _validar_nota_texto(dados):
    return (dados.get('texto') or '').strip()[:LIM_NOTA]


@socketio.on('criar_geonote')
def criar_geonote(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    if not localizacao_ligada(usuario):
        emit('erro_bazinga', {'msg': MSG_LOCALIZACAO_DESLIGADA})
        return

    try:
        pos = coordenada_valida(dados.get('lat'), dados.get('lng'))
        if not pos:
            emit('erro_bazinga', {'msg': 'Local inválido para a nota.'})
            return
        if not _dentro_do_alcance(pos, RAIO_NOTAS_M):
            emit('erro_bazinga', {'msg': 'Esse ponto está fora do seu alcance - chegue mais perto pra deixar a nota.'})
            return

        texto = _validar_nota_texto(dados) or "Loot raro aqui!"
        cor = dados.get('cor') or '#5865F2'
        icone = (dados.get('icone') or '').strip()[:16] or None
        # Duração: o modelo e o /api/mapa/dados já filtram por expires_at, mas
        # isso aqui nunca era preenchido - toda nota virava eterna.
        duracao = _parse_ilimitado(dados.get('duracao'))
        agora = br_now()
        expira_em = agora + timedelta(hours=duracao) if duracao else None

        ativas = com_retry(lambda: GeoNote.query.filter(
            GeoNote.author_id == usuario.id,
            or_(GeoNote.expires_at == None, GeoNote.expires_at > agora)).count())  # noqa: E711
        if ativas >= MAX_NOTAS_ATIVAS_POR_PESSOA:
            emit('erro_bazinga', {'msg': f'Você já tem {ativas} notas ativas no mapa (o limite é {MAX_NOTAS_ATIVAS_POR_PESSOA}). Apague alguma antes.'})
            return

        def preparar():
            # Faxina de quebra: nota vencida há mais de 1 dia não serve pra nada.
            GeoNote.query.filter(GeoNote.expires_at != None, GeoNote.expires_at < agora - timedelta(days=1)).delete()  # noqa: E711
            nota = GeoNote(
                lat=pos[0], lng=pos[1], text=texto, color=cor, icone=icone,
                author_id=usuario.id, duration_hours=duracao, expires_at=expira_em
            )
            db.session.add(nota)
            return nota

        nota = comitar_com_retry(preparar)

        _emitir_perto('nova_geonote', nota_para_json(nota), nota.lat, nota.lng, RAIO_NOTAS_M, tambem_sid=request.sid)
        _avisar_amigos('nova_geonote', nota_para_json(nota), usuario)
        _emitir_progresso(usuario, {'nota': 1})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRIAR GEONOTE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar a nota: {e}'})


@socketio.on('editar_geonote')
def editar_geonote(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        nota = com_retry(lambda: GeoNote.query.get(dados.get('id')))
        if not nota or nota.author_id != usuario.id:
            return

        def preparar():
            if 'texto' in dados:
                nota.text = _validar_nota_texto(dados) or nota.text
            if 'cor' in dados:
                nota.color = dados.get('cor') or nota.color
            if 'icone' in dados:
                nota.icone = (dados.get('icone') or '').strip()[:16] or None

        comitar_com_retry(preparar)
        _emitir_perto('geonote_editada', nota_para_json(nota), nota.lat, nota.lng, RAIO_NOTAS_M, tambem_sid=request.sid)
        _avisar_amigos('geonote_editada', nota_para_json(nota), usuario)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EDITAR GEONOTE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível editar a nota: {e}'})


@socketio.on('apagar_geonote')
def apagar_geonote(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        nota = com_retry(lambda: GeoNote.query.get(dados.get('id')))
        if not nota or nota.author_id != usuario.id:
            return
        nota_id = nota.id

        def preparar():
            db.session.delete(nota)

        comitar_com_retry(preparar)
        # Só o id vai pra todo mundo (não vaza nada) - quem tinha a nota na tela tira.
        emit('geonote_apagada', {'id': nota_id}, broadcast=True)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR GEONOTE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar a nota: {e}'})


@socketio.on('copiar_geonote')
def copiar_geonote(dados):
    """Copia uma nota que a pessoa está vendo pra dentro do SEU alcance. Não copia
    link nem texto pra área de transferência - cria uma nota nova, dela, igual à outra."""
    usuario = usuario_logado()
    if not usuario:
        return

    if not localizacao_ligada(usuario):
        emit('erro_bazinga', {'msg': MSG_LOCALIZACAO_DESLIGADA})
        return

    try:
        centro = centros_mapa.get(request.sid)
        nota = com_retry(lambda: GeoNote.query.get(dados.get('id')))
        agora = br_now()
        if not centro or not nota or nota.oculta or (nota.expires_at and nota.expires_at <= agora):
            emit('erro_bazinga', {'msg': 'Essa nota não está mais disponível.'})
            return
        if distancia_m(centro[0], centro[1], nota.lat, nota.lng) > RAIO_NOTAS_M * 1.15:
            emit('erro_bazinga', {'msg': 'Essa nota está longe demais pra copiar.'})
            return

        pos = coordenada_valida(dados.get('lat'), dados.get('lng')) or centro
        if distancia_m(centro[0], centro[1], pos[0], pos[1]) > RAIO_NOTAS_M * 1.15:
            pos = centro

        ativas = com_retry(lambda: GeoNote.query.filter(
            GeoNote.author_id == usuario.id,
            or_(GeoNote.expires_at == None, GeoNote.expires_at > agora)).count())  # noqa: E711
        if ativas >= MAX_NOTAS_ATIVAS_POR_PESSOA:
            emit('erro_bazinga', {'msg': f'Você já tem {ativas} notas ativas (limite {MAX_NOTAS_ATIVAS_POR_PESSOA}).'})
            return

        horas = nota.duration_hours or 24

        def preparar():
            copia = GeoNote(lat=pos[0], lng=pos[1], text=nota.text, color=nota.color, icone=nota.icone,
                            author_id=usuario.id, duration_hours=horas, expires_at=agora + timedelta(hours=horas))
            db.session.add(copia)
            return copia

        copia = comitar_com_retry(preparar)
        _emitir_perto('nova_geonote', nota_para_json(copia), copia.lat, copia.lng, RAIO_NOTAS_M, tambem_sid=request.sid)
        emit('nota_copiada', {'id': copia.id})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO COPIAR GEONOTE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível copiar a nota: {e}'})


@socketio.on('plantar_servidor')
def plantar_servidor(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    if not localizacao_ligada(usuario):
        emit('erro_bazinga', {'msg': MSG_LOCALIZACAO_DESLIGADA})
        return

    try:
        server_id = dados.get('server_id')
        srv = com_retry(lambda: Server.query.get(int(server_id))) if server_id else None
        if not srv or srv.owner_id != usuario.id:
            emit('erro_bazinga', {'msg': 'Você só pode plantar um servidor que você é dono.'})
            return

        pos = coordenada_valida(dados.get('lat'), dados.get('lng'))
        if not pos:
            emit('erro_bazinga', {'msg': 'Local inválido para o servidor.'})
            return
        if not _dentro_do_alcance(pos, RAIO_SERVIDORES_M):
            emit('erro_bazinga', {'msg': 'Esse ponto está fora do seu alcance.'})
            return

        vagas = _parse_ilimitado(dados.get('vagas'))
        duracao = _parse_ilimitado(dados.get('duracao'))
        expira_em = br_now() + timedelta(hours=duracao) if duracao else None

        def preparar():
            pino = MapServer(
                name=srv.name, lat=pos[0], lng=pos[1],
                max_tickets=vagas, duration_hours=duracao, expires_at=expira_em,
                owner_id=usuario.id, server_id=srv.id
            )
            db.session.add(pino)
            return pino

        pino = comitar_com_retry(preparar)

        _emitir_perto('novo_servidor_mapa', servidor_mapa_para_json(pino), pino.lat, pino.lng,
                      RAIO_SERVIDORES_M, tambem_sid=request.sid)
        _emitir_progresso(usuario, {'plantar': 1})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PLANTAR SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível plantar o servidor: {e}'})


@socketio.on('editar_servidor_mapa')
def editar_servidor_mapa(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        pino = com_retry(lambda: MapServer.query.get(dados.get('id')))
        if not pino or pino.owner_id != usuario.id:
            return

        vagas = _parse_ilimitado(dados.get('vagas'))
        duracao = _parse_ilimitado(dados.get('duracao'))

        def preparar():
            pino.max_tickets = vagas
            pino.duration_hours = duracao
            pino.expires_at = br_now() + timedelta(hours=duracao) if duracao else None

        comitar_com_retry(preparar)
        _emitir_perto('servidor_mapa_editado', servidor_mapa_para_json(pino), pino.lat, pino.lng,
                      RAIO_SERVIDORES_M, tambem_sid=request.sid)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EDITAR SERVIDOR MAPA] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível editar o servidor plantado: {e}'})


@socketio.on('apagar_servidor_mapa')
def apagar_servidor_mapa(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        pino = com_retry(lambda: MapServer.query.get(dados.get('id')))
        if not pino or pino.owner_id != usuario.id:
            return
        pino_id = pino.id

        def preparar():
            db.session.delete(pino)

        comitar_com_retry(preparar)
        emit('servidor_mapa_apagado', {'id': pino_id}, broadcast=True)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR SERVIDOR MAPA] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar o servidor plantado: {e}'})


@socketio.on('denunciar')
def denunciar(dados):
    """Denuncia uma nota ou um servidor plantado (conteúdo +18, assédio, spam...).
    Com DENUNCIAS_PARA_OCULTAR pessoas diferentes denunciando, o alvo some do mapa
    até alguém revisar. Quem denuncia também deixa de ver na hora (cliente)."""
    usuario = usuario_logado()
    if not usuario:
        return

    tipo = (dados or {}).get('tipo')
    motivo = (dados or {}).get('motivo')
    if tipo not in ('nota', 'servidor', 'usuario') or motivo not in MOTIVOS_DENUNCIA:
        emit('erro_bazinga', {'msg': 'Denúncia inválida.'})
        return
    try:
        alvo_id = int(dados.get('id'))
    except (TypeError, ValueError):
        return

    try:
        modelo = {'nota': GeoNote, 'servidor': MapServer, 'usuario': Person}[tipo]
        alvo = com_retry(lambda: modelo.query.get(alvo_id))
        if not alvo:
            emit('erro_bazinga', {'msg': 'Isso já não existe mais.'})
            return
        dono_id = alvo.id if tipo == 'usuario' else (alvo.author_id if tipo == 'nota' else alvo.owner_id)
        if dono_id == usuario.id:
            emit('erro_bazinga', {'msg': 'Você não pode denunciar o seu próprio conteúdo.'})
            return
        if com_retry(lambda: Denuncia.query.filter_by(denunciante_id=usuario.id, tipo=tipo, alvo_id=alvo_id).first()):
            emit('denuncia_registrada', {'tipo': tipo, 'id': alvo_id, 'repetida': True})
            return

        detalhe = (dados.get('detalhe') or '').strip()[:300] or None
        escondeu = {'v': False}

        def preparar():
            db.session.add(Denuncia(denunciante_id=usuario.id, tipo=tipo, alvo_id=alvo_id, motivo=motivo, detalhe=detalhe))
            db.session.flush()
            total = Denuncia.query.filter_by(tipo=tipo, alvo_id=alvo_id).count()
            # Pessoa denunciada não "some": a denúncia fica registrada pra revisão humana.
            if tipo != 'usuario' and total >= DENUNCIAS_PARA_OCULTAR and not alvo.oculta:
                alvo.oculta = True
                escondeu['v'] = True

        comitar_com_retry(preparar)
        emit('denuncia_registrada', {'tipo': tipo, 'id': alvo_id})
        if escondeu['v']:
            evento = 'geonote_apagada' if tipo == 'nota' else 'servidor_mapa_apagado'
            emit(evento, {'id': alvo_id}, broadcast=True)
        print(f"[DENUNCIA] {usuario.name} denunciou {tipo} #{alvo_id} ({motivo})")
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO DENUNCIAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível registrar a denúncia: {e}'})


@socketio.on('atualizar_localizacao')
def atualizar_localizacao(dados):
    """Posição ao vivo: não é persistida no banco.

    IMPORTANTE: isso é coordenada de GPS real. Antes ia em broadcast pro site
    inteiro; agora só vai para as salas dos Servidores em que o usuário é
    membro - ou seja, quem já convive com ele.
    """
    usuario = usuario_logado()
    if not usuario:
        return

    # Localização desligada: a posição nem entra no servidor e some do radar de quem já via (regra 6).
    if not localizacao_ligada(usuario):
        ultimas_posicoes.pop(usuario.id, None)
        centros_mapa.pop(request.sid, None)
        return

    pos = coordenada_valida((dados or {}).get('lat'), (dados or {}).get('lng'))
    if not pos:
        return

    # O servidor sempre sabe onde este socket está olhando (pro filtro por raio),
    # mas isso nunca sai daqui - o Fantasma só controla se OUTROS veem o pino.
    centros_mapa[request.sid] = pos

    # Fantasma valendo de verdade: a posição nem sai do servidor. Antes só o
    # navegador se continha, então um cliente adulterado (ou o teletransporte
    # por duplo clique) vazava a posição mesmo com o modo ligado.
    if usuario.ghost_mode:
        ultimas_posicoes.pop(usuario.id, None)
        return

    try:
        payload = {
            'usuario_id': usuario.id,
            'nome': usuario.name,
            'avatar': usuario.avatar,
            'lat': pos[0],
            'lng': pos[1]
        }
        ultimas_posicoes[usuario.id] = dict(payload, _t=time.time())
        for sala in _salas_da_posicao(usuario):
            emit('posicao_amigo_atualizada', payload, to=sala, include_self=False)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ATUALIZAR LOCALIZACAO] {e}")


# ==========================================
# PERFIL DO USUÁRIO
# ==========================================
def _payload_perfil(usuario):
    """O que a própria pessoa recebe (em todas as abas) depois de mudar o perfil."""
    return {
        'name': usuario.name,
        'custom_status': usuario.custom_status,
        'bio': usuario.bio,
        'banner_color': usuario.banner_color,
        'banner_url': usuario.banner_url,
        'banner_ajuste': usuario.banner_ajuste,
        'pronomes': usuario.pronomes,
        'username': usuario.username,
        'status_emoji': usuario.status_emoji,
        'pensando': usuario.pensando,
        'perfil_tema': usuario.perfil_tema,
        'nome_estilo': usuario.nome_estilo,
        'placa': usuario.placa,
        'moldura': usuario.moldura,
        'equipados': equipados_da_pessoa(usuario),
        'avatar': usuario.avatar
    }


def _difundir_aparencia(usuario):
    """Avisa quem convive (servidores e amigos) que o visual mudou - sem isso só quem editou
    via a mudança até um F5 (regra 6)."""
    payload_publico = {'usuario_id': usuario.id, 'nome': usuario.name, 'avatar': usuario.avatar,
                       'placa': usuario.placa, 'nome_estilo': usuario.nome_estilo, 'moldura': usuario.moldura,
                       'equipados': equipados_da_pessoa(usuario),
                       'pensando': usuario.pensando, 'status_texto': texto_do_status(usuario)}
    for srv in usuario.servers:
        emit('perfil_membro_mudou', payload_publico, to=sala_servidor(srv.id), include_self=False)
    for amigo in amigos_de(usuario):
        emit('perfil_membro_mudou', payload_publico, to=sala_pessoal(amigo.id))
    _atualizar_visual_na_call(usuario)


def _atualizar_visual_na_call(usuario):
    """Quem equipa algo no meio de uma call: os outros participantes (e quem só está olhando a prévia do canal de
    voz) precisam ver o visual novo agora, não só quando a pessoa sair e entrar de novo (regra 6)."""
    try:
        for chave, lista in list(participantes_call.items()):
            meus = [p for p in lista if p.get('usuario_id') == usuario.id]
            if not meus:
                continue
            for p in meus:
                p.update({'moldura': usuario.moldura, 'nome_estilo': usuario.nome_estilo,
                          'equipados': equipados_da_pessoa(usuario)})
            payload = {'canal_id': chave, 'participantes': lista}
            if chave.startswith('dm_'):
                _, id_a, id_b = chave.split('_')
                emit('participantes_call_mudou', payload, to=sala_pessoal(int(id_a)))
                emit('participantes_call_mudou', payload, to=sala_pessoal(int(id_b)))
            else:
                canal = com_retry(lambda: Channel.query.get(int(chave)))
                if canal and canal.server_id:
                    emit('participantes_call_mudou', payload, to=sala_servidor(canal.server_id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO VISUAL NA CALL] {e}")   # nunca derruba o equipar


@socketio.on('atualizar_perfil')
def atualizar_perfil(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    # Nome da conta (@): validado e checado por unicidade antes de tudo. Se falhar,
    # o resto do perfil ainda salva - só o @ fica como estava.
    username_novo = None
    if 'username' in dados:
        candidato = (dados.get('username') or '').strip().lstrip('@').lower()
        if candidato != (usuario.username or ''):
            if not username_valido(candidato):
                emit('erro_bazinga', {'msg': 'Nome da conta inválido: use de 3 a 32 letras minúsculas, números, ponto ou _.'})
            elif com_retry(lambda: Person.query.filter(Person.username == candidato, Person.id != usuario.id).first()):
                emit('erro_bazinga', {'msg': f'O nome de conta "{candidato}" já está em uso.'})
            else:
                username_novo = candidato

    # Enfeite EXCLUSIVO (laboratório) só se a pessoa tem a posse (regra 4): o cliente pode
    # mandar qualquer id, o servidor é quem confere. Livre passa direto.
    posses = {}
    negados = []

    def pode_usar(tipo, valor):
        if not valor or not item_exclusivo(tipo, valor):
            return True
        if 'conjunto' not in posses:
            posses['conjunto'] = posses_da_pessoa(usuario.id)
        if f'{tipo}:{valor}' in posses['conjunto']:
            return True
        if valor not in negados:
            negados.append(valor)
        return False

    try:
        def preparar():
            if 'name' in dados:
                nome_novo = (dados.get('name') or '').strip()[:LIM_NOME_EXIBICAO]
                if nome_novo:
                    usuario.name = nome_novo
            if 'custom_status' in dados:
                usuario.custom_status = (dados.get('custom_status') or '').strip()[:LIM_STATUS] or None
            if 'bio' in dados:
                usuario.bio = (dados.get('bio') or '').strip()[:1000] or None
            if 'banner_color' in dados:
                # Só #rrggbb ou anim:<id conhecido>: essa string vai parar num style=""/class=""
                # no cliente de todo mundo.
                cor = (dados.get('banner_color') or '').strip()
                valida = bool(re.match(r'^#[0-9a-fA-F]{6}$', cor)) or (cor.startswith('anim:') and cor[5:] in FAIXAS_ANIMADAS)
                if not valida:
                    usuario.banner_color = None
                elif pode_usar('faixa', cor[5:] if cor.startswith('anim:') else None):
                    usuario.banner_color = cor
            if 'pronomes' in dados:
                usuario.pronomes = (dados.get('pronomes') or '').strip()[:LIM_PRONOMES] or None
            if 'banner_url' in dados:
                # Caminho do site, Cloudinary ou Giphy (mesma regra do avatar e do tema -
                # antes só aceitava os dois primeiros, então o GIF escolhido nas
                # sugestões era descartado em silêncio e a faixa "não salvava").
                # Vazio limpa e volta pra cor.
                url = (dados.get('banner_url') or '').strip()
                usuario.banner_url = url if url_de_imagem_ok(url) else None
                if not usuario.banner_url:
                    usuario.banner_ajuste = None
            if 'banner_ajuste' in dados:
                usuario.banner_ajuste = ajuste_de_imagem_valido(dados.get('banner_ajuste')) if usuario.banner_url else None
            if 'status_emoji' in dados:
                usuario.status_emoji = (dados.get('status_emoji') or '').strip()[:16] or None
            if 'pensando' in dados:
                usuario.pensando = (dados.get('pensando') or '').strip()[:LIM_PENSANDO] or None
            if 'perfil_tema' in dados:
                tema = (dados.get('perfil_tema') or '').strip()
                usuario.perfil_tema = tema if tema and tema_perfil_valido(tema) else None
            # Id fora do catálogo/'padrao' limpa o slot; exclusivo sem posse NÃO muda nada
            # (não pode apagar o que a pessoa já tinha equipado só porque pediu o que não tem).
            if 'nome_estilo' in dados:
                estilo = dados.get('nome_estilo')
                if estilo in ESTILOS_NOME and estilo != 'padrao':
                    if pode_usar('nome', estilo):
                        usuario.nome_estilo = estilo
                else:
                    usuario.nome_estilo = None
            if 'placa' in dados:
                placa = dados.get('placa')
                if placa in PLACAS and placa != 'nenhuma':
                    if pode_usar('placa', placa):
                        usuario.placa = placa
                else:
                    usuario.placa = None
            if 'moldura' in dados:
                moldura = dados.get('moldura')
                if moldura in MOLDURAS and moldura != 'nenhuma':
                    if pode_usar('moldura', moldura):
                        usuario.moldura = moldura
                else:
                    usuario.moldura = None
            if username_novo:
                usuario.username = username_novo
            avatar = dados.get('avatar')
            # Só caminho do site, Cloudinary ou Giphy (antes só barrava blob:, então
            # qualquer URL externa virava o avatar de todo mundo).
            if avatar and url_de_imagem_ok(avatar):
                usuario.avatar = avatar

        comitar_com_retry(preparar)
        emit('perfil_atualizado', _payload_perfil(usuario))
        if negados:
            emit('erro_bazinga', {'msg': 'Você ainda não tem esse item exclusivo: ' + ', '.join(negados) + '.'})

        # Nome/avatar aparecem em telas de quem não é "eu": lista de membros
        # de cada servidor. Sem isso, só quem editou via as próprias
        # (várias abas dele) via perfil_atualizado; o resto via F5.
        visual = ('name', 'avatar', 'placa', 'nome_estilo', 'moldura', 'status_emoji', 'pensando', 'custom_status')
        if any(k in dados for k in visual):
            _difundir_aparencia(usuario)
        if ('status_emoji' in dados or 'custom_status' in dados) and (usuario.status or 'online') == 'custom':
            aviso = {'usuario_id': usuario.id, 'status': status_visivel(usuario), 'emoji': usuario.status_emoji,
                     'texto': usuario.custom_status}
            for srv in usuario.servers:
                emit('status_visivel_mudou', aviso, to=sala_servidor(srv.id), include_self=False)
            for amigo in amigos_de(usuario):
                emit('status_visivel_mudou', aviso, to=sala_pessoal(amigo.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ATUALIZAR PERFIL] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar o perfil: {e}'})


# ==========================================
# INVENTÁRIO: equipar / desequipar (itens com posse + livres)
# ------------------------------------------------------------
# O cliente manda só "<tipo>:<id>"; o servidor confere se o id existe e, se o item é exclusivo,
# se a pessoa TEM a posse. Pacote = equipa todos os itens do tema de uma vez.
# ==========================================
_TUPLAS_LIVRES = {'moldura': MOLDURAS, 'placa': PLACAS, 'nome': ESTILOS_NOME, 'faixa': FAIXAS_ANIMADAS}


def _equipavel(tipo, valor, posses):
    """True se `valor` existe pra esse tipo e (sendo exclusivo) a pessoa o possui."""
    if tipo in TIPOS_COLUNA:
        if valor not in _TUPLAS_LIVRES[tipo] or valor in ('padrao', 'nenhuma'):
            return False
    elif tipo in TIPOS_JSON:
        if not item_exclusivo(tipo, valor):
            return False
    else:
        return False
    return (not item_exclusivo(tipo, valor)) or f'{tipo}:{valor}' in posses


def _estado_inventario(usuario, posses):
    """Foto do inventário da pessoa: o que possui, o que está equipado e a tabela de patentes."""
    equipados = {t: valor_atual_do_slot(usuario, t) for t in TIPOS_EQUIPAVEIS}
    return {'posses': sorted(posses), 'catalogo': catalogo_para_json(posses),
            'equipados': {t: v for t, v in equipados.items() if v},
            'patentes': patentes_para_json(), 'nivel': nivel_da_pessoa(usuario.xp)}


@socketio.on('listar_inventario')
def listar_inventario(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        emit('inventario', _estado_inventario(usuario, com_retry(lambda: posses_da_pessoa(usuario.id))))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LISTAR INVENTARIO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível abrir o inventário: {e}'})


@socketio.on('equipar_item')
def equipar_item(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    item_id = str((dados or {}).get('item_id') or '')[:60]
    tipo, _, valor = item_id.partition(':')

    try:
        posses = com_retry(lambda: posses_da_pessoa(usuario.id))
        if tipo == 'pacote':
            if item_id not in CATALOGO or item_id not in posses:
                emit('erro_bazinga', {'msg': 'Você ainda não tem esse pacote.'})
                return
            escolhas = {t: v for t, v in PACOTES.get(valor, {}).items() if _equipavel(t, v, posses)}
        else:
            if not _equipavel(tipo, valor, posses):
                emit('erro_bazinga', {'msg': 'Você ainda não tem esse item.' if item_exclusivo(tipo, valor) else 'Item inválido.'})
                return
            escolhas = {tipo: valor}

        def preparar():
            for t, v in escolhas.items():
                definir_slot(usuario, t, v)

        comitar_com_retry(preparar)
        emit('perfil_atualizado', _payload_perfil(usuario), to=sala_pessoal(usuario.id))
        emit('inventario', _estado_inventario(usuario, posses), to=sala_pessoal(usuario.id))
        _difundir_aparencia(usuario)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EQUIPAR ITEM] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível equipar: {e}'})


@socketio.on('desequipar_item')
def desequipar_item(dados):
    """Tira o que está equipado num slot (volta ao padrão). `tipo` = moldura, placa, nome, faixa, efeito_*..."""
    usuario = usuario_logado()
    if not usuario:
        return
    tipo = str((dados or {}).get('tipo') or '')
    if tipo not in TIPOS_EQUIPAVEIS:
        return
    try:
        def preparar():
            definir_slot(usuario, tipo, None)

        comitar_com_retry(preparar)
        posses = com_retry(lambda: posses_da_pessoa(usuario.id))
        emit('perfil_atualizado', _payload_perfil(usuario), to=sala_pessoal(usuario.id))
        emit('inventario', _estado_inventario(usuario, posses), to=sala_pessoal(usuario.id))
        _difundir_aparencia(usuario)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO DESEQUIPAR ITEM] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível desequipar: {e}'})


@socketio.on('alternar_fantasma')
def alternar_fantasma(dados):
    """Liga/desliga o Modo Fantasma e guarda na conta.

    Aceita o valor explícito (`ativo`) em vez de só inverter: duas abas
    clicando quase juntas não podem acabar uma contra a outra.
    """
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        ativo = bool(dados.get('ativo'))

        def preparar():
            usuario.ghost_mode = ativo

        comitar_com_retry(preparar)

        # Todas as abas/aparelhos da própria pessoa acompanham.
        emit('preferencias_carregadas', {'ghost_mode': ativo}, to=sala_pessoal(usuario.id))

        # Ligou: quem já via o pino dela precisa tirar agora (antes o pino
        # ficava parado no mapa dos outros até F5).
        if ativo:
            ultimas_posicoes.pop(usuario.id, None)
            for sala in _salas_da_posicao(usuario):
                emit('posicao_amigo_removida', {'usuario_id': usuario.id}, to=sala, include_self=False)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ALTERNAR FANTASMA] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível mudar o Modo Fantasma: {e}'})


@socketio.on('alternar_localizacao')
def alternar_localizacao(dados):
    """Liga/desliga a localização (e a reserva por IP) na conta. Valor explícito, como no Modo Fantasma."""
    usuario = usuario_logado()
    if not usuario:
        return

    dados = dados or {}
    try:
        novo_ativa = bool(dados['ativa']) if 'ativa' in dados else None
        novo_ip = bool(dados['ip']) if 'ip' in dados else None

        def preparar():
            if novo_ativa is not None:
                usuario.localizacao_ativa = novo_ativa
            if novo_ip is not None:
                usuario.localizacao_ip = novo_ip

        comitar_com_retry(preparar)

        emit('preferencias_carregadas', {'localizacao_ativa': localizacao_ligada(usuario),
                                         'localizacao_ip': usuario.localizacao_ip is not False},
             to=sala_pessoal(usuario.id))

        # Desligou: some do radar de quem já via o pino (igual ao Fantasma) e esquece onde estava.
        if novo_ativa is False:
            ultimas_posicoes.pop(usuario.id, None)
            for sala in _salas_da_posicao(usuario):
                emit('posicao_amigo_removida', {'usuario_id': usuario.id}, to=sala, include_self=False)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ALTERNAR LOCALIZACAO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar a localização: {e}'})


@socketio.on('mudar_tema')
def mudar_tema(dados):
    """Guarda o tema visual na conta e sincroniza as outras abas/aparelhos."""
    usuario = usuario_logado()
    if not usuario:
        return

    tema = (dados or {}).get('tema')
    if tema not in ('dark', 'light', 'amoled'):
        return

    try:
        def preparar():
            usuario.tema = tema

        comitar_com_retry(preparar)
        emit('preferencias_carregadas', {'tema': tema}, to=sala_pessoal(usuario.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MUDAR TEMA] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar o tema: {e}'})


@socketio.on('mudar_status')
def mudar_status(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        status = dados.get('status')
        if status not in STATUS_VALIDOS:
            return

        def preparar():
            usuario.status = status

        comitar_com_retry(preparar)

        # Outras abas/aparelhos dela: status de verdade (inclusive Invisível).
        emit('meu_status_mudou', {'status': status, 'emoji': usuario.status_emoji, 'texto': usuario.custom_status}, to=sala_pessoal(usuario.id))
        # Quem convive: só o que ela deixa ver (Invisível = offline). Antes só
        # salvava no banco e ninguém via a bolinha mudar sem recarregar (regra 6).
        aviso = {'usuario_id': usuario.id, 'status': status_visivel(usuario), 'emoji': emoji_do_status(usuario),
                 'texto': texto_do_status(usuario)}
        for srv in usuario.servers:
            emit('status_visivel_mudou', aviso, to=sala_servidor(srv.id), include_self=False)
        for amigo in amigos_de(usuario):
            emit('status_visivel_mudou', aviso, to=sala_pessoal(amigo.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MUDAR STATUS] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível mudar seu status: {e}'})


@socketio.on('obter_perfil')
def obter_perfil(dados):
    """Cartão de perfil de alguém. Quem não convive (nem servidor, nem amizade)
    só recebe nome e foto - bio/status/faixa não são públicos pro site todo."""
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        alvo = com_retry(lambda: Person.query.get(int(dados.get('usuario_id'))))
    except (TypeError, ValueError):
        return
    if not alvo:
        return

    try:
        sou_eu = alvo.id == usuario.id
        amigo = False if sou_eu else sao_amigos(usuario.id, alvo.id)
        convivem = sou_eu or amigo or bool(
            {s.id for s in usuario.servers} & {s.id for s in alvo.servers})

        if not convivem:
            emit('perfil_publico', {'id': alvo.id, 'nome': alvo.name, 'avatar': alvo.avatar, 'restrito': True,
                                     'username': alvo.username, 'nome_estilo': alvo.nome_estilo})
            return

        pendente = False
        if not sou_eu and not amigo:
            pendente = Friendship.query.filter(
                Friendship.status == 'pending',
                or_(and_(Friendship.requester_id == usuario.id, Friendship.addressee_id == alvo.id),
                    and_(Friendship.requester_id == alvo.id, Friendship.addressee_id == usuario.id))
            ).first() is not None

        nivel = nivel_da_pessoa(alvo.xp)
        badges = badges_do_conjunto(com_retry(lambda: posses_da_pessoa(alvo.id)))
        emit('perfil_publico', {
            'id': alvo.id, 'nome': alvo.name, 'avatar': alvo.avatar, 'restrito': False,
            'bio': alvo.bio, 'custom_status': alvo.custom_status, 'pronomes': alvo.pronomes,
            'username': alvo.username, 'status_emoji': alvo.status_emoji, 'emoji': emoji_do_status(alvo),
            'pensando': alvo.pensando, 'status_texto': texto_do_status(alvo),
            'perfil_tema': alvo.perfil_tema, 'nome_estilo': alvo.nome_estilo,
            'placa': alvo.placa, 'moldura': alvo.moldura,
            'banner_color': alvo.banner_color, 'banner_url': alvo.banner_url,
            'banner_ajuste': alvo.banner_ajuste,
            'status': (alvo.status or 'online') if sou_eu else status_visivel(alvo),
            'membro_desde': membro_desde_texto(alvo.created_at),
            'nivel': nivel, 'titulo': titulo_do_nivel(nivel), 'patente': patente_do_nivel(nivel),
            'badges': badges, 'equipados': equipados_da_pessoa(alvo),
            'eh_amigo': amigo, 'pedido_pendente': pendente, 'sou_eu': sou_eu,
            'tem_loja': Product.query.filter_by(seller_id=alvo.id).count() > 0
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO OBTER PERFIL] {e}")


# ==========================================
# AMIZADES DE VERDADE
# ------------------------------------------------------------
# Antes /chat mostrava TODO MUNDO que existe no banco como "amigo" e o botão
# de pedido só dava um toast de sucesso sem salvar nada. Agora é uma
# Friendship (pending -> accepted) de verdade.
# ==========================================
def pessoa_para_json_amigo(p):
    sv = status_visivel(p)
    return {'id': p.id, 'nome': p.name, 'avatar': p.avatar, 'username': p.username,
            'status': sv if sv != 'offline' else (p.status or 'online'), 'online': sv != 'offline',
            'emoji': emoji_do_status(p), 'status_texto': texto_do_status(p), 'pensando': p.pensando,
            'placa': p.placa, 'nome_estilo': p.nome_estilo}


# ------------------------------------------------------------
# Regras do pedido de amizade
#   - quem ENVIA fica "aguardando" (não tem botão de aceitar o próprio pedido);
#   - quem RECEBE vê a pessoa na lista de DMs como temporária, com Aceitar /
#     Recusar / Bloquear, e na tela de Amigos > Pendente;
#   - o pedido vale 24h (VALIDADE_PEDIDO) e some sozinho depois;
#   - bloqueio: quem bloqueou é o `requester_id` da linha 'blocked'.
# ------------------------------------------------------------
VALIDADE_PEDIDO = timedelta(hours=24)


def relacao_entre(id1, id2):
    """Linha de Friendship entre duas pessoas (qualquer sentido/status), ou None."""
    return Friendship.query.filter(
        or_(and_(Friendship.requester_id == id1, Friendship.addressee_id == id2),
            and_(Friendship.requester_id == id2, Friendship.addressee_id == id1))
    ).first()


def pedido_expirou(f):
    return f.status == 'pending' and f.created_at is not None and br_now() - f.created_at > VALIDADE_PEDIDO


def limpar_pedidos_expirados(pessoa_id):
    """Apaga os pedidos pendentes com mais de 24h que envolvem a pessoa."""
    corte = br_now() - VALIDADE_PEDIDO
    velhos = Friendship.query.filter(
        Friendship.status == 'pending', Friendship.created_at < corte,
        or_(Friendship.requester_id == pessoa_id, Friendship.addressee_id == pessoa_id)).all()
    if velhos:
        ids = [f.id for f in velhos]
        pares = [(f.requester_id, f.addressee_id) for f in velhos]

        def preparar():
            Friendship.query.filter(Friendship.id.in_(ids)).delete(synchronize_session=False)
            # Mensagem entre quem NÃO virou amigo é temporária: some junto com o pedido.
            for a, b in pares:
                DirectMessage.query.filter(
                    or_(and_(DirectMessage.sender_id == a, DirectMessage.receiver_id == b),
                        and_(DirectMessage.sender_id == b, DirectMessage.receiver_id == a))
                ).delete(synchronize_session=False)

        comitar_com_retry(preparar)
    return len(velhos)


def compartilham_servidor(a, b):
    return bool({s.id for s in a.servers} & {s.id for s in b.servers})


_SEM_REL = object()


def pode_trocar_dm(usuario, destinatario, rel=_SEM_REL):
    """DM só entre quem se conhece: a si mesmo (Anotações), amigos, pedido de amizade
    pendente (em qualquer sentido) ou quem divide um servidor. Bloqueio corta tudo.
    Antes qualquer pessoa mandava DM pra qualquer id do banco.
    `rel` (opcional) é a Friendship já buscada por quem chama: evita repetir a mesma ida ao banco."""
    if usuario.id == destinatario.id:
        return True
    if rel is _SEM_REL:
        rel = relacao_entre(usuario.id, destinatario.id)
    if rel:
        if rel.status == 'blocked':
            return False
        if rel.status == 'accepted':
            return True
        if rel.status == 'pending' and not pedido_expirou(rel):
            return True
    return compartilham_servidor(usuario, destinatario)


def _pedido_json(f, eu_id):
    enviado = f.requester_id == eu_id
    outro = f.addressee if enviado else f.requester
    restante = 0
    if f.created_at:
        restante = max(0, int((f.created_at + VALIDADE_PEDIDO - br_now()).total_seconds()))
    d = pessoa_para_json_amigo(outro)
    d.update({'pedido_id': f.id, 'direcao': 'enviado' if enviado else 'recebido', 'restante_s': restante,
              'rapida': bool(f.rapida)})
    return d


def oculta_pra(f, pessoa_id):
    """True se esta ponta já fechou a conversa/recusou (some só do lado dela)."""
    return bool(f.oculta_req if f.requester_id == pessoa_id else f.oculta_dest)


def montar_amizades(pessoa):
    """Tudo da tela de Amigos de uma vez: amigos, pedidos (enviados e recebidos) e bloqueados."""
    limpar_pedidos_expirados(pessoa.id)
    todas = Friendship.query.filter(
        or_(Friendship.requester_id == pessoa.id, Friendship.addressee_id == pessoa.id)
    ).options(joinedload(Friendship.requester), joinedload(Friendship.addressee)).all()
    amigos, pedidos, bloqueados = [], [], []
    for f in todas:
        outro = f.addressee if f.requester_id == pessoa.id else f.requester
        if f.status == 'accepted':
            amigos.append(pessoa_para_json_amigo(outro))
        elif f.status == 'pending':
            if not oculta_pra(f, pessoa.id):
                pedidos.append(_pedido_json(f, pessoa.id))
        elif f.status == 'blocked' and f.requester_id == pessoa.id:
            bloqueados.append({'id': outro.id, 'nome': outro.name, 'avatar': outro.avatar, 'username': outro.username})
    silenciados = [s.alvo_id for s in Silenciado.query.filter_by(person_id=pessoa.id).all()]
    return {'amigos': amigos, 'pedidos': pedidos, 'bloqueados': bloqueados, 'silenciados': silenciados}


def emitir_amizades(pessoa_id):
    """Manda o retrato atual das amizades pra TODAS as abas de uma pessoa (regra 6:
    a outra ponta do pedido precisa ver a mudança agora, não só quem agiu)."""
    try:
        _cache_contatos.pop(pessoa_id, None)
        pessoa = com_retry(lambda: Person.query.get(pessoa_id))
        if pessoa:
            emit('amizades', com_retry(lambda: montar_amizades(pessoa)), to=sala_pessoal(pessoa_id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EMITIR AMIZADES] {e}")


@socketio.on('listar_amizades')
def listar_amizades(dados=None):
    usuario = usuario_logado()
    if usuario:
        emitir_amizades(usuario.id)


def _aceitar_pedido(pedido, quem_aceitou):
    """Marca como aceito e avisa os dois lados. `quem_aceitou` é o destinatário."""
    solicitante = pedido.requester
    solicitante_id = solicitante.id

    if pedido.rapida and pedido.oculta_req:
        # Quem puxou a conversa já a tinha fechado: aceitar NÃO faz virar amigo na hora - o pedido
        # volta pra ele (com as mensagens) e agora é ele quem decide aceitar, recusar ou bloquear.
        def trocar():
            pedido.requester_id, pedido.addressee_id = quem_aceitou.id, solicitante_id
            pedido.rapida = False
            pedido.oculta_req = False
            pedido.oculta_dest = False
            pedido.created_at = br_now()

        comitar_com_retry(trocar)
        emit('pedido_amizade_recebido', {
            'de_id': quem_aceitou.id, 'de_nome': quem_aceitou.name, 'de_avatar': quem_aceitou.avatar,
            'pedido_id': pedido.id
        }, to=sala_pessoal(solicitante_id))
        criar_notificacao(solicitante_id, 'amizade', f'{quem_aceitou.name} quer ser seu amigo',
                          'Vocês já tinham trocado mensagens. O pedido vale por 24 horas.',
                          de_id=quem_aceitou.id, ref=str(quem_aceitou.id))
        emit('pedido_amizade_enviado', {'para': solicitante.name, 'para_id': solicitante_id}, to=sala_pessoal(quem_aceitou.id))
        emitir_amizades(quem_aceitou.id)
        emitir_amizades(solicitante_id)
        return

    def preparar():
        pedido.status = 'accepted'
        pedido.rapida = False

    comitar_com_retry(preparar)
    emit('pedido_amizade_respondido', {'aceito': True, 'amigo': pessoa_para_json_amigo(solicitante)},
         to=sala_pessoal(quem_aceitou.id))
    emit('pedido_amizade_respondido', {'aceito': True, 'amigo': pessoa_para_json_amigo(quem_aceitou)},
         to=sala_pessoal(solicitante_id))
    criar_notificacao(solicitante_id, 'amizade', f'{quem_aceitou.name} aceitou seu pedido de amizade',
                      de_id=quem_aceitou.id, ref=str(quem_aceitou.id))
    emitir_amizades(quem_aceitou.id)
    emitir_amizades(solicitante_id)


@socketio.on('enviar_pedido_amizade')
def enviar_pedido_amizade(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    busca = (dados.get('busca') or '').strip()
    alvo_id = dados.get('usuario_id')   # vindo do cartão de perfil: exato, sem depender do nome
    if not busca and alvo_id is None:
        return

    try:
        if alvo_id is not None:
            try:
                alvo = com_retry(lambda: Person.query.get(int(alvo_id)))
            except (TypeError, ValueError):
                return
        else:
            arroba = busca.lstrip('@').lower()
            # @conta e e-mail são únicos. O nome de EXIBIÇÃO pode repetir: com mais de uma pessoa
            # com o mesmo nome não dá pra adivinhar quem é - pede o @ em vez de escolher qualquer uma.
            alvo = com_retry(lambda: Person.query.filter(
                or_(Person.username == arroba, Person.email == busca)).first())
            if not alvo:
                iguais = com_retry(lambda: Person.query.filter(
                    func.lower(Person.name) == busca.lower(), Person.id != usuario.id).limit(6).all())
                if len(iguais) > 1:
                    lista = ', '.join('@' + (p.username or str(p.id)) for p in iguais[:5])
                    emit('erro_bazinga', {'msg': f'Tem mais de uma pessoa chamada "{busca}": {lista}. Use o @ da conta pra escolher.'})
                    return
                alvo = iguais[0] if iguais else None

        if not alvo:
            emit('erro_bazinga', {'msg': f'Não achei ninguém com "{busca}" no Panteão.'})
            return
        if alvo.id == usuario.id:
            emit('erro_bazinga', {'msg': 'Você não pode adicionar a si mesmo.'})
            return

        existente = com_retry(lambda: relacao_entre(usuario.id, alvo.id))
        if existente and pedido_expirou(existente):
            limpar_pedidos_expirados(usuario.id)
            existente = None

        if existente:
            if existente.status == 'blocked':
                if existente.requester_id == usuario.id:
                    emit('erro_bazinga', {'msg': f'Você bloqueou {alvo.name}. Desbloqueie em Amigos > Bloqueados para adicionar.'})
                else:
                    # Não revela que foi bloqueado.
                    emit('erro_bazinga', {'msg': f'Não foi possível enviar o pedido para {alvo.name}.'})
            elif existente.status == 'accepted':
                emit('erro_bazinga', {'msg': f'Você já é amigo de {alvo.name}.'})
            elif existente.requester_id == alvo.id:
                # A outra pessoa já tinha pedido: pedir de volta = aceitar.
                _aceitar_pedido(existente, usuario)
            elif existente.rapida:
                # Conversa rápida que EU puxei: "Adicionar amigo" a transforma em pedido de verdade.
                def virar_pedido():
                    existente.rapida = False
                    existente.oculta_req = False
                    existente.created_at = br_now()

                comitar_com_retry(virar_pedido)
                emit('pedido_amizade_enviado', {'para': alvo.name, 'para_id': alvo.id})
                emit('pedido_amizade_recebido', {
                    'de_id': usuario.id, 'de_nome': usuario.name, 'de_avatar': usuario.avatar,
                    'pedido_id': existente.id
                }, to=sala_pessoal(alvo.id))
                criar_notificacao(alvo.id, 'amizade', f'{usuario.name} quer ser seu amigo',
                                  'O pedido vale por 24 horas.', de_id=usuario.id, ref=str(usuario.id))
                emitir_amizades(usuario.id)
                emitir_amizades(alvo.id)
            else:
                emit('erro_bazinga', {'msg': f'Você já enviou um pedido para {alvo.name}. Aguarde a resposta (vale por 24h).'})
            return

        def preparar():
            novo = Friendship(requester_id=usuario.id, addressee_id=alvo.id, status='pending')
            db.session.add(novo)
            return novo

        pedido = comitar_com_retry(preparar)

        emit('pedido_amizade_enviado', {'para': alvo.name, 'para_id': alvo.id})
        emit('pedido_amizade_recebido', {
            'de_id': usuario.id, 'de_nome': usuario.name, 'de_avatar': usuario.avatar,
            'pedido_id': pedido.id
        }, to=sala_pessoal(alvo.id))
        criar_notificacao(alvo.id, 'amizade', f'{usuario.name} quer ser seu amigo',
                          'O pedido vale por 24 horas.', de_id=usuario.id, ref=str(usuario.id))
        emitir_amizades(usuario.id)
        emitir_amizades(alvo.id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PEDIDO AMIZADE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível enviar o pedido: {e}'})


@socketio.on('listar_pedidos_pendentes')
def listar_pedidos_pendentes(dados=None):
    """Compatível com o cliente antigo; a tela nova usa `listar_amizades`."""
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        limpar_pedidos_expirados(usuario.id)
        pedidos = com_retry(lambda: Friendship.query.filter_by(
            addressee_id=usuario.id, status='pending').all())
        emit('pedidos_pendentes', {
            'pedidos': [{'id': f.id, 'de_id': f.requester_id,
                        'de_nome': f.requester.name, 'de_avatar': f.requester.avatar} for f in pedidos]
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LISTAR PEDIDOS] {e}")


@socketio.on('responder_pedido_amizade')
def responder_pedido_amizade(dados):
    """acao: 'aceitar' | 'recusar' | 'bloquear' (ou o antigo `aceitar: true/false`)."""
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        pedido = com_retry(lambda: Friendship.query.get(dados.get('pedido_id')))
        # Só quem RECEBEU responde - quem enviou não pode aceitar o próprio pedido.
        if not pedido or pedido.addressee_id != usuario.id or pedido.status != 'pending':
            return
        if pedido_expirou(pedido):
            limpar_pedidos_expirados(usuario.id)
            emit('erro_bazinga', {'msg': 'Esse pedido de amizade expirou (valia 24h).'})
            emitir_amizades(usuario.id)
            return

        acao = dados.get('acao') or ('aceitar' if dados.get('aceitar') else 'recusar')
        solicitante_id = pedido.requester_id
        solicitante_nome = pedido.requester.name

        if acao == 'aceitar':
            _aceitar_pedido(pedido, usuario)
        elif acao == 'bloquear':
            def preparar():
                pedido.requester_id, pedido.addressee_id = usuario.id, solicitante_id
                pedido.status = 'blocked'
            comitar_com_retry(preparar)
            emit('pedido_amizade_respondido', {'aceito': False, 'de_id': solicitante_id})
            emitir_amizades(usuario.id)
            emitir_amizades(solicitante_id)
        else:
            def preparar():
                if pedido.rapida and not pedido.oculta_req:
                    # Conversa rápida: recusar só tira do SEU lado. Quem puxou continua vendo
                    # (sem saber que foi recusada) até as 24h acabarem.
                    pedido.oculta_dest = True
                else:
                    db.session.delete(pedido)
            comitar_com_retry(preparar)
            emit('pedido_amizade_respondido', {'aceito': False, 'de_id': solicitante_id})
            emitir_amizades(usuario.id)
            emitir_amizades(solicitante_id)

        print(f"[AMIZADE] {usuario.name} -> {acao} o pedido de {solicitante_nome}")
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO RESPONDER PEDIDO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível responder ao pedido: {e}'})


@socketio.on('cancelar_pedido_amizade')
def cancelar_pedido_amizade(dados):
    """Quem enviou desiste do pedido enquanto ele está pendente."""
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        pedido = com_retry(lambda: Friendship.query.get(dados.get('pedido_id')))
        if not pedido or pedido.requester_id != usuario.id or pedido.status != 'pending':
            return
        outro_id = pedido.addressee_id

        def preparar():
            if pedido.rapida and not pedido.oculta_dest:
                # Fechar uma conversa rápida some só do seu lado; a outra pessoa ainda pode ler
                # e, se aceitar, o pedido volta pra você decidir.
                pedido.oculta_req = True
            else:
                db.session.delete(pedido)

        comitar_com_retry(preparar)
        emitir_amizades(usuario.id)
        emitir_amizades(outro_id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CANCELAR PEDIDO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível cancelar o pedido: {e}'})


@socketio.on('remover_amigo')
def remover_amigo(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        amigo_id = int(dados.get('amigo_id'))
        pedido = com_retry(lambda: Friendship.query.filter(
            Friendship.status == 'accepted',
            or_(and_(Friendship.requester_id == usuario.id, Friendship.addressee_id == amigo_id),
                and_(Friendship.requester_id == amigo_id, Friendship.addressee_id == usuario.id))
        ).first())
        if not pedido:
            return

        def preparar():
            db.session.delete(pedido)

        comitar_com_retry(preparar)
        emit('amigo_removido', {'amigo_id': amigo_id})
        emit('amigo_removido', {'amigo_id': usuario.id}, to=sala_pessoal(amigo_id))
        emitir_amizades(usuario.id)
        emitir_amizades(amigo_id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO REMOVER AMIGO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível desfazer a amizade: {e}'})


@socketio.on('silenciar_contato')
def silenciar_contato(dados):
    """Silencia/desilencia um contato (sem som, toast, badge nem caixa de entrada)."""
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        alvo_id = int(dados.get('alvo_id'))
        ativo = bool(dados.get('ativo'))
        if alvo_id == usuario.id:
            return

        def preparar():
            existente = Silenciado.query.filter_by(person_id=usuario.id, alvo_id=alvo_id).first()
            if ativo and not existente:
                db.session.add(Silenciado(person_id=usuario.id, alvo_id=alvo_id))
            elif not ativo and existente:
                db.session.delete(existente)

        comitar_com_retry(preparar)
        emitir_amizades(usuario.id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO SILENCIAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível silenciar: {e}'})


@socketio.on('bloquear_usuario')
def bloquear_usuario(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        alvo_id = int(dados.get('usuario_id'))
    except (TypeError, ValueError):
        return
    if alvo_id == usuario.id:
        return

    try:
        alvo = com_retry(lambda: Person.query.get(alvo_id))
        if not alvo:
            return
        rel = com_retry(lambda: relacao_entre(usuario.id, alvo_id))
        eram_amigos = bool(rel and rel.status == 'accepted')

        def preparar():
            r = rel
            if r is None:
                r = Friendship(requester_id=usuario.id, addressee_id=alvo_id, status='blocked')
                db.session.add(r)
            else:
                r.requester_id, r.addressee_id = usuario.id, alvo_id
                r.status = 'blocked'

        comitar_com_retry(preparar)
        if eram_amigos:
            emit('amigo_removido', {'amigo_id': alvo_id})
            emit('amigo_removido', {'amigo_id': usuario.id}, to=sala_pessoal(alvo_id))
        emit('usuario_bloqueado', {'usuario_id': alvo_id, 'nome': alvo.name})
        emitir_amizades(usuario.id)
        emitir_amizades(alvo_id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO BLOQUEAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível bloquear: {e}'})


@socketio.on('desbloquear_usuario')
def desbloquear_usuario(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        alvo_id = int(dados.get('usuario_id'))
        rel = com_retry(lambda: relacao_entre(usuario.id, alvo_id))
        if not rel or rel.status != 'blocked' or rel.requester_id != usuario.id:
            return

        def preparar():
            db.session.delete(rel)

        comitar_com_retry(preparar)
        emitir_amizades(usuario.id)
        emitir_amizades(alvo_id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO DESBLOQUEAR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível desbloquear: {e}'})


# ==========================================
# CAIXA DE ENTRADA (notificações guardadas) - DM, pedido de amizade e menção
# ------------------------------------------------------------
# A de DM é agregada por remetente (uma linha com contador, não 200 linhas).
# O som/toast quem decide é o cliente (respeita "Não perturbar"); aqui só guarda
# e avisa ao vivo.
# ==========================================
def notificacao_json(n):
    return {
        'id': n.id, 'tipo': n.tipo, 'titulo': n.titulo, 'texto': n.texto, 'de_id': n.de_id,
        'ref': n.ref, 'quantidade': n.quantidade or 1, 'lida': bool(n.lida),
        'idade_s': max(0, int((br_now() - (n.atualizada_em or n.created_at or br_now())).total_seconds()))
    }


def criar_notificacao(destino_id, tipo, titulo, texto=None, de_id=None, ref=None, agrupar=False):
    """Guarda na caixa de entrada e avisa a sala pessoal. Nunca quebra quem chamou."""
    try:
        def preparar():
            n = None
            if agrupar:
                n = Notificacao.query.filter_by(person_id=destino_id, tipo=tipo, de_id=de_id, lida=False).first()
            if n:
                n.quantidade = (n.quantidade or 1) + 1
                n.titulo = titulo[:120]
                n.texto = (texto or '')[:300] or None
                n.atualizada_em = br_now()
            else:
                n = Notificacao(person_id=destino_id, tipo=tipo, de_id=de_id, titulo=titulo[:120],
                                texto=(texto or '')[:300] or None, ref=ref, quantidade=1, lida=False)
                db.session.add(n)
            return n

        n = comitar_com_retry(preparar)
        emit('notificacao_nova', notificacao_json(n), to=sala_pessoal(destino_id))
        return n
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO NOTIFICACAO] {e}")
        return None


def enviar_notificacoes(usuario):
    itens = Notificacao.query.filter_by(person_id=usuario.id).order_by(Notificacao.atualizada_em.desc()).limit(50).all()
    nao_lidas = Notificacao.query.filter_by(person_id=usuario.id, lida=False).count()
    emit('notificacoes', {'itens': [notificacao_json(n) for n in itens], 'nao_lidas': nao_lidas})


@socketio.on('listar_notificacoes')
def listar_notificacoes(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        com_retry(lambda: enviar_notificacoes(usuario))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LISTAR NOTIFICACOES] {e}")


@socketio.on('marcar_notificacoes_lidas')
def marcar_notificacoes_lidas(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    ids = (dados or {}).get('ids')
    try:
        def preparar():
            q = Notificacao.query.filter_by(person_id=usuario.id, lida=False)
            if ids:
                q = q.filter(Notificacao.id.in_([int(i) for i in ids[:100]]))
            q.update({'lida': True}, synchronize_session=False)

        comitar_com_retry(preparar)
        com_retry(lambda: enviar_notificacoes(usuario))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MARCAR NOTIFICACOES] {e}")


@socketio.on('limpar_notificacoes')
def limpar_notificacoes(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        def preparar():
            Notificacao.query.filter_by(person_id=usuario.id).delete(synchronize_session=False)

        comitar_com_retry(preparar)
        com_retry(lambda: enviar_notificacoes(usuario))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LIMPAR NOTIFICACOES] {e}")


# ==========================================
# EVENTOS PARA MENSAGENS DIRETAS (DMs)
# ==========================================
@socketio.on('entrar_dm')
def on_entrar_dm(data):
    # Cada usuário fica na própria sala pessoal (já entrou no connect), então
    # não existe mais uma sala por par de usuários. Mantido por compatibilidade
    # com o frontend, que ainda emite este evento ao abrir uma conversa.
    usuario = usuario_logado()
    if usuario:
        join_room(sala_pessoal(usuario.id))


def anexo_dm_valido(url):
    url = str(url or '')
    return bool(url) and len(url) <= 500 and (
        url.startswith('/') or url.startswith('https://res.cloudinary.com/')
        or bool(re.match(r'^https://media\d*\.giphy\.com/', url)))


@socketio.on('enviar_mensagem_direta')
def on_enviar_mensagem_direta(data):
    usuario = usuario_logado()
    if not usuario:
        print("[ERRO DM] Usuário não está logado na sessão.")
        return

    try:
        target_id = int(data.get('target_id'))
    except (TypeError, ValueError):
        return

    texto = (data.get('texto') or '').strip()[:2000]

    # Anexo (foto/gif/vídeo/arquivo): sobe por /api/upload e chega só como URL;
    # GIF do Giphy vem direto do CDN deles (mesma regra das mensagens de canal).
    anexo_url = data.get('anexo_url') if anexo_dm_valido(data.get('anexo_url')) else None
    anexo_tipo = data.get('anexo_tipo') if data.get('anexo_tipo') in ('image', 'video', 'file') else None
    anexo_nome = (data.get('anexo_nome') or '').strip()[:255] or None
    if not anexo_url:
        anexo_tipo = anexo_nome = None
    elif not anexo_tipo:
        anexo_tipo = 'image'

    if not texto and not anexo_url:
        return

    try:
        destinatario = com_retry(lambda: Person.query.get(target_id))
        if not destinatario:
            emit('erro_bazinga', {'msg': 'Esse usuário não existe mais.'})
            return
        # A relação é buscada UMA vez e serve pra checar permissão e decidir a conversa rápida (antes eram 2 idas
        # iguais ao Neon antes de a mensagem sair - parte do "DM demora pra atualizar").
        rel = None if target_id == usuario.id else com_retry(lambda: relacao_entre(usuario.id, target_id))
        if not com_retry(lambda: pode_trocar_dm(usuario, destinatario, rel)):
            emit('erro_bazinga', {'msg': f'Você não pode mandar mensagem para {destinatario.name} agora.'})
            return

        # Primeira mensagem pra alguém que não é amigo (e não tem pedido): nasce uma CONVERSA RÁPIDA,
        # um pedido pendente de 24h com as mensagens temporárias. Quem recebe vê Aceitar/Recusar/Bloquear.
        if rel and pedido_expirou(rel):
            limpar_pedidos_expirados(usuario.id)
            rel = None
        criar_rapida = target_id != usuario.id and rel is None
        oculto_pro_destino = False
        if rel and rel.status == 'pending':
            oculto_pro_destino = oculta_pra(rel, target_id)

        def preparar():
            if criar_rapida:
                db.session.add(Friendship(requester_id=usuario.id, addressee_id=target_id,
                                          status='pending', rapida=True))
            elif rel and rel.status == 'pending' and oculta_pra(rel, usuario.id):
                # eu tinha fechado essa conversa e voltei a escrever nela: ela reaparece pra mim
                if rel.requester_id == usuario.id:
                    rel.oculta_req = False
                else:
                    rel.oculta_dest = False
            # content '' (e não None) quando é só anexo: a coluna do Neon ainda pode ser NOT NULL.
            nova = DirectMessage(sender_id=usuario.id, receiver_id=target_id, content=texto or '',
                                 attachment_url=anexo_url, attachment_type=anexo_tipo,
                                 attachment_name=anexo_nome, lida=(target_id == usuario.id))
            db.session.add(nova)
            return nova

        nova_msg = comitar_com_retry(preparar)

        payload = {
            'id': nova_msg.id,
            'usuario': usuario.name,
            'usuario_id': usuario.id,
            'destinatario_id': target_id,
            'avatar': usuario.avatar,
            'nome_estilo': usuario.nome_estilo, 'moldura': usuario.moldura, 'equipados': equipados_da_pessoa(usuario),
            'texto': nova_msg.content or '',
            'anexo_url': nova_msg.attachment_url,
            'anexo_tipo': nova_msg.attachment_type,
            'anexo_nome': nova_msg.attachment_name,
            'hora': hora_formatada(nova_msg.timestamp),
            'cor': usuario.role.color if usuario.role else '#5865F2',
            # Ecoa pra quem mandou trocar a bolha otimista pela real, sem duplicar.
            'temp_id': temp_id_seguro(data)
        }

        # Vai só para as duas pessoas da conversa (e não para uma sala
        # compartilhada em que qualquer um poderia ter entrado).
        # Quem já recusou/fechou essa conversa não recebe mais nada dela (nem aviso).
        salas = {sala_pessoal(usuario.id)}
        if not oculto_pro_destino:
            salas.add(sala_pessoal(target_id))
        for sala in salas:
            emit('receber_mensagem_direta', payload, to=sala)

        if criar_rapida:
            # o retrato das amizades faz a conversa aparecer pros dois; o aviso é o da própria mensagem
            emitir_amizades(usuario.id)
            emitir_amizades(target_id)

        # Caixa de entrada + aviso (som/toast) pra quem recebeu - não pra si mesmo, nem se ele silenciou.
        if target_id != usuario.id and not oculto_pro_destino:
            silenciou = com_retry(lambda: Silenciado.query.filter_by(person_id=target_id, alvo_id=usuario.id).first())
            if not silenciou:
                resumo = texto[:140] if texto else ('📎 ' + (anexo_nome or 'Anexo'))
                criar_notificacao(target_id, 'dm', usuario.name, resumo, de_id=usuario.id,
                                  ref=str(usuario.id), agrupar=True)

        resultado_xp = conceder_xp_por_mensagem(usuario)
        if resultado_xp:
            emit('xp_atualizado', resultado_xp, to=sala_pessoal(usuario.id))
        _emitir_progresso(usuario, {'dm': 1})

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRÍTICO NA DM] O banco bloqueou o salvamento: {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível enviar a DM: {e}'})


@socketio.on('marcar_dm_lida')
def marcar_dm_lida(dados):
    """A pessoa abriu a conversa: zera o contador de não lidas (em todas as abas dela)."""
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        amigo_id = int(dados.get('amigo_id'))

        def preparar():
            DirectMessage.query.filter(
                DirectMessage.receiver_id == usuario.id, DirectMessage.sender_id == amigo_id,
                DirectMessage.lida == False  # noqa: E712
            ).update({'lida': True}, synchronize_session=False)
            Notificacao.query.filter_by(person_id=usuario.id, tipo='dm', de_id=amigo_id, lida=False
                                        ).update({'lida': True}, synchronize_session=False)

        comitar_com_retry(preparar)
        emit('dm_lidas', {'amigo_id': amigo_id}, to=sala_pessoal(usuario.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MARCAR DM LIDA] {e}")


def contagem_dms_nao_lidas(usuario):
    linhas = db.session.query(DirectMessage.sender_id, func.count(DirectMessage.id)).filter(
        DirectMessage.receiver_id == usuario.id, DirectMessage.sender_id != usuario.id,
        DirectMessage.lida == False  # noqa: E712
    ).group_by(DirectMessage.sender_id).all()
    return {str(i): n for i, n in linhas}


# ==========================================
# CONVITES (link e QR code)
# ==========================================
def convite_para_json(cv):
    return {
        'code': cv.code,
        'server_id': cv.server_id,
        'server_name': cv.server.name if cv.server else '',
        'expira_em': cv.expires_at.strftime('%d/%m/%Y %H:%M') if cv.expires_at else None,
        'max_usos': cv.max_uses,
        'usos': cv.uses or 0,
        'criado_por': cv.creator.name if cv.creator else '???'
    }


@socketio.on('criar_convite')
def criar_convite(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        # Qualquer MEMBRO convida (antes só o dono: "não gera convite, só adm"). Quem não é dono tem teto: o link vale
        # no máximo 7 dias e 25 pessoas - convite sem fim/sem limite continua sendo coisa de dono.
        try:
            srv = Server.query.get(int(dados.get('server_id')))
        except (TypeError, ValueError):
            srv = None
        if not srv or not eh_membro(usuario, srv.id):
            emit('erro_bazinga', {'msg': 'Você precisa estar no servidor pra convidar alguém.'})
            return
        sou_dono = pode_gerenciar_servidor(usuario, srv)

        duracao = _parse_ilimitado(dados.get('duracao'))     # horas, None = nunca expira
        max_usos = _parse_ilimitado(dados.get('max_usos'))   # None = ilimitado
        if not sou_dono:
            duracao = min(duracao or 168, 168)
            max_usos = min(max_usos or 25, 25)
        expira_em = br_now() + timedelta(hours=duracao) if duracao else None

        def preparar():
            convite = Invite(
                code=gerar_codigo_convite(), server_id=srv.id, creator_id=usuario.id,
                expires_at=expira_em, max_uses=max_usos, uses=0
            )
            db.session.add(convite)
            return convite

        convite = comitar_com_retry(preparar)
        emit('convite_criado', convite_para_json(convite))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRIAR CONVITE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível criar o convite: {e}'})


@socketio.on('listar_convites')
def listar_convites(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = servidor_gerenciavel(usuario, dados.get('server_id'))
        if not srv:
            return

        convites = com_retry(lambda: Invite.query.filter_by(server_id=srv.id)
                             .order_by(Invite.created_at.desc()).all())
        emit('convites_do_servidor', {
            'server_id': srv.id,
            'convites': [convite_para_json(c) for c in convites if c.esta_valido()]
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LISTAR CONVITES] {e}")


@socketio.on('apagar_convite')
def apagar_convite(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        convite = com_retry(lambda: Invite.query.filter_by(code=dados.get('code')).first())
        if not convite:
            return
        if not servidor_gerenciavel(usuario, convite.server_id):
            return

        codigo = convite.code

        def preparar():
            db.session.delete(convite)

        comitar_com_retry(preparar)
        emit('convite_apagado', {'code': codigo})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR CONVITE] {e}")


@socketio.on('entrar_por_convite')
def entrar_por_convite(dados):
    """Usado quando a pessoa cola o código direto na plataforma (sem abrir o link)."""
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        codigo = (dados.get('code') or '').strip().lower()
        # Aceita tanto o código puro quanto o link inteiro colado.
        if '/convite/' in codigo:
            codigo = codigo.rsplit('/convite/', 1)[-1].split('?')[0].strip('/')

        convite = com_retry(lambda: Invite.query.filter_by(code=codigo).first())
        if not convite or not convite.esta_valido():
            emit('erro_bazinga', {'msg': 'Convite inválido ou expirado.'})
            return

        srv = Server.query.get(convite.server_id)
        if not srv:
            emit('erro_bazinga', {'msg': 'Esse servidor não existe mais.'})
            return

        if usuario in srv.members:
            join_room(sala_servidor(srv.id))
            emit('servidor_discord_criado', servidor_para_json(srv, usuario))
            emit('erro_bazinga', {'msg': f'Você já está em {srv.name}.'})
            return

        def preparar():
            srv.members.append(usuario)
            convite.uses = (convite.uses or 0) + 1

        comitar_com_retry(preparar)

        join_room(sala_servidor(srv.id))
        emit('servidor_discord_criado', servidor_para_json(srv, usuario))
        emit('entrou_por_convite', {'server_id': srv.id, 'server_name': srv.name})
        emit('membro_entrou_servidor', {
            'server_id': srv.id,
            'membro': {'id': usuario.id, 'nome': usuario.name, 'avatar': usuario.avatar}
        }, to=sala_servidor(srv.id), include_self=False)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ENTRAR POR CONVITE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível entrar pelo convite: {e}'})


# ==========================================
# CALENDÁRIO DE EVENTOS
# ==========================================
def evento_para_json(ev):
    return {
        'id': ev.id,
        'server_id': ev.server_id,
        'titulo': ev.title,
        'descricao': ev.description,
        # ISO para o JS montar a data sem depender de parsing de formato BR
        'inicio': ev.starts_at.isoformat() if ev.starts_at else None,
        'fim': ev.ends_at.isoformat() if ev.ends_at else None,
        'emoji': ev.emoji or '🎉',
        'cor': ev.color or '#5865F2',
        'criador': ev.creator.name if ev.creator else '???',
        'criador_id': ev.creator_id
    }


def _parse_data_evento(valor):
    """Converte 'YYYY-MM-DDTHH:MM' (o que o <input type=datetime-local> manda)."""
    if not valor:
        return None
    from datetime import datetime
    texto = str(valor).strip().replace(' ', 'T')[:16]
    try:
        return datetime.strptime(texto, '%Y-%m-%dT%H:%M')
    except ValueError:
        return None


@socketio.on('listar_eventos')
def listar_eventos(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = com_retry(lambda: Server.query.get(int(dados.get('server_id'))))
        # Ver o calendário é pra qualquer membro; só mexer é que exige permissão.
        if not srv or usuario not in srv.members:
            return

        eventos = com_retry(lambda: Event.query.filter_by(server_id=srv.id)
                            .order_by(Event.starts_at.asc()).all())
        emit('eventos_do_servidor', {
            'server_id': srv.id,
            'pode_gerenciar': pode_gerenciar_servidor(usuario, srv),
            'eventos': [evento_para_json(e) for e in eventos]
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO LISTAR EVENTOS] (rode atualizar_banco.py se for erro de tabela): {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível carregar o calendário: {e}'})


@socketio.on('criar_evento')
def criar_evento(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        srv = servidor_gerenciavel(usuario, dados.get('server_id'))
        if not srv:
            emit('erro_bazinga', {'msg': 'Você não tem permissão para criar eventos aqui.'})
            return

        titulo = (dados.get('titulo') or '').strip()[:120]
        inicio = _parse_data_evento(dados.get('inicio'))
        if not titulo or not inicio:
            emit('erro_bazinga', {'msg': 'O evento precisa de um título e uma data de início.'})
            return

        def preparar():
            ev = Event(
                server_id=srv.id, creator_id=usuario.id,
                title=titulo,
                description=(dados.get('descricao') or '').strip()[:1000] or None,
                starts_at=inicio,
                ends_at=_parse_data_evento(dados.get('fim')),
                emoji=(dados.get('emoji') or '🎉')[:16],
                color=dados.get('cor') or '#5865F2'
            )
            db.session.add(ev)
            return ev

        ev = comitar_com_retry(preparar)
        emit('evento_criado', evento_para_json(ev), to=sala_servidor(srv.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRIAR EVENTO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível criar o evento: {e}'})


@socketio.on('editar_evento')
def editar_evento(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        ev = com_retry(lambda: Event.query.get(dados.get('id')))
        if not ev:
            return
        srv = servidor_gerenciavel(usuario, ev.server_id)
        if not srv:
            emit('erro_bazinga', {'msg': 'Você não tem permissão para editar eventos aqui.'})
            return

        def preparar():
            if 'titulo' in dados:
                titulo = (dados.get('titulo') or '').strip()[:120]
                if titulo:
                    ev.title = titulo
            if 'descricao' in dados:
                ev.description = (dados.get('descricao') or '').strip()[:1000] or None
            if 'inicio' in dados:
                inicio = _parse_data_evento(dados.get('inicio'))
                if inicio:
                    ev.starts_at = inicio
            if 'fim' in dados:
                ev.ends_at = _parse_data_evento(dados.get('fim'))
            if 'emoji' in dados:
                ev.emoji = (dados.get('emoji') or '🎉')[:16]
            if 'cor' in dados:
                ev.color = dados.get('cor') or ev.color

        comitar_com_retry(preparar)
        emit('evento_editado', evento_para_json(ev), to=sala_servidor(srv.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EDITAR EVENTO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível editar o evento: {e}'})


@socketio.on('apagar_evento')
def apagar_evento(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        ev = com_retry(lambda: Event.query.get(dados.get('id')))
        if not ev:
            return
        srv = servidor_gerenciavel(usuario, ev.server_id)
        if not srv:
            emit('erro_bazinga', {'msg': 'Você não tem permissão para apagar eventos aqui.'})
            return

        ev_id, server_id = ev.id, srv.id

        def preparar():
            db.session.delete(ev)

        comitar_com_retry(preparar)
        emit('evento_apagado', {'id': ev_id, 'server_id': server_id},
             to=sala_servidor(server_id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR EVENTO] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar o evento: {e}'})

