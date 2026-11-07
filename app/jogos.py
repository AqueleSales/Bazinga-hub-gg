"""Jogos leves da call (sem socket): jogo da velha, pedra-papel-tesoura, forca e a mesa de sites (os dados viraram painel pessoal: app/dados.py).

O xadrez mora em `atividades.py` (motor próprio). Estes jogos seguem a MESMA interface que `atividades_events.py` espera de uma atividade:
`id`, `tipo`, `iniciador_id`, `seq`, `lados` (assento -> id da pessoa), `lado_de`, `sentar`, `levantar`, `partida` (None até a mesa estar completa),
`estado()` e, nos jogos novos, `acao(...)`.

Regra de ouro: o SERVIDOR decide tudo. O cliente manda o que quer fazer (uma casa, uma letra, uma escolha); aqui se confere vez, tipo e limites.
A palavra da forca e a escolha de quem ainda não revelou no pedra-papel-tesoura NUNCA saem do servidor antes da hora.
"""
import itertools
import random
import re
import threading
import time
import unicodedata

_alea = random.SystemRandom()        # sorteio de verdade (o que decide "quem vai?" não pode ser previsível)
_ids = itertools.count(1)
_trava_ids = threading.Lock()


def proximo_id():
    with _trava_ids:
        return next(_ids)


RESERVA_SEGUNDOS = 60               # quanto tempo uma cadeira fica guardada pra quem foi convidado


class Reserva:
    """Cadeira guardada pra quem foi convidado: com 3+ pessoas na call, quem chama escolhe o adversário e ninguém "rouba" o lugar."""
    reserva = None

    def _reserva_ativa(self):
        r = self.reserva
        if r and r['ate'] > time.time():
            return r
        self.reserva = None
        return None

    def reservar(self, usuario_id, segundos=RESERVA_SEGUNDOS):
        self.reserva = {'uid': usuario_id, 'ate': time.time() + segundos}
        self.seq += 1

    def liberar_reserva(self):
        if self.reserva is not None:
            self.reserva = None
            self.seq += 1

    def _vaga_para(self, usuario_id, livres):
        """Pode sentar numa das cadeiras `livres`? Se a última livre está guardada pra outra pessoa, não."""
        r = self._reserva_ativa()
        if r and r['uid'] != usuario_id and len(livres) <= 1:
            return False, 'Essa cadeira está guardada pra quem foi convidado. Se a pessoa recusar, ela abre de novo.'
        return True, ''

    def _ao_sentar(self, usuario_id):
        r = self._reserva_ativa()
        if r and r['uid'] == usuario_id:
            self.reserva = None

    def reserva_para_estado(self):
        r = self._reserva_ativa()
        if not r:
            return None, 0
        return r['uid'], max(1, int(r['ate'] - time.time()))


class Mesa(Reserva):
    """Base dos jogos de assento (jogo da velha, pedra-papel-tesoura) e dos abertos a todos (forca, dados)."""
    TIPO = ''
    LADOS = ()                # chaves dos assentos; vazio = jogo aberto (qualquer um da call participa)
    ROTULOS = {}

    def __init__(self, iniciador_id):
        self.id = proximo_id()
        self.tipo = self.TIPO
        self.iniciador_id = iniciador_id
        self.lados = {l: None for l in self.LADOS}
        self.nomes = {}                       # usuario_id -> {'nome', 'avatar'} (só para desenhar)
        self.seq = 0
        self.criada_em = time.time()
        self.iniciada = not self.LADOS        # jogo aberto já nasce valendo
        self.reserva = None

    # --- assentos ---------------------------------------------------------------------------------------------------
    @property
    def partida(self):
        """Compatível com o xadrez: None enquanto a mesa não está completa, qualquer coisa verdadeira depois."""
        return self if self.iniciada else None

    def lado_de(self, usuario_id):
        for l, uid in self.lados.items():
            if uid == usuario_id:
                return l
        return None

    def sentar(self, usuario_id, nome, avatar, lado=None):
        if not self.LADOS:
            return False, 'Esse jogo não tem cadeiras: é só participar.'
        if self.iniciada:
            return False, 'A partida já começou.'
        if self.lado_de(usuario_id):
            return False, 'Você já está sentado.'
        livres = [l for l, uid in self.lados.items() if uid is None]
        if not livres:
            return False, 'As cadeiras já estão ocupadas.'
        ok, motivo = self._vaga_para(usuario_id, livres)
        if not ok:
            return False, motivo
        if lado is None:
            lado = _alea.choice(livres)
        if lado not in livres:
            return False, 'Essa cadeira já está ocupada.'
        self.lados[lado] = usuario_id
        self.nomes[usuario_id] = {'nome': nome, 'avatar': avatar}
        self._ao_sentar(usuario_id)
        self.seq += 1
        if all(self.lados.values()):
            self.iniciada = True
            self.comecar()
        return True, ''

    def levantar(self, usuario_id):
        if self.iniciada and not self.terminou():
            return False, 'Não dá pra sair no meio da partida. Use "Desistir".'
        l = self.lado_de(usuario_id)
        if not l:
            return False, ''
        self.lados[l] = None
        self.iniciada = False
        self.resetar()
        self.seq += 1
        return True, ''

    # --- ganchos dos jogos -------------------------------------------------------------------------------------------
    def comecar(self):
        pass

    def resetar(self):
        pass

    def terminou(self):
        return False

    def acao(self, usuario_id, nome, avatar, dados, presentes=None, ouvinte=False):
        return False, 'Ação desconhecida.'

    def extra(self):
        return {}

    def estado(self):
        reservado, resta = self.reserva_para_estado()
        base = {
            'id': self.id, 'tipo': self.tipo, 'seq': self.seq, 'iniciador_id': self.iniciador_id,
            'lados': list(self.LADOS),
            'jogadores': {l: ({'id': uid, **self.nomes.get(uid, {})} if uid else None) for l, uid in self.lados.items()},
            'reservado_para': reservado, 'reserva_restante': resta,
            'situacao': ('aguardando' if not self.iniciada else ('fim' if self.terminou() else 'jogando')),
        }
        base.update(self.extra())
        return base


# =====================================================================================================================
# Jogo da velha
# =====================================================================================================================
LINHAS_VELHA = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


class Velha(Mesa):
    TIPO = 'velha'
    LADOS = ('x', 'o')

    def __init__(self, iniciador_id):
        super().__init__(iniciador_id)
        self.resetar()

    def resetar(self):
        self.casas = [''] * 9
        self.vez = 'x'
        self.resultado = None
        self.linha = None

    def comecar(self):
        self.resetar()

    def terminou(self):
        return self.resultado is not None

    def _conferir(self):
        for a, b, c in LINHAS_VELHA:
            if self.casas[a] and self.casas[a] == self.casas[b] == self.casas[c]:
                self.resultado = {'vencedor': self.casas[a], 'motivo': 'linha'}
                self.linha = [a, b, c]
                return
        if all(self.casas):
            self.resultado = {'vencedor': None, 'motivo': 'empate'}

    def acao(self, usuario_id, nome, avatar, dados, presentes=None, ouvinte=False):
        a = dados.get('acao')
        lado = self.lado_de(usuario_id)
        if not lado or not self.iniciada:
            return False, 'Você não está jogando esta partida.'
        if a == 'jogar':
            if self.resultado:
                return False, 'A partida já acabou.'
            if self.vez != lado:
                return False, 'Não é a sua vez.'
            casa = dados.get('casa')
            if isinstance(casa, bool) or not isinstance(casa, int) or not 0 <= casa <= 8:
                return False, 'Casa inválida.'
            if self.casas[casa]:
                return False, 'Essa casa já está ocupada.'
            self.casas[casa] = lado
            self.vez = 'o' if lado == 'x' else 'x'
            self._conferir()
            return True, ''
        if a == 'desistir':
            if self.resultado:
                return False, ''
            self.resultado = {'vencedor': 'o' if lado == 'x' else 'x', 'motivo': 'desistencia'}
            return True, ''
        if a == 'revanche':
            if not self.resultado:
                return False, ''
            self.lados['x'], self.lados['o'] = self.lados['o'], self.lados['x']      # troca quem começa
            self.resetar()
            return True, ''
        return False, 'Ação desconhecida.'

    def extra(self):
        return {'casas': list(self.casas), 'vez': self.vez, 'resultado': self.resultado, 'linha': self.linha}


# =====================================================================================================================
# Pedra, papel e tesoura (melhor de 3)
# =====================================================================================================================
ESCOLHAS_PPT = ('pedra', 'papel', 'tesoura')
VENCE = {'pedra': 'tesoura', 'tesoura': 'papel', 'papel': 'pedra'}


class PedraPapelTesoura(Mesa):
    TIPO = 'ppt'
    LADOS = ('a', 'b')
    VITORIAS = 2

    def __init__(self, iniciador_id):
        super().__init__(iniciador_id)
        self.resetar()

    def resetar(self):
        self.placar = {'a': 0, 'b': 0}
        self.rodada = 1
        self.escolhas = {}                 # lado -> escolha (SECRETA até os dois escolherem)
        self.revelado = None               # {'a': 'pedra', 'b': 'papel', 'vencedor': 'a'|'b'|None} depois que os dois escolhem
        self.resultado = None

    def comecar(self):
        self.resetar()

    def terminou(self):
        return self.resultado is not None

    def acao(self, usuario_id, nome, avatar, dados, presentes=None, ouvinte=False):
        a = dados.get('acao')
        lado = self.lado_de(usuario_id)
        if not lado or not self.iniciada:
            return False, 'Você não está jogando esta partida.'
        if a == 'escolher':
            if self.resultado or self.revelado:
                return False, 'Espere a próxima rodada.'
            valor = dados.get('valor')
            if valor not in ESCOLHAS_PPT:
                return False, 'Escolha pedra, papel ou tesoura.'
            if lado in self.escolhas:
                return False, 'Você já escolheu nesta rodada.'
            self.escolhas[lado] = valor
            if len(self.escolhas) == 2:
                ea, eb = self.escolhas['a'], self.escolhas['b']
                venc = None if ea == eb else ('a' if VENCE[ea] == eb else 'b')
                if venc:
                    self.placar[venc] += 1
                self.revelado = {'a': ea, 'b': eb, 'vencedor': venc}
                if venc and self.placar[venc] >= self.VITORIAS:
                    self.resultado = {'vencedor': venc, 'motivo': 'melhor_de_3'}
            return True, ''
        if a == 'proxima':
            if not self.revelado or self.resultado:
                return False, ''
            self.rodada += 1
            self.escolhas = {}
            self.revelado = None
            return True, ''
        if a == 'desistir':
            if self.resultado:
                return False, ''
            self.resultado = {'vencedor': 'b' if lado == 'a' else 'a', 'motivo': 'desistencia'}
            return True, ''
        if a == 'revanche':
            if not self.resultado:
                return False, ''
            self.resetar()
            return True, ''
        return False, 'Ação desconhecida.'

    def extra(self):
        return {'placar': dict(self.placar), 'rodada': self.rodada, 'escolheu': {l: (l in self.escolhas) for l in self.LADOS},
                'revelado': self.revelado, 'resultado': self.resultado}


# =====================================================================================================================
# Forca (todo mundo da call chuta letras)
# =====================================================================================================================
PALAVRAS_FORCA = (
    ('animal', 'elefante girafa tartaruga cachorro papagaio golfinho jacare borboleta macaco coruja pinguim tubarao camaleao hipopotamo'),
    ('comida', 'chocolate macarrao hamburguer sorvete pizza feijoada brigadeiro coxinha pastel lasanha panqueca tapioca churrasco abacaxi morango'),
    ('lugar', 'aeroporto biblioteca praia montanha escola hospital shopping cinema floresta deserto estacionamento supermercado'),
    ('objeto', 'guarda-chuva computador telefone geladeira televisao escova relogio mochila cadeira ventilador tesoura martelo'),
    ('profissao', 'professor medico bombeiro engenheiro cantor jogador dentista fotografo astronauta programador cozinheiro'),
    ('jogo e tecnologia', 'teclado servidor internet microfone controle console aplicativo mensagem notificacao navegador'),
    ('natureza', 'cachoeira vulcao arco-iris tempestade oceano relampago floresta planeta galaxia estrela'),
)
MAX_ERROS = 6


def _sem_acento(c):
    return ''.join(x for x in unicodedata.normalize('NFD', c) if unicodedata.category(x) != 'Mn')


class Forca(Mesa):
    TIPO = 'forca'
    LADOS = ()

    def __init__(self, iniciador_id):
        super().__init__(iniciador_id)
        self.resetar()

    def resetar(self):
        categoria, lista = _alea.choice(PALAVRAS_FORCA)
        self.dica = categoria
        self.palavra = _alea.choice(lista.split())            # SEGREDO: só vai pro cliente quando o jogo acaba
        self.certas = set()
        self.erradas = []
        self.chutes = {}                                        # letra -> usuario_id (quem chutou)
        self.resultado = None

    def terminou(self):
        return self.resultado is not None

    def _mascara(self):
        return [c if (not c.isalpha() or _sem_acento(c) in self.certas or self.resultado) else None for c in self.palavra]

    def acao(self, usuario_id, nome, avatar, dados, presentes=None, ouvinte=False):
        a = dados.get('acao')
        if ouvinte:
            return False, 'Quem só ouve a call assiste, mas não chuta.'
        self.nomes[usuario_id] = {'nome': nome, 'avatar': avatar}
        if a == 'letra':
            if self.resultado:
                return False, 'O jogo acabou. Comecem outra palavra.'
            letra = dados.get('letra')
            if not isinstance(letra, str) or len(letra) != 1 or not letra.isalpha():
                return False, 'Chute uma letra.'
            letra = _sem_acento(letra.lower())
            if not ('a' <= letra <= 'z'):
                return False, 'Chute uma letra.'
            if letra in self.chutes:
                return False, f'A letra {letra.upper()} já foi chutada.'
            self.chutes[letra] = usuario_id
            if any(_sem_acento(c) == letra for c in self.palavra):
                self.certas.add(letra)
                if all((not c.isalpha()) or _sem_acento(c) in self.certas for c in self.palavra):
                    self.resultado = {'venceu': True}
            else:
                self.erradas.append(letra)
                if len(self.erradas) >= MAX_ERROS:
                    self.resultado = {'venceu': False}
            return True, ''
        if a == 'nova':
            if not self.resultado:
                return False, 'Terminem esta palavra primeiro.'
            self.resetar()
            return True, ''
        return False, 'Ação desconhecida.'

    def extra(self):
        fim = self.resultado is not None
        return {
            'dica': self.dica, 'mascara': self._mascara(), 'erradas': list(self.erradas), 'max_erros': MAX_ERROS,
            'acertos': sorted(self.certas), 'resultado': self.resultado,
            'palavra': self.palavra if fim else None,
            'quem': {l: self.nomes.get(u, {}).get('nome', '?') for l, u in self.chutes.items()},
        }


# =====================================================================================================================
# Mesa de RPG e sites: uma PÁGINA que a call inteira abre junta (quadro de desenho, mapa de batalha, jogo de navegador, mesa virtual)
# =====================================================================================================================
# Lista FECHADA de sites (nada de endereço qualquer: uma iframe de página escolhida por um desconhecido seria porta de golpe e de rastreio).
# `embute`: o site deixa aparecer dentro de outro site (conferido nos cabeçalhos X-Frame-Options/frame-ancestors deles). Quem NÃO deixa (Owlbear Rodeo, Roll20,
# Foundry, D&D Beyond...) vira "todo mundo abre o mesmo link": a call compartilha o endereço da sala e cada um abre numa aba.
# Pra incluir um site: só entra o que tem https, e só depois de olhar se ele deixa embutir (curl -I e procurar X-Frame-Options / frame-ancestors).
SITES = {
    'excalidraw.com': ('Excalidraw', 'Quadro branco em grupo: desenhe mapas, planeje a batalha, rabisque junto.', True),
    'tldraw.com': ('tldraw', 'Quadro infinito pra desenhar e anotar em grupo.', True),
    'www.tldraw.com': ('tldraw', 'Quadro infinito pra desenhar e anotar em grupo.', True),
    'jklm.fun': ('JKLM', 'Jogos de palavras pra jogar em grupo.', True),
    'skribbl.io': ('skribbl.io', 'Desenhe e adivinhe.', True),
    'owlbear.rodeo': ('Owlbear Rodeo', 'Mesa virtual de RPG com mapa e fichas.', False),
    'www.owlbear.rodeo': ('Owlbear Rodeo', 'Mesa virtual de RPG com mapa e fichas.', False),
    'app.roll20.net': ('Roll20', 'Mesa virtual de RPG.', False),
    'roll20.net': ('Roll20', 'Mesa virtual de RPG.', False),
    'foundryvtt.com': ('Foundry VTT', 'Mesa virtual de RPG (a sala é a do seu servidor Foundry).', False),
    'www.dndbeyond.com': ('D&D Beyond', 'Fichas e regras de D&D.', False),
    'dndbeyond.com': ('D&D Beyond', 'Fichas e regras de D&D.', False),
    'lichess.org': ('Lichess', 'Xadrez online (a sala de vocês).', False),
    'www.chess.com': ('Chess.com', 'Xadrez online.', False),
}
MAX_URL_SITE = 300


def escolher_site(url):
    """(True, info) ou (False, mensagem). Só https, sem usuário:senha, e o endereço tem que ser de um site da lista. Guarda o endereço normalizado
    (com o #fragmento: é nele que o Excalidraw leva a sala). Não faz pedido de rede nenhum: é só conferir o texto."""
    from urllib.parse import urlsplit
    s = str(url or '').strip()
    if not s or len(s) > MAX_URL_SITE or any(ch in s for ch in ' \t\n\r"\'<>\\'):
        return False, 'Cole o link da sala ou da mesa (https://...).'
    try:
        u = urlsplit(s)
    except ValueError:
        return False, 'Esse link não é válido.'
    if u.scheme != 'https' or not u.hostname or u.username or u.password or (u.port not in (None, 443)):
        return False, 'Só links https:// de sites da lista.'
    host = u.hostname.lower()
    if host not in SITES:
        return False, 'Esse site ainda não está na lista de mesas e quadros que a call pode abrir junto.'
    nome, desc, embute = SITES[host]
    limpo = f'https://{host}{u.path or "/"}' + (f'?{u.query}' if u.query else '') + (f'#{u.fragment}' if u.fragment else '')
    return True, {'url': limpo, 'host': host, 'nome': nome, 'desc': desc, 'embute': embute}


class SiteCompartilhado(Mesa):
    TIPO = 'site'
    LADOS = ()

    def __init__(self, iniciador_id):
        super().__init__(iniciador_id)
        self.info = {'url': '', 'host': '', 'nome': '', 'desc': '', 'embute': False}

    def definir(self, info):
        self.info = dict(info)
        self.seq += 1

    def terminou(self):
        return False

    def acao(self, usuario_id, nome, avatar, dados, presentes=None, ouvinte=False):
        if ouvinte:
            return False, 'Quem só ouve a call assiste, mas não troca a página.'
        if dados.get('acao') == 'trocar':
            if usuario_id != self.iniciador_id:
                return False, 'Só quem abriu a atividade troca a página.'
            ok, info = escolher_site(dados.get('url'))
            if not ok:
                return False, info
            self.definir(info)
            return True, ''
        return False, 'Ação desconhecida.'

    def extra(self):
        return {'site': dict(self.info)}


# Os dados NÃO estão aqui: a partir da Rodada 40 são um painel PESSOAL (app/dados.py, dados_events.py), não uma atividade que ocupa a call.
JOGOS = {c.TIPO: c for c in (Velha, PedraPapelTesoura, Forca, SiteCompartilhado)}
