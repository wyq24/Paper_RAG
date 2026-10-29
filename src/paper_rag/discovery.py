"""Bounded OpenAlex neighborhoods with cached, resumable requests and frozen output."""
import argparse,collections,hashlib,json,pathlib,sqlite3,time,urllib.parse
import requests
from .library import Library,load,save,sha,now
from .discovery_common import norm,normdoi

FIELDS='id,doi,title,publication_year,publication_date,authorships,primary_topic,cited_by_count,referenced_works,abstract_inverted_index,is_retracted,locations'
class Client:
    def __init__(self,root,max_requests=150,offline=False):
        self.root=pathlib.Path(root);self.root.mkdir(parents=True,exist_ok=True);(self.root/'cache').mkdir(exist_ok=True)
        self.max_requests=max_requests;self.offline=offline
        self.count=len((self.root/'requests.jsonl').read_text().splitlines()) if (self.root/'requests.jsonl').exists() else 0
    def get(self,params):
        url='https://api.openalex.org/works?'+urllib.parse.urlencode(params)
        key=hashlib.sha256(url.encode()).hexdigest();p=self.root/'cache'/(key+'.json')
        if p.exists():r=load(p)
        else:
            if self.offline:raise RuntimeError('OFFLINE_CACHE_MISS')
            if self.count>=self.max_requests:raise RuntimeError('REQUEST_LIMIT_REACHED')
            self.count+=1;t=time.time()
            try:
                z=requests.get(url,timeout=30);body=z.json();r={'url':url,'status':z.status_code,'body':body,'retrieved_at':now()}
            except Exception as e:r={'url':url,'status':0,'error':str(e),'body':{},'retrieved_at':now()}
            r['seconds']=time.time()-t;save(p,r)
            with (self.root/'requests.jsonl').open('a') as f:f.write(json.dumps({k:v for k,v in r.items() if k!='body'})+'\n')
            time.sleep(.2)
        if r['status']!=200:raise RuntimeError(f"Provider request failed ({r['status']}); cached; no paid fallback")
        return r

def build(root,seeds,collected,client,citers=50,max_candidates=500,queue_size=40):
    root=pathlib.Path(root)
    if (root/'RELEASE_MANIFEST.json').exists():raise ValueError('Snapshot already frozen; use a new output directory')
    identities=[];works={};coverage=[]
    for s in seeds:
        doi=normdoi(s.get('doi'))
        if not doi:raise ValueError('Explicit seed title + DOI required; unresolved titles are not trusted')
        r=client.get({'filter':'doi:https://doi.org/'+doi,'select':FIELDS,'per_page':2});matches=[w for w in r['body'].get('results',[]) if norm(w['title'])==norm(s['title']) and normdoi(w.get('doi'))==doi]
        x=dict(s,identity_status='UNRESOLVED')
        if len(matches)==1:
            w=matches[0];x.update(openalex_id=w['id'],identity_status='MATCHED_TITLE_AND_DOI_OR_LOCAL_AUTHOR',identity_basis='exact normalized title and DOI',provider_url=r['url']);works[w['id']]=w
        identities.append(x)
    save(root/'bibliographic_identity_resolved.json',identities)
    resolved=[x for x in identities if x['identity_status']!='UNRESOLVED']
    if len(resolved)<2:raise ValueError('At least two verified distinct seeds required')
    ids={s['openalex_id'] for s in resolved}
    if len(ids)!=len(resolved):raise ValueError('Duplicate seeds')
    save(root/'seeds.json',{'seeds':resolved})
    for s in resolved:
        w=works[s['openalex_id']];seen=set();queries=[]
        for sort in ['publication_date:desc','cited_by_count:desc']:
            r=client.get({'filter':'cites:'+w['id'].split('/')[-1],'sort':sort,'per_page':citers,'select':FIELDS});queries.append({k:v for k,v in r.items() if k!='body'})
            for c in r['body'].get('results',[]):
                if w['id'] in c.get('referenced_works',[]):works[c['id']]=c;seen.add(c['id'])
        coverage.append({'seed':w['id'],'paper_id':s['paper_id'],'provider_cited_by_count':w['cited_by_count'],'reference_count':len(w.get('referenced_works',[])),'unique_observed_citers':len(seen),'coverage_fraction_vs_provider_count':len(seen)/w['cited_by_count'] if w['cited_by_count'] else None,'queries':queries})
    counts=collections.Counter(ref for s in ids for ref in works[s].get('referenced_works',[]))
    # One bounded expansion only: seed references and sampled citers; their reference IDs remain stubs.
    pool=set(works)-ids;missing=[k for k,_ in counts.most_common() if k not in works][:max(0,max_candidates-len(pool))];pool.update(missing)
    for start in range(0,len(missing),50):
        r=client.get({'filter':'openalex_id:'+'|'.join(k.split('/')[-1] for k in missing[start:start+50]),'select':FIELDS,'per_page':100})
        works.update({w['id']:w for w in r['body'].get('results',[])})
    if len(pool)>max_candidates:raise ValueError('Candidate limit exceeded; reduce seed count or citers per seed')
    save(root/'graph_work_metadata.json',works);save(root/'candidate_pool.json',{'ids':sorted(pool),'metadata_missing':sorted(pool-set(works))});save(root/'neighborhood_coverage.json',coverage)
    edges=[{'citing':w['id'],'cited':ref,'provider':'OpenAlex','relation':'CITES','retrieved_at':now(),'identity_confidence':'PROVIDER_EDGE_NOT_SCIENTIFIC_AGREEMENT'} for w in works.values() for ref in w.get('referenced_works',[])]
    (root/'citation_edges.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in edges))
    allids=set(works)|{e['cited'] for e in edges}
    (root/'citation_graph.jsonl').write_text(''.join(json.dumps({'id':k,'metadata_status':'PROVIDER_RECORD' if k in works else 'UNEXPANDED_REFERENCE_STUB','title':works.get(k,{}).get('title')})+'\n' for k in sorted(allids)))
    from .ranking import run
    run(root,collected,queue_size)
    save(root/'USAGE.json',{'api_requests_including_prior_attempts':client.count,'answer_model_calls':0,'screening':'NOT_RUN_HUMAN_REVIEW_REQUIRED','coordinator_tokens':None})
    names=['bibliographic_identity_resolved.json','graph_work_metadata.json','candidate_relations.jsonl','citation_edges.jsonl','citation_graph.jsonl','neighborhood_coverage.json','topic_communities.json','candidate_rankings.csv','candidate_explanations.md','DISCOVERY_REPORT_ZH.md','candidate_metadata.sqlite','USAGE.json']
    save(root/'RELEASE_MANIFEST.json',{'snapshot':now(),'seed_count':len(resolved),'files':{n:sha(root/n) for n in names}})
    return {'snapshot':str(root),'verified_seeds':len(resolved),'candidates':len(pool),'requests':client.count,'automatic_ingestion':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed-file',required=True);p.add_argument('--out',required=True);p.add_argument('--config');p.add_argument('--max-requests',type=int,default=150);p.add_argument('--citers-per-order',type=int,default=50);p.add_argument('--max-candidates',type=int,default=500);p.add_argument('--queue-size',type=int,default=40);p.add_argument('--offline',action='store_true')
    a=p.parse_args();seeds=load(a.seed_file)
    if not 2<=len(seeds)<=20 or not 1<=a.citers_per_order<=100 or not 1<=a.queue_size<=100 or a.max_requests<1 or a.max_candidates<1:p.error('Invalid bounded parameters')
    lib=Library(a.config);collected=lib.list();root=pathlib.Path(a.out).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
    params={'seeds':seeds,'citers':a.citers_per_order,'max_candidates':a.max_candidates,'queue_size':a.queue_size}
    if (root/'PLAN.json').exists() and load(root/'PLAN.json')!=params:raise ValueError('Cannot resume with changed plan; use a new output directory')
    save(root/'PLAN.json',params)
    try:result=build(root,seeds,collected,Client(root,a.max_requests,a.offline),a.citers_per_order,a.max_candidates,a.queue_size)
    except Exception as e:save(root/('failure_'+str(time.time_ns())+'.json'),{'at':now(),'error':str(e)});raise
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
