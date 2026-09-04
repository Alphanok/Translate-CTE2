#!/usr/bin/env python3
"""
snbt_quest_diff.py

Сравнивает структуру квестов FTB Quests в SNBT-файлах между двумя папками:
  - new      (оригинал)
  - chapter  (перевод)

Для каждого квеста (сопоставление идёт по полю "id") проверяется совпадение
структуры: набор ключей, вложенные объекты/массивы, количество элементов
в массивах (rewards, tasks, dependencies и т.д.), при этом поля
description / title / subtitle игнорируются полностью (и на верхнем уровне
квеста, и внутри вложенных объектов, например внутри tasks).

Использование:
    python3 snbt_quest_diff.py <папка_new> <папка_chapter> [опции]

Опции:
    --skip-keys description,title,subtitle   какие ключи не проверять (по умолчанию эти три)
    --report out.txt                         сохранить отчёт в файл
    --no-value-diffs                         не показывать отличия значений "технических" полей
                                              (id, x, y, item, type и т.п.), только структуру
    --quiet                                  не печатать построчный отчёт в консоль, только сводку
"""

import argparse
import glob
import os
import re
import sys
from collections import OrderedDict


# ---------------------------------------------------------------------------
# Токенизатор + парсер SNBT (упрощённый, под формат FTB Quests)
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r'''
      (?P<ws>\s+)
    | (?P<punct>[{}\[\]:,])
    | "(?P<string>(?:\\.|[^"\\])*)"
    | (?P<bare>[^\s{}\[\]:,"]+)
    ''',
    re.VERBOSE | re.DOTALL,
)


class SnbtParseError(Exception):
    pass


def strip_line_comments(text):
    """Убирает строки, которые целиком являются '//' комментарием.
    Не трогает содержимое внутри кавычек (грубая, но достаточная эвристика:
    комментарии в квест-файлах всегда занимают отдельную строку)."""
    out_lines = []
    for line in text.splitlines():
        if line.strip().startswith("//"):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def line_col(text, pos):
    """Возвращает (номер_строки, номер_столбца) 1-based для позиции pos в text."""
    line = text.count("\n", 0, pos) + 1
    last_nl = text.rfind("\n", 0, pos)
    col = pos - last_nl
    return line, col


def context_snippet(text, pos, context_lines=2):
    line_no, _ = line_col(text, pos)
    lines = text.splitlines()
    start = max(0, line_no - 1 - context_lines)
    end = min(len(lines), line_no + context_lines)
    out = []
    for i in range(start, end):
        marker = ">>" if (i + 1) == line_no else "  "
        out.append(f"{marker} {i+1:5d} | {lines[i]}")
    return "\n".join(out)


def tokenize(text):
    tokens = []
    pos = 0
    length = len(text)
    while pos < length:
        m = TOKEN_RE.match(text, pos)
        if not m:
            line, col = line_col(text, pos)
            raise SnbtParseError(
                f"Не удалось разобрать символ (строка {line}, столбец {col}): {text[pos:pos+20]!r}\n"
                f"{context_snippet(text, pos)}"
            )
        start = m.start()
        pos = m.end()
        if m.lastgroup == "ws":
            continue
        elif m.lastgroup == "punct":
            tokens.append(("PUNCT", m.group("punct"), start))
        elif m.lastgroup == "string":
            raw = m.group("string")
            raw = raw.replace('\\"', '"').replace("\\\\", "\\")
            tokens.append(("STR", raw, start))
        elif m.lastgroup == "bare":
            tokens.append(("BARE", m.group("bare"), start))
    return tokens


class Parser:
    def __init__(self, tokens, text):
        self.tokens = tokens
        self.pos = 0
        self.text = text

    def peek(self):
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def err(self, msg, pos_source=None):
        if pos_source is not None:
            char_pos = pos_source[2]
        elif self.pos < len(self.tokens):
            char_pos = self.tokens[self.pos][2]
        elif self.tokens:
            char_pos = self.tokens[-1][2]
        else:
            char_pos = 0
        line, col = line_col(self.text, char_pos)
        return SnbtParseError(
            f"{msg} (строка {line}, столбец {col})\n{context_snippet(self.text, char_pos)}"
        )

    def parse_value(self):
        tok = self.peek()
        if tok is None:
            raise self.err("Неожиданный конец файла")
        kind, val, _ = tok
        if kind == "PUNCT" and val == "{":
            return self.parse_object()
        if kind == "PUNCT" and val == "[":
            return self.parse_array()
        if kind in ("STR", "BARE"):
            self.advance()
            return val
        raise self.err(f"Неожиданный токен {kind} {val!r} - ожидалось значение")

    def parse_object(self):
        self.advance()  # '{'
        result = OrderedDict()
        while True:
            tok = self.peek()
            if tok is None:
                raise self.err("Не найдена закрывающая '}' (файл закончился раньше)")
            if tok[0] == "PUNCT" and tok[1] == "}":
                self.advance()
                break
            if tok[0] == "PUNCT" and tok[1] == ",":
                self.advance()
                continue
            key_tok = self.advance()
            if key_tok[0] not in ("STR", "BARE"):
                raise self.err(
                    f"Ожидался ключ (имя поля), но найден {key_tok[0]} {key_tok[1]!r}. "
                    f"Скорее всего, чуть выше не закрыта фигурная/квадратная скобка, "
                    f"или в строке есть незаэкранированная кавычка \"",
                    pos_source=key_tok,
                )
            key = key_tok[1]
            colon = self.advance() if self.peek() else None
            if colon is None or not (colon[0] == "PUNCT" and colon[1] == ":"):
                raise self.err(f"После ключа '{key}' ожидалось ':'", pos_source=colon or key_tok)
            value = self.parse_value()
            result[key] = value
            nxt = self.peek()
            if nxt and nxt[0] == "PUNCT" and nxt[1] == ",":
                self.advance()
        return result

    def parse_array(self):
        self.advance()  # '['
        result = []
        while True:
            tok = self.peek()
            if tok is None:
                raise self.err("Не найдена закрывающая ']' (файл закончился раньше)")
            if tok[0] == "PUNCT" and tok[1] == "]":
                self.advance()
                break
            if tok[0] == "PUNCT" and tok[1] == ",":
                self.advance()
                continue
            value = self.parse_value()
            result.append(value)
            nxt = self.peek()
            if nxt and nxt[0] == "PUNCT" and nxt[1] == ",":
                self.advance()
        return result


def parse_snbt(text):
    stripped = strip_line_comments(text)
    tokens = tokenize(stripped)
    parser = Parser(tokens, stripped)
    if not tokens:
        return OrderedDict()
    value = parser.parse_value()
    return value


# ---------------------------------------------------------------------------
# Загрузка квестов из папки
# ---------------------------------------------------------------------------

def load_quests(root_dir, errors):
    """Возвращает dict: id квеста -> (quest_dict, путь_к_файлу)"""
    quests = OrderedDict()
    pattern = os.path.join(root_dir, "**", "*.snbt")
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        errors.append(f"В папке '{root_dir}' не найдено ни одного .snbt файла")
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            obj = parse_snbt(text)
        except Exception as e:
            errors.append(f"Ошибка разбора файла '{fpath}': {e}")
            continue

        if isinstance(obj, dict) and isinstance(obj.get("quests"), list):
            for q in obj["quests"]:
                if not isinstance(q, dict):
                    continue
                qid = q.get("id")
                if not qid:
                    errors.append(f"В файле '{fpath}' найден квест без поля id")
                    continue
                if qid in quests:
                    errors.append(
                        f"Дублирующийся id квеста '{qid}' "
                        f"(файлы '{quests[qid][1]}' и '{fpath}')"
                    )
                quests[qid] = (q, fpath)
    return quests


# ---------------------------------------------------------------------------
# Сравнение структуры
# ---------------------------------------------------------------------------

def type_name(v):
    if isinstance(v, dict):
        return "object"
    if isinstance(v, list):
        return "array"
    return "value"


def compare_structure(orig, trans, path, skip_keys, diffs, show_value_diffs):
    to, tt = type_name(orig), type_name(trans)
    if to != tt:
        diffs.append(f"{path}: разный тип (оригинал={to}, перевод={tt})")
        return

    if to == "object":
        ok = {k for k in orig.keys() if k not in skip_keys}
        tk = {k for k in trans.keys() if k not in skip_keys}
        for k in sorted(ok - tk):
            diffs.append(f"{path}: в переводе отсутствует ключ '{k}'")
        for k in sorted(tk - ok):
            diffs.append(f"{path}: в переводе лишний ключ '{k}' (нет в оригинале)")
        for k in sorted(ok & tk):
            compare_structure(orig[k], trans[k], f"{path}.{k}", skip_keys, diffs, show_value_diffs)

    elif to == "array":
        orig_has_ids = bool(orig) and all(isinstance(x, dict) and "id" in x for x in orig)
        trans_has_ids = bool(trans) and all(isinstance(x, dict) and "id" in x for x in trans)

        if orig_has_ids and trans_has_ids:
            om = OrderedDict((x["id"], x) for x in orig)
            tm = OrderedDict((x["id"], x) for x in trans)
            for eid in [i for i in om if i not in tm]:
                diffs.append(f"{path}: в переводе отсутствует элемент с id '{eid}'")
            for eid in [i for i in tm if i not in om]:
                diffs.append(f"{path}: в переводе лишний элемент с id '{eid}'")
            for eid in [i for i in om if i in tm]:
                compare_structure(om[eid], tm[eid], f"{path}[id={eid}]", skip_keys, diffs, show_value_diffs)
        else:
            if len(orig) != len(trans):
                diffs.append(
                    f"{path}: разное количество элементов "
                    f"(оригинал={len(orig)}, перевод={len(trans)})"
                )
            for i in range(min(len(orig), len(trans))):
                compare_structure(orig[i], trans[i], f"{path}[{i}]", skip_keys, diffs, show_value_diffs)

    else:
        if show_value_diffs and orig != trans:
            diffs.append(f"{path}: отличается значение (оригинал={orig!r}, перевод={trans!r})")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Сравнение структуры SNBT-квестов FTB Quests между new/ (оригинал) и chapter/ (перевод)")
    ap.add_argument("new_dir", help="Папка с оригинальными квестами (new)")
    ap.add_argument("chapter_dir", help="Папка с переведёнными квестами (chapter)")
    ap.add_argument("--skip-keys", default="description,title,subtitle",
                     help="Список ключей через запятую, которые не нужно сравнивать (по умолчанию: description,title,subtitle)")
    ap.add_argument("--report", default=None, help="Путь к файлу для сохранения отчёта")
    ap.add_argument("--no-value-diffs", action="store_true",
                     help="Не показывать отличия значений 'технических' полей, только структуру")
    ap.add_argument("--quiet", action="store_true", help="Не печатать построчный отчёт, только сводку")
    args = ap.parse_args()

    skip_keys = {k.strip() for k in args.skip_keys.split(",") if k.strip()}
    show_value_diffs = not args.no_value_diffs

    load_errors = []
    new_quests = load_quests(args.new_dir, load_errors)
    chapter_quests = load_quests(args.chapter_dir, load_errors)

    out_lines = []

    def emit(line=""):
        out_lines.append(line)

    if load_errors:
        emit("=== Ошибки загрузки файлов ===")
        for e in load_errors:
            emit(f"  ! {e}")
        emit()

    new_ids = set(new_quests.keys())
    chapter_ids = set(chapter_quests.keys())

    missing_in_chapter = new_ids - chapter_ids   # есть в оригинале, нет в переводе
    extra_in_chapter = chapter_ids - new_ids     # есть в переводе, нет в оригинале
    common_ids = new_ids & chapter_ids

    if missing_in_chapter:
        emit(f"=== Квесты отсутствуют в переводе ({len(missing_in_chapter)}) ===")
        for qid in sorted(missing_in_chapter):
            _, fpath = new_quests[qid]
            emit(f"  - id {qid}  (оригинал: {fpath})")
        emit()

    if extra_in_chapter:
        emit(f"=== Лишние квесты в переводе, которых нет в оригинале ({len(extra_in_chapter)}) ===")
        for qid in sorted(extra_in_chapter):
            _, fpath = chapter_quests[qid]
            emit(f"  - id {qid}  (перевод: {fpath})")
        emit()

    quests_with_diffs = 0
    total_diffs = 0

    for qid in sorted(common_ids):
        orig_q, orig_path = new_quests[qid]
        trans_q, trans_path = chapter_quests[qid]
        diffs = []
        compare_structure(orig_q, trans_q, f"quest[{qid}]", skip_keys, diffs, show_value_diffs)
        if diffs:
            quests_with_diffs += 1
            total_diffs += len(diffs)
            emit(f"--- Квест {qid} ---")
            emit(f"    оригинал: {orig_path}")
            emit(f"    перевод : {trans_path}")
            for d in diffs:
                emit(f"    * {d}")
            emit()

    emit("=== Сводка ===")
    emit(f"Квестов в оригинале: {len(new_ids)}")
    emit(f"Квестов в переводе : {len(chapter_ids)}")
    emit(f"Общих квестов      : {len(common_ids)}")
    emit(f"Отсутствуют в переводе: {len(missing_in_chapter)}")
    emit(f"Лишние в переводе     : {len(extra_in_chapter)}")
    emit(f"Квестов с расхождениями структуры: {quests_with_diffs}")
    emit(f"Всего замечаний: {total_diffs}")

    report_text = "\n".join(out_lines)

    if not args.quiet:
        print(report_text)
    else:
        # в тихом режиме печатаем только сводку
        summary_start = report_text.rfind("=== Сводка ===")
        print(report_text[summary_start:])

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report_text + "\n")
        print(f"\nОтчёт сохранён: {args.report}")

    if quests_with_diffs or missing_in_chapter or extra_in_chapter or load_errors:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()