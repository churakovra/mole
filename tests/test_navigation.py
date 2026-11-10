from pathlib import Path
import tempfile
import unittest

from test_html import BROWSER, browser_test
from test_layout import dense_model
from molekit.html import render
from molekit.scanner import scan
from molekit.adapters import enrich
from molekit.knowledge import compose


@unittest.skipUnless(Path(BROWSER).is_file(), "Chrome unavailable")
class NavigationTests(unittest.TestCase):
    def test_compiled_dense_cycles_have_bounded_navigation_and_working_view_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            source = 'from fastapi import FastAPI\napp=FastAPI()\n'
            for i in range(8):
                source += ('@app.get("/")\n' if i == 0 else '') + 'def f' + str(i) + '():\n'
                source += ''.join('    f' + str(j) + '()\n' for j in range(8) if j != i)
            (repo / 'app.py').write_text(source)
            workspace = Path(tmp) / 'workspace'
            workspace.mkdir()
            model = compose(enrich(scan(repo, workspace)))
            target = model['diagramViews'][0]['childRefs'][0]
            title = next(view['title'] for view in model['diagramViews'] if view['id'] == target)
            import json
            result = browser_test(render(model), '''
check(document.querySelectorAll('#tree button').length<=600,'factorial navigation expansion');
check(document.querySelector('#title').textContent===''' + json.dumps(title) + ''','view fragment ignored');
''', tmp, prelude='history.replaceState(null,"","#view=' + target + '");')
            self.assertTrue(result['ok'], result)
    def test_shared_child_back_follows_actual_parent_and_loops_stop(self):
        model = dense_model()
        model["relationships"] = []
        model["scenarios"] = [{"id": "s" + str(index), "operationIds": ["op-" + str(index)]} for index in range(3)]
        def view(identity, title, nodes, children, scenarios):
            return {"id": identity, "title": title, "nodes": [{"id": "op-" + str(n), "label": "Process " + str(n)} for n in nodes],
                    "edgeIds": [], "childRefs": children, "scenarioIds": scenarios}
        model["diagramViews"] = [view("root", "Root", [0, 1], ["a", "b"], []),
            view("a", "Parent A", [2], ["shared"], ["s0"]), view("b", "Parent B", [2], ["shared"], ["s1"]),
            view("shared", "Shared child", [0], ["a"], ["s2"])]
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(model), '''
const dbl=id=>document.querySelector('.node[data-id="'+id+'"]').dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
dbl('op-0'); dbl('op-2');
check(document.querySelector('#title').textContent==='Shared child','shared drill');
dbl('op-0'); check(document.querySelector('#title').textContent==='Shared child','navigation cycle');
document.querySelector('#back').click();
check(document.querySelector('#title').textContent==='Parent A','wrong A ancestor');
document.querySelector('#back').click(); dbl('op-1'); dbl('op-2'); document.querySelector('#back').click();
check(document.querySelector('#title').textContent==='Parent B','shared child lost B route');
''', tmp)
            self.assertTrue(result["ok"], result)

    def test_trusted_mouse_pan_and_pointer_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(dense_model()), '''
for(let i=0;i<20;i++) document.querySelector('#zoom-in').click();
const viewport=document.querySelector('#viewport'), rect=viewport.getBoundingClientRect();
const x=rect.left+10,y=rect.top+20;
check(!document.elementFromPoint(x,y).closest('.node,.edge'),'not background');
window.__moleActions=[{type:'mousePressed',x,y,button:'left',buttons:1,clickCount:1},
 {type:'mouseMoved',x:x-100,y:y-70,button:'left',buttons:1},
 {type:'mouseReleased',x:x-100,y:y-70,button:'left',buttons:0,clickCount:1}];
await new Promise(resolve=>{const timer=setInterval(()=>{if(window.__moleActionsDone){clearInterval(timer);resolve();}},10);});
check(viewport.scrollLeft>=80 && viewport.scrollTop>=50,'mouse drag did not pan');
check(!viewport.classList.contains('dragging'),'pointer capture did not release');
''', tmp)
            self.assertTrue(result["ok"], result)

    def test_trusted_touch_scroll_and_visible_edit_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(dense_model()), '''
for(let i=0;i<16;i++) document.querySelector('#zoom-in').click();
const viewport=document.querySelector('#viewport'),rect=viewport.getBoundingClientRect();
const x=rect.left+90,y=rect.top+200;
window.__moleActions=[
 {method:'Input.dispatchTouchEvent',params:{type:'touchStart',touchPoints:[{x,y}]}},
 {method:'Input.dispatchTouchEvent',params:{type:'touchMove',touchPoints:[{x:x-25,y:y-25}]}},
 {method:'Input.dispatchTouchEvent',params:{type:'touchMove',touchPoints:[{x:x-50,y:y-55}]}},
 {method:'Input.dispatchTouchEvent',params:{type:'touchMove',touchPoints:[{x:x-70,y:y-90}]}},
 {method:'Input.dispatchTouchEvent',params:{type:'touchEnd',touchPoints:[]}}];
await new Promise(resolve=>{const timer=setInterval(()=>{if(window.__moleActionsDone){clearInterval(timer);resolve();}},10);});
await new Promise(resolve=>setTimeout(resolve,100));
check(viewport.scrollTop>30 || viewport.scrollLeft>30,'touch did not pan locally');
check(document.documentElement.scrollWidth<=innerWidth,'touch layout expanded page');
document.querySelector('.node').dispatchEvent(new MouseEvent('click',{bubbles:true}));
const button=[...document.querySelectorAll('#details button')].find(button=>button.textContent==='Edit label');
check(button,'visible touch edit control absent');button.click();
check(document.querySelector('#mole-editor').open,'touch edit control failed');
''', tmp,390)
            self.assertTrue(result['ok'], result)
