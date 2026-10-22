"""Log de novidades: o que aparece no pop-up do botão "Atualização disponível" (a setinha ao lado da caixa de entrada).

Como funciona: cada página carrega sabendo a última novidade que tinha (`novidade_atual()` vai no HTML). Quando o servidor sobe uma
versão nova, o botão aparece e o pop-up mostra o que é MAIS NOVO que a página aberta ("Chega nesta atualização") e, abaixo, o histórico.

Pra anunciar uma atualização: ponha uma entrada NOVA no TOPO da lista, com `id` maior que o da anterior. Texto curto, em português
de gente (nada de nome de função). Cada item: `icone` (Font Awesome sem o "fa-solid"), `titulo` e `texto`.
"""

NOVIDADES = [
    {
        'id': 33, 'data': '21/10/2026', 'titulo': 'Chamadas mais seguras',
        'itens': [
            {'icone': 'fa-shield-halved', 'titulo': 'Só quem está na call entra na call',
             'texto': 'O endereço da sua chamada agora só vai pra quem está nela, e o app só atende ligação de quem o servidor confirma. Canal de voz privado também deixou de aparecer pra quem não tem acesso.'},
            {'icone': 'fa-lock', 'titulo': 'Proteções extras no site',
             'texto': 'Cabeçalhos de segurança, conexão em tempo real só do endereço oficial e verificação dos scripts externos.'},
        ],
    },
    {
        'id': 32, 'data': '21/10/2026', 'titulo': 'Permissões por canal',
        'itens': [
            {'icone': 'fa-shield-halved', 'titulo': 'Cada canal com as suas regras', 'texto': 'Em Editar canal > Permissões do canal (ou em Configurações > Canais), escolha um cargo, ou o "Membro" que vale pra todo mundo, e libere ou negue só naquele canal: ver, escrever, publicar anúncios, falar na voz ou no palco, apagar e fixar mensagens.'},
            {'icone': 'fa-eye-slash', 'titulo': 'Canais que só alguns enxergam', 'texto': 'Quem não pode ver um canal não vê nem o nome dele (nem a categoria, se só tiver esse). Negar vence liberar, e o dono e os administradores ignoram tudo isso. Em canal privado a lista de convidados continua mandando.'},
        ],
    },
    {
        'id': 31, 'data': '19/10/2026', 'titulo': 'Cargos, categorias e mais tipos de canal nos servidores',
        'itens': [
            {'icone': 'fa-user-shield', 'titulo': 'Cargos com permissões', 'texto': 'Em Configurações do servidor > Cargos, crie cargos com cor e permissões (gerenciar canais, remover membros, apagar mensagens, ver canais privados, falar no palco...). Quem tem cargo mais alto manda nos de baixo, e o nome do membro ganha a cor do cargo. O dono continua podendo tudo.'},
            {'icone': 'fa-folder', 'titulo': 'Categorias e separadores', 'texto': 'Renomeie as categorias da lista de canais, crie novas, recolha e arraste canais entre elas. Dá pra colocar linhas separadoras, com título ou sem.'},
            {'icone': 'fa-bullhorn', 'titulo': 'Anúncios, regras, mídia e palco', 'texto': 'Novos tipos de canal: Anúncios e Regras (só lê quem não tem permissão), Mídia (só foto, vídeo e GIF), Voz com limite de pessoas e Palco (oradores e ouvintes). Cada canal pode ter um emoji próprio.'},
            {'icone': 'fa-image', 'titulo': 'Banner e boas-vindas', 'texto': 'O servidor pode ter banner no topo da lista, uma mensagem de boas-vindas mostrada uma vez a cada pessoa e um canal que abre primeiro.'},
        ],
    },
    {
        'id': 30, 'data': '19/10/2026', 'titulo': 'Arraste pra organizar servidores e conversas',
        'itens': [
            {'icone': 'fa-hand', 'titulo': 'Segure e arraste os servidores', 'texto': 'Segure o ícone de um servidor na barra lateral: ele se solta, sobe e segue o seu dedo ou o mouse enquanto os outros abrem espaço. Solte onde quiser: a ordem fica salva na sua conta, em qualquer aparelho.'},
            {'icone': 'fa-folder', 'titulo': 'Pastinhas de servidores', 'texto': 'Segure um servidor em cima de outro por uns 2 segundos (um anel vai crescendo) e os dois viram uma pasta, com nome e cor que você escolhe. Toque pra abrir e fechar; arraste um servidor pra fora da barra pra tirar da pasta. Pasta com um servidor só se desfaz.'},
            {'icone': 'fa-thumbtack', 'titulo': 'Conversas fixadas no topo', 'texto': 'Nas conversas diretas, segure e arraste uma pra cima da linha: ela fica fixada onde você pôs, mesmo chegando mensagem nova. As outras seguem por mensagem mais recente. Também dá pelo botão direito (Fixar no topo).'},
            {'icone': 'fa-keyboard', 'titulo': 'Sem mouse também', 'texto': 'Com um servidor ou conversa selecionado pelo teclado, Alt + seta pra cima ou pra baixo move; o botão direito (ou a tecla de menu) mostra Mover, Juntar numa pasta e Tirar da pasta.'},
        ],
    },
    {
        'id': 29, 'data': '19/10/2026', 'titulo': 'Responder e reagir nas notas do mapa',
        'itens': [
            {'icone': 'fa-comment-dots', 'titulo': 'Responda uma nota', 'texto': 'Chegou perto de uma nota? Abra o balão e escreva embaixo dela. As respostas aparecem em ordem e a resposta de um amigo ganha o selo de amigo. Quem deixou a nota recebe um aviso na caixa de entrada.'},
            {'icone': 'fa-face-smile', 'titulo': 'Reaja com um toque', 'texto': 'Seis reações (coração, risada, joinha, fogo, surpresa e tristeza). Só o total aparece: ninguém sabe quem reagiu.'},
            {'icone': 'fa-user-lock', 'titulo': 'Você escolhe quem responde', 'texto': 'Ao deixar ou editar uma nota, marque se respondem todos, só os seus amigos ou ninguém. No modo "só amigos" as respostas só aparecem pra você e seus amigos. Dá pra apagar qualquer resposta na sua nota e denunciar as que passarem do limite.'},
        ],
    },
    {
        'id': 28, 'data': '14/10/2026', 'titulo': 'Editar e apagar mensagens nas DMs',
        'itens': [
            {'icone': 'fa-pen', 'titulo': 'Editar mensagem na DM funciona', 'texto': 'Antes, editar uma mensagem na conversa direta dava erro. Agora você edita (duplo clique ou no lápis) e o outro lado vê o "(editada)" na hora.'},
            {'icone': 'fa-trash', 'titulo': 'Apagar mensagem na DM', 'texto': 'Só quem escreveu apaga, e a mensagem some da conversa pra vocês dois.'},
            {'icone': 'fa-face-smile', 'titulo': 'Reagir e fixar ficam só nos canais', 'texto': 'Na DM esses dois botões saíram do menu: eles nunca tiveram onde guardar a reação da conversa direta.'},
        ],
    },
    {
        'id': 27, 'data': '14/10/2026', 'titulo': 'Mais de cem temas novos no Armazém',
        'itens': [
            {'icone': 'fa-shapes', 'titulo': 'Armazém por categorias', 'texto': 'O Armazém agora se divide em Anime, Jogos, Quadrinhos, Esportes, Fofos, Sombrio, Dia a dia, Fantasia, Básicos e Datas Especiais. Clique numa categoria, ou filtre por tipo, tema, raridade e animação.'},
            {'icone': 'fa-heart', 'titulo': 'Fofos, emo, terror e dia a dia', 'texto': 'Gatinhos, docinhos, nuvens, coelhinhos e mais; Emo Noite, Coração Partido, Gótico e Vampiro; Sangue, Fantasmas, Fita VHS, Ocultismo e outros sustos; Café, Praia, Synthwave, Quadro-negro e muito mais. Cada tema tem moldura, nome, placa, faixa e efeitos próprios.'},
            {'icone': 'fa-bolt', 'titulo': 'Jogos, anime e heróis', 'texto': 'Valhalla, Neo Arena, Fortaleza, Tijolos e os reinos do Hextech; Aventura Bizarra (parar o tempo, vento dourado, areia, platina), Derby, Ego e Chama Azul; Teia, Multiverso, Gotham, Krypton, Stark, Escudo, Trovão, Wakanda e muitos outros heróis. Tudo em arte original.'},
            {'icone': 'fa-gift', 'titulo': 'Datas especiais', 'texto': 'Natal, Ano Novo, Aniversário, Dia dos Namorados, Carnaval, Páscoa, Halloween e Festa Junina, com efeitos que ocupam o cartão inteiro.'},
            {'icone': 'fa-circle', 'titulo': 'Básicos com todas as cores', 'texto': 'Todas as cores lisas, vivas, pastel e escuras, mais listras, xadrez, bolinhas, zigue-zague, quadriculado e degradês. Baratos e parados. Eles não contam para a Coleção do Armazém.'},
        ],
    },
    {
        'id': 26, 'data': '13/10/2026', 'titulo': 'Efeitos do perfil mais fáceis de escolher e o tema Simbionte',
        'itens': [
            {'icone': 'fa-wand-magic-sparkles', 'titulo': 'Efeito de avatar ao lado da moldura', 'texto': 'Em Configurações > Meu Perfil, o efeito da foto ganhou o seu quadradinho ao lado da moldura: clique e veja cada efeito que você tem rodando na sua foto antes de escolher.'},
            {'icone': 'fa-layer-group', 'titulo': 'Efeito de perfil em carrossel', 'texto': 'Os efeitos que cobrem o cartão inteiro agora são um carrossel de cartões de exemplo: passe pelos que você tem, veja o efeito em ação e equipe o que mais gostar.'},
            {'icone': 'fa-spider', 'titulo': 'Tema Simbionte no Armazém', 'texto': 'Gosma preta, olhos brancos e a aranha no peito: moldura, nome, placa, faixa e dois efeitos. No efeito de avatar, a gosma come a sua foto, mostra o símbolo e recua em tentáculos vivos.'},
        ],
    },
    {
        'id': 25, 'data': '13/10/2026', 'titulo': 'Música no Pantheon e playlist no perfil',
        'itens': [
            {'icone': 'fa-music', 'titulo': 'Música', 'texto': 'Novo botão Música na barra lateral (no celular, em Você): pesquise uma música, toque, monte a sua fila e ouça enquanto usa o app. Dá pra colar um link de música ou playlist do YouTube e do YouTube Music, e guardar as que você gosta na playlist do seu perfil. O som vem do player do YouTube, que fica sempre à vista.'},
            {'icone': 'fa-compact-disc', 'titulo': 'Playlist no perfil', 'texto': 'Em Configurações > Conexões, crie a sua playlist e cole links de músicas ou playlists do YouTube ou do YouTube Music. No seu perfil ela vira um disco que toca em sequência, com próxima e anterior, e quem abrir escolhe qual faixa ouvir. Vídeo que o dono não deixa tocar fora do YouTube é pulado.'},
        ],
    },
    {
        'id': 24, 'data': '13/10/2026', 'titulo': 'Conexões no perfil, radar no mapa e painel do Estúdio',
        'itens': [
            {'icone': 'fa-link', 'titulo': 'Conexões no perfil', 'texto': 'Em Configurações > Conexões, cole o link do seu GitHub, YouTube, Spotify, Twitch, Instagram, site ou da sua loja do Bazar e o cartão já vem pronto. Não tem edição: se mudar algo, mude na página oficial e o Pantheon atualiza. Cada cartão ganha a cara da empresa (YouTube vermelho, Amazon amarelo, LinkedIn branco...). No cartão de perfil, a setinha ao lado vira o cartão para as conexões. Prefere uma conexão por página? Ligue o carrossel em Configurações > Conexões. Spotify e YouTube viram um toca-discos que só carrega o player quando você aperta Ouvir. Pro LinkedIn, solte o PDF do seu perfil e o currículo aparece.'},
            {'icone': 'fa-satellite-dish', 'titulo': 'Radar de pessoas por perto', 'texto': 'Opcional e desligado por padrão (Configurações > Geral): de tempos em tempos o radar mostra um vulto apagado de quem está por perto, sem nome e sem lugar exato. Quem usa o Modo Fantasma nunca aparece. Também dá pra localizar um amigo no mapa pelo botão direito, ver a lista de amigos no mapa e os servidores ao seu alcance.'},
            {'icone': 'fa-chart-column', 'titulo': 'Estúdio com gráficos', 'texto': 'O painel de admin ganhou gráficos e a lista de quem usa o app. Apagar uma temporada do passe ficou rápido e confiável.'},
        ],
    },
    {
        'id': 23, 'data': '12/10/2026', 'titulo': 'Explorar servidores e efeitos novos',
        'itens': [
            {'icone': 'fa-compass', 'titulo': 'Explorar servidores', 'texto': 'No "+" da barra de servidores agora tem o Explorar: um mar de barquinhos, um por servidor (quanto maior o barco, mais gente a bordo). Veja a prévia, entre, procure por tema ou peça pra ser surpreendido. Quer aparecer lá? Donos ligam em Configurações do servidor.'},
            {'icone': 'fa-landmark', 'titulo': 'Passe da Odisseia', 'texto': 'A temporada Deuses agora é uma viagem em dez cantos, de Ítaca ao Olimpo: molduras, placas, faixas, efeitos e títulos de mitologia grega, com filtro por categoria na trilha.'},
            {'icone': 'fa-wand-magic-sparkles', 'titulo': 'Efeitos novos de perfil', 'texto': 'Novos efeitos de cartão e de avatar começam a chegar, criados no Estúdio do app.'},
        ],
    },
    {
        'id': 22, 'data': '12/10/2026', 'titulo': 'Passe de temporada, títulos e missões novas',
        'itens': [
            {'icone': 'fa-ranking-star', 'titulo': 'Passe de Batalha de temporada', 'texto': 'Agora o passe tem temporadas, com tema próprio, duas trilhas (Grátis e Premium) e prêmios nível a nível: moedas, molduras, efeitos de cartão, títulos e até temas do app. A primeira é a Temporada 1: Deuses. Veja em Battle Pass.'},
            {'icone': 'fa-signature', 'titulo': 'Títulos', 'texto': 'Ganhe títulos no passe e escolha um pra aparecer no cartão, ao lado do @ e dos pronomes. Alguns têm animação.'},
            {'icone': 'fa-list-check', 'titulo': 'Missões novas', 'texto': 'Agora são 5 diárias por dia, e as semanais você escolhe (3 entre 8). Tem muito mais tipos de missão. Mensagem repetida ou sem sentido, e reação em rajada, não contam mais.'},
            {'icone': 'fa-palette', 'titulo': 'Temas de temporada', 'texto': 'Templo e Tártaro: dois temas do app que só saem no passe. Aparecem trancados em Configurações > Aparência até você ganhar.'},
            {'icone': 'fa-landmark', 'titulo': 'Visual mais limpo e logo nova', 'texto': 'Saíram os gradientes coloridos dos títulos e barras. A logo agora é preta e dourada, chapada.'},
        ],
    },
    {
        'id': 21, 'data': '10/10/2026', 'titulo': 'Tema separado pro celular e pro computador',
        'itens': [
            {'icone': 'fa-mobile-screen', 'titulo': 'Um fundo pra cada aparelho', 'texto': 'Em Configurações > Aparência, o tema (e o papel de parede) que você escolhe vale só pro tipo de aparelho em que você está: o do computador não mexe no do celular, e o do celular não mexe no do computador. Tudo fica salvo na conta, então ao entrar de outro celular ou computador o seu fundo já está lá.'},
            {'icone': 'fa-arrows-rotate', 'titulo': 'Instalador do app do Windows', 'texto': 'Atualizar o app do Windows pelo botão "Procurar atualizações" agora instala no lugar da versão antiga e abre o app sozinho.'},
        ],
    },
    {
        'id': 20, 'data': '10/10/2026', 'titulo': 'Aviso de atualização novo, mais temas e editor na lojinha',
        'itens': [
            {'icone': 'fa-arrow-down', 'titulo': 'Este botão', 'texto': 'A faixa de "saiu uma versão nova" foi embora. Agora uma setinha aparece ao lado da caixa de entrada quando há atualização, e você escolhe a hora de atualizar.'},
            {'icone': 'fa-palette', 'titulo': 'Mais temas', 'texto': 'Dez temas novos em Configurações > Aparência (claros e escuros), cada um com a sua cor de destaque.'},
            {'icone': 'fa-wand-magic-sparkles', 'titulo': 'Tema personalizado', 'texto': 'Monte o seu: imagem de fundo do aparelho, de um link (dá pra colar o link de uma imagem do Pinterest) ou de GIF, com corte e zoom, cor de destaque, escurecimento e transparência dos painéis.'},
            {'icone': 'fa-crop-simple', 'titulo': 'Editor na lojinha do Bazar', 'texto': 'Logo, banner, fotos dos produtos e arte de anúncio agora passam pelo mesmo editor do perfil: cortar, girar, espelhar e dar zoom. Vídeo curto vira animação.'},
        ],
    },
    {
        'id': 19, 'data': '09/10/2026', 'titulo': 'Som da call, login que dura e o nome Pantheon',
        'itens': [
            {'icone': 'fa-headphones', 'titulo': 'Call com som de volta', 'texto': 'Numa call sem câmera ninguém ouvia ninguém. Corrigido: o som toca sempre, o fone desligado cala de verdade e, se o microfone falhar, o app diz o motivo.'},
            {'icone': 'fa-key', 'titulo': 'Login que dura', 'texto': 'Você entra com o Google uma vez e fica conectado, sem pedir de novo toda vez que fecha o navegador.'},
            {'icone': 'fa-bell', 'titulo': 'Notificações melhores', 'texto': 'Ícone próprio, sem aviso repetido e sem o contador de mensagens piscando.'},
            {'icone': 'fa-microphone', 'titulo': 'Menus do microfone e do fone inteiros', 'texto': 'A lista de dispositivos não fica mais cortada pela barra lateral.'},
            {'icone': 'fa-landmark', 'titulo': 'Agora é Pantheon', 'texto': 'O app mudou de nome em todo lugar.'},
        ],
    },
    {
        'id': 18, 'data': '09/10/2026', 'titulo': 'Bazar completo',
        'itens': [
            {'icone': 'fa-heart', 'titulo': 'Favoritos e ordem', 'texto': 'Siga lojas, ordene por nota, vendas, preço ou novidade e veja as lojas perto de você.'},
            {'icone': 'fa-shield-halved', 'titulo': 'Reputação e selos', 'texto': 'Selos de loja nova, confiável e verificada, e regras pra lojas novas venderem com segurança.'},
            {'icone': 'fa-truck', 'titulo': 'Frete e retirada', 'texto': 'Produto físico com frete, retirada e endereço que só as duas pontas veem e que some quando o pedido termina.'},
            {'icone': 'fa-gavel', 'titulo': 'Disputa e moderação', 'texto': 'Abra uma disputa num pedido e um administrador analisa. Também há banimento e anúncios no carrossel.'},
        ],
    },
    {
        'id': 17, 'data': '08/10/2026', 'titulo': 'Domínios do Armazém refeitos',
        'itens': [
            {'icone': 'fa-bolt', 'titulo': 'Gojo, Sukuna e Mahoraga', 'texto': 'Os três pacotes foram refeitos, com sons de entrada e domínios que aparecem com calma no cartão de perfil.'},
            {'icone': 'fa-coins', 'titulo': 'Dracmas por missão', 'texto': 'Missões diárias e semanais agora também rendem Dracmas.'},
        ],
    },
    {
        'id': 16, 'data': '08/10/2026', 'titulo': 'Armazém: filtros, raridades e temas premium',
        'itens': [
            {'icone': 'fa-filter', 'titulo': 'Filtros', 'texto': 'Filtre por tipo, tema, raridade e animação, e ordene como quiser.'},
            {'icone': 'fa-gem', 'titulo': 'Cyber Neon, Eldoria e Arcade', 'texto': 'Três temas premium com moldura, nome, placa, faixa e efeitos completos.'},
            {'icone': 'fa-user-gear', 'titulo': 'Efeitos de perfil', 'texto': 'Os efeitos que você compra aparecem nas Configurações, prontos pra equipar.'},
        ],
    },
    {
        'id': 15, 'data': '08/10/2026', 'titulo': 'Relíquia da semana e coleção',
        'itens': [
            {'icone': 'fa-hourglass-half', 'titulo': 'Relíquia da semana', 'texto': 'Um item com 25% de desconto que troca toda segunda-feira.'},
            {'icone': 'fa-trophy', 'titulo': 'Coleção', 'texto': 'Compre itens do Armazém e ganhe prêmios exclusivos por coleção.'},
            {'icone': 'fa-stamp', 'titulo': 'Edições limitadas', 'texto': 'Itens por tempo ou por estoque, até acabar.'},
        ],
    },
    {
        'id': 13, 'data': '08/10/2026', 'titulo': 'Bazar da comunidade',
        'itens': [
            {'icone': 'fa-store', 'titulo': 'Abra a sua lojinha', 'texto': 'Cadastre produtos com foto e vídeo, receba por Pix direto e acompanhe os pedidos pela "Minha lojinha".'},
            {'icone': 'fa-shuffle', 'titulo': 'Feed misturado', 'texto': 'Todas as lojas aparecem em ordem embaralhada, e o carrossel mostra propagandas.'},
        ],
    },
    {
        'id': 10, 'data': '08/10/2026', 'titulo': 'Armazém',
        'itens': [
            {'icone': 'fa-wand-magic-sparkles', 'titulo': 'A loja do app', 'texto': 'Molduras, nomes, placas, faixas e pacotes por tema, comprados com Dracmas. Veja o extrato em qualquer momento.'},
        ],
    },
]


def novidade_atual():
    """Id da novidade mais recente (vai no HTML: é o que aquela página já "conhece")."""
    return NOVIDADES[0]['id']


def novidades_para_cliente(limite=12):
    return NOVIDADES[:limite]
