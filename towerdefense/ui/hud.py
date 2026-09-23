"""Desenho do HUD (barra de topo) e tela de game over.

Todas as funcoes recebem a instancia do Game (para ler estado como ouro,
vidas, onda atual...) e a Surface onde desenhar. Algumas tambem guardam
de volta no Game os rects dos botoes (gem_button_rect, skip_button_rect)
para que o tratamento de clique em game.py possa reutiliza-los.

Layout do topo (ver `draw_hud`): a barra e dividida em duas fileiras para
nunca deixar texto por baixo de botao -- a fileira de cima tem os 3
numeros principais (ouro/vidas/onda), a de baixo tem status/abates/mapa
a esquerda e os botoes de acao (pular onda, gemas) a direita, cada
cluster com sua propria largura reservada (RIGHT_W) para nao colidir.

Nao ha mais barra/legenda no rodape do mapa (removida a pedido: so tinha
dicas de tecla e a legenda de cores de nivel). Os atalhos de teclado
seguem os mesmos, so pararam de ser listados na tela.
"""

import pygame

from ..config import (
    WIDTH, HEIGHT, TOP_HUD_HEIGHT,
    COL_PANEL, COL_GRID_BORDER, COL_GOLD, COL_GEM, COL_TEXT, COL_TEXT_DIM,
    COL_WHITE, COL_RED, COL_GREEN,
    SKIP_WAVE_BASE_BONUS, SKIP_WAVE_BONUS_PER_WAVE,
)
from ..fonts import get_font
from ..maps import MAP_DEFS
from . import theme


def draw_gem_icon(surf, cx, cy, size):
    """Desenha um icone de gema (corte "esmeralda" facetado, como um
    diamante de verdade): mesa plana no topo, cintura larga e uma
    quilha estreita embaixo, com linhas internas de faceta e um
    brilhinho -- em vez do losango liso de antes."""
    s = size
    top_y = cy - s
    girdle_y = cy - s * 0.15
    bottom_y = cy + s

    # mesa (facetinha plana no topo) + ombros ate a cintura
    table = [
        (cx - s * 0.42, top_y), (cx + s * 0.42, top_y),
        (cx + s * 1.05, girdle_y), (cx - s * 1.05, girdle_y),
    ]
    # corpo inferior (pavilhao) terminando numa quilha em ponta
    pavilion = [
        (cx - s * 1.05, girdle_y), (cx + s * 1.05, girdle_y),
        (cx, bottom_y),
    ]

    fill_light = theme.shade(COL_GEM, 0.35)
    fill_dark = theme.shade(COL_GEM, -0.25)

    pygame.draw.polygon(surf, fill_light, table)
    pygame.draw.polygon(surf, fill_dark, pavilion)

    outline = (18, 26, 36)
    pygame.draw.polygon(surf, outline, table, 1)
    pygame.draw.polygon(surf, outline, pavilion, 1)

    # linhas de faceta internas do pavilhao (do meio da cintura ate a quilha)
    facet_col = theme.shade(COL_GEM, -0.05)
    pygame.draw.line(surf, facet_col, (cx - s * 0.5, girdle_y), (cx, bottom_y), 1)
    pygame.draw.line(surf, facet_col, (cx + s * 0.5, girdle_y), (cx, bottom_y), 1)

    # brilho: um pequeno triangulo claro no canto superior esquerdo da mesa
    glint = [
        (cx - s * 0.30, top_y + s * 0.12),
        (cx - s * 0.02, top_y + s * 0.12),
        (cx - s * 0.20, girdle_y - s * 0.05),
    ]
    pygame.draw.polygon(surf, (255, 255, 255), glint)


def draw_hud(game, surf):
    font_big = get_font(23, bold=True)
    font_med = get_font(17, bold=True)
    font_small = get_font(14)
    font_tiny = get_font(12)

    # --- barra de fundo do topo, com leve degrade + linha de borda ---
    theme.vertical_gradient(surf, (0, 0, WIDTH, TOP_HUD_HEIGHT),
                             theme.shade(COL_PANEL, 0.08), theme.shade(COL_PANEL, -0.1))
    pygame.draw.line(surf, COL_GRID_BORDER, (0, TOP_HUD_HEIGHT), (WIDTH, TOP_HUD_HEIGHT), 2)

    # ------------------------------------------------------------------
    # FILEIRA 1 (y ~14-38): ouro, vidas, onda -- os 3 numeros principais
    # ------------------------------------------------------------------
    theme.draw_coin_icon(surf, 30, 26, 10, COL_GOLD)
    gold_txt = font_big.render(f"{int(game.gold)}", True, COL_GOLD)
    surf.blit(gold_txt, (46, 16))

    lives_color = COL_GREEN if game.lives > 5 else COL_RED
    theme.draw_heart_icon(surf, 236, 26, 10, lives_color)
    lives_txt = font_big.render(f"{game.lives}", True, lives_color)
    surf.blit(lives_txt, (252, 16))

    wave_txt = font_big.render(f"Onda {game.wave_mgr.wave_num}", True, COL_TEXT)
    surf.blit(wave_txt, (400, 16))

    # ------------------------------------------------------------------
    # FILEIRA 2 (y ~48-64): status da onda (sob "Onda"), abates + mapa
    # ------------------------------------------------------------------
    if game.wave_mgr.wave_active:
        status = f"Em andamento - {len(game.enemies)} vivos"
        scol = COL_TEXT
    else:
        remaining = max(0, game.wave_mgr.auto_start_delay - game.wave_mgr.time_since_wave_end)
        status = f"Proxima em {remaining:0.1f}s (ESPACO)"
        scol = COL_TEXT_DIM
    status_txt = font_small.render(status, True, scol)
    surf.blit(status_txt, (400, 48))

    info_x = 620
    kills_txt = font_small.render(f"Abates: {game.total_kills}", True, COL_TEXT_DIM)
    surf.blit(kills_txt, (info_x, 16))

    map_name = MAP_DEFS[game.selected_map_id]["name"]
    map_txt = font_small.render(f"Mapa: {map_name} (M)", True, COL_TEXT_DIM)
    surf.blit(map_txt, (info_x, 40))

    # ocupacao dos slots de tier 6 (um por TIPO de torre): mostra de
    # relance quais super torres ja foram gastas na partida, que e a
    # decisao mais irreversivel do jogo
    _draw_tier6_slots(game, surf, info_x + 150, 20)

    # ------------------------------------------------------------------
    # CLUSTER DIREITO: largura reservada (RIGHT_W) para nunca colidir com
    # o texto de abates/mapa a esquerda, nao importa o tamanho da janela.
    # ------------------------------------------------------------------
    # gemas: recurso mais valioso do jogo, ganho matando bosses.
    # tambem funciona como botao para abrir o shop de melhorias (G).
    gem_rect = pygame.Rect(0, 0, 136, 34)
    gem_rect.topright = (WIDTH - 20, 12)
    game.gem_button_rect = gem_rect
    gem_hovered = gem_rect.collidepoint(game.mouse_pos)
    gem_fill = theme.shade(COL_GEM, -0.72) if not gem_hovered else theme.shade(COL_GEM, -0.6)
    theme.draw_panel(surf, gem_rect, gem_fill, border=COL_GEM, radius=9)
    draw_gem_icon(surf, gem_rect.x + 20, gem_rect.centery, 8)
    gem_txt = font_med.render(f"{game.gems}", True, COL_GEM)
    surf.blit(gem_txt, (gem_rect.x + 36, gem_rect.centery - gem_txt.get_height() // 2))
    key_txt = font_tiny.render("(G)", True, theme.shade(COL_GEM, -0.15))
    krect = key_txt.get_rect()
    krect.midright = (gem_rect.right - 10, gem_rect.centery)
    surf.blit(key_txt, krect)

    cost_txt = font_tiny.render(f"Torre nova: {game.tower_cost}g", True, COL_TEXT_DIM)
    crect = cost_txt.get_rect()
    crect.topright = (gem_rect.right, gem_rect.bottom + 4)
    surf.blit(cost_txt, crect)

    # botao de pular onda (da ouro extra, mas antecipa a proxima onda).
    # Fica desabilitado (cinza, sem hover) enquanto o jogo esta pausado
    # OU enquanto a onda atual ja e a onda-marco de um boss ainda vivo
    # (ver Game.can_skip_wave/max_skippable_wave) -- so libera de novo
    # depois que aquele boss for derrotado.
    bonus = SKIP_WAVE_BASE_BONUS + game.wave_mgr.wave_num * SKIP_WAVE_BONUS_PER_WAVE
    boss_locked = not game.can_skip_wave()
    disabled = game.paused or boss_locked
    btn_w, btn_h = 196, 34
    btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
    btn_rect.topright = (gem_rect.left - 14, gem_rect.top)
    game.skip_button_rect = None if disabled else btn_rect
    if game.paused:
        label = "Pular onda (N)"
    elif boss_locked:
        label = "Pular onda (N)   Derrote o boss!"
    else:
        label = f"Pular onda (N)   +{bonus}g"
    txt_col = COL_GOLD if not disabled else COL_TEXT_DIM
    btn_txt = font_small.render(label, True, txt_col)
    theme.button(surf, btn_rect, game.mouse_pos, COL_GOLD, btn_txt, enabled=not disabled, radius=9)

    # anuncio de habilidade tier 6 disparada pela IA: como o jogador nao
    # clica pra ativar, sem esse aviso o efeito parece acontecer "do nada"
    if getattr(game, "ability_banner", None) is not None:
        name, life = game.ability_banner
        alpha = max(0, min(255, int(255 * min(1.0, life))))
        a_txt = font_med.render(name, True, (255, 230, 140))
        a_txt.set_alpha(alpha)
        arect = a_txt.get_rect(center=(WIDTH // 2, TOP_HUD_HEIGHT + 52))
        surf.blit(a_txt, arect)

    if game.paused:
        p_txt = font_big.render("PAUSADO (P para continuar)", True, COL_WHITE)
        rect = p_txt.get_rect(center=(WIDTH // 2, TOP_HUD_HEIGHT + 24))
        pad_rect = rect.inflate(24, 12)
        theme.draw_panel(surf, pad_rect, (30, 20, 10), border=COL_GOLD, radius=8)
        surf.blit(p_txt, rect)


def _draw_tier6_slots(game, surf, x, y):
    """Cinco quadradinhos, um por tipo de torre: aceso = o tier 6 daquele
    tipo ja existe na partida (limite de 1 por tipo, 5 no total)."""
    from ..config import TOWER_TYPE_KEYS
    font = get_font(11)
    used = {t.ttype for t in game.towers.values() if t.has_ability}
    surf.blit(font.render("Tier 6", True, COL_TEXT_DIM), (x, y - 14))
    size = 14
    for i, key in enumerate(TOWER_TYPE_KEYS):
        rect = pygame.Rect(x + i * (size + 5), y + 2, size, size)
        if key in used:
            pygame.draw.rect(surf, (255, 225, 120), rect, border_radius=3)
        else:
            pygame.draw.rect(surf, (44, 50, 62), rect, border_radius=3)
            pygame.draw.rect(surf, (70, 76, 90), rect, 1, border_radius=3)
    cnt = font.render(f"{len(used)}/5", True, COL_TEXT_DIM)
    surf.blit(cnt, (x + 5 * (size + 5) + 4, y + 3))


def draw_game_over(game, surf):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((6, 6, 10, 195))
    surf.blit(overlay, (0, 0))

    panel_rect = pygame.Rect(0, 0, 560, 300)
    panel_rect.center = (WIDTH // 2, HEIGHT // 2)
    theme.draw_panel(surf, panel_rect, (26, 18, 20), border=COL_RED, radius=16, border_w=3)

    font_big = get_font(52, bold=True)
    font_med = get_font(24)
    t1 = font_big.render("GAME OVER", True, COL_RED)
    r1 = t1.get_rect(center=(WIDTH // 2, panel_rect.y + 64))
    surf.blit(t1, r1)
    t2 = font_med.render(f"Voce sobreviveu ate a onda {game.wave_mgr.wave_num}", True, COL_TEXT)
    r2 = t2.get_rect(center=(WIDTH // 2, panel_rect.y + 132))
    surf.blit(t2, r2)
    t3 = font_med.render(f"Total de abates: {game.total_kills}", True, COL_TEXT_DIM)
    r3 = t3.get_rect(center=(WIDTH // 2, panel_rect.y + 170))
    surf.blit(t3, r3)

    # botao tocavel (equivalente ao atalho de teclado R) -- essencial no
    # mobile, onde nao ha tecla R; ver game_over_button_rect().
    btn_rect = game_over_button_rect(panel_rect)
    btn_label = font_med.render("Escolher outro mapa", True, COL_WHITE)
    theme.button(surf, btn_rect, game.mouse_pos, COL_GOLD, btn_label, radius=10)
    hint = get_font(13).render("(ou aperte R)", True, COL_TEXT_DIM)
    hrect = hint.get_rect(midtop=(WIDTH // 2, btn_rect.bottom + 6))
    surf.blit(hint, hrect)


def game_over_button_rect(panel_rect=None):
    """Rect do botao 'Escolher outro mapa' na tela de game over. Aceita
    o panel_rect ja calculado (evita recalcular) ou recalcula sozinho se
    chamado so pra testar clique/toque, como os outros *_rect() do pacote."""
    if panel_rect is None:
        panel_rect = pygame.Rect(0, 0, 560, 300)
        panel_rect.center = (WIDTH // 2, HEIGHT // 2)
    rect = pygame.Rect(0, 0, 260, 46)
    rect.center = (WIDTH // 2, panel_rect.y + 230)
    return rect
