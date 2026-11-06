"""ACERVO (Rodada 39): FIGURINHAS e SONS (soundboard e som de entrada na call). Regra, sem socket; os eventos moram em acervo_events.py e o
envio/leitura do arquivo em acervo_routes.py.

O que o ACERVO guarda é reutilizado por muita gente e fica (uma figurinha é vista por todo mundo do chat; um som toca no ouvido de todos na call),
então a moderação é mais dura que a do resto do app:
  * todo arquivo passa pelo Guardião ANTES de os outros poderem ver/ouvir (`guardiao.avaliar_para_acervo`): a IA liberou = 'aprovado'; sem IA, IA fora
    do ar ou suspeita = 'em_analise' (só quem enviou vê e ouve) até uma pessoa responsável decidir no Estúdio > Guardião. O contrário do resto do app,
    onde a IA fora do ar libera: aqui o caso errado é permanente e público.
  * o arquivo é validado pelo CONTEÚDO (assinatura), nunca pela extensão ou pelo que o navegador disse; figurinha é decodificada e REGRAVADA pelo Pillow
    (WebP, até 320 px: tira metadado, polyglot e bomba de descompressão); som tem teto de tamanho e a duração é cortada no cliente (6 s).
  * cotas por pessoa e por servidor; quem gerencia o servidor cria o acervo DO servidor; apagar é de quem enviou ou de quem gerencia o servidor.
  * figurinha/som de servidor só vale pra quem é membro dele; o acervo pessoal só vale pra própria pessoa (mas a figurinha MANDADA aparece pra todo
    mundo na conversa: o arquivo é entregue a qualquer pessoa logada, e só se estiver aprovado).
"""
import hashlib
import io
import re
import struct

from . import cargos, guardiao
from .models import db, AcervoItem, GuardiaoCaso, Person, Server
from .utils import comitar_com_retry, com_retry, eh_membro

TIPOS = ('figurinha', 'som')
ESCOPOS = ('pessoa', 'servidor')
COTAS = {'pessoa': {'figurinha': 30, 'som': 12}, 'servidor': {'figurinha': 50, 'som': 24}}
MAX_FIG_ENVIO = 3 * 1024 * 1024        # o que a pessoa pode mandar (a figurinha final é bem menor)
MAX_FIG_FINAL = 512 * 1024
LADO_FIG = 320
MAX_QUADROS_FIG = 60
MAX_SOM_BYTES = 300 * 1024
MAX_SOM_MS = 6000
PRESETS_SOM = ('sino', 'moeda', 'gota', 'arpejo', 'laser', 'tambor', 'aplauso', 'boasvindas', 'pop', 'teclado')   # sintetizados no cliente (static/js/sons.js)


class ErroAcervo(Exception):
    """Recusa de regra: a mensagem vai pra pessoa."""


# ---------------------------------------------------------------------------
# validação
# ---------------------------------------------------------------------------
def limpar_nome(v, padrao='Sem nome'):
    s = re.sub(r'[\x00-\x1f\x7f​-‏‪-‮⁦-⁩]', '', str(v or ''))
    s = re.sub(r'\s+', ' ', s).strip()[:24]
    return s or padrao


def detectar_som(dados):
    """Mime do áudio pela ASSINATURA do arquivo (mp3, ogg, wav, m4a/mp4, webm). None = não é um áudio que aceitamos."""
    c = dados[:16]
    if len(dados) < 64:
        return None
    if c[:3] == b'ID3' or (c[0] == 0xFF and (c[1] & 0xE0) == 0xE0):
        return 'audio/mpeg'
    if c[:4] == b'OggS':
        return 'audio/ogg'
    if c[:4] == b'RIFF' and c[8:12] == b'WAVE':
        return 'audio/wav'
    if c[4:8] == b'ftyp':
        return 'audio/mp4'
    if c[:4] == b'\x1a\x45\xdf\xa3':
        return 'audio/webm'
    return None


def duracao_wav_ms(dados):
    """Duração REAL de um WAV (cabeçalho). None se não der pra ler. Os outros formatos contam com o corte no cliente + teto de tamanho."""
    try:
        if dados[:4] != b'RIFF' or dados[8:12] != b'WAVE':
            return None
        pos, taxa, total = 12, None, None
        while pos + 8 <= len(dados):
            ident, tam = dados[pos:pos + 4], struct.unpack('<I', dados[pos + 4:pos + 8])[0]
            if ident == b'fmt ' and tam >= 16:
                taxa = struct.unpack('<I', dados[pos + 16:pos + 20])[0]          # bytes por segundo
            elif ident == b'data':
                total = min(tam, len(dados) - pos - 8)
                break
            pos += 8 + tam + (tam & 1)
        return int(total * 1000 / taxa) if taxa and total is not None else None
    except (struct.error, ZeroDivisionError):
        return None


def validar_som(dados, dur_ms_cliente):
    if len(dados) > MAX_SOM_BYTES:
        raise ErroAcervo(f'Som grande demais (máximo {MAX_SOM_BYTES // 1024} KB): corte pra uns 5 segundos.')
    mime = detectar_som(dados)
    if not mime:
        raise ErroAcervo('Esse arquivo não é um áudio que o Pantheon aceita (use MP3, OGG, WAV ou M4A).')
    real = duracao_wav_ms(dados) if mime == 'audio/wav' else None
    try:
        informada = int(dur_ms_cliente) if dur_ms_cliente not in (None, '') else None
    except (TypeError, ValueError):
        informada = None
    dur = real if real is not None else informada
    if dur is not None and dur > MAX_SOM_MS + 400:
        raise ErroAcervo(f'O som tem mais de {MAX_SOM_MS // 1000} segundos. Corte antes de enviar.')
    return mime, max(1, min(dur or MAX_SOM_MS, MAX_SOM_MS))


def preparar_figurinha(dados):
    """Decodifica e REGRAVA como WebP (parado ou animado) de até LADO_FIG px. Devolve (bytes, largura, altura, animado, dur_ms)."""
    from PIL import Image, ImageSequence
    if len(dados) > MAX_FIG_ENVIO:
        raise ErroAcervo(f'Imagem grande demais (máximo {MAX_FIG_ENVIO // (1024 * 1024)} MB).')
    try:
        im = Image.open(io.BytesIO(dados))
        formato = (im.format or '').upper()
        if formato not in ('PNG', 'WEBP', 'GIF', 'JPEG'):
            raise ErroAcervo('Use PNG, WebP, GIF ou JPG.')
        if im.width * im.height > 30_000_000:
            raise ErroAcervo('Imagem com pixels demais.')
        n = getattr(im, 'n_frames', 1)
        animado = n > 1
        if n > MAX_QUADROS_FIG:
            raise ErroAcervo(f'Figurinha animada com quadros demais (máximo {MAX_QUADROS_FIG}).')
        quadros, duracoes = [], []
        for f in ImageSequence.Iterator(im):
            q = f.convert('RGBA')
            q.thumbnail((LADO_FIG, LADO_FIG))
            quadros.append(q.copy())
            duracoes.append(int(f.info.get('duration') or 80))
        if not quadros:
            raise ErroAcervo('Não consegui ler a imagem.')
        saida = io.BytesIO()
        if animado:
            quadros[0].save(saida, 'WEBP', save_all=True, append_images=quadros[1:], duration=[max(20, d) for d in duracoes], loop=0, quality=80, method=4)
        else:
            quadros[0].save(saida, 'WEBP', quality=88, method=4)
        corpo = saida.getvalue()
        if len(corpo) > MAX_FIG_FINAL:
            raise ErroAcervo('Figurinha pesada demais mesmo depois de reduzida. Tente uma imagem mais simples ou com menos quadros.')
        return corpo, quadros[0].width, quadros[0].height, animado, (sum(duracoes) if animado else None)
    except ErroAcervo:
        raise
    except Exception:
        raise ErroAcervo('Não consegui abrir essa imagem. Ela está corrompida ou não é uma figurinha válida.')


# ---------------------------------------------------------------------------
# criar / listar / apagar
# ---------------------------------------------------------------------------
def _servidor_gerenciavel(usuario, server_id):
    try:
        srv = com_retry(lambda: Server.query.get(int(server_id)))
    except (TypeError, ValueError):
        srv = None
    if not srv or not eh_membro(usuario, srv.id):
        raise ErroAcervo('Servidor não encontrado.')
    if not cargos.pode(usuario, srv, 'gerenciar_servidor'):
        raise ErroAcervo('Só quem gerencia o servidor adiciona figurinhas e sons dele.')
    return srv


def criar(usuario, tipo, escopo, server_id, nome, emoji, dados, dur_ms=None):
    """Valida, passa pelo Guardião e grava. Devolve (item, aviso). Levanta ErroAcervo."""
    if tipo not in TIPOS or escopo not in ESCOPOS:
        raise ErroAcervo('Pedido inválido.')
    srv = _servidor_gerenciavel(usuario, server_id) if escopo == 'servidor' else None
    if not dados:
        raise ErroAcervo('Nenhum arquivo enviado.')
    if tipo == 'figurinha':
        corpo, w, h, animado, dur = preparar_figurinha(dados)
        mime = 'image/webp'
    else:
        mime, dur = validar_som(dados, dur_ms)
        corpo, w, h, animado = dados, None, None, None
    sha = hashlib.sha256(corpo).hexdigest()
    dono = {'person_id': usuario.id} if escopo == 'pessoa' else {'server_id': srv.id}
    q = AcervoItem.query.filter_by(tipo=tipo, escopo=escopo, sha=sha, **dono)
    repetido = com_retry(lambda: q.first())
    if repetido:
        return repetido, 'Você já tinha enviado esse arquivo.'
    usados = com_retry(lambda: AcervoItem.query.filter_by(tipo=tipo, escopo=escopo, **dono).filter(AcervoItem.status != 'recusado').count())
    if usados >= COTAS[escopo][tipo]:
        rot = 'figurinhas' if tipo == 'figurinha' else 'sons'
        raise ErroAcervo(f'Limite de {COTAS[escopo][tipo]} {rot} {"do servidor" if escopo == "servidor" else "no seu acervo"}. Apague alguma antes.')

    # Guardião ANTES de os outros verem/ouvirem
    resultado = guardiao.avaliar_para_acervo(tipo, corpo, mime)
    status = resultado['status']

    def preparar():
        item = AcervoItem(tipo=tipo, escopo=escopo, person_id=usuario.id, server_id=srv.id if srv else None, nome=limpar_nome(nome, 'Sem nome'),
                          emoji=cargos.emoji_valido(emoji), mime=mime, dados=corpo, tamanho=len(corpo), dur_ms=dur, largura=w, altura=h,
                          animado=animado, sha=sha, status=status)
        db.session.add(item)
        return item
    item = comitar_com_retry(preparar)

    aviso = None
    if status != 'aprovado':
        v = resultado['veredito']
        caso = guardiao.registrar_caso('figurinha' if tipo == 'figurinha' else 'som', usuario.id, v, trecho=f'{tipo.capitalize()} "{item.nome}" ({"do servidor" if srv else "pessoal"})',
                                       server_id=srv.id if srv else None, anexo_url=f'/api/acervo/{item.id}/arquivo')
        db.session.query(GuardiaoCaso).filter_by(id=caso.id).update({'ref_id': item.id})
        db.session.commit()
        try:
            from .bazar import ids_dos_admins
            for admin_id in ids_dos_admins():
                if admin_id != usuario.id:
                    guardiao.notificar_fora_do_socket(admin_id, 'Guardião: ' + ('figurinha' if tipo == 'figurinha' else 'som') + ' em análise', f'{item.nome} · caso #{caso.id}')
        except Exception as e:
            print(f'[ACERVO] aviso aos admins: {e}')
        aviso = ('Enviada! Ela fica em análise: o Guardião confere antes de os outros poderem ver. Você já pode ver e ouvir a sua aqui.' if tipo == 'figurinha'
                 else 'Enviado! Ele fica em análise: o Guardião confere antes de os outros poderem ouvir. Você já pode testar o seu.')
    return item, aviso


def item_json(item, eu_id=None):
    return {'id': item.id, 'tipo': item.tipo, 'escopo': item.escopo, 'nome': item.nome, 'emoji': item.emoji, 'status': item.status,
            'dur_ms': item.dur_ms, 'animado': bool(item.animado), 'tamanho': item.tamanho, 'server_id': item.server_id,
            'meu': item.person_id == eu_id, 'url': f'/api/acervo/{item.id}/arquivo'}


def listar(usuario, server_id=None):
    """O acervo da pessoa e, se ela é membro, o do servidor pedido. Quem não é dono só vê o que está APROVADO."""
    meus = com_retry(lambda: AcervoItem.query.filter_by(escopo='pessoa', person_id=usuario.id).filter(AcervoItem.status != 'recusado').order_by(AcervoItem.id.desc()).all())
    saida = {'meus': {'figurinha': [item_json(i, usuario.id) for i in meus if i.tipo == 'figurinha'], 'som': [item_json(i, usuario.id) for i in meus if i.tipo == 'som']},
             'servidor': None, 'cotas': COTAS, 'presets': list(PRESETS_SOM), 'som_entrada': usuario.som_entrada}
    if server_id is not None:
        try:
            sid = int(server_id)
        except (TypeError, ValueError):
            sid = None
        if sid and eh_membro(usuario, sid):
            srv = com_retry(lambda: Server.query.get(sid))
            gerencia = bool(srv and cargos.pode(usuario, srv, 'gerenciar_servidor'))
            q = AcervoItem.query.filter_by(escopo='servidor', server_id=sid).filter(AcervoItem.status != 'recusado')
            if not gerencia:
                q = q.filter(AcervoItem.status == 'aprovado')
            lista = com_retry(lambda: q.order_by(AcervoItem.id.desc()).all())
            saida['servidor'] = {'server_id': sid, 'gerencia': gerencia, 'nome': srv.name if srv else '',
                                 'figurinha': [item_json(i, usuario.id) for i in lista if i.tipo == 'figurinha'], 'som': [item_json(i, usuario.id) for i in lista if i.tipo == 'som']}
    return saida


def pode_gerenciar(usuario, item):
    if item.person_id == usuario.id and item.escopo == 'pessoa':
        return True
    if item.escopo == 'servidor' and item.server_id:
        srv = com_retry(lambda: Server.query.get(item.server_id))
        return bool(srv and eh_membro(usuario, srv.id) and cargos.pode(usuario, srv, 'gerenciar_servidor'))
    return False


def apagar(usuario, item_id):
    item = com_retry(lambda: AcervoItem.query.get(int(item_id)))
    if not item or not pode_gerenciar(usuario, item):
        raise ErroAcervo('Item não encontrado.')

    def preparar():
        # quem usava este som de entrada volta ao padrão (sem isso `custom:<id>` ficaria apontando pro nada)
        Person.query.filter(Person.som_entrada == f'custom:{item.id}').update({'som_entrada': None}, synchronize_session=False)
        db.session.delete(item)
    comitar_com_retry(preparar)
    return item.id


def renomear(usuario, item_id, nome, emoji):
    item = com_retry(lambda: AcervoItem.query.get(int(item_id)))
    if not item or not pode_gerenciar(usuario, item):
        raise ErroAcervo('Item não encontrado.')

    def preparar():
        item.nome = limpar_nome(nome, item.nome)
        item.emoji = cargos.emoji_valido(emoji)
    comitar_com_retry(preparar)
    return item


# ---------------------------------------------------------------------------
# uso
# ---------------------------------------------------------------------------
def item_usavel(usuario, item_id, tipo):
    """O item (figurinha ou som) que essa pessoa pode USAR agora, ou None: aprovado e (dela, ou de servidor onde ela é membro)."""
    try:
        item = com_retry(lambda: AcervoItem.query.get(int(item_id)))
    except (TypeError, ValueError):
        return None
    if not item or item.tipo != tipo or item.status != 'aprovado':
        return None
    if item.escopo == 'pessoa':
        return item if item.person_id == usuario.id else None
    return item if item.server_id and eh_membro(usuario, item.server_id) else None


def som_entrada_valido(pessoa):
    """O som de entrada da pessoa como ela pode ser vista pelos outros na call: 'preset:<id>' ou 'custom:<id>' (aprovado e dela). None = padrão.
    Custom custa uma consulta, só quando existe um."""
    v = getattr(pessoa, 'som_entrada', None)
    if not v:
        return None
    if v.startswith('preset:') and v[7:] in PRESETS_SOM:
        return v
    m = re.fullmatch(r'custom:(\d{1,9})', v)
    if m:
        item = com_retry(lambda: AcervoItem.query.filter_by(id=int(m.group(1)), tipo='som', escopo='pessoa', person_id=pessoa.id, status='aprovado').first())
        return v if item else None
    return None


def definir_som_entrada(usuario, valor):
    if valor in (None, '', 'padrao'):
        novo = None
    elif isinstance(valor, str) and valor.startswith('preset:') and valor[7:] in PRESETS_SOM:
        novo = valor
    elif isinstance(valor, str) and re.fullmatch(r'custom:\d{1,9}', valor):
        item = com_retry(lambda: AcervoItem.query.filter_by(id=int(valor[7:]), tipo='som', escopo='pessoa', person_id=usuario.id).first())
        if not item:
            raise ErroAcervo('Esse som não está no seu acervo.')
        if item.status != 'aprovado':
            raise ErroAcervo('Esse som ainda está em análise: quando o Guardião liberar, você pode usar como som de entrada.')
        novo = valor
    else:
        raise ErroAcervo('Som inválido.')

    def preparar():
        usuario.som_entrada = novo
    comitar_com_retry(preparar)
    return novo


def aplicar_decisao(item_id, acao):
    """O responsável decidiu o caso do Guardião: liberar aprova o item; confirmar/apagar recusa (apagar também joga fora os bytes)."""
    item = AcervoItem.query.get(int(item_id))
    if not item:
        return

    def preparar():
        if acao == 'liberar':
            item.status = 'aprovado'
        else:
            item.status = 'recusado'
            if acao == 'apagar':
                item.dados = b''
                item.tamanho = 0
            Person.query.filter(Person.som_entrada == f'custom:{item.id}').update({'som_entrada': None}, synchronize_session=False)
    comitar_com_retry(preparar)
