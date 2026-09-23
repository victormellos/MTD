"""Classe principal do jogo: estado, loop de eventos, update e desenho.

Esta classe orquestra os outros modulos (entidades, sistemas, paths, ui)
mas tenta nao reimplementar logica que ja vive neles.
"""

import sys
import pygame

from .config import (
    WIDTH, HEIGHT, FPS, COL_BG, COL_MERGE_GLOW, COL_SWAP_GLOW,
    STARTING_GOLD, STARTING_LIVES, TOWER_BASE_COST, TOWER_SELL_REFUND_RATIO,
    SKIP_WAVE_BASE_BONUS, SKIP_WAVE_BONUS_PER_WAVE,
    GRID_ORIGIN_X, GRID_ORIGIN_Y, GRID_COLS, GRID_ROWS, CELL_SIZE,
    CLICK_DRAG_THRESHOLD, COL_GOLD, COL_GEM, COL_RED, TOP_HUD_HEIGHT,
    TOWER_PANEL_WIDTH, TOWER_PANEL_SLIDE_SPEED, TOWER_PANEL_DOUBLE_CLICK_MS,
    TIER6_GEM_COST, TOWER_TYPES, ENEMY_TYPES, BOSS_WAVE_INTERVAL,
    DIFFICULTY_DEFS, DEFAULT_DIFFICULTY_ID,
)
from .paths import MapPath
from .maps import DEFAULT_MAP_ID
from .entities import Tower
from .entities.enemy import Enemy
from .systems import WaveManager, MetaUpgrades, AbilityController, combat, vfx
from . import upgrades as up
from . import save_system
from .fonts import get_font
from .ui import hud, menus, board, map_menu, difficulty_menu, main_menu, tower_panel, mobile_bar, theme
from .config import IS_MOBILE

# Autosave a cada N segundos de jogo (alem do save imediato ao fechar o
# jogo) -- ver Game.update / Game._autosave_tick.
AUTOSAVE_INTERVAL = 8.0


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Tower Defense Infinito - Merge das Torres")
        # `self.screen` e a JANELA de verdade (redimensionavel pelo usuario
        # ou em tela cheia); `self.canvas` e uma superficie interna de
        # resolucao FIXA (WIDTH x HEIGHT), a mesma que todo o resto do jogo
        # (ui/, entities/, systems/) sempre desenhou. Nenhum outro modulo
        # precisa saber que a janela mudou de tamanho: eles continuam
        # desenhando no `canvas` logico normalmente; so aqui em Game a
        # gente escala esse canvas pro tamanho real da janela na hora do
        # flip (letterbox, preservando proporcao) e convertemos cliques/
        # posicao do mouse de "pixel da janela" pra "pixel logico do
        # canvas" antes de qualquer outro codigo ver essas coordenadas.
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.windowed_size = (WIDTH, HEIGHT)  # ultimo tamanho em modo janela (p/ restaurar ao sair da tela cheia)
        self.is_fullscreen = False
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        # `self.render_rect` e onde o canvas logico cai dentro da janela
        # real (a area "letterboxed"); recalculado sempre que a janela
        # muda de tamanho. Comeca preenchendo a janela 1:1.
        self.render_rect = pygame.Rect(0, 0, WIDTH, HEIGHT)
        self._update_render_rect()
        self.clock = pygame.time.Clock()
        # gemas e melhorias permanentes NAO sao zeradas pelo reset() normal:
        # elas representam progresso de longo prazo entre tentativas,
        # como e comum em jogos com "prestige"/meta-progressao.
        self.gems = 0
        self.meta = MetaUpgrades()
        # progresso permanente (gemas + niveis de melhorias compradas com
        # gemas): persiste entre partidas E entre execucoes do jogo (ver
        # save_system.save_meta/load_meta). Carregado aqui, ANTES do
        # primeiro reset() la embaixo, pra o ouro inicial ja sair
        # calculado com os upgrades permanentes certos.
        meta_data = save_system.load_meta()
        if meta_data is not None:
            save_system.apply_meta_data(self, meta_data)
        self.total_bosses_killed = 0
        self.meta_shop_open = False
        self.gem_button_rect = None
        self.mouse_pos = (0, 0)
        # estado geral do jogo: comeca no menu principal (tela de titulo).
        # "main_menu" -> tela de titulo | "map_select" -> escolhendo mapa
        # | "difficulty_select" -> escolhendo dificuldade (apos o mapa)
        # | "playing" -> partida em curso
        self.state = "main_menu"
        self.show_help = False
        self.selected_map_id = DEFAULT_MAP_ID
        self.map_path = MapPath(self.selected_map_id)
        self.selected_difficulty_id = DEFAULT_DIFFICULTY_ID
        self._pending_map_id = self.selected_map_id
        self.reset()
        # save em disco: ver save_system.py (grava em C:\MTD\save_game.json).
        # `has_save_file` so controla se o menu principal mostra o botao
        # "Continuar" -- o carregamento de verdade so acontece se o
        # jogador clicar nele (load_from_disk).
        self.has_save_file = save_system.has_save()
        self.autosave_timer = AUTOSAVE_INTERVAL

    # ------------------------------------------------------------------
    # SAVE / LOAD EM DISCO
    # ------------------------------------------------------------------
    def load_from_disk(self):
        """Chamado pelo botao 'Continuar' do menu principal: le o save,
        reconstroi o mapa/estado da partida e entra direto no jogo."""
        data = save_system.load_game()
        if data is None:
            self.has_save_file = False
            self.state = "map_select"
            return
        self.selected_map_id = data.get("map_id", DEFAULT_MAP_ID)
        self.map_path = MapPath(self.selected_map_id)
        self.selected_difficulty_id = data.get("difficulty_id", DEFAULT_DIFFICULTY_ID)
        self.reset()
        save_system.apply_save_data(self, data)
        self.state = "playing"

    def save_to_disk(self):
        """Grava a partida atual em disco. So chamado com uma partida
        de verdade em andamento (ver chamadas em update()/run())."""
        save_system.save_game(self)

    def _minimize_android(self):
        """Manda o app Android pro segundo plano (equivalente ao botao
        Home), em vez de matar o processo (ver uso em K_ESCAPE acima).
        Usa pyjnius (disponivel no bootstrap SDL2 do python-for-android)
        pra chamar Activity.moveTaskToBack; se pyjnius nao existir (rodando
        no desktop com MTD_FORCE_MOBILE=1 so pra testar o layout, por
        exemplo) simplesmente nao faz nada -- nunca derruba o jogo."""
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            PythonActivity.mActivity.moveTaskToBack(True)
        except Exception:
            pass

    def _trigger_game_over(self):
        """Marca fim de partida e apaga o save em disco: a corrida
        terminou, entao nao ha mais "continuar" essa partida especifica
        (o proximo 'Continuar' nao deve reabrir um jogo ja perdido)."""
        self.game_over = True
        save_system.delete_save()
        self.has_save_file = False

    def _autosave_tick(self, dt):
        """Autosave periodico enquanto a partida esta em andamento (nao
        pausada, sem game over). Roda em Game.update; alem disso o jogo
        tambem salva uma ultima vez ao fechar (ver run())."""
        if self.state != "playing" or self.game_over:
            return
        self.autosave_timer -= dt
        if self.autosave_timer <= 0:
            self.autosave_timer = AUTOSAVE_INTERVAL
            self.save_to_disk()
            self.has_save_file = True

    # ------------------------------------------------------------------
    # JANELA / TELA CHEIA / ESCALA
    # ------------------------------------------------------------------
    def _update_render_rect(self):
        """Recalcula onde o canvas logico (WIDTH x HEIGHT fixo) cai dentro
        da janela real, preservando a proporcao (letterbox) -- chamado
        sempre que a janela muda de tamanho (redimensionar ou F11)."""
        win_w, win_h = self.screen.get_size()
        scale = min(win_w / WIDTH, win_h / HEIGHT)
        scale = max(scale, 0.01)  # nunca zero/negativo (janela minimizada etc.)
        draw_w = int(WIDTH * scale)
        draw_h = int(HEIGHT * scale)
        off_x = (win_w - draw_w) // 2
        off_y = (win_h - draw_h) // 2
        self.render_rect = pygame.Rect(off_x, off_y, draw_w, draw_h)

    def handle_resize(self, size):
        """Chamado em VIDEORESIZE: so recalcula a area de escala. O canvas
        logico (WIDTH x HEIGHT) nunca muda -- por isso nenhum outro modulo
        do jogo (grid, HUD, paineis) precisa saber que a janela mudou."""
        if not self.is_fullscreen:
            self.windowed_size = size
        self._update_render_rect()

    def toggle_fullscreen(self):
        """F11: alterna entre janela livre (redimensionavel) e tela cheia,
        sempre preservando o ultimo tamanho de janela pra restaurar depois."""
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            self.is_fullscreen = False
        else:
            self.windowed_size = self.screen.get_size()
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.is_fullscreen = True
        self._update_render_rect()

    def window_to_canvas(self, pos):
        """Converte uma posicao em pixel da JANELA (o que pygame reporta em
        eventos de mouse e em get_pos) pra pixel do canvas LOGICO (o
        sistema de coordenadas que board/hud/tower_panel/etc sempre
        usaram). Fora da area util (nas barras pretas do letterbox), o
        ponto e grudado na borda mais proxima do canvas -- assim um clique
        levemente fora ainda resolve pra algo coerente em vez de vazar
        coordenada negativa/gigante pro resto do jogo."""
        rect = self.render_rect
        if rect.width <= 0 or rect.height <= 0:
            return (0, 0)
        rel_x = (pos[0] - rect.x) / rect.width
        rel_y = (pos[1] - rect.y) / rect.height
        rel_x = min(max(rel_x, 0.0), 1.0)
        rel_y = min(max(rel_y, 0.0), 1.0)
        return (rel_x * WIDTH, rel_y * HEIGHT)

    def start_map(self, map_id):
        """Define o mapa escolhido, (re)constroi o caminho e comeca a
        partida de verdade (com a dificuldade ja selecionada em
        self.selected_difficulty_id). Mantido como o metodo que efetivamente
        inicia o jogo -- chamado tanto pelo fluxo normal (apos escolher
        mapa e dificuldade) quanto por quem queira pular direto pra uma
        partida com a dificuldade padrao/atual (ex.: testes)."""
        self.selected_map_id = map_id
        self.map_path = MapPath(map_id)
        self.reset()
        self.state = "playing"

    def choose_map(self, map_id):
        """Chamado ao clicar num card do menu de mapas: guarda o mapa
        escolhido e manda para a escolha de dificuldade (start_map so
        roda de fato depois, em choose_difficulty)."""
        self._pending_map_id = map_id
        self.state = "difficulty_select"

    def choose_difficulty(self, difficulty_id):
        """Chamado ao clicar num card de dificuldade: fixa a dificuldade
        escolhida e so ai inicia a partida no mapa pendente."""
        self.selected_difficulty_id = difficulty_id
        self.start_map(self._pending_map_id)

    def reset(self):
        self.gold = STARTING_GOLD + self.meta.bonus_starting_gold()
        self.lives = STARTING_LIVES
        self.enemies = []
        self.projectiles = []
        # `vfx` e `pending_blasts` fazem do Game o "world" que entities/ e
        # systems/ recebem (ver comentario de convencao em systems/combat.py):
        # projeteis, explosoes e habilidades escrevem aqui em vez de
        # conhecer a classe Game.
        self.vfx = []
        self.pending_blasts = []
        self.towers = {}  # (col, row) -> Tower
        self.abilities = AbilityController()
        self.ability_banner = None  # [nome, tempo_restante] mostrado no HUD
        # efeitos globais de habilidade sao atributos de classe do Enemy:
        # zerar aqui evita comecar uma partida nova com a pista ainda sob
        # DOMINIO ETERNO da partida anterior
        Enemy.global_amp = 0.0
        Enemy.global_slow = 1.0
        self.wave_mgr = WaveManager(self.map_path, self.selected_difficulty_id)
        self.paused = False
        self.game_over = False
        self.dragging_tower = None
        self.drag_origin = None
        self.floating_texts = []  # (x, y, text, color, life)
        self.tower_cost = TOWER_BASE_COST  # sera recalculado abaixo
        self.total_kills = 0
        self.hovered_cell = None
        self.skip_button_rect = None  # calculado no draw_hud, usado no clique
        self.mouse_down_pos = None  # posicao do ultimo mousedown (p/ distinguir clique de drag)

        # -- painel lateral de torres (compra + upgrade) --
        self.tower_panel_open = True
        # posicao x atual da borda esquerda do painel (anima entre aberto/fechado)
        self.tower_panel_x = WIDTH - TOWER_PANEL_WIDTH
        self.selected_tower_cell = None  # celula com upgrade aberto no painel
        self.dragging_from_panel = None  # type_key sendo arrastado do painel, ou None
        # type_key em "modo de colocacao": clicou uma vez no card (sem
        # arrastar) e continua selecionado ate o jogador clicar de novo no
        # mesmo card, escolher outro, apertar ESC ou abrir o modo upgrade --
        # NAO desmarca sozinho depois de uma compra, pra dar pra clicar em
        # varias celulas seguidas sem reabrir o painel a cada torre.
        self.selected_shop_type = None
        self.panel_click_pending = None  # (type_key, tempo_ms) do ultimo clique no card, p/ duplo-clique

        self.recalc_tower_cost()

    # ------------------------------------------------------------------
    def add_floating_text(self, x, y, text, color):
        self.floating_texts.append([x, y, text, color, 1.0])

    def update_floating_texts(self, dt):
        for ft in self.floating_texts:
            ft[1] -= 30 * dt
            ft[4] -= dt
        self.floating_texts = [ft for ft in self.floating_texts if ft[4] > 0]

    # ------------------------------------------------------------------
    def cell_from_pixel(self, x, y):
        if x < GRID_ORIGIN_X or y < GRID_ORIGIN_Y:
            return None
        col = (x - GRID_ORIGIN_X) // CELL_SIZE
        row = (y - GRID_ORIGIN_Y) // CELL_SIZE
        if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
            return int(col), int(row)
        return None

    # ------------------------------------------------------------------
    def first_empty_cell(self):
        """Retorna a primeira celula (varrendo linha a linha) que nao
        e caminho e nao tem torre, ou None se a grade estiver cheia."""
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                cell = (col, row)
                if cell in self.map_path.cell_set:
                    continue
                if cell not in self.towers:
                    return cell
        return None

    def buy_tower_at(self, cell, ttype):
        """Tenta comprar uma torre do tipo dado na celula dada. Retorna
        True se a compra foi concluida (ouro descontado, torre criada)."""
        if cell is None or cell in self.towers or cell in self.map_path.cell_set:
            return False
        cost = self.tower_cost_for(ttype)
        if self.gold < cost:
            return False
        self.gold -= cost
        start_level = 1 + int(self.meta.start_tower_level_bonus())
        t = Tower(cell[0], cell[1], ttype=ttype, level=start_level, invested=cost)
        self.towers[cell] = t
        self.add_floating_text(*t.grid_pos(), f"-{cost}g", COL_GOLD)
        return True

    # ------------------------------------------------------------------
    def sell_tower(self, cell):
        """Vende a torre da celula dada, devolvendo uma fracao
        (TOWER_SELL_REFUND_RATIO) do ouro investido nela (compra +
        upgrades de caminho + o que veio de merges). Retorna True se
        vendeu."""
        tower = self.towers.get(cell)
        if tower is None:
            return False
        refund = int(round(tower.invested * TOWER_SELL_REFUND_RATIO))
        self.gold += refund
        tx, ty = tower.grid_pos()
        del self.towers[cell]
        if self.selected_tower_cell == cell:
            self.selected_tower_cell = None
        self.add_floating_text(tx, ty, f"+{refund}g", COL_GOLD)
        return True

    # ------------------------------------------------------------------
    def tower_cost_for(self, ttype):
        """Custo de compra de uma torre NOVA do tipo dado, considerando a
        onda atual, o multiplicador de preco por tipo (`buy_cost_factor`
        em TOWER_TYPES -- torres de elite como sniper/canhao pesado sao
        mais caras de comprar, nao so de evoluir) e os descontos
        permanentes comprados com gemas."""
        raw = TOWER_BASE_COST + (self.wave_mgr.wave_num - 1) * 6
        factor = TOWER_TYPES[ttype].get("buy_cost_factor", 1.0)
        return max(10, int(round(raw * factor * self.meta.tower_cost_mult())))

    def recalc_tower_cost(self):
        """Recalcula `self.tower_cost`, o preco de referencia (tipo
        "canhao", fator 1.0) usado onde ainda nao se sabe qual tipo o
        jogador vai comprar (ex.: checagem generica de "tem ouro pra
        alguma torre?"). O preco de cada card na loja usa
        `tower_cost_for(ttype)`, nao este valor generico."""
        self.tower_cost = self.tower_cost_for("canhao")

    # ------------------------------------------------------------------
    def max_skippable_wave(self):
        """Onda-marco de boss mais proxima ainda nao superada. Pular pode
        levar o jogador ATE essa onda (ela inclui o boss), mas nao alem
        dela -- so libera pular mais ondas depois que ESSE boss for
        derrotado (`total_bosses_killed` sobe e a proxima onda-marco
        vira o limite)."""
        return (self.total_bosses_killed + 1) * BOSS_WAVE_INTERVAL

    def can_skip_wave(self):
        """Falso quando a onda atual ja alcancou a onda-marco de boss
        pendente: o jogador precisa matar aquele boss antes de poder
        pular de novo (ver `max_skippable_wave`)."""
        return self.wave_mgr.wave_num < self.max_skippable_wave()

    # ------------------------------------------------------------------
    def skip_current_wave(self):
        """Pula para a proxima onda antes da hora. Da um bonus de ouro
        mas a proxima onda passa a vir junto com o que restar da atual
        (mais inimigos na tela ao mesmo tempo = mais dificil). Bloqueado
        se a onda atual ja e a onda-marco de um boss ainda vivo (ver
        `can_skip_wave`)."""
        if self.game_over or self.paused or not self.can_skip_wave():
            return
        bonus = SKIP_WAVE_BASE_BONUS + self.wave_mgr.wave_num * SKIP_WAVE_BONUS_PER_WAVE
        self.gold += bonus
        self.wave_mgr.skip_wave()
        self.recalc_tower_cost()
        cx = WIDTH // 2
        cy = TOP_HUD_HEIGHT + 40
        self.add_floating_text(cx, cy, f"Onda pulada! +{bonus}g", COL_GOLD)

    # ------------------------------------------------------------------
    def update_tower_panel_slide(self, dt):
        """Anima a posicao x do painel deslizando entre aberto/fechado.
        Fechado, o painel fica totalmente fora da tela (nao redimensiona
        o grid); a abinha de abrir/fechar continua acessivel."""
        target_x = WIDTH - TOWER_PANEL_WIDTH if self.tower_panel_open else WIDTH
        step = TOWER_PANEL_SLIDE_SPEED * dt
        if self.tower_panel_x < target_x:
            self.tower_panel_x = min(target_x, self.tower_panel_x + step)
        elif self.tower_panel_x > target_x:
            self.tower_panel_x = max(target_x, self.tower_panel_x - step)

    # ------------------------------------------------------------------
    # ENTRADA (mouse/teclado)
    # ------------------------------------------------------------------
    def toggle_tower_panel(self):
        self.tower_panel_open = not self.tower_panel_open

    # ------------------------------------------------------------------
    # ARVORE DE UPGRADES (caminhos / crosspath / tier 6)
    # ------------------------------------------------------------------
    def tier6_owner(self, ttype):
        """Celula da PRIMEIRA torre que ja tem tier 6 daquele tipo nesta
        partida, ou None -- usado so como informacao (ex.: destaque de
        UI). NAO bloqueia mais compras: o limitador de quantos tier 6 um
        jogador consegue bancar agora e o custo em gemas (TIER6_GEM_COST),
        nao uma trava artificial de "1 por tipo"."""
        for cell, t in self.towers.items():
            if t.ttype == ttype and t.has_ability:
                return cell
        return None

    def path_purchase_state(self, tower, path_index):
        """Tudo que a UI e o clique precisam saber sobre comprar o proximo
        tier de um caminho: (pode_comprar, custo, motivo_do_bloqueio).

        Concentrado aqui de proposito -- desenho (tower_panel) e clique
        (try_click_panel_upgrade) leem da MESMA fonte, entao um botao
        nunca aparece habilitado e recusa a compra (ou vice-versa).

        Retorna (ok, custo_ouro, motivo). O custo em gemas do tier 6 e
        consultado separadamente via `path_upgrade_gem_cost`.
        """
        tier = tower.tiers[path_index] + 1
        if tier > up.MAX_TIER:
            return False, None, "Tier maximo"
        ok, reason = up.can_upgrade(tower.tiers, path_index)
        if not ok:
            return False, None, reason
        cost = self.path_upgrade_cost(tower, path_index)
        if tier == up.MAX_TIER:
            gem_cost = self.path_upgrade_gem_cost(tower, path_index)
            if self.gems < gem_cost:
                return False, cost, f"Requer {gem_cost} gemas"
        if self.gold < cost:
            return False, cost, "Ouro insuficiente"
        return True, cost, ""

    def path_upgrade_gem_cost(self, tower, path_index):
        """Custo em GEMAS de comprar o proximo tier de um caminho -- so
        e diferente de zero quando o proximo tier e o 6 (a "super torre"
        da partida). E o que agora libera o tier 6, no lugar da antiga
        trava de "1 por tipo"."""
        tier = tower.tiers[path_index] + 1
        if tier == up.MAX_TIER:
            return TIER6_GEM_COST
        return 0

    def path_upgrade_cost(self, tower, path_index):
        base = tower.next_tier_cost(path_index)
        if base is None:
            return None
        return max(1, int(round(base * self.meta.upgrade_cost_mult())))

    def selected_tower(self):
        """Torre cujo painel de upgrade esta aberto, ou None se o painel
        esta em modo LOJA.

        UNICA fonte de verdade do modo do painel: desenho
        (ui/tower_panel.py) e clique (handle_click_down) chamam esta
        funcao, nunca leem `selected_tower_cell` cru. Ja existiu um bug em
        que os dois discordavam: se a torre selecionada saia da celula
        (merge ou simples mover de lugar), `selected_tower_cell` ficava
        apontando pra uma celula vazia; o painel DESENHAVA a loja (porque
        testava `in towers`) mas o clique entrava no ramo de upgrade
        (porque testava so `is not None`) e era engolido -- os cards de
        compra apareciam e nao respondiam, sem comprar nem descontar ouro.
        Aqui a selecao obsoleta e limpa na hora, entao os dois lados sempre
        veem o mesmo modo.
        """
        cell = self.selected_tower_cell
        if cell is None:
            return None
        tower = self.towers.get(cell)
        if tower is None:
            self.selected_tower_cell = None  # torre saiu da celula: volta pra loja
            return None
        return tower

    def try_click_panel_upgrade(self, pos):
        """Processa um clique quando o painel esta em modo upgrade
        (uma torre do grid selecionada). Retorna True se o clique foi
        consumido (dentro do painel)."""
        tower = self.selected_tower()
        if tower is None:
            return False
        rects, back_rect, sell_rect = tower_panel.upgrade_button_rects(
            self.tower_panel_x, tower.ttype)
        if back_rect.collidepoint(pos):
            self.selected_tower_cell = None
            return True
        if sell_rect.collidepoint(pos):
            self.sell_tower(self.selected_tower_cell)
            return True
        if not TOWER_TYPES[tower.ttype].get("no_targeting", False):
            for prect, key in tower_panel.target_priority_rects(self.tower_panel_x, tower):
                if prect.collidepoint(pos):
                    if tower.target_priority == key:
                        # clicar na opcao ja ativa volta a "seguir upgrade"
                        # (a mesma logica de effective_target_priority)
                        tower.target_priority = None
                    else:
                        tower.target_priority = key
                    tower.target = None  # reavalia o alvo atual com a regra nova
                    return True
        for rect, path_index in rects:
            if rect.collidepoint(pos):
                ok, cost, reason = self.path_purchase_state(tower, path_index)
                tx, ty = tower.grid_pos()
                if ok:
                    gem_cost = self.path_upgrade_gem_cost(tower, path_index)
                    self.gold -= cost
                    self.gems -= gem_cost
                    tower.buy_path(path_index)
                    tower.invested += cost
                    name = up.tier_def(tower.ttype, path_index, tower.tiers[path_index])["name"]
                    self.add_floating_text(tx, ty - 24, name, COL_MERGE_GLOW)
                elif reason:
                    self.add_floating_text(tx, ty - 24, reason, (255, 140, 140))
                return True
        area = tower_panel.panel_area_rect()
        area.x = self.tower_panel_x
        if area.collidepoint(pos):
            return True  # clique dentro do painel mas fora de botoes: nao fecha
        return False

    def try_click_panel_shop(self, pos):
        """Processa um clique quando o painel esta em modo loja.

        Alem do modo de colocacao persistente (ver `selected_shop_type`),
        um SEGUNDO clique rapido no MESMO card (dentro de
        TOWER_PANEL_DOUBLE_CLICK_MS) e tratado aqui, no MOUSEDOWN, como
        atalho de "compra instantanea": poe uma torre direto na primeira
        celula vazia e desliga o modo de colocacao, sem esperar o
        jogador escolher a celula -- util pra comprar rapido sem mirar.
        Fora isso, so COMECA um drag potencial (dragging_from_panel +
        guarda mouse_down_pos); a decisao entre "foi um clique" (liga/
        desliga `selected_shop_type`) ou "foi um arrasto de verdade"
        (solta uma unica torre onde o mouse estiver) e feita no MOUSEUP,
        em `handle_click_up`, comparando a distancia percorrida (mesmo
        padrao usado pra distinguir clique de arrasto numa torre ja
        colocada, ver CLICK_DRAG_THRESHOLD). Retorna True se o clique
        foi consumido (dentro do painel)."""
        for rect, ttype in tower_panel.shop_card_rects(self.tower_panel_x):
            if rect.collidepoint(pos):
                now = pygame.time.get_ticks()
                pending = self.panel_click_pending
                if pending is not None and pending[0] == ttype and \
                        now - pending[1] <= TOWER_PANEL_DOUBLE_CLICK_MS:
                    # 2o clique rapido no mesmo card: compra instantanea,
                    # cancela o "drag potencial" que o 1o clique comecou
                    # e sai do modo de colocacao (o 1o clique ja tinha
                    # ligado `selected_shop_type` no mouseup dele).
                    self.panel_click_pending = None
                    self.dragging_from_panel = None
                    self.mouse_down_pos = None
                    self.selected_shop_type = None
                    cell = self.first_empty_cell()
                    if cell is not None:
                        self.buy_tower_at(cell, ttype)
                else:
                    self.panel_click_pending = (ttype, now)
                    self.dragging_from_panel = ttype
                    self.mouse_down_pos = pos
                return True
        area = tower_panel.panel_area_rect()
        area.x = self.tower_panel_x
        if area.collidepoint(pos):
            return True
        return False

    def handle_click_down(self, pos):
        if self.game_over:
            return

        # aba de abrir/fechar o painel
        tab = tower_panel.toggle_tab_rect(self.tower_panel_x)
        if tab.collidepoint(pos):
            self.toggle_tower_panel()
            return

        # painel aberto (ou animando pra fora): checa cliques nele primeiro.
        # O modo vem de selected_tower() (mesma funcao que o desenho usa),
        # senao o painel pode mostrar a loja enquanto o clique vai parar no
        # tratamento de upgrade e some sem efeito nenhum.
        if self.tower_panel_x < WIDTH:
            if self.selected_tower() is not None:
                consumed = self.try_click_panel_upgrade(pos)
            else:
                consumed = self.try_click_panel_shop(pos)
            if consumed:
                return

        cell = self.cell_from_pixel(*pos)
        if cell is None:
            return

        # modo de colocacao ativo (card clicado no painel, ver
        # `selected_shop_type`): clicar numa celula valida da grade compra
        # ali direto, na hora, SEM desmarcar o tipo selecionado -- assim
        # da pra clicar em varias celulas em sequencia. So sai do modo de
        # colocacao clicando o mesmo card de novo, escolhendo outro tipo,
        # apertando ESC, ou selecionando uma torre ja colocada (upgrade).
        if self.selected_shop_type is not None:
            if cell in self.towers or cell in self.map_path.cell_set:
                return  # celula ocupada/e caminho: ignora, mantem selecionado
            if self.gold < self.tower_cost_for(self.selected_shop_type):
                cx, cy = (GRID_ORIGIN_X + cell[0] * CELL_SIZE + CELL_SIZE // 2,
                          GRID_ORIGIN_Y + cell[1] * CELL_SIZE + CELL_SIZE // 2)
                self.add_floating_text(cx, cy, "Sem ouro!", COL_RED)
                return
            self.buy_tower_at(cell, self.selected_shop_type)
            return

        if cell in self.towers:
            # comeca um "drag potencial": so vira arrasto de verdade se o
            # mouse se mover o suficiente antes de soltar (ver handle_click_up)
            self.dragging_tower = self.towers[cell]
            self.dragging_tower.being_dragged = True
            self.drag_origin = cell
            self.mouse_down_pos = pos

    def _pos_over_panel(self, pos):
        """True se pos cair sobre a area visivel do painel ou sua aba
        de abrir/fechar (que ficam na frente do grid); usado para nao
        deixar soltar/arrastar uma torre numa celula escondida atras
        do painel aberto."""
        tab = tower_panel.toggle_tab_rect(self.tower_panel_x)
        if tab.collidepoint(pos):
            return True
        if self.tower_panel_x >= WIDTH:
            return False
        area = tower_panel.panel_area_rect()
        area.x = self.tower_panel_x
        return area.collidepoint(pos)

    def handle_click_up(self, pos):
        # soltar uma torre que estava sendo arrastada do painel (compra).
        # Aqui e onde se decide se aquele mousedown no card foi um CLIQUE
        # (liga/troca/desliga `selected_shop_type`, o modo de colocacao
        # persistente) ou um ARRASTO de verdade (solta uma unica torre na
        # celula onde o mouse estiver e NAO altera a selecao persistente
        # -- e uma acao pontual, independente dela).
        if self.dragging_from_panel is not None:
            ttype = self.dragging_from_panel
            self.dragging_from_panel = None
            moved = False
            if self.mouse_down_pos is not None:
                dx = pos[0] - self.mouse_down_pos[0]
                dy = pos[1] - self.mouse_down_pos[1]
                moved = dx * dx + dy * dy > CLICK_DRAG_THRESHOLD ** 2
            self.mouse_down_pos = None
            if moved:
                if not self._pos_over_panel(pos):
                    cell = self.cell_from_pixel(*pos)
                    self.buy_tower_at(cell, ttype)
            else:
                if self.selected_shop_type == ttype:
                    self.selected_shop_type = None  # clicou o mesmo card: desliga
                else:
                    self.selected_shop_type = ttype  # clicou um card novo: troca/liga
            return

        if self.dragging_tower is None:
            return
        cell = self.cell_from_pixel(*pos)
        if cell is not None and self._pos_over_panel(pos):
            cell = None  # soltar sobre o painel = cancela, nao move pra celula escondida
        origin = self.drag_origin
        tower = self.dragging_tower
        tower.being_dragged = False

        # se o mouse mal se moveu desde o clique inicial, trata como um
        # CLIQUE (nao arrasto): seleciona a torre no painel (modo upgrade)
        if self.mouse_down_pos is not None:
            dx = pos[0] - self.mouse_down_pos[0]
            dy = pos[1] - self.mouse_down_pos[1]
            if dx * dx + dy * dy <= CLICK_DRAG_THRESHOLD ** 2:
                self.dragging_tower = None
                self.drag_origin = None
                self.mouse_down_pos = None
                self.selected_tower_cell = origin
                self.selected_shop_type = None  # sai do modo de colocacao ao abrir upgrade
                self.tower_panel_open = True
                return
        self.mouse_down_pos = None

        if cell is None or cell == origin or cell in self.map_path.cell_set:
            self.dragging_tower = None
            self.drag_origin = None
            return

        if cell in self.towers:
            target_tower = self.towers[cell]
            if target_tower is tower:
                pass
            elif target_tower.ttype == tower.ttype:
                merged_tiers = [max(a, b) for a, b in
                                zip(target_tower.tiers, tower.tiers)]
                if target_tower.level == tower.level and up.is_legal_config(merged_tiers):
                    # MERGE! So ocorre quando as duas torres tem o MESMO
                    # nivel: o nivel resultante sobe em 1. Cada CAMINHO da
                    # arvore fica com o maior tier entre as duas (nunca
                    # soma) -- fundir uma 3-0-0 com uma 0-2-0 resulta numa
                    # 3-2-0, que continua legal pelo crosspath.
                    #
                    # Se a combinacao violar o crosspath (ex.: 5-0-0 com
                    # 0-5-0 daria 5-5-0), o merge e PROIBIDO e as torres
                    # so trocam de lugar -- senao daria pra driblar a
                    # regra mais importante da arvore fundindo torres.
                    new_level = target_tower.level + 1
                    target_tower.level = new_level
                    target_tower.tiers = merged_tiers
                    # o ouro investido nas duas torres se soma na
                    # resultante -- senao vender depois de fundir
                    # devolveria so metade do que foi de fato gasto
                    target_tower.invested += tower.invested
                    target_tower.recalc_stats()
                    del self.towers[origin]
                    if self.selected_tower_cell == origin:
                        # a selecao segue a torre resultante do merge
                        self.selected_tower_cell = cell
                    cx, cy = target_tower.grid_pos()
                    self.add_floating_text(cx, cy - 20, f"MERGE! Nv.{new_level}", COL_MERGE_GLOW)
                else:
                    # Niveis diferentes: merge e proibido. As torres apenas
                    # trocam de lugar (nenhuma delas ganha ou perde nivel
                    # ou melhorias).
                    target_tower.col, target_tower.row = origin
                    tower.col, tower.row = cell
                    self.towers[origin] = target_tower
                    self.towers[cell] = tower
                    if self.selected_tower_cell == origin:
                        self.selected_tower_cell = cell
                    elif self.selected_tower_cell == cell:
                        self.selected_tower_cell = origin
            else:
                # tipos diferentes: nao faz nada, volta pro lugar
                pass
        else:
            # mover para celula vazia
            del self.towers[origin]
            tower.col, tower.row = cell
            self.towers[cell] = tower
            if self.selected_tower_cell == origin:
                self.selected_tower_cell = cell

        self.dragging_tower = None
        self.drag_origin = None

    # ------------------------------------------------------------------
    def handle_meta_shop_click(self, pos):
        from .config import META_UPGRADE_DEFS
        rects, close_rect, panel_rect = menus.meta_shop_rects()
        if close_rect.collidepoint(pos):
            self.meta_shop_open = False
            return
        for rect, key in rects:
            if rect.collidepoint(pos):
                cost = self.meta.cost_for_next(key)
                if cost is not None and self.gems >= cost:
                    self.gems -= cost
                    self.meta.buy(key)
                    # aplica imediatamente efeitos que afetam o estado atual
                    if key == "extra_lives":
                        self.lives += META_UPGRADE_DEFS["extra_lives"]["effect_per_level"]
                    if key == "tower_cost":
                        self.recalc_tower_cost()
                    label = META_UPGRADE_DEFS[key]["label"]
                    cx = WIDTH // 2
                    self.add_floating_text(cx, TOP_HUD_HEIGHT + 40, f"{label} melhorado!", COL_GEM)
                    save_system.save_meta(self)
                return
        if not panel_rect.collidepoint(pos):
            self.meta_shop_open = False

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    def update_spikes(self, dt):
        """Colisao entre inimigos e os espinhos plantados no caminho (torre
        "espinhos"): quando um inimigo entra na celula de um espinho vivo,
        leva um acerto. Cada inimigo so pode ser furado por um dado
        espinho uma vez por "passagem" -- usamos um raio pequeno (metade
        da celula) em vez da celula inteira, pra o furo acontecer perto
        do centro em vez de assim que o inimigo encosta na borda."""
        hit_radius = CELL_SIZE * 0.35
        r2 = hit_radius * hit_radius
        # cooldown de "recarga de furo" por espinho, pra nao acertar o
        # mesmo inimigo parado em cima a cada frame (60x/s)
        for t in self.towers.values():
            if t.ttype != "espinhos":
                continue
            for sp in list(t.spikes):
                if not sp.alive or not sp.landed:
                    continue
                sp_cd = sp._cooldown - dt
                if sp_cd > 0:
                    sp._cooldown = sp_cd
                    continue
                for e in self.enemies:
                    if not e.alive or e.flying:
                        continue
                    if (e.x - sp.x) ** 2 + (e.y - sp.y) ** 2 <= r2:
                        sp.try_hit(self, e)
                        sp._cooldown = 0.35  # pequena janela antes de poder furar de novo
                        break

    def _spawn_split(self, parent):
        """Cria os filhotes de um inimigo que "divide ao morrer" (Slime,
        ver `splits_into`/`split_count`/`split_hp_frac` em ENEMY_TYPES).
        Nascem na MESMA posicao do caminho onde o pai morreu (nao voltam
        pro inicio), com uma fracao do HP dele repartida entre todos os
        filhotes -- e por isso que a soma dos HPs dos filhotes e MENOR
        que o HP do pai (`split_hp_frac` < 1), senao dividir seria de
        graca. Cada filhote sai com um pequeno atraso de distancia
        percorrida entre si, soh pra nao aparecerem 100% sobrepostos."""
        kind = parent.splits_into
        count = parent.split_count
        if not kind or count <= 0 or kind not in ENEMY_TYPES:
            return []
        children = []
        hp_frac_each = parent.split_hp_frac / count
        for i in range(count):
            c = Enemy(kind, self.wave_mgr.wave_num, self.wave_mgr.hp_mult(),
                       self.wave_mgr.speed_mult(), self.map_path)
            # reaplica o HP como fracao do MAX_HP JA ESCALADO do pai (nao
            # do base do filhote), entao a divisao acompanha o quao forte
            # o slime original estava nesta onda/mapa
            c.max_hp = max(1.0, parent.max_hp * hp_frac_each)
            c.hp = c.max_hp
            # nasce um pouco antes/depois do ponto onde o pai morreu, pra
            # nao ficarem 100% empilhados um em cima do outro
            spread = (i - (count - 1) / 2.0) * 10.0
            c.dist = max(0.0, parent.dist + spread)
            c.x, c.y, c.angle = self.map_path.point_at_distance(c.dist)
            children.append(c)
        return children

    def update(self, dt):
        self.mouse_pos = self.window_to_canvas(pygame.mouse.get_pos())
        if self.state in ("map_select", "difficulty_select", "main_menu"):
            return
        self.hovered_cell = self.cell_from_pixel(*self.mouse_pos)
        self.update_tower_panel_slide(dt)

        if self.game_over or self.paused:
            self.update_floating_texts(dt)
            return

        # ondas
        self.wave_mgr.update(dt, self.enemies)
        if (not self.wave_mgr.wave_active and not self.enemies and
                self.wave_mgr.time_since_wave_end >= self.wave_mgr.auto_start_delay):
            self.wave_mgr.start_next_wave()
            self.recalc_tower_cost()

        # torres (recebem o proprio Game como "world": e por ele que
        # torres/projeteis/habilidades enxergam inimigos, projeteis e vfx)
        for t in self.towers.values():
            t.update(dt, self)

        # colisao inimigo x espinho: feita aqui (nao dentro de Tower.update)
        # porque precisa varrer os inimigos, que a torre nao enxerga sozinha
        self.update_spikes(dt)

        # habilidades tier 6: rodam DEPOIS das torres pra enxergarem o
        # estado ja atualizado da pista neste frame
        self.abilities.update(self, dt)

        # projeteis
        for p in self.projectiles:
            p.update(dt, self)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # explosoes agendadas (secundarias/encadeadas) e efeitos visuais
        combat.update_pending_blasts(self, dt)
        self.vfx = vfx.update_vfx(self.vfx, dt)
        if self.ability_banner is not None:
            self.ability_banner[1] -= dt
            if self.ability_banner[1] <= 0:
                self.ability_banner = None

        # inimigos: primeiro avanca os que ainda estao vivos (para detectar
        # quem chega ao fim do caminho), depois processa TODOS os que
        # morreram neste frame (seja por dano de projetil ou por chegar
        # ao fim), concedendo ouro/vida perdida uma unica vez cada.
        for e in self.enemies:
            if e.alive:
                e.update(dt)

        spawned_splits = []
        for e in self.enemies:
            if e.alive or e._processed_death:
                continue
            e._processed_death = True
            if e.reached_end:
                if e.try_second_chance(self.meta.second_chance_prob()):
                    self.add_floating_text(e.x, e.y - 22, "SEGUNDA CHANCE!", COL_GEM)
                    continue
                if e.is_boss:
                    # boss que passou de verdade (nao foi salvo pela segunda
                    # chance) e HITKILL: mata na hora, indepenente de
                    # quantas vidas restam.
                    self.lives = 0
                    self._trigger_game_over()
                    continue
                self.lives -= 1
                if self.lives <= 0:
                    self.lives = 0
                    self._trigger_game_over()
            else:
                # morreu por dano de torre
                diff_def = DIFFICULTY_DEFS.get(self.selected_difficulty_id, DIFFICULTY_DEFS[DEFAULT_DIFFICULTY_ID])
                gold_gain = int(round(e.gold * self.meta.gold_mult() * self.map_path.gold_mult * diff_def["gold_mult"]))
                self.gold += gold_gain
                self.total_kills += 1
                self.add_floating_text(e.x, e.y, f"+{gold_gain}g", COL_GOLD)
                if e.is_boss:
                    self.total_bosses_killed += 1
                    if e.gems > 0:
                        gems_gain = max(1, round(e.gems * diff_def["gem_mult"]))
                        self.gems += gems_gain
                        self.add_floating_text(e.x, e.y - 22, f"+{gems_gain} gema{'s' if gems_gain != 1 else ''}", COL_GEM)
                        save_system.save_meta(self)
                if e.splits_into:
                    spawned_splits.extend(self._spawn_split(e))

        self.enemies = [e for e in self.enemies if e.alive] + spawned_splits

        self.update_floating_texts(dt)
        self._autosave_tick(dt)

    # ------------------------------------------------------------------
    # DESENHO
    # ------------------------------------------------------------------
    def draw(self):
        # Tudo desenha no `canvas` logico (resolucao fixa WIDTH x HEIGHT) --
        # exatamente como antes, so que o alvo do blit deixou de ser a
        # janela e passou a ser esse buffer interno. `_present()` no final
        # escala o canvas inteiro pro tamanho real da janela.
        if self.state == "main_menu":
            main_menu.draw_main_menu(self, self.canvas)
            self._present()
            return

        if self.state == "map_select":
            map_menu.draw_map_menu(self, self.canvas)
            self._present()
            return

        if self.state == "difficulty_select":
            difficulty_menu.draw_difficulty_menu(self, self.canvas)
            self._present()
            return

        self.canvas.fill(COL_BG)
        offset = (0, 0)
        board.draw_path(self.canvas, offset, self.map_path)

        for e in self.enemies:
            e.draw(self.canvas, offset)

        for t in self.towers.values():
            if t.ttype == "espinhos":
                for sp in t.spikes:
                    sp.draw(self.canvas, offset)

        for p in self.projectiles:
            p.draw(self.canvas, offset)

        for v in self.vfx:
            v.draw(self.canvas, offset)

        board.draw_grid(self, self.canvas)

        # torres (nao-arrastadas primeiro) -- desenhadas ordenadas por
        # ROW (linha na grade), nao pela ordem de insercao no dict. Sem
        # isso, uma torre "de tras" (row menor, mais pro topo da tela)
        # colocada DEPOIS de uma "da frente" (row maior) desenhava por
        # cima dela, sobrepondo errado (cano/corpo de tras cortando a
        # torre da frente). Ordenando por row, quem esta mais embaixo na
        # tela sempre fica visualmente na frente -- efeito "pintor" comum
        # em jogos top-down como esse.
        for cell, t in sorted(self.towers.items(), key=lambda item: item[1].row):
            if t is not self.dragging_tower:
                t.draw(self.canvas, None, False)

        menus.draw_tower_range_hover(self, self.canvas, offset)

        # torre sendo arrastada por cima de tudo -- o destaque da celula
        # alvo (retangulo colorido indicando merge/troca) precisa ser
        # desenhado ANTES da torre, senao ele fica por cima dela (a torre
        # arrastada acabava parecendo "embaixo da grade" quando passava
        # sobre a celula de destino, mesmo o comentario dizendo "por cima
        # de tudo" -- a ordem do codigo nao batia com a intencao).
        if self.dragging_tower is not None:
            cell = self.hovered_cell
            if cell is not None:
                x = GRID_ORIGIN_X + cell[0] * CELL_SIZE
                y = GRID_ORIGIN_Y + cell[1] * CELL_SIZE
                rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
                target_here = self.towers.get(cell)
                same_type = (target_here is not None and
                             target_here.ttype == self.dragging_tower.ttype and
                             target_here is not self.dragging_tower)
                merge_ok = False
                if same_type:
                    merged = [max(a, b) for a, b in
                              zip(target_here.tiers, self.dragging_tower.tiers)]
                    merge_ok = (target_here.level == self.dragging_tower.level
                                and up.is_legal_config(merged))
                if merge_ok:
                    col = COL_MERGE_GLOW  # merge: mesmo tipo, mesmo nivel, crosspath valido
                elif same_type:
                    col = COL_SWAP_GLOW  # mesmo tipo, nivel diferente: so troca de lugar
                else:
                    col = (120, 120, 130)
                pygame.draw.rect(self.canvas, col, rect.inflate(-4, -4), 3, border_radius=8)
            self.dragging_tower.draw(self.canvas, self.mouse_pos, True)

        # preview da celula alvo enquanto arrasta uma torre nova do painel
        # OU com um tipo selecionado no modo de colocacao (`selected_shop_type`)
        preview_ttype = self.dragging_from_panel or self.selected_shop_type
        if preview_ttype is not None:
            cell = self.hovered_cell
            if cell is not None:
                x = GRID_ORIGIN_X + cell[0] * CELL_SIZE
                y = GRID_ORIGIN_Y + cell[1] * CELL_SIZE
                rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
                valid = cell not in self.towers and cell not in self.map_path.cell_set
                col = COL_MERGE_GLOW if valid else (200, 80, 80)
                pygame.draw.rect(self.canvas, col, rect.inflate(-4, -4), 3, border_radius=8)

        tower_panel.draw_tower_panel(self, self.canvas)
        if preview_ttype is not None and not self._pos_over_panel(self.mouse_pos):
            tower_panel.draw_dragged_card_ghost(self, self.canvas)

        # floating texts
        font_ft = get_font(16, bold=True)
        for x, y, text, color, life in self.floating_texts:
            alpha = max(0, min(255, int(255 * life)))
            surf = font_ft.render(text, True, color)
            surf.set_alpha(alpha)
            self.canvas.blit(surf, (x - surf.get_width() / 2, y))

        hud.draw_hud(self, self.canvas)
        mobile_bar.draw(self, self.canvas)

        # loja de gemas: por cima de absolutamente tudo, inclusive HUD
        menus.draw_meta_shop(self, self.canvas)

        if self.game_over:
            hud.draw_game_over(self, self.canvas)

        self._present()

    def _present(self):
        """Escala o canvas logico (resolucao fixa) pro tamanho real da
        janela e manda pra tela. Fora da area escalada (letterbox), pinta
        de preto -- evita "lixo" do frame anterior nas bordas quando a
        janela tem proporcao diferente da do canvas."""
        self.screen.fill((0, 0, 0))
        if self.render_rect.width > 0 and self.render_rect.height > 0:
            scaled = pygame.transform.smoothscale(
                self.canvas, (self.render_rect.width, self.render_rect.height)
            )
            self.screen.blit(scaled, self.render_rect.topleft)
        pygame.display.flip()

    # ------------------------------------------------------------------
    # LOOP PRINCIPAL
    # ------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)  # evita saltos grandes

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif IS_MOBILE and event.type == getattr(pygame, "APP_WILLENTERBACKGROUND", -1):
                    # o Android pode suspender o app a qualquer momento sem
                    # passar pelo botao Voltar (tecla Home, troca de app,
                    # ligacao recebida...) -- salva na hora, igual ao save
                    # que ja acontecia ao fechar a janela no desktop, senao
                    # esse progresso se perderia.
                    if self.state == "playing" and not self.game_over:
                        self.save_to_disk()
                    save_system.save_meta(self)
                elif event.type == pygame.VIDEORESIZE:
                    # janela livre foi redimensionada (arrastando a borda,
                    # maximizando etc.) -- so recalcula a area de escala;
                    # o canvas logico continua com a mesma resolucao fixa.
                    if not self.is_fullscreen:
                        self.handle_resize(event.size)
                elif event.type == pygame.KEYDOWN:
                    # botao fisico "Voltar" do Android (K_AC_BACK) reusa a
                    # MESMA cascata de ESC (fechar ajuda -> voltar de menu
                    # -> cancelar colocacao -> sair) em vez de duplicar a
                    # logica -- so tratamos como se fosse ESC.
                    if IS_MOBILE and event.key == getattr(pygame, "K_AC_BACK", None):
                        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
                    if event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    elif event.key == pygame.K_ESCAPE and self.state == "main_menu" and self.show_help:
                        self.show_help = False  # ESC fecha o "Como Jogar" antes de sair
                    elif event.key == pygame.K_ESCAPE and self.state == "map_select":
                        self.state = "main_menu"  # ESC volta ao menu principal
                    elif event.key == pygame.K_ESCAPE and self.state == "difficulty_select":
                        self.state = "map_select"  # ESC volta a escolha de mapa
                    elif event.key == pygame.K_ESCAPE and self.selected_shop_type is not None:
                        self.selected_shop_type = None  # cancela o modo de colocacao antes de sair
                    elif event.key == pygame.K_ESCAPE:
                        if IS_MOBILE:
                            # no Android, "sair" de verdade (matar o processo)
                            # nao e o comportamento esperado do botao Voltar
                            # sem nenhum menu aberto -- so minimiza o app,
                            # deixando o sistema operacional decidir se/quando
                            # ele e encerrado (mesmo padrao de qualquer app
                            # Android). Salva antes, pelo mesmo motivo do
                            # APP_WILLENTERBACKGROUND acima: o processo pode
                            # ser encerrado a qualquer momento depois disso.
                            if self.state == "playing" and not self.game_over:
                                self.save_to_disk()
                            save_system.save_meta(self)
                            self._minimize_android()
                        else:
                            running = False
                    elif self.state == "main_menu":
                        pass  # sem atalhos extras; usar os botoes do menu
                    elif self.state == "map_select":
                        pass  # nenhum atalho de teclado no menu de mapas
                    elif self.state == "difficulty_select":
                        pass  # nenhum atalho de teclado no menu de dificuldade
                    elif event.key == pygame.K_p and not self.game_over:
                        self.paused = not self.paused
                    elif event.key == pygame.K_SPACE and not self.game_over:
                        if not self.wave_mgr.wave_active:
                            self.wave_mgr.start_next_wave()
                            self.recalc_tower_cost()
                    elif event.key == pygame.K_n and not self.game_over:
                        self.skip_current_wave()
                    elif event.key == pygame.K_g:
                        self.meta_shop_open = not self.meta_shop_open
                        # fecha outros menus pra nao sobrepor
                        self.selected_tower_cell = None
                        self.selected_shop_type = None
                    elif event.key == pygame.K_t:
                        self.toggle_tower_panel()
                    elif event.key == pygame.K_r and self.game_over:
                        self.state = "map_select"
                    elif event.key == pygame.K_m:
                        # volta ao menu de mapas a qualquer momento
                        self.state = "map_select"
                        self.meta_shop_open = False
                        self.selected_tower_cell = None
                        self.selected_shop_type = None
                        self.dragging_from_panel = None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        # pos convertida de pixel da JANELA pra pixel do
                        # canvas logico -- daqui pra baixo, todo o resto do
                        # jogo (rects de UI, grade, etc.) continua raciocinando
                        # nas mesmas coordenadas fixas de sempre.
                        pos = self.window_to_canvas(event.pos)
                        if self.game_over:
                            if hud.game_over_button_rect().collidepoint(pos):
                                self.state = "map_select"
                        elif self.state == "main_menu":
                            if self.show_help:
                                if main_menu.help_close_rect().collidepoint(pos):
                                    self.show_help = False
                                elif not main_menu.help_panel_rect().collidepoint(pos):
                                    self.show_help = False
                            else:
                                for rect, action in main_menu.button_rects(self):
                                    if rect.collidepoint(pos):
                                        if action == "play":
                                            self.state = "map_select"
                                        elif action == "continue":
                                            self.load_from_disk()
                                        elif action == "help":
                                            self.show_help = True
                                        elif action == "quit":
                                            running = False
                                        break
                        elif self.state == "map_select":
                            if theme.back_button_rect().collidepoint(pos):
                                self.state = "main_menu"
                            else:
                                for rect, map_id in map_menu.map_card_rects():
                                    if rect.collidepoint(pos):
                                        self.choose_map(map_id)
                                        break
                        elif self.state == "difficulty_select":
                            if theme.back_button_rect().collidepoint(pos):
                                self.state = "map_select"
                            else:
                                for rect, diff_id in difficulty_menu.difficulty_card_rects():
                                    if rect.collidepoint(pos):
                                        self.choose_difficulty(diff_id)
                                        break
                        elif self.meta_shop_open:
                            self.handle_meta_shop_click(pos)
                        elif self.gem_button_rect is not None and self.gem_button_rect.collidepoint(pos):
                            self.meta_shop_open = True
                            self.selected_tower_cell = None
                            self.selected_shop_type = None
                        elif self.skip_button_rect is not None and self.skip_button_rect.collidepoint(pos):
                            self.skip_current_wave()
                        elif IS_MOBILE and mobile_bar.handle_tap(self, pos):
                            pass  # toque consumido pela barra mobile (pausa/onda/painel/mapas)
                        else:
                            self.handle_click_down(pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1 and self.state not in ("map_select", "difficulty_select", "main_menu"):
                        self.handle_click_up(self.window_to_canvas(event.pos))

            self.update(dt)
            self.draw()

        # ultimo save antes de fechar de verdade: garante que fechar o
        # jogo (janela, ESC, Alt+F4 etc.) nunca perde o progresso, mesmo
        # que o ultimo autosave periodico ja tenha ficado alguns segundos
        # pra tras (ou nao tenha rodado por causa da pausa).
        if self.state == "playing" and not self.game_over:
            self.save_to_disk()
        # gemas/melhorias permanentes: ja sao salvas a cada mudanca (ver
        # save_system.save_meta), isso aqui e so uma rede de seguranca.
        save_system.save_meta(self)

        pygame.quit()
        sys.exit()