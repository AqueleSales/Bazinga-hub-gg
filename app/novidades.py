"""Log de novidades: o que aparece no pop-up do botão "Atualização disponível" (a setinha ao lado da caixa de entrada).

Como funciona: cada página carrega sabendo a última novidade que tinha (`novidade_atual()` vai no HTML). Quando o servidor sobe uma
versão nova, o botão aparece e o pop-up mostra o que é MAIS NOVO que a página aberta ("Chega nesta atualização") e, abaixo, o histórico.

Pra anunciar uma atualização: ponha uma entrada NOVA no TOPO da lista, com `id` maior que o da anterior. Texto curto, em português
de gente (nada de nome de função). Cada item: `icone` (Font Awesome sem o "fa-solid"), `titulo` e `texto`.
"""

NOVIDADES = [
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
