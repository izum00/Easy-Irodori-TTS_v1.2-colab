"""Restrict cleanup to application-owned generated audio, never voice references."""
from pathlib import Path
import json,hashlib

def inventory(store):
    root=store.root.resolve(); protected={(root/v['audio']).resolve() for v in store.voices}
    records=[]
    for relative in ('outputs/internal',):
        folder=root/relative
        if not folder.exists():continue
        for p in folder.rglob('*.wav'):
            if p.is_symlink() or any(x.is_symlink() or (x.stat().st_file_attributes & 1024 if hasattr(x.stat(),'st_file_attributes') else False) for x in [p,*p.parents] if x!=root and root in x.parents):continue
            if not p.resolve().is_relative_to(root) or p.resolve() in protected:continue
            stat=p.stat();records.append(dict(path=str(p),name=str(p.relative_to(root)),size=stat.st_size,mtime=stat.st_mtime_ns))
    records.sort(key=lambda x:x['path'])
    stamp=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()
    return records,stamp

def recycle(store,stamp):
    """Colab has no recycle bin, so application-owned internal audio is deleted."""
    records,current=inventory(store)
    if current!=stamp:raise ValueError('対象が変わりました。もう一度一覧を確認してください。')
    for x in records:
        try:Path(x['path']).unlink()
        except FileNotFoundError:pass
        except OSError as exc:raise ValueError('削除を完了できませんでした。対象を再確認してください。') from exc
    return sum(not Path(x['path']).exists() for x in records)
