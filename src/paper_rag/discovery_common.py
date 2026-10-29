"""Shared deterministic bibliometric helpers; no model calls."""
import json,pathlib,hashlib,datetime,re,unicodedata,collections,math
from .library import save,load,sha,now

def norm(s):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s or '').lower())
def normdoi(s):return (s or '').lower().removeprefix('https://doi.org/')
def abstract(w):
    return ' '.join(word for _,word in sorted((pos,word) for word,positions in (w.get('abstract_inverted_index') or {}).items() for pos in positions))
