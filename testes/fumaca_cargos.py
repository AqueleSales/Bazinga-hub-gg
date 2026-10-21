"""Rodada 29: cargos por servidor. Quem pode o que, hierarquia, cargo apagado limpa, canal privado, regra 6 com vários clientes.
SQLite em memória + socketio.test_client (molde: fumaca_servidor.py)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import cargos
from app.models import Role, Person, Server, Channel, Message, ServerRole, MemberRole, Event

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


def erro(cli):
    """Texto do 1º erro_bazinga recebido (ou None). Esvazia a fila."""
    e = ev(cli, 'erro_bazinga')
    return e[0]['args'][0]['msg'] if e else None


def ultimo_srv(cli, evento='servidor_estrutura'):
    r = ev(cli, evento)
    return r[-1]['args'][0] if r else None


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Gerente', 'Mod', 'Comum', 'Extra', 'Intruso'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    dono, fdono = cliente('Dono')
    dono.emit('criar_servidor_discord', {'nome': 'Reino'})
    sid = ev(dono, 'servidor_discord_criado')[-1]['args'][0]['id']
    srv = Server.query.get(sid)
    ok(not srv.estrutura, 'Servidor novo nasce sem estrutura (zero query extra no /chat)')

    # todo mundo entra por convite
    dono.emit('criar_convite', {'server_id': sid})
    codigo = ev(dono, 'convite_criado')[-1]['args'][0]['code']
    cl, fc = {}, {}
    for n in ('Gerente', 'Mod', 'Comum', 'Extra'):
        cl[n], fc[n] = cliente(n)
        cl[n].emit('entrar_por_convite', {'code': codigo})
        ev(cl[n])
    intruso, fint = cliente('Intruso')
    ev(dono)
    texto = Channel.query.filter_by(server_id=sid, channel_type='text').first()
    canal_id = texto.id
    for n in ('Dono', 'Gerente', 'Mod', 'Comum', 'Extra'):
        (dono if n == 'Dono' else cl[n]).emit('entrar_canal', {'canal_id': canal_id})
    ev(dono)
    for n in cl: ev(cl[n])

    # ---------- permissões padrão (o que qualquer membro já podia antes dos cargos) ----------
    srv = Server.query.get(sid)
    ctx_comum = cargos.contexto(Person.query.get(ids['Comum']), srv)
    ok(ctx_comum.tem('criar_convite') and ctx_comum.tem('fixar_mensagens') and ctx_comum.tem('falar_voz'), 'Membro comum mantém convidar, fixar e falar em voz')
    ok(not any(ctx_comum.tem(p) for p in ('gerenciar_servidor', 'gerenciar_canais', 'gerenciar_cargos', 'expulsar', 'gerenciar_eventos', 'apagar_mensagens',
                                          'ver_canais_privados', 'enviar_anuncios', 'falar_palco', 'administrador')), 'Membro comum NÃO tem nenhuma permissão de gestão')
    ok(cargos.contexto(Person.query.get(ids['Dono']), srv).dono and cargos.contexto(Person.query.get(ids['Dono']), srv).perms == cargos.TODAS, 'Dono pode tudo')
    ok(cargos.contexto(Person.query.get(ids['Intruso']), srv).perms == 0, 'Quem não é membro não pode nada')

    # quem não pode, não consegue (e o banco não muda)
    comum = cl['Comum']
    comum.emit('criar_canal', {'server_id': sid, 'nome': 'invasao'})
    ok(erro(comum) and Channel.query.filter_by(name='invasao').count() == 0, 'Comum NÃO cria canal')
    comum.emit('editar_servidor', {'server_id': sid, 'nome': 'Hackeado'})
    ok(erro(comum) and Server.query.get(sid).name == 'Reino', 'Comum NÃO edita o servidor')
    comum.emit('expulsar_membro', {'server_id': sid, 'person_id': ids['Extra']})
    ok(erro(comum) and len(Server.query.get(sid).members) == 5, 'Comum NÃO remove membros')
    comum.emit('criar_evento', {'server_id': sid, 'titulo': 'Festa', 'inicio': '2030-01-01T10:00'})
    ok(erro(comum) and Event.query.count() == 0, 'Comum NÃO cria evento')
    comum.emit('cargo_criar', {'server_id': sid, 'nome': 'Rei', 'permissoes': ['administrador']})
    ok(erro(comum) and ServerRole.query.count() == 0, 'Comum NÃO cria cargo')
    comum.emit('categoria_criar', {'server_id': sid, 'nome': 'X'})
    ok(erro(comum), 'Comum NÃO cria categoria')
    comum.emit('apagar_servidor', {'server_id': sid})
    ok(erro(comum) and Server.query.get(sid) is not None, 'Comum NÃO apaga o servidor')
    intruso.emit('cargo_criar', {'server_id': sid, 'nome': 'Rei'})
    ok(erro(intruso) and ServerRole.query.count() == 0, 'Quem não é do servidor NÃO cria cargo')
    comum.emit('criar_convite', {'server_id': sid, 'duracao': 'ilimitado', 'max_usos': 'ilimitado'})
    conv = ev(comum, 'convite_criado')
    ok(bool(conv) and conv[0]['args'][0]['max_usos'] == 25, 'Convite do membro comum continua com teto de 25 usos')

    # ---------- dono cria cargos ----------
    dono.emit('cargo_criar', {'server_id': sid, 'nome': '  Moderador   da   Casa  ', 'cor': '#FF8800', 'permissoes': ['expulsar', 'apagar_mensagens', 'inventada'],
                              'destacar': True})
    s_dono = ultimo_srv(dono)
    ok(s_dono is not None and len(s_dono['cargos']) == 1, 'Dono recebe o servidor com o cargo novo')
    cm = s_dono['cargos'][0]
    ok(cm['nome'] == 'Moderador da Casa' and cm['cor'] == '#ff8800' and cm['destacar'] is True, 'Nome limpo, cor normalizada, destaque ligado')
    ok(sorted(cm['perms']) == ['apagar_mensagens', 'expulsar'], 'Permissão desconhecida é ignorada')
    ok(Server.query.get(sid).estrutura is True, 'Servidor passa a ter estrutura')
    for n in ('Gerente', 'Mod', 'Comum', 'Extra'):
        s = ultimo_srv(cl[n])
        ok(s is not None and s['cargos'] and s['cargos'][0]['nome'] == 'Moderador da Casa', f'{n} recebe o cargo novo na hora (regra 6)')
        ok(s is not None and 'perms' not in s['cargos'][0], f'{n} não vê as permissões do cargo (só quem gerencia cargos)')
    ok(ev(intruso, 'servidor_estrutura') == [], 'Quem não é do servidor não recebe nada')
    id_mod = cm['id']

    dono.emit('cargo_criar', {'server_id': sid, 'nome': 'N' * 40, 'cor': 'vermelho', 'permissoes': 'tudo'})
    s = ultimo_srv(dono)
    novo = [x for x in s['cargos'] if x['id'] != id_mod][0]
    ok(len(novo['nome']) == 24 and novo['cor'] is None and novo['perms'] == [], 'Nome truncado em 24, cor inválida some, permissões fora da lista viram nada')
    pos = {x['id']: x['pos'] for x in s['cargos']}
    ok(pos[novo['id']] < pos[id_mod], 'Cargo novo nasce no fundo da lista')
    dono.emit('cargo_apagar', {'server_id': sid, 'cargo_id': novo['id']}); ev(dono)
    ok(ServerRole.query.count() == 1, 'Dono apaga o cargo extra')

    # cargo do Gerente: gerenciar cargos e canais; depois sobe acima do Moderador
    dono.emit('cargo_criar', {'server_id': sid, 'nome': 'Gerente', 'permissoes': ['gerenciar_cargos', 'gerenciar_canais', 'expulsar'], 'cor': '#3366ff'})
    s = ultimo_srv(dono)
    id_ger = [x for x in s['cargos'] if x['nome'] == 'Gerente'][0]['id']
    dono.emit('cargos_reordenar', {'server_id': sid, 'ordem': [id_ger, id_mod]})
    s = ultimo_srv(dono)
    pos = {x['id']: x['pos'] for x in s['cargos']}
    ok(pos[id_ger] > pos[id_mod], 'Dono reordena: Gerente acima de Moderador')

    # ---------- atribuir ----------
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Mod'], 'cargo_id': id_mod, 'ativo': True})
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Gerente'], 'cargo_id': id_ger, 'ativo': True})
    ev(dono)
    ok(MemberRole.query.count() == 2, 'Dono dá os dois cargos')
    s_mod = ultimo_srv(cl['Mod'])
    ok(s_mod is not None and 'expulsar' in s_mod['minhasPerms'] and 'apagar_mensagens' in s_mod['minhasPerms'] and s_mod['meusCargos'] == [id_mod], 'Moderador recebe as permissões do cargo (e o id dele)')
    s_ger = ultimo_srv(cl['Gerente'])
    ok(s_ger is not None and 'gerenciar_cargos' in s_ger['minhasPerms'] and 'perms' in s_ger['cargos'][0], 'Gerente vê as permissões dos cargos (gerencia cargos)')

    # lista de membros mostra os cargos
    dono.emit('listar_membros_servidor', {'server_id': sid})
    mm = ev(dono, 'membros_do_servidor')[-1]['args'][0]['membros']
    por = {m['id']: m for m in mm}
    ok(por[ids['Mod']]['cargos'] == [id_mod] and por[ids['Comum']]['cargos'] == [], 'Lista de membros traz o cargo de cada um')

    # ---------- o que o cargo libera ----------
    mod = cl['Mod']
    ev(mod)
    db.session.add(Message(text='ofensivo', person_id=ids['Comum'], channel_id=canal_id)); db.session.commit()
    msg_id = Message.query.filter_by(text='ofensivo').first().id
    comum.emit('apagar_mensagem', {'msg_id': msg_id})
    # o próprio autor apaga as suas; outro comum NÃO apaga a dos outros
    db.session.add(Message(text='alheia', person_id=ids['Extra'], channel_id=canal_id)); db.session.commit()
    alheia = Message.query.filter_by(text='alheia').first().id
    comum.emit('apagar_mensagem', {'msg_id': alheia})
    ok(Message.query.get(alheia) is not None and erro(comum), 'Comum NÃO apaga mensagem de outra pessoa')
    mod.emit('apagar_mensagem', {'msg_id': alheia})
    ok(Message.query.get(alheia) is None, 'Moderador (com "Apagar mensagens dos outros") apaga a mensagem alheia')
    mod.emit('criar_canal', {'server_id': sid, 'nome': 'sorrateiro'})
    ok(erro(mod) and Channel.query.filter_by(name='sorrateiro').count() == 0, 'Moderador NÃO cria canal (não tem a permissão)')

    # ---------- hierarquia ----------
    mod.emit('expulsar_membro', {'server_id': sid, 'person_id': ids['Dono']})
    ok(erro(mod) and ids['Dono'] in [m.id for m in Server.query.get(sid).members], 'NINGUÉM expulsa o dono')
    mod.emit('expulsar_membro', {'server_id': sid, 'person_id': ids['Gerente']})
    ok(erro(mod) and ids['Gerente'] in [m.id for m in Server.query.get(sid).members], 'Moderador NÃO remove o Gerente (cargo acima)')
    cl['Gerente'].emit('expulsar_membro', {'server_id': sid, 'person_id': ids['Mod']})
    ok(ids['Mod'] not in [m.id for m in Server.query.get(sid).members], 'Gerente (acima) remove o Moderador')
    ok(MemberRole.query.filter_by(person_id=ids['Mod']).count() == 0, 'Remover o membro limpa os cargos dele')
    # Mod volta com convite e recebe o cargo de novo
    dono.emit('criar_convite', {'server_id': sid}); codigo2 = ev(dono, 'convite_criado')[-1]['args'][0]['code']
    mod2, fmod2 = cliente('Mod'); mod2.emit('entrar_por_convite', {'code': codigo2}); ev(mod2)
    ok(len(Server.query.get(sid).members) == 5, 'Moderador voltou ao servidor')
    ok(cargos.contexto(Person.query.get(ids['Mod']), Server.query.get(sid)).nivel == 0, 'Voltou SEM os cargos antigos')
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Mod'], 'cargo_id': id_mod, 'ativo': True}); ev(dono); ev(mod2)
    mod = mod2

    ger = cl['Gerente']
    ev(ger)
    # Gerente não mexe em cargo igual/acima, não concede o que não tem
    ger.emit('cargo_editar', {'server_id': sid, 'cargo_id': id_ger, 'nome': 'Golpe'})
    ok(erro(ger) and ServerRole.query.get(id_ger).nome == 'Gerente', 'Gerente NÃO edita o próprio cargo (igual ao seu)')
    ger.emit('cargo_apagar', {'server_id': sid, 'cargo_id': id_ger})
    ok(erro(ger) and ServerRole.query.get(id_ger) is not None, 'Gerente NÃO apaga o próprio cargo')
    ger.emit('cargo_criar', {'server_id': sid, 'nome': 'Poderoso', 'permissoes': ['apagar_mensagens']})
    ok(erro(ger) and ServerRole.query.filter_by(nome='Poderoso').count() == 0, 'Gerente NÃO cria cargo com permissão que ele não tem')
    ger.emit('cargo_criar', {'server_id': sid, 'nome': 'Admin', 'permissoes': ['administrador']})
    ok(erro(ger) and ServerRole.query.filter_by(nome='Admin').count() == 0, 'Gerente NÃO cria cargo de Administrador')
    ger.emit('cargo_criar', {'server_id': sid, 'nome': 'Visitante', 'permissoes': ['expulsar'], 'cor': '#00ff00'})
    vis = ServerRole.query.filter_by(nome='Visitante').first()
    ok(vis is not None and vis.posicao < ServerRole.query.get(id_ger).posicao, 'Gerente cria cargo abaixo do dele, só com permissões que tem')
    ev(ger)
    # Moderador (abaixo do Gerente) tem apagar_mensagens: o Gerente não tem, então não pode dar esse cargo a ninguém
    ger.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': id_mod, 'ativo': True})
    ok(erro(ger) and MemberRole.query.filter_by(person_id=ids['Comum']).count() == 0, 'Gerente NÃO dá um cargo com permissão que ele não tem')
    ger.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': vis.id, 'ativo': True})
    ok(MemberRole.query.filter_by(person_id=ids['Comum'], role_id=vis.id).count() == 1, 'Gerente dá o cargo que está dentro das permissões dele')
    ev(ger)
    ger.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Dono'], 'cargo_id': vis.id, 'ativo': True})
    ok(erro(ger) and MemberRole.query.filter_by(person_id=ids['Dono']).count() == 0, 'Ninguém dá cargo ao dono')
    ger.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Gerente'], 'cargo_id': id_mod, 'ativo': True})
    ger.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Extra'], 'cargo_id': id_ger, 'ativo': True})
    ok(erro(ger) and MemberRole.query.filter_by(person_id=ids['Extra']).count() == 0, 'Gerente NÃO dá cargo do nível dele')
    # cargo de fora do servidor / id louco
    ger.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': 99999, 'ativo': True})
    ok(erro(ger), 'Cargo inexistente é recusado')
    ger.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Intruso'], 'cargo_id': vis.id, 'ativo': True})
    ok(erro(ger) and MemberRole.query.filter_by(person_id=ids['Intruso']).count() == 0, 'Cargo não vai pra quem não é membro')

    # reordenar: o Gerente só mexe nos de baixo (a posição dele fica)
    pos_antes = {r_.id: r_.posicao for r_ in ServerRole.query.all()}
    ger.emit('cargos_reordenar', {'server_id': sid, 'ordem': [id_mod, vis.id, id_ger]}); ev(ger)
    pos_depois = {r_.id: r_.posicao for r_ in ServerRole.query.all()}
    ok(pos_depois[id_ger] == pos_antes[id_ger], 'Reordenar não move o cargo do próprio Gerente')
    ok(pos_depois[id_mod] > pos_depois[vis.id] and pos_depois[id_ger] > max(pos_depois[id_mod], pos_depois[vis.id]), 'O Gerente reordena os de baixo e continua acima deles')

    # administrador: tudo menos o que é só do dono
    dono.emit('cargo_criar', {'server_id': sid, 'nome': 'Vice', 'permissoes': ['administrador']}); ev(dono)
    id_vice = ServerRole.query.filter_by(nome='Vice').first().id
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Extra'], 'cargo_id': id_vice, 'ativo': True}); ev(dono)
    extra = cl['Extra']; ev(extra)
    ok(cargos.contexto(Person.query.get(ids['Extra']), Server.query.get(sid)).perms == cargos.TODAS, 'Administrador tem todas as permissões')
    extra.emit('editar_servidor', {'server_id': sid, 'descricao': 'Quem manda aqui é o vice'})
    ok(Server.query.get(sid).description == 'Quem manda aqui é o vice', 'Administrador edita o servidor')
    extra.emit('apagar_servidor', {'server_id': sid})
    ok(erro(extra) and Server.query.get(sid) is not None, 'Administrador NÃO apaga o servidor (só o dono)')
    extra.emit('transferir_posse', {'server_id': sid, 'person_id': ids['Extra']})
    ok(erro(extra) and Server.query.get(sid).owner_id == ids['Dono'], 'Administrador NÃO passa a posse')
    extra.emit('expulsar_membro', {'server_id': sid, 'person_id': ids['Dono']})
    ok(erro(extra) and ids['Dono'] in [m.id for m in Server.query.get(sid).members], 'Administrador NÃO remove o dono')
    extra.emit('cargo_padrao', {'server_id': sid, 'permissoes': ['administrador']})
    ok(erro(extra) and Server.query.get(sid).perms_membro is None, 'Ninguém vira administrador pelo cargo "Membro"')

    # ---------- cargo padrão "Membro" ----------
    db.session.add(Message(text='fixavel', person_id=ids['Dono'], channel_id=canal_id)); db.session.commit()
    fixavel = Message.query.filter_by(text='fixavel').first().id
    comum.emit('fixar_mensagem', {'msg_id': fixavel})
    ok(Message.query.get(fixavel).is_pinned is True, 'Antes de mexer no cargo Membro, qualquer membro fixa (como sempre foi)')
    comum.emit('fixar_mensagem', {'msg_id': fixavel}); ev(comum)    # desafixa
    dono.emit('cargo_padrao', {'server_id': sid, 'permissoes': ['criar_convite', 'falar_voz']}); ev(dono)
    ok(not cargos.contexto(Person.query.get(ids['Comum']), Server.query.get(sid)).tem('fixar_mensagens'), 'Dono tira "Fixar" do cargo Membro')
    comum.emit('fixar_mensagem', {'msg_id': fixavel})
    ok(erro(comum) and Message.query.get(fixavel).is_pinned is False, 'Comum não fixa mais')
    dono.emit('fixar_mensagem', {'msg_id': fixavel})
    ok(Message.query.get(fixavel).is_pinned is True, 'Dono fixa')
    dono.emit('cargo_padrao', {'server_id': sid, 'permissoes': ['criar_convite', 'falar_voz', 'fixar_mensagens']}); ev(dono)
    s_c = ultimo_srv(comum)
    ok(s_c is not None and 'fixar_mensagens' in s_c['minhasPerms'], 'A mudança do cargo Membro chega a todos (regra 6)')

    # ---------- canal privado: só vê quem foi chamado, o dono ou o cargo "Ver canais privados" ----------
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'cofre', 'privado': True, 'membros': [ids['Comum']]})
    ev(dono); [ev(x) for x in cl.values()]
    cofre = Channel.query.filter_by(name='cofre').first()
    ok(cargos.contexto(Person.query.get(ids['Mod']), Server.query.get(sid)).perms & cargos.BIT['ver_canais_privados'] == 0, 'Moderador não tem "Ver canais privados"')
    mod.emit('entrar_canal', {'canal_id': cofre.id})
    ok(erro(mod), 'Moderador NÃO entra no canal privado')
    mod.emit('enviar_mensagem', {'canal_id': cofre.id, 'texto': 'bisbilhotando'})
    ok(Message.query.filter_by(channel_id=cofre.id).count() == 0, 'Moderador NÃO escreve no canal privado')
    ok(fmod2.get(f'/api/mensagens/{cofre.id}').status_code == 403, 'API devolve 403 pro Moderador')
    dono.emit('cargo_editar', {'server_id': sid, 'cargo_id': id_mod, 'permissoes': ['expulsar', 'apagar_mensagens', 'ver_canais_privados']})
    s_mod = ultimo_srv(mod)
    ok(s_mod is not None and cofre.id in [x['id'] for x in s_mod['channels']], 'Com "Ver canais privados" o canal passa a aparecer pra ele (regra 6)')
    ok(fmod2.get(f'/api/mensagens/{cofre.id}').status_code == 200, 'E a API libera')
    dono.emit('cargo_editar', {'server_id': sid, 'cargo_id': id_mod, 'permissoes': ['expulsar', 'apagar_mensagens']})
    s_mod = ultimo_srv(mod)
    ok(s_mod is not None and cofre.id not in [x['id'] for x in s_mod['channels']], 'Tirando a permissão, o canal some de novo')
    ok(fmod2.get(f'/api/mensagens/{cofre.id}').status_code == 403, 'E a API volta a recusar')

    # ---------- cargo apagado limpa ----------
    antes = MemberRole.query.filter_by(role_id=id_mod).count()
    ok(antes == 1, 'Moderador tem 1 membro com o cargo')
    dono.emit('cargo_apagar', {'server_id': sid, 'cargo_id': id_mod})
    ok(ServerRole.query.get(id_mod) is None and MemberRole.query.filter_by(role_id=id_mod).count() == 0, 'Apagar o cargo apaga as ligações com os membros')
    s_mod = ultimo_srv(mod)
    ok(s_mod is not None and s_mod['meusCargos'] == [] and 'expulsar' not in s_mod['minhasPerms'], 'Quem tinha o cargo perde as permissões na hora')
    mod.emit('expulsar_membro', {'server_id': sid, 'person_id': ids['Comum']})
    ok(erro(mod), 'E não consegue mais remover ninguém')

    # sair do servidor limpa
    cl['Comum'].emit('sair_do_servidor', {'server_id': sid}); ev(cl['Comum'])
    ok(MemberRole.query.filter_by(person_id=ids['Comum']).count() == 0, 'Sair do servidor limpa os cargos')

    # limite de cargos
    existentes = ServerRole.query.filter_by(server_id=sid).count()
    for i in range(cargos.MAX_CARGOS - existentes + 2):
        dono.emit('cargo_criar', {'server_id': sid, 'nome': f'c{i}'})
    ok(ServerRole.query.filter_by(server_id=sid).count() == cargos.MAX_CARGOS, f'Teto de {cargos.MAX_CARGOS} cargos por servidor')
    ev(dono)

    # apagar o servidor leva cargos junto
    dono.emit('apagar_servidor', {'server_id': sid}); ev(dono)
    ok(Server.query.get(sid) is None and ServerRole.query.count() == 0 and MemberRole.query.count() == 0, 'Apagar o servidor apaga cargos e ligações')

    # ---------- validadores puros ----------
    ok(cargos.mascara_de(['expulsar', 'xx', 3, None]) == cargos.BIT['expulsar'], 'mascara_de ignora ids desconhecidos e tipos errados')
    ok(cargos.ids_da_mascara(cargos.mascara_de(cargos.IDS_PERMISSAO)) == list(cargos.IDS_PERMISSAO), 'Todas as permissões fazem a viagem de ida e volta')
    ok(len(set(cargos.BIT.values())) == len(cargos.BIT), 'Cada permissão tem um bit só dela')
    ok(cargos.cor_valida('#AbCdEf') == '#abcdef' and cargos.cor_valida('red') is None and cargos.cor_valida('#fff') is None and cargos.cor_valida('#12345g') is None, 'Cor só #rrggbb')
    ok(cargos.limpar_nome('a\x00b‮  c', 24) == 'ab c', 'Nome sem caractere de controle nem inversão de texto')

    # ---------- o cliente espelha as listas fechadas do servidor ----------
    import re
    js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'static', 'js', 'cargos.js'), encoding='utf-8').read()
    bloco_js = re.search(r"const PERMISSOES = \[(.*?)\n    \];", js, re.S).group(1)   # só a lista do servidor (a de canal, PERMS_CANAL, é conferida em fumaca_permissoes_canal.py)
    ids_js = re.findall(r"^\s+\['([a-z_]+)', '[^']+', '", bloco_js, re.M)
    ok(ids_js == list(cargos.IDS_PERMISSAO), 'cargos.js lista as MESMAS permissões, na mesma ordem')
    tipos_js = set(re.findall(r"^\s+([a-z]+): \{ fam: '", js, re.M))
    ok(tipos_js == set(cargos.TIPOS_CANAL), 'cargos.js lista os MESMOS tipos de canal')
    ok(all(re.search(rf"{t}: \{{ fam: '{i['familia']}'", js) for t, i in cargos.TIPOS_CANAL.items()), 'E cada tipo na mesma família')
    css = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'static', 'css', 'cargos.css'), encoding='utf-8').read()
    ok('.sep-item' in css and '.cat-bloco' in css and '.tipo-card' in css, 'cargos.css cobre separador, categoria e cartões de tipo')

print()
print('FALHAS:', falhas if falhas else 'nenhuma')
sys.exit(1 if falhas else 0)
