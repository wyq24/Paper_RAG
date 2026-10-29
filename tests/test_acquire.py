import tempfile,unittest,pathlib,json
from paper_rag.acquire import Acquisition
from paper_rag.config import initialize_config
from paper_rag.library import Library
class AcquisitionTests(unittest.TestCase):
    def test_wrong_pdf_not_ingested(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);cfg=root/'config.json';initialize_config(cfg,root/'library');lib=Library(cfg)
            pdf=pymupdf.open();p=pdf.new_page();p.insert_text((50,50),'A completely different paper.');raw=pdf.tobytes();pdf.close()
            fetch=Acquisition(root/'attempt');fetch.get=lambda u:(raw,{'status':200})
            r=fetch.run({'title':'The requested scientific paper','doi':'10.1234/one','pdf_urls':['https://example.invalid/paper.pdf']},lib)
            self.assertEqual(r['status'],'PDF_NOT_OBTAINED_OR_IDENTITY_UNRESOLVED');self.assertEqual(lib.status()['papers'],0);lib.db.close()
    def test_init_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'config.json';initialize_config(p,pathlib.Path(d)/'a');before=p.read_bytes()
            with self.assertRaises(ValueError):initialize_config(p,pathlib.Path(d)/'b')
            self.assertEqual(p.read_bytes(),before)
if __name__=='__main__':unittest.main()
