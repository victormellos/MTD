# -*- coding: utf-8 -*-
"""Sistema de save em disco.

Grava o progresso da partida em andamento num arquivo JSON dentro de
C:\\MTD\\ (no Windows -- exatamente a pasta pedida), para o jogador nunca
perder o progresso so por fechar o jogo/computador. O `Game` chama
`save_game()` periodicamente (autosave) e ao sair; `load_game()` e
`apply_save_data()` sao usados no menu principal para retomar de onde
parou. Gemas e niveis de melhoria permanente ficam num arquivo separado
(`save_meta`/`load_meta`), que nunca e apagado.

IMPORTANTE sobre C:\\MTD no Windows: escrever direto na RAIZ do disco C:
exige permissao de administrador em muitas contas padrao do Windows (e a
causa mais comum do save "nao funcionar" silenciosamente: a pasta nunca
chega a ser criada e toda gravacao falha sem avisar nada na tela do
jogo). Por isso, ao carregar este modulo, `_resolve_save_dir()` TESTA se
consegue mesmo escrever em C:\\MTD; se nao conseguir, cai automaticamente
para uma pasta MTD dentro do perfil do usuario (sempre gravavel, sem
precisar de admin), mantendo a mesma estrutura de arquivos. `SAVE_DIR`
sempre reflete a pasta realmente usada.

Fora do Windows (Linux/Mac, usado so em desenvolvimento/teste, ja que
"C:\\" nao existe la) a mesma pasta MTD cai dentro do HOME do usuario.
"""

import json
import os
import sys
import tempfile
from datetime import datetime

from .config import DEFAULT_DIFFICULTY_ID

SAVE_VERSION = 1
SAVE_FILENAME = "save_game.json"
META_FILENAME = "meta_progress.json"


def _log_error(context, exc):
    """Loga no console (stderr) em vez de falhar 100% em silencio -- se
    ate o diretorio de fallback nao for gravavel, pelo menos fica um
    rastro visivel pra quem rodar o jogo por terminal/console."""
    print(f"[save_system] {context}: {exc!r}", file=sys.stderr)


def _dir_is_writable(path):
    """Testa na pratica se da pra criar `path` e escrever um arquivo
    dentro dele (criar o diretorio sozinho nem sempre basta: em alguns
    casos a pasta e criada mas a escrita de arquivos dentro dela e
    negada)."""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _candidate_dirs():
    # Android (rodando via python-for-android/buildozer): NAO tem uma
    # pasta de usuario "de verdade" tipo Windows/Linux desktop, e o app
    # nao tem permissao de escrever fora da propria area privada sem
    # pedir permissao de armazenamento ao usuario. `ANDROID_PRIVATE` e
    # uma env var que o proprio p4a define com o caminho certo (dados
    # privados do app, sempre gravavel, apagado so se o usuario desinstalar
    # o app) -- ver towerdefense/config.py:IS_MOBILE para a deteccao.
    android_private = os.environ.get("ANDROID_PRIVATE")
    if android_private:
        return [os.path.join(android_private, "MTD")]
    if sys.platform.startswith("win"):
        drive = os.environ.get("SystemDrive", "C:")
        if not drive.endswith(":"):
            drive += ":"
        candidates = [os.path.join(drive + os.sep, "MTD")]
        # fallback: a pasta do usuario (%USERPROFILE%) e sempre gravavel
        # sem precisar de administrador -- ao contrario da raiz do C:\.
        userprofile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        candidates.append(os.path.join(userprofile, "MTD"))
        return candidates
    # Fora do Windows: so a pasta MTD dentro do HOME (dev/teste).
    return [os.path.join(os.path.expanduser("~"), "MTD")]


def _resolve_save_dir():
    candidates = _candidate_dirs()
    for path in candidates:
        if _dir_is_writable(path):
            return path
    # nenhum candidato gravavel (bem raro: disco cheio, politica de
    # grupo bloqueando tudo, etc.) -- usa o primeiro mesmo assim; as
    # gravacoes vao continuar falhando, mas de forma logada (ver
    # _log_error), nunca travando o jogo.
    _log_error("nenhuma pasta de save gravavel encontrada, usando",
                candidates[0])
    return candidates[0]


SAVE_DIR = _resolve_save_dir()
SAVE_PATH = os.path.join(SAVE_DIR, SAVE_FILENAME)
META_PATH = os.path.join(SAVE_DIR, META_FILENAME)


def has_save():
    """True se existe um save valido (arquivo presente) no disco."""
    return os.path.isfile(SAVE_PATH)


def delete_save():
    """Remove o save do disco (ex.: quando a partida termina em game over
    ou o jogador escolhe comecar um jogo novo)."""
    try:
        if os.path.isfile(SAVE_PATH):
            os.remove(SAVE_PATH)
    except OSError as exc:
        _log_error("falha ao apagar save", exc)


def _atomic_write(path, text):
    """Escreve o arquivo de forma atomica (escreve num temporario no
    mesmo diretorio e substitui por cima) para nunca deixar um save
    corrompido/pela metade se o jogo for fechado no meio da escrita."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".save_tmp_", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------
# SERIALIZACAO (Game -> dict) / APLICACAO (dict -> Game)
# ---------------------------------------------------------------------
def _serialize_tower(t):
    return {
        "col": t.col,
        "row": t.row,
        "ttype": t.ttype,
        "level": t.level,
        "tiers": list(t.tiers),
        "invested": t.invested,
        "target_priority": t.target_priority,
    }


def _serialize_enemy(e):
    return {
        "kind": e.kind,
        "spawn_wave": getattr(e, "spawn_wave", 1),
        "hp": e.hp,
        "max_hp": e.max_hp,
        "dist": e.dist,
        "used_second_chance": e.used_second_chance,
    }


def build_save_data(game):
    """Monta o dict serializavel com tudo que define o progresso atual
    de uma partida em andamento. Gemas e niveis de melhoria permanente
    NAO entram aqui -- moram em meta_progress.json (ver build_meta_data),
    que e a unica fonte de verdade pra eles (sobrevive inclusive a um
    game over, ao contrario deste save)."""
    wm = game.wave_mgr
    return {
        "version": SAVE_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "map_id": game.selected_map_id,
        "difficulty_id": getattr(game, "selected_difficulty_id", DEFAULT_DIFFICULTY_ID),
        "gold": game.gold,
        "lives": game.lives,
        "total_kills": game.total_kills,
        "total_bosses_killed": game.total_bosses_killed,
        "paused": game.paused,
        "wave": {
            "wave_num": wm.wave_num,
            "spawn_queue": list(wm.spawn_queue),
            "spawn_timer": wm.spawn_timer,
            "spawn_interval": wm.spawn_interval,
            "wave_active": wm.wave_active,
            "time_since_wave_end": wm.time_since_wave_end,
            "pending_bosses": [list(entry) for entry in wm.pending_bosses],
        },
        "towers": [_serialize_tower(t) for t in game.towers.values()],
        "enemies": [_serialize_enemy(e) for e in game.enemies if e.alive],
    }


def save_game(game):
    """Salva o estado atual da partida em C:\\MTD\\save_game.json (ou
    equivalente fora do Windows). So deve ser chamado com uma partida em
    andamento (state == 'playing', sem game over) -- ver Game._autosave."""
    try:
        data = build_save_data(game)
        _atomic_write(SAVE_PATH, json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except OSError as exc:
        # disco cheio, sem permissao, pasta inacessivel etc.: nao pode
        # derrubar o jogo, mas o erro fica logado pra dar pra investigar.
        _log_error("falha ao salvar partida", exc)
        return False


def load_game():
    """Le o save do disco e retorna o dict, ou None se nao existir ou
    estiver corrompido/incompativel (nesse caso, o arquivo ruim e
    descartado para nao travar autosaves futuros)."""
    if not os.path.isfile(SAVE_PATH):
        return None
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            return None
        return data
    except (OSError, ValueError):
        return None


def apply_save_data(game, data):
    """Restaura o estado de `game` a partir do dict de um save carregado.
    Constroi torres/inimigos/onda de volta a partir dos dados salvos.
    Chamado com o jogo ja tendo passado por `reset()` (ou logo apos
    `__init__`), sobre o mapa correto (ver Game.load_from_disk)."""
    # imports locais para evitar dependencia circular no carregamento
    # do pacote (save_system e importado bem cedo por game.py)
    from .entities import Tower
    from .entities.enemy import Enemy

    game.gold = data.get("gold", game.gold)
    game.lives = data.get("lives", game.lives)
    game.total_kills = data.get("total_kills", 0)
    game.total_bosses_killed = data.get("total_bosses_killed", 0)
    game.paused = data.get("paused", False)

    # gemas e niveis de melhoria permanente NAO vem daqui de proposito:
    # ja foram carregados de meta_progress.json no Game.__init__ (ver
    # save_system.load_meta/apply_meta_data), que e sempre a versao mais
    # atual (salva a cada mudanca, nao so a cada autosave da partida).

    wm = game.wave_mgr
    wm.difficulty_id = getattr(game, "selected_difficulty_id", DEFAULT_DIFFICULTY_ID)
    wdata = data.get("wave") or {}
    wm.wave_num = wdata.get("wave_num", 0)
    wm.spawn_queue = list(wdata.get("spawn_queue", []))
    wm.spawn_timer = wdata.get("spawn_timer", 0.0)
    wm.spawn_interval = wdata.get("spawn_interval", 0.5)
    wm.wave_active = wdata.get("wave_active", False)
    wm.time_since_wave_end = wdata.get("time_since_wave_end", 0.0)
    wm.pending_bosses = [list(entry) for entry in wdata.get("pending_bosses", [])]

    game.towers = {}
    for tdata in data.get("towers", []):
        t = Tower(
            tdata["col"], tdata["row"],
            ttype=tdata.get("ttype", "canhao"),
            level=tdata.get("level", 1),
            tiers=tdata.get("tiers"),
            invested=tdata.get("invested", 0),
        )
        t.target_priority = tdata.get("target_priority")
        game.towers[(t.col, t.row)] = t

    game.enemies = []
    for edata in data.get("enemies", []):
        hp_mult = _hp_mult_for_wave(edata.get("spawn_wave", 1), game.map_path, wm.difficulty_id)
        speed_mult = _speed_mult_for_wave(edata.get("spawn_wave", 1), wm.difficulty_id)
        e = Enemy(edata["kind"], edata.get("spawn_wave", 1), hp_mult, speed_mult, game.map_path)
        e.spawn_wave = edata.get("spawn_wave", 1)
        e.max_hp = edata.get("max_hp", e.max_hp)
        e.hp = edata.get("hp", e.hp)
        e.dist = edata.get("dist", 0.0)
        e.used_second_chance = edata.get("used_second_chance", False)
        e.x, e.y, e.angle = game.map_path.point_at_distance(e.dist)
        if e.hp <= 0:
            continue
        game.enemies.append(e)

    game.recalc_tower_cost()


def _hp_mult_for_wave(n, map_path, difficulty_id):
    # mesma formula de WaveManager.hp_mult, parametrizada pela onda de
    # nascimento do inimigo salvo (ver comentario em WaveManager)
    from .config import DIFFICULTY_DEFS
    diff_def = DIFFICULTY_DEFS.get(difficulty_id, DIFFICULTY_DEFS[DEFAULT_DIFFICULTY_ID])
    base = 1.0 + (n - 1) * 0.18
    return base * map_path.hp_mult * diff_def["enemy_power_mult"]


def _speed_mult_for_wave(n, difficulty_id):
    from .config import DIFFICULTY_DEFS
    diff_def = DIFFICULTY_DEFS.get(difficulty_id, DIFFICULTY_DEFS[DEFAULT_DIFFICULTY_ID])
    base = min(2.2, 1.0 + (n - 1) * 0.015)
    return base * diff_def["enemy_power_mult"]


# ---------------------------------------------------------------------
# PROGRESSO PERMANENTE (gemas + niveis de upgrade permanente)
# ---------------------------------------------------------------------
# Arquivo SEPARADO do save da partida em andamento (save_game.json):
# gemas e os niveis da loja de melhorias permanentes (systems/meta_upgrades)
# nao pertencem a uma corrida especifica -- sobrevivem a fechar o jogo E
# a um game over (o save_game.json normal e apagado no game over, mas
# este NUNCA e). Gravado a cada mudanca real (ganhar gemas, comprar uma
# melhoria), nao por timer, ja que essas mudancas sao raras e pontuais.
def build_meta_data(game):
    return {
        "version": SAVE_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "gems": game.gems,
        "meta_levels": dict(game.meta.levels),
    }


def save_meta(game):
    """Salva so gemas + niveis de melhorias permanentes, em
    C:\\MTD\\meta_progress.json (ou equivalente fora do Windows)."""
    try:
        data = build_meta_data(game)
        _atomic_write(META_PATH, json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except OSError as exc:
        _log_error("falha ao salvar progresso permanente (gemas/upgrades)", exc)
        return False


def load_meta():
    """Le o progresso permanente do disco, ou None se nao existir/estiver
    corrompido/incompativel."""
    if not os.path.isfile(META_PATH):
        return None
    try:
        with open(META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            return None
        return data
    except (OSError, ValueError):
        return None


def apply_meta_data(game, data):
    """Aplica gemas + niveis de melhorias permanentes lidos do disco em
    `game`. Chamado uma vez no Game.__init__, antes do primeiro reset()
    (para o ouro/vidas iniciais ja saírem calculados com os upgrades
    permanentes certos)."""
    game.gems = data.get("gems", game.gems)
    meta_levels = data.get("meta_levels") or {}
    for k, v in meta_levels.items():
        if k in game.meta.levels:
            game.meta.levels[k] = v
