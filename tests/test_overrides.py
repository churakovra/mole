from pathlib import Path
import tempfile
import unittest

from test_layout import dense_model
from test_html import BROWSER, browser_test
from molekit.html import render


@unittest.skipUnless(Path(BROWSER).is_file(), "Chrome unavailable")
class OverrideTests(unittest.TestCase):
    def test_view_label_and_entity_title_share_consistent_base(self):
        model = dense_model()
        model["diagramViews"][0]["nodes"][0]["label"] = "Short view label"
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(model), '''
const node=document.querySelector('.node');
node.dispatchEvent(new MouseEvent('click',{bubbles:true}));
node.querySelector('text').dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
document.querySelector('#mole-edit-value').value='My label';
document.querySelector('#mole-save').click();
check(!document.querySelector('#warning').textContent.includes('conflict'),'fresh edit falsely conflicted');
check(document.querySelector('#details h2').textContent==='My label','detail label not synchronized');
''', tmp)
            self.assertTrue(result["ok"], result)

    def test_oversized_save_preserves_previous_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            prelude = '''const records=Array.from({length:198},(_,i)=>({targetId:'old-'+i,fieldPath:'notes',baseFieldHash:'h',value:'x'.repeat(10000)}));localStorage.setItem('mole:local-explorer:v1',JSON.stringify({schemaVersion:1,artifactId:'local-explorer',fields:records}));window.beforeEdits=localStorage.getItem('mole:local-explorer:v1');'''
            result = browser_test(render(dense_model()), '''
document.querySelector('.node').dispatchEvent(new KeyboardEvent('keydown',{key:'F2',bubbles:true}));
document.querySelector('#mole-edit-value').value='y'.repeat(10000);
document.querySelector('#mole-save').click();
const after=localStorage.getItem('mole:local-explorer:v1');
check(after.length<=2000000,'saved unreadable data');
check(document.querySelector('#warning').textContent.includes('memory only'),'oversized save falsely reported success');
check(after===window.beforeEdits,'overwrote prior persisted data');
''', tmp, prelude=prelude)
            self.assertTrue(result["ok"], result)

    def test_edit_reload_and_no_text_drill(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(dense_model()), '''
if (!localStorage.getItem('test-reloaded')) {
 const label=document.querySelector('.node text');
 const oldTitle=document.querySelector('#title').textContent;
 label.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
 check(document.querySelector('#mole-editor').open,'editor missing');
 check(document.querySelector('#title').textContent===oldTitle,'text drilled');
 document.querySelector('#mole-edit-value').value='My authored label <script>alert(1)</script>';
 document.querySelector('#mole-save').click();
 check(document.querySelector('.node').textContent.includes('My authored label'),'edit missing');
 const stored=JSON.parse(localStorage.getItem('mole:local-explorer:v1'));
 check(stored.fields.length===1 && !stored.symbols,'storage is not field-level');
 localStorage.setItem('test-reloaded','yes');
 location.reload(); await new Promise(()=>{});
}
check(document.querySelector('.node').textContent.includes('My authored label'),'reload lost edit');
check(!document.querySelector('#diagram script'),'active injection');
''', tmp)
            self.assertTrue(result["ok"], result)

    def test_conflict_retains_edit_and_malformed_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            prelude = '''localStorage.setItem('mole:local-explorer:v1',JSON.stringify({schemaVersion:1,artifactId:'local-explorer',fields:[{targetId:'op-0',fieldPath:'label',baseFieldHash:'changed-base',value:'Retained authored label'}]}));'''
            result = browser_test(render(dense_model()), '''
check(document.querySelector('.node').textContent.includes('Retained authored label'),'conflict lost edit');
check(document.querySelector('#warning').textContent.includes('Conflicting'),'conflict invisible');
''', tmp, prelude=prelude)
            self.assertTrue(result["ok"], result)
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(dense_model()), '''
check(document.querySelectorAll('.node').length===40,'malformed storage broke viewer');
check(document.querySelector('#warning').textContent.includes('malformed'),'missing storage error');
''', tmp, prelude="localStorage.setItem('mole:local-explorer:v1','{invalid');")
            self.assertTrue(result["ok"], result)

    def test_blocked_storage_does_not_claim_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(dense_model()), '''
document.querySelector('.node').dispatchEvent(new KeyboardEvent('keydown',{key:'F2',bubbles:true}));
document.querySelector('#mole-edit-value').value='Session only';
document.querySelector('#mole-save').click();
check(document.querySelector('#warning').textContent.includes('in memory only'),'false save claim');
check(document.querySelector('.node').textContent.includes('Session only'),'session edit missing');
''', tmp, prelude="Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked');}});")
            self.assertTrue(result["ok"], result)
