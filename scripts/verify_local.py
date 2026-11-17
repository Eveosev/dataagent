"""Install actual local packages in a fresh project and verify their public CLI.

The phase implementations live in scripts/acceptance/<phase>.py; this file
only parses the command line, builds the common fresh project, dispatches to
the selected phase and writes the report.
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acceptance import PHASES, bootstrap
from acceptance.common import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['bootstrap', 'files', 'sources', 'api-workflow', 'mixed-workflow', 'discovery'], default='bootstrap')
    parser.add_argument('--output', type=Path, default=ROOT/'.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance')
    parser.add_argument('--ocr-root', type=Path, help='verified local OCR directory to use for scanned PDF acceptance')
    parser.add_argument('--postgres-locator', help='local test database URL with a seeded invoice table')
    parser.add_argument('--postgres-user', default='dataagent_reader')
    args = parser.parse_args()
    if args.phase == 'files' and not args.ocr_root:
        parser.error('--phase files requires a verified local --ocr-root')
    if args.phase == 'sources' and not args.postgres_locator:
        parser.error('--phase sources requires --postgres-locator')
    mint = shutil.which('mint') or str(Path.home()/'.mint/bin/mint')
    project = Path(tempfile.mkdtemp(prefix='dataagent-intake-'))
    context = bootstrap.prepare(project, mint)
    args.output.mkdir(parents=True, exist_ok=True)
    report = bootstrap.base_report(args, context, project, mint)
    PHASES[args.phase].apply(report, project, args, context)
    (args.output/f'{args.phase}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    summary = {'status': 'passed', 'project': str(project), 'report': str(args.output/f'{args.phase}.json')}
    if args.phase == 'discovery':
        summary['session_id'] = report['discovery']['session_id']
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
