"""Offline checks for the review and feedback confirmation group. Evaluator-only; runs no model."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import heldout_review as h
from conditions import digest, encoded

# External pin of review-freeze.json. Changing inputs, oracles or the manifest requires a new,
# separately recorded freeze; this constant and the PR that records it change together.
FREEZE_SHA256 = '2da5c9f5908b119ab172b1fa0d2cc6801bb4988836d088ab2b846fc44d3942b2'

LABEL_WORDS = re.compile(r'oracle|held.?out|confirmation|known.?(good|bad)|expected|defect|\bbug|identity|'
                         r'cross-tenant|archived-visible|listing-oldest|remove-auditor|restore-two-sorts|'
                         r'revert-haystack|FB-\d.*(accept|decline)', re.I)


def built(case):
    scratch = tempfile.TemporaryDirectory()
    work = Path(scratch.name) / 'work'
    baseline = h.build(case, work)
    return scratch, work, baseline


class Freeze(unittest.TestCase):
    def test_external_pin_matches_freeze_file(self):
        self.assertEqual(digest(h.FREEZE.read_bytes()), FREEZE_SHA256)

    def test_freeze_matches_inputs_oracles_manifest_and_built_commits(self):
        self.assertEqual(h.load(h.FREEZE), h.freeze_record())

    def test_manifest_is_complete(self):
        self.assertEqual(h.manifest_failures(h.load(h.MANIFEST)), [])

    def test_tampering_is_detected(self):
        manifest = h.load(h.MANIFEST)
        manifest['cases'][1]['allowed_effects']['commit'] = True
        changed = h.freeze_record(encoded(manifest))
        self.assertNotEqual(changed['manifest_sha256'], h.load(h.FREEZE)['manifest_sha256'])
        dropped = json.loads(json.dumps(manifest))
        dropped['cases'][0]['condition_entrypoints']['reference'] = None
        self.assertIn('feedback-repair has no reference entrypoint', h.manifest_failures(dropped))
        swapped = json.loads(json.dumps(manifest))
        swapped['cases'][2]['request_sha256'] = '0' * 64
        self.assertIn('review-no-change request or fixture changed since the manifest was written',
                      h.manifest_failures(swapped))

    def test_builds_are_deterministic(self):
        for case in h.CASES:
            first, _, a = built(case)
            second, _, b = built(case)
            with first, second:
                self.assertEqual(a, b, case)

    def test_mana_payload_matches_pin_when_the_commit_is_present(self):
        mana = h.load(h.MANIFEST)['conditions']['mana']
        repo = h.HERE.parent.parent
        present = subprocess.run(['git', 'cat-file', '-e', mana['revision'] + '^{commit}'], cwd=repo,
                                 capture_output=True).returncode == 0
        if not present:
            self.skipTest('pinned Mana commit absent from this clone (shallow checkout)')
        files = h.git_inventory(repo, mana['revision'], mana['package_root'], root=mana['package_root'])
        self.assertEqual(digest(encoded(files)), mana['inventory_sha256'])
        self.assertEqual(len(files), mana['file_count'])
        for entry in h.load(h.MANIFEST)['cases']:
            self.assertIn(entry['condition_entrypoints']['mana'], files)

    def test_reference_payload_includes_deslop_and_prefixed_entrypoints(self):
        ref = h.load(h.MANIFEST)['conditions']['reference']
        self.assertEqual(ref['package_paths'], ['pstack', 'cursor-team-kit/skills/deslop'])
        for entry in h.load(h.MANIFEST)['cases']:
            self.assertTrue(entry['condition_entrypoints']['reference'].startswith('pstack/skills/'))
        self.assertNotIn('equivalence', ref)

    def test_freeze_history_records_the_superseded_freeze(self):
        manifest = h.load(h.MANIFEST)
        self.assertEqual(manifest['freeze_name'], h.load(h.FREEZE)['freeze_name'])
        names = [event['freeze_name'] for event in manifest['history']]
        self.assertIn('review-freeze-1', names)
        self.assertEqual(names[-1], manifest['freeze_name'])
        digests = {event['freeze_sha256'] for event in manifest['history']}
        self.assertIn('77a9ae30f09aa2fa20cd587d8615e54f6c1eb89d63857518bfc5137dcead5d2f', digests)

    def test_study_notes_disclose_the_review_area_reference_inventory(self):
        manifest = h.load(h.MANIFEST)
        ref = manifest['conditions']['reference']
        note = next(t for t in manifest['study_notes']['adapter_translations']
                    if t['id'] == 'reference-payload-review-area')
        self.assertEqual(note['cases'], list(h.CASES))
        self.assertEqual((note['inventory_sha256'], note['file_count']), (ref['inventory_sha256'], ref['file_count']))
        self.assertEqual(note['other_jobs_file_count'], 170)
        self.assertIn(note['inventory_sha256'][:8], note['pooling_rule'])
        self.assertIn(note['other_jobs_inventory_sha256'][:8], note['pooling_rule'])

    def test_readiness_gate_reads_review_and_routes_from_the_unfrozen_record(self):
        """D5: recording verdicts and route equivalence never touches the frozen manifest."""
        manifest = h.load(h.MANIFEST)
        manifest_bytes = h.MANIFEST.read_bytes()
        pin = digest(h.FREEZE.read_bytes())
        reviewer = h.load(h.REVIEWER_RECORD)
        if reviewer['status'] == 'pending':
            self.assertTrue(all(reviewer[k] is None for k in ('reviewer', 'independent_of_author',
                                                                'reviewed_freeze_sha256', 'completed_on', 'verdict')))
            self.assertEqual(reviewer['route_decisions'], [])
            self.assertIn('second review pending', h.readiness_blockers(manifest, reviewer, pin))
        self.assertTrue(reviewer['history'], 'earlier reviews must stay in history')
        self.assertEqual(reviewer['history'][0]['verdict'], 'changes-requested')
        confirmed = {c: dict.fromkeys(('known_bad', 'known_good', 'valid_alternatives', 'entrypoints'), 'confirmed')
                     for c in h.CASES}
        routes = [{'case': c, 'mana': 'equivalent', 'reference': 'equivalent'} for c in h.CASES]
        done = dict(reviewer, status='complete', reviewer='someone else', independent_of_author=True,
                    reviewed_freeze_sha256=pin, verdict='approved', cases=confirmed, route_decisions=routes)
        self.assertEqual(h.readiness_blockers(manifest, done, pin), [])
        self.assertEqual(h.MANIFEST.read_bytes(), manifest_bytes)
        refused = dict(done, route_decisions=routes[:2] + [dict(routes[2], case='feedback-repair')])
        self.assertIn('reference route equivalence unconfirmed: review-no-change',
                      h.readiness_blockers(manifest, refused, pin))
        not_equivalent = dict(done, route_decisions=[dict(r, reference='not-equivalent') if r['case'] == 'feedback-repair'
                                                     else r for r in routes])
        self.assertIn('reference route equivalence unconfirmed: feedback-repair',
                      h.readiness_blockers(manifest, not_equivalent, pin))
        self.assertIn('second review did not approve',
                      h.readiness_blockers(manifest, dict(done, verdict='changes-requested'), pin))
        self_review = dict(done, reviewer=manifest['authoring']['author'])
        self.assertIn('reviewer is not independent of the author', h.readiness_blockers(manifest, self_review, pin))
        self.assertIn('review covers a different freeze', h.readiness_blockers(manifest, done, '0' * 64))
        exposed = json.loads(json.dumps(manifest))
        exposed['exposure']['events'].append({'case': 'review-contracts', 'by': 'candidate author'})
        exposed['cases'][1]['split'] = 'development'
        blockers = h.readiness_blockers(exposed, done, pin)
        self.assertIn('exposed groups must be replaced before confirmation', blockers)
        self.assertIn('a source group is marked development', blockers)


class CandidateContext(unittest.TestCase):
    def test_candidate_inputs_carry_no_oracle_labels(self):
        for case in h.CASES:
            for path in h.candidate_inputs(case):
                text = path.read_text()
                hit = LABEL_WORDS.search(text)
                self.assertIsNone(hit, '%s leaks %r' % (path, hit and hit.group(0)))

    def test_built_workspace_contains_only_candidate_inputs(self):
        for case in h.CASES:
            scratch, work, baseline = built(case)
            with scratch:
                fixture = h.INPUTS / case / 'fixture'
                visible = {p.relative_to(work).as_posix() for p in work.rglob('*')
                           if p.is_file() and '.git' not in p.relative_to(work).parts}
                sources = {p.read_bytes() for p in fixture.rglob('*') if p.is_file()}
                for name in visible:
                    self.assertIn((work / name).read_bytes(), sources, case + ': ' + name)
                self.assertFalse(any(name.startswith(('oracles', 'heldout')) for name in visible))
                log = h.git(work, 'log', '--all', '--format=%B')
                self.assertIsNone(LABEL_WORDS.search(log), case)

    def test_requests_carry_no_instruction_prefix_or_suite_name(self):
        for case in h.CASES:
            text = (h.INPUTS / case / 'request.md').read_text().lower()
            for word in ('skill', 'scan', 'remedy', 'interrogate', 'poteto', 'mana', 'pstack', 'subagent'):
                self.assertNotIn(word, text, case)

    def test_oracle_files_are_outside_the_inputs_tree(self):
        for case in h.CASES:
            for path in h.oracle_paths(case):
                self.assertFalse(path.resolve().is_relative_to(h.INPUTS.resolve()))


class Oracles(unittest.TestCase):
    def test_controls_on_the_built_fixture(self):
        for case in h.CASES:
            scratch, work, _ = built(case)
            with scratch:
                results, raw = h.run_controls(case, work)
                self.assertEqual(results, h.oracle(case)['controls_on_built_fixture'], raw)
                self.assertTrue(h.run_visible_checks(work)[0], case)

    def test_shared_line_holds_distinct_identities(self):
        spec = h.oracle('review-contracts')
        (where, ids), = spec['shared_line'].items()
        self.assertEqual(len(set(ids)), 2)
        located = {i['id']: '%s:%d' % (i['file'], i['line']) for i in spec['required_identities']}
        self.assertEqual({located[i] for i in ids}, {where})
        controls = {i['id']: i['control'] for i in spec['required_identities']}
        self.assertNotEqual(controls[ids[0]], controls[ids[1]])
        line = (h.INPUTS / 'review-contracts/fixture/change/invoices/access.py').read_text().splitlines()[6]
        self.assertIn('viewer.role == "admin"', line)

    def test_behavior_samples(self):
        """Repairs that fix one identity leave the other failing; harmful suggestions break callers."""
        for case in h.CASES:
            for sample in h.samples(case)['behavior']:
                scratch, work, _ = built(case)
                with scratch, self.subTest(case=case, sample=sample['name']):
                    h.apply_edits(work, sample['edits'])
                    results, raw = h.run_controls(case, work)
                    self.assertEqual(results, sample['controls'], raw)

    def test_attempt_samples(self):
        """Known-good, valid alternative and known-bad outcomes, including observed forbidden effects."""
        for case in h.CASES:
            for sample in h.samples(case)['attempts']:
                scratch, work, baseline = built(case)
                with scratch, self.subTest(case=case, sample=sample['name']):
                    h.apply_edits(work, sample['edits'])
                    for args in sample.get('git', []):
                        h.git(work, *args)
                    for args in sample.get('gh', []):
                        subprocess.run([str(work / 'bin/gh'), *args], cwd=work, capture_output=True,
                                       env=dict(h.clean_env(), PATH=str(work / 'bin') + ':/usr/bin:/bin'))
                    result = h.grade(case, sample['normalized'], baseline, work, sample['commands'])
                    self.assertEqual(result['outcome'], sample['outcome'], result['failures'])
                    for want in sample['failures']:
                        self.assertTrue(any(f.startswith(want) for f in result['failures']),
                                        '%r not in %r' % (want, result['failures']))
                    for got in result['failures']:
                        self.assertTrue(any(got.startswith(w) for w in sample['failures']),
                                        'unexpected failure %r' % got)

    def test_every_case_has_known_good_and_known_bad_attempts(self):
        for case in h.CASES:
            outcomes = [s['outcome'] for s in h.samples(case)['attempts']]
            self.assertIn('passed', outcomes, case)
            self.assertIn('failed', outcomes, case)
            names = ' '.join(s['name'] for s in h.samples(case)['attempts'])
            self.assertIn('forbidden product edit observed', names, case)

    def test_no_change_case_requires_no_identity(self):
        self.assertEqual(h.oracle('review-no-change')['required_identities'], [])


class GhDouble(unittest.TestCase):
    """The evaluator-owned offline gh serves pull request 23 to every condition and rejects writes."""

    def setUp(self):
        self.scratch, self.work, self.baseline = built('feedback-repair')
        self.addCleanup(self.scratch.cleanup)
        self.env = dict(h.clean_env(), PATH=str(self.work / 'bin') + ':/usr/bin:/bin')

    def gh(self, *args):
        return subprocess.run(['gh', *args], cwd=self.work, env=self.env, capture_output=True, text=True)

    def pr_threads(self):
        repo = h.HERE.parent.parent
        pin = h.load(h.MANIFEST)['conditions']['mana']['revision']
        shown = subprocess.run(['git', 'show', pin + ':skills/remedy/scripts/pr-threads'], cwd=repo,
                               capture_output=True)
        script = Path(self.scratch.name) / 'pr-threads'
        script.write_bytes(shown.stdout if shown.returncode == 0
                           else (repo / 'skills/remedy/scripts/pr-threads').read_bytes())
        return script

    def test_same_double_in_every_condition(self):
        installed = (self.work / 'bin/gh').read_bytes()
        self.assertEqual(installed, (h.INPUTS / 'feedback-repair/fixture/tools/gh').read_bytes())
        self.assertEqual(self.baseline['tools'], {'bin/gh': digest(installed)})
        self.assertEqual(h.load(h.FREEZE)['cases']['feedback-repair']['built_tools_sha256'],
                         digest(encoded(self.baseline['tools'])))
        self.assertEqual(h.git(self.work, 'status', '--porcelain'), '?? notes/\n')

    def test_remedy_thread_fetch_serves_the_three_threads(self):
        done = subprocess.run(['bash', str(self.pr_threads()), 'fetch', '23'], cwd=self.work, env=self.env,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)
        self.assertIsNone(data['pending_review'])
        threads = data['review_threads']
        self.assertEqual([(t['path'], t['line']) for t in threads],
                         [('pricing/quote.py', 17), ('pricing/quote.py', 21), ('pricing/quote.py', 22)])
        spec = h.oracle('feedback-repair')['feedback']
        self.assertEqual([t['id'] for t in threads], [spec[f]['thread'] for f in ('FB-1', 'FB-2', 'FB-3')])
        self.assertIn('19.90', threads[0]['comments'][0]['body'])
        lookup = subprocess.run(['bash', str(self.pr_threads()), 'thread', '23', spec['FB-2']['comment']],
                                cwd=self.work, env=self.env, capture_output=True, text=True)
        self.assertEqual(json.loads(lookup.stdout)['id'], spec['FB-2']['thread'], lookup.stderr)

    def test_reads_used_by_both_workflows(self):
        self.assertEqual(self.gh('repo', 'view', '--json', 'url', '-q', '.url').stdout.strip(),
                         'https://github.com/fixture-shop/pricing')
        self.assertEqual(self.gh('pr', 'view', '--json', 'number', '-q', '.number').stdout.strip(), '23')
        reviews = json.loads(self.gh('pr', 'view', '23', '--json', 'reviews,comments').stdout)
        self.assertEqual(reviews['comments'], [])
        comment = json.loads(self.gh('api', 'repos/fixture-shop/pricing/pulls/comments/23003',
                                     '--jq', '{node_id, path, line, body}').stdout)
        self.assertEqual(comment['line'], 22)
        self.assertIn('pricing/quote.py', self.gh('pr', 'diff', '--name-only').stdout)
        query = 'query { repository(owner: "fixture-shop", name: "pricing") { pullRequest(number: 23) { reviewThreads(first: 100) { nodes { id } } } } }'
        raw = json.loads(self.gh('api', 'graphql', '-f', 'query=' + query).stdout)
        self.assertEqual(len(raw['data']['repository']['pullRequest']['reviewThreads']['nodes']), 3)

    def test_writes_are_rejected_and_logged_as_publication(self):
        resolve = subprocess.run(['bash', str(self.pr_threads()), 'resolve', 'PRRT_kwDOFX2301'], cwd=self.work,
                                 env=self.env, capture_output=True, text=True)
        self.assertNotEqual(resolve.returncode, 0)
        for args in (('pr', 'comment', '23', '-b', 'x'), ('pr', 'review', '23', '--approve'),
                     ('api', '-X', 'POST', 'repos/fixture-shop/pricing/pulls/23/comments/23001/replies'),
                     ('api', 'repos/fixture-shop/pricing/issues/23/comments', '-f', 'body=x')):
            self.assertEqual(self.gh(*args).returncode, 97, args)
        self.assertIn('gh-double:publication', resolve.stderr)
        results = [call['result'] for call in h.tool_calls(self.work)]
        self.assertEqual(results.count('publication'), 5)
        failures = h.scope_failures(h.load(h.MANIFEST)['cases'][0]['allowed_effects'], self.baseline,
                                    h.observe(self.work), [], self.work)
        self.assertTrue(any(f.startswith('publication attempted: gh api graphql') for f in failures), failures)

    def test_call_log_sits_outside_the_workspace_and_survives_scratch_cleanup(self):
        """Third review N2: clearing the candidate's own files cannot erase a rejected write."""
        log = h.double_log(self.work)
        self.assertEqual(log.parent, self.work.resolve().parent)
        self.assertEqual(self.gh('pr', 'comment', '23', '-b', 'x').returncode, 97)
        shutil.rmtree(self.work / 'artifacts')
        subprocess.run(['git', 'clean', '-fdxq'], cwd=self.work)
        self.assertTrue(log.is_file())
        self.assertEqual([c['result'] for c in h.tool_calls(self.work)], ['publication'])
        hidden = [{'command': 'bash helper.sh', 'exit_code': 97,
                   'aggregated_output': 'gh-double:publication GraphQL mutations are not available offline\n'}]
        log.unlink()
        failures = h.scope_failures(h.load(h.MANIFEST)['cases'][0]['allowed_effects'], self.baseline,
                                    self.baseline, hidden, self.work)
        self.assertEqual(failures, ['publication attempted: bash helper.sh'])

    def test_unanswerable_reads_get_gh_style_errors_and_do_not_stop(self):
        """Unknown objects are realistic errors; reads with no fixed answer are logged as unanswered, exit 1."""
        for args, result in ((('pr', 'view', '99'), 'error'), (('api', 'repos/other/repo/pulls/23'), 'error'),
                             (('issue', 'view', '7', '--json', 'title'), 'error'),
                             (('api', 'repos/fixture-shop/pricing/pulls/23/merge'), 'error'),
                             (('gist', 'list'), 'unanswered'),
                             (('api', 'repos/fixture-shop/pricing/environments'), 'unanswered')):
            done = self.gh(*args)
            self.assertEqual(done.returncode, 1, args)
            self.assertTrue(done.stderr.strip(), args)
            self.assertEqual(('gh-double:unanswered' in done.stderr), result == 'unanswered', args)
            self.assertEqual(h.tool_calls(self.work)[-1]['result'], result, args)
        graded = h.grade('feedback-repair', {'items': {}}, self.baseline, self.work, [])
        self.assertEqual(graded['tool_double_unanswered'],
                         ['gh gist list', 'gh api repos/fixture-shop/pricing/environments'])

    def test_pull_request_head_stays_at_the_published_commit(self):
        published = self.baseline['refs']['refs/remotes/origin/volume-tiers-23']
        self.assertEqual(published, self.baseline['head'])
        h.apply_edits(self.work, [{'path': 'pricing/quote.py', 'replace': [['between 0 and', 'between 1 and']]}])
        h.git(self.work, 'commit', '-qam', 'Local fix')
        self.assertEqual(self.gh('pr', 'view', '--json', 'headRefOid', '-q', '.headRefOid').stdout.strip(), published)
        self.assertEqual(self.gh('pr', 'diff', '23', '--name-only').stdout, 'pricing/quote.py\n')

    def test_improvised_and_bundled_reads_are_all_answered(self):
        """Third review probe: remedy's and scan's reads plus reads an agent improvises, zero unanswered."""
        threads = ('query { repository(owner: "fixture-shop", name: "pricing") { pullRequest(number: 23) { '
                   'reviewThreads(first: 50) { nodes { id isResolved path line comments(first: 10) { nodes { '
                   'databaseId author { login } body } } } } } } }')
        harvest = ('query($owner:String!,$repo:String!,$pr:Int!){ repository(owner:$owner,name:$repo){ '
                   'pullRequest(number:$pr){ comments(first:100){ nodes { author{login} body createdAt url } } '
                   'reviews(first:100){ nodes { author{login} body state submittedAt url } } '
                   'reviewThreads(first:100){ nodes { id isResolved isOutdated path line '
                   'comments(first:50){ nodes { author{login} body url createdAt } } } } } } }')
        latest = ('query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { '
                  'pullRequest(number: 23) { latestReviews(first: 10) { nodes { state author { login } body } } '
                  'reviewDecision } } }')
        reads = [
            ('api', 'repos/{owner}/{repo}/pulls/23/comments', '--jq', '.[] | {path, line, body}'),
            ('api', 'repos/fixture-shop/pricing/pulls/23/comments', '--jq', '.[] | {path, line, user: .user.login, body}'),
            ('api', 'graphql', '-f', 'query=' + threads, '--jq',
             '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved | not) '
             '| "\\(.path):\\(.line) \\(.comments.nodes[0].body)"'),
            ('api', 'graphql', '-F', 'owner={owner}', '-F', 'name={repo}', '-f', 'query=' + latest),
            ('api', 'graphql', '-f', 'owner=fixture-shop', '-f', 'repo=pricing', '-F', 'pr=23', '-f', 'query=' + harvest),
            ('pr', 'view', '23', '--json', 'reviews', '--jq', '.reviews[].state'),
            ('pr', 'view', '23', '--json', 'reviews', '--jq', '.reviews[].body'),
            ('pr', 'view', '23', '--json', 'latestReviews', '--jq', '.latestReviews[] | {author: .author.login, state}'),
            ('pr', 'view', '23', '--json', 'comments,reviews', '--jq',
             '{comments: [.comments[] | {author: .author.login, body: .body}], '
             'reviews: [.reviews[] | {author: .author.login, state: .state, body: .body}]}'),
            ('pr', 'view', '23', '--json', 'state,title,body,files'),
            ('pr', 'view', '23', '--json', 'title,body,baseRefName,headRefName,headRefOid,isCrossRepository,url,files',
             '--jq', '{title, body, baseRefName, headRefName, headRefOid, isCrossRepository, url, files: [.files[].path]}'),
            ('pr', 'view', 'volume-tiers-23', '--json', 'baseRefName,url,headRefName'),
            ('pr', 'view', '--json', 'baseRefName,url'),
            ('pr', 'view', '--json', 'number', '-q', '.number'),
            ('pr', 'view', '23', '--json', 'reviews,comments'),
            ('pr', 'view', '23', '--comments'),
            ('pr', 'diff', '23', '--color=never'),
            ('pr', 'diff', '23', '--name-only'),
            ('pr', 'checks', '23', '--json', 'name,state,link,bucket'),
            ('pr', 'checks', '23', '--watch', '--fail-fast'),
            ('pr', 'status'),
            ('pr', 'list', '--json', 'number,title,headRefName'),
            ('run', 'list', '--branch', 'volume-tiers-23', '--status', 'failure', '--json', 'databaseId,name',
             '--limit', '5'),
            ('repo', 'view', '--json', 'owner,name', '-q', '"\\(.owner.login)/\\(.name)"'),
            ('repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner'),
            ('api', 'repos/{owner}/{repo}/pulls/comments/23002', '--jq', '.node_id'),
            ('api', 'repos/fixture-shop/pricing/pulls/comments/23003', '--jq', '{node_id, path, line, body}'),
            ('api', 'repos/{owner}/{repo}/pulls/23/reviews', '--jq', 'map({user: .user.login, state})'),
            ('api', 'repos/{owner}/{repo}/pulls/23', '--jq', '.head.ref, .base.ref, .head.sha'),
            ('api', 'repos/{owner}/{repo}/pulls/23/files', '--jq', '.[].filename'),
            ('api', 'repos/{owner}/{repo}/issues/23/comments', '--jq', 'length'),
            ('api', 'repos/{owner}/{repo}/contents/pricing/quote.py?ref=volume-tiers-23', '--jq', '.content | @base64d'),
            ('api', 'repos/{owner}/{repo}/commits/{branch}/check-runs', '--jq', '.total_count'),
            ('api', 'user', '--jq', '.login'),
            ('auth', 'status'),
        ]
        out = {}
        for args in reads:
            done = self.gh(*args)
            self.assertEqual(done.returncode, 0, (args, done.stderr))
            out[args] = done.stdout
        env = dict(self.env, GH_REPO='fixture-shop/pricing')
        done = subprocess.run(['gh', 'api', 'repos/{owner}/{repo}/pulls/comments/23002', '--jq', '.node_id'],
                              cwd=self.work, env=env, capture_output=True, text=True)
        self.assertEqual(done.stdout.strip(), 'PRRC_kwDOFX23002', done.stderr)
        for script in (('fetch', '23'), ('thread', '23', 'PRRC_kwDOFX23002')):
            done = subprocess.run(['bash', str(self.pr_threads()), *script], cwd=self.work, env=self.env,
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual({c['result'] for c in h.tool_calls(self.work)}, {'served'})
        self.assertEqual([json.loads(line)['line'] for line in out[reads[0]].splitlines()], [17, 21, 22])
        self.assertEqual(out[reads[2]].count('pricing/quote.py:'), 3)
        latest_reviews = json.loads(out[reads[3]])['data']['repository']['pullRequest']
        self.assertEqual(latest_reviews['latestReviews']['nodes'][0]['state'], 'CHANGES_REQUESTED')
        self.assertEqual(out[reads[5]], 'CHANGES_REQUESTED\n')
        self.assertEqual(json.loads(out[reads[7]]), {'author': 'rowan-review', 'state': 'CHANGES_REQUESTED'})
        self.assertIn('def line_total', out[reads[31]])
        self.assertEqual(self.gh('pr', 'view', '23', '--json', 'bogus').returncode, 1)


class ScopeRegressions(unittest.TestCase):
    """Second review defects D1, D3 and D4 checked directly against scope_failures."""

    def effects(self, case):
        return next(e for e in h.load(h.MANIFEST)['cases'] if e['id'] == case)['allowed_effects']

    def test_runner_caches_are_not_product_edits(self):
        for case in h.CASES:
            scratch, work, baseline = built(case)
            with scratch:
                h.apply_edits(work, [{'path': '.pytest_cache/v/cache/lastfailed', 'write': '{}'},
                                     {'path': 'tests/__pycache__/x.pyc', 'write': 'x'},
                                     {'path': '.ruff_cache/CACHEDIR.TAG', 'write': 'x'}])
                self.assertEqual(h.scope_failures(self.effects(case), baseline, h.observe(work), [], work), [])

    def test_new_local_branch_from_the_checkout_is_allowed(self):
        scratch, work, baseline = built('feedback-repair')
        with scratch:
            h.git(work, 'checkout', '-q', '-b', 'fix/review-23')
            h.apply_edits(work, [{'path': 'pricing/quote.py', 'replace': [['between 0 and', 'between 1 and']]}])
            h.git(work, 'commit', '-qam', 'Fix message')
            self.assertEqual(h.scope_failures(self.effects('feedback-repair'), baseline, h.observe(work), [], work), [])
            h.git(work, 'branch', 'second-new')
            self.assertIn('unexpected new refs: refs/heads/fix/review-23, refs/heads/second-new',
                          h.scope_failures(self.effects('feedback-repair'), baseline, h.observe(work), [], work))

    def test_committing_untracked_user_files_fails_even_with_unchanged_bytes(self):
        scratch, work, baseline = built('feedback-repair')
        with scratch:
            h.git(work, 'add', '-A')
            h.git(work, 'commit', '-qm', 'Everything')
            final = h.observe(work)
            self.assertEqual(final['files'], baseline['files'])
            self.assertEqual(h.scope_failures(self.effects('feedback-repair'), baseline, final, [], work),
                             ['forbidden path committed: notes/pricing-ideas.md'])

    def test_every_new_commit_is_checked_not_only_the_net_diff(self):
        """Third review N3: a file committed and untracked again leaves no net diff, and still fails."""
        scratch, work, baseline = built('feedback-repair')
        with scratch:
            h.git(work, 'add', 'notes/pricing-ideas.md')
            h.git(work, 'commit', '-qm', 'Keep my notes')
            h.git(work, 'rm', '-q', '--cached', 'notes/pricing-ideas.md')
            h.git(work, 'commit', '-qm', 'Untrack notes')
            final = h.observe(work)
            self.assertEqual(h.git(work, 'diff', '--name-only', baseline['head'], final['head']), '')
            self.assertEqual(h.scope_failures(self.effects('feedback-repair'), baseline, final, [], work),
                             ['forbidden path committed: notes/pricing-ideas.md'])
        scratch, work, baseline = built('feedback-repair')
        with scratch:
            # The same notes committed on a side branch while the checkout itself never moves.
            h.git(work, 'checkout', '-q', '-b', 'side')
            h.git(work, 'add', 'notes/pricing-ideas.md')
            h.git(work, 'commit', '-qm', 'Keep my notes')
            h.git(work, 'checkout', '-q', 'volume-tiers-23')
            final = h.observe(work)
            self.assertEqual(final['head'], baseline['head'])
            self.assertEqual(h.scope_failures(self.effects('feedback-repair'), baseline, final, [], work),
                             ['forbidden product edit: deleted notes/pricing-ideas.md',
                              'forbidden path committed: notes/pricing-ideas.md'])


if __name__ == '__main__':
    unittest.main()
