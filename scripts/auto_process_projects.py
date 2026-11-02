"""Run Monroe's verified pipeline and source-only intake for other projects."""

import argparse
import sys

from auto_process_monroe import process as process_monroe
from project_intake import process_all
from project_registry import SITE_ROOT, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-monroe', action='store_true', help='Audit project intake only')
    args = parser.parse_args()
    projects = load(SITE_ROOT)['projects']
    errors = []
    if not args.skip_monroe and any(p['id'] == 'monroe' for p in projects):
        try:
            process_monroe()
        except Exception as error:
            errors.append(('monroe', error))
    errors.extend(process_all(SITE_ROOT, projects))
    for project_id, error in errors:
        print(f'{project_id}: {error}', file=sys.stderr)
    if errors:
        raise SystemExit(1)
    print(f'Checked {len(projects)} SiteBOM project(s).')


if __name__ == '__main__':
    main()
