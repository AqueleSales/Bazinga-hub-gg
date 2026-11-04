"""Arquivos de arte do Estúdio (/estudio): Lottie, imagem (GIF, WebP, APNG, PNG, JPEG) e vídeo (MP4, WebM).

A pessoa que produz a arte (ou a IA dela) faz o arquivo fora do site; o admin arrasta pro Estúdio, ajusta tamanho/posição/velocidade
e o arquivo vira uma camada ("arquivo") de um efeito. Os bytes ficam no banco (tabela `estudio_arquivo`) e saem por
`/estudio/arquivo/<id>` com cache imutável: o id é aleatório e o arquivo nunca muda (pra trocar a arte, sobe-se outro).

Nada aqui confia no que o cliente diz: o TIPO e o mime saem do CONTEÚDO (assinatura do arquivo), o tamanho e as dimensões saem do
próprio arquivo (Pillow / JSON), e o Lottie passa por uma checagem que recusa expressões (código), imagens embutidas, texto e áudio.
Só o vídeo traz medidas do navegador (largura, altura e duração), porque não há como ler um MP4 sem ffmpeg; elas são só informação
(limitadas) e a capa (1º quadro) que o navegador manda é reencodada aqui como imagem.

SVG é recusado de propósito (carrega script). O Lottie é desenhado no navegador pela versão "light" do lottie-web (static/js/vendor),
que NÃO roda expressões: mesmo assim a expressão é barrada aqui, porque dado que o motor ignora hoje pode deixar de ser ignorado amanhã.
"""
import hashlib
import io
import json
import re
import secrets

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from .models import db, EstudioArquivo, EfeitoCustom
from .utils import com_retry, comitar_com_retry

LIM_LOTTIE = 400 * 1024
LIM_IMAGEM = 3 * 1024 * 1024
LIM_VIDEO = 6 * 1024 * 1024
LIM_CAPA = 600 * 1024
LIM_TOTAL = 120 * 1024 * 1024          # teto de tudo que a biblioteca guarda (o banco do plano grátis é pequeno)
MAX_ARQUIVOS = 200
MAX_LADO = 2048                         # imagem: maior lado
MAX_QUADROS = 240                       # imagem animada
MAX_PIXELS_ANIMADOS = 60_000_000        # largura x altura x quadros: segura o tempo de leitura e a memória de quem abre
MAX_DURACAO_S = 20                      # uma passada de animação/vídeo
MAX_CAMADAS_LOTTIE = 200
MAX_NOS_LOTTIE = 300_000
LADO_CAPA = 512
RE_ID = re.compile(r'^[0-9a-f]{12}$')

# camadas de Lottie aceitas: 0 pré-composição, 1 sólido, 3 nulo, 4 forma. Fora: 2 imagem, 5 texto, 6 áudio, 9 vídeo, câmera, luz...
LOTTIE_CAMADAS_OK = {0, 1, 3, 4}

MIME_IMAGEM = {'PNG': 'image/png', 'GIF': 'image/gif', 'WEBP': 'image/webp', 'JPEG': 'image/jpeg'}


class ErroArquivo(Exception):
    """Erro que o admin pode ler (vai pro toast)."""


def _mb(n):
    return f'{n / (1024 * 1024):.0f} MB' if n >= 1024 * 1024 else f'{n // 1024} KB'


# ---------------------------------------------------------------------------------------------
# DETECÇÃO PELO CONTEÚDO
# ---------------------------------------------------------------------------------------------
def detectar(dados):
    """('lottie'|'imagem'|'video', mime provisório) a partir dos primeiros bytes. Levanta ErroArquivo se não for nenhum dos aceitos."""
    ini = dados[:16]
    if not ini:
        raise ErroArquivo('O arquivo está vazio.')
    if ini.startswith(b'\x89PNG\r\n\x1a\n') or ini[:6] in (b'GIF87a', b'GIF89a') or ini.startswith(b'\xff\xd8\xff') or (ini[:4] == b'RIFF' and ini[8:12] == b'WEBP'):
        return 'imagem', ''
    if ini[4:8] == b'ftyp':
        if ini[8:12] == b'qt  ':
            raise ErroArquivo('Vídeo .mov não é aceito. Exporte em MP4 (H.264) ou WebM.')
        return 'video', 'video/mp4'
    if ini[:4] == b'\x1a\x45\xdf\xa3':
        return 'video', 'video/webm'
    limpo = dados[:64].lstrip(b'\xef\xbb\xbf \t\r\n')
    if limpo.startswith(b'{'):
        return 'lottie', 'application/json'
    if limpo.startswith(b'<'):
        raise ErroArquivo('SVG não é aceito (pode carregar script). Exporte como Lottie, WebP, APNG, GIF ou vídeo.')
    raise ErroArquivo('Formato não aceito. Use Lottie (.json), GIF, WebP, APNG/PNG, JPEG, MP4 ou WebM.')


# ---------------------------------------------------------------------------------------------
# LOTTIE
# ---------------------------------------------------------------------------------------------
def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validar_lottie(dados):
    """Confere o Lottie e devolve (bytes compactos, info). Recusa: expressões (código), imagens embutidas/externas, texto, áudio, vídeo,
    câmera/luz, e qualquer coisa grande ou longa demais. O arquivo é reserializado sem espaços (menor, e só o JSON entra, nunca lixo ao redor)."""
    if len(dados) > LIM_LOTTIE:
        raise ErroArquivo(f'Lottie pesado demais ({_mb(len(dados))}). O máximo é {_mb(LIM_LOTTIE)}: simplifique a animação.')
    try:
        obj = json.loads(dados.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ErroArquivo('Esse JSON não é um Lottie válido.')
    if not isinstance(obj, dict):
        raise ErroArquivo('Esse JSON não é um Lottie válido.')
    for k in ('fr', 'ip', 'op', 'w', 'h'):
        if not _numero(obj.get(k)):
            raise ErroArquivo(f'Lottie sem o campo "{k}": exporte de novo pelo Bodymovin/LottieFiles.')
    if not isinstance(obj.get('layers'), list) or not obj['layers']:
        raise ErroArquivo('Esse Lottie não tem camadas.')
    fr, ip, op, w, h = obj['fr'], obj['ip'], obj['op'], obj['w'], obj['h']
    if not 1 <= fr <= 60:
        raise ErroArquivo('A taxa de quadros do Lottie tem que ficar entre 1 e 60.')
    if op <= ip:
        raise ErroArquivo('O Lottie não tem duração.')
    if (op - ip) / fr > MAX_DURACAO_S:
        raise ErroArquivo(f'O Lottie dura mais de {MAX_DURACAO_S} s. Corte a animação.')
    if not (1 <= w <= 4096 and 1 <= h <= 4096):
        raise ErroArquivo('O tamanho (largura x altura) do Lottie é inválido.')

    camadas = 0
    nos = 0
    pilha = [obj]
    while pilha:
        no = pilha.pop()
        nos += 1
        if nos > MAX_NOS_LOTTIE:
            raise ErroArquivo('Esse Lottie é complexo demais. Simplifique.')
        if isinstance(no, dict):
            if isinstance(no.get('x'), str):
                raise ErroArquivo('Esse Lottie usa expressões (código dentro da animação). Exporte sem expressões.')
            lista = no.get('layers')
            if isinstance(lista, list):
                for c in lista:
                    camadas += 1
                    if not isinstance(c, dict) or c.get('ty') not in LOTTIE_CAMADAS_OK:
                        raise ErroArquivo('Esse Lottie tem camada de imagem, texto, áudio, vídeo ou câmera. Só formas, sólidos e pré-composições são aceitos: converta o texto em formas.')
            pilha.extend(no.values())
        elif isinstance(no, list):
            pilha.extend(no)
    if camadas > MAX_CAMADAS_LOTTIE:
        raise ErroArquivo(f'Esse Lottie tem {camadas} camadas (o máximo é {MAX_CAMADAS_LOTTIE}).')
    for a in obj.get('assets') or []:
        if not isinstance(a, dict) or 'layers' not in a:
            raise ErroArquivo('Esse Lottie traz imagem ou áudio embutido. Só formas são aceitas.')

    compacto = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return compacto, {'w': int(w), 'h': int(h), 'dur_ms': int((op - ip) / fr * 1000), 'quadros': int(op - ip)}


# ---------------------------------------------------------------------------------------------
# IMAGEM
# ---------------------------------------------------------------------------------------------
def _abrir_imagem(dados, limite_lado=MAX_LADO):
    try:
        im = Image.open(io.BytesIO(dados))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ErroArquivo('Esse arquivo não é uma imagem de verdade.')
    if im.format not in MIME_IMAGEM:
        raise ErroArquivo('Formato de imagem não aceito. Use GIF, WebP, APNG/PNG ou JPEG.')
    w, h = im.size
    if w < 8 or h < 8:
        raise ErroArquivo('Imagem pequena demais.')
    if w > limite_lado or h > limite_lado:
        raise ErroArquivo(f'Imagem grande demais ({w}x{h}). O máximo é {limite_lado} px de lado.')
    return im


def capa_webp(im):
    """1º quadro da imagem em WebP (RGBA, no máximo LADO_CAPA px): a versão parada, pra listas, 'reduzir movimento' e pausas."""
    try:
        im.seek(0)
    except EOFError:
        pass
    quadro = im.convert('RGBA')
    quadro.thumbnail((LADO_CAPA, LADO_CAPA))
    saida = io.BytesIO()
    quadro.save(saida, 'WEBP', quality=85, method=4)
    return saida.getvalue()


def validar_imagem(dados):
    """(info, capa|None). Confere formato real, tamanho, quantidade de quadros e o peso total na memória; mede a duração de uma passada."""
    if len(dados) > LIM_IMAGEM:
        raise ErroArquivo(f'Imagem pesada demais ({_mb(len(dados))}). O máximo é {_mb(LIM_IMAGEM)}: reduza o tamanho ou os quadros.')
    im = _abrir_imagem(dados)
    w, h = im.size
    n = getattr(im, 'n_frames', 1)
    info = {'w': w, 'h': h, 'dur_ms': None, 'quadros': n, 'mime': MIME_IMAGEM[im.format]}
    if n <= 1:
        try:
            im.load()
        except (OSError, ValueError):
            raise ErroArquivo('Essa imagem está corrompida.')
        return info, None
    if n > MAX_QUADROS:
        raise ErroArquivo(f'A animação tem {n} quadros (o máximo é {MAX_QUADROS}).')
    if w * h * n > MAX_PIXELS_ANIMADOS:
        raise ErroArquivo(f'A animação é pesada demais ({w}x{h} com {n} quadros). Reduza o tamanho ou corte quadros.')
    total = 0
    try:
        for i in range(n):
            im.seek(i)
            im.load()                    # no WebP a duração do quadro só aparece depois de carregar o quadro (no GIF/APNG já viria do seek)
            total += int(im.info.get('duration') or 100) or 100
    except (EOFError, OSError, ValueError):
        raise ErroArquivo('Essa animação está corrompida.')
    if total > MAX_DURACAO_S * 1000:
        raise ErroArquivo(f'A animação dura mais de {MAX_DURACAO_S} s. Corte.')
    info['dur_ms'] = max(total, 40)
    return info, capa_webp(im)


def validar_capa(dados):
    """A capa que o navegador gerou do vídeo: tem que ser imagem de verdade e leve; sai reencodada em WebP."""
    if not dados:
        return None
    if len(dados) > LIM_CAPA:
        raise ErroArquivo('A imagem de capa do vídeo ficou pesada demais.')
    im = _abrir_imagem(dados, 1024)
    return capa_webp(im)


# ---------------------------------------------------------------------------------------------
# GUARDAR / LER
# ---------------------------------------------------------------------------------------------
def _info_video(medidas):
    def _int(v, mn, mx):
        try:
            x = int(float(v))
        except (TypeError, ValueError):
            return None
        return x if mn <= x <= mx else None
    medidas = medidas or {}
    dur = _int(medidas.get('dur'), 100, MAX_DURACAO_S * 1000)
    if dur is None:
        raise ErroArquivo(f'O vídeo precisa ter até {MAX_DURACAO_S} s (e mais de 0,1 s).')
    return {'w': _int(medidas.get('w'), 16, 4096), 'h': _int(medidas.get('h'), 16, 4096), 'dur_ms': dur, 'quadros': None}


def guardar(dados, nome, pessoa_id, capa=None, medidas=None):
    """Valida e guarda um arquivo. Devolve o EstudioArquivo (existente, se o mesmo conteúdo já estava na biblioteca)."""
    tipo, mime = detectar(dados)
    capa_final = None
    if tipo == 'lottie':
        dados, info = validar_lottie(dados)
    elif tipo == 'imagem':
        info, capa_final = validar_imagem(dados)
        mime = info.pop('mime')
    else:
        if len(dados) > LIM_VIDEO:
            raise ErroArquivo(f'Vídeo pesado demais ({_mb(len(dados))}). O máximo é {_mb(LIM_VIDEO)}: reduza a duração ou a resolução.')
        info = _info_video(medidas)
        capa_final = validar_capa(capa)
        if capa_final is None:
            raise ErroArquivo('Não consegui gerar a imagem de capa do vídeo. Tente outro arquivo ou outro codec (MP4 H.264 costuma funcionar).')

    sha = hashlib.sha256(dados).hexdigest()
    existente = com_retry(lambda: EstudioArquivo.query.filter_by(sha=sha).first())
    if existente:
        return existente

    total, qtd = com_retry(lambda: db.session.query(func.coalesce(func.sum(EstudioArquivo.bytes), 0), func.count(EstudioArquivo.id)).one())
    if qtd >= MAX_ARQUIVOS:
        raise ErroArquivo(f'A biblioteca já tem {MAX_ARQUIVOS} arquivos. Apague os que não usa.')
    if int(total) + len(dados) + len(capa_final or b'') > LIM_TOTAL:
        raise ErroArquivo(f'A biblioteca chegou no limite de {_mb(LIM_TOTAL)}. Apague arquivos que não usa.')

    novo_id = secrets.token_hex(6)
    nome_limpo = re.sub(r'[\x00-\x1f<>"\']', '', (nome or '').rsplit('/', 1)[-1].rsplit('\\', 1)[-1])[:80] or None

    def preparar():
        a = EstudioArquivo(id=novo_id, tipo=tipo, mime=mime, nome=nome_limpo, bytes=len(dados), w=info.get('w'), h=info.get('h'),
                           dur_ms=info.get('dur_ms'), quadros=info.get('quadros'), sha=sha, dados=dados, capa=capa_final,
                           tem_capa=bool(capa_final), criado_por=pessoa_id)
        db.session.add(a)
        return a

    try:
        return comitar_com_retry(preparar)
    except IntegrityError:        # dois envios do mesmo arquivo ao mesmo tempo: o outro já gravou
        db.session.rollback()
        igual = EstudioArquivo.query.filter_by(sha=sha).first()
        if igual:
            return igual
        raise


def info_para_cliente(a):
    """O que o motor do navegador (e a biblioteca) precisa saber. Só endereços do próprio servidor, montados aqui a partir do id."""
    return {'id': a.id, 'k': a.tipo, 'url': f'/estudio/arquivo/{a.id}', 'capa': f'/estudio/arquivo/{a.id}/capa' if a.tem_capa else None,
            'dur': a.dur_ms, 'w': a.w, 'h': a.h, 'q': a.quadros}


def biblioteca_para_json(a):
    j = info_para_cliente(a)
    j.update({'nome': a.nome or '', 'mime': a.mime, 'bytes': a.bytes, 'criado_em': a.criado_em.isoformat() if a.criado_em else None})
    return j


def listar():
    linhas = com_retry(lambda: EstudioArquivo.query.order_by(EstudioArquivo.criado_em.desc()).all())
    return [biblioteca_para_json(a) for a in linhas]


def uso_total():
    total, qtd = com_retry(lambda: db.session.query(func.coalesce(func.sum(EstudioArquivo.bytes), 0), func.count(EstudioArquivo.id)).one())
    return {'bytes': int(total), 'qtd': int(qtd), 'max_bytes': LIM_TOTAL, 'max_qtd': MAX_ARQUIVOS}


def existe(aid):
    return bool(isinstance(aid, str) and RE_ID.match(aid) and com_retry(lambda: db.session.query(EstudioArquivo.id).filter_by(id=aid).first()))


def resolver(ids):
    """{id: info_para_cliente} dos arquivos que existem (uma consulta pra todos). Id que sumiu fica de fora: o motor pula a camada."""
    ids = {i for i in ids if isinstance(i, str) and RE_ID.match(i)}
    if not ids:
        return {}
    linhas = com_retry(lambda: EstudioArquivo.query.filter(EstudioArquivo.id.in_(list(ids))).all())
    return {a.id: info_para_cliente(a) for a in linhas}


def conteudo(aid):
    """(mime, bytes, sha) do arquivo, ou None."""
    if not isinstance(aid, str) or not RE_ID.match(aid):
        return None
    a = com_retry(lambda: EstudioArquivo.query.get(aid))
    return (a.mime, a.dados, a.sha) if a else None


def conteudo_capa(aid):
    """(bytes da capa, sha) ou None."""
    if not isinstance(aid, str) or not RE_ID.match(aid):
        return None
    a = com_retry(lambda: EstudioArquivo.query.get(aid))
    return (a.capa, a.sha) if a and a.tem_capa and a.capa else None


def efeitos_que_usam(aid):
    """ids dos efeitos cuja receita aponta pra este arquivo."""
    linhas = com_retry(lambda: EfeitoCustom.query.filter(EfeitoCustom.receita.like(f'%"arq":"{aid}"%')).all())
    return [e.id for e in linhas]


def apagar(aid):
    if not isinstance(aid, str) or not RE_ID.match(aid):
        raise ErroArquivo('Arquivo não encontrado.')
    a = com_retry(lambda: db.session.query(EstudioArquivo.id).filter_by(id=aid).first())
    if not a:
        raise ErroArquivo('Arquivo não encontrado.')
    usos = efeitos_que_usam(aid)
    if usos:
        raise ErroArquivo('Esse arquivo é usado por: ' + ', '.join(usos) + '. Tire dos efeitos antes de apagar.')

    def preparar():
        EstudioArquivo.query.filter_by(id=aid).delete()

    comitar_com_retry(preparar)
