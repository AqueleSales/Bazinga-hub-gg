"""Atividades da call (Rodada 34): jogos leves que duas pessoas jogam DENTRO de uma call enquanto as outras assistem.

Hoje só existe o xadrez. Este arquivo não tem socket: é o motor (regras do xadrez, para o SERVIDOR decidir se um lance vale,
sem confiar no navegador de ninguém) e o estado em memória de cada atividade. Os eventos moram em `atividades_events.py`.

O cliente usa o chess.js só para desenhar (lances possíveis, notação). Quem manda é este motor: lance ilegal, fora de vez ou de
quem não está sentado é recusado aqui.
"""
import random
import re
import time

FILES = 'abcdefgh'
_RE_CASA = re.compile(r'^[a-h][1-8]$')

TIPOS_ATIVIDADE = ('xadrez',)   # lista fechada: tipo inventado pelo cliente é ignorado

COR_BRANCA, COR_PRETA = 'w', 'b'
INICIAL_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

_CAVALO = ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1))
_REI = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
_DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))
_RETA = ((1, 0), (-1, 0), (0, 1), (0, -1))


def casa(nome):
    """'e4' -> 28 (a1 = 0, h8 = 63)."""
    return (int(nome[1]) - 1) * 8 + FILES.index(nome[0])


def nome_casa(i):
    return FILES[i % 8] + str(i // 8 + 1)


def _cor_da_peca(p):
    return COR_BRANCA if p.isupper() else COR_PRETA


class Posicao:
    """Uma posição de xadrez (peças, vez, roques, en passant e contadores). Imutável na prática: `aplicar` devolve outra."""

    __slots__ = ('tab', 'vez', 'roques', 'ep', 'meio', 'cheio')

    def __init__(self, tab, vez, roques, ep, meio, cheio):
        self.tab = tab          # lista de 64; '.' = vazia, maiúscula = branca, minúscula = preta
        self.vez = vez
        self.roques = roques    # subconjunto de 'KQkq'
        self.ep = ep            # índice da casa de captura en passant (ou None)
        self.meio = meio        # lances desde a última captura/peão (regra dos 50)
        self.cheio = cheio

    # ---------- FEN ----------
    @classmethod
    def do_fen(cls, fen):
        partes = fen.split()
        if len(partes) < 4:
            raise ValueError('FEN incompleto')
        tab = []
        linhas = partes[0].split('/')
        if len(linhas) != 8:
            raise ValueError('FEN com número errado de linhas')
        for linha in reversed(linhas):          # o FEN começa pela linha 8; o índice 0 é a1
            col = 0
            for ch in linha:
                if ch.isdigit():
                    tab.extend('.' * int(ch)); col += int(ch)
                elif ch in 'PNBRQKpnbrqk':
                    tab.append(ch); col += 1
                else:
                    raise ValueError('FEN com peça inválida')
            if col != 8:
                raise ValueError('FEN com linha de tamanho errado')
        if partes[1] not in ('w', 'b'):
            raise ValueError('FEN sem vez')
        ep = casa(partes[3]) if _RE_CASA.match(partes[3]) else None
        roques = ''.join(c for c in 'KQkq' if c in partes[2])
        meio = int(partes[4]) if len(partes) > 4 and partes[4].isdigit() else 0
        cheio = int(partes[5]) if len(partes) > 5 and partes[5].isdigit() else 1
        return cls(tab, partes[1], roques, ep, meio, cheio)

    @classmethod
    def inicial(cls):
        return cls.do_fen(INICIAL_FEN)

    def fen(self):
        linhas = []
        for r in range(7, -1, -1):
            s, vazias = '', 0
            for f in range(8):
                p = self.tab[r * 8 + f]
                if p == '.':
                    vazias += 1
                else:
                    if vazias:
                        s += str(vazias); vazias = 0
                    s += p
            if vazias:
                s += str(vazias)
            linhas.append(s)
        return '%s %s %s %s %d %d' % ('/'.join(linhas), self.vez, self.roques or '-',
                                       nome_casa(self.ep) if self.ep is not None else '-', self.meio, self.cheio)

    def chave(self):
        """Identifica a posição para a regra das 3 repetições (ep só conta se alguém realmente pode capturar)."""
        ep = '-'
        if self.ep is not None and any(m[1] == self.ep and self.tab[m[0]].upper() == 'P' for m in self._pseudo_lances(self.vez)):
            ep = nome_casa(self.ep)
        return ''.join(self.tab) + self.vez + self.roques + ep

    # ---------- ataques ----------
    def rei_de(self, cor):
        alvo = 'K' if cor == COR_BRANCA else 'k'
        return self.tab.index(alvo) if alvo in self.tab else -1

    def atacada(self, i, por):
        """A casa `i` é atacada por alguma peça da cor `por`?"""
        f, r = i % 8, i // 8
        tab = self.tab
        peao, cavalo, rei, bispo, torre, dama = (('P', 'N', 'K', 'B', 'R', 'Q') if por == COR_BRANCA else ('p', 'n', 'k', 'b', 'r', 'q'))
        dr = -1 if por == COR_BRANCA else 1      # o peão branco ataca "para cima": ele está uma linha ABAIXO da casa atacada
        for df in (-1, 1):
            ff, rr = f + df, r + dr
            if 0 <= ff < 8 and 0 <= rr < 8 and tab[rr * 8 + ff] == peao:
                return True
        for df, dr2 in _CAVALO:
            ff, rr = f + df, r + dr2
            if 0 <= ff < 8 and 0 <= rr < 8 and tab[rr * 8 + ff] == cavalo:
                return True
        for df, dr2 in _REI:
            ff, rr = f + df, r + dr2
            if 0 <= ff < 8 and 0 <= rr < 8 and tab[rr * 8 + ff] == rei:
                return True
        for dirs, tipos in ((_DIAG, (bispo, dama)), (_RETA, (torre, dama))):
            for df, dr2 in dirs:
                ff, rr = f + df, r + dr2
                while 0 <= ff < 8 and 0 <= rr < 8:
                    p = tab[rr * 8 + ff]
                    if p != '.':
                        if p in tipos:
                            return True
                        break
                    ff += df; rr += dr2
        return False

    def em_xeque(self, cor=None):
        cor = cor or self.vez
        k = self.rei_de(cor)
        return k >= 0 and self.atacada(k, COR_PRETA if cor == COR_BRANCA else COR_BRANCA)

    # ---------- geração de lances ----------
    def _pseudo_lances(self, cor):
        """(de, para, promocao) sem conferir se o próprio rei fica em xeque (isso é feito em `lances_legais`)."""
        tab = self.tab
        lances = []
        inimiga = COR_PRETA if cor == COR_BRANCA else COR_BRANCA
        for i, p in enumerate(tab):
            if p == '.' or _cor_da_peca(p) != cor:
                continue
            f, r = i % 8, i // 8
            t = p.upper()
            if t == 'P':
                d = 1 if cor == COR_BRANCA else -1
                inicio = 1 if cor == COR_BRANCA else 6
                ultima = 7 if cor == COR_BRANCA else 0
                rr = r + d
                if 0 <= rr < 8:
                    if tab[rr * 8 + f] == '.':
                        if rr == ultima:
                            lances.extend((i, rr * 8 + f, x) for x in 'qrbn')
                        else:
                            lances.append((i, rr * 8 + f, None))
                            if r == inicio and tab[(r + 2 * d) * 8 + f] == '.':
                                lances.append((i, (r + 2 * d) * 8 + f, None))
                    for df in (-1, 1):
                        ff = f + df
                        if not 0 <= ff < 8:
                            continue
                        alvo = rr * 8 + ff
                        if tab[alvo] != '.' and _cor_da_peca(tab[alvo]) == inimiga:
                            if rr == ultima:
                                lances.extend((i, alvo, x) for x in 'qrbn')
                            else:
                                lances.append((i, alvo, None))
                        elif self.ep is not None and alvo == self.ep and tab[alvo] == '.':
                            lances.append((i, alvo, None))
            elif t in 'NK':
                for df, dr in (_CAVALO if t == 'N' else _REI):
                    ff, rr = f + df, r + dr
                    if 0 <= ff < 8 and 0 <= rr < 8:
                        alvo = rr * 8 + ff
                        if tab[alvo] == '.' or _cor_da_peca(tab[alvo]) == inimiga:
                            lances.append((i, alvo, None))
            else:
                dirs = _DIAG if t == 'B' else _RETA if t == 'R' else _DIAG + _RETA
                for df, dr in dirs:
                    ff, rr = f + df, r + dr
                    while 0 <= ff < 8 and 0 <= rr < 8:
                        alvo = rr * 8 + ff
                        if tab[alvo] == '.':
                            lances.append((i, alvo, None))
                        else:
                            if _cor_da_peca(tab[alvo]) == inimiga:
                                lances.append((i, alvo, None))
                            break
                        ff += df; rr += dr
        return lances

    def _roques_possiveis(self, cor):
        """Roques que o rei pode fazer agora (casas livres, nada atacado no caminho, rei fora de xeque)."""
        tab = self.tab
        base = 0 if cor == COR_BRANCA else 56
        rei, torre = ('K', 'R') if cor == COR_BRANCA else ('k', 'r')
        inimiga = COR_PRETA if cor == COR_BRANCA else COR_BRANCA
        lances = []
        if tab[base + 4] != rei or self.atacada(base + 4, inimiga):
            return lances
        pequeno = 'K' if cor == COR_BRANCA else 'k'
        grande = 'Q' if cor == COR_BRANCA else 'q'
        if pequeno in self.roques and tab[base + 7] == torre and tab[base + 5] == '.' and tab[base + 6] == '.' \
                and not self.atacada(base + 5, inimiga) and not self.atacada(base + 6, inimiga):
            lances.append((base + 4, base + 6, None))
        if grande in self.roques and tab[base] == torre and tab[base + 1] == '.' and tab[base + 2] == '.' and tab[base + 3] == '.' \
                and not self.atacada(base + 3, inimiga) and not self.atacada(base + 2, inimiga):
            lances.append((base + 4, base + 2, None))
        return lances

    def lances_legais(self):
        cor = self.vez
        legais = []
        for m in self._pseudo_lances(cor) + self._roques_possiveis(cor):
            nova = self.aplicar(*m)
            if not nova.em_xeque(cor):
                legais.append(m)
        return legais

    def aplicar(self, de, para, promocao=None):
        """Devolve a posição depois do lance (não confere se é legal)."""
        tab = list(self.tab)
        peca = tab[de]
        alvo = tab[para]
        cor = _cor_da_peca(peca)
        ep_novo = None
        roques = self.roques
        tipo = peca.upper()
        if tipo == 'P' and para == self.ep and alvo == '.' and (de % 8) != (para % 8):
            tab[para - 8 if cor == COR_BRANCA else para + 8] = '.'           # en passant: o peão capturado está atrás
        if tipo == 'P' and abs(para - de) == 16:
            ep_novo = (de + para) // 2
        tab[de] = '.'
        tab[para] = peca
        if tipo == 'P' and para // 8 in (0, 7):
            nova_peca = (promocao or 'q')
            tab[para] = nova_peca.upper() if cor == COR_BRANCA else nova_peca.lower()
        if tipo == 'K' and abs(para - de) == 2:                                # roque: a torre pula pro outro lado
            base = de - de % 8
            if para > de:
                tab[base + 5], tab[base + 7] = tab[base + 7], '.'
            else:
                tab[base + 3], tab[base] = tab[base], '.'
        # direitos de roque: rei ou torre mexeu, ou torre foi capturada na casa de origem
        if tipo == 'K':
            roques = roques.replace('K', '').replace('Q', '') if cor == COR_BRANCA else roques.replace('k', '').replace('q', '')
        for ponto, letra in ((0, 'Q'), (7, 'K'), (56, 'q'), (63, 'k')):
            if de == ponto or para == ponto:
                roques = roques.replace(letra, '')
        meio = 0 if (tipo == 'P' or alvo != '.') else self.meio + 1
        cheio = self.cheio + (1 if cor == COR_PRETA else 0)
        return Posicao(tab, COR_PRETA if cor == COR_BRANCA else COR_BRANCA, roques, ep_novo, meio, cheio)

    def material_insuficiente(self):
        """Rei x rei, rei+bispo/cavalo x rei, ou bispos todos da mesma cor: ninguém dá xeque-mate."""
        pecas = [(i, p) for i, p in enumerate(self.tab) if p not in ('.', 'K', 'k')]
        if not pecas:
            return True
        if any(p.upper() in 'PRQ' for _, p in pecas):
            return False
        if len(pecas) == 1:
            return True
        if all(p.upper() == 'B' for _, p in pecas):
            return len({((i % 8) + (i // 8)) % 2 for i, _ in pecas}) == 1
        return False


def lance_de_texto(de, para, promocao=None):
    """Valida o texto vindo do cliente: devolve (de, para, promocao) como números, ou None se o formato é inválido."""
    if not isinstance(de, str) or not isinstance(para, str) or not _RE_CASA.match(de) or not _RE_CASA.match(para):
        return None
    if promocao not in (None, '', 'q', 'r', 'b', 'n'):
        return None
    return casa(de), casa(para), (promocao or None)


def lance_em_texto(de, para, promocao=None):
    return nome_casa(de) + nome_casa(para) + (promocao or '')


def perft(pos, profundidade):
    """Conta as posições alcançáveis em N lances (usado nos testes para provar que o motor gera exatamente os lances legais)."""
    if profundidade == 0:
        return 1
    total = 0
    for m in pos.lances_legais():
        total += perft(pos.aplicar(*m), profundidade - 1) if profundidade > 1 else 1
    return total


# ---------------------------------------------------------------------------------------------------------------------
# Partida e atividade em memória
# ---------------------------------------------------------------------------------------------------------------------

class Partida:
    """Uma partida: posição atual, lances jogados e posições vistas (para as 3 repetições)."""

    def __init__(self):
        self.pos = Posicao.inicial()
        self.lances = []                 # ['e2e4', 'e7e5', 'g1f3', ... , 'e7e8q']
        self.ultimo = None               # (de, para) do último lance
        self.vistas = {self.pos.chave(): 1}
        self.resultado = None            # None enquanto joga; depois {'vencedor': 'w'|'b'|None, 'motivo': str}
        self.empate_de = None            # cor de quem propôs empate (None = ninguém)

    def jogar(self, de, para, promocao=None):
        """Aplica o lance se for legal. Devolve (ok, motivo_da_recusa)."""
        if self.resultado:
            return False, 'A partida já acabou.'
        legais = self.pos.lances_legais()
        if promocao is None and self.pos.tab[de].upper() == 'P' and para // 8 in (0, 7):
            promocao = 'q'                                    # promoção sem escolha vira dama
        if (de, para, promocao) not in legais:
            return False, 'Esse lance não é permitido.'
        self.pos = self.pos.aplicar(de, para, promocao)
        self.lances.append(lance_em_texto(de, para, promocao))
        self.ultimo = (de, para)
        self.empate_de = None                                 # mexer recusa a proposta pendente
        k = self.pos.chave()
        self.vistas[k] = self.vistas.get(k, 0) + 1
        self._conferir_fim()
        return True, ''

    def _conferir_fim(self):
        pos = self.pos
        if not pos.lances_legais():
            if pos.em_xeque():
                self.resultado = {'vencedor': COR_PRETA if pos.vez == COR_BRANCA else COR_BRANCA, 'motivo': 'xequemate'}
            else:
                self.resultado = {'vencedor': None, 'motivo': 'afogamento'}
        elif pos.material_insuficiente():
            self.resultado = {'vencedor': None, 'motivo': 'material'}
        elif self.vistas.get(pos.chave(), 0) >= 3:
            self.resultado = {'vencedor': None, 'motivo': 'repeticao'}
        elif pos.meio >= 100:
            self.resultado = {'vencedor': None, 'motivo': 'cinquenta'}

    def desistir(self, cor):
        if not self.resultado:
            self.resultado = {'vencedor': COR_PRETA if cor == COR_BRANCA else COR_BRANCA, 'motivo': 'desistencia'}

    def empatar(self):
        if not self.resultado:
            self.resultado = {'vencedor': None, 'motivo': 'acordo'}


class Atividade:
    """O que está rolando numa call: tipo, quem sentou em cada lado e a partida."""
    _contador = 0

    def __init__(self, tipo, iniciador_id):
        Atividade._contador += 1
        self.id = Atividade._contador
        self.tipo = tipo
        self.iniciador_id = iniciador_id
        self.lados = {COR_BRANCA: None, COR_PRETA: None}      # cor -> usuario_id
        self.nomes = {}                                      # usuario_id -> {'nome', 'avatar'} (só para desenhar)
        self.partida = None                                  # nasce quando os dois lados estão ocupados
        self.seq = 0                                         # sobe a cada mudança: o cliente ignora estado mais velho
        self.criada_em = time.time()

    def lado_de(self, usuario_id):
        for cor, uid in self.lados.items():
            if uid == usuario_id:
                return cor
        return None

    def sentar(self, usuario_id, nome, avatar, cor=None):
        """Senta a pessoa num lado livre (`cor` None = sorteia entre os livres). Devolve (ok, motivo)."""
        if self.partida is not None:
            return False, 'A partida já começou.'
        if self.lado_de(usuario_id):
            return False, 'Você já está sentado.'
        livres = [c for c, uid in self.lados.items() if uid is None]
        if not livres:
            return False, 'Os dois lados já estão ocupados.'
        if cor is None:
            cor = random.choice(livres)
        if cor not in livres:
            return False, 'Esse lado já está ocupado.'
        self.lados[cor] = usuario_id
        self.nomes[usuario_id] = {'nome': nome, 'avatar': avatar}
        self.seq += 1
        if all(self.lados.values()):
            self.partida = Partida()
        return True, ''

    def levantar(self, usuario_id):
        if self.partida is not None and not self.partida.resultado:
            return False, 'Não dá pra sair no meio da partida. Use "Desistir".'
        cor = self.lado_de(usuario_id)
        if not cor:
            return False, ''
        self.lados[cor] = None
        self.partida = None
        self.seq += 1
        return True, ''

    def revanche(self):
        """Nova partida com as cores trocadas (só depois do fim)."""
        if self.partida is None or not self.partida.resultado:
            return False
        self.lados[COR_BRANCA], self.lados[COR_PRETA] = self.lados[COR_PRETA], self.lados[COR_BRANCA]
        self.partida = Partida()
        self.seq += 1
        return True

    def estado(self):
        """O que cada cliente precisa para desenhar (sem nada além do que já é visível numa call)."""
        p = self.partida
        if p is None:
            situacao = 'aguardando'
        else:
            situacao = 'fim' if p.resultado else 'jogando'
        return {
            'id': self.id, 'tipo': self.tipo, 'seq': self.seq, 'situacao': situacao, 'iniciador_id': self.iniciador_id,
            'jogadores': {cor: ({'id': uid, **self.nomes.get(uid, {})} if uid else None) for cor, uid in self.lados.items()},
            'fen': p.pos.fen() if p else INICIAL_FEN,
            'lances': list(p.lances) if p else [],
            'vez': p.pos.vez if p else COR_BRANCA,
            'ultimo': [nome_casa(p.ultimo[0]), nome_casa(p.ultimo[1])] if p and p.ultimo else None,
            'xeque': bool(p and not p.resultado and p.pos.em_xeque()),
            'resultado': p.resultado if p else None,
            'empate_de': p.empate_de if p else None,
        }


# chave da call -> Atividade em andamento (uma por call; some quando a call esvazia ou alguém encerra)
ATIVIDADES = {}


def da_call(chave):
    return ATIVIDADES.get(chave)


def iniciar(chave, tipo, iniciador_id):
    if tipo not in TIPOS_ATIVIDADE or chave in ATIVIDADES:
        return None
    ATIVIDADES[chave] = Atividade(tipo, iniciador_id)
    return ATIVIDADES[chave]


def encerrar(chave):
    return ATIVIDADES.pop(chave, None)
