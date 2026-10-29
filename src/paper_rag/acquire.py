"""Explicit, bounded public-PDF acquisition. No citation candidates are auto-promoted."""
import argparse,hashlib,json,pathlib,re,time,uuid,xml.etree.ElementTree as ET
import requests
from .library import Library,save,now,norm

class Acquisition:
    def __init__(self,out,max_requests=100,max_bytes=100_000_000):
        self.out=pathlib.Path(out);self.out.mkdir(parents=True,exist_ok=True)
        self.max_requests=max_requests;self.max_bytes=max_bytes;self.requests=0
    def get(self,url):
        if self.requests>=self.max_requests:raise RuntimeError('REQUEST_BUDGET_EXHAUSTED')
        if not url.startswith('https://'):raise ValueError('Only public HTTPS URLs supported')
        self.requests+=1;t=time.time();r={'url':url,'at':now()};data=b''
        try:
            with requests.get(url,timeout=30,stream=True,headers={'User-Agent':'PaperRAG/0.1 public scholarly acquisition'}) as z:
                r.update(status=z.status_code,final_url=z.url)
                if z.status_code==200:
                    for chunk in z.iter_content(65536):
                        data+=chunk
                        if len(data)>self.max_bytes:raise ValueError('FILE_SIZE_LIMIT')
        except Exception as e:r['error']=str(e);data=b''
        r.update(bytes=len(data),seconds=time.time()-t)
        with (self.out/'http_attempts.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
        return data,r
    def json(self,url):
        b,_=self.get(url)
        try:return json.loads(b)
        except ValueError:return {}
    def candidates(self,item):
        urls=[]
        for u in item.get('pdf_urls',[]):
            urls.append({'url':u,'doi':item.get('doi'),'version':'USER_SPECIFIED'} if isinstance(u,str) else u)
        doi=item.get('doi','').removeprefix('https://doi.org/')
        if doi.startswith(('10.1101/','10.64898/')):
            urls.append({'url':f'https://www.biorxiv.org/content/{doi}v1.full.pdf','doi':doi,'version':'PREPRINT_V1'})
        # Use current official PMC cloud API. No HTML-to-PDF substitutions.
        pmcid=item.get('pmcid')
        if pmcid:
            if not re.fullmatch(r'PMC\d+',pmcid):raise ValueError('Invalid PMCID')
            base='https://pmc-oa-opendata.s3.amazonaws.com/'
            raw,_=self.get(base+'?list-type=2&prefix='+pmcid+'.')
            try:keys=[x.text for x in ET.fromstring(raw).iter() if x.tag.endswith('}Key') and x.text.endswith('.json')]
            except ET.ParseError:keys=[]
            metas=[]
            for key in keys[:8]:
                m=self.json(base+key);save(self.out/(pmcid+'_'+hashlib.sha256(key.encode()).hexdigest()[:8]+'.json'),m)
                if m.get('pdf_url') and norm(m.get('title',''))==norm(item['title']):metas.append(m)
            for m in sorted(metas,key=lambda x:bool(x.get('is_manuscript'))):
                urls.append({'url':m['pdf_url'].replace('s3://pmc-oa-opendata/',base),'doi':m.get('doi',doi),'version':'AUTHOR_MANUSCRIPT' if m.get('is_manuscript') else 'PUBLISHED_PDF'})
        return urls
    def run(self,item,lib):
        doi=item.get('doi','').removeprefix('https://doi.org/').lower();title=item['title']
        if not title.strip():raise ValueError('A verified target title is required')
        matches=[dict(r) for r in lib.db.execute('select paper_id,title,doi,state from papers') if (doi and (r['doi'] or '').lower()==doi) or norm(r['title'])==norm(title)]
        if matches and item.get('selection_label','manual')=='manual':
            for r in matches:lib.mark(r['paper_id'],'manual','User explicitly requested existing paper')
        if matches:return {'title':title,'doi':doi,'status':'EXISTING_RECORD','matches':matches}
        for candidate in self.candidates(item):
            raw,http=self.get(candidate['url'])
            if not raw.startswith(b'%PDF-'):continue
            import pymupdf
            try:
                with pymupdf.open(stream=raw,filetype='pdf') as pdf:
                    text='\n'.join(p.get_text() for p in list(pdf)[:2]);pages=len(pdf)
                # Require title in early text, not just a cited DOI in references.
                title_ok=norm(title) in norm(text[:5000])
            except Exception:continue
            digest=hashlib.sha256(raw).hexdigest();pdfpath=self.out/(digest+'.pdf');pdfpath.write_bytes(raw)
            save(self.out/(digest+'_identity.json'),{'target':item,'source':candidate,'pages':pages,'title_match':title_ok,'source_sha256':digest})
            if not title_ok:continue  # Preserve unresolved files but never index them.
            receipt=lib.ingest(pdfpath,title=title,doi=candidate.get('doi') or doi,selection_label=item.get('selection_label','manual'))
            return {'title':title,'doi':doi,'source':candidate,'status':receipt['status'],'ingestion':receipt}
        return {'title':title,'doi':doi,'status':'PDF_NOT_OBTAINED_OR_IDENTITY_UNRESOLVED','indexed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest',help='JSON list of title, doi, pdf_urls, optional pmcid');p.add_argument('--config');p.add_argument('--max-requests',type=int,default=100)
    a=p.parse_args()
    if a.max_requests<1:p.error('max-requests must be positive')
    lib=Library(a.config);items=json.loads(pathlib.Path(a.manifest).read_text())
    if not isinstance(items,list) or not 1<=len(items)<=100:p.error('Explicit batch must contain 1–100 items')
    out=lib.root/'imports'/(time.strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]);fetch=Acquisition(out,a.max_requests);results=[]
    for item in items:
        try:r=fetch.run(item,lib)
        except Exception as e:r={'title':item.get('title'),'status':'FAILED_NOT_INDEXED','error':str(e)}
        results.append(r);save(out/'results.json',results)
        if fetch.requests>=fetch.max_requests:
            for rest in items[len(results):]:results.append({'title':rest.get('title'),'status':'NOT_RUN_REQUEST_LIMIT'})
            save(out/'results.json',results);break
    save(out/'usage.json',{'http_requests':fetch.requests,'answer_model_calls':0,'coordinator_tokens':None});print(json.dumps({'record':str(out),'results':results},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
