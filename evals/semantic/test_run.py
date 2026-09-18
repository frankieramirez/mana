"""Offline tests; no credentials or live API calls."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.questions = run.load_inputs(run.HERE / 'cases.jsonl', run.HERE / 'questions.json')

    def response(self, probability=0.1):
        return {'model': 'jev-1.13', 'answers': {k: {'type': 'noul', 'noul': probability} for k in self.questions},
                'usage': {'input_tokens': 123, 'output_tokens': 4}}

    def test_labels_never_sent(self):
        body = run.payload(self.cases[0], self.questions, 'jev-1.13')
        self.assertEqual(set(body['state']), {'source', 'output'})
        self.assertNotIn('expected', json.dumps(body))
        self.assertNotIn('label_note', json.dumps(body))

    def test_uncertainty_and_false_passes(self):
        self.assertEqual([run.verdict(p, .2, .8) for p in (.2, .5, .8)], ['pass', 'uncertain', 'fail'])
        case = {'expected': {'unsupported_claim': True, 'meaning_lost': False}}
        results = run.evaluate(case, self.response(), .2, .8)
        self.assertEqual(results['unsupported_claim']['comparison'], 'false-pass')
        self.assertEqual(results['meaning_lost']['comparison'], 'agree')
        results = run.evaluate(case, self.response(.9), .2, .8)
        self.assertEqual(results['meaning_lost']['comparison'], 'false-fail')
        self.assertEqual(run.evaluate({}, self.response(), .2, .8)['meaning_lost']['comparison'], 'unlabeled')

    def test_bad_responses_rejected(self):
        for value in (True, -0.1, 1.1, float('nan'), '0.9', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run.validate_response(self.response(value), self.questions)
        response = self.response()
        del response['answers']['meaning_lost']
        with self.assertRaises(ValueError):
            run.validate_response(response, self.questions)

    def test_invalid_cases_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cases.jsonl'
            for cases in ([self.cases[0], self.cases[0]], [dict(self.cases[0], expected={'unknown': True})], []):
                path.write_text(''.join(json.dumps(c) + '\n' for c in cases))
                with self.assertRaises(ValueError):
                    run.load_inputs(path, run.HERE / 'questions.json')

    def test_check_needs_no_key_or_network(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(run, 'ask') as ask, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run.main(['--check']), 0)
            ask.assert_not_called()

    def test_partial_failure_preserves_completed_results(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'TYPESAFE_API_KEY': 'secret-test-key'}), \
             patch.object(run, 'ask', side_effect=[self.response(), ValueError('Jev HTTP 429')]), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            out = Path(tmp) / 'report'
            self.assertEqual(run.main(['--model', 'jev-1.13', '--limit', '2', '--out', str(out)]), 2)
            report = json.loads((out / 'report.json').read_text())
            self.assertEqual(report['status'], 'incomplete')
            self.assertEqual(len(report['runs']), 1)
            self.assertNotIn('secret-test-key', (out / 'report.json').read_text())

    def test_complete_advisory_run_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test'}), \
             patch.object(run, 'ask', return_value=self.response(.9)), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            out = Path(tmp) / 'report'
            args = ['--model', 'jev-1.13', '--limit', '1', '--out', str(out)]
            self.assertEqual(run.main(args), 0)  # Bad output is advisory, not a CI failure.
            self.assertIn('false-fail', (out / 'report.md').read_text())
            self.assertEqual(json.loads((out / 'report.json').read_text())['status'], 'complete')
            self.assertEqual(run.main(args), 2)

    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run.main(['--model', 'jev-1.13']), 2)
            self.assertEqual(run.main(['--model', 'jev-latest']), 2)

    def test_default_alias_sent_and_returned_model_recorded(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test'}), \
             patch.object(run, 'ask', return_value=self.response()) as ask, \
             contextlib.redirect_stdout(io.StringIO()):
            out = Path(tmp) / 'report'
            self.assertEqual(run.main(['--limit', '1', '--out', str(out)]), 0)
            self.assertEqual(ask.call_args.args[0]['model'], 'jev-latest')
            report = json.loads((out / 'report.json').read_text())
            self.assertEqual(report['model'], 'jev-latest')
            self.assertEqual(report['runs'][0]['response']['model'], 'jev-1.13')

    def test_http_error_preserves_diagnostic_and_redacts_key(self):
        error = run.urllib.error.HTTPError(run.ENDPOINT, 400, 'Bad Request', {},
            io.BytesIO(b'{"detail":"Unknown model jev-1.13", "authorization":"Bearer secret-test-key"}'))
        with patch.object(run.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(ValueError) as raised:
                run.ask(run.payload(self.cases[0], self.questions, 'jev-1.13'), 'secret-test-key')
        message = str(raised.exception)
        self.assertIn('Jev HTTP 400', message)
        self.assertIn('Unknown model jev-1.13', message)
        self.assertNotIn('secret-test-key', message)

    def test_empty_http_error_body(self):
        error = run.urllib.error.HTTPError(run.ENDPOINT, 400, 'Bad Request', {}, io.BytesIO(b''))
        with error:
            self.assertEqual(run.http_error_detail(error, 'test'), 'empty response body')


if __name__ == '__main__':
    unittest.main()
