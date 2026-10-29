"""Additive evidence checks, frozen citation graph access, and PDF-page extraction."""
import base64,hashlib,json,pathlib,re,uuid
HERE=pathlib.Path(__file__).resolve().parent
from .config import read_config
def record_root():return pathlib.Path(read_config()['library_root'])/'mcp_records'
def graph_root():
 value=read_config().get('citation_snapshot')
 if not value:raise ValueError('NO_CITATION_SNAPSHOT: run bounded discovery and configure its path')
 return pathlib.Path(value)
REQUIRED=['subject_and_method_ownership','target_or_output_definition','dataset_and_sample_unit','experimental_conditions','comparator_and_metric','denominator_exclusions_and_aggregation','limitations_and_uncertainty']

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def artifact(kind,data):
 p=record_root()/kind/(uuid.uuid4().hex+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2));return p.stem

def checked_graph(name):
 p=graph_root()/name;manifest=json.loads((graph_root()/'RELEASE_MANIFEST.json').read_text())
 if digest(p)!=manifest['files'][name]:raise ValueError('Frozen citation asset integrity failure')
 return p

def run(req,lib,fetch):
 op=req['operation']
 if op=='evidence_checklist':
  question=req['question'].strip()
  if not question or len(question)>4000:raise ValueError('Invalid question')
  extra=req.get('extra_fields',[])
  if not isinstance(extra,list) or len(extra)>25 or any(not isinstance(x,str) or not x.strip() or len(x)>120 for x in extra) or len(set(extra))!=len(extra) or set(extra)&set(REQUIRED):raise ValueError('Invalid extra fields')
  data={'question':question,'fields':REQUIRED,'extra_fields':req.get('extra_fields',[]),'instruction':'For each field supply cited evidence or explicitly mark missing/not_applicable with a reason. This is a generic checklist, not proof of complete scientific coverage.'}
  data['checklist_id']=artifact('checklists',data);return data
 if op=='audit_answer':
  cid=req['checklist_id']
  if not re.fullmatch('[a-f0-9]{32}',cid):raise ValueError('Invalid checklist ID')
  plan=json.loads((record_root()/'checklists'/f'{cid}.json').read_text())
  fields=REQUIRED+plan['extra_fields'];items=req['items']
  if len(items)>40:raise ValueError('Too many assertions')
  errors=[];checked=[];seen=set();missing=[]
  for item in items:
   field=item.get('field');status=item.get('status')
   if field in seen:errors.append('DUPLICATE_FIELD:'+str(field))
   seen.add(field)
   if field not in fields:errors.append('UNKNOWN_FIELD:'+str(field))
   if status not in ['supported','missing','not_applicable']:errors.append('INVALID_STATUS:'+str(field))
   if not item.get('statement','').strip():errors.append('EMPTY_STATEMENT:'+str(field))
   anchors=[]
   if status=='supported':
    cites=item.get('citations',[])
    if not cites:errors.append('NO_CITATIONS:'+str(field))
    for c in cites:
     e=fetch({'operation':'fetch','id':c['id'],'offset':c.get('offset',0)})
     quote=c.get('quote','');ok=bool(quote and quote in e['text'])
     if not ok:errors.append('QUOTE_NOT_FOUND:'+str(field))
     anchors.append({'id':c['id'],'quote_matched':ok,'pages':e['paragraphs'],'paper_id':e['paper_id'],'source_sha256':e['source_sha256']})
   else:
    if not item.get('reason','').strip():errors.append('MISSING_REASON:'+str(field))
    if status=='missing':missing.append(field)
   checked.append({'field':field,'status':status,'anchors':anchors})
  errors+=['UNCOVERED_FIELD:'+f for f in fields if f not in seen]
  result={'status':'FAIL' if errors else ('GAPS_DISCLOSED' if missing else 'STRUCTURAL_CHECKS_PASS'),'errors':errors,'missing_fields':missing,'checked':checked,'semantic_entailment':'NOT_VERIFIED','method_ownership':'NOT_INDEPENDENTLY_VERIFIED','scientific_accuracy_certified':False,'instruction':'This validates field accounting, exact quotes and source integrity only. It does not establish that statements follow from quotes or validate prose outside submitted items. Report these limitations; do not call this scientifically verified.'}
  result['audit_id']=artifact('audits',{'request':req,'result':result});return result
 if op=='citation_network':
  if not lib.c.get('citation_snapshot'):return {'status':'NO_CITATION_SNAPSHOT','results':[],'limitations':['No configured graph; absence is not absence of citations.']}
  q=req['identifier'];mode=req.get('mode','references');offset=req.get('offset',0)
  if offset<0 or mode not in ['references','citing','relations']:raise ValueError('Invalid pagination or mode')
  identities=json.loads(checked_graph('bibliographic_identity_resolved.json').read_text())
  matches=[x for x in identities if x['paper_id']==q]
  confidence='PROVIDER_ID_ONLY'
  if matches:
   x=matches[0];confidence=x['identity_status']
   if confidence!='MATCHED_TITLE_AND_DOI_OR_LOCAL_AUTHOR':return {'status':'UNRESOLVED_IDENTITY','identity_status':confidence}
   q=x['openalex_id']
  elif re.fullmatch('W[0-9]+',q):q='https://openalex.org/'+q
  if not re.fullmatch(r'https://openalex.org/W[0-9]+',q):return {'status':'NO_VERIFIED_GRAPH_MAPPING','instruction':'Supply a registered paper_id or OpenAlex W ID. Not indexed does not mean no citations.'}
  result=[]
  if mode=='relations':
   with checked_graph('candidate_relations.jsonl').open() as f:
    for line in f:
     d=json.loads(line)
     for relation in d['relations']:
      if q in [d['candidate_id'],relation['seed_id']]:result.append(dict(relation,candidate_id=d['candidate_id'],provider=d['provider']))
  else:
   with checked_graph('citation_edges.jsonl').open() as f:
    for line in f:
     d=json.loads(line)
     if d['citing' if mode=='references' else 'cited']==q:result.append(d)
  coverage=[x for x in json.loads(checked_graph('neighborhood_coverage.json').read_text()) if x['seed']==q]
  selected=result[offset:offset+10]
  metadata=json.loads(checked_graph('graph_work_metadata.json').read_text())
  ids={q}
  for entry in selected:
   ids.update(entry[k] for k in ['citing','cited','candidate_id','seed_id'] if k in entry)
  works={i:({k:metadata[i].get(k) for k in ['title','doi','publication_year']} if i in metadata else {'metadata_status':'UNEXPANDED_REFERENCE_STUB'}) for i in ids}
  # Preserve exact shared IDs; paginate relations at record level, without silently discarding them.
  out={'identifier':q,'identity_status':confidence,'mode':mode,'results':selected,'total_in_snapshot':len(result),'next_offset':offset+10 if offset+10<len(result) else None,'coverage':coverage,'snapshot':json.loads((graph_root()/'RELEASE_MANIFEST.json').read_text()).get('snapshot','UNSPECIFIED'),'limitations':['Bounded seed-neighborhood snapshot, not a complete citation network; unexpanded nodes may have no metadata.','Citation does not establish agreement or method inheritance.','No live fetch, corpus expansion, or automatic paper ingestion.']}
  out['works']=works
  return out
 if op=='source_page':
  row=lib.db.execute("SELECT * FROM papers WHERE paper_id=? AND state='READY'",(req['paper_id'],)).fetchone()
  if not row:raise ValueError('Unknown or inactive paper')
  path=pathlib.Path(row['source_path'])
  if digest(path)!=row['source_sha256']:raise ValueError('Source integrity failure')
  import pymupdf
  with pymupdf.open(path) as doc:
   page=req['page']
   if page<1 or page>len(doc):raise ValueError('Page out of range')
   p=doc[page-1];raw=p.get_text();out={'paper_id':row['paper_id'],'title':row['title'],'pdf_page':page,'page_count':len(doc),'text':raw[:20000],'text_truncated':len(raw)>20000,'source_sha256':row['source_sha256'],'hash_status':'MATCHED','verification':row['verification'],'limitations':'Original page image is available for tables, figures and formulas. Text extraction is not structured-table or OCR certification.'}
   if req.get('render',True):out['image_base64']=base64.b64encode(p.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False).tobytes('png')).decode()
   record={k:v for k,v in out.items() if k!='image_base64'};out['record_id']=artifact('pages',record);return out
 raise ValueError('Unknown extension operation')
