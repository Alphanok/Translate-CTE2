#!/usr/bin/env python3
"""Заменяет одиночные % на %% в ru_ru.json.

Не трогает:
  - уже удвоенные %%
  - плейсхолдеры: %s, %d, %f, %1$s, %2$d, %.1f, %05d и т.п.

Использование:
    python fix_percent.py [путь_к_файлу]
По умолчанию берётся ru_ru.json из текущей папки.
"""
import json
import re
import shutil
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "ru_ru.json"

# Порядок важен: сначала %%, потом плейсхолдеры, и только потом одиночный %
TOKEN = re.compile(r"%%|%(?:\d+\$)?[\d.]*[sdf]|%")

count = 0


def fix(match):
    global count
    token = match.group(0)
    if token == "%":  # одиночный процент
        count += 1
        return "%%"
    return token


with open(path, "r", encoding="utf-8") as f:
    text = f.read()

new_text = TOKEN.sub(fix, text)

if count == 0:
    print("Одиночных % не найдено, файл не изменён.")
    sys.exit(0)

# Проверяем, что JSON остался валидным
json.loads(new_text)

shutil.copyfile(path, path + ".bak")
with open(path, "w", encoding="utf-8", newline="") as f:
    f.write(new_text)

print(f"Готово: заменено {count} шт. Резервная копия: {path}.bak")
