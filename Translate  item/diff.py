

import argparse
import json
import os
import sys
from pathlib import Path


OLD_DIR_NAME = "old"
NEW_DIR_NAME = "new"
DEFAULT_OUTPUT_NAME = "report_json.txt"


def find_json_files(root: Path) -> dict[str, Path]:
    result = {}
    for path in root.rglob("*.json"):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            result[rel] = path
    return result


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return json.load(f)


def flatten(obj, prefix: str = "") -> dict:

    flat = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}.{k}" if prefix else str(k)
            flat.update(flatten(v, new_key))
    else:
        flat[prefix] = obj
    return flat


def compare_files(old_path: Path, new_path: Path):

    old_data = load_json(old_path)
    new_data = load_json(new_path)

    old_flat = flatten(old_data)
    new_flat = flatten(new_data)

    old_keys = set(old_flat.keys())
    new_keys = set(new_flat.keys())

    changed = []
    for key in sorted(old_keys & new_keys):
        if old_flat[key] != new_flat[key]:
            changed.append((key, old_flat[key], new_flat[key]))

    added = [(key, new_flat[key]) for key in sorted(new_keys - old_keys)]
    removed = [(key, old_flat[key]) for key in sorted(old_keys - new_keys)]

    return changed, added, removed


def format_value(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def run_comparison(old_dir: Path, new_dir: Path, output_path: Path):
    if not old_dir.is_dir():
        print(f"Ошибка: папка не найдена: {old_dir}")
        return False
    if not new_dir.is_dir():
        print(f"Ошибка: папка не найдена: {new_dir}")
        return False

    old_files = find_json_files(old_dir)
    new_files = find_json_files(new_dir)

    old_keys = set(old_files.keys())
    new_keys = set(new_files.keys())

    common = sorted(old_keys & new_keys)
    added_files = sorted(new_keys - old_keys)
    removed_files = sorted(old_keys - new_keys)

    per_file_results = []  # (rel, changed, added, removed)
    parse_errors = []      # (rel, error_message)
    unchanged_count = 0

    for rel in common:
        try:
            changed, added, removed = compare_files(old_files[rel], new_files[rel])
        except json.JSONDecodeError as e:
            parse_errors.append((rel, str(e)))
            continue
        if not changed and not added and not removed:
            unchanged_count += 1
            continue
        per_file_results.append((rel, changed, added, removed))

    lines_out = []
    lines_out.append("=" * 70)
    lines_out.append("ОТЧЁТ О СРАВНЕНИИ .json ФАЙЛОВ")
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
    if parse_errors:
        lines_out.append(f"Не удалось разобрать как JSON: {len(parse_errors)}")
    lines_out.append("")

    # 1. Изменённые файлы
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
            for key, old_v, new_v in changed:
                lines_out.append(f'  "{key}": {format_value(old_v)}  ->  {format_value(new_v)}')

        if added:
            lines_out.append("")
            lines_out.append("ДОБАВЛЕНО (новые ключи):")
            for key, v in added:
                lines_out.append(f'  + "{key}": {format_value(v)}')

        if removed:
            lines_out.append("")
            lines_out.append("УДАЛЕНО (ключей нет в новой версии):")
            for key, v in removed:
                lines_out.append(f'  - "{key}": {format_value(v)}')


    lines_out.append("")
    lines_out.append("#" * 70)
    lines_out.append("# НОВЫЕ ФАЙЛЫ (появились в новой версии)")
    lines_out.append("#" * 70)
    if not added_files:
        lines_out.append("(нет новых файлов)")
    for rel in added_files:
        lines_out.append(f"+ {rel}")


    lines_out.append("")
    lines_out.append("#" * 70)
    lines_out.append("# УДАЛЁННЫЕ ФАЙЛЫ (были в старой версии, отсутствуют в новой)")
    lines_out.append("#" * 70)
    if not removed_files:
        lines_out.append("(нет удалённых файлов)")
    for rel in removed_files:
        lines_out.append(f"- {rel}")


    if parse_errors:
        lines_out.append("")
        lines_out.append("#" * 70)
        lines_out.append("# ФАЙЛЫ, КОТОРЫЕ НЕ УДАЛОСЬ РАЗОБРАТЬ КАК JSON")
        lines_out.append("#" * 70)
        for rel, err in parse_errors:
            lines_out.append(f"! {rel}: {err}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")

    print(f"Готово. Отчёт сохранён в: {output_path.resolve()}")
    print(f"Изменено файлов: {len(per_file_results)}, новых: {len(added_files)}, удалено: {len(removed_files)}")
    return True


def main():
    base_dir = Path(os.path.dirname(os.path.abspath(__file__)))


    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Сравнение .json файлов между версиями (по ключам)")
        parser.add_argument("old_dir", help="Папка со старой версией")
        parser.add_argument("new_dir", help="Папка с новой версией")
        parser.add_argument("-o", "--output", default=str(base_dir / DEFAULT_OUTPUT_NAME),
                             help="Файл отчёта (по умолчанию report_json.txt рядом со скриптом)")
        args = parser.parse_args()
        old_dir = Path(args.old_dir)
        new_dir = Path(args.new_dir)
        output_path = Path(args.output)
    else:

        old_dir = base_dir / OLD_DIR_NAME
        new_dir = base_dir / NEW_DIR_NAME
        output_path = base_dir / DEFAULT_OUTPUT_NAME

        if not old_dir.is_dir() or not new_dir.is_dir():
            print("Не найдены папки для сравнения.")
            print(f"Ожидались подпапки рядом со скриптом ({base_dir}):")
            print(f"  - {OLD_DIR_NAME}\\   (старая версия)")
            print(f"  - {NEW_DIR_NAME}\\   (новая версия)")
            print()
            print("Создайте эти папки и положите в них .json файлы,")
            print("либо измените OLD_DIR_NAME / NEW_DIR_NAME в начале скрипта,")
            print("либо запустите скрипт из консоли с аргументами:")
            print("    python diff_item.py <папка_старая> <папка_новая>")
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