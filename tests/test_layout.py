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
    @unittest.skipUnless(Path(BROWSER).is_file(), 'Chrome unavailable')
    def test_seven_process_overview_is_readable_without_zoom(self):
        model = dense_model()
        model['relationships'] = []
        model['operations'] = model['operations'][:7]
        view = model['diagramViews'][0]
        view['nodes'] = [{'id': op['id'], 'label': 'Business process ' + str(i)} for i, op in enumerate(model['operations'])]
        view['edgeIds'] = []
        geometry = layout(model, view)
        self.assertEqual(len({point['column'] for point in geometry['nodes'].values()}), 3)
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(model), '''
for(const node of document.querySelectorAll('.node')) {
  check(node.querySelector('rect').getBoundingClientRect().width>=180,'overview card shrank below readable size');
}
check(document.documentElement.scrollWidth<=innerWidth,'overview expanded page');
''', tmp)
            self.assertTrue(result['ok'], result)

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

    def test_topology_layers_and_routes_have_no_edge_count_blank_band_or_node_intersections(self):
        model = dense_model()
        view = model['diagramViews'][0]
        # Long forward path plus jump/back/self edges exercises the gutters.
        model['relationships'][-1]['target'] = 'op-39'
        for source, target in ((0, 20), (30, 5), (10, 10)):
            model['relationships'].append({'id': 'extra-' + str(source), 'source': 'op-' + str(source),
                'target': 'op-' + str(target), 'kind': 'possible', 'condition': '', 'resolution': 'possible', 'evidenceIds': ['ev1']})
        view['edgeIds'] = [edge['id'] for edge in model['relationships']]
        result = layout(model, view)
        self.assertEqual(min(point['y'] for point in result['nodes'].values()), 64)
        self.assertGreater(result['nodes']['op-39']['x'], result['nodes']['op-0']['x'])
        for route in result['edges'].values():
            for (x1, y1), (x2, y2) in zip(route['points'], route['points'][1:]):
                for point in result['nodes'].values():
                    left, top, right, bottom = point['x'], point['y'], point['x']+point['width'], point['y']+point['height']
                    crosses = ((x1 == x2 and left < x1 < right and max(min(y1,y2),top) < min(max(y1,y2),bottom))
                               or (y1 == y2 and top < y1 < bottom and max(min(x1,x2),left) < min(max(x1,x2),right)))
                    self.assertFalse(crosses, (route, point))

    @unittest.skipUnless(Path(BROWSER).is_file(), 'Chrome unavailable')
    def test_long_self_edge_condition_stays_inside_canvas_and_full_details_remain(self):
        model = dense_model()
        model['operations'] = model['operations'][:1]
        edge = model['relationships'][0]
        edge.update(target=edge['source'], condition='Very long conditional branch expression ' * 12)
        model['relationships'] = [edge]
        model['diagramViews'][0].update(nodes=model['diagramViews'][0]['nodes'][:1], edgeIds=[edge['id']])
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(model), '''
const svg=document.querySelector('#diagram'),label=svg.querySelector('.edge text'),box=label.getBBox();
check(box.x>=0 && box.x+box.width<=svg.viewBox.baseVal.width,'edge label clipped');
check(label.textContent.includes('…'),'long edge label not marked');
check(svg.querySelector('.edge title').textContent.includes('Very long conditional'),'full condition tooltip missing');
svg.querySelector('.edge').dispatchEvent(new MouseEvent('click',{bubbles:true}));
check(document.querySelector('#details').textContent.includes('Very long conditional'),'full condition details missing');
''',tmp)
            self.assertTrue(result['ok'],result)
