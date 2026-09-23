[app]

# ---------------------------------------------------------------------------
# Identidade do app
# ---------------------------------------------------------------------------
title = Tower Defense Infinito
package.name = mtdtowerdefense
package.domain = org.victormellos

# ---------------------------------------------------------------------------
# Codigo-fonte
# ---------------------------------------------------------------------------
source.dir = .
source.include_exts = py
# main.py (ponto de entrada) e todo o pacote towerdefense/ ja ficam
# incluidos automaticamente por estarem dentro de source.dir. Pastas de
# desenvolvimento que NAO devem ir pro APK:
source.exclude_dirs = tests,.git,.buildozer,bin,build,.venv,venv,__pycache__

version = 1.0

# ---------------------------------------------------------------------------
# Dependencias Python que vao dentro do APK
# ---------------------------------------------------------------------------
# pygame puro (sem pygame_ce) e o testado pelo bootstrap sdl2 do p4a.
# Se o build falhar resolvendo "pygame", tentar trocar por "pygame_sdl2"
# (ver README_MOBILE.md, secao "Se o build falhar").
requirements = python3,pygame

# ---------------------------------------------------------------------------
# Orientacao e tela
# ---------------------------------------------------------------------------
# Jogo foi projetado em resolucao fixa 1280x738 (16:9 horizontal, ver
# towerdefense/config.py) e escala com letterbox -- so faz sentido em
# paisagem. "landscape" trava a orientacao (o usuario nao gira pra
# retrato); "sensorLandscape" permitiria girar entre as duas paisagens
# (normal/invertida) se preferir no futuro.
orientation = landscape
fullscreen = 1

# ---------------------------------------------------------------------------
# Icone / splash (opcional)
# ---------------------------------------------------------------------------
# O jogo nao tem nenhum arquivo de imagem (todo o visual e desenhado via
# pygame.draw) -- por isso nao ha um icon.png pronto pra apontar aqui.
# Sem isso, o Android usa um icone generico. Pra usar um icone proprio,
# coloque um PNG (idealmente 512x512) na raiz do projeto e descomente:
# icon.filename = %(source.dir)s/icon.png

# ---------------------------------------------------------------------------
# Permissoes Android
# ---------------------------------------------------------------------------
# O save fica na pasta privada do app (ANDROID_PRIVATE, ver
# towerdefense/save_system.py) -- nao precisa de permissao de
# armazenamento externo pra isso.
android.permissions =

# ---------------------------------------------------------------------------
# SDK / NDK / API
# ---------------------------------------------------------------------------
# Combinacao estavel e amplamente testada com p4a em 2026 (ver
# README_MOBILE.md para instrucoes completas de instalacao do
# SDK/NDK/JDK antes de rodar `buildozer android debug`).
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

# bootstrap SDL2: e o que da suporte a pygame no Android (emula eventos
# de mouse a partir de toque, entre outras coisas) -- NAO trocar por
# "service_only" ou outro bootstrap.
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
