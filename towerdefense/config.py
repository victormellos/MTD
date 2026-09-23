"""
Configuracoes gerais e constantes do jogo.

Nenhuma logica mora aqui - apenas numeros, cores e tabelas de dados
que os outros modulos importam. Manter tudo centralizado facilita
balancear o jogo sem precisar mexer no codigo de comportamento.
"""

# ----------------------------------------------------------------------------
# JANELA / GRADE
# ----------------------------------------------------------------------------
FPS = 60

# A grade cobre toda a area de jogo (o caminho serpenteia por dentro dela).
# Torres so podem ser construidas em celulas que NAO fazem parte do caminho.
GRID_COLS = 15
GRID_ROWS = 9
CELL_SIZE = 72
TOP_HUD_HEIGHT = 90
# Nao ha mais barra/legenda no rodape (removida a pedido: o jogo so tinha
# dicas de tecla + legenda de cores de nivel ali). Mantido como constante
# (em vez de apagar todo mundo que referencia "rodape") para o dia em que
# algo precisar de novo de uma faixa inferior - hoje vale 0.
BOTTOM_HUD_HEIGHT = 0

# Compatibilidade mobile/Android (touch, sem teclado fisico): liga uma
# barra inferior de botoes que cobre os atalhos de teclado essenciais
# (pausar, pular onda, abrir painel de torres, menu de mapas, sair).
# Detectado automaticamente pela plataforma relatada pelo SDL/python-for-
# android; pode ser forcado via variavel de ambiente MTD_FORCE_MOBILE=1
# (util pra testar o layout mobile rodando no desktop).
import os as _os
import sys as _sys
IS_MOBILE = (
    _sys.platform == "android"
    or _os.environ.get("ANDROID_ARGUMENT") is not None
    or _os.environ.get("MTD_FORCE_MOBILE") == "1"
)
if IS_MOBILE:
    BOTTOM_HUD_HEIGHT = 96

# A altura da janela e derivada da grade (nao um numero solto): assim o
# grid nunca fica cortado/sobreposto por uma eventual barra inferior.
WIDTH = 1280
HEIGHT = TOP_HUD_HEIGHT + GRID_ROWS * CELL_SIZE + BOTTOM_HUD_HEIGHT

GRID_ORIGIN_X = (WIDTH - GRID_COLS * CELL_SIZE) // 2
GRID_ORIGIN_Y = TOP_HUD_HEIGHT

PANEL_WIDTH = WIDTH  # mantido por compatibilidade com HUD que usa toda a largura

# ----------------------------------------------------------------------------
# PAINEL LATERAL DE TORRES (estilo Bloons TD)
# Fica sobreposto na frente do grid (nao redimensiona a area de jogo).
# Pode abrir/fechar deslizando; quando fechado fica totalmente fora da tela.
# ----------------------------------------------------------------------------
TOWER_PANEL_WIDTH = 300
TOWER_PANEL_CARD_H = 96
TOWER_PANEL_CARD_GAP = 10
TOWER_PANEL_SLIDE_SPEED = 1900  # px/s da animacao de abrir/fechar
TOWER_PANEL_DOUBLE_CLICK_MS = 400  # janela para o "2 cliques = auto-coloca"

# ----------------------------------------------------------------------------
# ECONOMIA / REGRAS GERAIS
# ----------------------------------------------------------------------------
STARTING_GOLD = 220
STARTING_LIVES = 20
TOWER_BASE_COST = 60
# ouro extra ganho ao pular a onda -- e ouro "de graca" (sem precisar
# matar nada), entao fica deliberadamente mais fraco que o ouro ganho
# lutando a onda inteira, senao pular vira a fonte de renda otima e o
# jogador nunca enfrenta a dificuldade real da onda que pulou.
SKIP_WAVE_BASE_BONUS = 20
SKIP_WAVE_BONUS_PER_WAVE = 2  # cresce bem mais devagar que antes (era 6, depois 3)
# fracao do ouro INVESTIDO (compra + upgrades de caminho, incluindo o que
# foi fundido) devolvida ao vender uma torre -- ver Tower.invested e
# Game.sell_tower. Menor que 1 de proposito, senao comprar/vender vira
# uma forma gratis de "reordenar" torres na grade sem custo nenhum.
TOWER_SELL_REFUND_RATIO = 0.7

# As melhorias por torre NAO sao mais tres barrinhas genericas de
# dano/alcance/cadencia: viraram a arvore de 3 caminhos x 6 tiers
# (estilo Bloons TD 6) que vive em `towerdefense/upgrades.py` -- e la
# que ficam nomes, descricoes, efeitos e custos de cada upgrade.
CLICK_DRAG_THRESHOLD = 8  # pixels; abaixo disso, soltar o mouse conta como clique

# --- parametros de combate usados pela arvore de upgrades ---
# intervalo entre os tiros extras de uma rajada (mod `burst_add`)
BURST_INTERVAL = 0.09
# abertura (radianos) entre projeteis de um mesmo ataque multiplo
SHOT_SPREAD = 0.10
# de quanto em quanto tempo uma aura (Permafrost, Era Glacial...) pulsa
AURA_PULSE_INTERVAL = 0.25
# a partir de quanta armadura um inimigo conta como "pesado" para os
# bonus anti-colosso (bosses sempre contam, independente da armadura)
HEAVY_ENEMY_ARMOR = 8
# chance de um inimigo esquivo/camuflado ignorar um acerto de uma torre
# SEM deteccao (ver "Visao Tatica", caminho Observador da sniper)
EVASION_CHANCE = 0.35

# ----------------------------------------------------------------------------
# DIFICULDADES
# Escolhida pelo jogador numa tela propria, depois do mapa (ver
# ui/difficulty_menu.py). Multiplica por cima do que o MAPA ja aplica
# (map_path.hp_mult/gold_mult) e da progressao normal por onda -- os
# tres continuam funcionando exatamente como antes, a dificuldade so
# adiciona mais um fator em cima.
#   - gold_mult: multiplica todo ouro ganho ao abater inimigos
#   - gem_mult: multiplica gemas ganhas de boss (recompensa de risco:
#     dificuldades mais altas rendem mais gemas, o recurso permanente)
#   - spawn_count_mult: multiplica a QUANTIDADE de inimigos por onda
#   - enemy_power_mult: multiplica HP e velocidade dos inimigos
# DEFAULT_DIFFICULTY_ID e o que toda partida nova comeca selecionada
# na tela (nao pula a tela -- so define o card pre-marcado).
# ----------------------------------------------------------------------------
DIFFICULTY_DEFS = {
    "pacifico": {
        "label": "Pacifico", "desc": "Quase sem pressao: ideal para relaxar e testar torres.",
        "gold_mult": 1.6, "gem_mult": 0.5, "spawn_count_mult": 0.5, "enemy_power_mult": 0.6,
    },
    "super_facil": {
        "label": "Super Facil", "desc": "Bem tranquilo, com uma pressao minima.",
        "gold_mult": 1.3, "gem_mult": 0.7, "spawn_count_mult": 0.7, "enemy_power_mult": 0.75,
    },
    "facil": {
        "label": "Facil", "desc": "Um desafio leve para quem esta comecando.",
        "gold_mult": 1.15, "gem_mult": 0.85, "spawn_count_mult": 0.85, "enemy_power_mult": 0.9,
    },
    "medio": {
        "label": "Medio", "desc": "O equilibrio padrao do jogo.",
        "gold_mult": 1.0, "gem_mult": 1.0, "spawn_count_mult": 1.0, "enemy_power_mult": 1.0,
    },
    "dificil": {
        "label": "Dificil", "desc": "Mais inimigos e mais fortes: exige boas escolhas.",
        "gold_mult": 0.85, "gem_mult": 1.25, "spawn_count_mult": 1.2, "enemy_power_mult": 1.2,
    },
    "muito_dificil": {
        "label": "Muito Dificil", "desc": "Pressao pesada o jogo todo: poucas margens de erro.",
        "gold_mult": 0.7, "gem_mult": 1.6, "spawn_count_mult": 1.4, "enemy_power_mult": 1.45,
    },
    "morte": {
        "label": "Morte", "desc": "O modo mais brutal: cada onda testa o limite da sua defesa.",
        "gold_mult": 0.5, "gem_mult": 2.2, "spawn_count_mult": 1.6, "enemy_power_mult": 1.8,
    },
}
DIFFICULTY_ORDER = ["pacifico", "super_facil", "facil", "medio", "dificil", "muito_dificil", "morte"]
DEFAULT_DIFFICULTY_ID = "medio"

BOSS_WAVE_INTERVAL = 10  # a cada quantas ondas surge um boss
BOSS_HP_SCALE_PER_CYCLE = 0.55  # bosses ficam mais fortes a cada ciclo de 10 ondas
BOSS_GEMS_PER_CYCLE = 1  # gemas extras a cada ciclo de boss (alem da base)

# ----------------------------------------------------------------------------
# CORES
# ----------------------------------------------------------------------------
COL_BG = (18, 22, 30)
COL_PANEL = (26, 32, 44)
COL_PATH = (72, 60, 44)
COL_PATH_EDGE = (50, 40, 28)
COL_GRID_EMPTY = (40, 48, 62)
COL_GRID_EMPTY_HOVER = (55, 66, 84)
COL_GRID_BORDER = (60, 70, 90)
COL_TEXT = (235, 235, 240)
COL_TEXT_DIM = (160, 168, 182)
COL_GOLD = (255, 210, 90)
COL_GEM = (120, 220, 255)
COL_HP_BG = (60, 20, 20)
COL_HP_FG = (90, 220, 110)
COL_WHITE = (255, 255, 255)
COL_RED = (230, 70, 70)
COL_GREEN = (90, 220, 110)
COL_MERGE_GLOW = (255, 255, 140)
COL_SWAP_GLOW = (140, 190, 255)

# Niveis de torre: cores fixas para os primeiros niveis; alem disso a cor
# eh gerada proceduralmente (ciclo de matiz infinito) para nunca "estourar".
TOWER_LEVEL_COLORS = [
    (110, 190, 255),   # nivel 1 - azul claro
    (110, 255, 170),   # nivel 2 - verde
    (255, 220, 90),    # nivel 3 - amarelo
    (255, 150, 70),    # nivel 4 - laranja
    (255, 90, 90),     # nivel 5 - vermelho
    (220, 90, 255),    # nivel 6 - roxo
    (255, 255, 255),   # nivel 7 - branco/lendario
]

TOWER_LEVEL_NAMES = ["Recruta", "Soldado", "Veterano", "Elite", "Campeao", "Mestre", "Lendario"]

# ----------------------------------------------------------------------------
# TIPOS DE TORRE
# Cada tipo tem sua propria progressao de dano/alcance/cadencia e um
# comportamento especial que se intensifica com o nivel (vindo de merges).
# Torres so se fundem com outra do MESMO tipo E MESMO nivel.
#
# `buy_cost_factor` multiplica `TOWER_BASE_COST` no preco de COMPRA
# (Game.tower_cost_for) -- antes do rebalanceamento, toda torre custava
# o mesmo pra comprar e so o preco de UPGRADE (TYPE_COST_FACTOR, em
# upgrades.py) variava por tipo. Isso fazia uma torre estritamente
# melhor em tudo (ex.: canhao pesado) nao ter nenhuma desvantagem real
# antes mesmo de qualquer upgrade. Agora o preco de entrada tambem
# reflete o poder base: torres de nicho (espinhos/flecha) sao baratas
# pra comprar em quantidade; torres de elite (sniper/canhao pesado) sao
# caras logo na primeira compra, nao so ao evoluir.
# ----------------------------------------------------------------------------
TOWER_TYPES = {
    "canhao": {
        "label": "Canhao",
        "desc": "Dano solido, bom alcance. Equilibrado.",
        "base_color": (110, 190, 255),
        "base_range": 120, "base_damage": 14, "base_rate": 0.70,
        "splash_from_lvl": 3, "splash_base": 24, "splash_step": 6,
        "proj_speed": 420, "proj_shape": "circle",
        "tower_shape": "circle",
        "buy_cost_factor": 1.00,
    },
    "flecha": {
        "label": "Torre de Flechas",
        "desc": "Barata e rapidissima; ótima contra hordas, fraca contra armadura pesada.",
        "base_color": (140, 230, 120),
        "base_range": 130, "base_damage": 7, "base_rate": 0.24,
        "splash_from_lvl": None, "splash_base": 0, "splash_step": 0,
        "proj_speed": 620, "proj_shape": "arrow",
        "tower_shape": "triangle",
        "buy_cost_factor": 0.80,
    },
    "gelo": {
        "label": "Torre de Gelo",
        "desc": "Dano baixo, mas sempre desacelera o alvo com forca.",
        "base_color": (140, 220, 255),
        "base_range": 105, "base_damage": 5.5, "base_rate": 0.55,
        "splash_from_lvl": 4, "splash_base": 30, "splash_step": 8,
        "proj_speed": 380, "proj_shape": "shard",
        "always_slow": (0.48, 1.0),
        "tower_shape": "hexagon",
        "buy_cost_factor": 0.90,
    },
    "canhao_pesado": {
        "label": "Canhao Pesado",
        "desc": "O soco de area mais caro do jogo: tiro lento, alcance curto, dano gigante.",
        "base_color": (255, 140, 70),
        "base_range": 115, "base_damage": 46, "base_rate": 1.75,
        "splash_from_lvl": 1, "splash_base": 34, "splash_step": 7,
        "proj_speed": 340, "proj_shape": "square",
        "tower_shape": "square",
        "buy_cost_factor": 1.55,
    },
    "sniper": {
        "label": "Sniper",
        "desc": "Alcance imenso e dano alto, mas cadencia bem lenta e sem splash.",
        "base_color": (230, 90, 220),
        "base_range": 280, "base_damage": 38, "base_rate": 1.5,
        "splash_from_lvl": None, "splash_base": 0, "splash_step": 0,
        "proj_speed": 900, "proj_shape": "line",
        "armor_pierce": True,
        "tower_shape": "diamond",
        "buy_cost_factor": 1.35,
    },
    "espinhos": {
        "label": "Armadilheiro",
        "desc": "Barata, cobre o caminho inteiro; nao mira, nao erra, ignora evasao.",
        "base_color": (170, 140, 90),
        # sem "mira" tradicional: plant_range é o raio em que ela pode
        # plantar espinhos no caminho (analogo ao base_range das outras).
        "base_range": 130, "base_damage": 11.5, "base_rate": 1.4,
        "base_charges": 2, "base_max_spikes": 4,
        "splash_from_lvl": None, "splash_base": 0, "splash_step": 0,
        "proj_speed": 0, "proj_shape": None,
        "no_targeting": True,  # nao mira/atira: ver Tower.update
        "tower_shape": "spikes",
        "buy_cost_factor": 0.75,
    },
}
TOWER_TYPE_KEYS = list(TOWER_TYPES.keys())

# ----------------------------------------------------------------------------
# TIPOS DE INIMIGOS
# `shape` identifica a silhueta usada em `Enemy.draw` (entities/enemy.py) --
# cada tipo tem a SUA propria forma (nunca duas reaproveitando a mesma),
# pra dar pra reconhecer o tipo so pela silhueta, sem precisar checar a
# cor de perto. `flying` e `splits_into` sao mecanicas especiais (ver
# comentarios em "voador" e "slime" abaixo).
# ----------------------------------------------------------------------------
ENEMY_TYPES = {
    "grunt": {
        "color": (200, 90, 90), "radius": 12, "speed": 60, "hp": 40,
        "gold": 8, "shape": "circle", "min_wave": 1, "armor": 0,
    },
    "runner": {
        # triangulo apontando na direcao do movimento: comunica velocidade
        # so pela silhueta, sem precisar olhar a barra de vida
        "color": (250, 200, 60), "radius": 10, "speed": 120, "hp": 22,
        "gold": 7, "shape": "arrow_tri", "min_wave": 2, "armor": 0,
    },
    "tank": {
        # quadrado com borda grossa: "bloco" solido, robusto
        "color": (110, 110, 190), "radius": 18, "speed": 34, "hp": 160,
        "gold": 18, "shape": "square", "min_wave": 4, "armor": 4,
    },
    "swarm": {
        # par de losangos colados: sugere "enxame" (varios juntos), nao
        # so um circulo pequeno como as outras torres leves
        "color": (230, 130, 220), "radius": 7, "speed": 95, "hp": 14,
        "gold": 4, "shape": "swarm_pair", "min_wave": 3, "armor": 0,
    },
    "brute": {
        # hexagono: mais "pesado" que o quadrado do tank sem repetir a
        # mesma silhueta
        "color": (150, 70, 40), "radius": 22, "speed": 40, "hp": 340,
        "gold": 30, "shape": "hexagon", "min_wave": 7, "armor": 8,
    },
    "phantom": {
        # "camuflado": tem chance de ignorar acertos de torres sem
        # deteccao (ver EVASION_CHANCE e o caminho Observador da sniper).
        # Anel vazado/pontilhado em vez de preenchido: parece "instavel",
        # condizente com a evasao.
        "color": (170, 230, 255), "radius": 11, "speed": 85, "hp": 70,
        "gold": 14, "shape": "phantom_ring", "min_wave": 6, "armor": 2,
        "evasive": True,
    },
    "titan": {
        # octogono grande: o maior terrestre nao-boss, forma com mais
        # lados = leitura de "o mais imponente antes do boss"
        "color": (255, 80, 80), "radius": 28, "speed": 26, "hp": 900,
        "gold": 70, "shape": "octagon", "min_wave": 12, "armor": 15,
    },
    "voador": {
        # "voa" por cima da pista: ignora espinhos por completo (o
        # armadilheiro planta NO CHAO, ver Tower._plant_spike/Spike) e
        # tem chance propria de fazer QUALQUER torre errar o tiro
        # (FLYING_DODGE_CHANCE), independente de deteccao -- e uma
        # esquiva "fisica" (esta fora de alcance de acerto confiavel),
        # nao uma esquiva "de visao" como a do phantom/camo_detect, entao
        # nenhum upgrade de deteccao a anula.
        "color": (255, 235, 140), "radius": 10, "speed": 70, "hp": 55,
        "gold": 12, "shape": "bird", "min_wave": 5, "armor": 0,
        "flying": True,
    },
    "slime": {
        # ao morrer, divide em filhotes menores (ver `splits_into` em
        # Game.update -- "morreu por dano de torre"). Os filhotes usam o
        # tipo "slime_small" (abaixo), que NAO tem `splits_into`, entao a
        # divisao para depois de uma geracao (sem enxame infinito).
        "color": (120, 220, 120), "radius": 16, "speed": 50, "hp": 90,
        "gold": 10, "shape": "slime_blob", "min_wave": 6, "armor": 0,
        "splits_into": "slime_small", "split_count": 2, "split_hp_frac": 0.6,
    },
    "slime_small": {
        # filhote do slime: nao aparece em onda nenhuma (min_wave alto e
        # irrelevante -- so nasce via `splits_into`, nunca no spawn normal
        # de onda, ver WaveManager.build_wave_queue), menor, mais rapido,
        # sem dividir de novo.
        "color": (150, 235, 150), "radius": 9, "speed": 65, "hp": 20,
        "gold": 3, "shape": "slime_blob", "min_wave": 9999, "armor": 0,
    },
    "boss": {
        "color": (255, 215, 0), "radius": 34, "speed": 22, "hp": 2200,
        "gold": 180, "shape": "star", "min_wave": 10, "armor": 20,
        "is_boss": True, "gems": 3,
    },
}

# Chance de QUALQUER torre errar um inimigo voador a cada tiro (esquiva
# "fisica", independente de camo_detect -- ver comentario em "voador"
# acima e Enemy.dodges).
FLYING_DODGE_CHANCE = 0.50

# ----------------------------------------------------------------------------
# META-UPGRADES (SHOP DE GEMAS)
# Melhorias permanentes DENTRO DA PARTIDA ATUAL, compradas com gemas
# (o recurso mais raro/valioso, obtido matando bosses). Cada upgrade tem
# niveis, custo crescente em gemas, e afeta o jogo inteiro (nao uma
# torre especifica).
#
# Balanceamento: gemas sao raras (poucas por boss), entao cada nivel
# precisa custar gemas de verdade -- nao mais 1-3 gemas por compra.
# `max_level: None` == sem teto (upgrade infinito); quando usado, o
# proprio `effect_per_level` costuma ser consumido de forma nao-linear
# pelo metodo em MetaUpgrades (ver systems/meta_upgrades.py) em vez de
# so multiplicar, pra nao explodir com nivel alto.
# ----------------------------------------------------------------------------
META_UPGRADE_DEFS = {
    "gold_gain": {
        "label": "Ganho de Ouro",
        "desc": "Aumenta todo ouro recebido ao abater inimigos.",
        "icon_color": (255, 210, 90),
        "base_cost": 4, "cost_step": 4,
        # Era 0.10 x ate nivel 15 (+150% no teto). Isso e permanente entre
        # partidas (ver save_system.save_meta), entao compunha com toda
        # sessao futura -- depois de algumas partidas o ouro em jogo ja
        # nascia inflado antes de qualquer decisao do jogador na partida
        # atual. +84% no teto ainda vale a pena comprar, so nao dobra
        # sozinho a economia inteira.
        "effect_per_level": 0.07,  # +7% por nivel
        "max_level": 12,
    },
    "start_level": {
        "label": "Nivel Inicial das Torres",
        "desc": "Toda torre nova ja nasce em um nivel mais alto.",
        "icon_color": (140, 220, 255),
        "base_cost": 10, "cost_step": 8,
        "effect_per_level": 1,  # +1 nivel inicial por ponto
        "max_level": 6,
    },
    "tower_cost": {
        "label": "Desconto em Torres",
        "desc": "Reduz o preco de compra de novas torres.",
        "icon_color": (140, 255, 170),
        "base_cost": 6, "cost_step": 4,
        "effect_per_level": 0.05,  # -5% de custo por nivel
        "max_level": 9,
    },
    "starting_gold": {
        "label": "Ouro Inicial",
        "desc": "Comeca cada partida com mais ouro no bolso.",
        "icon_color": (255, 180, 60),
        "base_cost": 5, "cost_step": 3,
        "effect_per_level": 40,  # +40 de ouro inicial por ponto
        "max_level": 10,
    },
    "extra_lives": {
        "label": "Segunda Chance",
        "desc": "Da uma chance de o inimigo que chegaria ao fim voltar "
                 "para o comeco em vez de tirar uma vida (max. 1x por "
                 "inimigo). Sem limite de nivel, mas cada nivel novo "
                 "aumenta a chance cada vez menos -- nunca chega a 100%.",
        "icon_color": (255, 120, 120),
        "base_cost": 8, "cost_step": 5,
        # curva assintotica: chance(n) = SECOND_CHANCE_CAP * (1 - decay^n)
        # (ver SECOND_CHANCE_CAP / SECOND_CHANCE_DECAY abaixo e o metodo
        # `second_chance_prob` em systems/meta_upgrades.py)
        "effect_per_level": None,
        "max_level": None,  # infinito de proposito
    },
    "upgrade_discount": {
        "label": "Desconto em Melhorias",
        "desc": "Reduz o custo dos upgrades de caminho das torres.",
        "icon_color": (220, 140, 255),
        "base_cost": 9, "cost_step": 6,
        "effect_per_level": 0.06,  # -6% de custo por nivel
        "max_level": 7,
    },
}
META_UPGRADE_KEYS = list(META_UPGRADE_DEFS.keys())

# Curva de "Segunda Chance" (ver acima): teto teorico e velocidade de
# aproximacao. Com cap=0.65 e decay=0.90, a chance sobe rapido no
# comeco e desacelera bastante depois do nivel ~15, sem nunca chegar
# no teto (e o teto ja fica bem longe de 100%).
SECOND_CHANCE_CAP = 0.65
SECOND_CHANCE_DECAY = 0.90

# ----------------------------------------------------------------------------
# TIER 6 -- LIBERADO POR GEMAS
# Alem do custo em ouro (TIER_COSTS[-1] em upgrades.py), tier 6 agora
# tambem exige gemas -- e por isso que a trava antiga de "so um tier 6
# por tipo de torre na partida" foi removida (ver Game.tier6_owner):
# gemas ja sao o limitador natural de quantos tier 6 voce consegue
# bancar, entao a trava artificial deixou de fazer sentido.
# ----------------------------------------------------------------------------
TIER6_GEM_COST = 10
