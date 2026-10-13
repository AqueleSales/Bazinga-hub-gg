"""Passe de Batalha (temporadas), títulos, temas de temporada, missões (5 diárias, semanais por escolha, anti-spam) e o painel /admin.
Banco SQLite em memória, socketio.test_client."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from datetime import timedelta
from app import create_app, db, socketio
from app import passe, passe_events, utils as u
from app import cosmeticos as cos
from app.bazar import definir_admin
from app.models import (Role, Person, Posse, MovimentoDrc, PasseTemporada, PasseRecompensa, PassePessoa, PasseResgate, Titulo,
                        MissaoProgresso, EfeitoCustom, br_now)

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def levanta(exc, fn):
    try:
        fn()
    except exc:
        db.session.rollback()
        return True
    except Exception as e:
        db.session.rollback()
        print('   (levantou outra coisa:', type(e).__name__, e, ')')
        return False
    return False


def recebidos(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for nome, user in (('Ana', 'ana'), ('Beto', 'beto'), ('Adm', 'adm')):
        p = Person(name=nome, email=f'{user}@x', role_id=r.id, username=user, bazinga_coins=500)
        db.session.add(p); db.session.commit(); ids[user] = p.id
    definir_admin(ids['adm'])

    def pessoa(user):
        db.session.expire_all()
        return db.session.get(Person, ids[user])

    def cliente(user):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[user]
        cl = socketio.test_client(app, flask_test_client=fc)
        cl.get_received()
        return cl, fc

    # ---------- 1. painel /admin: só admin, e só com o cabeçalho anti-forja ----------
    anon = app.test_client()
    ok(anon.get('/admin').status_code == 404, '/admin sem login: 404 (nem confirma que existe)')
    ok(anon.get('/admin/api/geral').status_code == 403, 'API do admin sem login: 403')
    _, fc_ana = cliente('ana')
    ok(fc_ana.get('/admin').status_code == 404 and fc_ana.get('/admin/api/catalogo').status_code == 403, 'Quem não é admin: 404 na página e 403 na API')
    ok(fc_ana.post('/admin/api/passe/modelo', json={}, headers={'X-Requested-With': 'fetch'}).status_code == 403, 'Não-admin não cria temporada')
    _, fc_adm = cliente('adm')
    pg = fc_adm.get('/admin')
    ok(pg.status_code == 200 and b'admin.js' in pg.data and pg.headers.get('Cache-Control') == 'no-store', 'Admin abre /admin (no-store)')
    ok(fc_adm.post('/admin/api/passe/modelo', json={}).status_code == 400, 'POST sem X-Requested-With é recusado (requisição forjada)')
    H = {'X-Requested-With': 'fetch'}
    cat = fc_adm.get('/admin/api/catalogo').get_json()
    ids_cat = {i['id'] for i in cat['itens']}
    ok({'moldura:louros', 'moldura:coroa_zeus', 'placa:marmore', 'faixa:partenon', 'nome:olimpo', 'nome:ambrosia',
        'efeito_perfil:olimpo', 'efeito_perfil:tempestade', 'efeito_avatar:relampago'} <= ids_cat, 'Catálogo do admin traz os itens da Temporada 1')
    ok(not any(i['tipo'] == 'pacote' for i in cat['itens']), 'Pacotes não entram no seletor de recompensa')
    ok({'templo', 'tartaro'} <= {t['id'] for t in cat['temas_app']}, 'Temas de temporada listados')
    ok(len(fc_adm.get('/admin/api/missoes').get_json()['missoes']) >= 30, 'Painel lista as missões')

    # ---------- 2. temporada modelo ----------
    rm = fc_adm.post('/admin/api/passe/modelo', json={}, headers=H).get_json()
    tid = rm['id']
    ok(rm.get('ok') and tid, 'Modelo "Deuses" criado pela API')
    recs = fc_adm.get(f'/admin/api/passe/temporada/{tid}/recompensas').get_json()['recompensas']
    ok(len(recs) == 200, f'200 recompensas (100 níveis x 2 trilhas): {len(recs)}')
    por = {(x['nivel'], x['trilha']): x for x in recs}
    ok(por[(10, 'gratis')]['valor'] == 'moldura:louros' and por[(20, 'gratis')]['valor'] == 'efeito_perfil:olimpo', 'Marcos: moldura no 10, efeito de cartão no 20')
    ok(por[(15, 'gratis')]['tipo'] == 'titulo' and por[(45, 'gratis')]['tipo'] == 'tema', 'Título no 15 e tema no 45')
    ok(por[(1, 'gratis')]['tipo'] == 'moeda' and por[(10, 'premium')]['valor'] == 'moldura:coroa_zeus', 'Moedas nos níveis comuns; premium com moldura no 10')
    ok(all(x['tipo'] != 'item' or x['valor'] in cos.CATALOGO for x in recs), 'Toda recompensa de item do modelo existe no catálogo')
    ok({t['id'] for t in fc_adm.get('/admin/api/titulos').get_json()['titulos']} >= {'aspirante_olimpo', 'senhor_do_olimpo'}, 'O modelo criou os títulos')
    passe.invalidar_cache()
    ok(passe.estado(pessoa('ana')) == {'ativa': False, 'admin': False}, 'Sem temporada ativa: o passe diz isso')

    # ---------- 2b. a Odisseia: cantos, itens e efeitos do Estúdio no modelo ----------
    itens_modelo = {x['valor'] for x in recs if x['tipo'] == 'item'}
    ok({'moldura:egide', 'moldura:tridente', 'placa:vinho_escuro', 'placa:colunata', 'faixa:trirreme', 'nome:bronze'} <= itens_modelo, 'O modelo usa os itens novos da Odisseia (nenhum caiu pra moeda por falta de item)')
    ok({'efeito_perfil:lira_de_apolo', 'efeito_perfil:noite_de_nyx', 'efeito_perfil:brasas_de_hefesto', 'efeito_avatar:tridente_azul'} <= itens_modelo, 'O modelo cria e usa efeitos feitos no Estúdio (receita, sem código)')
    ok(EfeitoCustom.query.count() == 4 and all(x['valor'] in cos.CATALOGO for x in recs if x['tipo'] == 'item'), 'Os 4 efeitos do Estúdio existem no banco e no catálogo')
    ok(len({x['valor'] for x in recs if x['tipo'] == 'titulo'}) == len(passe.TITULOS_MODELO) == 15, 'Os 15 títulos do modelo são todos usados (nenhum sobrando)')
    ok(len(itens_modelo) >= 19 and len([x for x in recs if x['tipo'] != 'moeda']) >= 36, 'A trilha tem prêmio de verdade a cada poucos níveis (19+ itens, 36+ prêmios que não são moeda)')
    ok(all(por[(n, 'gratis')]['tipo'] != 'moeda' for n in range(10, 101, 10)), 'Todo fim de canto (10, 20...100) tem um prêmio grande na trilha Grátis')
    ok(all(por[(n, 'premium')]['tipo'] != 'moeda' for n in (10, 20, 30, 40, 50, 60, 70, 80, 100)), '...e na Premium (menos o 90, que é pra ter um respiro de moedas)')
    passe.invalidar_cache()
    tcap = db.session.get(PasseTemporada, tid)
    ok(len(passe._ler_capitulos(tcap.capitulos)) == 10 and tcap.capitulo_niveis == 10, 'O modelo guarda 10 capítulos de 10 níveis')

    # ---------- 3. ativar, XP do passe, janela e catch-up ----------
    ok(fc_adm.post(f'/admin/api/passe/temporada/{tid}/ativar', json={'ativa': True}, headers=H).get_json().get('ok'), 'Ativar a temporada')
    ana = pessoa('ana'); xp_conta0 = ana.xp
    st = passe.estado(ana)
    ok(st['ativa'] and st['nivel'] == 0 and st['niveis_total'] == 100 and len(st['niveis']) == 100, 'Estado: nível 0 de 100')
    ok(st['pendentes'] == 0 and st['segundos_restantes'] is None and not st['premium'], 'Sem data: sem contagem; sem premium; nada pendente')
    ok(len(st['capitulos']) == 10 and st['capitulos'][0] == {'n': 1, 'nome': 'Ítaca', 'de': 1, 'ate': 10} and st['capitulos'][9]['ate'] == 100 and st['capitulo_atual'] == 1, 'Estado traz os 10 cantos (níveis de cada um) e o canto em que a pessoa está')
    u.registrar_eventos(ana, {}, xp_extra=2000, motivo='tempo')
    pp = PassePessoa.query.filter_by(person_id=ids['ana'], temporada_id=tid).first()
    ok(pp and pp.xp == 2000, f'O XP da conta também vale pro passe ({pp.xp if pp else None})')
    ok(pessoa('ana').xp == xp_conta0 + 2000, 'E segue valendo pro nível da conta')
    st = passe.estado(pessoa('ana'))
    ok(st['nivel'] == 2 and st['xp_no_nivel'] == 400 and st['pendentes'] == 2, f'2000 XP / 800 = nível 2 sobrando 400; 2 grátis pendentes ({st["nivel"]}, {st["pendentes"]})')

    # janela de datas
    with app.app_context():
        t = db.session.get(PasseTemporada, tid)
        t.fim = br_now() - timedelta(days=1); db.session.commit()
    passe.invalidar_cache()
    u.registrar_eventos(pessoa('ana'), {}, xp_extra=500, motivo='tempo')
    ok(PassePessoa.query.filter_by(person_id=ids['ana']).first().xp == 2000, 'Temporada encerrada por data: o XP do passe não anda')
    with app.app_context():
        t = db.session.get(PasseTemporada, tid)
        t.fim = br_now() + timedelta(days=3); t.catchup_dias = 14; t.catchup_pct = 50; db.session.commit()
    passe.invalidar_cache()
    u.registrar_eventos(pessoa('ana'), {}, xp_extra=100, motivo='tempo')
    ok(PassePessoa.query.filter_by(person_id=ids['ana']).first().xp == 2150, 'Catch-up: nos últimos dias o XP rende +50% (100 -> 150)')
    ok(passe.estado(pessoa('ana'))['catchup'] is True, 'O estado avisa que o catch-up está ligado')
    with app.app_context():
        t = db.session.get(PasseTemporada, tid)
        t.fim = None; db.session.commit()
    passe.invalidar_cache()
    pp = PassePessoa.query.filter_by(person_id=ids['ana']).first(); pp.xp = 2000; db.session.commit()

    # ---------- 4. resgate ----------
    ana = pessoa('ana'); saldo0 = ana.bazinga_coins
    r1 = passe.resgatar(ana, 1, 'gratis')
    ok(r1['moedas'] == 50 and pessoa('ana').bazinga_coins == saldo0 + 50, 'Resgatar nível 1 grátis: +50 moedas')
    mv = MovimentoDrc.query.filter_by(person_id=ids['ana'], motivo='passe').all()
    ok(len(mv) == 1 and mv[0].delta == 50 and mv[0].saldo_apos == pessoa('ana').bazinga_coins, 'Livro-razão: movimento "passe" de +50 com saldo_apos certo')
    ok(levanta(passe.ErroPasse, lambda: passe.resgatar(pessoa('ana'), 1, 'gratis')), 'Resgatar de novo o mesmo: recusado')
    ok(pessoa('ana').bazinga_coins == saldo0 + 50, 'Resgate repetido não pagou duas vezes')
    ok(levanta(passe.ErroPasse, lambda: passe.resgatar(pessoa('ana'), 1, 'premium')), 'Premium sem ter o premium: recusado')
    ok(levanta(passe.ErroPasse, lambda: passe.resgatar(pessoa('ana'), 3, 'gratis')), 'Nível que ainda não chegou: recusado')
    ok(levanta(passe.ErroPasse, lambda: passe.resgatar(pessoa('ana'), 1, 'inventada')), 'Trilha inventada: recusada')
    # corrida: outra aba já gravou o resgate -> a transação inteira desfaz (inclusive as moedas)
    db.session.add(PasseResgate(person_id=ids['ana'], temporada_id=tid, nivel=2, trilha='gratis')); db.session.commit()
    s_antes = pessoa('ana').bazinga_coins
    ok(levanta(passe.ErroPasse, lambda: passe.resgatar(pessoa('ana'), 2, 'gratis')) and pessoa('ana').bazinga_coins == s_antes, 'Resgate duplicado (corrida): recusado e sem pagar')
    PasseResgate.query.filter_by(person_id=ids['ana'], nivel=2).delete(); db.session.commit()
    rt = passe.resgatar(pessoa('ana'))
    ok(rt['qtd'] == 1 and rt['moedas'] == 50, 'Resgatar tudo pega só o que falta (nível 2) e não o já resgatado')
    ok(levanta(passe.ErroPasse, lambda: passe.resgatar(pessoa('ana'))), 'Resgatar tudo sem nada novo: aviso')

    # premium e prêmios de verdade (item, título, tema)
    passe.definir_premium(ids['ana'], True)
    pp = PassePessoa.query.filter_by(person_id=ids['ana']).first(); pp.xp = 100 * 800; db.session.commit()
    rt = passe.resgatar(pessoa('ana'))
    posses = cos.posses_da_pessoa(ids['ana'])
    ok({'moldura:louros', 'placa:marmore', 'moldura:coroa_zeus', 'efeito_perfil:olimpo'} <= posses, 'Itens do passe entram no inventário (posse)')
    ok({'titulo:aspirante_olimpo', 'titulo:senhor_do_olimpo', 'titulo:filho_do_trovao'} <= posses, 'Títulos viram posse "titulo:<id>"')
    ok({'tema:templo', 'tema:tartaro'} <= posses, 'Temas de temporada viram posse "tema:<id>"')
    ok(Posse.query.filter_by(person_id=ids['ana'], item_id='moldura:louros').first().origem == 'passe', 'Origem da posse: passe')
    ok(PasseResgate.query.filter_by(person_id=ids['ana']).count() == 200, 'Os 200 slots resgatados (grátis + premium)')
    ok(passe.estado(pessoa('ana'))['capitulo_atual'] == 10, 'No nível 100 o canto atual é o último (A Volta ao Olimpo)')
    ok(passe.estado(pessoa('ana'))['pendentes'] == 0 and passe.estado(pessoa('ana'))['nivel'] == 100, 'Passe completo: nada pendente, nível 100 (teto)')
    u.registrar_eventos(pessoa('ana'), {}, xp_extra=50000, motivo='tempo')
    ok(PassePessoa.query.filter_by(person_id=ids['ana']).first().xp == 80000, 'O XP do passe para no teto (niveis x xp_por_nivel)')
    # beto não tem nada e não resgata o que é do outro
    ok(passe.estado(pessoa('beto'))['nivel'] == 0 and levanta(passe.ErroPasse, lambda: passe.resgatar(pessoa('beto'), 10, 'gratis')), 'Quem não tem nível não resgata')

    # ---------- 5. títulos e tema exclusivo ----------
    ana = pessoa('ana')
    ok(levanta(passe.ErroPasse, lambda: passe.equipar_titulo(pessoa('beto'), 'aspirante_olimpo')), 'Sem ter ganhado, não equipa o título')
    passe.equipar_titulo(ana, 'favorito_dos_deuses')
    ok(pessoa('ana').titulo_id == 'favorito_dos_deuses' and passe.titulo_publico('favorito_dos_deuses')['anim'] == 'brilho', 'Título equipado (com animação) no perfil')
    ok(levanta(passe.ErroPasse, lambda: passe.equipar_titulo(pessoa('ana'), 'nao_existe')), 'Título que não existe: recusado')
    passe.equipar_titulo(pessoa('ana'), None)
    ok(pessoa('ana').titulo_id is None, 'Tirar o título')
    ok([t['id'] for t in passe.titulos_da_pessoa(cos.posses_da_pessoa(ids['ana']))][0] in {'aspirante_olimpo', 'mortal_ilustre', 'heroi_de_atenas'}, 'Lista de títulos ordenada da raridade menor pra maior')

    cl_ana, _ = cliente('ana'); cl_beto, _ = cliente('beto')
    cl_beto.emit('mudar_tema', {'tema': 'templo', 'aparelho': 'computador'})
    ev = recebidos(cl_beto)
    ok(any(m['name'] == 'erro_bazinga' and 'exclusivo' in m['args'][0]['msg'] for m in ev) and pessoa('beto').tema == 'dark', 'Tema de temporada sem posse: recusado no servidor')
    cl_ana.emit('mudar_tema', {'tema': 'templo', 'aparelho': 'computador'})
    ev = recebidos(cl_ana, 'preferencias_carregadas')
    ok(ev and pessoa('ana').tema == 'templo', 'Quem ganhou o tema consegue usar')
    ok(u.tema_eh_claro('templo') is False and 'templo' in u.TEMAS_ESCUROS, 'Temas de temporada são escuros')

    # ---------- 6. eventos do socket ----------
    from app.models import Server, Channel
    srv = Server(name='S', owner_id=ids['ana']); db.session.add(srv); db.session.commit()
    srv.members.append(pessoa('ana')); db.session.commit(); srv0_id = srv.id
    cl_ana.emit('passe_pedir', {})
    ev = recebidos(cl_ana, 'passe')
    ok(ev and ev[0]['args'][0]['ativa'] and ev[0]['args'][0]['nivel'] == 100, 'passe_pedir devolve o estado')
    sem_login = socketio.test_client(app); sem_login.get_received()
    sem_login.emit('passe_pedir', {}); sem_login.emit('passe_resgatar', {'todos': True}); sem_login.emit('listar_titulos', {}); sem_login.emit('equipar_titulo', {'titulo_id': 'x'})
    ok(not sem_login.get_received(), 'Sem login: nenhum evento do passe responde')
    cl_beto.get_received(); passe_events._ultimo.clear()
    cl_beto.emit('passe_resgatar', {'nivel': 1, 'trilha': 'gratis'})
    ev = recebidos(cl_beto)
    ok(any(m['name'] == 'passe_erro' for m in ev) and any(m['name'] == 'passe' for m in ev), 'Resgate recusado: toast de regra e a tela se corrige (passe de novo)')
    pb = PassePessoa.query.filter_by(person_id=ids['beto'], temporada_id=tid).first()
    ok(pb is not None and pb.xp > 0, 'O bônus diário ao conectar já soma no passe (a linha nasce sozinha)')
    pb.xp = 1700; db.session.commit()
    passe_events._ultimo.clear()
    cl_beto.emit('passe_resgatar', {'nivel': 1, 'trilha': 'gratis'})
    ev = recebidos(cl_beto)
    nomes = [m['name'] for m in ev]
    ok('passe_resgatado' in nomes and 'passe' in nomes and 'saldo_atualizado' in nomes and 'inventario' in nomes and 'titulos' in nomes, f'Resgate ok avisa passe_resgatado, passe, saldo, inventario e titulos ({nomes})')
    cl_beto2, _ = cliente('beto')       # outra aba do beto
    passe_events._ultimo.clear()
    cl_beto.emit('passe_resgatar', {'nivel': 2, 'trilha': 'gratis'})
    ok(any(m['name'] == 'passe_resgatado' for m in recebidos(cl_beto2)), 'Regra 6: a outra aba do mesmo usuário também recebe o resgate')
    passe_events._ultimo.clear()
    cl_beto.emit('equipar_titulo', {'titulo_id': 'aspirante_olimpo'})
    ev = recebidos(cl_beto)
    ok(any(m['name'] == 'passe_erro' for m in ev), 'Equipar título que não tem: toast de erro')
    PasseResgate.query.filter_by(person_id=ids['beto']).delete(); Posse.query.filter_by(person_id=ids['beto'], item_id='titulo:aspirante_olimpo').delete(); db.session.commit()
    pp = PassePessoa.query.filter_by(person_id=ids['beto']).first(); pp.xp = 4000; db.session.commit()
    passe_events._ultimo.clear()
    cl_beto.emit('passe_resgatar', {'todos': True}); cl_beto.get_received(); passe_events._ultimo.clear()
    cl_beto.emit('equipar_titulo', {'titulo_id': 'aspirante_olimpo'})
    ev = recebidos(cl_beto)
    pa = [m for m in ev if m['name'] == 'perfil_atualizado']
    ok(pa and pa[0]['args'][0]['titulo_perfil']['texto'] == 'Aspirante ao Olimpo', 'Equipar título: perfil_atualizado leva o título')
    srv0 = db.session.get(Server, srv0_id); srv0.members.append(pessoa('beto')); db.session.commit()
    cl_ana.get_received()
    cl_ana.emit('obter_perfil', {'usuario_id': ids['beto']})
    pp_ = [m for m in recebidos(cl_ana, 'perfil_publico')]
    ok(pp_ and pp_[0]['args'][0]['titulo_perfil']['texto'] == 'Aspirante ao Olimpo' and pp_[0]['args'][0]['titulo'], 'Cartão de quem convive mostra o título, e "titulo" continua sendo a patente')

    # ---------- 7. validação do admin ----------
    def salvar(lista, **kw):
        return passe.salvar_recompensas(tid, lista, **kw)
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': 'item', 'valor': 'moldura:nao_existe'}])), 'Recompensa com item inexistente: recusada')
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': 'item', 'valor': 'pacote:gojo'}])), 'Pacote não pode ser recompensa')
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': 'titulo', 'valor': 'xx_nao'}])), 'Título inexistente: recusado')
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': 'tema', 'valor': 'light'}])), 'Só tema de temporada vira recompensa (nada de tema comum)')
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 0}])), 'Moeda zero: recusada')
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 10**9}])), 'Moeda absurda: recusada')
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 101, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 5}])), 'Nível fora da temporada: recusado')
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 5, 'trilha': 'vip', 'tipo': 'moeda', 'quantidade': 5}])), 'Trilha inventada no admin: recusada')
    ok(levanta(passe.ErroPasse, lambda: salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 5}, {'nivel': 5, 'trilha': 'gratis', 'tipo': 'item', 'valor': 'x:y'}])), 'Lista com 1 inválida: nada é gravado')
    ok(PasseRecompensa.query.filter_by(temporada_id=tid, nivel=5, trilha='gratis').first().quantidade != 5, 'Nada foi gravado quando a lista tinha item inválido')
    salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 777}])
    ok(PasseRecompensa.query.filter_by(temporada_id=tid, nivel=5, trilha='gratis').first().quantidade == 777, 'Editar um slot')
    salvar([{'nivel': 5, 'trilha': 'gratis', 'tipo': ''}])
    ok(PasseRecompensa.query.filter_by(temporada_id=tid, nivel=5, trilha='gratis').first() is None, 'Tipo vazio apaga o slot')
    ok(levanta(passe.ErroPasse, lambda: passe.salvar_titulo({'id': 'Maiusculo', 'texto': 'x'})), 'Id de título com maiúscula: recusado')
    ok(levanta(passe.ErroPasse, lambda: passe.salvar_titulo({'id': 'ok_id', 'texto': 'Bom', 'animacao': 'inventada'})), 'Animação de título desconhecida: recusada')
    ok(levanta(passe.ErroPasse, lambda: passe.salvar_temporada({'nome': 'X', 'niveis': 100})), 'Nome de temporada curto: recusado')
    ok(levanta(passe.ErroPasse, lambda: passe.salvar_temporada({'nome': 'Teste', 'niveis': 9999})), 'Níveis demais: recusado')
    ok(levanta(passe.ErroPasse, lambda: passe.salvar_temporada({'nome': 'Teste', 'niveis': 10, 'inicio': '2026-10-10T10:00', 'fim': '2026-10-01T10:00'})), 'Fim antes do início: recusado')
    ok(levanta(passe.ErroPasse, lambda: passe.apagar_temporada(tid)), 'Temporada ativa não se apaga')
    t2 = passe.salvar_temporada({'nome': 'Temporada 2', 'tema': 'neutro', 'niveis': 10, 'xp_por_nivel': 500})
    passe.salvar_recompensas(t2, [{'nivel': 10, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 9}])
    passe.ativar_temporada(t2)
    ok(PasseTemporada.query.filter_by(ativa=True).count() == 1 and passe.temporada_ativa()['id'] == t2, 'Só uma temporada ativa por vez (ativar a nova desativa a velha)')
    passe.salvar_temporada({'nome': 'Temporada 2', 'tema': 'neutro', 'niveis': 5, 'xp_por_nivel': 500}, t2)
    ok(PasseRecompensa.query.filter_by(temporada_id=t2).count() == 0, 'Encolher a temporada apaga as recompensas dos níveis que sumiram')
    ok(levanta(passe.ErroPasse, lambda: passe.apagar_temporada(tid)) is False or True, 'apagar com progresso (checado abaixo)')
    passe.ativar_temporada(t2, False)
    ok(levanta(passe.ErroPasse, lambda: passe.apagar_temporada(tid)), 'Temporada com gente jogando não se apaga (só se encerra)')
    passe.apagar_temporada(t2)
    ok(db.session.get(PasseTemporada, t2) is None, 'Temporada sem progresso se apaga')
    passe.apagar_titulo('navegante_do_egeu')
    ok(not Posse.query.filter_by(item_id='titulo:navegante_do_egeu').count() and passe.titulo_publico('navegante_do_egeu') is None, 'Apagar título tira a posse de todo mundo')
    passe.ativar_temporada(tid)

    # capítulos: validação
    ok(levanta(passe.ErroPasse, lambda: passe.salvar_temporada({'nome': 'Teste', 'niveis': 10, 'capitulo_niveis': 1})), 'Capítulo com menos de 3 níveis: recusado')
    caps_txt = chr(10).join(['Um', '', '  Dois  ', 'x' * 100, 'Quatro'])
    tcap2 = passe.salvar_temporada({'nome': 'Com cantos', 'tema': 'neutro', 'niveis': 25, 'xp_por_nivel': 500, 'capitulos': caps_txt, 'capitulo_niveis': 10})
    t2 = db.session.get(PasseTemporada, tcap2)
    nomes2 = passe._ler_capitulos(t2.capitulos)
    ok(nomes2[:2] == ['Um', 'Dois'] and len(nomes2[2]) == 40 and len(nomes2) == 4, 'Capítulos: linhas vazias somem, espaços saem, nome limitado a 40')
    snap2 = {'niveis': 25, 'capitulos': nomes2, 'capitulo_niveis': 10}
    cc = passe.capitulos_da_temporada(snap2)
    ok([(c['de'], c['ate']) for c in cc] == [(1, 10), (11, 20), (21, 25)], 'O último capítulo é cortado no fim da temporada e capítulo além do fim some')
    passe.apagar_temporada(tcap2)
    ok(passe._ler_capitulos('lixo{') == [] and passe._ler_capitulos('{"a":1}') == [], 'JSON de capítulos quebrado vira lista vazia')

    # ---------- 8. missões: 5 diárias, semanais por escolha ----------
    ok(u.QTD_DIARIAS == 5 and u.ESCOLHAS_SEMANAIS == 3 and len(u.POOL_DIARIAS) >= 10 and len(u.POOL_SEMANAIS) >= 14, 'Pool maior: 5 diárias, escolher 3 semanais')
    beto = pessoa('beto')
    mj = u.missoes_do_usuario(beto)
    ok(len(mj['diarias']) == 5 and len({m['codigo'] for m in mj['diarias']}) == 5, '5 diárias diferentes')
    ok(mj['semanais'] == [] and len(mj['oferta_semanais']) == u.OFERTA_SEMANAIS and mj['escolhas_semanais'] == 3, 'Semanais: nenhuma escolhida ainda e uma oferta de 8')
    oferta = [m['codigo'] for m in mj['oferta_semanais']]
    ok(oferta == [m['codigo'] for m in u.missoes_do_usuario(beto)['oferta_semanais']], 'A oferta da semana é estável (não muda a cada abertura)')
    for cod in oferta[:3]:
        u.escolher_semanal(beto, cod)
    ok(len(u.missoes_do_usuario(beto)['semanais']) == 3 and len(u.missoes_do_usuario(beto)['oferta_semanais']) == 5, 'Escolheu 3: 3 semanais ativas, 5 sobram na oferta')
    ok(levanta(u.ErroMissao, lambda: u.escolher_semanal(beto, oferta[3])), 'Não escolhe a 4ª')
    ok(levanta(u.ErroMissao, lambda: u.escolher_semanal(beto, 'd_msg10')), 'Missão que não é da oferta: recusada')
    ok(levanta(u.ErroMissao, lambda: u.escolher_semanal(beto, 'codigo_falso')), 'Código inventado: recusado')
    u.escolher_semanal(beto, oferta[0], escolher=False)
    ok(len(u.missoes_do_usuario(beto)['semanais']) == 2, 'Desfazer uma que não começou')
    u.escolher_semanal(beto, oferta[3])
    # só conta o progresso das escolhidas
    escolhida = oferta[1]; evento = u.MISSOES[escolhida]['evento']
    u.registrar_eventos(beto, {evento: 1})
    linha = MissaoProgresso.query.filter_by(person_id=ids['beto'], codigo=escolhida).first()
    ok(linha.progresso == 1, 'Progresso vai pra missão escolhida')
    ok(MissaoProgresso.query.filter_by(person_id=ids['beto'], codigo=oferta[0]).first() is None, 'A não escolhida não tem linha nem progresso')
    ok(levanta(u.ErroMissao, lambda: u.escolher_semanal(beto, escolhida, escolher=False)), 'Missão com progresso não se desfaz')

    # anti-spam
    u._contagem_recente.clear(); u._reacoes_contadas.clear()
    ok(u.contagem_valida(99, 'mensagem', 'Bom dia pessoal') is True, 'Mensagem normal conta')
    ok(u.contagem_valida(99, 'mensagem', 'Outra mensagem bem diferente') is False, 'Duas seguidas dentro do intervalo: a 2ª não conta')
    u._contagem_recente[(99, 'mensagem')]['t'] -= 10
    ok(u.contagem_valida(99, 'mensagem', '  BOM   dia pessoal ') is False, 'Mesmo texto (mudando só caixa/espaços): não conta')
    ok(u.contagem_valida(99, 'mensagem', 'aaaaaaa') is False and u.contagem_valida(99, 'mensagem', 'oi') is False, '"aaaa" e "oi" não contam')
    u._contagem_recente[(99, 'mensagem')]['t'] -= 10
    ok(u.contagem_valida(99, 'mensagem', 'Agora sim outra frase') is True, 'Frase nova depois do intervalo conta')
    ok(u.contagem_valida(99, 'dm', 'Bom dia pessoal') is True, 'DM tem contagem separada da do canal')
    ok(u.contagem_valida(7, 'reacao', chave=55) is True, 'Reação a uma mensagem nova conta')
    ok(u.contagem_valida(7, 'reacao', chave=56) is False, 'Reação em rajada (menos de 1,5 s): não conta')
    u._contagem_recente[(7, 'reacao')]['t'] -= 10
    ok(u.contagem_valida(7, 'reacao', chave=55) is False, 'Ligar/desligar/ligar a reação na MESMA mensagem não conta de novo')
    ok(u.contagem_valida(7, 'reacao', chave=56) is True, 'Reação a outra mensagem, com intervalo: conta')
    ok(u.contagem_valida(8, 'explorar') is True and u.contagem_valida(8, 'explorar') is False, 'Explorar o mapa: 1 a cada 20 s')

    # spam de verdade pelo socket: 3 mensagens iguais seguidas contam como 1
    canal = Channel(name='geral', server_id=srv.id, channel_type='text'); db.session.add(canal); db.session.commit()
    u._contagem_recente.clear()
    cl_ana2, _ = cliente('ana')
    antes = {l.codigo: l.progresso for l in MissaoProgresso.query.filter_by(person_id=ids['ana']).all()}
    for _ in range(4):
        cl_ana2.emit('enviar_mensagem', {'canal_id': canal.id, 'texto': 'spam spam spam'})
    cl_ana2.get_received()
    db.session.expire_all()
    diarias_msg = [l for l in MissaoProgresso.query.filter_by(person_id=ids['ana'], periodo='diaria').all() if l.codigo in u.MISSOES and u.MISSOES[l.codigo]['evento'] == 'mensagem']
    ok(all(l.progresso <= 1 for l in diarias_msg), f'4 mensagens iguais seguidas contaram no máximo 1 ({[l.progresso for l in diarias_msg]})')

    # ---------- 9. front-end (arquivos) ----------
    js = open(os.path.join(RAIZ, 'static', 'js', 'passe.js'), encoding='utf-8').read()
    css_t = open(os.path.join(RAIZ, 'static', 'css', 'titulos.css'), encoding='utf-8').read()
    css_p = open(os.path.join(RAIZ, 'static', 'css', 'passe.css'), encoding='utf-8').read()
    html = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
    adm_js = open(os.path.join(RAIZ, 'static', 'js', 'admin.js'), encoding='utf-8').read()
    ok(all(f'.titulo-anim-{a}' in css_t for a in passe.ANIMACOES_TITULO), 'Toda animação de título tem CSS')
    ok(all(f'.titulo-rar-{r}' in css_t for r in passe.RARIDADES_TITULO), 'Toda raridade de título tem CSS')
    ok(all(f'[data-tema="{t}"]' in html or f":root[data-tema=\"{t}\"]" in html for t in u.TEMAS_EXCLUSIVOS), 'Os temas de temporada têm paleta no CSS')
    ok(all(f"id: '{t}'" in html for t in u.TEMAS_EXCLUSIVOS), 'Os temas de temporada estão no catálogo de temas do cliente')
    ok('id="passe"' in html and 'js/passe.js' in html and 'css/passe.css' in html and 'css/titulos.css' in html, 'chat.html monta e carrega o passe e os títulos')
    ok("socket.on('passe'" in html and "socket.on('titulos'" in html and "socket.on('passe_resgatado'" in html, 'Cliente escuta os eventos do passe')
    ok('titulo_perfil' in html and "'escolher_missao_semanal'" in html, 'Cartão mostra o título; cliente escolhe missão semanal')
    ok("emitir('passe_resgatar'" in js and 'passe_pedir' in js and 'equipar_titulo' in js, 'passe.js só PEDE o resgate/título (nada de calcular nível)')
    ok('linear-gradient' not in css_p and 'linear-gradient' not in css_t, 'Passe e títulos sem gradiente decorativo (cor chapada)')
    ok('X-Requested-With' in adm_js and 'innerHTML' in adm_js and adm_js.count('esc(') > 40, 'admin.js manda o cabeçalho anti-forja e escapa o que desenha')
    ok(re.search(r'(?<!\w)eval\(|document\.write', adm_js + js) is None, 'Sem eval/document.write no admin e no passe')

    # ---------- 10. apagar / aplicar modelo (bug de produção: lento + clique duplo = chave duplicada / "ainda referenciada") ----------
    # O SQLite NÃO impõe chave estrangeira por padrão e o Postgres impõe: ligamos aqui pra o teste valer de verdade.
    from sqlalchemy import event as _ev
    from sqlalchemy.engine import Engine as _Eng
    consultas = {'n': 0}
    def _conta(conn, cur, st, params, ctx, many): consultas['n'] += 1
    _ev.listen(_Eng, 'before_cursor_execute', _conta)
    db.session.execute(db.text('PRAGMA foreign_keys=ON')); db.session.commit()
    t_novo = passe.salvar_temporada({'nome': 'Modelo teste', 'tema': 'deuses', 'niveis': 100, 'xp_por_nivel': 800})
    passe.modelo_deuses(t_novo)                       # 1ª vez cria títulos e efeitos
    consultas['n'] = 0
    passe.modelo_deuses(t_novo)
    ok(consultas['n'] < 40, f'Aplicar o modelo usa poucas consultas (cada uma é uma ida ao Neon): {consultas["n"]}')
    ok(PasseRecompensa.query.filter_by(temporada_id=t_novo).count() == 200, 'O modelo grava as 200 recompensas')
    consultas['n'] = 0
    passe.apagar_temporada(t_novo)
    ok(consultas['n'] < 15, f'Apagar a temporada usa poucas consultas: {consultas["n"]}')
    ok(PasseTemporada.query.get(t_novo) is None and PasseRecompensa.query.filter_by(temporada_id=t_novo).count() == 0, 'Apagar remove as recompensas e depois a temporada (com chave estrangeira ligada)')
    t_rep = passe.salvar_temporada({'nome': 'Repetido', 'tema': 'deuses', 'niveis': 10, 'xp_por_nivel': 100})
    passe.salvar_recompensas(t_rep, [{'nivel': 1, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 5}, {'nivel': 1, 'trilha': 'gratis', 'tipo': 'moeda', 'quantidade': 9}])
    ok([(r.nivel, r.quantidade) for r in PasseRecompensa.query.filter_by(temporada_id=t_rep)] == [(1, 9)], 'Lista com o mesmo nível/trilha repetido não estoura a chave única (o último vale)')
    passe.salvar_recompensas(t_rep, [{'nivel': 1, 'trilha': 'gratis', 'tipo': None}])
    ok(PasseRecompensa.query.filter_by(temporada_id=t_rep).count() == 0, 'Slot vazio apaga a recompensa')
    _ev.remove(_Eng, 'before_cursor_execute', _conta)
    ok('trabalhando(' in adm_js and "b.textContent = 'Aguarde...'" in adm_js, 'admin.js trava o botão enquanto a operação roda (sem clique duplo)')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
