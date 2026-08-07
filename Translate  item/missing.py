import re
import os
import sys

def main():
    # Папка, где лежит сам скрипт (а не текущая рабочая директория)
    base_dir = os.path.dirname(os.path.abspath(__file__))

    old_file = os.path.join(base_dir, "ru_ru.json")
    new_file = os.path.join(base_dir, "en_us.json")
    output_file = os.path.join(base_dir, "missing.txt")

    # Проверка наличия файлов
    for path, name in [(old_file, "ru_ru.json"), (new_file, "en_us.json")]:
        if not os.path.isfile(path):
            print(f"Ошибка: не найден файл {name} рядом со скриптом ({base_dir})")
            input("\nНажмите Enter, чтобы закрыть окно...")
            sys.exit(1)

    # Регулярное выражение для поиска ключа
    key_pattern = re.compile(r'^\s*"([^"]+)"\s*:')

    # Собираем все ключи из старого файла
    old_keys = set()
    with open(old_file, "r", encoding="utf-8") as f:
        for line in f:
            match = key_pattern.match(line)
            if match:
                old_keys.add(match.group(1))

    # Ищем строки, которых нет в старом файле
    missing_lines = []
    with open(new_file, "r", encoding="utf-8") as f:
        for line in f:
            match = key_pattern.match(line)
            if match:
                key = match.group(1)
                if key not in old_keys:
                    missing_lines.append(line.rstrip())

    # Сохраняем результат
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(missing_lines))

    print(f"Найдено новых строк: {len(missing_lines)}")
    print(f"Результат сохранён в {output_file}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        input("\nНажмите Enter, чтобы закрыть окно...")