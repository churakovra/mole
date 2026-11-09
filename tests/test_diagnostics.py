import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.cli import main
from molekit.pipeline import start


class DiagnosticTests(unittest.TestCase):
    def test_internal_error_has_private_redacted_trace_and_is_not_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, workspace = Path(tmp) / 'repo', Path(tmp) / 'workspace'
            repo.mkdir()
            start(repo, workspace, 'standard', 'repository')
            stream = io.StringIO()
            with patch('molekit.cli.pipeline.operate', side_effect=RuntimeError('secret raw source content')):
                with contextlib.redirect_stdout(stream):
                    code = main(['status', '--workspace', str(workspace), '--json'])
            result = json.loads(stream.getvalue())
            self.assertEqual(code, 10)
            self.assertFalse(result['error']['recoverable'])
            diagnostic = workspace / '.diagnostics' / (result['error']['diagnosticId'] + '.json')
            self.assertTrue(diagnostic.is_file())
            self.assertNotIn('secret', diagnostic.read_text() + stream.getvalue())
            self.assertNotIn(str(repo), diagnostic.read_text())

    def test_bad_request_remains_correctable(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(['invalid']), 2)
        self.assertTrue(json.loads(stream.getvalue())['error']['recoverable'])
