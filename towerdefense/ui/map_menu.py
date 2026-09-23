"""Tela de selecao de mapa, exibida antes de iniciar/reiniciar a partida.

Mostra um card por mapa (na ordem de maps.MAP_ORDER), cada um com nome,
descricao, estrelas de dificuldade e cor tematica. Escalavel: quando um
mapa novo e adicionado em maps.py, ele aparece aqui automaticamente,
sem precisar mexer neste arquivo.
"""

import math
import pygame

from ..config import (
    WIDTH, HEIGHT, COL_BG, COL_PANEL, COL_GRID_BORDER, COL_WHITE,
    COL_TEXT, COL_TEXT_DIM, COL_GOLD,
)
from ..fonts import get_font
from ..maps import MAP_DEFS, MAP_ORDER
from . import theme


def map_card_rects():
    """Retorna lista de (rect, map_id) para os cards do menu, dispostos
    em uma unica fileira central (ate 4 cards cabem confortavelmente;
    alem disso, quebra em mais de uma linha automaticamente)."""
    n = len(MAP_ORDER)
    card_w, card_h = 260, 300
    gap = 28
    max_per_row = max(1, min(n, (WIDTH - 80) // (card_w + gap)))
    rows = (n + max_per_row - 1) // max_per_row

    rects = []
    for i, map_id in enumerate(MAP_ORDER):
        row = i // max_per_row
        col = i % max_per_row
        items_this_row = min(max_per_row, n - row * max_per_row)
        total_w = items_this_row * card_w + (items_this_row - 1) * gap
        start_x = (WIDTH - total_w) // 2
        total_h = rows * card_h + (rows - 1) * gap
        start_y = (HEIGHT - total_h) // 2 + 30
        x = start_x + col * (card_w + gap)
        y = start_y + row * (card_h + gap)
        rects.append((pygame.Rect(x, y, card_w, card_h), map_id))
    return rects


def draw_stars(surf, x, y, count, max_count=5, size=8, color=COL_GOLD):
    gap = size * 2.6
    for i in range(max_count):
        cx = x + i * gap
        filled = i < count
        pts = []
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5
            r = size if k % 2 == 0 else size * 0.45
            pts.append((cx + r * math.cos(ang), y + r * math.sin(ang)))
        if filled:
            pygame.draw.polygon(surf, color, pts)
        else:
            pygame.draw.polygon(surf, (70, 70, 78), pts, 1)


def draw_map_menu(game, surf):
    theme.vertical_gradient(surf, (0, 0, WIDTH, HEIGHT),
                             theme.shade(COL_BG, 0.08), theme.shade(COL_BG, -0.3))

    font_title = get_font(34, bold=True)
    title = font_title.render("Selecione o Mapa", True, COL_WHITE)
    trect = title.get_rect(center=(WIDTH // 2, 64))
    surf.blit(title, trect)

    font_sub = get_font(14)
    sub = font_sub.render("Cada mapa tem um caminho e uma dificuldade diferentes.", True, COL_TEXT_DIM)
    srect = sub.get_rect(center=(WIDTH // 2, 96))
    surf.blit(sub, srect)

    mouse_pos = game.mouse_pos
    theme.draw_back_button(surf, mouse_pos)
    font_name = get_font(20, bold=True)
    font_diff = get_font(13, bold=True)
    font_desc = get_font(13)
    font_hint = get_font(12)

    for rect, map_id in map_card_rects():
        map_def = MAP_DEFS[map_id]
        accent = map_def["accent_color"]
        hovered = rect.collidepoint(mouse_pos)
        selected = (map_id == game.selected_map_id)

        # cards com hover "levantam" (sombra maior + leve deslocamento
        # pra cima) em vez de so trocar a cor de fundo
        draw_rect = rect.move(0, -4) if hovered else rect
        theme.draw_shadow(surf, draw_rect, radius=14,
                           offset=(0, 10 if hovered else 6),
                           alpha=130 if hovered else 90)

        bg = theme.shade(COL_PANEL, 0.1) if hovered else COL_PANEL
        border_w = 3 if (hovered or selected) else 2
        border_col = accent if (hovered or selected) else COL_GRID_BORDER
        theme.draw_panel(surf, draw_rect, bg, border=border_col, radius=14,
                          border_w=border_w, shadow=False)

        # faixa de cor no topo do card
        top_strip = pygame.Rect(draw_rect.x, draw_rect.y, draw_rect.w, 10)
        pygame.draw.rect(surf, accent, top_strip, border_top_left_radius=14, border_top_right_radius=14)

        # miniatura simples do caminho do mapa
        preview_rect = pygame.Rect(draw_rect.x + 16, draw_rect.y + 24, draw_rect.w - 32, 120)
        pygame.draw.rect(surf, (16, 20, 28), preview_rect, border_radius=8)
        pygame.draw.rect(surf, theme.shade(accent, -0.5), preview_rect, 1, border_radius=8)
        cells = map_def["path_builder"](12, 7)
        if cells:
            max_c = max(c for c, r in cells) or 1
            max_r = max(r for c, r in cells) or 1
            pts = []
            for c, r in cells:
                px = preview_rect.x + 10 + (c / max_c) * (preview_rect.w - 20)
                py = preview_rect.y + 10 + (r / max_r) * (preview_rect.h - 20)
                pts.append((px, py))
            if len(pts) >= 2:
                pygame.draw.lines(surf, accent, False, pts, 4)
            pygame.draw.circle(surf, (140, 220, 140), pts[0], 5)
            pygame.draw.circle(surf, (0, 0, 0), pts[0], 5, 1)
            pygame.draw.circle(surf, (230, 90, 90), pts[-1], 5)
            pygame.draw.circle(surf, (0, 0, 0), pts[-1], 5, 1)

        name_txt = font_name.render(map_def["name"], True, COL_WHITE)
        surf.blit(name_txt, (draw_rect.x + 16, draw_rect.y + 156))

        draw_stars(surf, draw_rect.x + 18, draw_rect.y + 190, map_def["difficulty_stars"], color=accent)
        diff_txt = font_diff.render(map_def["difficulty"], True, accent)
        surf.blit(diff_txt, (draw_rect.x + 16, draw_rect.y + 202))

        # descricao com quebra simples de linha
        words = map_def["desc"].split(" ")
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if font_desc.size(test)[0] > draw_rect.w - 32:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        for i, line in enumerate(lines[:3]):
            ltxt = font_desc.render(line, True, COL_TEXT_DIM)
            surf.blit(ltxt, (draw_rect.x + 16, draw_rect.y + 226 + i * 17))

        play_txt = font_hint.render("Clique para jogar", True, COL_WHITE if hovered else COL_TEXT_DIM)
        prect = play_txt.get_rect(midbottom=(draw_rect.centerx, draw_rect.bottom - 12))
        surf.blit(play_txt, prect)
