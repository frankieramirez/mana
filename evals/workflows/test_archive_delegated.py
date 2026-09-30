import gzip
import json
from pathlib import Path
import tempfile
import unittest
from archive_delegated import archive, verify


class Archive(unittest.TestCase):
    def test_roundtrip_excludes_host_state_and_checks_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'run';source.mkdir()
            (source/'events.jsonl').write_text('{"output":"observed"}\n')
            private=source/'workspace/home';private.mkdir(parents=True)
            (private/'private').write_text('excluded')
            (source/'linked').symlink_to(source/'events.jsonl')
            target=root/'evidence.json.gz'
            archive(source,target)
            payload=json.loads(gzip.decompress(target.read_bytes()))
            self.assertEqual({'events.jsonl'},set(payload['files']))
            self.assertEqual(1,verify(target)['verified_files'])
            payload['files']['events.jsonl']['text']='changed'
            target.write_bytes(gzip.compress(json.dumps(payload).encode()))
            with self.assertRaisesRegex(ValueError,'digest mismatch'):verify(target)


if __name__=='__main__':unittest.main()
