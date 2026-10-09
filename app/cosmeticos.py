"""Catálogo único de cosméticos, patentes de nível, insígnias e posse.

Fonte da verdade dos itens que NÃO são livres. Os itens livres (moldura "neon", placa
"ouro"...) continuam nas tuplas de `utils.py` e nos catálogos do `chat.html`; aqui
moram os que exigem posse - o servidor só aceita equipar o que a pessoa TEM.

Convenções:
  * `item_id` = "<tipo>:<id>" (ex.: "moldura:gogeta", "badge:criador", "pacote:sasuke").
    É o que vai na tabela `Posse` e nos eventos do socket.
  * O `<id>` sozinho é o que vai pro banco/CSS: `Person.moldura = 'gogeta'` -> classe
    `.moldura-gogeta`. Por isso o id nunca é texto livre: só entra o que está aqui.
  * Nada neste arquivo toca o banco no import (models só é importado dentro das funções).
"""
import json
from datetime import datetime

# ==========================================
# TEMAS DO LABORATÓRIO (só o dono e o amigo beta tester)
# ==========================================
TEMAS = {
    'gogeta': {'nome': 'Gogeta', 'cor': '#ff9d2e', 'desc': 'Fusão, aura dourada e a Punição de Alma.'},
    'sasuke': {'nome': 'Sasuke', 'cor': '#8b5cf6', 'desc': 'Chidori, Sharingan e a chama negra.'},
    'fusao': {'nome': 'Fusão', 'cor': '#e879f9', 'desc': 'Duas chamas, uma só. Só nós dois.'},
    # ---- JJK (Rodada 16): temas da LOJA, nível lendário (12 itens cada) + um combo misto. Arte em CSS/SVG e som sintetizado (nada copiado da obra). ----
    'gojo': {'nome': 'Gojo', 'cor': '#4aa8ff', 'loja': True, 'premium': True, 'cores': ['#4aa8ff', '#9b5cff'], 'icone': 'fa-eye',
             'lema': 'Nada te alcança.',
             'desc': 'Infinito, Seis Olhos, o azul e o vermelho que viram roxo e a Expansão de Domínio: Vazio Ilimitado, com os dedos cruzados.'},
    'sukuna': {'nome': 'Sukuna', 'cor': '#e63946', 'loja': True, 'premium': True, 'cores': ['#e63946', '#f3e9d2'], 'icone': 'fa-skull',
               'lema': 'Aqui é o meu santuário.',
               'desc': 'Aura maldita, nome em brasa, cortes e a Expansão de Domínio: Santuário Malevolente, com as marcas do rosto e montes de cortes pretos.'},
    'mahoraga': {'nome': 'Mahoraga', 'cor': '#d9a520', 'loja': True, 'premium': True, 'cores': ['#d9a520', '#2b2d2a'], 'icone': 'fa-dharmachakra',
                 'lema': 'Tudo se adapta.', 'desc': 'A roda dourada que gira um encaixe de cada vez, e se adapta.'},
    'jjk': {'nome': 'Combo JJK', 'cor': '#9b5cff', 'combo': True, 'desc': 'Gojo contra Sukuna no mesmo perfil.'},
    # ---- Temas da LOJA (à venda por DRC no Armazém). Arte original, só evoca o tema: nada de símbolo/sprite de terceiros. ----
    # `cores` = as duas cores da vitrine do tema; `lema` = a frase do cartão; `icone` = Font Awesome.
    'relojoaria': {'nome': 'Relojoaria', 'cor': '#d4a24c', 'loja': True, 'cores': ['#d4a24c', '#3f5f6b'], 'icone': 'fa-clock',
                   'lema': 'Cada segundo tem o seu mecanismo.',
                   'desc': 'Latão, engrenagens e um relógio de bolso que abre, some e volta a fechar.'},
    'dualidade': {'nome': 'Dualidade', 'cor': '#9b5cff', 'loja': True, 'cores': ['#2f6bff', '#ff2d55'], 'icone': 'fa-circle-half-stroke',
                  'lema': 'Azul, vermelho... e o que nasce quando se encontram.',
                  'desc': 'Duas energias se aproximam, viram roxo e explodem.'},
    'cubos': {'nome': 'Cubos', 'cor': '#5fa83a', 'loja': True, 'cores': ['#5fa83a', '#8b5a2b'], 'icone': 'fa-cube',
              'lema': 'Um mundo inteiro feito de blocos.',
              'desc': 'Grama, terra e céu em blocos: anel que avança aos pulinhos, nuvens quadradas e um chão quadriculado.'},
    'batida': {'nome': 'Batida', 'cor': '#d946ef', 'loja': True, 'cores': ['#d946ef', '#22d3ee'], 'icone': 'fa-music',
               'lema': 'O seu perfil também tem ritmo.',
               'desc': 'Barras de equalizador pulsando, um vinil que gira e um nome que acompanha o refrão.'},
    'quadra': {'nome': 'Quadra', 'cor': '#e8742c', 'loja': True, 'cores': ['#e8742c', '#2a5db0'], 'icone': 'fa-volleyball',
               'lema': 'Bola no ar, jogo decidido no último ponto.',
               'desc': 'Uma bola orbitando o avatar, rede esticada na placa e uma quadra inteira na faixa.'},
    'mira': {'nome': 'Mira', 'cor': '#e8483f', 'loja': True, 'cores': ['#e8483f', '#4fd1c5'], 'icone': 'fa-crosshairs',
             'lema': 'Travou o alvo. Agora é com você.',
             'desc': 'Uma mira que trava no avatar, um mapa tático na placa e um radar que varre a faixa.'},
    'manga': {'nome': 'Mangá', 'cor': '#e63946', 'loja': True, 'cores': ['#e63946', '#f1faee'], 'icone': 'fa-pen-nib',
              'lema': 'Preto, branco e uma cor só para o clímax.',
              'desc': 'Traço de tinta que se desenha sozinho, retícula de página e linhas de velocidade.'},
    # ---- Rodada 15: coleção "Básicos" (comum, sem animação) e 3 temas premium com efeitos (arte original que só evoca o estilo) ----
    'basicos': {'nome': 'Básicos', 'cor': '#9aa3b2', 'loja': True, 'sem_hero': True, 'sem_pacote': True, 'cores': ['#9aa3b2', '#5b6475'], 'icone': 'fa-circle',
                'lema': 'Cor lisa, sem firula.', 'desc': 'O essencial: molduras, nomes, placas e faixas de cor lisa, sem animação. Os mais baratos do Armazém.'},
    'cyber': {'nome': 'Cyber Neon', 'cor': '#22e4ff', 'loja': True, 'cores': ['#22e4ff', '#ff2d95'], 'icone': 'fa-microchip', 'premium': True,
              'lema': 'A cidade nunca dorme. O neon também não.',
              'desc': 'Ciano e rosa-choque: scanlines, letreiro holográfico, chuva de dados, estática de rádio e um "sistema online" ao entrar na call.'},
    'eldoria': {'nome': 'Eldoria', 'cor': '#d9a520', 'loja': True, 'cores': ['#d9a520', '#2f9e6a'], 'icone': 'fa-wand-sparkles', 'premium': True,
                'lema': 'Todo reino começa com uma runa.',
                'desc': 'Fantasia medieval: coroa de carvalho, pergaminho com runas, poeira mágica, anel rúnico e um cristal no mapa.'},
    'arcade': {'nome': 'Arcade 8-bit', 'cor': '#ffd23f', 'loja': True, 'cores': ['#ff4fa3', '#ffd23f'], 'icone': 'fa-gamepad', 'premium': True,
               'lema': 'Insira uma moeda para continuar.',
               'desc': 'Pixels, corações de vida, moedas girando, chuva de pixels e o som de uma moeda coletada.'},
    # ---- Fora dos temas da vitrine (sem chip nem pacote): edições limitadas à venda e recompensas de coleção ----
    'edicao': {'nome': 'Edição Limitada', 'cor': '#ffcc33', 'desc': 'Acaba por prazo ou por estoque. Quando acabar, acabou.'},
    'colecao': {'nome': 'Coleção', 'cor': '#c0c8d6', 'desc': 'Prêmios de quem coleciona o Armazém. Não se compram: se conquistam.'},
}

# ==========================================
# PATENTES (substituem Novato/Explorador/...)
# ------------------------------------------------------------
# O nível vai de 1 a 1000+ (XP total, nunca zera - ver utils.py). A patente é a
# "faixa" do nível; cada uma tem 3 subníveis visuais (I, II, III), repartidos em
# terços da faixa. `anim` (0-4) diz quanto o ícone se mexe: quanto maior a patente,
# mais animação. O desenho do ícone mora no chat.html (`svgPatente`), por id.
# `de`/`ate` incluem os dois extremos; `ate=None` = sem teto (Panteão).
# ==========================================
PATENTES = [
    {'id': 'iniciado',    'nome': 'Iniciado',    'de': 1,   'ate': 9,    'anim': 0, 'cor': '#d98a4a'},
    {'id': 'aprendiz',    'nome': 'Aprendiz',    'de': 10,  'ate': 24,   'anim': 0, 'cor': '#a78bfa'},
    {'id': 'explorador',  'nome': 'Explorador',  'de': 25,  'ate': 49,   'anim': 1, 'cor': '#f5c542'},
    {'id': 'desbravador', 'nome': 'Desbravador', 'de': 50,  'ate': 89,   'anim': 1, 'cor': '#2dd4bf'},
    {'id': 'veterano',    'nome': 'Veterano',    'de': 90,  'ate': 149,  'anim': 2, 'cor': '#60a5fa'},
    {'id': 'heroi',       'nome': 'Herói',       'de': 150, 'ate': 229,  'anim': 2, 'cor': '#38bdf8'},
    {'id': 'lenda',       'nome': 'Lenda',       'de': 230, 'ate': 329,  'anim': 3, 'cor': '#fb923c'},
    {'id': 'campeao',     'nome': 'Campeão',     'de': 330, 'ate': 449,  'anim': 3, 'cor': '#a5f3fc'},
    {'id': 'semideus',    'nome': 'Semideus',    'de': 450, 'ate': 599,  'anim': 3, 'cor': '#fbbf24'},
    {'id': 'tita',        'nome': 'Titã',        'de': 600, 'ate': 749,  'anim': 4, 'cor': '#f97316'},
    {'id': 'olimpiano',   'nome': 'Olimpiano',   'de': 750, 'ate': 899,  'anim': 4, 'cor': '#fef3c7'},
    {'id': 'panteao',     'nome': 'Panteão',     'de': 900, 'ate': None, 'anim': 4, 'cor': '#e879f9'},
]
ROMANOS = ('I', 'II', 'III')


def _limites_sub(p):
    """Níveis em que começa o subnível I, II e III da patente."""
    if p['ate'] is None:
        return [p['de'], p['de'] + 50, p['de'] + 100]        # Panteão: 900 / 950 / 1000+
    tam = p['ate'] - p['de'] + 1
    return [p['de'], p['de'] + tam // 3, p['de'] + (tam * 2) // 3]


for _i, _p in enumerate(PATENTES):
    _p['idx'] = _i + 1
    _p['limites'] = _limites_sub(_p)


def patente_do_nivel(nivel):
    """Tudo o que a interface precisa saber da patente de um nível (o cliente só desenha)."""
    nivel = max(int(nivel or 1), 1)
    pos = 0
    for i, p in enumerate(PATENTES):
        if nivel >= p['de']:
            pos = i
    p = PATENTES[pos]
    sub = 1
    for k, inicio in enumerate(p['limites']):
        if nivel >= inicio:
            sub = k + 1
    nome_completo = f"{p['nome']} {ROMANOS[sub - 1]}"

    # Próxima vez que o ícone muda: o próximo subnível ou a próxima patente.
    if sub < 3:
        proximo = {'nivel': p['limites'][sub], 'nome': f"{p['nome']} {ROMANOS[sub]}", 'nova_patente': False}
    elif pos + 1 < len(PATENTES):
        seguinte = PATENTES[pos + 1]
        proximo = {'nivel': seguinte['de'], 'nome': f"{seguinte['nome']} I", 'nova_patente': True}
    else:
        proximo = None
    return {'id': p['id'], 'idx': p['idx'], 'nome': p['nome'], 'sub': sub, 'romano': ROMANOS[sub - 1],
            'nome_completo': nome_completo, 'de': p['de'], 'ate': p['ate'], 'anim': p['anim'], 'cor': p['cor'],
            'proximo': proximo}


def patentes_para_json():
    """A tabela inteira (galeria do inventário): `de`, `ate` e os limites dos subníveis."""
    return [{k: p[k] for k in ('id', 'idx', 'nome', 'de', 'ate', 'anim', 'cor', 'limites')} for p in PATENTES]


def patente_comeca_em(nivel):
    """Nome da patente que COMEÇA exatamente neste nível (None se não começa nenhuma, ou se é a 1ª)."""
    for p in PATENTES[1:]:
        if p['de'] == nivel:
            return p['nome']
    return None


# ==========================================
# CATÁLOGO DE ITENS COM POSSE
# ==========================================
# Tipos que ocupam uma coluna do Person (ids validados também em utils.py):
TIPOS_COLUNA = {'moldura': 'moldura', 'placa': 'placa', 'nome': 'nome_estilo', 'faixa': 'banner_color'}
# Tipos guardados no JSON `Person.equipados` (um slot por tipo):
TIPOS_JSON = ('efeito_avatar', 'efeito_perfil', 'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota')
TIPOS_EQUIPAVEIS = tuple(TIPOS_COLUNA) + TIPOS_JSON
ROTULO_TIPO = {
    'badge': 'Insígnia', 'moldura': 'Moldura', 'placa': 'Placa', 'nome': 'Estilo de nome', 'faixa': 'Faixa do perfil',
    'efeito_avatar': 'Efeito de avatar', 'efeito_perfil': 'Efeito de perfil', 'efeito_fala': 'Efeito de fala',
    'efeito_radar': 'Efeito do radar', 'efeito_chat': 'Efeito do chat', 'som_call': 'Som de entrada', 'pin_nota': 'Pin de nota',
    'efeito_servidor': 'Efeito de servidor',
    'pacote': 'Pacote de tema',
}

CATALOGO = {}   # item_id -> descritor


def _item(tipo, id_, nome, desc, tema=None, raridade='lendario', **extra):
    CATALOGO[f'{tipo}:{id_}'] = {'id': f'{tipo}:{id_}', 'tipo': tipo, 'valor': id_, 'nome': nome, 'desc': desc,
                                 'tema': tema, 'raridade': raridade, 'exclusivo': True, **extra}


# ---- Insígnias (aparecem no cartão de perfil, ao lado do nome) ----
# A ordem aqui é a ordem em que aparecem no cartão. Regras de quem recebe cada uma:
#   criador / coder / so_nos  -> manual (LABORATORIO abaixo ou conceder_item.py)
#   alpha_tester              -> lista de pessoas (ALPHA_NOMES, concedida por atualizar_banco.py / conceder_item.py)
#   beta_tester               -> TODO MUNDO (o app inteiro está no beta): garantir_insignias_automaticas()
#   bazinga                   -> quem é membro do servidor Bazinga (id em config_app 'servidor_bazinga_id')
_item('badge', 'criador', 'Criador', 'Quem construiu o Panteão do zero, tijolo por tijolo.', raridade='unico')
_item('badge', 'alpha_tester', 'Alpha Tester', 'Esteve aqui antes de todo mundo e viu o Panteão nascer.', raridade='unico')
_item('badge', 'beta_tester', 'Beta Tester', 'Está no beta. Cada bug achado acorda a Medusa.', raridade='lendario')
_item('badge', 'bazinga', 'BAZINGA', 'on top!', raridade='lendario')
_item('badge', 'coder', 'Coder', 'Mexeu no código por baixo do capô.', raridade='unico')
_item('badge', 'so_nos', 'Só nós', 'Uma sarça que arde e não se consome. Só quem começou isso tem.', raridade='unico', tema='fusao')

# ---- Laboratório: itens do tema Gogeta ----
_item('moldura', 'gogeta', 'Aura Dourada', 'Anel de ki dourado com chamas subindo.', 'gogeta')
_item('placa', 'gogeta', 'Em Chamas', 'A placa pega fogo: brasas sobem atrás do seu nome.', 'gogeta')
_item('nome', 'gogeta', 'Super Saiyajin', 'Ouro e laranja pulsando, com um clarão de energia.', 'gogeta')
_item('faixa', 'gogeta', 'Aura Saiyajin', 'Energia dourada subindo pela faixa do perfil.', 'gogeta')
_item('efeito_avatar', 'gogeta', 'Aura Super Saiyajin', 'Uma aura de chamas douradas atrás da sua foto.', 'gogeta')
_item('efeito_perfil', 'gogeta', 'Poeira Cósmica e Punição de Alma', 'Poeira de ki dourada sobe pelo cartão e, de vez em quando, partículas giram até formar a bolha colorida da Punição de Alma, que estoura.', 'gogeta')
_item('efeito_fala', 'gogeta', 'Ki ao Falar', 'Quando você fala na call, o ki explode em volta da sua foto.', 'gogeta')
_item('efeito_radar', 'gogeta', 'Ondas de Ki', 'As ondas do seu radar viram ondas de energia dourada.', 'gogeta')
_item('efeito_chat', 'gogeta', 'Ki no Teclado', 'A barra de mensagem brilha enquanto você digita e solta faíscas ao enviar.', 'gogeta')
_item('som_call', 'gogeta', 'Teleporte', 'Um som de teletransporte toca quando você entra numa call.', 'gogeta')
_item('pin_nota', 'gogeta', 'Esfera de Estrelas', 'Suas notas no mapa viram uma esfera laranja de estrelas.', 'gogeta')

# ---- Laboratório: itens do tema Sasuke ----
_item('moldura', 'sasuke', 'Sharingan', 'Anel vermelho de Sharingan com três tomoe, pulsando.', 'sasuke')
_item('placa', 'sasuke', 'Cinzas Roxas', 'Cinza e poeira subindo, com um brilho roxo por trás.', 'sasuke')
_item('nome', 'sasuke', 'Mangekyō', 'Roxo e preto com um tremor vermelho de Sharingan.', 'sasuke')
_item('faixa', 'sasuke', 'Tempestade Roxa', 'Nuvens roxas e relâmpagos na faixa do perfil.', 'sasuke')
_item('efeito_avatar', 'sasuke', 'Olho Brilhante', 'O Sharingan brilha em vermelho de tempos em tempos e volta ao normal.', 'sasuke')
_item('efeito_perfil', 'sasuke', 'Raios e Amaterasu', 'Raios caindo pelo cartão e uma chama negra de Amaterasu que sobe de leve da base e some.', 'sasuke')
_item('efeito_fala', 'sasuke', 'Chidori ao Falar', 'Quando você fala na call, relâmpagos estalam em volta da sua foto.', 'sasuke')
_item('efeito_radar', 'sasuke', 'Ondas Roxas', 'As ondas do seu radar viram ondas roxas com um estalo de raio.', 'sasuke')
_item('efeito_chat', 'sasuke', 'Raio no Teclado', 'A barra de mensagem crepita enquanto você digita e solta um raio ao enviar.', 'sasuke')
_item('som_call', 'sasuke', 'Sharingan', 'O som do Sharingan despertando toca quando você entra numa call.', 'sasuke')
_item('pin_nota', 'sasuke', 'Kunai Roxa', 'Suas notas no mapa viram uma kunai roxa.', 'sasuke')

# ---- Laboratório: itens do tema Fusão (só nós dois) ----
_item('moldura', 'fusao', 'Fusão', 'Laranja e roxo girando juntos num anel só.', 'fusao')
_item('placa', 'fusao', 'Duas Chamas', 'Uma chama laranja e uma roxa disputando a placa.', 'fusao')
_item('nome', 'fusao', 'Fusão', 'O nome muda do laranja pro roxo e volta.', 'fusao')
_item('faixa', 'fusao', 'Fusão', 'Chamas laranja e roxa se misturando na faixa.', 'fusao')

# ---- LOJA (Armazém) ----
# Tabela central de preços em DRC por raridade e tipo. É a ÚNICA fonte: item da loja usa `_item_loja`, que lê daqui.
# Calibrada com `python testes/calibrar_precos.py` (conta em cima de quanto cada perfil de uso ganha por dia). Premissas: os 500 DRC
# iniciais pagam 1 item de nome/placa no 1º dia; o 1º pacote leva ~1 semana pra quem joga normal e ~1 mês pra quem entra pouco;
# o nível "épico" é o premium (meses). MUDOU o ganho de DRC (utils.py) ou um preço aqui? Rode o script de novo.
# Raridades (da mais comum à mais rara). `ordem` serve pra ordenar e pra decidir a raridade de um pacote.
RARIDADES = [
    {'id': 'comum', 'nome': 'Comum', 'cor': '#9aa3b2'},       # cor lisa, sem animação
    {'id': 'raro', 'nome': 'Raro', 'cor': '#4a90e2'},         # efeito sutil / animação leve
    {'id': 'epico', 'nome': 'Épico', 'cor': '#a855f7'},       # animação complexa, temas com efeitos
    {'id': 'lendario', 'nome': 'Lendário', 'cor': '#f5b82e'},  # efeito em tela cheia e edições limitadas
]
ORDEM_RARIDADE = {r['id']: i for i, r in enumerate(RARIDADES)}
PRECOS = {
    'comum': {'nome': 120, 'placa': 120, 'faixa': 150, 'moldura': 180},
    'raro':  {'nome': 350, 'placa': 350, 'faixa': 450, 'moldura': 550},
    'epico': {'nome': 600, 'placa': 600, 'faixa': 750, 'moldura': 900,
              # temas "premium" (com efeitos): cada slot de efeito tem o seu preço
              'efeito_avatar': 450, 'efeito_perfil': 700, 'efeito_fala': 300, 'efeito_radar': 250,
              'efeito_chat': 300, 'som_call': 200, 'pin_nota': 250, 'efeito_servidor': 500},
    'lendario': {'moldura': 1200, 'nome': 800, 'placa': 800, 'faixa': 1000,
                 'efeito_avatar': 700, 'efeito_perfil': 900, 'efeito_fala': 400, 'efeito_radar': 350,
                 'efeito_chat': 400, 'som_call': 300, 'pin_nota': 350, 'efeito_servidor': 700},
}
DESCONTO_PACOTE = 0.30        # o pacote custa a soma dos 4 itens menos isto (arredondado pra múltiplo de 50)


def _item_loja(tipo, id_, nome, desc, tema, raridade='raro', animado=True):
    """Item à venda no Armazém: o preço vem de PRECOS (por raridade e tipo). Item sem `preco` nunca é vendido (laboratório, insígnias).
    `animado=False` = estático (aparece no filtro "Sem animação")."""
    _item(tipo, id_, nome, desc, tema, raridade, preco=PRECOS[raridade][tipo], animado=animado)


def _pacote_loja(tema, nome, desc):
    """Pacote de tema: o preço só é calculado depois que os itens existem (`recalcular_pacotes`)."""
    _item('pacote', tema, nome, desc, tema, 'epico', preco=None, pacote_loja=True)


# ---- tema Relojoaria (evoca relógio de bolso e engrenagens; tudo CSS, arte própria) ----
_item_loja('moldura', 'relojoaria', 'Relógio de Bolso', 'Um relógio de bolso de latão: a tampa abre, a borda some por um instante e tudo volta a fechar.', 'relojoaria')
_item_loja('nome', 'relojoaria', 'Tique-Taque', 'O nome brilha em latão e avança aos "tiques", como o ponteiro dos segundos.', 'relojoaria')
_item_loja('placa', 'relojoaria', 'Engrenagens', 'Dentes de engrenagem girando devagar atrás do seu nome.', 'relojoaria')
_item_loja('faixa', 'relojoaria', 'Mecanismo', 'O interior de um relógio: anéis de latão e um ponteiro varrendo a faixa.', 'relojoaria')

# ---- tema Dualidade (azul e vermelho se encontram, viram roxo e explodem) ----
_item_loja('moldura', 'dualidade', 'Vazio Roxo', 'Um arco azul e um vermelho se aproximam, viram roxo e explodem.', 'dualidade')
_item_loja('nome', 'dualidade', 'Azul e Vermelho', 'O nome vai de azul a vermelho e, no meio, clareia em roxo.', 'dualidade')
_item_loja('placa', 'dualidade', 'Convergência', 'Uma luz azul e uma vermelha caminham até o centro da placa e se fundem.', 'dualidade')
_item_loja('faixa', 'dualidade', 'Colapso', 'Duas esferas, azul e vermelha, se juntam na faixa e estouram em roxo.', 'dualidade')

# ---- tema Cubos (mundo de blocos: evoca jogos de construção em cubos; arte própria) ----
_item_loja('moldura', 'cubos', 'Bloco de Grama', 'Um anel de blocos de grama e terra que avança aos pulinhos, como um mundo feito de cubos.', 'cubos')
_item_loja('nome', 'cubos', 'Pixelado', 'As letras trocam de cor em blocos: verde, musgo e terra.', 'cubos')
_item_loja('placa', 'cubos', 'Terreno', 'Uma faixa de grama sobre terra quadriculada, andando devagar atrás do seu nome.', 'cubos')
_item_loja('faixa', 'cubos', 'Mundo de Blocos', 'Céu azul, nuvens quadradas passando e um chão de grama e terra.', 'cubos')

# ---- tema Batida (música) ----
_item_loja('moldura', 'batida', 'Equalizador', 'Barras de equalizador em volta da foto, pulsando no ritmo, uma cor de cada vez.', 'batida')
_item_loja('nome', 'batida', 'Refrão', 'O nome troca de cor e pulsa como o refrão de uma música.', 'batida')
_item_loja('placa', 'batida', 'Pista de Dança', 'Colunas de equalizador subindo e descendo atrás do seu nome.', 'batida')
_item_loja('faixa', 'batida', 'Vinil', 'Um disco de vinil na faixa, com o brilho girando sobre os sulcos.', 'batida')

# ---- tema Quadra (esporte de quadra: evoca animes e jogos de vôlei, basquete e futsal) ----
_item_loja('moldura', 'quadra', 'Bola em Jogo', 'Uma bola orbita o seu avatar sem parar, sobre uma linha de quadra.', 'quadra')
_item_loja('nome', 'quadra', 'Saque', 'O nome pega fogo no saque: branco, laranja e um clarão de impacto.', 'quadra')
_item_loja('placa', 'quadra', 'Rede', 'Uma rede esticada atrás do seu nome, balançando de leve.', 'quadra')
_item_loja('faixa', 'quadra', 'Quadra Cheia', 'Piso de quadra com as linhas brancas e uma bola quicando de ponta a ponta.', 'quadra')

# ---- tema Mira (jogos de tiro tático e de herói: evoca mira, radar e mapa tático) ----
_item_loja('moldura', 'mira', 'Mira Travada', 'Uma mira fecha em volta do avatar, trava e pisca em vermelho.', 'mira')
_item_loja('nome', 'mira', 'Tático', 'Letras de painel tático, com uma luz de varredura que passa por elas.', 'mira')
_item_loja('placa', 'mira', 'Mapa Tático', 'Grade de mapa tático com um ponto vermelho pulsando.', 'mira')
_item_loja('faixa', 'mira', 'Radar', 'Um radar varre a faixa, com anéis, grade e um alvo piscando.', 'mira')

# ---- tema Mangá (anime genérico: página em preto e branco com um toque de vermelho) ----
_item_loja('moldura', 'manga', 'Traço de Tinta', 'Um traço de tinta desenha o anel em volta da foto e depois se apaga.', 'manga')
_item_loja('nome', 'manga', 'Onomatopeia', 'Letras grossas de quadrinho, com contorno e sombra vermelha que treme.', 'manga')
_item_loja('placa', 'manga', 'Retícula', 'Retícula de página de mangá, em pontinhos, com uma faixa vermelha.', 'manga')
_item_loja('faixa', 'manga', 'Página de Mangá', 'Linhas de velocidade saindo de um clarão vermelho, em preto e branco.', 'manga')

# ---- tema Básicos (comum: cor lisa, sem animação; sem pacote nem slide no carrossel) ----
for _tipo, _id, _nome, _desc in (
        ('moldura', 'liso_azul', 'Anel Azul', 'Um anel azul liso em volta da foto.'), ('moldura', 'liso_rosa', 'Anel Rosa', 'Um anel rosa liso em volta da foto.'),
        ('nome', 'tinta_verde', 'Tinta Verde', 'O nome em verde liso.'), ('nome', 'tinta_rosa', 'Tinta Rosa', 'O nome em rosa liso.'),
        ('placa', 'chapa_cinza', 'Chapa Cinza', 'Uma barra cinza lisa atrás do nome.'), ('placa', 'chapa_azul', 'Chapa Azul', 'Uma barra azul lisa atrás do nome.'),
        ('faixa', 'degrade_mar', 'Degradê Mar', 'Um degradê parado do azul ao verde-água.'), ('faixa', 'degrade_por', 'Degradê Pôr do Sol', 'Um degradê parado do laranja ao roxo.')):
    _item_loja(_tipo, _id, _nome, _desc, 'basicos', 'comum', animado=False)

# ---- temas PREMIUM (épicos, com um item de cada slot de efeito; o de perfil é lendário). Cada um: 4 visuais + 7 efeitos + efeito de servidor. ----
def _tema_premium(tema, itens, raridade='epico'):
    for tipo, nome, desc, *resto in itens:
        _item_loja(tipo, tema, nome, desc, tema, resto[0] if resto else raridade)


_tema_premium('cyber', [
    ('moldura', 'Anel Cibernético', 'Scanlines ciano e rosa giram em volta da foto e o anel falha de vez em quando.'),
    ('nome', 'Glitch Neon', 'Letras de terminal em ciano e rosa, com um tremor de sinal perdido.'),
    ('placa', 'Letreiro Holográfico', 'Um letreiro de neon escuro com uma luz de varredura passando.'),
    ('faixa', 'Skyline Noturna', 'Prédios com janelas acesas, chuva fina e neon rosa no horizonte.'),
    ('efeito_avatar', 'Energia Estática', 'Faíscas elétricas ciano e rosa estalam em volta da foto.'),
    ('efeito_perfil', 'Chuva de Dados', 'Colunas de dados caem pelo cartão inteiro, em ciano e rosa.', 'lendario'),
    ('efeito_fala', 'Estática de Rádio', 'Quando você fala na call, o card chia em ciano e rosa como um rádio mal sintonizado.'),
    ('efeito_radar', 'Pulso Digital', 'As ondas do seu radar viram pulsos tracejados de ciano.'),
    ('efeito_chat', 'Terminal', 'A barra de mensagem acende em ciano ao digitar e solta bits ao enviar.'),
    ('som_call', 'Sistema Online', 'Dois bipes subindo e uma varredura: "sistema online" ao entrar na call.'),
    ('pin_nota', 'Holograma', 'Suas notas no mapa viram um holograma ciano com linhas de varredura.'),
    ('efeito_servidor', 'Servidor Neon', 'O ícone do servidor alterna entre ciano e rosa (barra, cabeçalho e mapa).'),
])
_tema_premium('eldoria', [
    ('moldura', 'Coroa de Carvalho', 'Folhas de carvalho e fios de ouro numa coroa que gira devagar em volta da foto.'),
    ('nome', 'Serifa Dourada', 'Letras serifadas com um brilho de ouro que passa devagar.'),
    ('placa', 'Pergaminho', 'Pergaminho escuro de bordas queimadas, com runas que brilham e apagam.'),
    ('faixa', 'Floresta Encantada', 'Árvores na noite, uma lua rúnica e vaga-lumes à deriva.'),
    ('efeito_avatar', 'Aura Élfica', 'Um halo dourado e verde, com vaga-lumes orbitando a foto.'),
    ('efeito_perfil', 'Poeira Mágica', 'Partículas de ouro e esmeralda sobem pelo cartão inteiro.', 'lendario'),
    ('efeito_fala', 'Anel Rúnico', 'Quando você fala na call, anéis dourados se expandem em volta do avatar.'),
    ('efeito_radar', 'Ondas Rúnicas', 'As ondas do seu radar viram anéis rúnicos dourados com brilho esmeralda.'),
    ('efeito_chat', 'Escrita Mágica', 'A barra de mensagem brilha em dourado e solta partículas ao enviar.'),
    ('som_call', 'Chamado do Cristal', 'Uma harpa e um brilho de cristal ao entrar na call.'),
    ('pin_nota', 'Cristal Mágico', 'Suas notas no mapa viram um cristal esmeralda.'),
    ('efeito_servidor', 'Servidor Encantado', 'O ícone do servidor pulsa em ouro e esmeralda (barra, cabeçalho e mapa).'),
])
_tema_premium('arcade', [
    ('moldura', 'Corações de Vida', 'Blocos vermelhos de barra de vida piscam em volta da foto.'),
    ('nome', 'Pixel Arco-Íris', 'Letras pixeladas que passam por 8 cores, uma de cada vez.'),
    ('placa', 'Fita de Fliperama', 'Uma fita roxa de fliperama com pastilhas amarelas correndo.'),
    ('faixa', 'Fase 1', 'Céu roxo de pixels, tijolos no chão e moedas flutuando.'),
    ('efeito_avatar', 'Moedas Girando', 'Moedas de pixel giram em volta da foto, em passos.'),
    ('efeito_perfil', 'Chuva de Pixels', 'Pixels coloridos caem pelo cartão inteiro, em passos.', 'lendario'),
    ('efeito_fala', 'Barra de Energia', 'Quando você fala na call, o card pisca em cores de fliperama.'),
    ('efeito_radar', 'Varredura em Pixels', 'As ondas do seu radar viram anéis pontilhados em verde, em passos.'),
    ('efeito_chat', 'Coração Digitando', 'A barra de mensagem pisca em rosa ao digitar e solta corações de pixel ao enviar.'),
    ('som_call', 'Moeda', 'O "plim" de uma moeda coletada ao entrar na call.'),
    ('pin_nota', 'Pixel Pin', 'Suas notas no mapa viram um bloco amarelo de pixel piscando.'),
    ('efeito_servidor', 'Servidor Arcade', 'O ícone do servidor pisca em cores de fliperama (barra, cabeçalho e mapa).'),
])

# ---- JJK: três temas lendários (12 itens cada: 4 visuais, 7 efeitos e o efeito de servidor) ----
_tema_premium('gojo', [
    ('moldura', 'Infinito', 'Um anel de luz e, por fora, uma onda azul que se aproxima do avatar e nunca encosta.'),
    ('nome', 'Seis Olhos', 'Branco e azul com um brilho que corre pelas letras.'),
    ('placa', 'Venda', 'Uma faixa preta de tecido, com um brilho azul passando por trás.'),
    ('faixa', 'Vazio Ilimitado', 'Um céu preto de estrelas e linhas de luz que convergem para um centro roxo.'),
    ('efeito_avatar', 'Azul e Vermelho', 'Um orbe azul e um vermelho giram em volta da foto, se juntam num orbe roxo (o Vazio Roxo) e ele estoura.'),
    ('efeito_perfil', 'Expansão de Domínio: Vazio Ilimitado', 'Uma aura azul se expande e o cartão inteiro vira o Vazio Ilimitado: nebulosas, estrelas, linhas de luz, o anel aceso e seis olhos humanos abrindo em volta. Some, espera uns 4 segundos e recomeça.'),
    ('efeito_fala', 'Infinito ao Falar', 'Quando você fala na call, ondas azuis se afastam do avatar sem nunca encostar nele.'),
    ('efeito_radar', 'Ondas do Infinito', 'As ondas do seu radar viram anéis de luz azul e branca.'),
    ('efeito_chat', 'Azul', 'A barra de mensagem brilha em azul ao digitar e solta um orbe ao enviar.'),
    ('som_call', 'Expansão de Domínio', 'O som da expansão de domínio do Gojo ao entrar na call.'),
    ('pin_nota', 'Roxo Oco', 'Suas notas no mapa viram um orbe roxo girando.'),
    ('efeito_servidor', 'Servidor Infinito', 'O ícone do servidor ganha um brilho azul e branco que respira (barra, cabeçalho e mapa).'),
], 'lendario')
_tema_premium('sukuna', [
    ('moldura', 'Aura Maldita', 'Um anel vermelho e, por fora, uma aura que se expande sem parar.'),
    ('nome', 'Nome em Brasa', 'O seu nome pega fogo: chamas sobem uma vez por baixo das letras e o nome fica vermelho e amarelo por 8 segundos, de tempos em tempos.'),
    ('placa', 'Cortes', 'Uma barra escura riscada por cortes brancos que aparecem de repente.'),
    ('faixa', 'Santuário Malevolente', 'Um santuário de silhueta preta sob uma lua vermelha, com cinzas e cortes.'),
    ('efeito_avatar', 'Marcas Malditas', 'Brasas e um anel vermelho pulsando em volta da foto.'),
    ('efeito_perfil', 'Expansão de Domínio: Santuário Malevolente', 'A aura vermelha se expande, o cartão fica em brasa, as marcas do rosto dele aparecem e somem e montes de cortes pretos riscam tudo, em rajadas. Some, espera uns 4 segundos e recomeça.'),
    ('efeito_fala', 'Aura ao Falar', 'Quando você fala na call, a aura vermelha se expande em volta do avatar.'),
    ('efeito_radar', 'Ondas Malditas', 'As ondas do seu radar viram anéis vermelhos tracejados.'),
    ('efeito_chat', 'Corte', 'A barra de mensagem pulsa em vermelho ao digitar e leva um corte ao enviar.'),
    ('som_call', 'Santuário', 'O som da expansão de domínio do Sukuna ao entrar na call.'),
    ('pin_nota', 'Dedo Maldito', 'Suas notas no mapa viram um orbe vermelho rachado.'),
    ('efeito_servidor', 'Servidor Malevolente', 'O ícone do servidor pulsa em vermelho (barra, cabeçalho e mapa).'),
], 'lendario')
_tema_premium('mahoraga', [
    ('moldura', 'Roda Divina', 'Uma roda de oito encaixes dourados que gira um encaixe por vez.'),
    ('nome', 'General Divino', 'Ouro e branco que piscam a cada encaixe da roda.'),
    ('placa', 'Adaptação', 'Pedra escura com uma régua de encaixes dourados andando aos passos.'),
    ('faixa', 'A Roda Gira', 'O timão da Roda Divina, dourado e brilhando: gira um pouco, estala e para duro, sobre um fundo de pedra.'),
    ('efeito_avatar', 'Halo da Roda', 'Uma roda de oito raios gira aos passos em volta da foto.'),
    ('efeito_perfil', 'Adaptação', 'O timão da Roda Divina aparece no topo do cartão, brilha, gira 45° de cada vez e para duro; no fim o cartão pulsa em dourado: adaptou.'),
    ('efeito_fala', 'Adaptando', 'Quando você fala na call, a moldura pisca em ouro, aos passos.'),
    ('efeito_radar', 'Ondas Divinas', 'As ondas do seu radar viram anéis dourados pontilhados, que avançam aos passos.'),
    ('efeito_chat', 'Encaixe', 'A barra de mensagem brilha em ouro ao digitar e solta losangos dourados ao enviar.'),
    ('som_call', 'Roda Girando', 'O som da roda do Mahoraga girando, encaixe por encaixe, ao entrar na call.'),
    ('pin_nota', 'Roda', 'Suas notas no mapa viram uma roda dourada.'),
    ('efeito_servidor', 'Servidor Divino', 'O ícone do servidor pisca em ouro, aos passos (barra, cabeçalho e mapa).'),
], 'lendario')

# ---- EDIÇÕES LIMITADAS (tema 'edicao': sem chip nem pacote; ficam numa prateleira própria) ----
# `limitado` = {'estoque': N | None, 'ate': datetime | None}. Estoque acaba quando N pessoas compraram (tabela loja_estoque,
# atômico); prazo acaba quando `ate` passa (horário de Brasília, como o resto do app). Item encerrado/esgotado continua
# aparecendo (pra quem perdeu ver o que perdeu), mas ninguém compra; quem comprou fica com ele pra sempre.
_item('moldura', 'pioneiro', 'Pioneiro', 'Uma coroa de louros dourados em volta da foto, brilhando devagar. Só quem estava aqui no começo: sai do Armazém no fim de 2026 e nunca mais volta.',
      'edicao', 'lendario', preco=1500, limitado={'estoque': None, 'ate': datetime(2026, 12, 31, 23, 59, 59)})
_item('placa', 'lote_um', 'Lote 001', 'Chapa de metal escovado com rebites e um filete dourado. Só 100 unidades existem.',
      'edicao', 'lendario', preco=900, limitado={'estoque': 100, 'ate': None})
_item('faixa', 'eclipse', 'Eclipse', 'Um sol negro com a coroa em chamas atravessando a faixa. Só 150 unidades existem.',
      'edicao', 'lendario', preco=1100, limitado={'estoque': 150, 'ate': None})

# ---- COLEÇÃO: comprar itens do Armazém (qualquer um, fora os pacotes) desbloqueia prêmios que NÃO se compram ----
# `meta` = quantos itens avulsos a pessoa precisa ter comprado. Um pacote entrega 4 de uma vez, então o 1º prêmio sai com o 1º pacote.
_item('placa', 'colecionador', 'Colecionador', 'Bronze polido com estrelinhas: o prêmio de quem já tem uma estante cheia.', 'colecao', 'epico')
_item('moldura', 'curador', 'Curador', 'Um anel de prata com estrelas orbitando devagar: quem cuida de um acervo de verdade.', 'colecao', 'epico')
_item('nome', 'acervo', 'Acervo', 'Prata e ouro correm pelas letras, com um brilho de vitrine de museu.', 'colecao', 'epico')
COLECOES = [
    {'id': 'colecao4', 'meta': 4, 'item_id': 'placa:colecionador'},
    {'id': 'colecao12', 'meta': 12, 'item_id': 'moldura:curador'},
    {'id': 'colecao24', 'meta': 24, 'item_id': 'nome:acervo'},
]

# ---- Efeito de servidor: o DONO aplica a um servidor dele (Server.efeito); todo membro vê no ícone da barra, no
# cabeçalho e no pino do mapa. Não entra nos pacotes (não é um slot da pessoa, é do servidor). ----
_item('efeito_servidor', 'gogeta', 'Chamas do Servidor', 'O ícone do servidor ganha uma aura de chamas douradas (barra, cabeçalho e mapa).', 'gogeta')
_item('efeito_servidor', 'sasuke', 'Tempestade do Servidor', 'O ícone do servidor crepita com relâmpagos roxos (barra, cabeçalho e mapa).', 'sasuke')
_item('efeito_servidor', 'fusao', 'Fusão do Servidor', 'Laranja e roxo disputando o ícone do servidor (barra, cabeçalho e mapa).', 'fusao')

# ---- Pacotes (equipam o tema inteiro de uma vez; o conteúdo está em PACOTES) ----
_item('pacote', 'gogeta', 'Gogeta completo', 'Equipa tudo do tema Gogeta de uma vez.', 'gogeta')
_item('pacote', 'sasuke', 'Sasuke completo', 'Equipa tudo do tema Sasuke de uma vez.', 'sasuke')
_item('pacote', 'fusao', 'Fusão completa', 'Equipa a moldura, a placa, o nome e a faixa da Fusão.', 'fusao')
# Pacotes da loja: o preço é calculado (soma dos itens menos DESCONTO_PACOTE), ver `recalcular_pacotes`.
_pacote_loja('relojoaria', 'Pacote Relojoaria', 'Moldura, nome, placa e faixa da Relojoaria, equipados de uma vez.')
_pacote_loja('dualidade', 'Pacote Dualidade', 'Moldura, nome, placa e faixa da Dualidade, equipados de uma vez.')
_pacote_loja('cubos', 'Pacote Cubos', 'Moldura, nome, placa e faixa do mundo de Cubos, equipados de uma vez.')
_pacote_loja('batida', 'Pacote Batida', 'Moldura, nome, placa e faixa da Batida, equipados de uma vez.')
_pacote_loja('quadra', 'Pacote Quadra', 'Moldura, nome, placa e faixa da Quadra, equipados de uma vez.')
_pacote_loja('mira', 'Pacote Mira', 'Moldura, nome, placa e faixa da Mira, equipados de uma vez.')
_pacote_loja('manga', 'Pacote Mangá', 'Moldura, nome, placa e faixa do Mangá, equipados de uma vez.')
_pacote_loja('cyber', 'Pacote Cyber Neon', 'O tema Cyber Neon completo: 4 visuais e 7 efeitos (avatar, perfil, fala, radar, chat, som e pin), equipados de uma vez.')
_pacote_loja('eldoria', 'Pacote Eldoria', 'O tema Eldoria completo: 4 visuais e 7 efeitos (avatar, perfil, fala, radar, chat, som e pin), equipados de uma vez.')
_pacote_loja('gojo', 'Pacote Gojo', 'O tema Gojo completo: 4 visuais e 7 efeitos (avatar, perfil, fala, radar, chat, som e pin), equipados de uma vez.')
_pacote_loja('sukuna', 'Pacote Sukuna', 'O tema Sukuna completo: 4 visuais e 7 efeitos (avatar, perfil, fala, radar, chat, som e pin), equipados de uma vez.')
_pacote_loja('mahoraga', 'Pacote Mahoraga', 'O tema Mahoraga completo: 4 visuais e 7 efeitos (avatar, perfil, fala, radar, chat, som e pin), equipados de uma vez.')
_pacote_loja('jjk', 'Combo JJK: Gojo × Sukuna', 'O melhor dos dois lados no mesmo perfil: o Infinito e o som do Gojo, a aura, o nome em chamas e o domínio do Sukuna. Equipa 11 itens misturados.')
_pacote_loja('arcade', 'Pacote Arcade 8-bit', 'O tema Arcade 8-bit completo: 4 visuais e 7 efeitos (avatar, perfil, fala, radar, chat, som e pin), equipados de uma vez.')


def _pacote(tema):
    """tipo -> id de cada item do tema (só os equipáveis)."""
    escolhas = {}
    for d in CATALOGO.values():
        # o 1º item de cada tipo é o "principal" do tema; os extras são opcionais
        if d['tema'] == tema and d['tipo'] in TIPOS_EQUIPAVEIS:
            escolhas.setdefault(d['tipo'], d['valor'])
    return escolhas


# Calculado depois que todos os itens existem. Se um tipo novo entrar no catálogo, o pacote já o pega.
PACOTES = {}


# Pacotes montados à mão (misturam temas); o resto sai sozinho do 1º item de cada tipo do tema.
PACOTES_FIXOS = {
    'jjk': {'moldura': 'gojo', 'nome': 'sukuna', 'placa': 'gojo', 'faixa': 'sukuna', 'efeito_avatar': 'gojo', 'efeito_perfil': 'sukuna',
            'efeito_fala': 'sukuna', 'efeito_radar': 'gojo', 'efeito_chat': 'sukuna', 'som_call': 'gojo', 'pin_nota': 'sukuna'},
}


def recalcular_pacotes():
    for tema in TEMAS:
        PACOTES[tema] = dict(PACOTES_FIXOS.get(tema) or _pacote(tema))
    # preço do pacote da loja = soma dos itens avulsos do tema - DESCONTO_PACOTE, em múltiplos de 50
    for d in CATALOGO.values():
        if d.get('pacote_loja'):
            entrega = {f'{t}:{v}' for t, v in PACOTES.get(d['tema'], {}).items()}
            soma = sum(i['preco'] for i in CATALOGO.values() if i['id'] in entrega and i.get('preco'))
            d['preco'] = max(50, int(round(soma * (1 - DESCONTO_PACOTE) / 50.0)) * 50)
            base = [CATALOGO[f'{t}:{PACOTES[d["tema"]][t]}'] for t in ('moldura', 'nome', 'placa', 'faixa') if t in PACOTES.get(d['tema'], {})]
            if base:
                d['raridade'] = max((i['raridade'] for i in base), key=lambda r: ORDEM_RARIDADE.get(r, 0))


recalcular_pacotes()



def ids_do_tipo(tipo):
    """Ids (sem o prefixo do tipo) dos itens EXCLUSIVOS desse tipo."""
    return tuple(d['valor'] for d in CATALOGO.values() if d['tipo'] == tipo)


def item_exclusivo(tipo, valor):
    return f'{tipo}:{valor}' in CATALOGO


def efeito_servidor_valido(valor):
    """O id do efeito de servidor se o catálogo conhece; senão None (nunca chega um id solto no class="" de ninguém)."""
    return valor if valor and item_exclusivo('efeito_servidor', valor) else None


def descritor(item_id):
    return CATALOGO.get(item_id)


# ==========================================
# O QUE CADA PESSOA RECEBE NO LABORATÓRIO
# ------------------------------------------------------------
# Identidade resolvida UMA VEZ, na hora de conceder (por @username -> person_id), e dali
# em diante a posse é por id: se a pessoa trocar o @, nada muda; se outra pessoa pegar o
# @ antigo, não herda nada. Por isso conceder é um ato explícito (`atualizar_banco.py` ou
# `conceder_item.py`), nunca algo que roda sozinho no boot.
# ==========================================
def _itens_do_tema(tema):
    return [i for i, d in CATALOGO.items() if d['tema'] == tema and d['tipo'] != 'badge']


LABORATORIO = {
    'aquele.sales': (['badge:criador', 'badge:alpha_tester', 'badge:beta_tester', 'badge:coder', 'badge:so_nos']
                     + _itens_do_tema('gogeta') + _itens_do_tema('fusao')),
    'filippo.chiarion': (['badge:criador', 'badge:alpha_tester', 'badge:beta_tester', 'badge:coder', 'badge:so_nos']
                         + _itens_do_tema('sasuke') + _itens_do_tema('fusao')),
}


# ==========================================
# INSÍGNIAS POR REGRA (não precisam de concessão manual)
# ==========================================
BADGE_BETA = 'badge:beta_tester'
BADGE_BAZINGA = 'badge:bazinga'
ALPHA_NOMES = ['filippo', 'fernando albernaz', 'gabriel alves santana', 'gabriel silva', 'arthur neves fiorotti', 'juarez']
_cache_bazinga = {}


def _normalizar(texto):
    import unicodedata
    t = unicodedata.normalize('NFKD', texto or '')
    return ' '.join(''.join(c for c in t if not unicodedata.combining(c)).lower().split())


def id_servidor_bazinga():
    """Id do servidor Bazinga (config_app 'servidor_bazinga_id', ou a env BAZINGA_SERVER_ID). Por ID, nunca por nome:
    qualquer um pode criar um servidor chamado "Bazinga". None se ainda não foi definido."""
    import os
    if 'id' in _cache_bazinga:
        return _cache_bazinga['id']
    from .models import ConfigApp
    valor = os.environ.get('BAZINGA_SERVER_ID')
    if not valor:
        c = ConfigApp.query.get('servidor_bazinga_id')
        valor = c.valor if c else None
    if valor and str(valor).isdigit():
        _cache_bazinga['id'] = int(valor)   # só guarda quando existe: se ainda não foi definido, olha de novo da próxima vez
        return _cache_bazinga['id']
    return None


def garantir_insignias_automaticas(pessoa, posses):
    """Beta pra todo mundo; BAZINGA pra quem está no servidor Bazinga. Mexe em `posses` e devolve True se concedeu algo
    (quem chama comita). Só consulta o servidor quando a pessoa ainda NÃO tem a insígnia."""
    mudou = False
    if BADGE_BETA not in posses and conceder_item(pessoa.id, BADGE_BETA, 'beta'):
        posses.add(BADGE_BETA); mudou = True
    if BADGE_BAZINGA not in posses:
        sid = id_servidor_bazinga()
        if sid:
            from .utils import eh_membro
            if eh_membro(pessoa, sid) and conceder_item(pessoa.id, BADGE_BAZINGA, 'bazinga'):
                posses.add(BADGE_BAZINGA); mudou = True
    return mudou


def posses_com_regras(pessoa):
    """posses_da_pessoa + insígnias automáticas (1 escrita só na primeira vez de cada insígnia). Nunca quebra o /chat."""
    from .models import db
    posses = posses_da_pessoa(pessoa.id)
    try:
        if garantir_insignias_automaticas(pessoa, posses):
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'[ERRO INSIGNIAS AUTOMATICAS] {e}')
        posses = posses_da_pessoa(pessoa.id)
    return posses


def conceder_insignias_iniciais(log=print):
    """Passo único do atualizar_banco.py (idempotente): beta pra todos, define o servidor Bazinga e dá a insígnia aos
    membros, e alpha pra lista ALPHA_NOMES (por nome de exibição; avisa se não achar ou se tiver nome repetido)."""
    from sqlalchemy import func
    from .models import db, Person, Server, ConfigApp
    todas = Person.query.all()
    novos = sum(1 for p in todas if conceder_item(p.id, BADGE_BETA, 'beta'))
    log(f'✅ Beta Tester: {novos} pessoa(s) receberam agora (de {len(todas)}).')

    srv_cfg = ConfigApp.query.get('servidor_bazinga_id')
    if not (srv_cfg and srv_cfg.valor):
        srv = Server.query.filter(func.lower(Server.name) == 'bazinga').order_by(Server.id).first()
        if srv:
            db.session.add(ConfigApp(chave='servidor_bazinga_id', valor=str(srv.id)))
            db.session.flush()
            log(f'✅ Servidor Bazinga definido: id {srv.id} ("{srv.name}", dono id {srv.owner_id}). Confira se é o certo.')
    srv_cfg = ConfigApp.query.get('servidor_bazinga_id')
    if srv_cfg and srv_cfg.valor and srv_cfg.valor.isdigit():
        srv = Server.query.get(int(srv_cfg.valor))
        if srv:
            n = sum(1 for m in srv.members if conceder_item(m.id, BADGE_BAZINGA, 'bazinga'))
            log(f'✅ BAZINGA: {n} membro(s) do servidor "{srv.name}" receberam agora (de {len(srv.members)}).')
    else:
        log('ℹ️ Não achei um servidor chamado "Bazinga". Defina com a env BAZINGA_SERVER_ID ou insira em config_app.')

    por_nome = {}
    for p in todas:
        por_nome.setdefault(_normalizar(p.name), []).append(p)
    for nome in ALPHA_NOMES:
        achados = por_nome.get(nome, [])
        if len(achados) == 1:
            ok = conceder_item(achados[0].id, 'badge:alpha_tester', 'alpha')
            log(f'✅ Alpha Tester: {achados[0].name} (id {achados[0].id}, @{achados[0].username}) {"recebeu" if ok else "já tinha"}.')
        elif not achados:
            log(f'⚠️ Alpha Tester: não achei "{nome}". Use: python conceder_item.py <@usuario> badge:alpha_tester')
        else:
            log(f'⚠️ Alpha Tester: "{nome}" bate com {len(achados)} contas ({", ".join("@" + str(a.username) for a in achados)}). '
                f'Use conceder_item.py na certa.')
    db.session.commit()


# ==========================================
# POSSE (banco)
# ==========================================
def posses_da_pessoa(person_id):
    """Conjunto de item_id que a pessoa possui. UMA query."""
    from .models import Posse
    return {p.item_id for p in Posse.query.filter_by(person_id=person_id).all()}


def pessoa_tem(person_id, item_id, posses=None):
    if item_id not in CATALOGO:
        return True            # item livre: todo mundo tem
    if posses is None:
        posses = posses_da_pessoa(person_id)
    return item_id in posses


def conceder_item(person_id, item_id, origem='sistema'):
    """Dá o item à pessoa. Idempotente. Só faz `add` (quem chama comita)."""
    from .models import db, Posse
    if item_id not in CATALOGO:
        raise ValueError(f'Item desconhecido: {item_id}')
    if Posse.query.filter_by(person_id=person_id, item_id=item_id).first():
        return False
    db.session.add(Posse(person_id=person_id, item_id=item_id, origem=origem))
    return True


def revogar_item(person_id, item_id):
    from .models import Posse
    return Posse.query.filter_by(person_id=person_id, item_id=item_id).delete(synchronize_session=False)


def conceder_laboratorio(log=print):
    """Concede o pacote inicial do laboratório aos dois testers (por @username)."""
    from .models import db, Person
    total = 0
    for username, itens in LABORATORIO.items():
        pessoa = Person.query.filter_by(username=username).first()
        if not pessoa:
            log(f'ℹ️ Laboratório: não achei @{username} (ainda não entrou, ou mudou o @). '
                f'Use "python conceder_item.py {username} tudo" depois.')
            continue
        novos = sum(1 for i in itens if conceder_item(pessoa.id, i, 'laboratorio'))
        total += novos
        log(f'✅ Laboratório: @{username} (id {pessoa.id}) recebeu {novos} item(ns) novo(s) de {len(itens)}.')
    db.session.commit()
    return total


# ==========================================
# EQUIPADOS (JSON em Person.equipados)
# ==========================================
def equipados_da_pessoa(pessoa):
    """Dict {tipo: id} dos slots em JSON. Só devolve o que o catálogo conhece (defensivo:
    o que vai parar num class="" no navegador de todo mundo nunca vem do banco cru)."""
    bruto = getattr(pessoa, 'equipados', None)
    if not bruto:
        return {}
    try:
        dados = json.loads(bruto)
    except (TypeError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}
    return {t: v for t, v in dados.items() if t in TIPOS_JSON and isinstance(v, str) and item_exclusivo(t, v)}


def guardar_equipados(pessoa, equipados):
    limpo = {t: v for t, v in equipados.items() if t in TIPOS_JSON and v and item_exclusivo(t, v)}
    pessoa.equipados = json.dumps(limpo, separators=(',', ':')) if limpo else None


def valor_atual_do_slot(pessoa, tipo):
    """O que a pessoa tem equipado em um slot (tipo), qualquer que seja o jeito de guardar."""
    if tipo == 'faixa':
        cor = pessoa.banner_color or ''
        return cor[5:] if cor.startswith('anim:') else None
    if tipo in TIPOS_COLUNA:
        return getattr(pessoa, TIPOS_COLUNA[tipo]) or None
    return equipados_da_pessoa(pessoa).get(tipo)


def definir_slot(pessoa, tipo, valor):
    """Grava o valor no slot (None limpa). NÃO valida posse - quem chama valida."""
    if tipo == 'faixa':
        pessoa.banner_color = f'anim:{valor}' if valor else None
        if valor:
            pessoa.banner_url = None
            pessoa.banner_ajuste = None
    elif tipo in TIPOS_COLUNA:
        setattr(pessoa, TIPOS_COLUNA[tipo], valor or None)
    elif tipo in TIPOS_JSON:
        atuais = equipados_da_pessoa(pessoa)
        if valor:
            atuais[tipo] = valor
        else:
            atuais.pop(tipo, None)
        guardar_equipados(pessoa, atuais)


def badges_do_conjunto(posses):
    """Insígnias que uma pessoa mostra, na ordem do catálogo."""
    return [d['valor'] for d in CATALOGO.values() if d['tipo'] == 'badge' and d['id'] in posses]


def catalogo_para_json(posses):
    """Os itens exclusivos que a pessoa possui, com tudo que o inventário precisa."""
    return [{k: d[k] for k in ('id', 'tipo', 'valor', 'nome', 'desc', 'tema', 'raridade')}
            for d in CATALOGO.values() if d['id'] in posses]
