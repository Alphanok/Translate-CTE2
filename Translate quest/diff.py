#!/usr/bin/env python3
r"""
Сравнение .snbt файлов между двумя версиями (старая -> новая).

Запуск: просто дважды кликните по этому файлу.

Скрипт ожидает, что рядом с ним (в той же папке) лежат две подпапки:
    old\   - старая версия
    new\   - новая версия

Если хотите другие имена папок - поменяйте значения OLD_DIR_NAME и
NEW_DIR_NAME ниже, либо запустите из консоли с аргументами:
    python compare_snbt.py <папка_старая> <папка_новая> [-o отчёт.txt]

Формат отчёта по каждому изменённому файлу:
    ИЗМЕНЕНО:
        было:  ...
        стало: ...
    ДОБАВЛЕНО (новые строки):
        + ...
    (если что-то удалили без замены, тоже покажет отдельно)

А в конце - список файлов, которых не было в старой версии (новые файлы),
и файлов, которые пропали (удалённые файлы).
"""

import argparse
import difflib
import os
import sys
from pathlib import Path

# Имена папок по умолчанию (используются при запуске двойным кликом,
# без аргументов командной строки). Папки должны лежать рядом со скриптом.
OLD_DIR_NAME = "old"
NEW_DIR_NAME = "new"
DEFAULT_OUTPUT_NAME = "report.txt"


def find_snbt_files(root: Path) -> dict[str, Path]:
    result = {}
    for path in root.rglob("*.snbt"):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            result[rel] = path
    return result


def read_lines(path: Path) -> list[str]:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return [line.rstrip("\n") for line in f.readlines()]


def classify_changes(old_lines: list[str], new_lines: list[str]):
    """
    Возвращает три списка:
      changed: [(номер_строки_в_старом, старая_строка, номер_строки_в_новом, новая_строка), ...]
      added:   [(номер_строки_в_новом, новая_строка), ...]      - строки, которых не было вообще
      removed: [(номер_строки_в_старом, старая_строка), ...]    - строки, которые убрали без замены

    Номера строк - 1-based (как в текстовом редакторе).
    """
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    changed = []
    added = []
    removed = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old_block = old_lines[i1:i2]
        new_block = new_lines[j1:j2]
        if tag == "replace":
            # сопоставляем построчно, что смогли, остаток - как чистое добавление/удаление
            pair_count = min(len(old_block), len(new_block))
            for k in range(pair_count):
                changed.append((i1 + k + 1, old_block[k], j1 + k + 1, new_block[k]))
            if len(old_block) > pair_count:
                for k in range(pair_count, len(old_block)):
                    removed.append((i1 + k + 1, old_block[k]))
            if len(new_block) > pair_count:
                for k in range(pair_count, len(new_block)):
                    added.append((j1 + k + 1, new_block[k]))
        elif tag == "delete":
            for k, line in enumerate(old_block):
                removed.append((i1 + k + 1, line))
        elif tag == "insert":
            for k, line in enumerate(new_block):
                added.append((j1 + k + 1, line))

    return changed, added, removed


def run_comparison(old_dir: Path, new_dir: Path, output_path: Path):
    if not old_dir.is_dir():
        print(f"Ошибка: папка не найдена: {old_dir}")
        return False
    if not new_dir.is_dir():
        print(f"Ошибка: папка не найдена: {new_dir}")
        return False

    old_files = find_snbt_files(old_dir)
    new_files = find_snbt_files(new_dir)

    old_keys = set(old_files.keys())
    new_keys = set(new_files.keys())

    common = sorted(old_keys & new_keys)
    added_files = sorted(new_keys - old_keys)
    removed_files = sorted(old_keys - new_keys)

    per_file_results = []  # (rel, changed, added, removed)
    unchanged_count = 0

    for rel in common:
        old_lines = read_lines(old_files[rel])
        new_lines = read_lines(new_files[rel])
        changed, added, removed = classify_changes(old_lines, new_lines)
        if not changed and not added and not removed:
            unchanged_count += 1
            continue
        per_file_results.append((rel, changed, added, removed))

    lines_out = []
    lines_out.append("=" * 70)
    lines_out.append("ОТЧЁТ О СРАВНЕНИИ .snbt ФАЙЛОВ")
    lines_out.append(f"Старая версия: {old_dir}")
    lines_out.append(f"Новая версия:  {new_dir}")
    lines_out.append("=" * 70)
    lines_out.append("")
    lines_out.append(f"Всего файлов в старой версии: {len(old_files)}")
    lines_out.append(f"Всего файлов в новой версии:  {len(new_files)}")
    lines_out.append(f"Без изменений: {unchanged_count}")
    lines_out.append(f"Изменено файлов: {len(per_file_results)}")
    lines_out.append(f"Новых файлов: {len(added_files)}")
    lines_out.append(f"Удалённых файлов: {len(removed_files)}")
    lines_out.append("")

    # 1. Изменённые файлы - по каждому: сначала ИЗМЕНЕНО, потом ДОБАВЛЕНО, потом УДАЛЕНО
    lines_out.append("#" * 70)
    lines_out.append("# ИЗМЕНЁННЫЕ ФАЙЛЫ")
    lines_out.append("#" * 70)
    if not per_file_results:
        lines_out.append("(нет изменённых файлов)")
    for rel, changed, added, removed in per_file_results:
        lines_out.append("")
        lines_out.append("-" * 70)
        lines_out.append(f"ФАЙЛ: {rel}")
        lines_out.append("-" * 70)

        if changed:
            lines_out.append("")
            lines_out.append("ИЗМЕНЕНО:")
            for old_num, old_line, new_num, new_line in changed:
                lines_out.append(f"  было  (стр. {old_num}):  {old_line}")
                lines_out.append(f"  стало (стр. {new_num}):  {new_line}")
                lines_out.append("")

        if added:
            lines_out.append("ДОБАВЛЕНО (новые строки):")
            for num, line in added:
                lines_out.append(f"  + (стр. {num}) {line}")
            lines_out.append("")

        if removed:
            lines_out.append("УДАЛЕНО (без замены):")
            for num, line in removed:
                lines_out.append(f"  - (стр. {num}) {line}")
            lines_out.append("")

    # 2. Новые файлы
    lines_out.append("")
    lines_out.append("#" * 70)
    lines_out.append("# НОВЫЕ ФАЙЛЫ (появились в новой версии)")
    lines_out.append("#" * 70)
    if not added_files:
        lines_out.append("(нет новых файлов)")
    for rel in added_files:
        lines_out.append(f"+ {rel}")

    # 3. Удалённые файлы
    lines_out.append("")
    lines_out.append("#" * 70)
    lines_out.append("# УДАЛЁННЫЕ ФАЙЛЫ (были в старой версии, отсутствуют в новой)")
    lines_out.append("#" * 70)
    if not removed_files:
        lines_out.append("(нет удалённых файлов)")
    for rel in removed_files:
        lines_out.append(f"- {rel}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")

    print(f"Готово. Отчёт сохранён в: {output_path.resolve()}")
    print(f"Изменено файлов: {len(per_file_results)}, новых файлов: {len(added_files)}, удалено: {len(removed_files)}")
    return True


def main():
    base_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    # Если скрипт запущен с аргументами командной строки - используем их
    # (это по-прежнему работает, если кому-то нужна консоль).
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Сравнение .snbt файлов между версиями")
        parser.add_argument("old_dir", help="Папка со старой версией")
        parser.add_argument("new_dir", help="Папка с новой версией")
        parser.add_argument("-o", "--output", default=str(base_dir / DEFAULT_OUTPUT_NAME),
                             help="Файл отчёта (по умолчанию report.txt рядом со скриптом)")
        args = parser.parse_args()
        old_dir = Path(args.old_dir)
        new_dir = Path(args.new_dir)
        output_path = Path(args.output)
    else:
        # Запуск двойным кликом: берём папки old/ и new/ рядом со скриптом
        old_dir = base_dir / OLD_DIR_NAME
        new_dir = base_dir / NEW_DIR_NAME
        output_path = base_dir / DEFAULT_OUTPUT_NAME

        if not old_dir.is_dir() or not new_dir.is_dir():
            print("Не найдены папки для сравнения.")
            print(f"Ожидались подпапки рядом со скриптом ({base_dir}):")
            print(f"  - {OLD_DIR_NAME}\\   (старая версия)")
            print(f"  - {NEW_DIR_NAME}\\   (новая версия)")
            print()
            print("Создайте эти папки и положите в них .snbt файлы,")
            print("либо измените OLD_DIR_NAME / NEW_DIR_NAME в начале скрипта,")
            print("либо запустите скрипт из консоли с аргументами:")
            print("    python compare_snbt.py <папка_старая> <папка_новая>")
            input("\nНажмите Enter, чтобы закрыть окно...")
            sys.exit(1)

    run_comparison(old_dir, new_dir, output_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        if len(sys.argv) <= 1:
            input("\nНажмите Enter, чтобы закрыть окно...")