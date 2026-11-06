"""Call HÍBRIDA (Rodada 39): PREPARAÇÃO pra um servidor de mídia (SFU, LiveKit) que o dono vai ligar num servidor gratuito da Oracle.

O QUE ESTÁ PRONTO AQUI (sem socket, sem rede, sem dependência nova):
  * a POLÍTICA de qual transporte cada call usa (`politica`): P2P (PeerJS, como sempre) ou SFU;
  * a escolha FIXA por call (`ao_entrar`/`ao_sair`): a call nasce P2P, vira SFU quando passa de `CALL_P2P_MAX` pessoas e fica SFU até esvaziar
    (voltar de SFU pra P2P no meio da conversa só derrubaria todo mundo à toa);
  * a emissão do TOKEN de entrada no SFU (`emitir_token`: JWT HS256 no formato do LiveKit, assinado com a chave do servidor, sem biblioteca).

O QUE NÃO ESTÁ (de propósito, veja `docs/PLANO_SFU.md`): o adaptador do navegador que de fato conecta no SFU (precisa da biblioteca `livekit-client` e de um SFU
de verdade pra testar). Enquanto ele não existe, o cliente IGNORA o aviso de troca e todas as calls seguem P2P: ligar as variáveis sem o adaptador não muda nada.

Variáveis de ambiente (nenhuma é obrigatória; sem elas tudo segue P2P):
  CALL_MODE        p2p (padrão) | sfu (toda call de servidor usa o SFU) | auto (P2P até CALL_P2P_MAX pessoas, depois SFU)
  CALL_P2P_MAX     quantas pessoas a malha P2P aguenta antes de migrar (padrão 4; vai de 2 a 50)
  LIVEKIT_URL      wss://sfu.seudominio.com  (só wss://: o navegador do Pantheon é https e recusaria ws:// misturado)
  LIVEKIT_API_KEY / LIVEKIT_API_SECRET   o par que o `livekit-server generate-keys` cria (o segredo precisa ter 32+ caracteres)

O SEGREDO NUNCA SAI DO SERVIDOR: nem na página, nem no token (o token só leva a assinatura), nem em log.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time

MODOS = ('p2p', 'sfu', 'auto')
LIMITE_P2P_PADRAO = 4
LIMITE_P2P_MIN, LIMITE_P2P_MAX = 2, 50
TOKEN_TTL_S = 600                 # o token só vale pra ENTRAR na sala; quem já entrou segue mesmo depois de 10 min
SEGREDO_MIN = 32
FONTES_VOZ = ('microphone', 'camera')
FONTES_TELA = ('screen_share', 'screen_share_audio')

_RE_URL = re.compile(r'wss://[A-Za-z0-9.-]{3,253}(:\d{1,5})?(/[A-Za-z0-9/_.-]{0,100})?')
_RE_CHAVE_API = re.compile(r'[A-Za-z0-9_-]{4,64}')


class ErroSfu(Exception):
    pass


# ---------------------------------------------------------------------------------------------------------------- configuração
def modo():
    m = (os.environ.get('CALL_MODE') or 'p2p').strip().lower()
    return m if m in MODOS else 'p2p'


def limite_p2p():
    try:
        n = int(os.environ.get('CALL_P2P_MAX') or LIMITE_P2P_PADRAO)
    except ValueError:
        n = LIMITE_P2P_PADRAO
    return max(LIMITE_P2P_MIN, min(LIMITE_P2P_MAX, n))


def url_publica():
    """O endereço do SFU que o navegador vai usar, ou '' se não existe/é inválido (só wss://, sem usuário:senha, sem espaço)."""
    u = (os.environ.get('LIVEKIT_URL') or '').strip()
    return u if _RE_URL.fullmatch(u) else ''


def _chave_e_segredo():
    chave = (os.environ.get('LIVEKIT_API_KEY') or '').strip()
    segredo = (os.environ.get('LIVEKIT_API_SECRET') or '').strip()
    return (chave, segredo) if _RE_CHAVE_API.fullmatch(chave) and len(segredo) >= SEGREDO_MIN else ('', '')


def configurado():
    chave, segredo = _chave_e_segredo()
    return bool(url_publica() and chave and segredo)


def ativo():
    """O SFU pode ser usado agora: o dono pediu (CALL_MODE != p2p) E tudo que ele precisa está configurado. Qualquer lacuna = P2P."""
    return modo() != 'p2p' and configurado()


def politica_da_pagina():
    """O que a PÁGINA pode saber: modo, limite e o endereço. Nunca a chave nem o segredo."""
    ligado = ativo()
    return {'modo': modo() if ligado else 'p2p', 'limite_p2p': limite_p2p(), 'sfu': ligado, 'url': url_publica() if ligado else ''}


# ---------------------------------------------------------------------------------------------------------------- política
def politica(n_participantes, dm=False):
    """'p2p' ou 'sfu' pra uma call com `n_participantes` pessoas. Ligação de DM (2 pessoas) é sempre P2P: é o caso em que a malha é melhor."""
    if dm or not ativo():
        return 'p2p'
    if modo() == 'sfu':
        return 'sfu'
    return 'sfu' if n_participantes > limite_p2p() else 'p2p'


_transporte = {}                  # chave da call -> 'sfu' (ausente = p2p). Em memória, igual a participantes_call: reiniciar o servidor derruba as calls também.


def transporte_da_call(chave):
    return _transporte.get(str(chave), 'p2p')


def ao_entrar(chave, n_participantes, dm=False):
    """Chamado depois que alguém entra. Devolve (transporte, mudou). Uma vez SFU, a call fica SFU até esvaziar."""
    chave = str(chave)
    if _transporte.get(chave) == 'sfu':
        return 'sfu', False
    if politica(n_participantes, dm) == 'sfu':
        _transporte[chave] = 'sfu'
        return 'sfu', True
    return 'p2p', False


def ao_sair(chave, restantes):
    """Chamado depois que alguém sai. Call vazia esquece o transporte (a próxima nasce P2P de novo)."""
    if restantes <= 0:
        _transporte.pop(str(chave), None)


# ---------------------------------------------------------------------------------------------------------------- token (JWT HS256)
def _b64(dados):
    return base64.urlsafe_b64encode(dados).rstrip(b'=').decode('ascii')


def sala_do_sfu(chave):
    """O nome da sala no SFU: derivado SÓ da chave da call que o servidor já conferiu (nunca de um texto do cliente)."""
    return 'pantheon-' + re.sub(r'[^A-Za-z0-9_-]', '_', str(chave))[:50]


def emitir_token(usuario_id, nome, chave, publicar=True, tela=False, agora=None):
    """JWT de acesso do LiveKit pra UMA pessoa entrar na sala da call `chave`. `publicar=False` = só ouve/vê (ouvinte do palco).
    `tela=True` libera também a transmissão de tela (num canal de stream só o apresentador). O servidor decide tudo: o cliente só recebe o resultado."""
    if not configurado():
        raise ErroSfu('O SFU não está configurado.')
    chave_api, segredo = _chave_e_segredo()
    agora = int(agora if agora is not None else time.time())
    video = {'room': sala_do_sfu(chave), 'roomJoin': True, 'canSubscribe': True, 'canPublish': bool(publicar), 'canPublishData': bool(publicar)}
    if publicar:
        video['canPublishSources'] = list(FONTES_VOZ) + (list(FONTES_TELA) if tela else [])
    carga = {'iss': chave_api, 'sub': f'u{int(usuario_id)}', 'name': re.sub(r'[\x00-\x1f\x7f]', '', str(nome or ''))[:40],
             'nbf': agora - 10, 'iat': agora, 'exp': agora + TOKEN_TTL_S, 'video': video}
    cabecalho = _b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
    corpo = _b64(json.dumps(carga, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
    assinatura = _b64(hmac.new(segredo.encode('utf-8'), f'{cabecalho}.{corpo}'.encode('ascii'), hashlib.sha256).digest())
    return f'{cabecalho}.{corpo}.{assinatura}'
