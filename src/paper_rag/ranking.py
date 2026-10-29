from .discovery_common import *
import numpy as np,networkx as nx,csv,sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

def weighted_cosine(a,b,weights):
 denominator=math.sqrt(sum(weights[x] for x in a)*sum(weights[x] for x in b))
 return sum(weights[x] for x in a&b)/denominator if denominator else 0.0
def incoming_index(refs):
 incoming=collections.defaultdict(set)
 for k,rr in refs.items():
  for ref in rr:incoming[ref].add(k)
 return incoming

def run(root, collected, queue_size=40):
 global R
 R=pathlib.Path(root)
 works=load(R/'graph_work_metadata.json');seeds=load(R/'seeds.json')['seeds'];seedids=[x['openalex_id'] for x in seeds];seedby={x['openalex_id']:x for x in seeds};pool=load(R/'candidate_pool.json')['ids']
 oldtitles={norm(x['title']) for x in collected};olddois={normdoi(x.get('doi')) for x in collected if x.get('doi')};oldids={x.get('openalex_id') for x in collected}
 refs={k:set(w.get('referenced_works',[])) for k,w in works.items()};incoming=incoming_index(refs)
 df=collections.Counter(ref for rr in refs.values() for ref in rr)
 rw={ref:math.log(1+(len(works)+1)/(count+1))/math.sqrt(1+math.log1p(works.get(ref,{}).get('cited_by_count',0))) for ref,count in df.items()}
 cw={k:1/math.log(2+len(rr)) for k,rr in refs.items()}
 rnorm={k:sum(rw[r] for r in rr) for k,rr in refs.items()};cnorm={k:sum(cw[c] for c in cs) for k,cs in incoming.items()}
 def metrics(a,b):
  sharedrefs=refs.get(a,set())&refs.get(b,set());sharedciters=incoming.get(a,set())&incoming.get(b,set());bc=weighted_cosine(refs.get(a,set()),refs.get(b,set()),rw);co=weighted_cosine(incoming.get(a,set()),incoming.get(b,set()),cw)
  return {'seed_id':b,'shared_reference_ids':sorted(sharedrefs),'shared_citing_paper_ids':sorted(sharedciters),'bibliographic_coupling_weighted_cosine':bc,'co_citation_weighted_cosine_sampled':co,'candidate_cites_seed':b in refs.get(a,set()),'seed_cites_candidate':a in refs.get(b,set())}
 g=nx.Graph();g.add_nodes_from(seedids);pair=[]
 for i,a in enumerate(seedids):
  for b in seedids[i+1:]:
   m=metrics(a,b);weight=(m['bibliographic_coupling_weighted_cosine']+m['co_citation_weighted_cosine_sampled'])/2;pair.append({'seed_a':a,**m})
   if weight>=.1:g.add_edge(a,b,weight=weight)
 communities=nx.community.louvain_communities(g,weight='weight',seed=27) if g.number_of_edges() else [{s} for s in seedids];cmap={sid:i for i,c in enumerate(communities) for sid in c};save(R/'seed_pair_metrics.json',pair)
 save(R/'topic_communities.json',{'algorithm':'NetworkX Louvain, seed27, seed graph mean weighted coupling/cocitation>=0.1; descriptive sample communities, not validated scientific fields','communities':[{'id':i,'seed_ids':sorted(c),'titles':[works[k]['title'] for k in sorted(c)]} for i,c in enumerate(communities)]})
 ids=sorted(works);texts=[works[k]['title']+' '+abstract(works[k]) for k in ids];vectorizer=TfidfVectorizer(stop_words='english',ngram_range=(1,2),min_df=1,max_features=30000);tf=vectorizer.fit_transform(texts);svd=TruncatedSVD(n_components=min(64,len(ids)-1,tf.shape[1]-1),random_state=27);latent=normalize(svd.fit_transform(tf));indices={k:i for i,k in enumerate(ids)};center=normalize(latent[[indices[k] for k in seedids]].mean(axis=0).reshape(1,-1));semantic=(latent@center.T).flatten();sem={k:float(semantic[indices[k]]) for k in ids}
 rows=[];details={};excluded=[];seen={}
 for k in pool:
  if k not in works:continue
  w=works[k];doi=(w.get('doi') or '').lower().replace('https://doi.org/','');titlekey=norm(w.get('title'));collected=k in oldids or titlekey in oldtitles or bool(doi and doi in olddois)
  if collected:excluded.append({'id':k,'reason':'EXISTS_IN_PROVIDED_LOCAL_CATALOG'});continue
  first=(w.get('authorships') or [{}])[0].get('author',{}).get('display_name','');dedupkey=doi or titlekey+'|'+norm(first)
  if dedupkey in seen:excluded.append({'id':k,'reason':'DUPLICATE_CANDIDATE','canonical':seen[dedupkey]});continue
  seen[dedupkey]=k
  text=w.get('title','')+' '+abstract(w);domain=True;ms=[metrics(k,s) for s in seedids];details[k]=ms
  backward=[m['seed_id'] for m in ms if m['seed_cites_candidate']];forward=[m['seed_id'] for m in ms if m['candidate_cites_seed']];connected=[m['seed_id'] for m in ms if m['candidate_cites_seed'] or m['seed_cites_candidate'] or m['bibliographic_coupling_weighted_cosine']>=.15 or m['co_citation_weighted_cosine_sampled']>=.15];strength=collections.Counter()
  for m in ms:
   if m['seed_id'] in connected:strength[cmap[m['seed_id']]]+=max(m['bibliographic_coupling_weighted_cosine'],m['co_citation_weighted_cosine_sampled'],.3*bool(m['candidate_cites_seed'] or m['seed_cites_candidate']))
  participation=1-sum((v/sum(strength.values()))**2 for v in strength.values()) if strength else 0
  bc=max(m['bibliographic_coupling_weighted_cosine'] for m in ms);co=max(m['co_citation_weighted_cosine_sampled'] for m in ms);year=w.get('publication_year') or 0
  rows.append({'id':k,'doi':doi,'title':w['title'],'year':year,'provider_citations':w['cited_by_count'],'abstract_characters':len(abstract(w)),'metadata_status':'OPENALEX_ONLY_NOT_YET_CROSSCHECKED','backward_seed_count':len(backward),'forward_seed_count':len(forward),'independent_seed_connections':len(set(connected)),'direct_seed_connections':len(set(backward+forward)),'max_weighted_coupling':bc,'max_sampled_cocitation':co,'bridge_participation':participation,'connected_communities':len(strength),'lsa_cosine':sem[k],'domain_keyword_match':domain,'subtopic':(w.get('primary_topic') or {}).get('display_name','UNCLASSIFIED'),'retracted':w.get('is_retracted',False),'coverage':'sampled forward neighborhood; missing refs are not negative scientific evidence','uncollected_scope':'provided local catalog snapshot; no live external library access'})
 # Local-year citation percentile, no inference of globally normalized impact.
 years=collections.defaultdict(list)
 for r in rows:years[r['year']].append(r['provider_citations'])
 for r in rows:
  vals=years[r['year']];r['local_year_citation_percentile']=sum(v<=r['provider_citations'] for v in vals)/len(vals);relevance=max(0,r['lsa_cosine']);multi=math.log1p(r['independent_seed_connections'])/math.log1p(len(seeds));globalpenalty=1/math.sqrt(1+math.log1p(r['provider_citations']));yrboost=1 if r['year']>=datetime.datetime.now().year-2 else .35;bridge=r['bridge_participation']*multi
  r['scores']={'FOUNDATIONAL':r['backward_seed_count']/len(seeds)*globalpenalty,'EMERGING':r['forward_seed_count']/len(seeds)*yrboost*(.8+.2*r['local_year_citation_percentile']),'ADJACENT':max(r['max_weighted_coupling'],r['max_sampled_cocitation'])*multi,'BRIDGE':bridge}
  r['eligible']=bool(r['domain_keyword_match'] and relevance>=.12 and r['abstract_characters']>=200 and not r['retracted'])
 # independent channel orderings, normalized rank fusion + diversity selection
 eligible=[r for r in rows if r['eligible']];channels={}
 for ch in ['FOUNDATIONAL','EMERGING','ADJACENT','BRIDGE']:
  rr=[r for r in eligible if (ch!='FOUNDATIONAL' or r['backward_seed_count']>=2) and (ch!='EMERGING' or r['year']>=datetime.datetime.now().year-2 and r['forward_seed_count']>=2) and (ch!='BRIDGE' or r['connected_communities']>=2 and r['bridge_participation']>=.2)]
  rr.sort(key=lambda r:(-r['scores'][ch],-r['lsa_cosine'],r['id']));channels[ch]=[r['id'] for r in rr]
  for i,r in enumerate(rr):r.setdefault('channel_ranks',{})[ch]=i+1
 for r in eligible:r['fusion_score']=sum(1/(60+n) for n in r.get('channel_ranks',{}).values());r['priority_score']=r['fusion_score']*(.7+.3*r['lsa_cosine'])
 by={r['id']:r for r in rows};queue=[];counts=collections.Counter()
 # Round-robin independent channels ensures not only high-citation/foundational results; max18 per provider topic.
 for depth in range(max([len(v) for v in channels.values()]+[0])):
  for ch,ks in channels.items():
   if depth>=len(ks):continue
   r=by[ks[depth]]
   if r in queue or counts[r['subtopic']]>=18:continue
   queue.append(r);r['selected_via']=ch;counts[r['subtopic']]+=1
   if len(queue)==queue_size:break
  if len(queue)==queue_size:break
 for i,r in enumerate(queue,1):r['queue_rank']=i
 save(R/'channel_rankings.json',channels);save(R/'all_candidate_metrics.json',rows);save(R/'excluded_collected_or_duplicate.json',excluded);save(R/'ranked_queue.json',queue)
 with (R/'candidate_rankings.csv').open('w') as f:
  fields=[k for k in (queue[0] if queue else {'id':None,'title':None}) if k not in ['scores','channel_ranks']];writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(queue)
 (R/'candidate_relations.jsonl').write_text(''.join(json.dumps({'candidate_id':k,'provider':'OpenAlex','relations':ms},ensure_ascii=False)+'\n' for k,ms in details.items()))
 semanticrank=sorted(eligible,key=lambda r:(-r['lsa_cosine'],r['id']));topids={r['id'] for r in semanticrank[:queue_size]};queueids={r['id'] for r in queue};save(R/'semantic_baseline.json',{'method':'TF-IDF unigrams+bigrams -> TruncatedSVD64 latent semantic analysis -> cosine to mean seed vector; no external embeddings/model call; same citation-derived candidate pool, not independent discovery recall','top_candidates':[{'id':r['id'],'title':r['title'],'score':r['lsa_cosine']} for r in semanticrank[:queue_size]],'overlap_count':len(topids&queueids),'jaccard':len(topids&queueids)/len(topids|queueids) if topids|queueids else 0,'caveat':'Unsupervised text similarity is not human relevance gold'})
 db=sqlite3.connect(R/'candidate_metadata.sqlite');db.execute('create table if not exists metadata (openalex_id text primary key, title text, doi text, abstract text, metadata_json text)');db.executemany('insert or replace into metadata values (?,?,?,?,?)',[(k,w['title'],w.get('doi'),abstract(w),json.dumps(w,ensure_ascii=False)) for k,w in works.items()]);db.commit();db.close()
 save(R/'RANKING_METHOD.json',{'coupling':'sum shared reference weights / sqrt(sum reference weights A * sum reference weights B)','reference_weight':'log(1+(N+1)/(observed_df+1))/sqrt(1+log(1+global_citations_when_known)); unknown citation counts not imputed as verified zero','cocitation':'weighted cosine over shared citing papers observed in bounded graph; citing-paper weight 1/log(2+reference_count)','bridge':'participation coefficient across Louvain seed communities; based on direct or cosine>=0.15 links','year_normalization':'within harvested candidate year citation percentile; only20% component of emerging score; cutoff=current year minus 2','diversity':'channel round robin; at most18 per provider topic','semantic_relevance_threshold':.12,'no_gold':'all weights fixed heuristics, human judgment remains required'})
 print('ranked',len(rows),'eligible',len(eligible),'queue',len(queue),'communities',len(communities),'overlap',len(topids&queueids),flush=True)
 for r in queue[:12]:print(r['queue_rank'],r['selected_via'],r['year'],r['title'],flush=True)


 report=['# Citation discovery queue', '', 'Provider-only metadata; human review required. Citation relationships do not establish scientific agreement or method inheritance.', '']
 for r in queue:
  report += [f"## {r['queue_rank']}. {r['title']}", '', f"ID: {r['id']} | DOI: {r['doi']} | Channel: {r['selected_via']}", f"Independent seed connections: {r['independent_seed_connections']}; abstract cosine: {r['lsa_cosine']:.4f}", '']
  for m in details[r['id']]:
   if m['shared_reference_ids'] or m['shared_citing_paper_ids'] or m['candidate_cites_seed'] or m['seed_cites_candidate']:
    report += [f"Seed {m['seed_id']}: candidate cites seed={m['candidate_cites_seed']}; seed cites candidate={m['seed_cites_candidate']}", 'Shared references: '+', '.join(m['shared_reference_ids']), 'Shared citing papers: '+', '.join(m['shared_citing_paper_ids']), '']
 (R/'candidate_explanations.md').write_text('\n'.join(report))
 (R/'DISCOVERY_REPORT_ZH.md').write_text(f"# 有界引用发现报告\n\n种子 {len(seeds)} 篇；候选 {len(rows)} 篇；满足元数据与相似度规则 {len(eligible)} 篇；推荐队列 {len(queue)} 篇。\n\n引用队列与同候选池文本相似度前列重合 {len(topids&queueids)} 篇。这不构成独立召回率或科学相关性认证。\n\n请查看 candidate_explanations.md 的逐条关系、neighborhood_coverage.json 的采样覆盖和 USAGE.json 的实际请求数。未运行模型筛选，未自动入库。候选身份仍需独立核验，最终由人判断研究价值。\n")
