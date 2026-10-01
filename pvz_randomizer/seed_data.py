# -*- coding: utf-8 -*-
"""
Данные о растениях и уровнях PvZ (Steam / GOTY версия).

ВАЖНО: числовые id растений ниже соответствуют внутреннему enum SeedType
из декомпилов PvZ. Если на ВАШЕЙ сборке игра ведёт себя странно (ставит
не то растение), поправьте таблицу SEEDS под свою версию — скрипт использует
только эти числа, больше нигде id не «зашиты».
"""

SEEDS = {
    0:  "Горохострел",
    1:  "Подсолнух",
    2:  "Вишнёвая бомба",
    3:  "Орех",
    4:  "Картофельная мина",
    5:  "Снегорохострел",
    6:  "Хомпер",
    7:  "Повторитель",
    8:  "Колючка",
    9:  "Солнечный гриб",
    10: "Дымный гриб",
    11: "Ледяной гриб",
    12: "Гриб-гипнотизёр",
    13: "Дум-гриб",
    14: "Кактус",
    15: "Трёхстрел",
    16: "Бархатцы",
    17: "Водоросль-ловушка",
    18: "Кукурузомёт",
    19: "Магнит-гриб",
    20: "Капустомёт",
    21: "Цветочный горшок",
    22: "Кувшинка",
    23: "Звездоплод",
    24: "Тыква",
    25: "Фонарь",
    26: "Кофейное зерно",
    27: "Чеснок",
    28: "Зонтичный лист",
    29: "Раздвоенный горох",
    30: "Мрачный гриб (Gloom-shroom)",
    31: "Хвост котa (Cattail)",
    32: "Ворошилка (Winter Melon — на твоей сборке сверь!)",
    33: "Гриб-спори (Spick-and-span? сверь под свою версию)",
}

MAX_SEED_ID = max(SEEDS)


def seed_name(sid: int) -> str:
    return SEEDS.get(sid, f"Неизвестное растение #{sid}")


# --- Классификация для режима «возможный» (без софтлока) ---

# Грибы: на дневных уровнях без кофе спят => почти гарантированный софтлок,
# если их слишком много в деке дневного уровня.
MUSHROOMS = {8, 9, 10, 11, 12, 13, 19}

# Не атакуют сами по себе (требуют «базу» или бесполезны одними):
NON_ATTACKING = {21, 22, 24, 25, 26}   # горшок, кувшинка, тыква, фонарь, кофе

# Производят солнце (минимум одно нужно на длинных уровнях):
SUN_PRODUCERS = {1, 9}                 # подсолнух, солнечный гриб

# Обязательные растения для конкретных уровней (ключ — имя уровня "д-к"):
REQUIRED_PLANTS = {
    "3-5": {22},          # вода: без кувшинки ставить нечего
    "4-5": {22},          # вода
    "5-5": {21},          # крыша: без горшка ничего не посадить
    "5-6": {21},
    "5-7": {21},
    "5-8": {21},
    "5-9": {21},
    "5-10": {21},
}


def level_kind(level_name: str) -> str:
    """'water' | 'roof' | 'night' | 'fog' | 'day' — по имени уровня 'д-к'."""
    try:
        day, col = level_name.split("-")
        day, col = int(day), int(col)
    except (ValueError, AttributeError):
        return "day"
    if day == 5 or (day == 4 and col >= 5) or (day == 3 and col >= 6):
        pass
    # Канон: вода — 3-6..3-10, 4-6..4-10(частично), все 5-x; ночь — 2-x и 4-x(ночные)
    if day == 5:
        return "roof"
    if day == 3 and col >= 6:
        return "water"
    if day == 4 and col >= 6:
        return "water"
    if day == 2:
        return "night"
    if day == 4 and col <= 4:
        return "night"
    if day == 5:
        return "roof"
    return "day"


def possible_deck(rng, slots: int, level_name: str):
    """
    Сгенерировать «возможную» (проходимую) колодку из `slots` растений.
    rng — random.Random с уже выставленным сидом.
    Приоритет при нехватке слотов: обязательные растения уровня > солнце >
    бойцы > случайное разнообразие. Все id уникальны (игра иначе дублирует слот).
    """
    kind = level_kind(level_name)
    deck = []

    def add(sid):
        if sid not in deck and len(deck) < slots:
            deck.append(sid)

    # 1. Обязательные растения уровня (кувшинка/горшок)
    for sid in sorted(REQUIRED_PLANTS.get(level_name, ())):
        add(sid)

    # 2. Бойцы: чем меньше слотов, тем важнее они (на 1-2 слотах без них не пройти)
    attackers = [s for s in SEEDS
                 if s not in NON_ATTACKING and s not in MUSHROOMS]
    want_attackers = min(slots, 2 if slots >= 3 else max(1, slots - 1))
    tries = 0
    while sum(1 for s in deck if s in attackers) < want_attackers \
            and len(deck) < slots and tries < 200:
        add(rng.choice(attackers))
        tries += 1

    # 3. Источник солнца (если ещё есть место)
    add(1 if kind != "night" else rng.choice([1, 9]))

    # 4. Дозаполняем случайными уникальными, соблюдая лимит грибов на дню
    tries = 0
    while len(deck) < slots and tries < 500:
        tries += 1
        cand = rng.randint(0, MAX_SEED_ID)
        if cand in deck:
            continue
        if kind in ("day", "water", "roof") and cand in MUSHROOMS:
            if sum(1 for s in deck if s in MUSHROOMS) >= slots // 3:
                continue
        deck.append(cand)

    # 5. Страховка: если рандом уперся (мало свободных id), добираем детерминированно
    if len(deck) < slots:
        for cand in range(MAX_SEED_ID + 1):
            if len(deck) == slots:
                break
            if cand not in deck:
                deck.append(cand)

    rng.shuffle(deck)
    return deck


def technical_deck(rng, slots: int, level_name: str):
    """
    «Технически возможный» режим: рандому похуй.
    Любые растения, повторы допустимы, софтлок возможен.
    Ограничение только одно: id растения существует (игра не падает от id > MAX).
    """
    return [rng.randint(0, MAX_SEED_ID) for _ in range(slots)]
