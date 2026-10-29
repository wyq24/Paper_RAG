"""User curation overlay; never changes source artifacts or scientific status."""
import json,pathlib,uuid,datetime,math
LABELS={'manual','citation_discovery','historical','unclassified'}
def read(root):
 p=pathlib.Path(root)/'paper_preferences.json'
 return json.loads(p.read_text()) if p.exists() else {}
def describe(pid,prefs):
 label=prefs.get(pid,{}).get('label','unclassified')
 return {'selection_label':label,'manual_priority':label=='manual','retrieval_multiplier':1.1 if label=='manual' else 1.0}
def write(root,pid,label,reason):
 if label not in LABELS:raise ValueError('Unknown selection label')
 root=pathlib.Path(root);prefs=read(root);before=prefs.get(pid)
 entry={'label':label,'reason':reason,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 audit=root/'preference_history';audit.mkdir(exist_ok=True)
 token=uuid.uuid4().hex
 (audit/(token+'.json')).write_text(json.dumps({'paper_id':pid,'before':before,'after':entry},ensure_ascii=False,indent=2))
 prefs[pid]=entry;p=root/'paper_preferences.json';tmp=root/(token+'.tmp');tmp.write_text(json.dumps(prefs,ensure_ascii=False,indent=2));tmp.replace(p)
 return describe(pid,prefs)
def rerank(hits,prefs):
 def score(h):
  value=float(h.score or 0)
  return value*describe(h.node.metadata['paper_id'],prefs)['retrieval_multiplier'] if value>0 and math.isfinite(value) else value
 return sorted(hits,key=score,reverse=True)
