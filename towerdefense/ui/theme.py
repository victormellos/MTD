"""Pequenos helpers visuais reaproveitados por varios modulos de ui/.

Nao guardam estado (seguindo a convencao do pacote, ver CLAUDE.md) - sao
apenas funcoes de desenho/composicao usadas para dar consistencia visual
(sombras suaves, paineis arredondados com "elevacao", icones simples e
gradientes) sem duplicar o mesmo codigo em hud.py, menus.py, tower_panel.py
etc.
"""

import math
import pygame


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def shade(color, amount):
    """Clareia (amount > 0) ou escurece (amount < 0) uma cor RGB em ate
    +-255*|amount|. amount tipico: -0.4 a 0.4."""
    r, g, b = color[0], color[1], color[2]
    if amount >= 0:
        r = clamp(int(r + (255 - r) * amount), 0, 255)
        g = clamp(int(g + (255 - g) * amount), 0, 255)
        b = clamp(int(b + (255 - b) * amount), 0, 255)
    else:
        f = 1 + amount
        r = clamp(int(r * f), 0, 255)
        g = clamp(int(g * f), 0, 255)
        b = clamp(int(b * f), 0, 255)
    return (r, g, b)


def vertical_gradient(surf, rect, top_color, bottom_color):
    """Preenche `rect` com um degrade vertical simples (uma tira de 1px
    por linha). Barato o suficiente para paineis/fundos de tela inteira
    desenhados uma vez por frame."""
    x, y, w, h = rect
    if h <= 0 or w <= 0:
        return
    band = pygame.Surface((1, h), pygame.SRCALPHA)
    for i in range(h):
        t = i / max(1, h - 1)
        col = (
            int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
            int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
            int(top_color[2] + (bottom_color[2] - top_color[2]) * t),
        )
        band.set_at((0, i), col)
    band = pygame.transform.scale(band, (w, h))
    surf.blit(band, (x, y))


def draw_shadow(surf, rect, radius=12, offset=(0, 4), alpha=90, grow=2):
    """Sombra suave atras de um painel: um retangulo arredondado preto
    semi-transparente, levemente deslocado e maior que o rect original."""
    shadow_rect = pygame.Rect(rect).inflate(grow * 2, grow * 2)
    shadow_rect.x += offset[0]
    shadow_rect.y += offset[1]
    shadow_surf = pygame.Surface((shadow_rect.w, shadow_rect.h), pygame.SRCALPHA)
    pygame.draw.rect(shadow_surf, (0, 0, 0, alpha), (0, 0, shadow_rect.w, shadow_rect.h),
                      border_radius=radius + grow)
    surf.blit(shadow_surf, shadow_rect.topleft)


def draw_panel(surf, rect, fill, border=None, radius=12, border_w=2,
               shadow=True, fill_alpha=255, top_highlight=True):
    """Painel padrao usado em popups/cards/HUD: sombra suave + fundo
    (com leve degrade interno para dar volume) + borda opcional."""
    rect = pygame.Rect(rect)
    if shadow:
        draw_shadow(surf, rect, radius=radius)

    panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    top_col = shade(fill, 0.06)
    bot_col = shade(fill, -0.08)
    # degrade vertical dentro de uma mascara arredondada
    mask = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, rect.w, rect.h), border_radius=radius)
    grad = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    vertical_gradient(grad, (0, 0, rect.w, rect.h), top_col, bot_col)
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    panel.blit(grad, (0, 0))
    if fill_alpha < 255:
        panel.set_alpha(fill_alpha)
    surf.blit(panel, rect.topleft)

    if top_highlight:
        hl = pygame.Surface((rect.w - border_w * 2, 1), pygame.SRCALPHA)
        hl.fill((255, 255, 255, 30))
        surf.blit(hl, (rect.x + border_w, rect.y + border_w))

    if border is not None:
        pygame.draw.rect(surf, border, rect, border_w, border_radius=radius)


def draw_coin_icon(surf, cx, cy, r, color):
    pygame.draw.circle(surf, shade(color, -0.35), (cx, cy + 1), r)
    pygame.draw.circle(surf, color, (cx, cy), r)
    pygame.draw.circle(surf, shade(color, -0.45), (cx, cy), r, 2)
    pygame.draw.circle(surf, shade(color, 0.35), (cx - r * 0.3, cy - r * 0.3), max(1, r * 0.3))


def draw_heart_icon(surf, cx, cy, r, color):
    r = int(r)
    pygame.draw.circle(surf, color, (cx - r // 2, cy - r // 3), r // 2 + 1)
    pygame.draw.circle(surf, color, (cx + r // 2, cy - r // 3), r // 2 + 1)
    pts = [
        (cx - r, cy - r // 4),
        (cx, cy + r),
        (cx + r, cy - r // 4),
    ]
    pygame.draw.polygon(surf, color, pts)


def draw_wave_icon(surf, cx, cy, r, color):
    """Pequena bandeirola/onda estilizada usada ao lado do numero da onda."""
    pygame.draw.line(surf, color, (cx - r, cy + r), (cx - r, cy - r), 2)
    pts = [(cx - r, cy - r), (cx + r, cy - r * 0.4), (cx - r, cy + r * 0.2)]
    pygame.draw.polygon(surf, color, pts)


def draw_shape_icon(surf, cx, cy, r, shape, color):
    """Miniatura da silhueta de uma torre (mesma familia de formas de
    entities/tower.py _shape_points) -- usada nos cards do painel/loja e
    no tooltip, pra bater visualmente com o que aparece na grade.

    Poligono LIMPO e reto, sem jitter/perturbacao nos vertices: a versao
    antiga daqui desenhava cada vertice com um raio levemente aleatorio
    ("wobbly"), o que destoava da regra ja seguida pela torre de verdade
    (torres tortas/rabiscadas nao sao o visual desejado -- ver comentario
    em entities/tower.py) e deixava formas com poucos vertices (quadrado,
    diamond) parecendo deformadas no card de compra. Tambem faltava o
    caso "circle" (canhao): sem ele, essa forma caia no fallback de
    poligono e o icone do canhao saia como um octogono torto em vez de
    um circulo."""
    dark = shade(color, -0.6)

    def _regular(sides, rotation, y_scale=1.0):
        pts = []
        for i in range(sides):
            ang = rotation + i * (2 * math.pi / sides)
            pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r * y_scale))
        return pts

    if shape == "circle":
        pygame.draw.circle(surf, color, (cx, cy), r)
        pygame.draw.circle(surf, dark, (cx, cy), r, 2)
        return
    if shape == "square":
        pts = _regular(4, math.pi / 4)
    elif shape == "triangle":
        pts = _regular(3, -math.pi / 2)
    elif shape == "hexagon":
        pts = _regular(6, math.pi / 6)
    elif shape == "diamond":
        pts = _regular(4, -math.pi / 2, y_scale=1.3)
    else:
        pts = _regular(8, 0.0)  # fallback p/ tipo novo sem forma definida
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, dark, pts, 2)


def button(surf, rect, mouse_pos, base_color, label_surf, enabled=True,
           radius=8, border_w=2):
    """Botao generico com hover: painel + borda que reage ao mouse.
    Retorna True se o mouse esta sobre o botao (para o chamador decidir
    o que fazer no clique - esta funcao so desenha)."""
    rect = pygame.Rect(rect)
    hovered = enabled and rect.collidepoint(mouse_pos)
    fill = shade(base_color, -0.75) if enabled else (36, 36, 40)
    if hovered:
        fill = shade(base_color, -0.6)
    border = base_color if enabled else (80, 80, 86)
    draw_panel(surf, rect, fill, border=border, radius=radius, border_w=border_w,
               shadow=enabled, top_highlight=enabled)
    surf.blit(label_surf, label_surf.get_rect(center=rect.center))
    return hovered


def back_button_rect():
    """Rect do botao 'Voltar' padrao, sempre no canto superior esquerdo
    das telas de menu (map_select, difficulty_select). Existe pra dar
    um jeito tocavel de fazer o que o ESC ja faz no teclado -- essencial
    no mobile, onde nao ha ESC (ver towerdefense/ui/mobile_bar.py)."""
    return pygame.Rect(24, 24, 120, 40)


def draw_back_button(surf, mouse_pos):
    """Desenha o botao 'Voltar' padrao e retorna seu rect (pra o chamador
    testar clique/toque com collidepoint, mesmo padrao dos outros
    *_rects() deste pacote)."""
    from ..fonts import get_font
    rect = back_button_rect()
    label = get_font(15, bold=True).render("< Voltar", True, (235, 235, 240))
    button(surf, rect, mouse_pos, (150, 160, 180), label, radius=9)
    return rect
