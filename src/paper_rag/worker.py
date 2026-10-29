"""Bounded read-only adapter to the existing library; no answer-model calls."""
import contextlib
import hashlib
import json
import pathlib
import re
import sqlite3
import sys

from .library import Library, load, sha
from .config import read_config

from . import preferences

class ReadLibrary(Library):
    def __init__(self):
        self.c = read_config()
        self.root = pathlib.Path(self.c['library_root'])
        self.base = pathlib.Path(self.c['base_root']) if self.c.get('base_root') else None
        self.db = sqlite3.connect((self.root / 'catalog.sqlite').as_uri() + '?mode=ro', uri=True)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA query_only=ON')


def citation_url(row):
    doi = row['doi']
    return 'https://doi.org/' + doi if doi else 'scientific-library://paper/' + row['paper_id']


def execute(req):
    lib = ReadLibrary()
    try:
        op = req['operation']
        if op in ['evidence_checklist','audit_answer','citation_network','source_page']:
            from .extensions import run
            return run(req, lib, execute)
        if op == 'list_papers':
            term = req['query'].strip()
            if len(term) > 500: raise ValueError('Query too long')
            rows = lib.db.execute("SELECT paper_id,title,doi,verification FROM papers WHERE state='READY' AND (instr(lower(title),lower(?))>0 OR paper_id=? OR doi=?) ORDER BY title", (term,term,term)).fetchall()
            return {'papers': [dict(r, url=citation_url(r), **preferences.describe(r["paper_id"],preferences.read(lib.root))) for r in rows[:50]], 'total_matches': len(rows), 'truncated': len(rows)>50}
        if op == 'search':
            q = req['query'].strip()
            if not q or len(q)>2000: raise ValueError('Query must have 1–2000 characters')
            papers = req.get('paper_ids') or None
            if papers and (len(papers)>10 or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', p) for p in papers)): raise ValueError('Invalid paper IDs')
            # Existing source-first pipeline; catalog is opened read-only. Only caches and query records are written.
            record, packet = lib.retrieve(q, papers, budget=12000)
            results = []
            for i, e in enumerate(packet['evidence']):
                row = lib.db.execute('SELECT paper_id,doi FROM papers WHERE paper_id=?', (e['paper_id'],)).fetchone()
                clean = {k:v for k,v in e.items() if k != 'source_path'}
                results.append(dict(clean, id=record.name+':'+str(i), url=citation_url(row)))
            return {'results': results, 'query': q, 'seconds': packet['seconds'], 'omitted_oversize_nodes': len(packet['skipped_oversize_node_ids']), 'model_calls':0, 'certified':False, 'guidance':'Use fetch(id) for parent-section context. Heading labels do not prove method ownership. Missing retrieved evidence does not prove corpus-wide absence.'}
        if op == 'fetch':
            lib.verify_base()
            match = re.fullmatch(r'(\d{8}T\d{6}_[a-f0-9]{8}):(\d{1,3})', req['id'])
            if not match: raise ValueError('Use an exact result id returned by search')
            record, index = match.groups()
            evidence = load(lib.root/'queries'/record/'evidence.json')['evidence'][int(index)]
            row = lib.db.execute("SELECT * FROM papers WHERE paper_id=? AND state='READY'", (evidence['paper_id'],)).fetchone()
            if not row: raise ValueError('Paper is not active')
            if sha(row['source_path']) != row['source_sha256']: raise ValueError('Source hash mismatch')
            meta = json.loads(row['metadata_json'])
            cp = pathlib.Path(row['bundle_path'])/'chunks.json' if row['bundle_path'] else lib.base/'structured'/f"{row['paper_id']}_chunks.json"
            expected = meta['hashes']['chunks.json'] if row['bundle_path'] else meta['chunks_sha256']
            if sha(cp) != expected: raise ValueError('Chunk hash mismatch')
            chunks = [c for c in load(cp) if ' / '.join(c['headings'])==evidence['heading']]
            section = '\n\n'.join(c['text'] for c in chunks)
            if hashlib.sha256(section.encode()).hexdigest()!=evidence['parent_section_sha256']: raise ValueError('Parent section hash mismatch')
            start,end=evidence['section_char_span']
            if section[start:end]!=evidence['text']: raise ValueError('Evidence anchor mismatch')
            offset=req.get('offset',0)
            if not isinstance(offset,int) or offset<0 or offset>len(section): raise ValueError('Invalid offset')
            stop=min(offset+12000,len(section)); paragraphs=[];pos=0
            for c in chunks:
                end=pos+len(c['text'])
                if end>offset and pos<stop: paragraphs.append({'chunk_id':c['id'],'pages':c['pages'],'doc_items':c['doc_items'],'section_char_span':[pos,end]})
                pos=end+2
            return {'id':req['id'],'paper_id':row['paper_id'],'title':row['title'],'url':citation_url(row),'text':section[offset:stop],'heading':evidence['heading'],'section_char_span':[offset,stop],'section_total_chars':len(section),'next_offset':stop if stop<len(section) else None,'paragraphs':paragraphs,'source_sha256':row['source_sha256'],'hash_status':'MATCHED','verification':row['verification'],'method_ownership':'UNRESOLVED_REQUIRES_READING','model_calls':0}
        raise ValueError('Operation not allowed')
    finally:
        lib.db.close()


if __name__=='__main__':
    try:
        with contextlib.redirect_stdout(sys.stderr): result=execute(json.load(sys.stdin))
        print(json.dumps(result,ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'error':type(exc).__name__,'message':str(exc)},ensure_ascii=False))
        sys.exit(1)
