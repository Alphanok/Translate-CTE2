import json
import re
import sys
from pathlib import Path


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def find_brackets(text):
    """Находит все подстроки вида [что-то] в строке."""
    if not isinstance(text, str):
        return []
    return re.findall(r'\[[^\]]*\]', text)


def main(en_path, ru_path, report_path):
    en = load_json(en_path)
    ru = load_json(ru_path)

    report_lines = []
    all_keys = sorted(set(en.keys()) | set(ru.keys()))
    mismatches = 0

    for key in all_keys:
        en_val = en.get(key)
        ru_val = ru.get(key)

        en_has_brackets = bool(find_brackets(en_val))

        if key not in ru:
            if en_has_brackets:
                report_lines.append(f"[ОТСУТСТВУЕТ В RU] {key}\n  en: {en_val}\n")
                mismatches += 1
            continue
        if key not in en:
            continue

        ru_has_brackets = bool(find_brackets(ru_val))

        # Проверяем только наличие хотя бы одной [..] конструкции в ru,
        # если такая есть в en. Количество, порядок и содержимое скобок
        # не сравниваем.
        if en_has_brackets and not ru_has_brackets:
            report_lines.append(
                f"[НЕТ СКОБОК В RU] {key}\n"
                f"  en: {en_val}\n"
                f"  ru: {ru_val}\n"
            )
            mismatches += 1

    if not report_lines:
        summary = "Расхождений не найдено — везде, где есть скобки в en, они есть и в ru."
    else:
        summary = f"Найдено расхождений: {mismatches} из {len(all_keys)} ключей."

    full_report = summary + "\n\n" + "\n".join(report_lines)
    Path(report_path).write_text(full_report, encoding='utf-8')

    print(summary)
    print(f"Полный отчёт сохранён в: {report_path}")


if __name__ == "__main__":
    # Пути можно передать аргументами командной строки:
    #   python check_brackets.py en_us.json ru_ru.json report.txt
    en_path = sys.argv[1] if len(sys.argv) > 1 else "en_us.json"
    ru_path = sys.argv[2] if len(sys.argv) > 2 else "ru_ru.json"
    report_path = sys.argv[3] if len(sys.argv) > 3 else "bracket_check_report.txt"
    main(en_path, ru_path, report_path)