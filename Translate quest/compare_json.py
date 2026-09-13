#!/usr/bin/env python3
"""
Сравнение старого и нового JSON (например, файлов локализации FTB Quests).

Использование:
    python compare_json.py old.json new.json
    python compare_json.py old.json new.json --output diff.json
    python compare_json.py old.json new.json --only-changed
"""

import json
import argparse
import sys
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare(old: dict, new: dict):
    old_keys = set(old.keys())
    new_keys = set(new.keys())

    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    common = old_keys & new_keys

    changed = []
    unchanged = []
    for key in sorted(common):
        if old[key] != new[key]:
            changed.append(key)
        else:
            unchanged.append(key)

    return added, removed, changed, unchanged


def print_report(old, new, added, removed, changed, unchanged, only_changed=False):
    print("=" * 70)
    print(f"Всего ключей: старый={len(old)}  новый={len(new)}")
    print(f"Добавлено: {len(added)}  Удалено: {len(removed)}  "
          f"Изменено: {len(changed)}  Без изменений: {len(unchanged)}")
    print("=" * 70)

    if added and not only_changed:
        print(f"\n--- ДОБАВЛЕНО ({len(added)}) ---")
        for key in added:
            print(f"[+] {key}")
            print(f"      new: {new[key]!r}")

    if removed and not only_changed:
        print(f"\n--- УДАЛЕНО ({len(removed)}) ---")
        for key in removed:
            print(f"[-] {key}")
            print(f"      old: {old[key]!r}")

    if changed:
        print(f"\n--- ИЗМЕНЕНО ({len(changed)}) ---")
        for key in changed:
            print(f"[~] {key}")
            print(f"      old: {old[key]!r}")
            print(f"      new: {new[key]!r}")


def save_report(path, old, new, added, removed, changed):
    result = {
        "added": {k: new[k] for k in added},
        "removed": {k: old[k] for k in removed},
        "changed": {k: {"old": old[k], "new": new[k]} for k in changed},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nОтчёт сохранён в: {path}")


def main():
    parser = argparse.ArgumentParser(description="Сравнение двух JSON-файлов (локализация)")
    parser.add_argument("old", help="Путь к старому JSON")
    parser.add_argument("new", help="Путь к новому JSON")
    parser.add_argument("--output", "-o", help="Сохранить diff в JSON-файл")
    parser.add_argument("--only-changed", action="store_true",
                         help="Показывать только изменённые ключи (без added/removed)")
    args = parser.parse_args()

    if not Path(args.old).exists():
        sys.exit(f"Файл не найден: {args.old}")
    if not Path(args.new).exists():
        sys.exit(f"Файл не найден: {args.new}")

    old = load_json(args.old)
    new = load_json(args.new)

    added, removed, changed, unchanged = compare(old, new)
    print_report(old, new, added, removed, changed, unchanged, args.only_changed)

    if args.output:
        save_report(args.output, old, new, added, removed, changed)


if __name__ == "__main__":
    main()