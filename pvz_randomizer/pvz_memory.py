# -*- coding: utf-8 -*-
"""
Читы для ванильной PvZ (Steam/GOTY, 32-bit) через Read/WriteProcessMemory.

Это ПЛАН Б: если мод LPM недоступен, скрипт сам находит Plants.exe,
дожидается экрана выбора семян и переписывает слоты в памяти.

Offsets ниже — из публичных таблиц для GOTY-издания Steam. Если у вас
другая версия — правьте только константы в этом файле, логика не тронется.
Как найти свои оффсеты — описано в README.txt (раздел «Где взять адреса»).
"""

import struct
import time

import winmem
from seed_data import seed_name

MODULE_NAME = "Plants.exe"          # имя процесса в диспетчере задач
BASE_SYMBOL = 0x8C0000              # статический адрес базы GOTY-сборки

# Цепочки (в нотации Cheat Engine): [[BASE]+o1]+o2 ...
CHAIN_SEEDPACKET   = [0x9F790, 0x40]   # -> структура SeedPacket текущей плашки
OFF_SLOT_COUNT     = 0x28              # int32: сколько слотов на уровне
OFF_SLOTS_ARRAY    = 0x2C              # дальше идут int32[10] id растений
CHAIN_CURRENT_LEVEL = [0x9F790, 0x8C]  # int32: PvZLevelIdentifier текущего лвла


class PvzMemory:
    def __init__(self, base_symbol=BASE_SYMBOL):
        self.base = base_symbol
        self.h = None
        self.pid = None

    # ---------- подключение ----------
    def attach(self):
        pid = winmem.find_process(MODULE_NAME)
        if pid is None:
            raise RuntimeError(
                f"Процесс {MODULE_NAME} не найден. Сначала запусти игру.")
        self.pid = pid
        self.h = winmem.open_process(pid)
        return self

    def _addr(self, chain):
        return winmem.read_pointer_chain(self.h, self.base, chain)

    # ---------- чтение состояния ----------
    def current_level_id(self):
        try:
            return winmem.read_int(self.h, self._addr(CHAIN_CURRENT_LEVEL))
        except Exception:
            return -1

    def seed_packet_addr(self):
        return self._addr(CHAIN_SEEDPACKET)

    def slot_count(self):
        return winmem.read_int(self.h, self.seed_packet_addr() + OFF_SLOT_COUNT)

    def read_slots(self, n):
        a = self.seed_packet_addr() + OFF_SLOTS_ARRAY
        raw = winmem.read_bytes(self.h, a, 4 * n)
        return list(struct.unpack("<" + "i" * n, raw))

    # ---------- запись деки ----------
    def write_deck(self, deck_ids):
        """Записать колоду в слоты плашки. deck_ids короче/длиннее слотов —
        пишем по количеству фактических слотов уровня."""
        n = self.slot_count()
        if n <= 0 or n > 10:
            raise RuntimeError(f"Странное число слотов: {n}. Неверные оффсеты?")
        a = self.seed_packet_addr() + OFF_SLOTS_ARRAY
        values = []
        for i in range(n):
            values.append(deck_ids[i % len(deck_ids)])
        payload = struct.pack("<" + "i" * n, *values)
        winmem.write_bytes(self.h, a, payload)
        return n

    # ---------- «закрыть» плашку, чтобы уровень стартовал сам ----------
    _last_skip = 0.0

    def skip_seed_chooser(self):
        """
        В ванильной игре плашка живёт, пока её экран активен. Самый простой
        способ «пропустить» её без мыши — послать окну игры WM_LBUTTONDOWN/UP
        по кнопке 'Play' нельзя (адрес кнопки плывёт), поэтому здесь другой
        трюк: записать в поле mSeedChooserState значение CONFIRMED.
        Если на твоей сборке этот трюк не сработает — см. README, раздел
        «План В: hotkeys», там вариант с автокликером по фиксированной точке.
        """
        now = time.time()
        if now - PvzMemory._last_skip < 3.0:
            return True  # уже «подтверждали» — не долбим память каждый кадр
        PvzMemory._last_skip = now
        try:
            chooser = self._addr(CHAIN_SEEDPACKET)  # рядом лежит стейт
            # state-field лежит сразу за массивом слотов: 0x2C + 10*4 = 0x54
            winmem.write_int(self.h, chooser + 0x54, 2)  # 2 = SC_CONFIRMED
            return True
        except Exception:
            return False

    def close(self):
        if self.h:
            winmem.kernel32.CloseHandle(self.h)
            self.h = None


def wait_for_chooser(mem: PvzMemory, timeout=None, poll=0.25):
    """Ждать, пока игра откроет плашку выбора семян (появится валидный
    SeedPacket со слотами). Вернуть число слотов или None по таймауту."""
    start = time.time()
    while timeout is None or time.time() - start < timeout:
        try:
            n = mem.slot_count()
            if 0 < n <= 10:
                slots = mem.read_slots(n)
                # дождёмся, пока игра сама заполнит пресетом (не мусор)
                if all(0 <= s <= 45 for s in slots):
                    return n
        except Exception:
            pass
        time.sleep(poll)
    return None


def apply_and_report(mem: PvzMemory, deck_ids):
    n = mem.write_deck(deck_ids)
    print(f"[память] Записано {n} растений в слоты:")
    for i, sid in enumerate(deck_ids[:n]):
        print(f"   слот {i + 1}: #{sid} {seed_name(sid)}")
    if mem.skip_seed_chooser():
        print("[память] Плашка 'Choose Your Seeds' пропущена — уровень стартует.")
    else:
        print("[память] Пропустить плашку автоматически не вышло — "
              "нажми Enter/Play в игре, растения уже подставлены.")
    return n
