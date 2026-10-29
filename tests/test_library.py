"""Isolated integration tests; synthetic PDFs never enter the real library."""
import pathlib,tempfile,unittest,json,shutil
from paper_rag.library import Library,load,save,sha
from paper_rag.answer import validate
import os
from paper_rag.worker import execute
class DailyLibraryTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.p=pathlib.Path(cls.tmp.name);config={'library_root':str(cls.p/'library'),'base_root':None};save(cls.p/'config.json',config);cls.lib=Library(cls.p/'config.json');cls.lib.initialize();cls.old_env=os.environ.get('PAPER_RAG_CONFIG');os.environ['PAPER_RAG_CONFIG']=str(cls.p/'config.json')
  import pymupdf
  pdf=pymupdf.open();page=pdf.new_page();page.insert_text((60,60),'SYNTHETIC TEST ONLY - Zorbax binding model',fontsize=18);page.insert_text((60,110),'Methods',fontsize=14);page.insert_textbox(pymupdf.Rect(60,140,530,700),'The synthetic Zorbax method takes a target sequence and a ligand identifier as inputs. The output is a binary binding label. This is artificial test text and not a scientific paper. We use this fixture only to validate source ingestion, indexing, citations, duplicate detection, and recovery. The comparison baseline predicts a constant negative label. No experimental result is reported. '*3,fontsize=12);cls.pdf=cls.p/'fixture.pdf';pdf.save(cls.pdf);pdf.close();cls.original=sha(cls.pdf);cls.receipt=cls.lib.ingest(cls.pdf,title='SYNTHETIC TEST ONLY: Zorbax method');cls.pid=cls.receipt['paper_id']
 @classmethod
 def tearDownClass(cls):
  cls.lib.db.close();cls.tmp.cleanup()
  if cls.old_env is None:os.environ.pop('PAPER_RAG_CONFIG',None)
  else:os.environ['PAPER_RAG_CONFIG']=cls.old_env
 def test_01_parse_commit_source_preserved(self):
  self.assertEqual(self.receipt['status'],'READY',self.receipt);self.assertEqual(sha(self.pdf),self.original);self.assertEqual(self.lib.status()['papers'],1)
 def test_02_duplicate(self):
  self.assertEqual(self.lib.ingest(self.pdf)['status'],'DUPLICATE_UNCHANGED');self.assertEqual(self.lib.status()['papers'],1)
 def test_03_retrieve_with_parent_and_cache(self):
  for _ in range(2):
   rec,pkt=self.lib.retrieve('Zorbax method inputs output',papers=[self.pid]);self.assertTrue(pkt['evidence']);self.assertTrue(all(e['pages']==[1] for e in pkt['evidence']));self.assertTrue(any('binary binding label' in e['text'] for e in pkt['evidence']));self.assertTrue(all(e['section_char_span'][1]<=e['parent_section_chars'] for e in pkt['evidence']))
 def test_04_reversible_deactivation(self):
  self.lib.deactivate(self.pid,False)
  with self.assertRaises(ValueError):self.lib.retrieve('Zorbax',papers=[self.pid])
  self.lib.deactivate(self.pid,True);self.assertTrue(pathlib.Path(self.receipt['document_dir'],'source.pdf').exists())
 def test_05_failed_parse_never_indexed(self):
  p=self.p/'invalid.pdf';p.write_bytes(b'not a PDF');r=self.lib.ingest(p);self.assertEqual(r['status'],'FAILED_NOT_INDEXED');self.assertEqual(self.lib.status()['papers'],1)
 def test_06_citation_fail_closed(self):
  pkt={'evidence':[{'evidence_id':'e1','text':'Output is binary.'}]};a={'direct_answer':'Binary','statements':[{'text':'Binary','ownership_status':'authors_method','evidence_ids':['e1'],'exact_quote':'Output is binary.'}],'assumptions_and_conditions':[],'limitations':[]};self.assertEqual(validate(a,pkt),[]);a['statements'][0]['evidence_ids']=['e2'];self.assertIn('UNKNOWN_OR_MISSING_CITATION',validate(a,pkt))
 def test_07_quote_list_requires_every_anchor(self):
  pkt={'evidence':[{'evidence_id':'e','text':'First quote. Second quote.'}]};a={'direct_answer':'test','statements':[{'text':'test','ownership_status':'unresolved','evidence_ids':['e'],'exact_quote':['First quote.','Second quote.']}],'assumptions_and_conditions':[],'limitations':[]};self.assertEqual(validate(a,pkt),[]);a['statements'][0]['exact_quote'].append('invented');self.assertIn('QUOTE_NOT_FOUND',validate(a,pkt))
 def test_08_tampered_source_rejected(self):
  source=pathlib.Path(self.receipt['document_dir'])/'source.pdf';original=source.read_bytes();source.chmod(0o644);source.write_bytes(original+b'tampered')
  try:
   with self.assertRaisesRegex(ValueError,'integrity failure'):self.lib.retrieve('Zorbax inputs',papers=[self.pid])
  finally:source.write_bytes(original);source.chmod(0o444)
 def test_09_mcp_worker_checklist_and_semantic_boundary(self):
  plan=execute({'operation':'evidence_checklist','question':'Who owns this method?','extra_fields':[]})
  results=execute({'operation':'search','query':'Zorbax method','paper_ids':[self.pid]})['results']
  parent=execute({'operation':'fetch','id':results[0]['id']})
  items=[{'field':f,'status':'missing','statement':'unknown','reason':'not retrieved'} for f in plan['fields']]
  items[0]={'field':plan['fields'][0],'status':'supported','statement':'DELIBERATELY FALSE: the comparator owns the Zorbax method','citations':[{'id':results[0]['id'],'quote':parent['text'][:70]}]}
  audit=execute({'operation':'audit_answer','checklist_id':plan['checklist_id'],'items':items})
  self.assertFalse(audit['errors']);self.assertEqual(audit['semantic_entailment'],'NOT_VERIFIED')
  items[0]['citations'][0]['quote']='fabricated quote 992981'
  self.assertEqual(execute({'operation':'audit_answer','checklist_id':plan['checklist_id'],'items':items})['status'],'FAIL')
  items.append(items[0]);self.assertIn('DUPLICATE_FIELD:'+plan['fields'][0],execute({'operation':'audit_answer','checklist_id':plan['checklist_id'],'items':items})['errors'])
 def test_10_pdf_page_and_unknown_graph(self):
  page=execute({'operation':'source_page','paper_id':self.pid,'page':1,'render':True})
  self.assertTrue(page['image_base64']);self.assertEqual(page['hash_status'],'MATCHED')
  self.assertEqual(execute({'operation':'citation_network','identifier':self.pid})['status'],'NO_CITATION_SNAPSHOT')
  with self.assertRaises(ValueError):execute({'operation':'source_page','paper_id':self.pid,'page':0})
 def test_11_result_path_traversal(self):
  with self.assertRaises(ValueError):execute({'operation':'fetch','id':'../../secrets'})
 def test_12_missing_fields_fail(self):
  p=execute({'operation':'evidence_checklist','question':'Define labels','extra_fields':[]})
  self.assertEqual(execute({'operation':'audit_answer','checklist_id':p['checklist_id'],'items':[]})['status'],'FAIL')
if __name__=='__main__':unittest.main(verbosity=2)
