#!/usr/bin/env python3
"""
find_translation_source.py (v2)

Ищет заданную строку в:
  1. ЛЮБЫХ lang-файлах (en_us.json, ru_ru.json, en_us.lang и т.д.) внутри .jar модов (mods/*.jar)
  2. Ресурспаках в resourcepacks/ (и .zip, и распакованные папки) — там может лежать русификатор
  3. Текстовых/конфиг файлах в config/ и kubejs/ (json, toml, txt, lang, cfg)

Выводит диагностику: сколько jar/lang-файлов реально просканировано,
чтобы было видно, не ошибка ли в пути.

ИСПОЛЬЗОВАНИЕ:
    python find_translation_source.py "<путь к папке .minecraft инстанса>" "<искомая строка>"

Пример (Windows, Prism Launcher):
    python find_translation_source.py "C:\\Users\\User\\AppData\\Roaming\\PrismLauncher\\instances\\Craft to Exile 2\\.minecraft" "Wild West"
"""

import sys
import os
import zipfile
import json

CONFIG_EXTENSIONS = {".json", ".toml", ".txt", ".lang", ".cfg", ".cf"}

stats = {
    "jars_scanned": 0,
    "jars_failed": 0,
    "lang_files_found": 0,
    "resourcepack_files_found": 0,
    "config_files_scanned": 0,
}


def is_lang_path(entry_path):
    norm = entry_path.replace("\\", "/").lower()
    if "/lang/" not in norm:
        return False
    return norm.endswith(".json") or norm.endswith(".lang")


def read_zip_entry(zf, entry):
    try:
        raw = zf.read(entry)
    except Exception:
        return None
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def extract_match_context(raw_text, entry_path, term):
    lines_out = []
    if entry_path.lower().endswith(".json"):
        try:
            data = json.loads(raw_text)
            for key, value in data.items():
                if term.lower() in str(key).lower() or term.lower() in str(value).lower():
                    lines_out.append(f'      -> "{key}": "{value}"')
        except Exception:
            for line in raw_text.splitlines():
                if term.lower() in line.lower():
                    lines_out.append(f"      -> {line.strip()}")
    else:
        for line in raw_text.splitlines():
            if term.lower() in line.lower():
                lines_out.append(f"      -> {line.strip()}")
    return "\n".join(lines_out) if lines_out else "      (найдено, но не удалось извлечь контекст)"


def search_in_jars(mods_dir, term, results):
    if not os.path.isdir(mods_dir):
        print(f"[!] Папка mods не найдена: {mods_dir}")
        return

    jar_files = [f for f in os.listdir(mods_dir) if f.lower().endswith(".jar")]
    print(f"[i] Найдено {len(jar_files)} jar-файлов в mods/. Сканирую...")

    for jar_name in jar_files:
        jar_path = os.path.join(mods_dir, jar_name)
        try:
            with zipfile.ZipFile(jar_path, "r") as zf:
                stats["jars_scanned"] += 1
                for entry in zf.namelist():
                    if not is_lang_path(entry):
                        continue
                    stats["lang_files_found"] += 1
                    raw = read_zip_entry(zf, entry)
                    if raw is None:
                        continue
                    if term.lower() in raw.lower():
                        match_info = extract_match_context(raw, entry, term)
                        results.append(
                            f"[JAR] {jar_name}\n"
                            f"      файл внутри архива: {entry}\n"
                            f"{match_info}\n"
                        )
        except zipfile.BadZipFile:
            stats["jars_failed"] += 1
            print(f"[!] Не удалось открыть как zip: {jar_name}")
        except Exception as e:
            stats["jars_failed"] += 1
            print(f"[!] Ошибка при чтении {jar_name}: {e}")


def search_in_resourcepacks(base_dir, term, results):
    rp_dir = os.path.join(base_dir, "resourcepacks")
    if not os.path.isdir(rp_dir):
        print(f"[i] Папка resourcepacks не найдена (это нормально, если русификатора-ресурспака нет)")
        return

    print(f"[i] Сканирую resourcepacks: {rp_dir}")
    for item in os.listdir(rp_dir):
        item_path = os.path.join(rp_dir, item)

        if item.lower().endswith(".zip") and os.path.isfile(item_path):
            try:
                with zipfile.ZipFile(item_path, "r") as zf:
                    for entry in zf.namelist():
                        if not is_lang_path(entry):
                            continue
                        stats["resourcepack_files_found"] += 1
                        raw = read_zip_entry(zf, entry)
                        if raw and term.lower() in raw.lower():
                            match_info = extract_match_context(raw, entry, term)
                            results.append(
                                f"[RESOURCEPACK zip] {item}\n"
                                f"      файл внутри архива: {entry}\n"
                                f"{match_info}\n"
                            )
            except zipfile.BadZipFile:
                print(f"[!] Не удалось открыть как zip: {item}")

        elif os.path.isdir(item_path):
            for root, _, files in os.walk(item_path):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if is_lang_path(fpath):
                        stats["resourcepack_files_found"] += 1
                        try:
                            with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as f:
                                raw = f.read()
                        except Exception:
                            continue
                        if term.lower() in raw.lower():
                            match_info = extract_match_context(raw, fpath, term)
                            results.append(
                                f"[RESOURCEPACK folder] {item}\n"
                                f"      файл: {fpath}\n"
                                f"{match_info}\n"
                            )


def search_in_config_dirs(base_dir, term, results):
    targets = [os.path.join(base_dir, "config"), os.path.join(base_dir, "kubejs")]

    for folder in targets:
        if not os.path.isdir(folder):
            print(f"[i] Папка не найдена (пропускаю): {folder}")
            continue
        print(f"[i] Сканирую {folder} ...")
        for root, _, files in os.walk(folder):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in CONFIG_EXTENSIONS:
                    continue
                fpath = os.path.join(root, fname)
                stats["config_files_scanned"] += 1
                try:
                    with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as f:
                        raw = f.read()
                except Exception:
                    continue
                if term.lower() in raw.lower():
                    matches = [
                        line.strip()
                        for line in raw.splitlines()
                        if term.lower() in line.lower()
                    ]
                    match_block = "\n".join(f"      -> {m}" for m in matches[:10])
                    results.append(f"[CONFIG] {fpath}\n{match_block}\n")


def main():
    if len(sys.argv) != 3:
        print('Использование: python find_translation_source.py "<путь к .minecraft>" "<строка для поиска>"')
        sys.exit(1)

    base_dir = sys.argv[1]
    term = sys.argv[2]

    if not os.path.isdir(base_dir):
        print(f"[!] Указанная папка не существует: {base_dir}")
        sys.exit(1)

    print(f"[i] Ищу строку: \"{term}\"")
    print(f"[i] Базовая папка: {base_dir}\n")

    results = []

    search_in_jars(os.path.join(base_dir, "mods"), term, results)
    search_in_resourcepacks(base_dir, term, results)
    search_in_config_dirs(base_dir, term, results)

    print("\n" + "=" * 60)
    print("ДИАГНОСТИКА:")
    print(f"  jar-файлов успешно открыто: {stats['jars_scanned']}")
    print(f"  jar-файлов с ошибкой открытия: {stats['jars_failed']}")
    print(f"  lang-файлов найдено внутри jar-ов: {stats['lang_files_found']}")
    print(f"  lang-файлов найдено в resourcepacks: {stats['resourcepack_files_found']}")
    print(f"  config/kubejs файлов просканировано: {stats['config_files_scanned']}")
    print("=" * 60 + "\n")

    if stats["jars_scanned"] == 0:
        print("[!] ВНИМАНИЕ: не открыт ни один jar-файл. Скорее всего путь к папке mods указан неверно.")
        print("    Проверьте, что base_dir действительно указывает на папку .minecraft,")
        print("    внутри которой лежит подпапка mods с .jar файлами.")

    if results:
        print(f"[✓] Найдено совпадений: {len(results)}\n")
        for r in results:
            print(r)
    else:
        print(f'[x] Строка "{term}" нигде не найдена.')
        print("    Возможные причины:")
        print("    1) Путь к .minecraft указан неверно (см. диагностику выше).")
        print("    2) Название на карте генерируется автоматически из внутреннего ID")
        print('       (например "wild_west" код превращает в "Wild West" на лету),')
        print("       и как текст оно нигде не хранится — тогда обычным переводом такое не поправить.")
        print("    3) Строка лежит в формате, который скрипт не проверяет (например .nbt, .snbt, datapack json без 'lang' в пути).")

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search_results.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"Поиск строки: {term}\n")
        f.write(f"Папка: {base_dir}\n\n")
        f.write(f"jars_scanned={stats['jars_scanned']} jars_failed={stats['jars_failed']} "
                f"lang_files_found={stats['lang_files_found']} "
                f"resourcepack_files_found={stats['resourcepack_files_found']} "
                f"config_files_scanned={stats['config_files_scanned']}\n\n")
        f.write("\n".join(results) if results else "Ничего не найдено.\n")

    print(f"\n[i] Результаты также сохранены в: {out_file}")


if __name__ == "__main__":
    main()
