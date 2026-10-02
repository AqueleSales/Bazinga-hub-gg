"""Cosméticos: nível 1-1000+ e patentes, catálogo/posse, equipar com checagem no servidor, insígnias."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person, Posse
from app import cosmeticos as cos
from app import utils as u

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


# ---------- 1. curva de XP: os 100 primeiros níveis NÃO mudaram; 1000+ existe ----------
ok(u.xp_do_nivel(1) == 0 and u.xp_do_nivel(2) == 100, 'Nível 2 continua custando 100 XP')
ok(u.xp_do_nivel(100) == 999_504, 'Chegar ao nível 100 continua custando 999.504 XP (quem já tinha nível não mudou)')
ok(u.custo_do_passo(99) == 20_092, 'Passo 99->100 continua em 20.092 XP')
ok(u.custo_do_passo(100) == 20_117, 'Do 100 em diante o passo cresce 25 XP por nível')
ok(u.xp_do_nivel(1000) > u.xp_do_nivel(999) > u.xp_do_nivel(101) > u.xp_do_nivel(100), 'A tabela é estritamente crescente até 1000')
ok(all(u.nivel_da_pessoa(u.xp_do_nivel(n)) == n for n in (1, 2, 9, 10, 50, 99, 100, 101, 500, 999, 1000, 1001, 1500)),
   'nivel_da_pessoa(xp_do_nivel(n)) == n (ida e volta) em níveis de borda')
ok(all(u.nivel_da_pessoa(u.xp_do_nivel(n) - 1) == n - 1 for n in (2, 10, 100, 101, 1000, 1001)),
   '1 XP a menos que o limiar = nível anterior')
ok(u.nivel_da_pessoa(0) == 1 and u.nivel_da_pessoa(None) == 1 and u.nivel_da_pessoa(-5) == 1, 'XP zero/None/negativo = nível 1')
ok(u.nivel_da_pessoa(u.xp_do_nivel(1000) + 3 * u.custo_do_passo(1000)) == 1003, 'Depois do 1000 sobe um nível por passo fixo ("1000+")')
atual, falta = u.progresso_de_nivel(u.xp_do_nivel(1200) + 5)
ok(atual == 5 and falta == u.custo_do_passo(1000), 'Barra de progresso funciona no 1000+')
ok(len(u.marcos_da_pagina(1)) == 100 and u.marcos_da_pagina(1)[0]['nivel'] == 1, 'Trilha: página 1 = níveis 1-100')
ok(u.marcos_da_pagina(150)[0]['nivel'] == 101 and u.marcos_da_pagina(150)[-1]['nivel'] == 200, 'Trilha: nível 150 mostra 101-200')
ok(u.marcos_da_pagina(100)[-1]['nivel'] == 100, 'Trilha: nível 100 ainda está na página 1-100')

# ---------- 2. patentes ----------
ps = cos.PATENTES
ok(len(ps) == len({p['id'] for p in ps}), 'Ids de patente são únicos')
ok(ps[0]['de'] == 1 and all(ps[i]['ate'] + 1 == ps[i + 1]['de'] for i in range(len(ps) - 1)), 'Patentes cobrem os níveis sem buraco nem sobreposição')
ok(ps[-1]['ate'] is None, 'A última patente não tem teto')
ok([p['anim'] for p in ps] == sorted(p['anim'] for p in ps), 'A animação só sobe com a patente (nunca desce)')
for p in ps:
    lim = p['limites']
    ok(lim[0] == p['de'] and lim[0] < lim[1] < lim[2], f"Subníveis de {p['nome']} crescem ({lim})")
    if p['ate'] is not None:
        ok(lim[2] <= p['ate'], f"O subnível III de {p['nome']} cabe na faixa")
pat = cos.patente_do_nivel
ok(pat(1)['nome_completo'] == 'Iniciado I', 'Nível 1 = Iniciado I')
ok(pat(9)['nome_completo'] == 'Iniciado III', 'Nível 9 = Iniciado III')
ok(pat(10)['nome_completo'] == 'Aprendiz I' and pat(10)['proximo']['nivel'] == 15, 'Nível 10 = Aprendiz I e o próximo subnível vem no 15')
ok(pat(9)['proximo']['nova_patente'] is True and pat(9)['proximo']['nivel'] == 10, 'No Iniciado III o próximo passo é uma patente nova (nível 10)')
ok(pat(1000)['id'] == 'panteao' and pat(5000)['nome_completo'] == 'Panteão III', 'Nível 1000 e 5000 caem no Panteão III')
ok(pat(5000)['proximo'] is None, 'Quem está no topo não tem "próxima patente"')
ok(cos.patente_comeca_em(10) == 'Aprendiz' and cos.patente_comeca_em(11) is None and cos.patente_comeca_em(1) is None,
   'recompensa de patente só no 1º nível dela (e nunca no nível 1)')
ok(u.recompensa_do_nivel(25)['titulo'] == 'Explorador' and u.recompensa_do_nivel(26)['titulo'] is None, 'recompensa_do_nivel carrega o nome da patente nova')
ok(u.titulo_do_nivel(12) == 'Aprendiz I', 'titulo_do_nivel agora devolve patente + subnível')

# ---------- 3. catálogo ----------
ok(all(d['tipo'] in cos.ROTULO_TIPO for d in cos.CATALOGO.values()), 'Todo item tem um tipo conhecido')
ok(all(i == f"{d['tipo']}:{d['valor']}" for i, d in cos.CATALOGO.items()), 'item_id == "<tipo>:<valor>"')
ok('gogeta' in u.MOLDURAS and 'sasuke' in u.PLACAS and 'fusao' in u.ESTILOS_NOME and 'gogeta' in u.FAIXAS_ANIMADAS,
   'Ids exclusivos entram nas tuplas de validação do servidor')
ok(set(cos.PACOTES['gogeta']) >= {'moldura', 'placa', 'nome', 'faixa', 'efeito_avatar', 'efeito_perfil'}, 'Pacote Gogeta cobre os tipos do tema')
ok('badge' not in cos.PACOTES['gogeta'] and 'pacote' not in cos.PACOTES['gogeta'], 'Pacote não inclui insígnia nem outro pacote')
ok(all(i in cos.CATALOGO for itens in cos.LABORATORIO.values() for i in itens), 'Todo item concedido no laboratório existe no catálogo')

# ---------- 4. posse + equipar ----------
with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for nome, user in (('Aquele Sales', 'aquele.sales'), ('Filippo', 'filippo.chiarion'), ('Estranho', 'estranho')):
        p = Person(name=nome, email=f'{user}@x', role_id=r.id, username=user)
        db.session.add(p); db.session.commit(); ids[user] = p.id

    cos.conceder_laboratorio(lambda *_: None)
    p_sales = cos.posses_da_pessoa(ids['aquele.sales'])
    p_fil = cos.posses_da_pessoa(ids['filippo.chiarion'])
    ok('badge:criador' in p_sales and 'badge:criador' in p_fil and 'badge:coder' in p_fil, 'Criador, Beta Tester e Coder: os dois')
    ok('badge:so_nos' in p_sales and 'badge:so_nos' in p_fil, '"Só nós": os dois')
    ok('moldura:gogeta' in p_sales and 'moldura:gogeta' not in p_fil, 'Gogeta é do dono, não do amigo')
    ok('moldura:sasuke' in p_fil and 'moldura:sasuke' not in p_sales, 'Sasuke é do amigo, não do dono')
    ok('moldura:fusao' in p_sales and 'moldura:fusao' in p_fil, 'Fusão é dos dois')
    ok(not cos.posses_da_pessoa(ids['estranho']), 'Quem não é tester não recebe nada')
    n1 = db.session.query(Posse).count()
    cos.conceder_laboratorio(lambda *_: None)
    ok(db.session.query(Posse).count() == n1, 'conceder_laboratorio é idempotente (rodar de novo não duplica)')
    ok(cos.badges_do_conjunto(p_sales) == ['criador', 'beta_tester', 'coder', 'so_nos'], 'Insígnias saem na ordem do catálogo')

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    sales, fsales = cliente('aquele.sales'); fil, _ = cliente('filippo.chiarion'); est, fest = cliente('estranho')

    # equipar o que tem
    sales.emit('equipar_item', {'item_id': 'moldura:gogeta'})
    rec = ev(sales)
    pa = [m for m in rec if m['name'] == 'perfil_atualizado']
    ok(pa and pa[-1]['args'][0]['moldura'] == 'gogeta', 'Equipar item que possui: moldura vira "gogeta" e o servidor confirma')
    ok(any(m['name'] == 'inventario' and m['args'][0]['equipados'].get('moldura') == 'gogeta' for m in rec), 'O inventário devolvido mostra o item equipado')
    ok(db.session.get(Person, ids['aquele.sales']).moldura == 'gogeta', 'Ficou gravado no banco')

    # NÃO pode equipar o do outro (regra 4)
    fil.emit('equipar_item', {'item_id': 'moldura:gogeta'})
    rec = ev(fil)
    ok(any(m['name'] == 'erro_bazinga' for m in rec), 'Equipar item que NÃO possui é recusado com erro')
    ok(db.session.get(Person, ids['filippo.chiarion']).moldura is None, 'E nada muda no banco')
    est.emit('equipar_item', {'item_id': 'pacote:gogeta'}); ev(est)
    ok(db.session.get(Person, ids['estranho']).moldura is None, 'Estranho não equipa pacote que não tem')

    # id inventado / injeção
    for lixo in ('moldura:" onmouseover="x', 'moldura:padrao', 'moldura:nenhuma', 'xablau:foo', 'badge:criador', '', 'efeito_avatar:inexistente', 'moldura:' + 'a' * 500):
        sales.emit('equipar_item', {'item_id': lixo}); ev(sales)
    s = db.session.get(Person, ids['aquele.sales'])
    ok(s.moldura == 'gogeta', 'Ids inventados/badge/padrão não derrubam nem trocam a moldura equipada')

    # atualizar_perfil também confere a posse (o caminho antigo do editor)
    fil.emit('atualizar_perfil', {'moldura': 'gogeta', 'placa': 'gogeta', 'nome_estilo': 'gogeta', 'banner_color': 'anim:gogeta'})
    rec = ev(fil)
    f = db.session.get(Person, ids['filippo.chiarion'])
    ok(f.moldura is None and f.placa is None and f.nome_estilo is None and f.banner_color is None,
       'atualizar_perfil recusa moldura/placa/nome/faixa exclusivos sem posse')
    ok(any(m['name'] == 'erro_bazinga' for m in rec), 'e avisa com um toast de erro')
    fil.emit('atualizar_perfil', {'moldura': 'sasuke', 'placa': 'sasuke', 'nome_estilo': 'sasuke', 'banner_color': 'anim:sasuke', 'bio': 'oi'})
    ev(fil)
    f = db.session.get(Person, ids['filippo.chiarion'])
    ok((f.moldura, f.placa, f.nome_estilo, f.banner_color) == ('sasuke', 'sasuke', 'sasuke', 'anim:sasuke'),
       'atualizar_perfil aceita os exclusivos que a pessoa possui')
    ok(f.bio == 'oi', 'e o resto do perfil salva junto')
    # pedir o que não tem NÃO apaga o que já estava equipado
    fil.emit('atualizar_perfil', {'moldura': 'gogeta'}); ev(fil)
    ok(db.session.get(Person, ids['filippo.chiarion']).moldura == 'sasuke', 'Pedir item sem posse não apaga a moldura que já estava equipada')
    # id fora do catálogo limpa (comportamento antigo)
    fil.emit('atualizar_perfil', {'moldura': 'nenhuma'}); ev(fil)
    ok(db.session.get(Person, ids['filippo.chiarion']).moldura is None, '"nenhuma" continua limpando a moldura')
    # itens livres seguem livres
    est.emit('atualizar_perfil', {'moldura': 'fogo', 'placa': 'lava', 'nome_estilo': 'neon', 'banner_color': 'anim:aurora'}); ev(est)
    e = db.session.get(Person, ids['estranho'])
    ok((e.moldura, e.placa, e.nome_estilo, e.banner_color) == ('fogo', 'lava', 'neon', 'anim:aurora'), 'Itens livres continuam livres pra todo mundo')

    # slots em JSON
    sales.emit('equipar_item', {'item_id': 'efeito_avatar:gogeta'}); ev(sales)
    sales.emit('equipar_item', {'item_id': 'efeito_perfil:gogeta'}); ev(sales)
    ok(cos.equipados_da_pessoa(db.session.get(Person, ids['aquele.sales'])) == {'efeito_avatar': 'gogeta', 'efeito_perfil': 'gogeta'},
       'Efeito de avatar e de perfil ficam no JSON de equipados')
    sales.emit('equipar_item', {'item_id': 'efeito_avatar:sasuke'}); ev(sales)
    ok(cos.equipados_da_pessoa(db.session.get(Person, ids['aquele.sales'])).get('efeito_avatar') == 'gogeta', 'Efeito do outro tema é recusado')
    # JSON adulterado no banco nunca vira class=""
    s = db.session.get(Person, ids['aquele.sales'])
    s.equipados = '{"efeito_avatar": "\\" onload=\\"x", "efeito_perfil": "gogeta", "lixo": "gogeta"}'; db.session.commit()
    ok(cos.equipados_da_pessoa(s) == {'efeito_perfil': 'gogeta'}, 'JSON adulterado: só o que o catálogo conhece sai')
    s.equipados = 'isso não é json'; db.session.commit()
    ok(cos.equipados_da_pessoa(s) == {}, 'JSON quebrado vira vazio, sem derrubar nada')

    # desequipar
    sales.emit('equipar_item', {'item_id': 'efeito_avatar:gogeta'}); ev(sales)
    sales.emit('desequipar_item', {'tipo': 'moldura'}); ev(sales)
    sales.emit('desequipar_item', {'tipo': 'efeito_avatar'}); ev(sales)
    sales.emit('desequipar_item', {'tipo': 'faixa'}); sales.emit('desequipar_item', {'tipo': 'xablau'}); ev(sales)
    s = db.session.get(Person, ids['aquele.sales'])
    ok(s.moldura is None and 'efeito_avatar' not in cos.equipados_da_pessoa(s), 'Desequipar limpa moldura e efeito')

    # pacote
    sales.emit('equipar_item', {'item_id': 'pacote:gogeta'}); ev(sales)
    s = db.session.get(Person, ids['aquele.sales'])
    ok((s.moldura, s.placa, s.nome_estilo, s.banner_color) == ('gogeta', 'gogeta', 'gogeta', 'anim:gogeta'), 'Pacote Gogeta equipa moldura, placa, nome e faixa')
    ok(cos.equipados_da_pessoa(s).get('efeito_avatar') == 'gogeta', 'e os efeitos em JSON')
    sales.emit('equipar_item', {'item_id': 'pacote:sasuke'}); ev(sales)
    ok(db.session.get(Person, ids['aquele.sales']).moldura == 'gogeta', 'Pacote do outro tema é recusado (sem posse do pacote)')

    # ---------- 5. quem vê o quê (regra 6: avisa quem convive) ----------
    sales.emit('listar_inventario')
    inv = ev(sales, 'inventario')[-1]['args'][0]
    ok('moldura:gogeta' in inv['posses'] and any(i['id'] == 'badge:criador' for i in inv['catalogo']), 'listar_inventario devolve posses e descritores')
    ok(len(inv['patentes']) == len(cos.PATENTES), 'e a tabela de patentes (galeria)')
    fil.emit('listar_inventario')
    inv_f = ev(fil, 'inventario')[-1]['args'][0]
    ok('moldura:gogeta' not in inv_f['posses'] and not any(i['id'] == 'moldura:gogeta' for i in inv_f['catalogo']),
       'O inventário do amigo NÃO mostra os itens exclusivos do dono')

    # cartão de perfil: insígnias + patente + efeitos equipados chegam a quem convive
    from app.models import Server
    srv = Server(name='S', owner_id=ids['aquele.sales']); db.session.add(srv); db.session.flush()
    for who in ('aquele.sales', 'filippo.chiarion'):
        srv.members.append(db.session.get(Person, ids[who]))
    db.session.commit()
    p = db.session.get(Person, ids['aquele.sales']); p.xp = u.xp_do_nivel(230); db.session.commit()
    fil, _ = cliente('filippo.chiarion')
    fil.emit('obter_perfil', {'usuario_id': ids['aquele.sales']})
    perf = ev(fil, 'perfil_publico')[-1]['args'][0]
    ok(perf['badges'] == ['criador', 'beta_tester', 'coder', 'so_nos'], 'Cartão do dono mostra as 4 insígnias')
    ok(perf['patente']['id'] == 'lenda' and perf['nivel'] == 230, 'Cartão traz a patente do nível 230 (Lenda)')
    ok(perf['equipados'].get('efeito_perfil') == 'gogeta', 'Cartão traz os efeitos equipados')
    fil.emit('obter_perfil', {'usuario_id': ids['filippo.chiarion']})
    ok(ev(fil, 'perfil_publico')[-1]['args'][0]['badges'] == ['criador', 'beta_tester', 'coder', 'so_nos'], 'Cartão do amigo também mostra as 4 insígnias')
    est.emit('obter_perfil', {'usuario_id': ids['aquele.sales']})
    restrito = ev(est, 'perfil_publico')[-1]['args'][0]
    ok(restrito.get('restrito') and 'badges' not in restrito, 'Quem não convive não recebe nem as insígnias')

    # equipar avisa os outros membros do servidor (regra 6)
    ev(fil)
    sales.emit('equipar_item', {'item_id': 'moldura:fusao'}); ev(sales)
    mudou = [m for m in ev(fil, 'perfil_membro_mudou') if m['args'][0]['usuario_id'] == ids['aquele.sales']]
    ok(mudou and mudou[-1]['args'][0]['moldura'] == 'fusao', 'Equipar avisa quem convive (perfil_membro_mudou leva a moldura nova)')

    # /chat entrega o inventário no HTML (sem esperar o socket)
    html = fsales.get('/chat').get_data(as_text=True)
    ok('moldura:fusao' in html or 'fusao' in html, '/chat responde 200 com o inventário embutido')
    ok(fest.get('/chat').status_code == 200, '/chat de quem não tem nada também responde')

    # mensagens carregam os efeitos do autor
    from app.models import Channel, Message
    ch = Channel(name='geral', channel_type='text', server_id=srv.id); db.session.add(ch); db.session.commit()
    db.session.add(Message(text='oi', person_id=ids['aquele.sales'], channel_id=ch.id)); db.session.commit()
    resp = fsales.get(f'/api/mensagens/{ch.id}').get_json()
    ok(isinstance(resp, list) and resp and 'equipados' in resp[-1], '/api/mensagens leva "equipados" do autor')

    # ---------- 6. slots de comportamento: fala, radar, chat, som, pin ----------
    sales, _ = cliente('aquele.sales')   # reconecta: agora ele está na sala do servidor (entrou nela depois do connect antigo)
    ok({'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota'} <= set(cos.PACOTES['gogeta']) and
       {'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota'} <= set(cos.PACOTES['sasuke']),
       'Pacotes Gogeta e Sasuke cobrem os slots de comportamento')
    ok('efeito_fala' not in cos.PACOTES['fusao'], 'Pacote Fusão só tem o que a Fusão tem (sem efeitos de comportamento)')
    sales.emit('equipar_item', {'item_id': 'pacote:gogeta'}); ev(sales)
    eq_s = cos.equipados_da_pessoa(db.session.get(Person, ids['aquele.sales']))
    ok(eq_s.get('efeito_fala') == 'gogeta' and eq_s.get('pin_nota') == 'gogeta' and eq_s.get('som_call') == 'gogeta', 'Pacote equipa fala, pin e som')
    fil.emit('equipar_item', {'item_id': 'som_call:gogeta'}); ev(fil)
    ok('som_call' not in cos.equipados_da_pessoa(db.session.get(Person, ids['filippo.chiarion'])), 'Som do outro tema é recusado')
    fil.emit('equipar_item', {'item_id': 'pacote:sasuke'}); ev(fil)

    # nota do mapa leva o pin do AUTOR (e só um pin que ele possui)
    from app.models import GeoNote
    nota = GeoNote(lat=-15.8, lng=-47.9, text='oi', color='#fff', author_id=ids['aquele.sales'], expires_at=None)
    db.session.add(nota); db.session.commit()
    ok(u.nota_para_json(nota)['pin'] == 'gogeta', 'nota_para_json leva o pin equipado pelo autor')
    outra = GeoNote(lat=-15.8, lng=-47.9, text='oi', color='#fff', author_id=ids['estranho'], expires_at=None)
    db.session.add(outra); db.session.commit()
    ok(u.nota_para_json(outra)['pin'] is None, 'Quem não equipou pin: pin = None')

    # call: o servidor diz o visual de cada participante (o peer não pode afirmar item que não tem)
    from app.models import Channel
    voz = Channel(name='Lobby', channel_type='voice', server_id=srv.id); db.session.add(voz); db.session.commit()
    ev(sales); ev(fil)
    sales.emit('entrar_call', {'canal_id': str(voz.id), 'peer_id': 'peer-sales'}); ev(sales); ev(fil)
    fil.emit('entrar_call', {'canal_id': str(voz.id), 'peer_id': 'peer-fil'})
    novo = [m for m in ev(sales, 'novo_usuario_call')]
    ok(novo and novo[-1]['args'][0]['peer_id'] == 'peer-fil' and novo[-1]['args'][0]['equipados'].get('efeito_fala') == 'sasuke',
       'novo_usuario_call leva os efeitos equipados de quem entrou (vindos do servidor)')
    ok(novo and novo[-1]['args'][0]['moldura'] == 'sasuke', '... e a moldura')
    from app.events import participantes_call
    lista = participantes_call.get(str(voz.id), [])
    ok(len(lista) == 2 and all('equipados' in p for p in lista), 'participantes_call guarda o visual de cada um (pra quem chega depois)')
    ok(next(p for p in lista if p['peer_id'] == 'peer-sales')['equipados'].get('som_call') == 'gogeta', 'incluindo o som de entrada')

    # equipar/desequipar NO MEIO da call avisa os outros participantes (regra 6)
    ev(sales); ev(fil)
    fil.emit('desequipar_item', {'tipo': 'efeito_fala'}); ev(fil)
    aviso = [m for m in ev(sales, 'participantes_call_mudou')]
    eu_fil = aviso and next((p for p in aviso[-1]['args'][0]['participantes'] if p['peer_id'] == 'peer-fil'), None)
    ok(eu_fil is not None and 'efeito_fala' not in eu_fil['equipados'] and eu_fil['equipados'].get('efeito_avatar') == 'sasuke',
       'Desequipar durante a call atualiza o visual do participante pra quem está nela (participantes_call_mudou)')

    # ---------- 7. efeito de servidor: só o DONO, só com posse; todo membro vê (regra 6) ----------
    ok('efeito_servidor' not in cos.PACOTES['gogeta'], 'Efeito de servidor não entra em pacote (é do servidor, não da pessoa)')
    ev(sales); ev(fil)
    fil.emit('aplicar_efeito_servidor', {'server_id': srv.id, 'valor': 'sasuke'})
    ok(any(m['name'] == 'erro_bazinga' for m in ev(fil)) and db.session.get(Server, srv.id).efeito is None,
       'Membro que NÃO é dono não aplica efeito no servidor')
    sales.emit('aplicar_efeito_servidor', {'server_id': srv.id, 'valor': 'sasuke'})
    ok(any(m['name'] == 'erro_bazinga' for m in ev(sales)) and db.session.get(Server, srv.id).efeito is None,
       'Dono SEM a posse do item (é do tema do amigo) é recusado')
    sales.emit('aplicar_efeito_servidor', {'server_id': srv.id, 'valor': '" onload="x'}); ev(sales)
    ok(db.session.get(Server, srv.id).efeito is None, 'Id inventado não grava nada')
    sales.emit('aplicar_efeito_servidor', {'server_id': srv.id, 'valor': 'gogeta'})
    rec_s = ev(sales)
    ok(db.session.get(Server, srv.id).efeito == 'gogeta', 'Dono com a posse aplica o efeito')
    visto = [m for m in ev(fil, 'servidor_discord_criado') if m['args'][0]['id'] == srv.id]
    ok(visto and visto[-1]['args'][0]['efeito'] == 'gogeta', 'Os outros membros recebem o servidor com o efeito (regra 6)')
    ok(any(m['name'] == 'efeito_servidor_aplicado' for m in rec_s), 'Quem aplicou recebe a confirmação')
    db.session.get(Server, srv.id).efeito = 'xablau'; db.session.commit()
    from app.events import servidor_para_json
    ok(servidor_para_json(db.session.get(Server, srv.id))['efeito'] is None, 'Valor adulterado no banco nunca sai pro cliente')
    db.session.get(Server, srv.id).efeito = 'gogeta'; db.session.commit()
    sales.emit('aplicar_efeito_servidor', {'server_id': srv.id, 'valor': ''}); ev(sales)
    ok(db.session.get(Server, srv.id).efeito is None, 'Valor vazio remove o efeito')
    # pino no mapa leva o efeito do servidor
    from app.models import MapServer
    pino = MapServer(name='S', lat=-15.8, lng=-47.9, owner_id=ids['aquele.sales'], server_id=srv.id)
    db.session.add(pino); db.session.commit()
    db.session.get(Server, srv.id).efeito = 'gogeta'; db.session.commit()
    ok(u.servidor_mapa_para_json(pino)['efeito'] == 'gogeta', 'servidor_mapa_para_json leva o efeito (pino no mapa)')

    # ---------- 8. quem não é tester: o inventário funciona só com itens livres ----------
    est, fest = cliente('estranho')
    est.emit('equipar_item', {'item_id': 'moldura:aurora'}); ev(est)
    est.emit('equipar_item', {'item_id': 'faixa:menta'}); ev(est)
    est.emit('equipar_item', {'item_id': 'nome:neon'}); ev(est)
    e = db.session.get(Person, ids['estranho'])
    ok((e.moldura, e.banner_color, e.nome_estilo) == ('aurora', 'anim:menta', 'neon'), 'Item LIVRE se equipa pelo inventário sem precisar de posse')
    est.emit('equipar_item', {'item_id': 'moldura:fusao'}); ev(est)
    est.emit('equipar_item', {'item_id': 'efeito_chat:gogeta'}); ev(est)
    e = db.session.get(Person, ids['estranho'])
    ok(e.moldura == 'aurora' and not cos.equipados_da_pessoa(e), 'Quem não é tester não equipa nada exclusivo (e o livre equipado segue)')
    est.emit('desequipar_item', {'tipo': 'moldura'}); ev(est)
    ok(db.session.get(Person, ids['estranho']).moldura is None, 'Desequipar item livre limpa o slot')
    est.emit('listar_inventario')
    inv_e = ev(est, 'inventario')[-1]['args'][0]
    ok(inv_e['posses'] == [] and inv_e['catalogo'] == [], 'O inventário de quem não é tester não tem nenhum exclusivo')

print()
print('TUDO CERTO' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
