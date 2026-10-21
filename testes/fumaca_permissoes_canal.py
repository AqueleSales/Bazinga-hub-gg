"""Rodada 29b: permissão POR CANAL (sobrescrita por cargo). Quem pode o que, negar vence liberar, dono/Administrador ignoram, cargo apagado limpa,
canal privado e categoria não vazam, regra 6 com vários clientes, hierarquia/anti-escalada, e o custo (canal sem sobrescrita não consulta a tabela).
SQLite em memória + socketio.test_client (molde: fumaca_cargos.py)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import cargos
from app.models import Role, Person, Server, Channel, Message, ServerRole, MemberRole, ChannelOverwrite, ChannelCategory
from sqlalchemy import event as sa_event

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
    e = ev(cli, 'erro_bazinga')
    return e[0]['args'][0]['msg'] if e else None


def ultimo_srv(cli, evento='servidor_estrutura'):
    r = ev(cli, evento)
    return r[-1]['args'][0] if r else None


def canais_de(srv_json):
    return {x['id']: x for x in (srv_json or {}).get('channels', [])}


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Gerente', 'Mod', 'Comum', 'Extra', 'Adm', 'Intruso'):
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
    dono.emit('criar_convite', {'server_id': sid})
    codigo = ev(dono, 'convite_criado')[-1]['args'][0]['code']
    cl, fc = {}, {}
    for n in ('Gerente', 'Mod', 'Comum', 'Extra', 'Adm'):
        cl[n], fc[n] = cliente(n)
        cl[n].emit('entrar_por_convite', {'code': codigo}); ev(cl[n])
    intruso, fint = cliente('Intruso')
    ev(dono)
    ger, mod, comum, extra, adm = cl['Gerente'], cl['Mod'], cl['Comum'], cl['Extra'], cl['Adm']
    geral = Channel.query.filter_by(server_id=sid, channel_type='text').first().id

    def novo_canal(nome, **kw):
        dono.emit('criar_canal', dict({'server_id': sid, 'nome': nome}, **kw)); ev(dono)
        return Channel.query.filter_by(server_id=sid, name=nome).first().id

    def todos_limpam():
        ev(dono)
        for k in cl: ev(cl[k])

    # cargos: Gerente (gerenciar cargos/canais + apagar mensagens, nível alto), Mod (apagar e fixar), Redator (anúncios), Orador, Vice (administrador)
    for nome, perms in (('Gerente', ['gerenciar_cargos', 'gerenciar_canais', 'apagar_mensagens', 'fixar_mensagens']), ('Mod', ['apagar_mensagens', 'fixar_mensagens']),
                        ('Redator', ['enviar_anuncios']), ('Orador', []), ('Vice', ['administrador'])):
        dono.emit('cargo_criar', {'server_id': sid, 'nome': nome, 'permissoes': perms}); ev(dono)
    R = {x.nome: x.id for x in ServerRole.query.filter_by(server_id=sid).all()}
    dono.emit('cargos_reordenar', {'server_id': sid, 'ordem': [R['Vice'], R['Gerente'], R['Mod'], R['Redator'], R['Orador']]}); ev(dono)
    for pessoa, cargo in (('Gerente', 'Gerente'), ('Mod', 'Mod'), ('Extra', 'Redator'), ('Adm', 'Vice')):
        dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids[pessoa], 'cargo_id': R[cargo], 'ativo': True})
    todos_limpam()
    for n in ('Dono', 'Gerente', 'Mod', 'Comum', 'Extra', 'Adm'):
        (dono if n == 'Dono' else cl[n]).emit('entrar_canal', {'canal_id': geral})
    todos_limpam()

    # ---------- sem sobrescrita: nada muda, nada custa ----------
    ok(not Channel.query.get(geral).sobrescrita and ChannelOverwrite.query.count() == 0, 'Canal novo não tem sobrescrita nem linha na tabela')
    comum.emit('enviar_mensagem', {'canal_id': geral, 'texto': 'oi pessoal', 'temp_id': 't1'}); ev(comum)
    ok(Message.query.filter_by(text='oi pessoal').count() == 1, 'Sem sobrescrita, o membro comum escreve como sempre')
    s_comum = ultimo_srv(comum) or {}
    dono.emit('editar_servidor', {'server_id': sid, 'descricao': 'Reino de teste que existe pra provar o aviso'}); todos_limpam()
    comum.emit('listar_membros_servidor', {'server_id': sid}); ev(comum)
    consultas_tabela = []

    def espiar(conn, cursor, stmt, params, ctx, many):
        if 'channel_overwrite' in stmt.lower():
            consultas_tabela.append(stmt)
    sa_event.listen(db.engine, 'before_cursor_execute', espiar)
    comum.emit('enviar_mensagem', {'canal_id': geral, 'texto': 'outra sem custo', 'temp_id': 't2'}); ev(comum)
    mod.emit('apagar_mensagem', {'msg_id': Message.query.filter_by(text='outra sem custo').first().id}); ev(mod)
    mod.emit('fixar_mensagem', {'msg_id': Message.query.filter_by(text='oi pessoal').first().id}); ev(mod)
    dono.emit('editar_servidor', {'server_id': sid, 'descricao': 'Segunda descricao qualquer do reino'}); todos_limpam()
    ok(consultas_tabela == [], 'Enviar, apagar, fixar e reenviar o servidor em canal SEM sobrescrita não tocam a tabela channel_overwrite')
    sa_event.remove(db.engine, 'before_cursor_execute', espiar)

    # ---------- quem NÃO pode definir ----------
    for quem, nome in ((comum, 'Comum'), (mod, 'Mod (sem gerenciar cargos)'), (intruso, 'quem não é do servidor')):
        quem.emit('canal_permissao', {'canal_id': geral, 'cargo_id': None, 'negar': ['enviar_mensagens']})
        ok(erro(quem) and ChannelOverwrite.query.count() == 0, f'{nome} NÃO define permissão de canal')
    dono.emit('canal_permissao', {'canal_id': 999999, 'negar': ['ver_canal']})
    ok(erro(dono), 'Canal inexistente é recusado')

    # ---------- ver canal: Membro negado, Mod liberado; categoria e nome não vazam ----------
    staff = novo_canal('staff')
    dono.emit('categoria_criar', {'server_id': sid, 'nome': 'Equipe'}); ev(dono)
    cat = ChannelCategory.query.filter_by(server_id=sid, nome='Equipe').first()
    Channel.query.get(staff).category_id = cat.id; db.session.commit()
    todos_limpam()
    dono.emit('canal_permissao', {'canal_id': staff, 'cargo_id': None, 'negar': ['ver_canal']})
    recebido_dono = dono.get_received()
    ok(not [m for m in recebido_dono if m['name'] == 'erro_bazinga'], 'Dono define sem erro')
    ok(ChannelOverwrite.query.filter_by(channel_id=staff, role_id=None).count() == 1 and Channel.query.get(staff).sobrescrita is True,
       'Linha do Membro padrão criada (role_id NULL) e o canal fica marcado')
    ok(Server.query.get(sid).estrutura is True, 'Servidor tem estrutura')
    s_c = ultimo_srv(comum)
    ok(s_c is not None and staff not in canais_de(s_c), 'Comum deixa de ver o canal (regra 6: recebeu a SUA versão do servidor)')
    ok(s_c is not None and 'Equipe' not in [k['nome'] for k in s_c['categorias']], 'A categoria que só tinha esse canal some pra ele (o nome não vaza)')
    s_ex = ultimo_srv(extra)
    ok(s_ex is not None and staff not in canais_de(s_ex), 'Extra (Redator) também não vê')
    s_m = ultimo_srv(mod)
    ok(s_m is not None and staff not in canais_de(s_m), 'Mod também não vê enquanto o Membro estiver negado e ninguém liberar')
    s_d = [m for m in recebido_dono if m['name'] == 'servidor_estrutura'][-1]['args'][0]
    ok(staff in canais_de(s_d) and canais_de(s_d)[staff].get('sobrescrita') is True and 'Equipe' in [k['nome'] for k in s_d['categorias']], 'Dono continua vendo (ignora sobrescrita)')
    ok(staff in canais_de(ultimo_srv(adm)), 'Administrador (cargo Vice) continua vendo')
    comum.emit('entrar_canal', {'canal_id': staff})
    ok(erro(comum), 'Comum NÃO entra chutando o id do canal escondido')
    comum.emit('enviar_mensagem', {'canal_id': staff, 'texto': 'invasor'})
    ok(Message.query.filter_by(text='invasor').count() == 0, 'Comum NÃO escreve no canal escondido')
    dono.emit('enviar_mensagem', {'canal_id': staff, 'texto': 'segredo da equipe'}); ev(dono)
    msg_staff = Message.query.filter_by(text='segredo da equipe').first().id
    ok(fc['Comum'].get(f'/api/mensagens/{staff}').status_code in (401, 403, 404), 'API de mensagens recusa o canal escondido')
    ok(fdono.get(f'/api/mensagens/{staff}').status_code == 200, 'API de mensagens entrega ao dono')
    comum.emit('apagar_mensagem', {'msg_id': msg_staff}); comum.emit('fixar_mensagem', {'msg_id': msg_staff}); ev(comum)
    ok(Message.query.get(msg_staff) is not None and not Message.query.get(msg_staff).is_pinned, 'Nem apaga nem fixa mensagem do canal escondido')
    # a prévia pública do Explorar nunca lista canal com sobrescrita
    from app import explorar
    srv_obj = Server.query.get(sid)
    srv_obj.publico = True; srv_obj.description = 'Um reino de testes bem descrito'; srv_obj.tema_explorar = 'jogos'; db.session.commit()
    pv = explorar.previa(Person.query.get(ids['Intruso']), sid)
    nomes_previa = str(pv)
    ok('staff' not in nomes_previa and 'geral' in nomes_previa, 'A prévia do Explorar não lista o canal com sobrescrita (mas lista os normais)')

    # libera pro cargo Mod: a sobrescrita do cargo vence a do Membro
    dono.emit('canal_permissao', {'canal_id': staff, 'cargo_id': R['Mod'], 'permitir': ['ver_canal']})
    s_m = ultimo_srv(mod)
    ok(s_m is not None and staff in canais_de(s_m) and 'ver_canal' in canais_de(s_m)[staff]['perms'], 'Cargo liberado (Mod) volta a ver o canal, por cima do Membro negado')
    ok('Equipe' in [k['nome'] for k in s_m['categorias']], 'E a categoria volta pra ele')
    ok('ow' not in canais_de(s_m)[staff], 'Mod (sem gerenciar cargos) NÃO recebe o detalhe das sobrescritas')
    ok(staff not in canais_de(ultimo_srv(comum) or {}), 'Comum segue sem ver')
    s_g = ultimo_srv(ger)
    ok(s_g is not None and staff not in canais_de(s_g), 'Gerente também não vê (o Membro está negado e ele não tem o cargo liberado)')
    s_d = ultimo_srv(dono)
    ow = canais_de(s_d)[staff].get('ow') or []
    ok({(o['cargo'], tuple(o['permitir']), tuple(o['negar'])) for o in ow} == {(None, (), ('ver_canal',)), (R['Mod'], ('ver_canal',), ())},
       'Quem gerencia cargos recebe o detalhe (Membro nega, Mod libera)')
    mod.emit('entrar_canal', {'canal_id': staff}); ok(not erro(mod), 'Mod entra no canal')
    todos_limpam()

    # ---------- enviar mensagens: leitura sim, escrita não; negar vence liberar ----------
    quieto = novo_canal('quieto')
    dono.emit('canal_permissao', {'canal_id': quieto, 'cargo_id': None, 'negar': ['enviar_mensagens', 'fixar_mensagens']}); todos_limpam()
    dono.emit('canal_permissao', {'canal_id': quieto, 'cargo_id': R['Mod'], 'permitir': ['enviar_mensagens']}); todos_limpam()
    comum.emit('entrar_canal', {'canal_id': quieto}); ok(not erro(comum), 'Quem só perdeu "enviar" ainda ENTRA e lê o canal')
    comum.emit('enviar_mensagem', {'canal_id': quieto, 'texto': 'posso falar?', 'temp_id': 'tq1'})
    ev_c = ev(comum)
    ok(Message.query.filter_by(text='posso falar?').count() == 0 and any(m['name'] == 'erro_bazinga' for m in ev_c), 'Comum NÃO escreve onde "Enviar mensagens" está negado (e recebe o aviso)')
    ok(any(m['name'] == 'mensagem_recusada' and m['args'][0]['temp_id'] == 'tq1' for m in ev_c), 'A bolha otimista é desfeita (mensagem_recusada)')
    mod.emit('entrar_canal', {'canal_id': quieto})
    mod.emit('enviar_mensagem', {'canal_id': quieto, 'texto': 'moderador falando'}); ev(mod)
    ok(Message.query.filter_by(text='moderador falando').count() == 1, 'Cargo liberado (Mod) escreve por cima do Membro negado')
    extra.emit('enviar_mensagem', {'canal_id': quieto, 'texto': 'redator tentando'}); ev(extra)
    ok(Message.query.filter_by(text='redator tentando').count() == 0, 'Outro cargo sem liberação (Redator) herda a negação do Membro')
    dono.emit('enviar_mensagem', {'canal_id': quieto, 'texto': 'dono falando'}); ev(dono)
    ok(Message.query.filter_by(text='dono falando').count() == 1, 'Dono escreve sempre')
    adm.emit('entrar_canal', {'canal_id': quieto}); adm.emit('enviar_mensagem', {'canal_id': quieto, 'texto': 'vice falando'}); ev(adm)
    ok(Message.query.filter_by(text='vice falando').count() == 1, 'Administrador ignora a negação')
    # fixar negado ao Membro: o Mod tem "fixar" no cargo, mas o Membro-negado também o atinge (só uma liberação do cargo naquele canal o devolveria)
    mod.emit('fixar_mensagem', {'msg_id': Message.query.filter_by(text='moderador falando').first().id}); ev(mod)
    ok(Message.query.filter_by(text='moderador falando').first().is_pinned is not True, 'Negar "fixar" ao Membro tira o "fixar" do cargo Mod naquele canal (como no Discord: liberar de volta é por cargo)')
    # ---- negar vence liberar no mesmo nível: um cargo libera, outro nega o mesmo bit ----
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Mod'], 'cargo_id': R['Orador'], 'ativo': True}); todos_limpam()
    dono.emit('canal_permissao', {'canal_id': quieto, 'cargo_id': R['Orador'], 'negar': ['enviar_mensagens']}); todos_limpam()
    mod.emit('enviar_mensagem', {'canal_id': quieto, 'texto': 'agora nao pode'}); ev(mod)
    ok(Message.query.filter_by(text='agora nao pode').count() == 0, 'NEGAR vence LIBERAR: Mod (cargo libera) + Orador (cargo nega) = não escreve')
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Mod'], 'cargo_id': R['Orador'], 'ativo': False}); todos_limpam()
    mod.emit('enviar_mensagem', {'canal_id': quieto, 'texto': 'voltou a poder'}); ev(mod)
    ok(Message.query.filter_by(text='voltou a poder').count() == 1, 'Tirando o cargo que nega, volta a valer a liberação')
    # permitir e negar o MESMO bit no mesmo pedido: negar vence
    dono.emit('canal_permissao', {'canal_id': quieto, 'cargo_id': R['Redator'], 'permitir': ['enviar_mensagens'], 'negar': ['enviar_mensagens']}); todos_limpam()
    lin = ChannelOverwrite.query.filter_by(channel_id=quieto, role_id=R['Redator']).first()
    ok(lin is not None and lin.allow == 0 and lin.deny == cargos.BIT_CANAL['enviar_mensagens'], 'O mesmo bit nas duas listas vira só NEGAR')
    # lista fechada: id desconhecido e tipos errados são ignorados
    dono.emit('canal_permissao', {'canal_id': quieto, 'cargo_id': R['Redator'], 'permitir': ['inventada', 'gerenciar_servidor', 7, None], 'negar': 'tudo'}); todos_limpam()
    ok(ChannelOverwrite.query.filter_by(channel_id=quieto, role_id=R['Redator']).count() == 0, 'Só valem ids da lista de permissões de canal (o resto vira nada e a linha some)')

    # ---------- anúncios: o cargo com a permissão do servidor pode ser barrado só neste canal ----------
    av1 = novo_canal('avisos', tipo='anuncios'); av2 = novo_canal('avisos-gerais', tipo='anuncios')
    todos_limpam()
    extra.emit('enviar_mensagem', {'canal_id': av1, 'texto': 'comunicado 1'}); ev(extra)
    ok(Message.query.filter_by(text='comunicado 1').count() == 1, 'Redator (Publicar em anúncios) publica no canal de anúncios')
    dono.emit('canal_permissao', {'canal_id': av2, 'cargo_id': R['Redator'], 'negar': ['enviar_anuncios']}); todos_limpam()
    extra.emit('enviar_mensagem', {'canal_id': av2, 'texto': 'comunicado 2'}); ev(extra)
    ok(Message.query.filter_by(text='comunicado 2').count() == 0, 'Negar "publicar em anúncios" ao Redator só neste canal barra ele aqui')
    extra.emit('enviar_mensagem', {'canal_id': av1, 'texto': 'comunicado 3'}); ev(extra)
    ok(Message.query.filter_by(text='comunicado 3').count() == 1, 'E no outro canal de anúncios ele continua publicando')
    dono.emit('canal_permissao', {'canal_id': av2, 'cargo_id': R['Orador'], 'permitir': ['enviar_anuncios']}); todos_limpam()
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': R['Orador'], 'ativo': True}); todos_limpam()
    comum.emit('entrar_canal', {'canal_id': av2})
    comum.emit('enviar_mensagem', {'canal_id': av2, 'texto': 'comum publicando'}); ev(comum)
    ok(Message.query.filter_by(text='comum publicando').count() == 1, 'Liberar "publicar em anúncios" a um cargo só neste canal deixa quem tem o cargo publicar')
    comum.emit('enviar_mensagem', {'canal_id': av1, 'texto': 'comum publicando 2'}); ev(comum)
    ok(Message.query.filter_by(text='comum publicando 2').count() == 0, 'Mas não nos outros canais de anúncios')
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': R['Orador'], 'ativo': False}); todos_limpam()

    # ---------- apagar e fixar por canal ----------
    # Mod apaga no #geral (cargo) e, com negação só neste canal, não apaga em #quieto
    m_geral = Message(text='lixo geral', person_id=ids['Comum'], channel_id=geral); m_q = Message(text='lixo quieto', person_id=ids['Comum'], channel_id=quieto)
    db.session.add_all([m_geral, m_q]); db.session.commit()
    mod.emit('apagar_mensagem', {'msg_id': m_geral.id}); ev(mod)
    ok(Message.query.get(m_geral.id) is None, 'Sem sobrescrita, o Mod apaga a mensagem alheia (como antes)')
    dono.emit('canal_permissao', {'canal_id': quieto, 'cargo_id': R['Mod'], 'permitir': ['enviar_mensagens'], 'negar': ['apagar_mensagens']}); todos_limpam()
    mod.emit('apagar_mensagem', {'msg_id': m_q.id}); ev(mod)
    ok(Message.query.get(m_q.id) is not None, 'Negar "apagar mensagens" ao Mod só em #quieto impede aqui')
    outra = Message(text='lixo geral 2', person_id=ids['Comum'], channel_id=geral); db.session.add(outra); db.session.commit()
    mod.emit('apagar_mensagem', {'msg_id': outra.id}); ev(mod)
    ok(Message.query.get(outra.id) is None, 'E nos outros canais ele continua apagando')
    # fixar: o Membro está negado em #quieto
    comum.emit('fixar_mensagem', {'msg_id': m_q.id}); ev(comum)
    ok(Message.query.get(m_q.id).is_pinned is not True, 'Fixar negado ao Membro vale no canal')
    fix_geral = Message(text='fixavel geral', person_id=ids['Dono'], channel_id=geral); db.session.add(fix_geral); db.session.commit()
    comum.emit('fixar_mensagem', {'msg_id': fix_geral.id}); ev(comum)
    ok(Message.query.get(fix_geral.id).is_pinned is True, 'E em outro canal o Membro fixa normalmente')
    dono.emit('fixar_mensagem', {'msg_id': m_q.id}); ev(dono)
    ok(Message.query.get(m_q.id).is_pinned is True, 'Dono fixa em qualquer canal')

    # ---------- voz e palco ----------
    v1 = novo_canal('voz-a', tipo='voice'); v2 = novo_canal('voz-b', tipo='voice'); pal = novo_canal('palquinho', tipo='palco')
    todos_limpam()
    dono.emit('canal_permissao', {'canal_id': v1, 'cargo_id': None, 'negar': ['falar_voz']}); todos_limpam()
    comum.emit('entrar_call', {'peer_id': 'pc-a', 'canal_id': v1})
    papel = [m for m in ev(comum, 'palco_papel')]
    ok(papel and papel[-1]['args'][0]['ouvinte'] is True, 'Negar "falar na voz" ao Membro: entra no canal só como ouvinte')
    comum.emit('sair_call', {'canal_id': v1, 'peer_id': 'pc-a'}); ev(comum)
    comum.emit('entrar_call', {'peer_id': 'pc-b', 'canal_id': v2})
    papel = [m for m in ev(comum, 'palco_papel')]
    ok(papel and papel[-1]['args'][0]['ouvinte'] is False, 'Em outra voz sem sobrescrita ele fala normalmente')
    comum.emit('sair_call', {'canal_id': v2, 'peer_id': 'pc-b'}); ev(comum)
    dono.emit('canal_permissao', {'canal_id': v1, 'cargo_id': R['Orador'], 'permitir': ['falar_voz']}); todos_limpam()
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': R['Orador'], 'ativo': True}); todos_limpam()
    comum.emit('entrar_call', {'peer_id': 'pc-a2', 'canal_id': v1})
    ok([m for m in ev(comum, 'palco_papel')][-1]['args'][0]['ouvinte'] is False, 'Cargo liberado (Orador) fala na voz onde o Membro está negado')
    comum.emit('sair_call', {'canal_id': v1, 'peer_id': 'pc-a2'}); ev(comum)
    # palco: liberar falar_palco ao Orador só neste palco
    dono.emit('canal_permissao', {'canal_id': pal, 'cargo_id': R['Orador'], 'permitir': ['falar_palco']}); todos_limpam()
    comum.emit('entrar_call', {'peer_id': 'pc-p', 'canal_id': pal})
    ok([m for m in ev(comum, 'palco_papel')][-1]['args'][0]['ouvinte'] is False, 'Palco: quem tem o cargo liberado entra como orador')
    extra.emit('entrar_call', {'peer_id': 'pe-p', 'canal_id': pal})
    ok([m for m in ev(extra, 'palco_papel')][-1]['args'][0]['ouvinte'] is True, 'E quem não tem entra como ouvinte')
    comum.emit('palco_promover', {'canal_id': pal, 'person_id': ids['Extra'], 'ativo': True}); ev(comum); ev(extra)
    from app.events import participantes_call
    ok({p['usuario_id']: p['ouvinte'] for p in participantes_call[str(pal)]}[ids['Extra']] is False, 'Orador (por sobrescrita) chama um ouvinte pro palco')
    comum.emit('sair_call', {'canal_id': pal, 'peer_id': 'pc-p'}); extra.emit('sair_call', {'canal_id': pal, 'peer_id': 'pe-p'}); todos_limpam()
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': R['Orador'], 'ativo': False}); todos_limpam()

    # ---------- canal privado continua valendo ----------
    cofre = novo_canal('cofre', privado=True, membros=[ids['Mod']])
    todos_limpam()
    dono.emit('canal_permissao', {'canal_id': cofre, 'cargo_id': None, 'permitir': ['ver_canal']}); todos_limpam()
    ok(cofre not in canais_de(ultimo_srv(comum) or {}) and cofre not in canais_de(ultimo_srv(extra) or {}), 'Liberar "ver" ao Membro NÃO abre canal privado (a lista de convidados manda)')
    comum.emit('entrar_canal', {'canal_id': cofre}); ok(erro(comum), 'Comum não entra no privado mesmo com "ver" liberado')
    dono.emit('canal_permissao', {'canal_id': cofre, 'cargo_id': R['Mod'], 'negar': ['ver_canal']}); todos_limpam()
    mod.emit('entrar_canal', {'canal_id': cofre}); ok(erro(mod), 'Convidado ao privado que teve "ver" negado pelo cargo perde o acesso (a sobrescrita restringe)')
    # sai do privado: some pro Mod e a sala dele é limpa
    ok(cofre not in canais_de(ultimo_srv(mod) or {}), 'E o canal some da lista dele')

    # ---------- hierarquia e anti-escalada ----------
    ger.emit('canal_permissao', {'canal_id': geral, 'cargo_id': R['Gerente'], 'negar': ['apagar_mensagens']})
    ok(erro(ger) and ChannelOverwrite.query.filter_by(channel_id=geral).count() == 0, 'Gerente NÃO mexe na sobrescrita do cargo do próprio nível')
    ger.emit('canal_permissao', {'canal_id': geral, 'cargo_id': R['Vice'], 'negar': ['apagar_mensagens']})
    ok(erro(ger) and ChannelOverwrite.query.filter_by(channel_id=geral).count() == 0, 'Gerente NÃO mexe na sobrescrita de cargo ACIMA (Vice)')
    ger.emit('canal_permissao', {'canal_id': geral, 'cargo_id': R['Mod'], 'permitir': ['falar_palco']})
    ok(erro(ger) and ChannelOverwrite.query.filter_by(channel_id=geral).count() == 0, 'Gerente NÃO libera uma permissão que ele mesmo não tem ("falar no palco")')
    ger.emit('canal_permissao', {'canal_id': geral, 'cargo_id': R['Redator'], 'negar': ['enviar_anuncios']})
    ok(erro(ger) and ChannelOverwrite.query.filter_by(channel_id=geral).count() == 0, 'Nem NEGAR uma permissão que ele não tem ("publicar em anúncios")')
    ger.emit('canal_permissao', {'canal_id': geral, 'cargo_id': R['Redator'], 'permitir': ['apagar_mensagens', 'fixar_mensagens']})
    ok(not erro(ger) and ChannelOverwrite.query.filter_by(channel_id=geral, role_id=R['Redator']).count() == 1, 'Mas libera o que tem (apagar e fixar) a um cargo abaixo do dele')
    todos_limpam()
    ger.emit('canal_permissao', {'canal_id': geral, 'cargo_id': 99999, 'negar': ['enviar_mensagens']})
    ok(erro(ger), 'Cargo inexistente é recusado')
    # o Gerente não se tranca pra fora
    ger.emit('canal_permissao', {'canal_id': geral, 'cargo_id': None, 'negar': ['ver_canal']})
    ok(erro(ger) and ChannelOverwrite.query.filter_by(channel_id=geral, role_id=None).count() == 0, 'Gerente NÃO tira o próprio acesso ao canal (nega "ver" ao Membro sem ter uma liberação)')
    ger.emit('canal_permissao', {'canal_id': geral, 'cargo_id': None, 'negar': ['enviar_mensagens']})
    ok(not erro(ger) and ChannelOverwrite.query.filter_by(channel_id=geral, role_id=None).count() == 1, 'Gerente pode negar o "enviar" do Membro (não é "ver")')
    todos_limpam()
    # Gerente que não enxerga o canal escondido não consegue mexer nele
    ger.emit('canal_permissao', {'canal_id': staff, 'cargo_id': R['Mod'], 'negar': ['ver_canal']})
    ok(erro(ger), 'Quem não enxerga o canal NÃO mexe nas permissões dele')
    ok(ChannelOverwrite.query.filter_by(channel_id=staff, role_id=R['Mod']).first().allow == cargos.BIT_CANAL['ver_canal'], 'A sobrescrita do Mod em #staff segue como o dono deixou')
    # separador não aceita
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'linha', 'tipo': 'separador'}); ev(dono)
    sep = Channel.query.filter_by(server_id=sid, channel_type='separador').first()
    dono.emit('canal_permissao', {'canal_id': sep.id, 'cargo_id': None, 'negar': ['ver_canal']})
    ok(erro(dono) and not Channel.query.get(sep.id).sobrescrita, 'Separador não aceita permissões')
    # canal de OUTRO servidor
    outro = Server(name='Outro', owner_id=ids['Intruso']); db.session.add(outro); db.session.commit()
    canal_outro = Channel(name='x', server_id=outro.id); db.session.add(canal_outro); db.session.commit()
    dono.emit('canal_permissao', {'canal_id': canal_outro.id, 'cargo_id': None, 'negar': ['ver_canal']})
    ok(erro(dono) and ChannelOverwrite.query.filter_by(channel_id=canal_outro.id).count() == 0, 'Canal de outro servidor é recusado')
    dono.emit('canal_permissao', {'canal_id': geral, 'cargo_id': R['Orador'], 'negar': ['enviar_mensagens'], 'server_id': outro.id})
    ok(ChannelOverwrite.query.filter_by(channel_id=geral, role_id=R['Orador']).count() == 1, 'O server_id mandado pelo cliente não vale: o canal decide')

    # ---------- regra 6: dois clientes veem a mudança, e quem perdeu o canal sai da sala ----------
    abre = novo_canal('abre-e-fecha'); todos_limpam()
    comum.emit('entrar_canal', {'canal_id': abre}); extra.emit('entrar_canal', {'canal_id': abre}); todos_limpam()
    dono.emit('enviar_mensagem', {'canal_id': abre, 'texto': 'antes de fechar'}); ev(dono)
    ok(any(m['name'] == 'receber_mensagem' for m in ev(comum)) and any(m['name'] == 'receber_mensagem' for m in ev(extra)), 'Antes: os dois recebem as mensagens do canal')
    dono.emit('canal_permissao', {'canal_id': abre, 'cargo_id': R['Redator'], 'negar': ['ver_canal']})
    ev(dono)
    s_c = ultimo_srv(comum)
    ok(s_c is not None and abre in canais_de(s_c) and 'ow' not in canais_de(s_c)[abre], 'Comum segue vendo o canal (só o Redator foi negado)')
    s_e = ultimo_srv(extra)
    ok(s_e is not None and abre not in canais_de(s_e), 'Extra (Redator) recebe a lista SEM o canal (regra 6)')
    dono.emit('enviar_mensagem', {'canal_id': abre, 'texto': 'depois de fechar'}); ev(dono)
    ok(any(m['name'] == 'receber_mensagem' for m in ev(comum)), 'Comum (sem o cargo negado) continua recebendo')
    ok(not any(m['name'] == 'receber_mensagem' for m in ev(extra)), 'Extra (Redator, negado) para de receber as mensagens do canal (saiu da sala)')
    extra.emit('enviar_mensagem', {'canal_id': abre, 'texto': 'ainda aqui'}); ev(extra)
    ok(Message.query.filter_by(text='ainda aqui').count() == 0, 'E não consegue mais escrever')
    # a mudança chega por cargo também (regra 6): tirar o cargo devolve o canal
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Extra'], 'cargo_id': R['Redator'], 'ativo': False})
    ok(abre in canais_de(ultimo_srv(extra) or {}), 'Tirar o cargo negado devolve o canal na hora, na lista dele')
    todos_limpam()

    # ---------- cargo apagado limpa as sobrescritas ----------
    so_mod = novo_canal('so-mod'); todos_limpam()
    dono.emit('canal_permissao', {'canal_id': so_mod, 'cargo_id': R['Mod'], 'negar': ['enviar_mensagens']}); todos_limpam()
    ok(Channel.query.get(so_mod).sobrescrita is True, 'Canal com uma única sobrescrita (a do Mod) está marcado')
    antes = ChannelOverwrite.query.filter_by(role_id=R['Mod']).count()
    ok(antes >= 2, f'O cargo Mod tem sobrescritas em vários canais ({antes})')
    dono.emit('cargo_apagar', {'server_id': sid, 'cargo_id': R['Mod']}); todos_limpam()
    ok(ChannelOverwrite.query.filter_by(role_id=R['Mod']).count() == 0, 'Apagar o cargo apaga as sobrescritas dele')
    ok(Channel.query.get(so_mod).sobrescrita is False and Channel.query.get(cofre).sobrescrita is True and Channel.query.get(quieto).sobrescrita is True,
       'Canal que ficou sem nenhuma desmarca a flag; os que ainda têm outras (a do Membro) continuam marcados')
    ok(cofre not in canais_de(ultimo_srv(comum) or {}), 'Privado sem sobrescrita continua privado (comum não vê)')

    # ---------- desfazer: limpar tudo desmarca o canal e devolve o custo zero ----------
    for rid in (None, R['Mod'], R['Orador'], R['Redator']):
        dono.emit('canal_permissao', {'canal_id': staff, 'cargo_id': rid}); ev(dono)
    ok(ChannelOverwrite.query.filter_by(channel_id=staff).count() == 0 and not Channel.query.get(staff).sobrescrita, 'Limpar todas as linhas desmarca o canal')
    s_c = ultimo_srv(comum)
    ok(s_c is None or staff in canais_de(s_c), 'Comum volta a ver o canal limpo')
    ok(all('perms' not in x for x in canais_de(s_c).values() if x['id'] == staff) if s_c else True, 'Canal limpo volta a ser um canal comum no payload')

    # ---------- canal apagado leva as sobrescritas junto ----------
    dono.emit('apagar_canal', {'canal_id': quieto}); ev(dono)
    ok(ChannelOverwrite.query.filter_by(channel_id=quieto).count() == 0, 'Apagar o canal apaga as sobrescritas')

    # ---------- listas do cliente = servidor ----------
    js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'static', 'js', 'cargos.js'), encoding='utf-8').read()
    import re
    bloco = re.search(r"const PERMS_CANAL = \[(.*?)\n    \];", js, re.S)
    ok(bool(bloco) and re.findall(r"\['([a-z_]+)',", bloco.group(1)) == list(cargos.IDS_PERMS_CANAL), 'cargos.js lista as mesmas permissões de canal, na mesma ordem')
    ok(set(cargos.IDS_PERMS_CANAL) - {'ver_canal', 'enviar_mensagens'} <= set(cargos.IDS_PERMISSAO), 'Toda permissão de canal que não é só-de-canal é uma do servidor (mesmos bits)')
    ok(all(cargos.BIT_CANAL[i] == cargos.BIT[i] for i in cargos.IDS_PERMS_CANAL if i in cargos.BIT), 'E usa o MESMO bit do servidor')
    ok(not (cargos.PADRAO_CANAL & cargos.TODAS), 'ver_canal e enviar_mensagens não colidem com nenhum bit do servidor (servidor antigo não perde nada)')
    # resolver puro
    P = cargos.PERMS_MEMBRO_PADRAO
    r1 = cargos.resolver(P, [], [(None, 0, cargos.BIT_CANAL['ver_canal'])])
    ok(not r1 & cargos.BIT_CANAL['ver_canal'], 'resolver: Membro negado perde "ver"')
    r2 = cargos.resolver(P, [7], [(None, 0, cargos.BIT_CANAL['ver_canal']), (7, cargos.BIT_CANAL['ver_canal'], 0)])
    ok(r2 & cargos.BIT_CANAL['ver_canal'], 'resolver: cargo liberado vence o Membro negado')
    r3 = cargos.resolver(P, [7, 8], [(7, cargos.BIT_CANAL['ver_canal'], 0), (8, 0, cargos.BIT_CANAL['ver_canal'])])
    ok(not r3 & cargos.BIT_CANAL['ver_canal'], 'resolver: dois cargos, um libera e outro nega = nega')
    r4 = cargos.resolver(P | cargos.BIT['administrador'], [], [(None, 0, cargos.TODAS_CANAL)])
    ok(r4 == cargos.TODAS_CANAL, 'resolver: Administrador ignora tudo')

    print()
    print('FALHAS:', 'nenhuma' if not falhas else falhas)
    sys.exit(1 if falhas else 0)
