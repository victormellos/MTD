# -*- coding: utf-8 -*-
"""Barra inferior de botoes para compatibilidade mobile/Android.

Em desktop, varios atalhos de teclado (P, ESPACO, N, T, M, ESC) cobrem
acoes que nao tem botao na tela porque o teclado sempre esta disponivel.
Num celular/tablet sem teclado fisico, essas acoes precisam de um botao
tocavel -- e essa barra existe so pra isso: nao substitui nada da logica
do jogo (cada botao so chama o mesmo metodo que o atalho de teclado ja
chamava em game.py), so da um jeito de tocar nele.

So e desenhada/considerada quando `config.IS_MOBILE` for True (ver
config.py); em desktop BOTTOM_HUD_HEIGHT fica 0 e essa barra nunca
aparece nem ocupa espaco.
"""

import pygame

from ..config import (
    WIDTH, HEIGHT, BOTTOM_HUD_HEIGHT,
    COL_PANEL, COL_GRID_BORDER, COL_TEXT, COL_GOLD,
)
from ..fonts import get_font
from . import theme

BAR_Y = HEIGHT - BOTTOM_HUD_HEIGHT
_BUTTON_GAP = 10
_BUTTON_W = 118
_BUTTON_H = BOTTOM_HUD_HEIGHT - 20 if BOTTOM_HUD_HEIGHT else 0


def _button_defs(game):
    """Lista (id, rotulo, habilitado) dos botoes desta tela, na ordem em
    que devem aparecer da esquerda pra direita. So inclui o que faz
    sentido no estado atual (ex.: nao mostra "Pausar" na tela de menu)."""
    if game.state != "playing":
        return []
    defs = [("pause", "Pausa" if not game.paused else "Retomar", not game.game_over)]
    if not game.wave_mgr.wave_active:
        defs.append(("next_wave", "Proxima onda", not game.game_over))
    defs.append(("panel", "Torres", True))
    defs.append(("map_menu", "Mapas", True))
    return defs


def button_rects(game):
    """Retorna [(rect, action_id), ...] pros botoes visiveis agora --
    usado tanto pra desenhar quanto pra resolver toques (mesma fonte da
    verdade, igual ao padrao ja usado em main_menu/map_menu)."""
    defs = _button_defs(game)
    rects = []
    total_w = len(defs) * _BUTTON_W + max(0, len(defs) - 1) * _BUTTON_GAP
    start_x = (WIDTH - total_w) // 2
    y = BAR_Y + (BOTTOM_HUD_HEIGHT - _BUTTON_H) // 2
    for i, (action_id, _label, _enabled) in enumerate(defs):
        rect = pygame.Rect(start_x + i * (_BUTTON_W + _BUTTON_GAP), y, _BUTTON_W, _BUTTON_H)
        rects.append((rect, action_id))
    return rects


def draw(game, surf):
    if BOTTOM_HUD_HEIGHT <= 0:
        return
    bar_rect = pygame.Rect(0, BAR_Y, WIDTH, BOTTOM_HUD_HEIGHT)
    theme.vertical_gradient(surf, bar_rect, theme.shade(COL_PANEL, -0.05), theme.shade(COL_PANEL, -0.2))
    pygame.draw.line(surf, COL_GRID_BORDER, (0, BAR_Y), (WIDTH, BAR_Y), 2)

    font = get_font(16, bold=True)
    defs = {action_id: (label, enabled) for action_id, label, enabled in _button_defs(game)}
    for rect, action_id in button_rects(game):
        label, enabled = defs[action_id]
        label_surf = font.render(label, True, COL_TEXT if enabled else theme.shade(COL_TEXT, -0.4))
        theme.button(surf, rect, game.mouse_pos, COL_GOLD, label_surf, enabled=enabled, radius=10)


def handle_tap(game, pos):
    """Processa um toque na barra mobile. Retorna True se o toque foi
    consumido (caiu em algum botao), pra `game.py` nao tratar o mesmo
    toque tambem como clique na grade."""
    for rect, action_id in button_rects(game):
        if rect.collidepoint(pos):
            _run_action(game, action_id)
            return True
    return False


def _run_action(game, action_id):
    if action_id == "pause" and not game.game_over:
        game.paused = not game.paused
    elif action_id == "next_wave" and not game.game_over:
        if not game.wave_mgr.wave_active:
            game.wave_mgr.start_next_wave()
            game.recalc_tower_cost()
    elif action_id == "panel":
        game.toggle_tower_panel()
    elif action_id == "map_menu":
        game.state = "map_select"
        game.meta_shop_open = False
        game.selected_tower_cell = None
        game.selected_shop_type = None
        game.dragging_from_panel = None
