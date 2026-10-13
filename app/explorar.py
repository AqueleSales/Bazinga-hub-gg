"""Explorar servidores: descobrir servidores PÚBLICOS (o "mar" com barquinhos, as terras com recomendados, busca por tema e "Surpreenda-me").

Regras (regra 4 do CLAUDE.md, tudo no servidor):
  * Só aparece em Explorar o servidor que o DONO marcou como público (`Server.publico`) e que cumpre os requisitos (descrição, tema, canal
    de texto). Quem não é dono não consegue publicar; o admin pode tirar do Explorar (painel /admin > Servidores).
  * A prévia mostra só o que é seguro pra desconhecido: nome, ícone, descrição, tema, nº de membros, dono e os nomes dos canais de texto
    NÃO privados. **Nunca mensagens, nunca membros nominais, nunca canais privados.**
  * Entrar é uma ação explícita (`entrar`); servidor que não é público só entra por convite, como sempre.
O tamanho do barquinho (`porte`) vem do nº de membros; quando existir "nível de servidor"/impulso, ele entra aqui no cálculo.
"""
import hashlib
import random

from sqlalchemy import func

from .models import db, Server, Channel, Person, server_members
from .utils import com_retry, comitar_com_retry, eh_membro

# (id, nome, ícone Font Awesome, cor)
TEMAS_EXPLORAR = [
    ('jogos', 'Jogos', 'fa-gamepad', '#e8483f'), ('musica', 'Música', 'fa-music', '#d946ef'), ('anime', 'Anime e mangá', 'fa-pen-nib', '#e63946'),
    ('estudos', 'Estudos', 'fa-book-open', '#3b82f6'), ('tecnologia', 'Tecnologia', 'fa-microchip', '#22b8d6'), ('arte', 'Arte e design', 'fa-palette', '#f59e0b'),
    ('esportes', 'Esportes', 'fa-volleyball', '#e8742c'), ('filmes', 'Filmes e séries', 'fa-film', '#a855f7'),
    ('amizade', 'Bate-papo e amizade', 'fa-comments', '#23a559'), ('outros', 'Outros', 'fa-ellipsis', '#8ea0ba'),
]
IDS_TEMAS = {t[0] for t in TEMAS_EXPLORAR}
DESC_MIN, DESC_MAX = 10, 1000
MAR_MAX, TERRA_MAX, POR_TEMA_MAX = 12, 8, 8


class ErroExplorar(Exception):
    pass


def porte_do_barco(membros):
    """1 canoa, 2 veleiro, 3 caravela, 4 galeão (por nº de membros)."""
    return 1 if membros < 5 else 2 if membros < 20 else 3 if membros < 100 else 4


def _sorteio(seed, chave):
    return hashlib.md5(f'{seed}:{chave}'.encode()).hexdigest()


def _termo(txt):
    """Texto da busca sem os curingas do LIKE (%, _, barra): quem digita "100%" ou "_" não casa com tudo."""
    return txt.replace('\\', '').replace('%', '').replace('_', '').strip()


def _like(txt):
    return '%' + _termo(txt) + '%'


def _contagem(ids):
    if not ids:
        return {}
    return dict(db.session.query(server_members.c.server_id, func.count(server_members.c.person_id))
                .filter(server_members.c.server_id.in_(ids)).group_by(server_members.c.server_id).all())


def _item(s, membros, meu):
    return {'id': s.id, 'nome': s.name, 'icone': s.icon_url, 'descricao': (s.description or '')[:140], 'tema': s.tema_explorar or 'outros',
            'cor': s.banner_color, 'membros': membros, 'porte': porte_do_barco(membros), 'meu': meu}


def lista(usuario, busca='', tema='', seed=''):
    """O que a tela inteira precisa: `mar` (barquinhos, embaralhados pela seed), `terra` (os mais populares), `por_tema` e os chips de tema."""
    busca = (busca or '').strip()[:40]
    q = Server.query.filter(Server.publico.is_(True))
    if tema in IDS_TEMAS:
        q = q.filter(Server.tema_explorar == tema)
    if busca:
        q = q.filter(Server.name.ilike(_like(busca)) | Server.description.ilike(_like(busca)))
    servidores = com_retry(lambda: q.limit(300).all()) if not busca or _termo(busca) else []
    ids = [s.id for s in servidores]
    cont = com_retry(lambda: _contagem(ids))
    meus = com_retry(lambda: {r[0] for r in db.session.query(server_members.c.server_id).filter(server_members.c.person_id == usuario.id).all()}) if ids else set()
    itens = [_item(s, cont.get(s.id, 0), s.id in meus) for s in servidores]
    mar = sorted(itens, key=lambda i: _sorteio(seed or '0', i['id']))[:MAR_MAX]
    terra = sorted(itens, key=lambda i: (-i['membros'], i['id']))[:TERRA_MAX]
    por_tema = {}
    if not busca and tema not in IDS_TEMAS:
        for t in TEMAS_EXPLORAR:
            do_tema = [i for i in sorted(itens, key=lambda x: (-x['membros'], x['id'])) if i['tema'] == t[0]][:POR_TEMA_MAX]
            if do_tema:
                por_tema[t[0]] = do_tema
    contagem_por_tema = {}
    if not busca:
        for i in itens:
            contagem_por_tema[i['tema']] = contagem_por_tema.get(i['tema'], 0) + 1
    return {'mar': mar, 'terra': terra, 'por_tema': por_tema, 'total': len(itens), 'busca': busca, 'tema': tema if tema in IDS_TEMAS else '',
            'temas': [{'id': t[0], 'nome': t[1], 'icone': t[2], 'cor': t[3], 'qtd': contagem_por_tema.get(t[0], 0)} for t in TEMAS_EXPLORAR], 'seed': seed}


def previa(usuario, server_id):
    """Prévia SEGURA de um servidor público (ou de um em que a pessoa já está): sem mensagens, sem membros nominais, sem canal privado."""
    s = com_retry(lambda: Server.query.get(int(server_id)))
    if not s:
        raise ErroExplorar('Esse servidor não existe mais.')
    meu = eh_membro(usuario, s.id)
    if not s.publico and not meu:
        raise ErroExplorar('Esse servidor não está aberto a visitas.')
    membros = com_retry(lambda: _contagem([s.id])).get(s.id, 0)
    canais = com_retry(lambda: Channel.query.filter_by(server_id=s.id, is_private=False, channel_type='text').order_by(Channel.position, Channel.id).limit(12).all())
    voz = com_retry(lambda: Channel.query.filter_by(server_id=s.id, is_private=False, channel_type='voice').count())
    dono = com_retry(lambda: Person.query.get(s.owner_id))
    j = _item(s, membros, meu)
    j.update({'descricao': s.description or '', 'canais': [c.name for c in canais], 'canais_voz': voz, 'dono': dono.name if dono else '',
              'desde': s.created_at.strftime('%m/%Y') if s.created_at else '', 'publico': bool(s.publico), 'efeito': s.efeito})
    return j


def surpresa(usuario, tema=''):
    """Um servidor público ao acaso que a pessoa ainda NÃO conhece (ou, se já está em todos, qualquer um)."""
    q = Server.query.filter(Server.publico.is_(True))
    if tema in IDS_TEMAS:
        q = q.filter(Server.tema_explorar == tema)
    ids = [s.id for s in com_retry(lambda: q.with_entities(Server.id).limit(500).all())]
    if not ids:
        raise ErroExplorar('Ainda não tem servidor público nesse mar.')
    meus = {r[0] for r in db.session.query(server_members.c.server_id).filter(server_members.c.person_id == usuario.id).all()}
    novos = [i for i in ids if i not in meus] or ids
    return previa(usuario, random.choice(novos))


def definir_publico(srv, publico, tema=None):
    """Dono liga/desliga o Explorar. Pra publicar: descrição de verdade, tema e pelo menos um canal de texto que não seja privado."""
    if publico:
        if len((srv.description or '').strip()) < DESC_MIN:
            raise ErroExplorar(f'Escreva uma descrição de pelo menos {DESC_MIN} caracteres antes de aparecer no Explorar.')
        if tema not in IDS_TEMAS:
            raise ErroExplorar('Escolha um tema pro servidor.')
        if not Channel.query.filter_by(server_id=srv.id, is_private=False, channel_type='text').first():
            raise ErroExplorar('O servidor precisa de pelo menos um canal de texto aberto (não privado).')

    def preparar():
        srv.publico = bool(publico)
        if publico:
            srv.tema_explorar = tema
        elif tema in IDS_TEMAS:
            srv.tema_explorar = tema

    comitar_com_retry(preparar)


def entrar(usuario, server_id):
    """Entra num servidor PÚBLICO sem convite. Devolve (srv, ja_era_membro)."""
    s = com_retry(lambda: Server.query.get(int(server_id)))
    if not s or not s.publico:
        raise ErroExplorar('Esse servidor não está aberto pra entrar direto. Peça um convite.')
    if eh_membro(usuario, s.id):
        return s, True

    def preparar():
        if not eh_membro(usuario, s.id):
            s.members.append(usuario)

    comitar_com_retry(preparar)
    return s, False


def listar_publicos_admin():
    cont_q = com_retry(lambda: Server.query.filter(Server.publico.is_(True)).order_by(Server.id.desc()).limit(200).all())
    cont = com_retry(lambda: _contagem([s.id for s in cont_q]))
    dono = {p.id: p.name for p in com_retry(lambda: Person.query.filter(Person.id.in_({s.owner_id for s in cont_q} or {0})).all())}
    return [{'id': s.id, 'nome': s.name, 'dono': dono.get(s.owner_id, '?'), 'membros': cont.get(s.id, 0), 'tema': s.tema_explorar or 'outros',
             'descricao': (s.description or '')[:160]} for s in cont_q]


def despublicar(server_id):
    s = com_retry(lambda: Server.query.get(int(server_id)))
    if not s:
        raise ErroExplorar('Servidor não encontrado.')

    def preparar():
        s.publico = False

    comitar_com_retry(preparar)
    return s
