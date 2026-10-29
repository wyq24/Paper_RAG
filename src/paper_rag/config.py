"""Portable configuration; private state stays outside the code checkout."""
import json,os,pathlib,sys,shutil

def config_path(path=None):
    return pathlib.Path(path or os.environ.get('PAPER_RAG_CONFIG') or pathlib.Path.home()/'.config/paper-rag/config.json').expanduser().resolve()

def read_config(path=None):
    p=config_path(path)
    if not p.exists():raise ValueError('Run paper-rag init before using the library')
    c=json.loads(p.read_text())
    for key in ['library_root','base_root','citation_snapshot']:
        if c.get(key):c[key]=str(pathlib.Path(c[key]).expanduser().resolve())
    return c

def initialize_config(path=None,root=None):
    p=config_path(path)
    if p.exists():
        c=read_config(p)
        if root and pathlib.Path(root).expanduser().resolve()!=pathlib.Path(c['library_root']):
            raise ValueError('Existing config points elsewhere; use a new --config path. Nothing overwritten.')
        return c
    data=pathlib.Path(root or pathlib.Path.home()/'.local/share/paper-rag').expanduser().resolve()
    c={'library_root':str(data),'base_root':None,'citation_snapshot':None,'enable_codex_answer':False,'answer_model':None,'answer_effort':'medium','codex_cli':shutil.which('codex') or 'codex'}
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(c,f,indent=2)
    p.chmod(0o600)
    return c
