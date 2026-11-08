from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.adapters import enrich
from molekit.html import render
from molekit.knowledge import compose
from molekit.scanner import scan

BROWSER = os.environ.get("MOLE_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class ResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.result = ""

    def handle_starttag(self, tag, attrs):
        if tag == "pre" and dict(attrs).get("id") == "test-results":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "pre":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.result += data


def browser_test(document, script, directory, width=1280, screenshot=None, prelude=""):
    path = Path(directory) / "explorer.html"
    script = script.replace("</script", "<\\/script")
    prelude = prelude.replace("</script", "<\\/script")
    harness = '''<script>setTimeout(async () => { let result; try {
const check = (condition, message) => {if (!condition) throw new Error(message);};
''' + 'check(innerWidth === ' + str(width) + ', \"incorrect viewport width\");' + script + '''
result = {ok:true}; } catch(error) {result={ok:false,error:String(error)};}
const output=document.createElement('pre'); output.id='test-results';
output.textContent=JSON.stringify(result); document.body.append(output);
},100);</script>'''
    document = document.replace('<script id="mole-model"', "<script>" + prelude + "</script><script id=\"mole-model\"", 1)
    path.write_text(document.replace("</body>", harness + "</body>"), encoding="utf-8")
    command = ["node", str(Path(__file__).with_name("browser_runner.js")), BROWSER,
               str(directory), str(path), str(width), str(screenshot) if screenshot else ""]
    result = subprocess.run(command, capture_output=True, text=True, timeout=25)
    parser = ResultParser()
    parser.feed(result.stdout)
    if result.returncode != 0 or not parser.result:
        raise AssertionError("Browser did not complete test: " + result.stderr[-1200:])
    return json.loads(parser.result)


class HtmlTests(unittest.TestCase):
    def test_self_contained_script_safe_payload(self):
        model = {"diagramViews": [], "danger": "</script><script>alert(1)</script>"}
        document = render(model)
        self.assertNotIn(model["danger"], document)
        self.assertIn("connect-src 'none'", document)
        self.assertNotIn('<script src=', document)
        self.assertNotIn('<link ', document)

    @unittest.skipUnless(Path(BROWSER).is_file(), "Chrome unavailable; set MOLE_BROWSER_EXECUTABLE")
    def test_three_models_same_renderer_offline(self):
        for fixture in ("fastapi-db-events", "django-transactions", "consumer-retry-idempotency"):
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp) / "workspace"
                workspace.mkdir()
                model = compose(enrich(scan(Path(__file__).parent / "fixtures" / fixture, workspace)))
                result = browser_test(render(model), '''
check(document.querySelectorAll('.node').length>0,'nodes missing');
const node=document.querySelector('.node');
node.dispatchEvent(new MouseEvent('click',{bubbles:true}));
check(document.querySelector('#details').textContent.includes('ID:'),'details missing');
const oldTitle=document.querySelector('#title').textContent;
node.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
check(document.querySelector('#title').textContent!==oldTitle,'drill failed');
document.querySelector('#back').click();
check(document.querySelector('#title').textContent===oldTitle,'back failed');
check(performance.getEntriesByType('resource').length===0,'external resources requested');
''', tmp)
                self.assertTrue(result["ok"], result)
