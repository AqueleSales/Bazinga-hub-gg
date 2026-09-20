import time
from flask import session
from flask_socketio import emit, join_room, leave_room
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from datetime import timedelta
from . import socketio
from .models import db, br_now, Message, Person, DirectMessage, Server, Channel, GeoNote, MapServer


def com_retry(fn, tentativas=3, espera=0.8):
    """Roda fn() e tenta de novo se o Neon (banco serverless) estiver
    'acordando' de um cold start - com NullPool, toda operação abre uma
    conexão nova, então isso pode acontecer em qualquer query, não só no login."""
    for tentativa in range(tentativas):
        try:
            return fn()
        except OperationalError:
            db.session.rollback()
            if tentativa == tentativas - 1:
                raise
            time.sleep(espera * (tentativa + 1))


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


def dm_room(id_a, id_b):
    return f"dm_{min(id_a, id_b)}_{max(id_a, id_b)}"


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
# CONEXÃO: Carrega os servidores do usuário e
# entra nas salas de DM com todo mundo (para notificações em tempo real)
# ==========================================
@socketio.on('connect')
def handle_connect():
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        servidores = [servidor_para_json(srv) for srv in usuario.servers]
        emit('carregar_meus_servidores', servidores)

        outros = Person.query.filter(Person.id != usuario.id).all()
        for outro in outros:
            join_room(dm_room(usuario.id, outro.id))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CONNECT] {e}")


@socketio.on('entrar_canal')
def handle_join(dados):
    canal_id = str(dados['canal_id'])
    join_room(canal_id)


@socketio.on('sair_canal')
def handle_leave(dados):
    canal_id = str(dados['canal_id'])
    leave_room(canal_id)


@socketio.on('enviar_mensagem')
def lidar_com_mensagem(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        canal_id = str(dados['canal_id'])

        nova_msg = Message(
            text=dados['texto'],
            person_id=usuario.id,
            channel_id=int(canal_id)
        )
        db.session.add(nova_msg)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CHAT GERAL] Não foi possível salvar: {e}")
        return

    cor = usuario.role.color if usuario.role else '#23a559'
    hora_br = nova_msg.timestamp - timedelta(hours=3)
    hora_formatada = f"Hoje às {hora_br.strftime('%H:%M')}"

    emit('receber_mensagem', {
        'id': nova_msg.id,
        'usuario': usuario.name,
        'avatar': usuario.avatar,
        'texto': nova_msg.text,
        'hora': hora_formatada,
        'cor': cor
    }, to=canal_id)


@socketio.on('apagar_mensagem')
def lidar_com_exclusao(dados):
    msg_id = dados.get('msg_id')
    try:
        msg = Message.query.get(msg_id)
        if msg:
            canal_id = str(msg.channel_id)
            db.session.delete(msg)
            db.session.commit()
            emit('mensagem_apagada', {'msg_id': msg_id}, to=canal_id)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO AO APAGAR] {e}")


@socketio.on('entrar_call')
def lidar_entrar_call(dados):
    canal_id = str(dados['canal_id'])
    peer_id = dados['peer_id']
    nome_usuario = dados['usuario']

    sala_call = f"voz_{canal_id}"
    join_room(sala_call)

    usuario = usuario_logado()
    avatar = usuario.avatar if usuario else None

    emit('novo_usuario_call', {
        'peer_id': peer_id,
        'usuario': nome_usuario,
        'avatar': avatar,
        'canal_id': canal_id
    }, to=sala_call, include_self=False)


@socketio.on('sair_call')
def lidar_sair_call(dados):
    canal_id = str(dados['canal_id'])
    peer_id = dados['peer_id']
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

        def salvar():
            novo_srv = Server(name=nome, owner_id=usuario.id, icon_url=icon_url)
            novo_srv.members.append(usuario)
            db.session.add(novo_srv)
            db.session.flush()  # gera o novo_srv.id sem precisar comitar ainda

            db.session.add(Channel(name="geral", channel_type="text", server_id=novo_srv.id))
            db.session.add(Channel(name="Geral", channel_type="voice", server_id=novo_srv.id))
            db.session.commit()
            return novo_srv

        novo_srv = com_retry(salvar)
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

        def salvar():
            novo = Channel(name=nome, channel_type=tipo, server_id=srv.id)
            db.session.add(novo)
            db.session.commit()
            return novo

        novo_canal = com_retry(salvar)

        emit('canal_criado', {
            'server_id': srv.id,
            'id': novo_canal.id,
            'name': novo_canal.name,
            'type': novo_canal.channel_type
        })
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

        def salvar():
            srv = Server.query.get(server_id)
            if srv and usuario not in srv.members:
                srv.members.append(usuario)
                db.session.commit()
            return srv

        srv = com_retry(salvar)
        if not srv:
            return

        emit('servidor_discord_criado', servidor_para_json(srv))
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ENTRAR SERVIDOR] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível entrar no servidor: {e}'})


# ==========================================
# MAPA: Notas HQ (GeoNote) e Servidores Plantados (MapServer)
# ==========================================
@socketio.on('criar_geonote')
def criar_geonote(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        texto = (dados.get('texto') or '').strip()[:280] or "Loot raro aqui!"
        cor = dados.get('cor') or '#5865F2'

        def salvar():
            nota = GeoNote(
                lat=float(dados['lat']), lng=float(dados['lng']),
                text=texto, color=cor, author_id=usuario.id
            )
            db.session.add(nota)
            db.session.commit()
            return nota

        nota = com_retry(salvar)

        emit('nova_geonote', {
            'id': nota.id, 'lat': nota.lat, 'lng': nota.lng,
            'texto': nota.text, 'autor': usuario.name, 'cor': nota.color
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
        nota = GeoNote.query.get(dados.get('id'))
        if not nota or nota.author_id != usuario.id:
            return

        if 'texto' in dados:
            nota.text = (dados.get('texto') or '').strip()[:280] or nota.text
        if 'cor' in dados:
            nota.color = dados.get('cor') or nota.color
        db.session.commit()

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
        nota = GeoNote.query.get(dados.get('id'))
        if not nota or nota.author_id != usuario.id:
            return
        nota_id = nota.id
        db.session.delete(nota)
        db.session.commit()
        emit('geonote_apagada', {'id': nota_id}, broadcast=True)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR GEONOTE] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar a nota: {e}'})


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

        def salvar():
            pino = MapServer(
                name=srv.name, lat=float(dados['lat']), lng=float(dados['lng']),
                max_tickets=vagas, duration_hours=duracao, expires_at=expira_em,
                owner_id=usuario.id, server_id=srv.id
            )
            db.session.add(pino)
            db.session.commit()
            return pino

        pino = com_retry(salvar)

        emit('novo_servidor_mapa', {
            'id': pino.id, 'lat': pino.lat, 'lng': pino.lng,
            'nome': pino.name, 'owner': usuario.name,
            'vagas': vagas if vagas else 'ilimitado',
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
        pino = MapServer.query.get(dados.get('id'))
        if not pino or pino.owner_id != usuario.id:
            return

        vagas = _parse_ilimitado(dados.get('vagas'))
        duracao = _parse_ilimitado(dados.get('duracao'))
        pino.max_tickets = vagas
        pino.duration_hours = duracao
        pino.expires_at = br_now() + timedelta(hours=duracao) if duracao else None
        db.session.commit()

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
        pino = MapServer.query.get(dados.get('id'))
        if not pino or pino.owner_id != usuario.id:
            return
        pino_id = pino.id
        db.session.delete(pino)
        db.session.commit()
        emit('servidor_mapa_apagado', {'id': pino_id}, broadcast=True)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO APAGAR SERVIDOR MAPA] {e}")
        emit('erro_bazinga', {'msg': f'Não foi possível apagar o servidor plantado: {e}'})


@socketio.on('atualizar_localizacao')
def atualizar_localizacao(dados):
    # Posição ao vivo: não é persistida no banco, só retransmitida para o
    # radar dos outros usuários conectados (o frontend já sabe desenhá-la).
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        emit('posicao_amigo_atualizada', {
            'usuario_id': usuario.id,
            'nome': usuario.name,
            'avatar': usuario.avatar,
            'lat': float(dados['lat']),
            'lng': float(dados['lng'])
        }, broadcast=True, include_self=False)
    except Exception as e:
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
        if 'custom_status' in dados:
            usuario.custom_status = (dados.get('custom_status') or '').strip()[:128] or None
        if 'bio' in dados:
            usuario.bio = (dados.get('bio') or '').strip()[:1000] or None
        if 'banner_color' in dados:
            usuario.banner_color = dados.get('banner_color') or None
        if 'avatar' in dados and dados.get('avatar'):
            usuario.avatar = dados.get('avatar')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ATUALIZAR PERFIL] {e}")


@socketio.on('mudar_status')
def mudar_status(dados):
    usuario = usuario_logado()
    if not usuario:
        return

    try:
        status = dados.get('status')
        if status in ('online', 'idle', 'dnd', 'invisible'):
            usuario.status = status
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO MUDAR STATUS] {e}")


# ==========================================
# EVENTOS PARA MENSAGENS DIRETAS (DMs)
# ==========================================
@socketio.on('entrar_dm')
def on_entrar_dm(data):
    user_id = session.get('user_id')
    if not user_id:
        return

    target_id = int(data.get('target_id'))
    join_room(dm_room(user_id, target_id))


@socketio.on('enviar_mensagem_direta')
def on_enviar_mensagem_direta(data):
    user_id = session.get('user_id')
    if not user_id:
        print("[ERRO DM] Usuário não está logado na sessão.")
        return

    target_id = int(data.get('target_id'))
    texto = data.get('texto')

    try:
        usuario = Person.query.get(user_id)
        if not usuario:
            print("[ERRO DM] Usuário não encontrado no banco.")
            return

        nova_msg = DirectMessage(sender_id=user_id, receiver_id=target_id, content=texto)
        db.session.add(nova_msg)
        db.session.commit()

        hora_br = nova_msg.timestamp - timedelta(hours=3)
        hora_formatada = f"Hoje às {hora_br.strftime('%H:%M')}"

        room = dm_room(user_id, target_id)
        cor = usuario.role.color if usuario.role else '#5865F2'

        emit('receber_mensagem_direta', {
            'id': nova_msg.id,
            'usuario': usuario.name,
            'usuario_id': usuario.id,
            'destinatario_id': target_id,
            'avatar': usuario.avatar,
            'texto': texto,
            'hora': hora_formatada,
            'cor': cor
        }, room=room)

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO CRÍTICO NA DM] O banco bloqueou o salvamento: {e}")
        return
