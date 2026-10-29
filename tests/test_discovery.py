import json,pathlib,tempfile,unittest
from paper_rag.discovery import build,Client
from paper_rag.ranking import weighted_cosine,incoming_index
from paper_rag.library import load

class FakeClient:
    count=0
    def get(self,p):
        self.count+=1
        def work(n,refs):
            return {'id':'https://openalex.org/W'+str(n),'doi':'https://doi.org/10.1234/'+str(n),'title':'Synthetic protein binding method '+str(n),'publication_year':2025,'cited_by_count':5,'referenced_works':['https://openalex.org/W'+str(x) for x in refs],'abstract_inverted_index':{'protein':list(range(0,60,2)),'binding':list(range(1,60,2))},'is_retracted':False,'primary_topic':{'display_name':'Synthetic protein'}}
        f=p['filter']
        if f.startswith('doi:'):ws=[work(int(f.split('/')[-1]),[3])]
        elif f.startswith('cites:'):ws=[work(4,[1,2,3])]
        else:ws=[work(3,[])]
        return {'status':200,'url':'https://example.invalid/fixture','retrieved_at':'synthetic','body':{'results':ws}}

class DiscoveryTests(unittest.TestCase):
    def test_exact_shared_ids_and_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            seeds=[{'paper_id':'P'+str(i),'title':'Synthetic protein binding method '+str(i),'doi':'10.1234/'+str(i)} for i in [1,2]]
            build(d,seeds,[],FakeClient(),citers=2,max_candidates=10,queue_size=4)
            root=pathlib.Path(d);self.assertTrue((root/'RELEASE_MANIFEST.json').exists())
            rel=[json.loads(s) for s in (root/'candidate_relations.jsonl').read_text().splitlines()]
            four=next(x for x in rel if x['candidate_id'].endswith('W4'))
            self.assertEqual(four['relations'][0]['shared_reference_ids'],['https://openalex.org/W3'])
            with self.assertRaisesRegex(ValueError,'frozen'):build(d,seeds,[],FakeClient())
    def test_normalized_similarity(self):
        self.assertEqual(weighted_cosine({'a'},{'a'},{'a':2}),1)
        self.assertEqual(weighted_cosine(set(),{'a'},{'a':2}),0)
        self.assertEqual(incoming_index({'x':{'z'},'y':{'z'}})['z'],{'x','y'})
    def test_offline_no_network(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'OFFLINE_CACHE_MISS'):Client(d,offline=True).get({'filter':'doi:x'})
if __name__=='__main__':unittest.main()
