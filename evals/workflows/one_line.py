#!/usr/bin/env python3
"""Build a one-line control payload from a skills directory; never invokes a model.

Each skill keeps its SKILL.md frontmatter, so discovery and invocation see the same
name and description. The body becomes the first sentence of the description, and
references and scripts are left out. Running it beside the full skills shows whether
the long instructions beat a one-line instruction."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SENTENCE_END = re.compile(r'(?<=[.!?])\s+')


def outside_production(path):
    path = Path(path).resolve()
    for protected in (ROOT / 'skills', ROOT / 'agents', ROOT / 'output-styles'):
        if path == protected.resolve() or path.is_relative_to(protected.resolve()):
            raise ValueError('control payloads cannot be written under ' + str(protected))
    return path


def split_frontmatter(text):
    if not text.startswith('---\n'):
        raise ValueError('SKILL.md has no frontmatter')
    end = text.find('\n---\n', 4)
    if end < 0:
        raise ValueError('SKILL.md frontmatter is not closed')
    return text[:end + 5], text[4:end]


def description(frontmatter):
    for line in frontmatter.splitlines():
        if line.startswith('description:'):
            value = line[len('description:'):].strip()
            if value.startswith('"'):
                value = json.loads(value)
            if not value or value in ('>', '|', '>-', '|-'):
                raise ValueError('description must be a single-line value')
            return value
    raise ValueError('SKILL.md has no description')


def one_line(text):
    """Return the control SKILL.md for one full SKILL.md text."""
    head, frontmatter = split_frontmatter(text)
    sentence = SENTENCE_END.split(description(frontmatter), 1)[0].strip()
    return head + '\n' + sentence + '\n', sentence


def build(source, destination, names=None):
    """Write a new control payload. The source is only read; the destination must be new."""
    source = Path(source)
    destination = outside_production(destination)
    if destination.exists():
        raise ValueError('destination already exists: ' + str(destination))
    skills = sorted(p.parent.name for p in source.glob('*/SKILL.md'))
    if names:
        missing = sorted(set(names) - set(skills))
        if missing:
            raise ValueError('no such skill: ' + ', '.join(missing))
        skills = sorted(set(names))
    if not skills:
        raise ValueError('no SKILL.md under ' + str(source))
    record = {}
    for name in skills:
        body, sentence = one_line((source / name / 'SKILL.md').read_text(encoding='utf-8'))
        target = destination / name / 'SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_text(body, encoding='utf-8')
        record[name] = sentence
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True, help='skills directory to read')
    parser.add_argument('--out', type=Path, required=True, help='new directory for the control payload')
    parser.add_argument('--skill', action='append', help='limit to these skills; repeatable')
    args = parser.parse_args()
    try:
        record = build(args.build, args.out, args.skill)
    except (OSError, ValueError) as error:
        print('one_line: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps({'out': str(args.out.resolve()), 'skills': record}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
