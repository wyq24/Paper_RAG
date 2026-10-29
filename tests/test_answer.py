import json,os,pathlib,subprocess,tempfile,unittest
from unittest.mock import patch
from paper_rag.answer import answer

class AnswerTests(unittest.TestCase):
    def fixture(self,root):
        record=root/'record';record.mkdir()
        e={'evidence_id':'E1','paper_id':'P1','title':'Synthetic','heading':'Methods','pages':[1],'text':'A verified quote.','role_candidate':'UNRESOLVED','source_path':'synthetic','section_char_span':[0,17]}
        (record/'evidence.json').write_text(json.dumps({'question':'What method?','evidence':[e]}))
        return record,{'enable_codex_answer':True,'answer_model':'explicit-test-model','answer_effort':'medium','codex_cli':'mock-codex','library_root':str(root)}
    def test_paid_auth_rejected_before_generation(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{},clear=True):
            r,c=self.fixture(pathlib.Path(td))
            with patch('paper_rag.answer.subprocess.run',return_value=subprocess.CompletedProcess([],0,'API key login','')) as run:
                with self.assertRaises(ValueError):answer(r,c)
                self.assertEqual(run.call_count,1)
                self.assertFalse((r/'attempt.json').exists())
    def test_measured_usage_and_no_retry_with_mock_model(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{},clear=True):
            r,c=self.fixture(pathlib.Path(td))
            def fake(cmd,**kwargs):
                if cmd[1:]==['login','status']:return subprocess.CompletedProcess(cmd,0,'Logged in using ChatGPT','')
                (r/'answer.json').write_text(json.dumps({'direct_answer':'Evidence states a quote.','statements':[{'text':'Evidence states a quote.','ownership_status':'UNRESOLVED','evidence_ids':['E1'],'exact_quote':'A verified quote.'}],'assumptions_and_conditions':[],'limitations':['Synthetic fixture']}))
                return subprocess.CompletedProcess(cmd,0,json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':40,'output_tokens':12}}),'')
            with patch('paper_rag.answer.subprocess.run',side_effect=fake):
                result=answer(r,c)
                self.assertEqual(result['usage']['total_tokens'],112)
                self.assertEqual(result['usage']['usage']['cached_input_tokens'],40)
                self.assertEqual(result['status'],'COMPLETED_UNCERTIFIED')
                with self.assertRaises(ValueError):answer(r,c)
