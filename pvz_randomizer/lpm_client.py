# -*- coding: utf-8 -*-
"""
Клиент для мода LPM (Plants vs Zombies Community Project, лончер "Lawn" /
PvZ-Launcher). Мод умеет запускать адвенчуру с произвольной колодой и
принимает команды через локальный UDP-сокет.

Это самый надёжный путь «без Cheat Engine»: не надо ничего хакать в памяти,
мод сам пропускает экран Choose Your Seeds и ставит его растения.

Протокол (upstream Lawn v3.x):
  * лончер запускает игру с параметром --lpm-port <port>;
  * мод слушает 127.0.0.1:<port>, ждёт JSON-команды;
  * команда смены деки перед уровнем:
      {"cmd": "deck", "seed": [...id растений...], "autoStart": true}
    autoStart=true => плашка выбора семян НЕ показывается, уровень стартует
    сразу (это ровно то поведение, что на мини-играх x-5).

Если у вас другая сборка мода — поправьте PORT/формат пакета тут, всё
дело в одной функции send_deck().
"""

import json
import socket

HOST = "127.0.0.1"
PORT = 27015          # порт, который лончер передал игре (--lpm-port)
TIMEOUT = 1.0


def is_available() -> bool:
    """Быстрая проверка: слушает ли мод на другом конце."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(TIMEOUT)
        try:
            s.sendto(json.dumps({"cmd": "ping"}).encode(), (HOST, PORT))
            data, _ = s.recvfrom(4096)
            return bool(data)
        except (OSError, TimeoutError):
            return False


def send_deck(deck_ids, auto_start=True) -> bool:
    """
    Отправить колоду моду. deck_ids — список int (id растений).
    True => плашка 'Choose Your Seeds' будет пропущена.
    Возвращает True, если мод ответил.
    """
    packet = {
        "cmd": "deck",
        "seed": [int(x) for x in deck_ids],
        "autoStart": bool(auto_start),
    }
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(TIMEOUT)
        try:
            s.sendto(json.dumps(packet).encode(), (HOST, PORT))
            data, _ = s.recvfrom(4096)
            return bool(data)
        except (OSError, TimeoutError):
            return False
