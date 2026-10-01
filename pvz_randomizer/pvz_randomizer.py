# -*- coding: utf-8 -*-
"""
PVZ DECK RANDOMIZER v3.14
Автор: нейросеть (но на самом деле крутой пвзшер, которого вы все так любите)

Полностью автоматический рандомайзер колод для Plants vs Zombies:
  * режим 1 — «возможный»       (проходимая дека, без софтлока)
  * режим 2 — «технически возможный» (рандомому похуй, возможен софтлок)
  * режим 3 — ввод сида         (сид с минусом = технический, без минуса = возможный)

Система сидов как в Minecraft: один и тот же сид => одна и та же дека
на каждом уровне прохождения.

Работает без Cheat Engine: сам находит Plants.exe и правит память
(ctypes/WinAPI), либо отдаёт деку моду LPM, если он запущен.

Запуск: python pvz_randomizer.py   (от администратора, на Windows)
"""

import os
import random
import sys
import time

# Позволять импортировать пакеты как из корня папки, так и через python –m
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def ensure_admin():
    """На Windows перезапустить себя с правами админа (UAC-промпт)."""
    if sys.platform != "win32":
        return
    import ctypes
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    print("Запрашиваю права администратора (нужны для чтения памяти игры)...")
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{a}"' for a in sys.argv), None, 1)
    sys.exit(0)


BANNER = """\
-------------------------------------------------
PVZ DECK RANDOMIZER v3.14
by: нейросеть какая-то (но на самом деле крутой
    пвзшер которого вы все так любите и знаете)
читайте текстовый файл под названием: ЧИТАЙ ТВАРЬ.txt
(если не прочитаете — вас будут проклинать боги рандома)
-------------------------------------------------"""


def clear():
    os.system("cls" if os.name == "nt" else "")


def normalize_seed(raw: str):
    """
    Принимает строку сида. Возвращает (seed_int, mode).
      '12345'    -> (12345, 'possible')     — возможный
      '-12345'   -> (12345, 'technical')    — технически возможный
      ''         -> случайный сид, режим уточняется отдельно
    """
    raw = raw.strip()
    if not raw:
        return None, None
    neg = raw.startswith("-")
    digits = raw.lstrip("-")
    if not digits.isdigit():
        raise ValueError("Сид — это набор цифр (можно с минусом в начале).")
    return int(digits), ("technical" if neg else "possible")


def make_seed_string(seed_int: int, mode: str) -> str:
    return f"-{seed_int}" if mode == "technical" else str(seed_int)


def gen_deck(mode: str, seed_int: int, slots: int, level_name: str):
    from seed_data import possible_deck, technical_deck
    rng = random.Random(seed_int)
    # привязка деки к уровню: один сид = проложенный вариант прохождения,
    # но на РАЗНЫХ уровнях дека разная (как последовательные чанки в МК)
    rng = random.Random(f"{seed_int}:{level_name}")
    if mode == "technical":
        return technical_deck(rng, slots, level_name)
    return possible_deck(rng, slots, level_name)


def print_deck(deck):
    from seed_data import seed_name
    for i, sid in enumerate(deck, 1):
        print(f"   {i:>2}. #{sid:<2} {seed_name(sid)}")


def deliver_deck(deck, log_prefix=""):
    """
    Попытаться доставить деку в игру. Сначала пробуем мод LPM (план А),
    потом прямую запись в память (план Б). Возвращает строку-статус.
    """
    if sys.platform != "win32":
        print(f"{log_prefix}-> Не Windows: дека сгенерирована. Перенеси папку "
              f"pvz_randomizer на ПК с игрой и запусти там — тогда она "
              f"подставится сама.")
        return "manual"

    try:
        import lpm_client
        if lpm_client.is_available():
            if lpm_client.send_deck(deck, auto_start=True):
                print(f"{log_prefix}[LPM] Дека передана моду, плашка пропускается.")
                return "lpm"
    except Exception as e:
        print(f"{log_prefix}[LPM] Не удалось ({e}), пробую память...")

    try:
        import pvz_memory
        mem = pvz_memory.PvzMemory().attach()
    except Exception as e:
        print(f"{log_prefix}[память] Игра не найдена / нет доступа: {e}")
        print(f"{log_prefix}-> Дека сгенерирована, примени её вручную (см. ЧИТАЙ ТВАРЬ.txt)")
        return "manual"

    try:
        n = pvz_memory.wait_for_chooser(mem, timeout=20)
        if n is None:
            print(f"{log_prefix}[память] Плашка выбора семян не появилась за 20 с."
                  f" Дека ниже — примени вручную или включи автопилот (Enter"
                  f" вместо уровня в меню).")
            mem.close()
            return "manual"
        pvz_memory.apply_and_report(mem, deck)
        mem.close()
        return "memory"
    except KeyboardInterrupt:
        mem.close()
        raise
    except Exception as e:
        mem.close()
        print(f"{log_prefix}[память] Ошибка записи: {e}")
        return "manual"


# ------------------------------ МЕНЮ ------------------------------

def choose_mode():
    print("\nВыберите режим:")
    print("  1 — возможный (дека всегда проходима)")
    print("  2 — технически возможный (есть возможность софтлока)")
    print("  3 — ввести сид")
    while True:
        c = input("> ").strip()
        if c in ("1", "2", "3"):
            return c
        print("Пиши 1, 2 или 3, тварь.")


def ask_level():
    lvl = input("Уровень (например 1-1, Enter = следующая волна сама): ").strip()
    return lvl or "auto"


def run_session(mode: str, seed_int: int, slots: int, level_name: str,
                continuous: bool):
    seed_str = make_seed_string(seed_int, mode)
    mode_label = ("технически возможный (возможен софтлок)"
                  if mode == "technical" else "возможный")
    print("\nВаш сид:", seed_str)
    print("Режим:", mode_label)
    print(f"Дека на уровень {level_name}:")
    deck = gen_deck(mode, seed_int, slots, level_name)
    print_deck(deck)
    deliver_deck(deck)
    if continuous:
        print("\nБог рандма следит за игрой: на каждом новом уровне дека"
              " будет подставляться автоматически (Ctrl+C — остановить).")
        watch_loop(mode, seed_int, slots)


def watch_loop(mode, seed_int, slots):
    """Автопилот: ждём появления новой плашки выбора семян и вписываем деку."""
    try:
        import pvz_memory
        mem = pvz_memory.PvzMemory().attach()
    except Exception as e:
        print("Автопилот недоступен:", e)
        return
    last_sig = None
    print("[автопилот] Ищу плашку 'Choose Your Seeds'... (Ctrl+C — выход)")
    try:
        while True:
            try:
                n = mem.slot_count()
                lvl = mem.current_level_id()
                sig = (lvl, tuple(mem.read_slots(n))) if 0 < n <= 10 else None
                if sig and sig != last_sig:
                    name = f"lvl#{lvl}"
                    deck = gen_deck(mode, seed_int, n, name)
                    pvz_memory.apply_and_report(mem, deck)
                    last_sig = sig
            except Exception:
                pass  # игра ещё не на уровне — ждём
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n[автопилот] Остановлен.")
    finally:
        mem.close()


def main_menu():
    clear()
    print(BANNER)
    mode_choice = choose_mode()

    if mode_choice == "1":
        mode = "possible"
        seed_int = random.randint(0, 2**31 - 1)
    elif mode_choice == "2":
        mode = "technical"
        seed_int = random.randint(0, 2**31 - 1)
    else:
        raw = input("Напишите сид: ")
        try:
            seed_int, mode_from_seed = normalize_seed(raw)
        except ValueError as e:
            print(e)
            return main_menu()
        if seed_int is None:
            seed_int = random.randint(0, 2**31 - 1)
            mode = input("Режим (1=возможный, 2=технический): ").strip()
            mode = "technical" if mode == "2" else "possible"
        else:
            mode = mode_from_seed

    slots_raw = input("Слотов на уровне (Enter = 6): ").strip()
    slots = int(slots_raw) if slots_raw.isdigit() else 6
    slots = max(1, min(10, slots))

    level_name = ask_level()
    continuous = level_name == "auto"

    run_session(mode, seed_int, slots, level_name, continuous)
    print("\nУдачной игры!")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ensure_admin()
    if sys.platform != "win32":
        print("Внимание: ты не на Windows. Меню работает, но читать память"
              " игры сможет только скрипт на том ПК, где стоит PvZ.\n")
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nПроклятие богов рандома снято. Пока!")
