#!/usr/bin/env python3
"""Local incremental source-first library. Historical files are always read-only inputs."""
import argparse,contextlib,datetime,fcntl,hashlib,json,os,pathlib,re,shutil,sqlite3,sys,time,uuid
from .config import read_config
def load(p):return json.loads(pathlib.Path(p).read_text())
def save(p,x):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2));tmp.replace(p)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def norm(s):return re.sub(r'[^a-z0-9]','',s.lower())
from . import preferences
class Library:
 def __init__(self,config=None):
  self.c=read_config(config);self.root=pathlib.Path(self.c['library_root']);self.base=pathlib.Path(self.c['base_root']) if self.c.get('base_root') else None;self.root.mkdir(parents=True,exist_ok=True)
  for d in ['inbox','documents','staging','receipts','queries','cache']: (self.root/d).mkdir(exist_ok=True)
  self.db=sqlite3.connect(self.root/'catalog.sqlite',timeout=120);self.db.row_factory=sqlite3.Row
  self.db.executescript('''CREATE TABLE IF NOT EXISTS papers(paper_id TEXT PRIMARY KEY,title TEXT NOT NULL,doi TEXT,source_sha256 TEXT UNIQUE NOT NULL,source_path TEXT NOT NULL,bundle_path TEXT,origin TEXT NOT NULL,state TEXT NOT NULL,verification TEXT NOT NULL,added_at TEXT NOT NULL,metadata_json TEXT NOT NULL);CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at TEXT,kind TEXT,paper_id TEXT,payload_json TEXT);''');self.db.commit()
 @contextlib.contextmanager
 def lock(self):
  with (self.root/'writer.lock').open('a+') as f:
   fcntl.flock(f,fcntl.LOCK_EX)
   try:yield
   finally:fcntl.flock(f,fcntl.LOCK_UN)
 def event(self,kind,pid,payload):self.db.execute('insert into events(at,kind,paper_id,payload_json) values (?,?,?,?)',(now(),kind,pid,json.dumps(payload,ensure_ascii=False)))
 def initialize(self):
  if self.base is None:return self.status()
  with self.lock():
   corpus=load(self.base/'corpus87.json');prior={r['paper_id']:r for r in load(self.base/'parsing_receipts.json')};baseline_manifest={str(self.base/'corpus87.json'):sha(self.base/'corpus87.json'),str(self.base/'hierarchical_nodes.json'):sha(self.base/'hierarchical_nodes.json')}
   for d in corpus:
    pid=d['paper_id'];meta=dict(d,structured_sha256=prior[pid]['docling_sha256'],chunks_sha256=prior[pid]['chunks_sha256'],verification_timing='registered from historical receipts; rehash delivered sources at query time')
    if prior[pid]['source_pdf_sha256']!=d['source_sha256']:raise ValueError('Historical source receipts disagree: '+pid)
    self.db.execute('insert or ignore into papers values (?,?,?,?,?,?,?,?,?,?,?)',(pid,d['title'],None,d['source_sha256'],d['path'],None,'FROZEN_BASE','READY','HISTORICAL_STATUS_PRESERVED_NOT_REVERIFIED',now(),json.dumps(meta)))
   self.db.commit()
   manifest=self.root/'frozen_assets.json'
   if manifest.exists() and load(manifest)!=baseline_manifest:raise ValueError('Frozen index changed; do not overwrite its manifest')
   if not manifest.exists():save(manifest,baseline_manifest)
  return self.status()
 def status(self):
  return {'library_root':str(self.root),'papers':self.db.execute('select count(*) from papers').fetchone()[0],'states':[dict(r) for r in self.db.execute('select origin,state,count(*) n from papers group by origin,state')],'inbox_pdfs':len(list((self.root/'inbox').glob('*.pdf'))),'scientific_certification':False,'historical_benchmark_states':self.c.get('historical_benchmark_states',[])}
 def list(self,term=''):return [dict(r) for r in self.db.execute('select paper_id,title,doi,origin,state,verification from papers where title like ? or paper_id=? or lower(doi)=lower(?) order by added_at',('%'+term+'%',term,term))]
 def verify_base(self):
  if self.base is None:return
  if not (self.root/'frozen_assets.json').exists():raise ValueError('Run init first')
  for p,h in load(self.root/'frozen_assets.json').items():
   if sha(p)!=h:raise ValueError('Frozen asset changed: '+p)
 def mark(self,pid,label,reason="Explicit user curation"):
  with self.lock():
   if not self.db.execute("select 1 from papers where paper_id=?",(pid,)).fetchone():raise ValueError("Unknown paper ID")
   return dict(paper_id=pid,**preferences.write(self.root,pid,label,reason))
 def ingest(self,path,title=None,doi=None,selection_label="manual"):
  if selection_label not in preferences.LABELS:raise ValueError("Unknown selection label")
  path=pathlib.Path(path).expanduser().resolve()
  if path.suffix.lower()!='.pdf' or not path.is_file():raise ValueError('A local PDF is required')
  digest=sha(path);pid='SRC_'+digest[:16];receipt={'at':now(),'input_path':str(path),'source_sha256':digest,'paper_id':pid,'llm_calls':0}
  with self.lock():
   old=self.db.execute('select paper_id,state from papers where source_sha256=?',(digest,)).fetchone()
   if old:
    if selection_label=='manual':preferences.write(self.root,old['paper_id'],'manual','User explicitly supplied existing paper')
    result=dict(receipt,status='DUPLICATE_UNCHANGED',existing_paper_id=old['paper_id'],existing_state=old['state']);save(self.root/'receipts'/(uuid.uuid4().hex+'.json'),result);return result
   attempt=uuid.uuid4().hex;stage=self.root/'staging'/attempt;stage.mkdir();source=stage/'source.pdf';shutil.copy2(path,source)
   try:
    with source.open('rb') as pdf_file:signature=pdf_file.read(5)
    if signature!=b'%PDF-':raise ValueError('Not a PDF file')
    from docling.document_converter import DocumentConverter,PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.chunking import HierarchicalChunker
    options=PdfPipelineOptions();options.do_ocr=False;options.do_table_structure=False
    result=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)}).convert(source)
    status=getattr(result.status,'value',str(result.status))
    if str(status).lower()!='success':raise ValueError('Docling status '+str(status))
    doc=result.document;doc.save_as_json(stage/'structured.json')
    chunks=[{'id':f'{pid}:docling:{i}','paper_id':pid,'text':c.text,'headings':c.meta.headings or [],'doc_items':[x.self_ref for x in c.meta.doc_items],'pages':sorted({p.page_no for x in c.meta.doc_items for p in x.prov}),'source_sha256':digest} for i,c in enumerate(HierarchicalChunker().chunk(dl_doc=doc)) if c.text.strip()]
    if sum(len(c['text']) for c in chunks)<200 or not all(c['pages'] for c in chunks):raise ValueError('INSUFFICIENT_TEXT_OR_PAGE_PROVENANCE: scanned or inaccessible PDF; retained staging, not searchable')
    docjson=load(stage/'structured.json');titles=[x.get('text','') for x in docjson.get('texts',[]) if x.get('label')=='title'];resolved_title=title or (titles[0] if titles else path.stem)
    save(stage/'chunks.json',chunks);nodes=build_nodes(pid,resolved_title,digest,chunks);save(stage/'nodes.json',[n.to_dict() for n in nodes])
    if sha(source)!=digest:raise ValueError('Source changed during parsing')
    matching=[dict(r) for r in self.db.execute('select paper_id,title,doi from papers') if (doi and r['doi'] and r['doi'].lower()==doi.lower()) or norm(r['title'])==norm(resolved_title)]
    meta={'title':resolved_title,'doi':doi,'doi_status':'USER_SUPPLIED_UNVERIFIED' if doi else 'UNKNOWN','original_input_path':str(path),'related_versions_or_title_collisions':matching,'chunk_count':len(chunks),'node_count':len(nodes),'parser':'Docling PDF + HierarchicalChunker; OCR off; table-structure off','limitations':['Images/equations/tables may be inaccessible; no scientific claim extraction or verification'],'hashes':{f:sha(stage/f) for f in ['source.pdf','structured.json','chunks.json','nodes.json']}}
    save(stage/'manifest.json',meta);dest=self.root/'documents'/pid
    if dest.exists():dest=self.root/'documents'/(pid+'_'+attempt[:8])
    stage.rename(dest);(dest/'source.pdf').chmod(0o444)
    try:
     self.db.execute('insert into papers values (?,?,?,?,?,?,?,?,?,?,?)',(pid,resolved_title,doi,digest,str(dest/'source.pdf'),str(dest),'USER_IMPORT','READY','UNREVIEWED_SOURCE_ONLY',now(),json.dumps(meta)));self.event('INGEST_COMMITTED',pid,meta);self.db.commit()
    except Exception:self.db.rollback();raise
    preferences.write(self.root,pid,selection_label,'Ingestion source declared by caller')
    receipt.update(status='READY',paper_id=pid,title=resolved_title,related_versions=matching,document_dir=str(dest),metadata=meta)
   except Exception as e:
    self.db.rollback();receipt.update(status='FAILED_NOT_INDEXED',error=str(e),preserved_staging=str(dest if 'dest' in locals() and dest.exists() else stage));self.event('INGEST_FAILED',pid,receipt);self.db.commit()
   save(self.root/'receipts'/f'{attempt}.json',receipt)
  return receipt
 def sync(self):
  results=[]
  for p in sorted((self.root/'inbox').glob('*')):
   if p.suffix.lower()=='.pdf':results.append(self.ingest(p))
  return {'results':results,'files_left_in_inbox':True,'automatic_background_watch':False}
 def deactivate(self,pid,active):
  with self.lock():
   r=self.db.execute('select origin from papers where paper_id=?',(pid,)).fetchone()
   if not r:raise ValueError('Unknown paper ID')
   if r['origin']=='FROZEN_BASE':raise ValueError('Frozen baseline membership cannot be changed by this command')
   self.db.execute('update papers set state=? where paper_id=?',('READY' if active else 'INACTIVE',pid));self.event('RESTORE' if active else 'DEACTIVATE',pid,{'physical_files_deleted':False});self.db.commit()
  return {'paper_id':pid,'state':'READY' if active else 'INACTIVE','physical_files_deleted':False}
 def retrieve(self,question,papers=None,budget=9000,label=None):
  self.verify_base();t=time.time()
  from llama_index.core.schema import TextNode
  from llama_index.core import StorageContext
  from llama_index.core.node_parser import get_leaf_nodes
  from llama_index.retrievers.bm25 import BM25Retriever
  from llama_index.core.retrievers import AutoMergingRetriever
  rows=[dict(r) for r in self.db.execute("select * from papers where state='READY'")];rows=[r for r in rows if not papers or r['paper_id'] in papers]
  if papers and set(papers)-{r['paper_id'] for r in rows}:raise ValueError('Unknown or inactive --paper-id')
  if not rows:raise ValueError('No searchable papers; ingest a PDF first')
  prefs=preferences.read(self.root)
  if label:
   rows=[r for r in rows if preferences.describe(r['paper_id'],prefs)['selection_label']==label]
   if not rows:raise ValueError('No searchable papers with requested label')
  by={r['paper_id']:r for r in rows};raw=[n for n in load(self.base/'hierarchical_nodes.json') if n['metadata']['paper_id'] in by] if self.base else [];groups={}
  for r in rows:
   pid=r['paper_id'];meta=json.loads(r['metadata_json']);bundle=pathlib.Path(r['bundle_path']) if r['bundle_path'] else None
   if bundle:
    for f in ['nodes.json']:
     if sha(bundle/f)!=meta['hashes'][f]:raise ValueError('Stored source bundle modified: '+pid)
    raw+=load(bundle/'nodes.json')
  nodes=[TextNode.from_dict(n) for n in raw];leaf_nodes=get_leaf_nodes(nodes);top_k=min(8,len(leaf_nodes));store=StorageContext.from_defaults();store.docstore.add_documents(nodes)
  # Persist only this library's sparse index. Membership/content fingerprint selects a new cache generation.
  key=hashlib.sha256(json.dumps([(r['paper_id'],r['source_sha256']) for r in rows],sort_keys=True).encode()+json.dumps([n.node_id for n in nodes]).encode()).hexdigest();cache=self.root/'cache'/key
  with self.lock():
   if (cache/'COMPLETE.json').exists():bm=BM25Retriever.from_persist_dir(str(cache))
   else:
    bm=BM25Retriever.from_defaults(nodes=leaf_nodes,similarity_top_k=top_k);cache.mkdir(exist_ok=True);bm.persist(str(cache));save(cache/'COMPLETE.json',{'key':key,'at':now()})
  bm.similarity_top_k=top_k;ret=AutoMergingRetriever(bm,store,simple_ratio_thresh=.5);hits=preferences.rerank(ret.retrieve(question),prefs);terms=re.findall(r'\b(?:[A-Z][A-Za-z0-9]*[A-Z0-9][A-Za-z0-9-]*|[A-Z][a-z]+[A-Z][A-Za-z0-9-]*)\b',question);exact=sorted([n for n in nodes if any(re.search(r'(?<!\w)'+re.escape(z)+r'(?!\w)',n.text) for z in terms)],key=lambda n:-sum(n.text.lower().count(z.lower()) for z in terms))[:2]
  scores={h.node.node_id:float(h.score or 0) for h in hits}
  evidence=[];seen=set();used=0;skipped=[]
  for n in [h.node for h in hits]+exact:
   if n.node_id in seen:continue
   seen.add(n.node_id)
   if used+len(n.text)>budget:skipped.append(n.node_id);continue
   pid=n.metadata['paper_id'];r=by[pid];heading=n.metadata['heading']
   if (pid,heading) not in groups:
    meta=json.loads(r['metadata_json']);bundle=pathlib.Path(r['bundle_path']) if r['bundle_path'] else None;cp=bundle/'chunks.json' if bundle else self.base/'structured'/f'{pid}_chunks.json';expected=meta['hashes']['chunks.json'] if bundle else meta['chunks_sha256']
    if sha(cp)!=expected:raise ValueError('Chunk integrity failure: '+pid)
    for c in load(cp):groups.setdefault((pid,' / '.join(c['headings'])),[]).append(c)
   cc=groups[(pid,heading)];section='\n\n'.join(c['text'] for c in cc);start=section.find(n.text)
   if start<0:raise ValueError('Evidence not found in parent section')
   if sha(r['source_path'])!=r['source_sha256']:raise ValueError('PDF source integrity failure: '+pid)
   spans=[];offset=0
   for c in cc:
    end=offset+len(c['text'])
    if end>start and offset<start+len(n.text):spans.append({'chunk_id':c['id'],'pages':c['pages'],'doc_items':c['doc_items'],'paragraph_char_span':[max(0,start-offset),min(len(c['text']),start+len(n.text)-offset)]})
    offset=end+2
   evidence.append({'evidence_id':'LI:'+n.node_id,'paper_id':pid,'title':r['title'],'text':n.text,'heading':heading,'section_char_span':[start,start+len(n.text)],'parent_section_chars':len(section),'parent_section_sha256':hashlib.sha256(section.encode()).hexdigest(),'paragraph_spans':spans,'pages':sorted({p for s in spans for p in s['pages']}),'source_path':r['source_path'],'source_sha256':r['source_sha256'],'base_retrieval_score':scores.get(n.node_id),'adjusted_retrieval_score':scores[n.node_id]*preferences.describe(pid,prefs)['retrieval_multiplier'] if scores.get(n.node_id,0)>0 else scores.get(n.node_id),**preferences.describe(pid,prefs),'origin':r['origin'],'verification':r['verification'],'role_candidate':'COMPARATOR_OR_RELATED' if re.search('baseline|compar|related',heading,re.I) else 'UNRESOLVED','role_verified':False,'hash_status':'MATCHED'})
   used+=len(n.text)
  record=self.root/'queries'/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]);record.mkdir();packet={'question':question,'search_scope':[r['paper_id'] for r in rows],'evidence':evidence,'evidence_characters':used,'budget_characters':budget,'skipped_oversize_node_ids':skipped,'seconds':time.time()-t,'index_fingerprint':key,'selection_policy':{'manual_multiplier':1.1,'scope':'rerank retrieved candidates; exact-term supplements unchanged','label_filter':label},'claims_used':False,'certified':False};save(record/'evidence.json',packet);save(record/'status.json',{'answer':'NOT_RUN','at':now()});return record,packet

def build_nodes(pid,title,digest,chunks):
 from llama_index.core import Document
 from llama_index.core.node_parser import HierarchicalNodeParser
 groups={}
 for c in chunks:groups.setdefault(tuple(c['headings']),[]).append(c)
 docs=[Document(text='\n\n'.join(c['text'] for c in cc),metadata={'paper_id':pid,'title':title,'heading':' / '.join(h),'source_sha256':digest,'pages':sorted({p for c in cc for p in c['pages']}),'attribution':'UNRESOLVED'},excluded_llm_metadata_keys=['paper_id','title','heading','source_sha256','pages','attribution'],excluded_embed_metadata_keys=['paper_id','title','heading','source_sha256','pages','attribution']) for h,cc in groups.items()]
 return HierarchicalNodeParser.from_defaults(chunk_sizes=[1024,256],chunk_overlap=40).get_nodes_from_documents(docs)

def main():
 p=argparse.ArgumentParser();p.add_argument('--config');sub=p.add_subparsers(dest='cmd',required=True)
 for name in ['status','sync-inbox']:sub.add_parser(name)
 q=sub.add_parser('init');q.add_argument('--root',help='Private data directory, outside this repository')
 q=sub.add_parser('list');q.add_argument('term',nargs='?',default='')
 q=sub.add_parser('ingest');q.add_argument('pdf');q.add_argument('--title');q.add_argument('--doi');q.add_argument('--selection-label',choices=sorted(preferences.LABELS),default='manual')
 for name in ['deactivate','restore']:q=sub.add_parser(name);q.add_argument('paper_id')
 for name in ['retrieve','ask']:
  q=sub.add_parser(name);q.add_argument('question');q.add_argument('--search-query',help='Optional English retrieval phrasing; original question retained for the answer');q.add_argument('--paper-id',action='append');q.add_argument('--max-evidence-chars',type=int,default=9000);q.add_argument('--label',choices=sorted(preferences.LABELS))
 q=sub.add_parser('mark');q.add_argument('paper_id');q.add_argument('--label',choices=sorted(preferences.LABELS),required=True)
 a=p.parse_args()
 if a.cmd=='init':
  from .config import initialize_config
  initialize_config(a.config,a.root)
 lib=Library(a.config)
 if a.cmd=='init':out=lib.initialize()
 elif a.cmd=='status':out=lib.status()
 elif a.cmd=='list':out=[dict(r,**preferences.describe(r['paper_id'],preferences.read(lib.root))) for r in lib.list(a.term)]
 elif a.cmd=='mark':out=lib.mark(a.paper_id,a.label)
 elif a.cmd=='ingest':out=lib.ingest(a.pdf,a.title,a.doi,a.selection_label)
 elif a.cmd=='sync-inbox':out=lib.sync()
 elif a.cmd in ['deactivate','restore']:out=lib.deactivate(a.paper_id,a.cmd=='restore')
 else:
  record,packet=lib.retrieve(a.search_query or a.question,a.paper_id,a.max_evidence_chars,a.label)
  if a.search_query:packet['retrieval_query']=a.search_query;packet['question']=a.question;save(record/'evidence.json',packet)
  if a.cmd=='ask':
   from .answer import answer
   out=answer(record,lib.c)
  else:out={'record':str(record),'packet':packet,'model_calls':0}
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'status':'FAILED','error':str(e)},ensure_ascii=False));raise SystemExit(1)
