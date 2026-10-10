"""Baixar uma imagem de um link da internet (o campo "Colar link" do seletor de imagem: avatar, faixa, fundo, tema, lojinha).

Por que isso mora no servidor: o navegador não consegue ler a imagem de outro site (CORS) pra mandar pro editor, e deixar o servidor buscar
"qualquer URL que a pessoa mandar" é o buraco clássico de SSRF (pedir `https://localhost/...` ou o IP de um serviço interno). Por isso:

- só `https`, porta 443, sem usuário/senha no link, e o endereço tem que ser um DOMÍNIO (nada de IP direto nem `localhost`);
- o domínio é resolvido AQUI, todos os IPs têm que ser públicos (`is_global`), e a conexão vai pro IP que foi validado (com o certificado
  conferido contra o nome do site): trocar o DNS entre a checagem e a conexão não adianta (DNS rebinding);
- redirecionamento é seguido na mão (até 3), validando cada salto do zero;
- até 8 MB, sem compressão do lado do site, e o conteúdo é conferido com o Pillow (só PNG, JPEG, WebP e GIF: SVG fica de fora, pode ter script);
- link de PÁGINA (ex.: um pin do Pinterest) vale: pega a imagem que a própria página declara em `og:image` (1 nível só).
"""
import ipaddress
import re
import socket
from html import unescape
from io import BytesIO
from urllib.parse import urljoin, urlsplit

LIMITE_BYTES = 8 * 1024 * 1024
LIMITE_PAGINA_BYTES = 400 * 1024
MAX_SALTOS = 3
FORMATOS_OK = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp', 'GIF': 'image/gif'}

# domínio de verdade: pelo menos um ponto, letras/números/hífen, terminando em letras (IP e "localhost" não passam)
_RE_HOST = re.compile(r'^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')
_RE_META = re.compile(r'<meta\b[^>]*>', re.I)
_RE_ATRIBUTO = re.compile(r'''([a-zA-Z:_-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')''')
_UA = 'Mozilla/5.0 (compatible; PantheonImagem/1.0)'


class ErroImportar(Exception):
    """Erro que a pessoa pode ler (já vem em português e sem detalhe técnico)."""


def _ip_publico_de(host):
    """Resolve o domínio e devolve um IPv4 público. Qualquer endereço interno entre os resultados recusa o link."""
    try:
        infos = socket.getaddrinfo(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise ErroImportar('Não achei esse endereço. Confira o link.')
    ips = []
    for info in infos:
        ip = info[4][0]
        if not ipaddress.ip_address(ip).is_global:
            raise ErroImportar('Esse endereço não é um site público.')
        ips.append(ip)
    if not ips:
        raise ErroImportar('Não achei esse endereço. Confira o link.')
    return ips[0]


def _validar_url(url):
    """(host, caminho+consulta) de um link https público, ou ErroImportar."""
    if not isinstance(url, str) or len(url) > 2000:
        raise ErroImportar('Cole o link de uma imagem (começa com https://).')
    try:
        partes = urlsplit(url.strip())
        porta = partes.port
    except ValueError:
        raise ErroImportar('Esse link não parece válido.')
    if partes.scheme != 'https':
        raise ErroImportar('Só links https:// (com cadeado) funcionam.')
    if partes.username or partes.password or porta not in (None, 443):
        raise ErroImportar('Esse link não é aceito (sem usuário/senha e sem porta diferente).')
    host = (partes.hostname or '').lower().rstrip('.')
    if not _RE_HOST.match(host):
        raise ErroImportar('Use o link de um site (um endereço como i.exemplo.com), não um IP.')
    return host, (partes.path or '/') + ('?' + partes.query if partes.query else '')


def _pedir(host, ip, caminho):
    """Um GET na mão: conecta no IP já validado e confere o certificado contra o nome do site. Devolve (status, cabecalhos, corpo, trecho_lido)."""
    import certifi
    import urllib3
    pool = urllib3.HTTPSConnectionPool(
        ip, port=443, server_hostname=host, assert_hostname=host, cert_reqs='CERT_REQUIRED', ca_certs=certifi.where(),
        timeout=urllib3.Timeout(connect=5, read=8), retries=False, maxsize=1)
    try:
        resp = pool.urlopen('GET', caminho, redirect=False, retries=False, preload_content=False, assert_same_host=False,
                            headers={'Host': host, 'User-Agent': _UA, 'Accept': 'image/*,text/html;q=0.5,*/*;q=0.1', 'Accept-Encoding': 'identity'})
    except urllib3.exceptions.SSLError:
        pool.close()
        raise ErroImportar('O certificado desse site não é confiável.')
    except urllib3.exceptions.HTTPError:
        pool.close()
        raise ErroImportar('O site não respondeu. Tente de novo ou baixe a imagem e envie o arquivo.')
    return pool, resp


def _ler(resp, limite):
    corpo = bytearray()
    for pedaco in resp.stream(64 * 1024):
        corpo += pedaco
        if len(corpo) > limite:
            return bytes(corpo[:limite + 1]), True
    return bytes(corpo), False


def _imagem_da_pagina(html, base):
    """Endereço da imagem que a página declara (og:image / twitter:image), ou None."""
    for tag in _RE_META.findall(html):
        attrs = {m.group(1).lower(): unescape(m.group(2) if m.group(2) is not None else m.group(3)) for m in _RE_ATRIBUTO.finditer(tag)}
        if (attrs.get('property') or attrs.get('name') or '').lower() in ('og:image', 'og:image:url', 'og:image:secure_url', 'twitter:image', 'twitter:image:src'):
            if attrs.get('content'):
                return urljoin(base, attrs['content'].strip())
    return None


def baixar_imagem_externa(url, _pagina=False):
    """Baixa a imagem do link e devolve (bytes, mime). Levanta ErroImportar com a mensagem pra pessoa."""
    atual = url
    for _ in range(MAX_SALTOS + 1):
        host, caminho = _validar_url(atual)
        ip = _ip_publico_de(host)
        pool, resp = _pedir(host, ip, caminho)
        try:
            if resp.status in (301, 302, 303, 307, 308):
                destino = resp.headers.get('Location')
                if not destino:
                    raise ErroImportar('O link redireciona pra lugar nenhum.')
                atual = urljoin(atual, destino)
                continue
            if resp.status != 200:
                raise ErroImportar(f'O site recusou o pedido (erro {resp.status}). Baixe a imagem e envie o arquivo.')
            tipo = (resp.headers.get('Content-Type') or '').split(';')[0].strip().lower()
            tamanho = resp.headers.get('Content-Length')
            if tipo.startswith('image/') and tamanho and tamanho.isdigit() and int(tamanho) > LIMITE_BYTES:
                raise ErroImportar('Imagem muito pesada (máximo 8 MB).')
            if tipo in ('text/html', 'application/xhtml+xml'):
                if _pagina:
                    raise ErroImportar('Não achei uma imagem nesse link.')
                corpo, passou = _ler(resp, LIMITE_PAGINA_BYTES)
                alvo = _imagem_da_pagina(corpo.decode('utf-8', 'ignore'), atual)
                if not alvo:
                    raise ErroImportar('Esse link é de uma página sem imagem. Abra a foto, clique com o botão direito e escolha "Copiar endereço da imagem".')
                return baixar_imagem_externa(alvo, _pagina=True)
            dados, passou = _ler(resp, LIMITE_BYTES)
            if passou:
                raise ErroImportar('Imagem muito pesada (máximo 8 MB).')
            return _conferir_imagem(dados)
        finally:
            resp.release_conn()
            pool.close()
    raise ErroImportar('O link redireciona demais.')


def _conferir_imagem(dados):
    """Confere com o Pillow que é mesmo uma imagem (png/jpeg/webp/gif) de tamanho sensato. (bytes, mime)."""
    from PIL import Image
    try:
        im = Image.open(BytesIO(dados))
        formato = im.format
        largura, altura = im.size
        im.verify()
    except Exception:
        raise ErroImportar('Esse link não é de uma imagem.')
    if formato not in FORMATOS_OK:
        raise ErroImportar('Só imagens PNG, JPG, WebP e GIF.')
    if largura * altura > 40_000_000:
        raise ErroImportar('Imagem grande demais (mais de 40 megapixels).')
    return dados, FORMATOS_OK[formato]
