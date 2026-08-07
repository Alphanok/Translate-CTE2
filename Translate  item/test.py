import re

old_file = "ru_ru.json"
new_file = "en_us.json"
output_file = "missing.txt"

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