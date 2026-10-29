import tempfile,unittest,types
from paper_rag import preferences
class PreferencesTests(unittest.TestCase):
 def hit(self,pid,score):return types.SimpleNamespace(node=types.SimpleNamespace(metadata={'paper_id':pid}),score=score)
 def test_small_boost_not_overriding_clear_relevance(self):
  hits=[self.hit('strong',2),self.hit('ordinary',1.05),self.hit('manual',1),self.hit('zero',0)]
  prefs={'manual':{'label':'manual'},'zero':{'label':'manual'}}
  result=preferences.rerank(hits,prefs)
  self.assertEqual([h.node.metadata['paper_id'] for h in result],['strong','manual','ordinary','zero'])
  self.assertEqual(hits[2].score,1)
 def test_history_and_reversal(self):
  with tempfile.TemporaryDirectory() as td:
   preferences.write(td,'P','manual','test')
   self.assertEqual(preferences.describe('P',preferences.read(td))['retrieval_multiplier'],1.1)
   preferences.write(td,'P','citation_discovery','correction')
   self.assertEqual(preferences.describe('P',preferences.read(td))['retrieval_multiplier'],1)
   self.assertEqual(preferences.describe('UNKNOWN',{})['selection_label'],'unclassified')
 def test_invalid_label(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):preferences.write(td,'P','verified','invalid')
