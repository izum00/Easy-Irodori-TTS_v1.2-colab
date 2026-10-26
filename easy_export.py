"""Collision-free output, including retry after a partially failed export."""
import os
from pathlib import Path
import re
import shutil
import threading
from datetime import datetime
from uuid import uuid4
def uid(): return uuid4().hex

LOCK = threading.Lock()

def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value)).strip().rstrip('. ')
    value = value[:100].rstrip('. ') or '音声'
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', value, re.I):
        value = '_' + value
    return value

def filename(settings, card, voice, ordinal, date):
    pattern = settings['pattern'] if settings['custom_pattern'] else '$連番$_$話者名$_$日付$'
    tokens = {'$連番$': f'{ordinal:03}', '$話者名$': voice['name'],
              '$テキスト$': card['text'][:40], '$日付$': date}
    return safe_name(re.sub(r'\$(?:連番|話者名|テキスト|日付)\$', lambda m: tokens[m.group()], pattern))

def export_audio(root, source, settings, card, voice, ordinal, date, previous=None):
    folder = Path(settings['output_dir']) if settings['custom_output'] else Path(root) / 'outputs' / 'exports'
    if not folder.is_absolute():
        raise ValueError('保存先は絶対パスで指定してください。')
    folder.mkdir(parents=True, exist_ok=True)
    result = dict(previous or {})
    with LOCK:
        wav = Path(result['wav']) if result.get('wav') else None
        if wav and wav.parent.resolve() != folder.resolve():
            # A changed destination is a new export, not a retry into the old folder.
            result = {}
            wav = None
        if wav is None or not wav.is_file():
            base = filename(settings, card, voice, ordinal, date)
            index = 0
            while True:
                name = base + (f'_{index:03}' if index else '')
                wav = folder / (name + '.wav')
                if wav.with_suffix('.txt').exists():
                    index += 1
                    continue
                try:
                    # Exclusive create reserves the name even across application processes.
                    with wav.open('xb') as dest, Path(source).open('rb') as src:
                        shutil.copyfileobj(src, dest)
                    result['wav'] = str(wav)
                    break
                except FileExistsError:
                    index += 1
                except Exception:
                    wav.unlink(missing_ok=True)
                    raise
        if settings['txt']:
            txt = wav.with_suffix('.txt')
            try:
                with txt.open('x', encoding='utf-8-sig') as stream:
                    stream.write(card['text'])
                result['txt'] = str(txt)
            except FileExistsError:
                if txt.read_text(encoding='utf-8-sig') == card['text']:
                    result['txt'] = str(txt)
                else:
                    result['error'] = 'TXTが同名で存在します。保存先を確認してください。'
                    return result
            except OSError as exc:
                result['error'] = f'WAVは保存済みですがTXT保存に失敗しました: {exc}'
                return result
    result.pop('error', None)
    return result
