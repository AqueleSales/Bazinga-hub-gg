from flask import session, request
from flask_socketio import emit, join_room, leave_room
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, and_
from datetime import timedelta
import re
from . import socketio
from .models import (db, br_now, Message, Person, DirectMessage, Server, Channel,
                     GeoNote, MapServer, Reaction, Invite, Event, Friendship)
from .utils import (com_retry, comitar_com_retry, canal_permitido, pode_ver_canal,
                    servidor_gerenciavel, pode_gerenciar_servidor, gerar_codigo_convite)


def usuario_logado():
    """Busca a Person da sessão atual, ou None se não estiver logado."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    try:
        return com_retry(lambda: Person.query.get(user_id))
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


def _entrar_em_call(chave, peer_id, usuario):
    lista = participantes_call.setdefault(chave, [])
    lista[:] = [p for p in lista if p['peer_id'] != peer_id]
    lista.append({'peer_id': peer_id, 'usuario_id': usuario.id, 'nome': usuario.name, 'avatar': usuario.avatar})
    _call_por_sid[request.sid] = (chave, peer_id)


def _sair_de_call(chave, peer_id):
    lista = participantes_call.get(chave)
    if lista is not None:
        lista[:] = [p for p in lista if p['peer_id'] != peer_id]
        if not lista:
            participantes_call.pop(chave, None)
    _call_por_sid.pop(request.sid, None)


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


def servidor_para_json(srv, usuario=None):
    """Servidor + canais. Canal privado só entra na lista de quem tem acesso.

    Sem o `usuario`, devolve todos os canais - use só quando o destinatário
    for o próprio dono.
    """
    canais = Channel.query.filter_by(server_id=srv.id).order_by(
        Channel.position.asc(), Channel.id.asc()).all()
    if usuario is not None:
        canais = [c for c in canais if pode_ver_canal(usuario, c)]

    return {
        'id': srv.id,
        'name': srv.name,
        'iconUrl': srv.icon_url,
        'description': srv.description,
        'bannerColor': srv.banner_color,
        'owner_id': srv.owner_id,
        'membros': len(srv.members),
        'channels': [canal_para_json(c) for c in canais]
    }


def avisar_servidor(srv):
    """Reenvia o servidor inteiro para todos os membros conectados.

    Usado depois de qualquer mudança estrutural (nome, ícone, canais). Cada
    membro recebe a sua própria versão, porque a lista de canais depende de
    quais canais privados a pessoa pode ver.
    """
    for membro in srv.members:
        emit('servidor_discord_criado', servidor_para_json(srv, membro),
             to=sala_pessoal(membro.id))


# ==========================================
# CONEXÃO: Carrega os servidores do usuário e entra na sala pessoal
# (para DMs em tempo real) e nas salas dos servidores dele.
# ==========================================
@socketio.on('connect')
def handle_connect():
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        join_room(sala_pessoal(usuario.id))

        servidores = [servidor_para_json(srv, usuario) for srv in usuario.servers]
        for srv in usuario.servers:
            join_room(sala_servidor(srv.id))

        emit('carregar_meus_servidores', servidores)

        # Só avisa quem divide servidor com ela quando é o PRIMEIRO socket
        # dela (outra aba/dispositivo já conectado não deve gerar aviso de novo).
        era_offline = not esta_online(usuario.id)
        usuarios_conectados[usuario.id] = usuarios_conectados.get(usuario.id, 0) + 1
        amigos = amigos_de(usuario)
        if era_offline:
            for srv in usuario.servers:
                emit('usuario_ficou_online', {'usuario_id': usuario.id}, to=sala_servidor(srv.id), include_self=False)
            for amigo in amigos:
                emit('usuario_ficou_online', {'usuario_id': usuario.id}, to=sala_pessoal(amigo.id))

        # Snapshot de quem já tá online agora, pra corrigir a lista de amigos
        # que a página carregou "todo mundo offline" por padrão.
        emit('status_amigos_ao_conectar', {'online_ids': [a.id for a in amigos if esta_online(a.id)]})
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CONNECT] {e}")


@socketio.on('disconnect')
def handle_disconnect():
    # Queda de rede/aba fechada à força não passa por sair_call (só o
    # beforeunload do navegador manda isso, e ele nem sempre roda a tempo) -
    # sem isso, quem caiu ficava "fantasma" na prévia de participantes da
    # call pro resto da sessão de todo mundo.
    call_info = _call_por_sid.pop(request.sid, None)
    if call_info:
        chave, peer_id = call_info
        sala_call = f"voz_{chave}"
        leave_room(sala_call)
        _sair_de_call(chave, peer_id)
        emit('usuario_saiu_call', {'peer_id': peer_id}, to=sala_call, include_self=False)
        try:
            if isinstance(chave, str) and chave.startswith('dm_'):
                _, id_a, id_b = chave.split('_')
                payload = {'canal_id': chave, 'participantes': participantes_call.get(chave, [])}
                emit('participantes_call_mudou', payload, to=sala_pessoal(int(id_a)))
                emit('participantes_call_mudou', payload, to=sala_pessoal(int(id_b)))
            else:
                canal = com_retry(lambda: Channel.query.get(int(chave)))
                if canal and canal.server_id:
                    emit('participantes_call_mudou',
                         {'canal_id': chave, 'participantes': participantes_call.get(chave, [])},
                         to=sala_servidor(canal.server_id))
        except Exception as e:
            print(f"[ERRO LIMPAR CALL NO DISCONNECT] {e}")

    usuario = usuario_logado()
    if not usuario or usuario.id not in usuarios_conectados:
        return

    try:
        usuarios_conectados[usuario.id] -= 1
        if usuarios_conectados[usuario.id] <= 0:
            del usuarios_conectados[usuario.id]
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
    anexo_url = dados.get('anexo_url')
    anexo_tipo = dados.get('anexo_tipo') if dados.get('anexo_tipo') in ('image', 'video') else None
    anexo_nome = (dados.get('anexo_nome') or '').strip()[:255] or None
    anexo_url_str = str(anexo_url) if anexo_url else ''
    if anexo_url and not (anexo_url_str.startswith('/') or anexo_url_str.startswith('https://res.cloudinary.com/')):
        anexo_url = None  # só aceita caminho do próprio site ou do Cloudinary, devolvidos pelo upload
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

    emit('receber_mensagem', {
        'id': nova_msg.id,
        'usuario': usuario.name,
        'usuario_id': usuario.id,
        'avatar': usuario.avatar,
        'texto': nova_msg.text or '',
        'anexo_url': nova_msg.attachment_url,
        'anexo_tipo': nova_msg.attachment_type,
        'anexo_nome': nova_msg.attachment_name,
        'hora': hora_formatada(nova_msg.timestamp),
        'cor': cor,
        # Ecoa de volta pra quem mandou trocar a bolha otimista pela real
        # sem duplicar (ver enviarMensagemOtimista() no chat.html).
        'temp_id': temp_id_seguro(dados)
    }, to=str(canal.id))


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

        def preparar():
            existente = Reaction.query.filter_by(
                message_id=msg.id, person_id=usuario.id, emoji=emoji).first()
            if existente:
                db.session.delete(existente)
            else:
                db.session.add(Reaction(message_id=msg.id, person_id=usuario.id, emoji=emoji))

        comitar_com_retry(preparar)

        emit('reacoes_atualizadas', {
            'msg_id': msg.id,
            'reacoes': reacoes_para_json(msg.id)
        }, to=str(msg.channel_id))
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
            channel_id=canal_id, is_pinned=True).order_by(Message.timestamp.desc()).all())

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
    if not peer_id:
        return

    canal_id_bruto = dados.get('canal_id')

    # Chamada 1-a-1 por DM: a "sala" é "dm_<menorId>_<maiorId>", não um
    # Channel de verdade - checa amizade em vez de canal_permitido.
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

        sala_call = f"voz_{canal_id_bruto}"
        join_room(sala_call)
        _entrar_em_call(canal_id_bruto, peer_id, usuario)
        emit('novo_usuario_call', {
            'peer_id': peer_id, 'usuario': usuario.name, 'avatar': usuario.avatar,
            'canal_id': canal_id_bruto
        }, to=sala_call, include_self=False)
        payload = {'canal_id': canal_id_bruto, 'participantes': participantes_call.get(canal_id_bruto, [])}
        emit('participantes_call_mudou', payload, to=sala_pessoal(usuario.id))
        emit('participantes_call_mudou', payload, to=sala_pessoal(outro_id))
        return

    canal = canal_permitido(usuario, canal_id_bruto)
    if not canal:
        emit('erro_bazinga', {'msg': 'Você não tem acesso a esse canal de voz.'})
        return

    chave = str(canal.id)
    sala_call = f"voz_{chave}"
    join_room(sala_call)
    _entrar_em_call(chave, peer_id, usuario)

    emit('novo_usuario_call', {
        'peer_id': peer_id,
        'usuario': usuario.name,
        'avatar': usuario.avatar,
        'canal_id': chave
    }, to=sala_call, include_self=False)

    # Pra quem está com o servidor aberto mas ainda não entrou na call -
    # é isso que dá a prévia de "fulano já está na call" antes de entrar.
    if canal.server_id:
        emit('participantes_call_mudou',
             {'canal_id': chave, 'participantes': participantes_call.get(chave, [])},
             to=sala_servidor(canal.server_id))


@socketio.on('listar_participantes_call')
def listar_participantes_call(dados):
    """Prévia sob demanda: chamado ao abrir um servidor/DM, sem esperar
    alguém entrar ou sair de uma call pra saber quem já está nela."""
    usuario = usuario_logado()
    if not usuario:
        return

    canal_id_bruto = dados.get('canal_id')
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


@socketio.on('sair_call')
def lidar_sair_call(dados):
    canal_id = dados.get('canal_id')
    peer_id = dados.get('peer_id')
    if canal_id is None:
        return

    chave = str(canal_id) if not (isinstance(canal_id, str) and canal_id.startswith('dm_')) else canal_id
    sala_call = f"voz_{chave}"
    leave_room(sala_call)
    _sair_de_call(chave, peer_id)
    emit('usuario_saiu_call', {'peer_id': peer_id}, to=sala_call, include_self=False)

    try:
        if isinstance(chave, str) and chave.startswith('dm_'):
            _, id_a, id_b = chave.split('_')
            payload = {'canal_id': chave, 'participantes': participantes_call.get(chave, [])}
            emit('participantes_call_mudou', payload, to=sala_pessoal(int(id_a)))
            emit('participantes_call_mudou', payload, to=sala_pessoal(int(id_b)))
        else:
            canal = com_retry(lambda: Channel.query.get(canal_id))
            if canal and canal.server_id:
                emit('participantes_call_mudou',
                     {'canal_id': chave, 'participantes': participantes_call.get(chave, [])},
                     to=sala_servidor(canal.server_id))
    except Exception as e:
        print(f"[ERRO SAIR CALL] {e}")


# ==========================================
# CHAMADA 1-A-1 POR DM (toque + aceitar, igual Discord)
# ------------------------------------------------------------
# Só o "toque": avisa o amigo e espera ele aceitar/recusar. A call em si (depois
# de aceita) reaproveita entrar_call/sair_call de cima, com canal_id no formato
# "dm_<menorId>_<maiorId>" (ver sala_dm()).
# ==========================================
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

    sala = sala_dm(usuario.id, de_id)
    # Avisa os dois lados (quem aceitou também precisa do nome da sala pra entrar).
    emit('chamada_aceita', {'com_id': de_id, 'sala': sala}, include_self=True)
    emit('chamada_aceita', {'com_id': usuario.id, 'sala': sala}, to=sala_pessoal(de_id))


@socketio.on('recusar_chamada')
def recusar_chamada(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        de_id = int(dados.get('de_id'))
    except (TypeError, ValueError):
        return
    emit('chamada_recusada', {'por_nome': usuario.name}, to=sala_pessoal(de_id))


@socketio.on('cancelar_chamada')
def cancelar_chamada(dados):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
        para_id = int(dados.get('para_id'))
    except (TypeError, ValueError):
        return
    emit('chamada_cancelada', {}, to=sala_pessoal(para_id))


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
        nome = (dados.get('nome') or f"Servidor de {usuario.name}").strip()[:100]
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
        nome = (dados.get('nome') or '').strip().lower().replace(' ', '-')[:100]
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
                'status': m.status or 'online',
                'online': esta_online(m.id)
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
                nome = (dados.get('nome') or '').strip().lower().replace(' ', '-')[:100]
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
                nome = (dados.get('nome') or '').strip()[:100]
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
                'vagas': pino.max_tickets if pino.max_tickets else 'ilimitado',
                'online': len(srv.members)
            }, broadcast=True)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO EDITAR SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar o servidor: {e}'})


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
# ==========================================
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


@socketio.on('criar_geonote')
def criar_geonote(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        texto = (dados.get('texto') or '').strip()[:280] or "Loot raro aqui!"
        cor = dados.get('cor') or '#5865F2'
        # Duração: o modelo e o /api/mapa/dados já filtram por expires_at, mas
        # isso aqui nunca era preenchido - toda nota virava eterna.
        duracao = _parse_ilimitado(dados.get('duracao'))
        expira_em = br_now() + timedelta(hours=duracao) if duracao else None

        def preparar():
            nota = GeoNote(
                lat=float(dados['lat']), lng=float(dados['lng']),
                text=texto, color=cor, author_id=usuario.id,
                duration_hours=duracao, expires_at=expira_em
            )
            db.session.add(nota)
            return nota

        nota = comitar_com_retry(preparar)

        emit('nova_geonote', {
            'id': nota.id, 'lat': nota.lat, 'lng': nota.lng,
            'texto': nota.text, 'autor': usuario.name, 'autor_id': usuario.id,
            'cor': nota.color
        }, broadcast=True)
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
                nota.text = (dados.get('texto') or '').strip()[:280] or nota.text
            if 'cor' in dados:
                nota.color = dados.get('cor') or nota.color

        comitar_com_retry(preparar)

        emit('geonote_editada', {
            'id': nota.id, 'texto': nota.text, 'cor': nota.color
        }, broadcast=True)
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
        emit('geonote_apagada', {'id': nota_id}, broadcast=True)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR GEONOTE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar a nota: {e}'})


@socketio.on('plantar_servidor')
def plantar_servidor(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        server_id = dados.get('server_id')
        srv = com_retry(lambda: Server.query.get(int(server_id))) if server_id else None
        if not srv or srv.owner_id != usuario.id:
            emit('erro_bazinga', {'msg': 'Você só pode plantar um servidor que você é dono.'})
            return

        vagas = _parse_ilimitado(dados.get('vagas'))
        duracao = _parse_ilimitado(dados.get('duracao'))
        expira_em = br_now() + timedelta(hours=duracao) if duracao else None

        def preparar():
            pino = MapServer(
                name=srv.name, lat=float(dados['lat']), lng=float(dados['lng']),
                max_tickets=vagas, duration_hours=duracao, expires_at=expira_em,
                owner_id=usuario.id, server_id=srv.id
            )
            db.session.add(pino)
            return pino

        pino = comitar_com_retry(preparar)

        emit('novo_servidor_mapa', {
            'id': pino.id, 'lat': pino.lat, 'lng': pino.lng,
            'nome': srv.name, 'icon_url': srv.icon_url,
            'owner': usuario.name, 'owner_id': usuario.id,
            'vagas': vagas if vagas else 'ilimitado',
            'online': len(srv.members),
            'server_id': srv.id
        }, broadcast=True)
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

        srv = Server.query.get(pino.server_id) if pino.server_id else None
        emit('servidor_mapa_editado', {
            'id': pino.id,
            'nome': srv.name if srv else pino.name,
            'icon_url': srv.icon_url if srv else None,
            'vagas': vagas if vagas else 'ilimitado',
            'online': len(srv.members) if srv else 1
        }, broadcast=True)
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

    try:
        payload = {
            'usuario_id': usuario.id,
            'nome': usuario.name,
            'avatar': usuario.avatar,
            'lat': float(dados['lat']),
            'lng': float(dados['lng'])
        }
        for srv in usuario.servers:
            emit('posicao_amigo_atualizada', payload,
                 to=sala_servidor(srv.id), include_self=False)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ATUALIZAR LOCALIZACAO] {e}")


# ==========================================
# PERFIL DO USUÁRIO
# ==========================================
@socketio.on('atualizar_perfil')
def atualizar_perfil(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        def preparar():
            if 'name' in dados:
                nome_novo = (dados.get('name') or '').strip()[:100]
                if nome_novo:
                    usuario.name = nome_novo
            if 'custom_status' in dados:
                usuario.custom_status = (dados.get('custom_status') or '').strip()[:128] or None
            if 'bio' in dados:
                usuario.bio = (dados.get('bio') or '').strip()[:1000] or None
            if 'banner_color' in dados:
                usuario.banner_color = dados.get('banner_color') or None
            avatar = dados.get('avatar')
            # blob: só existe na aba que criou - nunca salvar isso no banco.
            if avatar and not avatar.startswith('blob:'):
                usuario.avatar = avatar

        comitar_com_retry(preparar)
        emit('perfil_atualizado', {
            'name': usuario.name,
            'custom_status': usuario.custom_status,
            'bio': usuario.bio,
            'banner_color': usuario.banner_color,
            'avatar': usuario.avatar
        })

        # Nome/avatar aparecem em telas de quem não é "eu": lista de membros
        # de cada servidor. Sem isso, só quem editou via as próprias
        # (várias abas dele) via perfil_atualizado; o resto via F5.
        if 'name' in dados or dados.get('avatar'):
            payload_publico = {'usuario_id': usuario.id, 'nome': usuario.name, 'avatar': usuario.avatar}
            for srv in usuario.servers:
                emit('perfil_membro_mudou', payload_publico, to=sala_servidor(srv.id), include_self=False)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ATUALIZAR PERFIL] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível salvar o perfil: {e}'})


@socketio.on('mudar_status')
def mudar_status(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        status = dados.get('status')
        if status not in ('online', 'idle', 'dnd', 'invisible'):
            return

        def preparar():
            usuario.status = status

        comitar_com_retry(preparar)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MUDAR STATUS] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível mudar seu status: {e}'})


# ==========================================
# AMIZADES DE VERDADE
# ------------------------------------------------------------
# Antes /chat mostrava TODO MUNDO que existe no banco como "amigo" e o botão
# de pedido só dava um toast de sucesso sem salvar nada. Agora é uma
# Friendship (pending -> accepted) de verdade.
# ==========================================
def pessoa_para_json_amigo(p):
    return {'id': p.id, 'nome': p.name, 'avatar': p.avatar,
            'status': p.status or 'online', 'online': esta_online(p.id)}


@socketio.on('enviar_pedido_amizade')
def enviar_pedido_amizade(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    busca = (dados.get('busca') or '').strip()
    if not busca:
        return

    try:
        alvo = com_retry(lambda: Person.query.filter(
            or_(Person.name == busca, Person.email == busca)
        ).first())

        if not alvo:
            emit('erro_bazinga', {'msg': f'Não achei ninguém com "{busca}" na Bazinga.'})
            return
        if alvo.id == usuario.id:
            emit('erro_bazinga', {'msg': 'Você não pode adicionar a si mesmo.'})
            return

        existente = com_retry(lambda: Friendship.query.filter(
            or_(and_(Friendship.requester_id == usuario.id, Friendship.addressee_id == alvo.id),
                and_(Friendship.requester_id == alvo.id, Friendship.addressee_id == usuario.id))
        ).first())
        if existente:
            if existente.status == 'accepted':
                emit('erro_bazinga', {'msg': f'Você já é amigo de {alvo.name}.'})
            else:
                emit('erro_bazinga', {'msg': f'Já existe um pedido pendente com {alvo.name}.'})
            return

        def preparar():
            db.session.add(Friendship(requester_id=usuario.id, addressee_id=alvo.id, status='pending'))

        comitar_com_retry(preparar)

        emit('pedido_amizade_enviado', {'para': alvo.name})
        emit('pedido_amizade_recebido', {
            'de_id': usuario.id, 'de_nome': usuario.name, 'de_avatar': usuario.avatar
        }, to=sala_pessoal(alvo.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO PEDIDO AMIZADE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível enviar o pedido: {e}'})


@socketio.on('listar_pedidos_pendentes')
def listar_pedidos_pendentes(dados=None):
    usuario = usuario_logado()
    if not usuario:
        return
    try:
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
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        pedido = com_retry(lambda: Friendship.query.get(dados.get('pedido_id')))
        if not pedido or pedido.addressee_id != usuario.id or pedido.status != 'pending':
            return

        aceitar = bool(dados.get('aceitar'))
        solicitante_id = pedido.requester_id
        solicitante_nome = pedido.requester.name

        if aceitar:
            def preparar():
                pedido.status = 'accepted'
            comitar_com_retry(preparar)
            emit('pedido_amizade_respondido', {'aceito': True, 'amigo': pessoa_para_json_amigo(pedido.requester)})
            emit('pedido_amizade_respondido', {'aceito': True, 'amigo': pessoa_para_json_amigo(usuario)},
                 to=sala_pessoal(solicitante_id))
        else:
            def preparar():
                db.session.delete(pedido)
            comitar_com_retry(preparar)
            emit('pedido_amizade_respondido', {'aceito': False})

        print(f"[AMIZADE] {usuario.name} {'aceitou' if aceitar else 'recusou'} o pedido de {solicitante_nome}")
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO RESPONDER PEDIDO] {e}")


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
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO REMOVER AMIGO] {e}")


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
    if not texto:
        return

    try:
        destinatario = com_retry(lambda: Person.query.get(target_id))
        if not destinatario:
            emit('erro_bazinga', {'msg': 'Esse usuário não existe mais.'})
            return

        def preparar():
            nova = DirectMessage(sender_id=usuario.id, receiver_id=target_id, content=texto)
            db.session.add(nova)
            return nova

        nova_msg = comitar_com_retry(preparar)

        payload = {
            'id': nova_msg.id,
            'usuario': usuario.name,
            'usuario_id': usuario.id,
            'destinatario_id': target_id,
            'avatar': usuario.avatar,
            'texto': nova_msg.content,
            'hora': hora_formatada(nova_msg.timestamp),
            'cor': usuario.role.color if usuario.role else '#5865F2'
        }

        # Vai só para as duas pessoas da conversa (e não para uma sala
        # compartilhada em que qualquer um poderia ter entrado).
        salas = {sala_pessoal(usuario.id), sala_pessoal(target_id)}
        for sala in salas:
            emit('receber_mensagem_direta', payload, to=sala)

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRÍTICO NA DM] O banco bloqueou o salvamento: {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível enviar a DM: {e}'})


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
        srv = servidor_gerenciavel(usuario, dados.get('server_id'))
        if not srv:
            emit('erro_bazinga', {'msg': 'Só o dono do servidor pode criar convites.'})
            return

        duracao = _parse_ilimitado(dados.get('duracao'))     # horas, None = nunca expira
        max_usos = _parse_ilimitado(dados.get('max_usos'))   # None = ilimitado
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

