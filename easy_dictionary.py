"""Local, literal reading replacements. No changes to the user's original text."""
import json
import os
from pathlib import Path
import re
import threading

PATH = Path(__file__).resolve().parent / "config" / "reading_dictionary.json"
LOCK = threading.RLock()


def load():
    if not PATH.exists():
        return {}
    try:
        entries = json.loads(PATH.read_text(encoding="utf-8-sig"))
        if not isinstance(entries, dict) or any(not isinstance(k, str) or not k.strip() or
                not isinstance(v, str) or not v.strip() for k, v in entries.items()):
            raise ValueError("invalid entries")
        return entries
    except (ValueError, OSError) as exc:
        raise ValueError("読み辞書を読み込めません。config/reading_dictionary.jsonを確認してください。元のファイルは変更していません。") from exc


def write(entries):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, PATH)


def save(word, reading):
    word, reading = str(word or "").strip(), str(reading or "").strip()
    if not word or not reading:
        raise ValueError("「表記」と「読み方」の両方を入力してください。")
    if len(word) > 100 or len(reading) > 200 or "\n" in word or "\n" in reading:
        raise ValueError("1行で入力してください。表記は100文字、読み方は200文字までです。")
    with LOCK:
        entries = load()
        updated = word in entries
        entries[word] = reading
        write(entries)
    return "読み方を更新しました。" if updated else "読み方を登録しました。"


def delete(word):
    with LOCK:
        entries = load()
        if word not in entries:
            raise ValueError("削除する登録を一覧から選んでください。")
        del entries[word]
        write(entries)
    return "選んだ登録を削除しました。"


def apply(text, enabled=True):
    if not enabled:
        return text
    with LOCK:
        entries = load()
    if not entries:
        return text
    # Longest literal match wins; replacement output is never processed again.
    pattern = "|".join(re.escape(k) for k in sorted(entries, key=len, reverse=True))
    return re.sub(pattern, lambda match: entries[match.group()], text)
