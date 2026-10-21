"""Rodada 29: categorias, separadores, organização da lista de canais, tipos de canal (anúncios, regras, mídia, voz com limite, palco),
ícone validado e personalização do servidor. SQLite em memória + socketio.test_client (molde: fumaca_servidor.py)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import cargos
from app.models import Role, Person, Server, Channel, Message, ChannelCategory, ServerRole

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


def estrutura(cli):
    r = ev(cli, 'servidor_estrutura')
    return r[-1]['args'][0] if r else None


def canais_de(s, cat):
    return [c['name'] for c in sorted([c for c in s['channels'] if c['categoria_id'] == cat], key=lambda c: c['pos'])]


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Gerente', 'Comum', 'Terceiro', 'Intruso'):
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
    dono.emit('criar_convite', {'server_id': sid}); codigo = ev(dono, 'convite_criado')[-1]['args'][0]['code']
    cl, fcl = {}, {}
    for n in ('Gerente', 'Comum', 'Terceiro'):
        cl[n], fcl[n] = cliente(n)
        cl[n].emit('entrar_por_convite', {'code': codigo}); ev(cl[n])
    intruso, fint = cliente('Intruso')
    ev(dono)
    comum, ger = cl['Comum'], cl['Gerente']
    geral = Channel.query.filter_by(server_id=sid, channel_type='text').first().id
    voz_geral = Channel.query.filter_by(server_id=sid, channel_type='voice').first().id

    # ---------- servidor antigo: seções "virtuais", nada de categoria no banco ----------
    dono.emit('listar_membros_servidor', {'server_id': sid}); ev(dono)
    ok(ChannelCategory.query.count() == 0, 'Servidor novo/antigo não tem categoria no banco (o cliente desenha as duas seções padrão)')
    srv0 = ev(dono, 'servidor_discord_criado')
    dono.emit('categoria_criar', {'server_id': sid, 'nome': ' Aventura  '}); s = estrutura(dono)
    ok(s is not None and [x['nome'] for x in s['categorias']] == ['CANAIS DE TEXTO', 'CANAIS DE VOZ', 'Aventura'],
       'A 1ª categoria leva junto as duas seções padrão (texto e voz) e entra por último, com o nome limpo')
    cat_txt, cat_voz, cat_av = [x['id'] for x in s['categorias']]
    ok(canais_de(s, cat_txt) == ['geral'] and canais_de(s, cat_voz) == ['Geral'], 'Os canais soltos entram na categoria do tipo deles')
    for n in cl: ok(estrutura(cl[n]) is not None, f'{n} recebe a nova lista na hora (regra 6)')
    ok(ev(intruso) == [], 'Quem não é do servidor não recebe nada')

    # segundo servidor antigo: renomear a seção virtual direto
    dono.emit('criar_servidor_discord', {'nome': 'Velho'}); ev(dono)
    sid2 = Server.query.filter_by(name='Velho').first().id
    dono.emit('categoria_renomear', {'server_id': sid2, 'categoria_id': 'padrao_text', 'nome': 'Papo reto'})
    s2 = estrutura(dono)
    ok(s2 is not None and [x['nome'] for x in s2['categorias']] == ['Papo reto', 'CANAIS DE VOZ'], 'Renomear a seção padrão cria as categorias de verdade e renomeia')
    dono.emit('categoria_renomear', {'server_id': sid2, 'categoria_id': 'padrao_text', 'nome': 'de novo'})
    ok(erro(dono), 'Com categorias reais, o id virtual antigo é recusado (cliente desatualizado)')

    # ---------- quem pode ----------
    comum.emit('categoria_criar', {'server_id': sid, 'nome': 'X'}); ok(erro(comum), 'Comum NÃO cria categoria')
    comum.emit('categoria_renomear', {'server_id': sid, 'categoria_id': cat_av, 'nome': 'Y'})
    ok(erro(comum) and ChannelCategory.query.get(cat_av).nome == 'Aventura', 'Comum NÃO renomeia categoria')
    comum.emit('categoria_apagar', {'server_id': sid, 'categoria_id': cat_av})
    ok(erro(comum) and ChannelCategory.query.get(cat_av) is not None, 'Comum NÃO apaga categoria')
    comum.emit('canais_organizar', {'server_id': sid, 'categorias': [cat_av, cat_txt, cat_voz], 'grupos': {str(cat_av): [geral]}})
    ok(erro(comum) and Channel.query.get(geral).category_id == cat_txt, 'Comum NÃO reorganiza canais')
    intruso.emit('canais_organizar', {'server_id': sid, 'grupos': {str(cat_av): [geral]}})
    ok(erro(intruso) and Channel.query.get(geral).category_id == cat_txt, 'Quem não é do servidor NÃO reorganiza')
    comum.emit('criar_canal', {'server_id': sid, 'nome': 'x', 'tipo': 'separador'})
    ok(erro(comum) and Channel.query.filter_by(channel_type='separador').count() == 0, 'Comum NÃO cria separador')

    # o Gerente com "Gerenciar canais" só (sem ser dono) organiza
    dono.emit('cargo_criar', {'server_id': sid, 'nome': 'Arquiteto', 'permissoes': ['gerenciar_canais']}); ev(dono)
    rid = ServerRole.query.filter_by(nome='Arquiteto').first().id
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Gerente'], 'cargo_id': rid, 'ativo': True}); ev(dono); ev(ger)

    # ---------- criar canal numa categoria; sem categoria cai na da mesma família ----------
    ger.emit('criar_canal', {'server_id': sid, 'nome': 'Taverna Nova', 'categoria_id': cat_av}); s = estrutura(ger)
    ok(s is not None and canais_de(s, cat_av) == ['taverna-nova'], 'Canal criado direto na categoria pedida (nome vira slug)')
    ger.emit('criar_canal', {'server_id': sid, 'nome': 'bar'}); s = estrutura(ger)
    ok(canais_de(s, cat_txt) == ['geral', 'bar'], 'Sem categoria escolhida, o canal de texto cai na categoria onde já moram os de texto')
    ger.emit('criar_canal', {'server_id': sid, 'nome': 'sala', 'tipo': 'voice'}); s = estrutura(ger)
    ok(canais_de(s, cat_voz) == ['Geral', 'sala'], 'E o de voz cai na categoria dos de voz')
    ger.emit('criar_canal', {'server_id': sid, 'nome': 'solto', 'categoria_id': 0}); s = estrutura(ger)
    ok(canais_de(s, None) == ['solto'], 'Pedir "sem categoria" de propósito deixa o canal solto no topo')
    ger.emit('criar_canal', {'server_id': sid, 'nome': 'alheio', 'categoria_id': 987654})
    ok(erro(ger) and Channel.query.filter_by(name='alheio').count() == 0, 'Categoria inexistente é recusada')
    outra = ChannelCategory(server_id=sid2, nome='De outro servidor'); db.session.add(outra); db.session.commit()
    ger.emit('criar_canal', {'server_id': sid, 'nome': 'furo', 'categoria_id': outra.id})
    ok(erro(ger) and Channel.query.filter_by(name='furo').count() == 0, 'Categoria de OUTRO servidor é recusada')

    # ---------- organizar (arrastar e soltar) ----------
    ids_c = {c.name: c.id for c in Channel.query.filter_by(server_id=sid).all()}
    estranho = Channel(name='canal-do-velho', channel_type='text', server_id=sid2); db.session.add(estranho); db.session.commit()
    ger.emit('canais_organizar', {'server_id': sid, 'categorias': [cat_av, cat_txt, cat_voz, outra.id, 'lixo'],
                                  'grupos': {str(cat_av): [ids_c['bar'], ids_c['taverna-nova'], estranho.id, 424242, 'x'],
                                             str(cat_txt): [ids_c['geral']], '0': [ids_c['solto']], str(outra.id): [ids_c['geral']]}})
    s = estrutura(ger)
    ok([x['id'] for x in s['categorias']] == [cat_av, cat_txt, cat_voz], 'A ordem das categorias muda (id de outro servidor e lixo ignorados)')
    ok(canais_de(s, cat_av) == ['bar', 'taverna-nova'], 'Canal arrastado pra outra categoria e reordenado')
    ok(canais_de(s, cat_txt) == ['geral'] and Channel.query.get(ids_c['geral']).category_id == cat_txt, 'Citar o mesmo canal em categoria de outro servidor não o move')
    ok(Channel.query.get(estranho.id).category_id is None and Channel.query.get(estranho.id).server_id == sid2, 'Canal de OUTRO servidor não é tocado')
    ok(canais_de(s, cat_voz) == ['Geral', 'sala'], 'Canal não citado fica onde estava')

    # canal privado que a pessoa não enxerga não é movido por id chutado
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'cofre', 'privado': True, 'membros': [], 'categoria_id': cat_txt}); ev(dono)
    cofre = Channel.query.filter_by(name='cofre').first()
    ok(cofre.category_id == cat_txt, 'Canal privado criado na categoria')
    ger.emit('canais_organizar', {'server_id': sid, 'grupos': {str(cat_av): [cofre.id]}}); ev(ger)
    ok(Channel.query.get(cofre.id).category_id == cat_txt, 'Gerente (que não vê o canal privado) NÃO o move chutando o id')
    ger.emit('editar_canal', {'canal_id': cofre.id, 'nome': 'rebatizado'})
    ok(erro(ger) and Channel.query.get(cofre.id).name == 'cofre', 'Nem edita')
    ger.emit('apagar_canal', {'canal_id': cofre.id})
    ok(erro(ger) and Channel.query.get(cofre.id) is not None, 'Nem apaga')

    # categoria que só tem canal privado não aparece (nem o nome) pra quem não vê nada nela
    dono.emit('categoria_criar', {'server_id': sid, 'nome': 'Bastidores'}); s = estrutura(dono)
    cat_bast = [x['id'] for x in s['categorias'] if x['nome'] == 'Bastidores'][0]
    dono.emit('editar_canal', {'canal_id': cofre.id, 'categoria_id': cat_bast}); ev(dono); [ev(x) for x in cl.values()]
    dono.emit('categoria_criar', {'server_id': sid, 'nome': 'Vazia'}); ev(dono)
    for n in cl: ev(cl[n])
    dono.emit('canais_organizar', {'server_id': sid, 'categorias': [cat_av, cat_txt, cat_voz, cat_bast]}); ev(dono)
    s_c, s_d, s_g = estrutura(comum), None, estrutura(ger)
    nomes_comum = [x['nome'] for x in s_c['categorias']]
    ok('Bastidores' not in nomes_comum and 'Vazia' not in nomes_comum, 'Categoria só de canal privado (ou vazia) NÃO aparece pra quem não gerencia canais')
    ok('Bastidores' in [x['nome'] for x in s_g['categorias']] and 'Vazia' in [x['nome'] for x in s_g['categorias']], 'Quem gerencia canais vê todas as categorias')
    ok('cofre' not in [c['name'] for c in s_c['channels']], 'E o canal privado continua escondido dele')

    # ---------- apagar categoria: os canais não somem ----------
    dono.emit('categoria_apagar', {'server_id': sid, 'categoria_id': cat_av}); s = estrutura(dono)
    ok(ChannelCategory.query.get(cat_av) is None and cat_av not in [x['id'] for x in s['categorias']], 'Categoria apagada')
    ok(canais_de(s, None) and 'bar' in canais_de(s, None) and 'taverna-nova' in canais_de(s, None), 'Os canais dela ficam soltos no topo (nada de canal apagado)')
    ok(Channel.query.get(ids_c['bar']) is not None, 'O canal continua existindo')

    # ---------- separadores ----------
    dono.emit('criar_canal', {'server_id': sid, 'nome': '', 'tipo': 'separador', 'categoria_id': cat_txt}); s = estrutura(dono)
    sep_sem = [c for c in s['channels'] if c['type'] == 'separador' and c['name'] == ''][0]
    ok(sep_sem['categoria_id'] == cat_txt, 'Separador sem título (só a linha) dentro da categoria')
    dono.emit('criar_canal', {'server_id': sid, 'nome': '  Eventos   &  Lives ', 'tipo': 'separador', 'icone': '🔥', 'privado': True, 'limite': 5}); s = estrutura(dono)
    sep = [c for c in s['channels'] if c['type'] == 'separador' and c['name']][0]
    ok(sep['name'] == 'Eventos & Lives' and not sep['is_private'] and sep['icone'] is None and sep['limite'] is None, 'Separador com título limpo; privado/ícone/limite não valem nele')
    dono.emit('editar_canal', {'canal_id': sep['id'], 'nome': 'Novo título', 'topico': 'x', 'privado': True}); s = estrutura(dono)
    sep2 = [c for c in s['channels'] if c['id'] == sep['id']][0]
    ok(sep2['name'] == 'Novo título' and not sep2['is_private'] and not sep2['topic'], 'Renomear separador funciona e o resto é ignorado')
    dono.emit('editar_canal', {'canal_id': sep['id'], 'nome': ''}); s = estrutura(dono)
    ok([c for c in s['channels'] if c['id'] == sep['id']][0]['name'] == '', 'Separador pode ficar sem título')
    dono.emit('entrar_canal', {'canal_id': sep['id']})
    ok(erro(dono), 'Ninguém "entra" num separador (nem o dono)')
    dono.emit('enviar_mensagem', {'canal_id': sep['id'], 'texto': 'oi'})
    ok(Message.query.filter_by(channel_id=sep['id']).count() == 0, 'Ninguém escreve num separador')
    ok(fdono.get(f"/api/mensagens/{sep['id']}").status_code == 403, 'API de mensagens recusa o separador')
    dono.emit('entrar_call', {'peer_id': 'pp1', 'canal_id': sep['id']})
    ok(erro(dono), 'Nem entra em call de separador')
    dono.emit('apagar_canal', {'canal_id': sep['id']}); ev(dono)
    dono.emit('apagar_canal', {'canal_id': sep_sem['id']}); ev(dono)
    ok(Channel.query.filter_by(server_id=sid, channel_type='separador').count() == 0, 'Separadores apagados')

    # o último canal de TEXTO continua protegido, e separador não conta como texto
    for nome in ('bar', 'taverna-nova', 'solto'):
        dono.emit('apagar_canal', {'canal_id': Channel.query.filter_by(server_id=sid, name=nome).first().id}); ev(dono)
    dono.emit('apagar_canal', {'canal_id': Channel.query.filter_by(server_id=sid, name='cofre').first().id}); ev(dono)
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'so-uma-linha', 'tipo': 'separador'}); ev(dono)
    dono.emit('apagar_canal', {'canal_id': geral})
    ok(erro(dono) and Channel.query.get(geral) is not None, 'O servidor não fica sem canal de texto (separador não conta)')
    Channel.query.filter_by(server_id=sid, channel_type='separador').delete(); db.session.commit()

    # ---------- tipos de canal ----------
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'hack', 'tipo': 'admin'})
    ok(erro(dono) and Channel.query.filter_by(name='hack').count() == 0, 'Tipo inventado é recusado')
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'hack', 'tipo': 'text; DROP'})
    ok(erro(dono) and Channel.query.filter_by(name='hack').count() == 0, 'Tipo malicioso é recusado')
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'sem-tipo'}); ev(dono)
    ok(Channel.query.filter_by(name='sem-tipo').first().channel_type == 'text', 'Sem tipo = texto, como sempre foi')
    ok(set(cargos.TIPOS_CANAL) == {'text', 'anuncios', 'regras', 'midia', 'voice', 'palco', 'separador'}, 'Conjunto fechado de tipos')

    dono.emit('criar_canal', {'server_id': sid, 'nome': 'avisos', 'tipo': 'anuncios', 'icone': '📣'}); ev(dono)
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'regras', 'tipo': 'regras', 'icone': '<script>'}); ev(dono)
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'fotos', 'tipo': 'midia'}); ev(dono)
    av = Channel.query.filter_by(name='avisos').first(); rg = Channel.query.filter_by(name='regras').first(); fo = Channel.query.filter_by(name='fotos').first()
    ok(av.icon == '📣' and rg.icon is None, 'Ícone do canal: emoji passa, texto/HTML não')
    for n in ('Gerente', 'Comum', 'Terceiro'): ev(cl[n])
    for canal in (av, rg, fo):
        comum.emit('entrar_canal', {'canal_id': canal.id}); dono.emit('entrar_canal', {'canal_id': canal.id})
    ev(comum); ev(dono)

    comum.emit('enviar_mensagem', {'canal_id': av.id, 'texto': 'quero postar'})
    ok(erro(comum) and Message.query.filter_by(channel_id=av.id).count() == 0, 'Comum NÃO escreve em canal de anúncios')
    comum.emit('enviar_mensagem', {'canal_id': rg.id, 'texto': 'quero mudar a regra', 'temp_id': 'tmp_9'})
    rr = ev(comum)
    ok(Message.query.filter_by(channel_id=rg.id).count() == 0 and any(m['name'] == 'mensagem_recusada' and m['args'][0]['temp_id'] == 'tmp_9' for m in rr),
       'Comum NÃO escreve em regras (e a bolha otimista é desfeita via mensagem_recusada)')
    dono.emit('enviar_mensagem', {'canal_id': av.id, 'texto': 'Novidade!'})
    ok(Message.query.filter_by(channel_id=av.id).count() == 1, 'Dono publica no canal de anúncios')
    ok(any(m['name'] == 'receber_mensagem' for m in ev(comum)), 'Comum LÊ o anúncio (chega ao vivo)')
    ok(fcl['Comum'].get(f'/api/mensagens/{av.id}').status_code == 200, 'Comum lê o histórico do canal de anúncios')
    dono.emit('cargo_criar', {'server_id': sid, 'nome': 'Redator', 'permissoes': ['enviar_anuncios']}); ev(dono)
    rid2 = ServerRole.query.filter_by(nome='Redator').first().id
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': rid2, 'ativo': True}); ev(dono); ev(comum)
    comum.emit('enviar_mensagem', {'canal_id': av.id, 'texto': 'agora posso'})
    ok(Message.query.filter_by(channel_id=av.id).count() == 2, 'Com "Publicar em anúncios e regras" o Comum publica')
    dono.emit('cargo_membro', {'server_id': sid, 'person_id': ids['Comum'], 'cargo_id': rid2, 'ativo': False}); ev(dono); ev(comum)
    comum.emit('enviar_mensagem', {'canal_id': av.id, 'texto': 'ainda posso?'})
    ok(Message.query.filter_by(channel_id=av.id).count() == 2, 'Tirado o cargo, volta a não poder')

    comum.emit('enviar_mensagem', {'canal_id': fo.id, 'texto': 'só texto'})
    ok(erro(comum) and Message.query.filter_by(channel_id=fo.id).count() == 0, 'Canal de mídia recusa mensagem só de texto')
    comum.emit('enviar_mensagem', {'canal_id': fo.id, 'texto': 'legenda', 'anexo_url': '/static/img/logo.svg', 'anexo_tipo': 'image'})
    ok(Message.query.filter_by(channel_id=fo.id).count() == 1, 'Canal de mídia aceita foto com legenda')
    comum.emit('enviar_mensagem', {'canal_id': fo.id, 'texto': 'link falso', 'anexo_url': 'https://evil.example/x.png', 'anexo_tipo': 'image'})
    ok(Message.query.filter_by(channel_id=fo.id).count() == 1, 'Anexo de fora da lista permitida não conta como mídia')
    comum.emit('enviar_mensagem', {'canal_id': geral, 'texto': 'texto normal continua livre'})
    ok(Message.query.filter_by(channel_id=geral).count() == 1, 'Canal de texto comum segue como sempre')

    # trocar o tipo: só dentro da família
    dono.emit('editar_canal', {'canal_id': geral, 'tipo': 'anuncios'}); ev(dono)
    ok(Channel.query.get(geral).channel_type == 'anuncios', 'Texto vira anúncios (mesma família)')
    dono.emit('editar_canal', {'canal_id': geral, 'tipo': 'voice'}); ev(dono)
    ok(Channel.query.get(geral).channel_type == 'anuncios', 'Texto NÃO vira voz (as mensagens ficariam órfãs)')
    dono.emit('editar_canal', {'canal_id': geral, 'tipo': 'separador'}); ev(dono)
    ok(Channel.query.get(geral).channel_type == 'anuncios', 'Canal NÃO vira separador')
    dono.emit('editar_canal', {'canal_id': geral, 'tipo': 'text'}); ev(dono)

    # ---------- voz: limite de pessoas, ouvinte e palco ----------
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'duo', 'tipo': 'voice', 'limite': 2, 'icone': '🎧'}); ev(dono)
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'texto-com-limite', 'limite': 3}); ev(dono)
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'gigante', 'tipo': 'voice', 'limite': 500}); ev(dono)
    duo = Channel.query.filter_by(name='duo').first()
    ok(duo.user_limit == 2 and duo.icon == '🎧', 'Canal de voz com limite 2 e ícone')
    ok(Channel.query.filter_by(name='texto-com-limite').first().user_limit is None, 'Limite não vale em canal de texto')
    ok(Channel.query.filter_by(name='gigante').first().user_limit is None, 'Limite acima do teto é ignorado')
    for n in ('Comum', 'Terceiro', 'Gerente'): ev(cl[n])
    dono.emit('entrar_call', {'peer_id': 'p-dono', 'canal_id': duo.id}); ev(dono)
    comum.emit('entrar_call', {'peer_id': 'p-comum', 'canal_id': duo.id}); ev(comum)
    ger.emit('entrar_call', {'peer_id': 'p-ger', 'canal_id': duo.id})
    ok(erro(ger) and ev(ger, 'participantes_call_mudou') == [], 'O 3º não entra no canal com limite 2')
    comum.emit('entrar_call', {'peer_id': 'p-comum', 'canal_id': duo.id})    # reentrada de quem já está: não conta de novo
    ok(not erro(comum), 'Quem já está dentro volta (reentrada) sem ser barrado pela lotação')
    dono.emit('editar_canal', {'canal_id': duo.id, 'limite': 3}); ev(dono)
    ger.emit('entrar_call', {'peer_id': 'p-ger', 'canal_id': duo.id}); ev(ger)
    ok(len(__import__('app.events', fromlist=['x']).participantes_call.get(str(duo.id), [])) == 3, 'Aumentando o limite o 3º entra')
    for n in ('Dono', 'Gerente', 'Comum'):
        (dono if n == 'Dono' else cl[n]).emit('sair_call', {'canal_id': duo.id, 'peer_id': {'Dono': 'p-dono', 'Gerente': 'p-ger', 'Comum': 'p-comum'}[n]})
    ev(dono)
    for n in cl: ev(cl[n])

    # palco
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'palco-principal', 'tipo': 'palco'}); ev(dono)
    palco = Channel.query.filter_by(name='palco-principal').first()
    from app.events import participantes_call, palco_convidados
    dono.emit('entrar_call', {'peer_id': 'pd', 'canal_id': palco.id})
    papel_dono = [m for m in ev(dono, 'palco_papel')][-1]['args'][0]
    ok(papel_dono['ouvinte'] is False and papel_dono['palco'] is True, 'Dono entra no palco como orador')
    comum.emit('entrar_call', {'peer_id': 'pc', 'canal_id': palco.id})
    papel_comum = [m for m in ev(comum, 'palco_papel')][-1]['args'][0]
    ok(papel_comum['ouvinte'] is True, 'Membro comum entra no palco como ouvinte')
    ok({p['usuario_id']: p['ouvinte'] for p in participantes_call[str(palco.id)]} == {ids['Dono']: False, ids['Comum']: True}, 'A lista de participantes marca quem é orador e quem escuta')
    ok(any(m['name'] == 'participantes_call_mudou' for m in ev(dono)), 'Quem está olhando recebe a lista atualizada (regra 6)')
    comum.emit('palco_promover', {'canal_id': palco.id, 'person_id': ids['Comum'], 'ativo': True})
    ok(erro(comum) and palco_convidados.get(str(palco.id)) is None, 'Ouvinte NÃO se promove sozinho')
    dono.emit('palco_promover', {'canal_id': palco.id, 'person_id': ids['Comum'], 'ativo': True})
    ok({p['usuario_id']: p['ouvinte'] for p in participantes_call[str(palco.id)]}[ids['Comum']] is False, 'Orador chama o ouvinte pro palco')
    pc = [m for m in ev(comum, 'palco_papel')][-1]['args'][0]
    ok(pc['ouvinte'] is False, 'O convidado recebe o papel novo na hora')
    dono.emit('palco_promover', {'canal_id': palco.id, 'person_id': ids['Comum'], 'ativo': False}); ev(comum)
    ok({p['usuario_id']: p['ouvinte'] for p in participantes_call[str(palco.id)]}[ids['Comum']] is True, 'E manda de volta pra plateia')
    dono.emit('palco_promover', {'canal_id': geral, 'person_id': ids['Comum'], 'ativo': True})
    ok(erro(dono), 'Só vale em canal de palco')
    dono.emit('palco_promover', {'canal_id': palco.id, 'person_id': ids['Terceiro'], 'ativo': True})
    ok(erro(dono), 'Só chama pro palco quem está lá dentro')
    dono.emit('sair_call', {'canal_id': palco.id, 'peer_id': 'pd'}); comum.emit('sair_call', {'canal_id': palco.id, 'peer_id': 'pc'}); ev(dono); ev(comum)
    ok(str(palco.id) not in palco_convidados, 'Palco vazio esquece os convidados')

    # sem "Falar nos canais de voz": entra como ouvinte em voz comum
    dono.emit('cargo_padrao', {'server_id': sid, 'permissoes': ['criar_convite']}); ev(dono)
    comum.emit('entrar_call', {'peer_id': 'pc2', 'canal_id': voz_geral})
    ok([m for m in ev(comum, 'palco_papel')][-1]['args'][0]['ouvinte'] is True, 'Sem "Falar nos canais de voz" a pessoa entra só como ouvinte')
    comum.emit('sair_call', {'canal_id': voz_geral, 'peer_id': 'pc2'}); ev(comum)
    dono.emit('cargo_padrao', {'server_id': sid, 'permissoes': ['criar_convite', 'falar_voz', 'fixar_mensagens']}); ev(dono)
    comum.emit('entrar_call', {'peer_id': 'pc3', 'canal_id': voz_geral})
    ok([m for m in ev(comum, 'palco_papel')][-1]['args'][0]['ouvinte'] is False, 'Com a permissão, fala normal')
    comum.emit('entrar_call', {'peer_id': 'pc3x', 'canal_id': geral})
    ok(erro(comum), 'Canal de texto não vira call')
    comum.emit('sair_call', {'canal_id': voz_geral, 'peer_id': 'pc3'}); ev(comum)

    # ---------- personalização do servidor ----------
    dono.emit('editar_servidor', {'server_id': sid, 'boas_vindas': 'Bem-vindo, viajante!\r\n\r\n\r\n\r\nRegras no canal ao lado.\x00', 'canal_boas_vindas_id': geral,
                                  'banner_url': '/static/img/logo.svg'}); s = ev(dono, 'servidor_discord_criado')[-1]['args'][0]
    ok(s['boasVindas'] == 'Bem-vindo, viajante!\n\nRegras no canal ao lado.' and s['canalBoasVindas'] == geral and s['bannerUrl'] == '/static/img/logo.svg',
       'Boas-vindas (texto limpo), canal e banner salvam e chegam no JSON')
    dono.emit('criar_canal', {'server_id': sid, 'nome': 'quarto-secreto', 'privado': True, 'membros': []}); ev(dono)
    secreto = Channel.query.filter_by(name='quarto-secreto').first()
    dono.emit('editar_servidor', {'server_id': sid, 'banner_url': "javascript:alert(1)", 'canal_boas_vindas_id': secreto.id}); s = ev(dono, 'servidor_discord_criado')[-1]['args'][0]
    ok(s['bannerUrl'] is None and s['canalBoasVindas'] is None, 'Banner de URL estranha e canal privado são descartados')
    dono.emit('editar_servidor', {'server_id': sid, 'canal_boas_vindas_id': 987654}); s = ev(dono, 'servidor_discord_criado')[-1]['args'][0]
    ok(s['canalBoasVindas'] is None, 'Canal inexistente também')
    estr_outro = Channel.query.filter_by(server_id=sid2).first()
    dono.emit('editar_servidor', {'server_id': sid, 'canal_boas_vindas_id': estr_outro.id}); s = ev(dono, 'servidor_discord_criado')[-1]['args'][0]
    ok(s['canalBoasVindas'] is None, 'E canal de OUTRO servidor')
    dono.emit('editar_servidor', {'server_id': sid, 'banner_url': "/static/x.png') ;background:url(//evil", 'canal_boas_vindas_id': voz_geral}); s = ev(dono, 'servidor_discord_criado')[-1]['args'][0]
    ok(s['bannerUrl'] is None and s['canalBoasVindas'] is None, 'Banner que tenta escapar do CSS e canal de voz como boas-vindas são recusados')
    dono.emit('editar_servidor', {'server_id': sid, 'boas_vindas': 'x' * 900}); s = ev(dono, 'servidor_discord_criado')[-1]['args'][0]
    ok(len(s['boasVindas']) == cargos.LIM_BOAS_VINDAS, 'Boas-vindas têm teto')
    comum.emit('editar_servidor', {'server_id': sid, 'boas_vindas': 'invasor'})
    ok(erro(comum) and Server.query.get(sid).boas_vindas != 'invasor', 'Comum NÃO mexe nas boas-vindas')

    # ---------- validadores ----------
    ok(cargos.emoji_valido('🔥') == '🔥' and cargos.emoji_valido('👨‍👩‍👧') == '👨‍👩‍👧' and cargos.emoji_valido('❤️') == '❤️', 'Emoji simples, composto (ZWJ) e com variação passam')
    ok(cargos.emoji_valido('a') is None and cargos.emoji_valido('<b>') is None and cargos.emoji_valido('"') is None and cargos.emoji_valido('') is None
       and cargos.emoji_valido(5) is None and cargos.emoji_valido('🔥' * 20) is None, 'Letra, HTML, aspa, vazio, número e texto longo não passam')
    ok(cargos.limite_de_voz('7') == 7 and cargos.limite_de_voz(0) is None and cargos.limite_de_voz(100) is None and cargos.limite_de_voz('x') is None, 'Limite de voz 1..99')

print()
print('FALHAS:', falhas if falhas else 'nenhuma')
sys.exit(1 if falhas else 0)
