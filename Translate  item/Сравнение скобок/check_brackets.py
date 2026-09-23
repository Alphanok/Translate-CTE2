#!/usr/bin/env python3
"""
Скрипт сравнивает en_us.json и ru_ru.json по количеству [] в значениях:
для каждого общего ключа считает, сколько раз встречается [...] в en
и сколько в ru, и выводит все ключи, где эти числа не совпадают
(включая случай, когда в ru скобок вообще нет, а в en есть).

Ключи с префиксами mmorpg.runeword. и mmorpg.unique_gear. пропускаются.

Использование:
    python check_brackets.py en_us.json ru_ru.json [report.txt]
"""

import json
import re
import sys
from pathlib import Path

# Считает пары квадратных скобок [...] в строке
BRACKET_RE = re.compile(r"\[[^\[\]]*\]")

# Ключи с такими префиксами полностью пропускаются при проверке
SKIP_PREFIXES = (
    "mmorpg.runeword.",
    "mmorpg.unique_gear.",
)


def should_skip(key: str) -> bool:
    return key.startswith(SKIP_PREFIXES)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def flatten(d: dict, prefix: str = "") -> dict:
    """Разворачивает вложенный json в плоский словарь key.path -> value (только строки)."""
    result = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(flatten(v, full_key))
        else:
            result[full_key] = v
    return result


def bracket_count(value) -> int:
    if not isinstance(value, str):
        return 0
    return len(BRACKET_RE.findall(value))


def main():
    if len(sys.argv) not in (3, 4):
        print("Использование: python check_brackets.py en_us.json ru_ru.json [report.txt]")
        sys.exit(1)

    en_path, ru_path = sys.argv[1], sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) == 4 else "report.txt"

    if not Path(en_path).exists() or not Path(ru_path).exists():
        print("Один из файлов не найден.")
        sys.exit(1)

    en_full = flatten(load_json(en_path))
    ru_full = flatten(load_json(ru_path))

    # Отфильтровываем ключи с пропускаемыми префиксами
    en = {k: v for k, v in en_full.items() if not should_skip(k)}
    ru = {k: v for k, v in ru_full.items() if not should_skip(k)}

    skipped_count = (len(en_full) - len(en)) + (len(ru_full) - len(ru))

    en_keys = set(en.keys())
    ru_keys = set(ru.keys())

    common_keys = sorted(en_keys & ru_keys)

    problems_bracket_mismatch = []   # количество [] в en и ru не совпадает

    for key in common_keys:
        en_count = bracket_count(en[key])
        ru_count = bracket_count(ru[key])

        if en_count != ru_count:
            problems_bracket_mismatch.append((key, en_count, ru_count, en[key], ru[key]))

    # ---- Формируем отчёт ----
    lines = []

    def out(s: str = ""):
        lines.append(s)

    out(f"Пропущено ключей (по префиксам {SKIP_PREFIXES}): {skipped_count}")
    out()

    out("=" * 70)
    out("Количество [] в en и ru не совпадает:")
    out("=" * 70)
    if problems_bracket_mismatch:
        for key, en_count, ru_count, en_val, ru_val in problems_bracket_mismatch:
            out(f"  - {key}   en: {en_count}  ru: {ru_count}")
            out(f"      en: {en_val!r}")
            out(f"      ru: {ru_val!r}")
    else:
        out("  Всё в порядке.")

    out()
    total_problems = len(problems_bracket_mismatch)
    out(f"Итого проблем найдено: {total_problems}")

    report_text = "\n".join(lines)

    # Печатаем в консоль и сохраняем в файл
    print(report_text)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_text + "\n")

    print(f"\nОтчёт сохранён в: {out_path}")

    sys.exit(1 if total_problems else 0)


if __name__ == "__main__":
    main()
