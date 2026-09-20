from flask import session
from flask_socketio import emit, join_room, leave_room
from sqlalchemy.exc import SQLAlchemyError
from datetime import timedelta
from . import socketio
from .models import db, br_now, Message, Person, DirectMessage, Server, Channel, GeoNote, MapServer
from .utils import com_retry, comitar_com_retry, canal_permitido, pode_ver_canal


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


def hora_formatada(ts):
    """Formata o timestamp de uma mensagem para exibição.

    `br_now()` já devolve horário de Brasília, então NÃO subtraia 3 horas aqui -
    isso era um bug antigo que fazia toda mensagem aparecer 3h no passado.
    """
    if ts is None:
        ts = br_now()
    return f"Hoje às {ts.strftime('%H:%M')}"


def servidor_para_json(srv):
    canais = Channel.query.filter_by(server_id=srv.id).order_by(Channel.id.asc()).all()
    return {
        'id': srv.id,
        'name': srv.name,
        'iconUrl': srv.icon_url,
        'owner_id': srv.owner_id,
        'channels': [{'id': c.id, 'name': c.name, 'type': c.channel_type} for c in canais]
    }


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

        servidores = [servidor_para_json(srv) for srv in usuario.servers]
        for srv in usuario.servers:
            join_room(sala_servidor(srv.id))

        emit('carregar_meus_servidores', servidores)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CONNECT] {e}")


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
    if not texto:
        return

    try:
        def preparar():
            nova = Message(text=texto, person_id=usuario.id, channel_id=canal.id)
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
        'texto': nova_msg.text,
        'hora': hora_formatada(nova_msg.timestamp),
        'cor': cor
    }, to=str(canal.id))


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


@socketio.on('entrar_call')
def lidar_entrar_call(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    canal = canal_permitido(usuario, dados.get('canal_id'))
    if not canal:
        emit('erro_bazinga', {'msg': 'Você não tem acesso a esse canal de voz.'})
        return

    peer_id = dados.get('peer_id')
    if not peer_id:
        return

    sala_call = f"voz_{canal.id}"
    join_room(sala_call)

    emit('novo_usuario_call', {
        'peer_id': peer_id,
        'usuario': usuario.name,
        'avatar': usuario.avatar,
        'canal_id': str(canal.id)
    }, to=sala_call, include_self=False)


@socketio.on('sair_call')
def lidar_sair_call(dados):
    canal_id = dados.get('canal_id')
    peer_id = dados.get('peer_id')
    if canal_id is None:
        return

    sala_call = f"voz_{canal_id}"
    leave_room(sala_call)
    emit('usuario_saiu_call', {'peer_id': peer_id}, to=sala_call, include_self=False)


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
        emit('servidor_discord_criado', servidor_para_json(novo_srv))
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

        def preparar():
            novo = Channel(name=nome, channel_type=tipo, server_id=srv.id)
            db.session.add(novo)
            return novo

        novo_canal = comitar_com_retry(preparar)

        emit('canal_criado', {
            'server_id': srv.id,
            'id': novo_canal.id,
            'name': novo_canal.name,
            'type': novo_canal.channel_type
        }, to=sala_servidor(srv.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRIAR CANAL] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível criar o canal: {e}'})


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
        emit('servidor_discord_criado', servidor_para_json(srv))
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
            'nome': pino.name, 'owner': usuario.name, 'owner_id': usuario.id,
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

        emit('servidor_mapa_editado', {
            'id': pino.id, 'vagas': vagas if vagas else 'ilimitado'
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
            'custom_status': usuario.custom_status,
            'bio': usuario.bio,
            'banner_color': usuario.banner_color,
            'avatar': usuario.avatar
        })
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
