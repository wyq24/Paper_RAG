"""Real STDIO protocol, empty isolated library; no production service or network."""
import asyncio,json,os,pathlib,sys,tempfile,unittest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from paper_rag.config import initialize_config
from paper_rag.library import Library

class TransportTest(unittest.TestCase):
    def test_seven_tools_over_stdio(self):
        async def exercise(config):
            params=StdioServerParameters(command=sys.executable,args=['-m','paper_rag.server'],env={**os.environ,'PAPER_RAG_CONFIG':str(config)})
            async with stdio_client(params) as (r,w):
                async with ClientSession(r,w) as session:
                    await session.initialize()
                    names={t.name for t in (await session.list_tools()).tools}
                    self.assertEqual(names,{'list_papers','search','fetch','evidence_checklist','audit_answer','source_page','citation_network'})
                    result=await session.call_tool('list_papers',{})
                    self.assertFalse(result.isError)
                    result=await session.call_tool('evidence_checklist',{'question':'What labels were used?'})
                    self.assertFalse(result.isError)
                    result=await session.call_tool('citation_network',{'identifier':'W123'})
                    self.assertFalse(result.isError)
                    self.assertIn('NO_CITATION_SNAPSHOT',str(result))
        with tempfile.TemporaryDirectory() as td:
            config=pathlib.Path(td)/'config.json';initialize_config(config,pathlib.Path(td)/'library');Library(config).initialize()
            asyncio.run(exercise(config))
