# Build do APK Android (MTD)

Este projeto ja esta preparado (touch, botoes mobile, paisagem forcada,
save no diretorio privado do app) pra rodar como app Android nativo,
empacotado com **Buildozer + python-for-android (p4a)**, bootstrap SDL2.

**Importante:** esse build so roda em **Linux, macOS, ou WSL no Windows**
(o Buildozer nao funciona no Windows nativo). Ele baixa e compila o
Android SDK/NDK na primeira vez, o que costuma levar de 15 a 40 minutos
e alguns GB de download.

## 1. Pre-requisitos (Ubuntu/Debian ou WSL)

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
    autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev \
    libssl-dev build-essential
```

Crie um ambiente virtual e instale o Buildozer:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install buildozer cython
```

## 2. Build

Na raiz do projeto (onde esta o `buildozer.spec`):

```bash
buildozer android debug
```

Na primeira execucao, o Buildozer baixa sozinho o Android SDK, NDK e
todas as dependencias do python-for-android — nao precisa instalar o
Android Studio. Acompanhe o log; se travar pedindo aceite de licenca do
SDK, digite `y` quando solicitado.

O APK final aparece em `bin/mtdtowerdefense-1.0-arm64-v8a_armeabi-v7a-debug.apk`
(o nome exato depende da versao/arquiteturas).

## 3. Instalar no celular

Com o celular conectado via USB e "Depuracao USB" ativada
(Configuracoes > Sobre o telefone > toque 7x em "Numero da versao" pra
ativar "Opcoes do desenvolvedor", depois ative "Depuracao USB" la):

```bash
buildozer android debug deploy run
```

Isso instala e ja abre o jogo no aparelho. Ou instale manualmente
transferindo o `.apk` e habilitando "Instalar apps de fontes
desconhecidas" nas configuracoes do Android.

## 4. Ver logs / debugar no celular

```bash
buildozer android logcat
```

Ou filtrando so o que o Python imprime:

```bash
adb logcat | grep python
```

## Testar o layout mobile no desktop antes de compilar

Nao precisa gerar o APK pra ver como fica a barra de botoes mobile.
Rode no seu computador normalmente, forcando o modo mobile:

```bash
MTD_FORCE_MOBILE=1 python main.py
```

Isso liga a barra de botoes inferior e o layout com `BOTTOM_HUD_HEIGHT`
extra, exatamente como vai aparecer no Android — util pra ajustar visual
sem esperar um build completo (que leva minutos).

## Se o build falhar

- **Erro compilando pygame**: no `buildozer.spec`, troque a linha
  `requirements = python3,pygame` por `requirements = python3,pygame_sdl2`
  (fork do pygame mantido especificamente para Android) e ajuste os
  `import pygame` do projeto para `import pygame_sdl2; pygame_sdl2.import_as_pygame(); import pygame`
  no topo de `main.py` (antes de qualquer outro import).
- **`ANDROIDSDK`/`ANDROIDNDK` nao encontrado**: normalmente o Buildozer
  cuida disso sozinho; se usar SDK/NDK ja instalados manualmente, aponte
  `android.sdk_path` / `android.ndk_path` no `buildozer.spec`.
- **App abre e fecha na hora (crash)**: rode `buildozer android logcat`
  e procure a linha com `Traceback` — geralmente aponta o erro Python
  exato, igual rodando no terminal.
- **Erros de licenca do NDK/SDK**: rode `buildozer android debug` de
  novo depois de aceitar as licencas pedidas (as vezes precisa aceitar
  mais de uma vez em versoes diferentes do build tools).

## O que foi adaptado pra mobile (resumo tecnico)

- `towerdefense/config.py`: `IS_MOBILE` detecta Android automaticamente
  (ou forcado com `MTD_FORCE_MOBILE=1`); liga `BOTTOM_HUD_HEIGHT` pra
  abrir espaco pra barra de botoes.
- `towerdefense/ui/mobile_bar.py` (novo): barra inferior com botoes
  tocaveis (Pausa, Proxima onda, Torres, Mapas) que chamam exatamente
  os mesmos metodos que os atalhos de teclado (P, ESPACO, T, M) ja
  chamavam no desktop.
- Botao "Voltar" tocavel nas telas de selecao de mapa/dificuldade, e
  botao "Escolher outro mapa" na tela de game over (antes so via ESC/R).
- Botao fisico Voltar do Android (`K_AC_BACK`) reaproveita a mesma
  cascata do ESC do desktop.
- ESC/Voltar sem nenhum menu aberto minimiza o app no Android (em vez
  de matar o processo, que nao e o esperado num app mobile) e salva a
  partida antes.
- `towerdefense/save_system.py`: usa a pasta privada do app
  (`ANDROID_PRIVATE`, definida pelo p4a) como local de save no Android,
  em vez de `~/MTD`.
- Toque simples/arrastar (compra, merge de torres, drag do painel):
  **nao precisou de codigo novo** — o bootstrap SDL2 usado pelo
  Buildozer ja traduz eventos de toque em eventos de mouse do pygame
  automaticamente.
- `buildozer.spec` (novo): orientacao travada em paisagem
  (`orientation = landscape`), tela cheia, bootstrap SDL2, API 33 /
  NDK 25b / minSdk 21.

## Limitacoes conhecidas

- So paisagem: o jogo nao tem layout alternativo pra celular em pe (foi
  uma decisao deliberada, nao um bug — ver `orientation = landscape`).
- Sem icone proprio: o projeto nao tem nenhum arquivo de imagem (todo o
  visual e desenhado via `pygame.draw`), entao o APK sai com o icone
  generico do Android. Pra usar um icone proprio, coloque um PNG
  (idealmente 512x512, fundo solido) na raiz do projeto e descomente a
  linha `icon.filename` no `buildozer.spec`.
- Telas muito pequenas (celulares antigos) podem deixar o texto do HUD
  apertado, ja que o canvas logico e fixo (1280x738) e so escala —
  nao ha ainda um segundo layout compacto pra telas pequenas.
