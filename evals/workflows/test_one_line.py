"""Offline one-line control payload checks; never invoke a model."""
import json
from pathlib import Path
import tempfile
import unittest

import conditions
import one_line
import run

SKILLS = run.ROOT / 'skills'


class OneLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_every_skill_keeps_frontmatter_and_gets_one_sentence(self):
        out = self.base / 'control'
        record = one_line.build(SKILLS, out)
        self.assertEqual(set(record), {p.parent.name for p in SKILLS.glob('*/SKILL.md')})
        for name, sentence in record.items():
            full = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
            head, frontmatter = one_line.split_frontmatter(full)
            text = (out / name / 'SKILL.md').read_text(encoding='utf-8')
            self.assertEqual(text, head + '\n' + sentence + '\n')
            self.assertTrue(one_line.description(frontmatter).startswith(sentence))
            self.assertEqual(sentence.count('. '), 0, name)
            self.assertEqual([p.name for p in (out / name).iterdir()], ['SKILL.md'])

    def test_payload_installs_through_the_legacy_skill_root(self):
        out = self.base / 'control'
        case = next(c for c in json.loads((run.ROOT / 'evals/workflows/cases.json').read_text())['cases']
                    if c['id'] == 'review-report-only')
        one_line.build(SKILLS, out, [case['skill']])
        work = self.base / 'run'
        work.mkdir()
        run.prepare(case, work, out)
        installed = work / 'workspace/installed' / case['skill'] / 'SKILL.md'
        self.assertEqual(installed.read_text(encoding='utf-8'),
                         (out / case['skill'] / 'SKILL.md').read_text(encoding='utf-8'))

    def test_payload_has_a_stable_inventory(self):
        first, second = self.base / 'a', self.base / 'b'
        one_line.build(SKILLS, first)
        one_line.build(SKILLS, second)
        self.assertEqual(conditions.inventory(first), conditions.inventory(second))

    def test_quoted_description_is_decoded(self):
        text = '---\nname: x\ndescription: "Say \\"hi\\" twice. Use when greeting."\n---\n\nLong body.\n'
        body, sentence = one_line.one_line(text)
        self.assertEqual(sentence, 'Say "hi" twice.')
        self.assertTrue(body.endswith('---\n\nSay "hi" twice.\n'))
        self.assertNotIn('Long body', body)

    def test_refuses_production_and_existing_destinations(self):
        for target in (SKILLS / 'one-line', run.ROOT / 'agents', run.ROOT / 'output-styles/x'):
            with self.assertRaisesRegex(ValueError, 'cannot be written under'):
                one_line.build(SKILLS, target)
        existing = self.base / 'existing'
        existing.mkdir()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            one_line.build(SKILLS, existing)

    def test_unknown_skill_and_bad_frontmatter_fail(self):
        with self.assertRaisesRegex(ValueError, 'no such skill'):
            one_line.build(SKILLS, self.base / 'x', ['no-such-skill'])
        with self.assertRaisesRegex(ValueError, 'no frontmatter'):
            one_line.one_line('Body only.\n')
        with self.assertRaisesRegex(ValueError, 'single-line'):
            one_line.one_line('---\nname: x\ndescription: >\n  folded\n---\n')
        with self.assertRaisesRegex(ValueError, 'no description'):
            one_line.one_line('---\nname: x\n---\n')


if __name__ == '__main__':
    unittest.main()
