"""Tela de selecao de dificuldade, exibida depois de escolher o mapa e
antes de a partida comecar de verdade (ver Game.start_map/start_game).

Mesmo padrao visual do menu de mapas (map_menu.py): um card por
dificuldade, na ordem de config.DIFFICULTY_ORDER. Escalavel: uma nova
dificuldade adicionada em DIFFICULTY_DEFS/DIFFICULTY_ORDER aparece aqui
automaticamente, sem precisar mexer neste arquivo.
"""

import pygame

from ..config import (
    WIDTH, HEIGHT, COL_BG, COL_PANEL, COL_GRID_BORDER, COL_WHITE,
    COL_TEXT, COL_TEXT_DIM, COL_GOLD, COL_GEM,
    DIFFICULTY_DEFS, DIFFICULTY_ORDER,
)
from ..fonts import get_font
from . import theme

# uma cor de destaque por dificuldade, na mesma ordem de DIFFICULTY_ORDER
# (verde -> vermelho, a progressao usual de "fica mais dificil")
_ACCENT_COLORS = [
    (110, 220, 140),   # pacifico
    (150, 220, 130),   # super_facil
    (170, 210, 110),   # facil
    (110, 190, 255),   # medio
    (230, 170, 90),    # dificil
    (230, 120, 80),    # muito_dificil
    (230, 70, 70),      # morte
]


def _accent_for(index):
    return _ACCENT_COLORS[index % len(_ACCENT_COLORS)]


def difficulty_card_rects():
    """Retorna lista de (rect, difficulty_id), em grade central que
    quebra linha automaticamente (mesma logica de map_menu.map_card_rects)."""
    n = len(DIFFICULTY_ORDER)
    card_w, card_h = 220, 230
    gap = 20
    max_per_row = max(1, min(n, (WIDTH - 80) // (card_w + gap)))
    rows = (n + max_per_row - 1) // max_per_row

    rects = []
    for i, diff_id in enumerate(DIFFICULTY_ORDER):
        row = i // max_per_row
        col = i % max_per_row
        items_this_row = min(max_per_row, n - row * max_per_row)
        total_w = items_this_row * card_w + (items_this_row - 1) * gap
        start_x = (WIDTH - total_w) // 2
        total_h = rows * card_h + (rows - 1) * gap
        start_y = (HEIGHT - total_h) // 2 + 30
        x = start_x + col * (card_w + gap)
        y = start_y + row * (card_h + gap)
        rects.append((pygame.Rect(x, y, card_w, card_h), diff_id))
    return rects


def _fmt_mult(value):
    """Formata um multiplicador como percentual relativo a 1.0x, com
    sinal (+30%, -50%, etc.) -- mais facil de ler que "1.3x" num card
    pequeno."""
    pct = round((value - 1.0) * 100)
    if pct == 0:
        return "padrao"
    return f"{'+' if pct > 0 else ''}{pct}%"


def draw_difficulty_menu(game, surf):
    theme.vertical_gradient(surf, (0, 0, WIDTH, HEIGHT),
                             theme.shade(COL_BG, 0.08), theme.shade(COL_BG, -0.3))

    font_title = get_font(34, bold=True)
    title = font_title.render("Selecione a Dificuldade", True, COL_WHITE)
    trect = title.get_rect(center=(WIDTH // 2, 60))
    surf.blit(title, trect)

    font_sub = get_font(14)
    sub = font_sub.render("Afeta ouro, gemas, quantidade e forca dos inimigos.", True, COL_TEXT_DIM)
    srect = sub.get_rect(center=(WIDTH // 2, 90))
    surf.blit(sub, srect)

    mouse_pos = game.mouse_pos
    theme.draw_back_button(surf, mouse_pos)
    font_name = get_font(17, bold=True)
    font_desc = get_font(11)
    font_stat = get_font(11, bold=True)
    font_hint = get_font(11)

    for i, (rect, diff_id) in enumerate(difficulty_card_rects()):
        d = DIFFICULTY_DEFS[diff_id]
        accent = _accent_for(i)
        hovered = rect.collidepoint(mouse_pos)
        selected = (diff_id == getattr(game, "selected_difficulty_id", None))

        draw_rect = rect.move(0, -4) if hovered else rect
        theme.draw_shadow(surf, draw_rect, radius=14,
                           offset=(0, 10 if hovered else 6),
                           alpha=130 if hovered else 90)

        bg = theme.shade(COL_PANEL, 0.1) if hovered else COL_PANEL
        border_w = 3 if (hovered or selected) else 2
        border_col = accent if (hovered or selected) else COL_GRID_BORDER
        theme.draw_panel(surf, draw_rect, bg, border=border_col, radius=14,
                          border_w=border_w, shadow=False)

        top_strip = pygame.Rect(draw_rect.x, draw_rect.y, draw_rect.w, 8)
        pygame.draw.rect(surf, accent, top_strip, border_top_left_radius=14, border_top_right_radius=14)

        name_txt = font_name.render(d["label"], True, COL_WHITE)
        surf.blit(name_txt, (draw_rect.x + 14, draw_rect.y + 20))

        # descricao com quebra simples de linha
        words = d["desc"].split(" ")
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if font_desc.size(test)[0] > draw_rect.w - 28:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        for li, line in enumerate(lines[:3]):
            ltxt = font_desc.render(line, True, COL_TEXT_DIM)
            surf.blit(ltxt, (draw_rect.x + 14, draw_rect.y + 46 + li * 15))

        # estatisticas: ouro, gemas, qtd. de inimigos, forca -- cada uma
        # com o rotulo e o percentual relativo ao padrao (medio = 100%)
        stats = [
            ("Ouro", d["gold_mult"], COL_GOLD),
            ("Gemas", d["gem_mult"], COL_GEM),
            ("Qtd. inimigos", d["spawn_count_mult"], COL_TEXT),
            ("Forca inimigos", d["enemy_power_mult"], COL_TEXT),
        ]
        stat_y = draw_rect.y + 100
        for label, value, col in stats:
            ltxt = font_stat.render(label, True, COL_TEXT_DIM)
            surf.blit(ltxt, (draw_rect.x + 14, stat_y))
            vtxt = font_stat.render(_fmt_mult(value), True, col)
            vrect = vtxt.get_rect(topright=(draw_rect.right - 14, stat_y))
            surf.blit(vtxt, vrect)
            stat_y += 18

        play_txt = font_hint.render("Clique para jogar", True, COL_WHITE if hovered else COL_TEXT_DIM)
        prect = play_txt.get_rect(midbottom=(draw_rect.centerx, draw_rect.bottom - 10))
        surf.blit(play_txt, prect)
