from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
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
        raise AssertionError(f"Browser did not complete test (exit {result.returncode}): " +
                             result.stderr[-1200:] + " stdout: " + result.stdout[-400:])
    return json.loads(parser.result)


class BrowserHarnessTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix" and shutil.which("node"), "Node and a POSIX shell are required for the harness test")
    def test_startup_failure_retries_once_and_cleans_unique_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); browser=root/"fake-browser"; log=root/"starts.log"
            browser.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$MOLE_FAKE_BROWSER_LOG"\nexit 23\n',encoding="utf-8")
            browser.chmod(0o755)
            page=root/"page.html";page.write_text("<html><body></body></html>",encoding="utf-8")
            env={**os.environ,"MOLE_FAKE_BROWSER_LOG":str(log)}
            result=subprocess.run(["node",str(Path(__file__).with_name("browser_runner.js")),str(browser),
                str(root),str(page),"1280",""],capture_output=True,text=True,timeout=10,env=env)
            self.assertEqual(result.returncode,1)
            self.assertEqual(result.stderr.count("Chrome startup failed; retrying once"),1)
            self.assertIn("code 23",result.stderr)
            profiles=re.findall(r"--user-data-dir=([^ ]+)",log.read_text(encoding="utf-8"))
            self.assertEqual(len(profiles),2)
            self.assertEqual(len(set(profiles)),2)
            self.assertTrue(all(not Path(profile).exists() for profile in profiles))


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

    @unittest.skipUnless(Path(BROWSER).is_file(), 'Chrome unavailable')
    def test_operation_details_link_workflow_document_and_source(self):
        from test_layout import dense_model
        model = dense_model()
        model['scenarios'] = [{'id':'semantic-test','title':'Example workflow','operationIds':['op-0']}]
        with tempfile.TemporaryDirectory() as tmp:
            result = browser_test(render(model,source_prefix='../../source repo'), '''
document.querySelector('.node[data-id="op-0"]').dispatchEvent(new MouseEvent('click',{bubbles:true}));
const links=[...document.querySelectorAll('#details a')];
check(links.some(link=>link.getAttribute('href')==='processes/semantic-test.md'),'workflow MD link absent');
check(links.some(link=>link.getAttribute('href')==='../../source%20repo/fixture.py'),'source link absent or unescaped');
''',tmp)
            self.assertTrue(result['ok'],result)
