"""Browser behavior on artifacts produced through v2 complete, not hand-written HTML."""
import json
from pathlib import Path
import tempfile
import unittest
from test_html import BROWSER,browser_test
from molekit.investigations import operate

@unittest.skipUnless(Path(BROWSER).is_file(),'Chrome unavailable')
class V2ExplorerTests(unittest.TestCase):
    def test_complete_process_navigation_branches_and_evidence_at_three_widths(self):
        from test_process_graph import GraphSubmissionTests
        fixture=GraphSubmissionTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.submit(fixture.patch)
        answer={'answerVersion':'1.0','requestId':'process-map','baseRevision':fixture.task['baseRevision'],
            'responseMarkdown':'Completion credits eligible rewards; purchase is independently callable.',
            'assertions':[{'text':fixture.claim['statement'],'claimIds':[fixture.claim['id']],
                'evidenceIds':fixture.claim['evidenceIds'],'category':'observation'}],
            'limitations':['Static evidence, no runtime verification.'],'selfReview':{'goalMatched':True,'readabilityChecked':True,'knownGaps':[]},'outcome':'ANSWERED'}
        path=fixture.root/'answer.json';path.write_text(json.dumps(answer))
        completed=operate('complete',fixture.workspace,answer=path,output=fixture.root/'output')
        document=(Path(completed['delivery']['output'])/'explorer.html').read_text()
        for width in (1280,390,320):
            with self.subTest(width=width),tempfile.TemporaryDirectory() as tmp:
                result=browser_test(document,'''
check(document.querySelector('.request-context').textContent==='Explain this service','original goal absent');
check(document.querySelectorAll('.node').length===3,'business overview missing');
check(document.querySelectorAll('.edge').length===1,'invented process sequence');
const edge=document.querySelector('.edge');edge.dispatchEvent(new MouseEvent('click',{bubbles:true}));
check(document.querySelector('#details').textContent.includes('Complete game'),'edge source missing');
check(document.querySelector('#details').textContent.includes('Credit wallet'),'edge target missing');
const process=document.querySelector('.node[data-id="process-complete"]');
process.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
check(document.querySelectorAll('.node').length===3,'branches missing');
check(document.querySelectorAll('.edge').length===2,'branch connectors missing');
const rejected=document.querySelector('.node[data-id="step-rejected"]');rejected.dispatchEvent(new MouseEvent('click',{bubbles:true}));
check(document.querySelector('#details').textContent.includes('Source-backed step-rejected'),'step explanation missing');
check(document.querySelector('#details').textContent.includes('app.py:'),'source locator missing');
check(document.querySelector('#open-details'),'technical drilldown missing');
document.querySelector('#open-details').click();document.querySelector('#back').click();
check(document.querySelector('#title').textContent==='Complete game','Back lost actual process');
document.querySelector('#fit').click();document.querySelector('#zoom-in').click();
check(document.documentElement.scrollWidth<=innerWidth+1,'horizontal page clipping');
''',tmp,width=width)
                self.assertTrue(result['ok'],result)
