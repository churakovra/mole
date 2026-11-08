from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.html import render
from molekit.layout import layout
from molekit.model import empty_model
from test_html import BROWSER, browser_test


def dense_model():
    model = empty_model("dense-revision")
    model["sources"] = [{"id":"s1","path":"fixture.py","revision":model["revision"],"lineStart":1,"lineEnd":1,"kind":"source_code"}]
    model["evidence"] = [{"id":"ev1","sourceId":"s1","observation":"Synthetic layout fixture", "extractor":"fixture", "excerptHash":"fixture", "classification":"source_code"}]
    for index in range(40):
        model["operations"].append({"id": "op-" + str(index), "title": "Long workflow label " + str(index) + " W" * 45,
                                     "kind": "candidate", "evidenceIds": ["ev1"]})
    model["relationships"] = [{"id": "edge-" + str(index), "source": "op-" + str(index),
                               "target": "op-" + str((index + 1) % 40), "kind": "possible call", "resolution": "possible",
                               "condition": "unproven", "evidenceIds": ["ev1"]} for index in range(40)]
    model["diagramViews"] = [{"id": "view-dense", "title": "Dense workflow", "scenarioIds": [],
        "nodes": [{"id": o["id"], "label": o["title"]} for o in model["operations"]],
        "edgeIds": [e["id"] for e in model["relationships"]], "childRefs": []}]
    return model


class LayoutTests(unittest.TestCase):
    def test_determinism_and_nonoverlapping_node_rectangles(self):
        model = dense_model()
        first = layout(model, model["diagramViews"][0])
        self.assertEqual(first, layout(model, model["diagramViews"][0]))
        nodes = list(first["nodes"].values())
        for i, a in enumerate(nodes):
            self.assertLessEqual(a["x"] + a["width"], first["width"])
            self.assertLessEqual(a["y"] + a["height"], first["height"])
            for b in nodes[i + 1:]:
                self.assertTrue(a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                                or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"])

    @unittest.skipUnless(Path(BROWSER).is_file(), "Chrome unavailable")
    def test_viewport_matrix_zoom_labels_and_local_overflow(self):
        for width in (390, 600, 768, 1280, 1920):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp:
                result = browser_test(render(dense_model()), '''
check(document.documentElement.scrollWidth<=innerWidth,'page horizontal overflow');
check(document.body.scrollWidth<=innerWidth,'body horizontal overflow');
check(document.querySelector('#zoom-label').textContent==='100%','fit baseline');
for (const node of document.querySelectorAll('.node')) {
  const rect=node.querySelector('rect').getBBox();
  for(const span of node.querySelectorAll('tspan')) {
    const box=span.getBBox();
    check(box.x>=rect.x && box.x+box.width<=rect.x+rect.width+1,'label horizontal clipping');
    check(box.y>=rect.y && box.y+box.height<=rect.y+rect.height+1,'label vertical clipping');
  }
}
document.querySelector('.node').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
check(document.querySelector('#details').textContent.includes('ID:'),'keyboard selection');
for(let i=0;i<10;i++) document.querySelector('#zoom-in').click();
const viewport=document.querySelector('#viewport');
check(viewport.scrollWidth>viewport.clientWidth || viewport.scrollHeight>viewport.clientHeight,'local overflow absent');
check(document.documentElement.scrollWidth<=innerWidth,'zoom expanded page');
const before=document.querySelector('#zoom-label').textContent;
viewport.dispatchEvent(new WheelEvent('wheel',{deltaY:100,bubbles:true}));
check(document.querySelector('#zoom-label').textContent===before,'wheel changed zoom');
document.querySelector('#fit').click();
check(document.querySelector('#zoom-label').textContent==='100%','fit reset');
check(document.querySelector('#fit').hidden,'fit button visibility');
''', tmp, width)
                self.assertTrue(result["ok"], result)
