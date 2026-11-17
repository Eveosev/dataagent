#!/usr/bin/env python3
"""Layering guard: business packages must not import platform adapters.

The platform package is `dataagent-runtime`; its `dataagent_runtime.adapters`
modules are the concrete local implementations behind the `ports`/`interfaces`
seams. Business packages may import contracts, ports, registry and interface
entry points, but reaching into an adapter couples them to the local platform
implementation (and is what R4/R5 removes).

Current violations are recorded in scripts/layering-baseline.json. The guard
is monotonically tightening: a violation site listed in the baseline may keep
its count or disappear; a new site, or a higher count at an existing site,
fails the check. Update the baseline only after a violation is actually
removed.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / 'scripts' / 'layering-baseline.json'
PLATFORM_PACKAGE = 'dataagent-runtime'
ADAPTER_ROOT = 'dataagent_runtime.adapters'


def business_packages(cap_dir: Path) -> list[Path]:
    return sorted(
        path for path in cap_dir.glob('dataagent-*')
        if path.is_dir() and path.name != PLATFORM_PACKAGE and (path / 'src').is_dir()
    )


def adapter_imports(tree: ast.AST) -> list[str]:
    """Return the platform-adapter modules imported by one module."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == ADAPTER_ROOT or alias.name.startswith(ADAPTER_ROOT + '.'):
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if module == 'dataagent_runtime' and any(alias.name == 'adapters' for alias in node.names):
                found.append(ADAPTER_ROOT)
            elif module == ADAPTER_ROOT or module.startswith(ADAPTER_ROOT + '.'):
                found.append(module)
    return found


def collect(cap_dir: Path) -> dict[tuple[str, str, str], int]:
    violations: dict[tuple[str, str, str], int] = {}
    for package in business_packages(cap_dir):
        for path in sorted((package / 'src').rglob('*.py')):
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            except (OSError, SyntaxError) as exc:
                raise SystemExit(f'check_layering: cannot parse {path}: {exc}')
            for module in adapter_imports(tree):
                key = (package.name, path.relative_to(package).as_posix(), module)
                violations[key] = violations.get(key, 0) + 1
    return violations


def baseline_entries(path: Path) -> dict[tuple[str, str, str], int]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise SystemExit(f'check_layering: cannot read baseline {path}: {exc}')
    entries: dict[tuple[str, str, str], int] = {}
    for item in data.get('violations', []):
        key = (item['package'], item['file'], item['module'])
        if key in entries:
            raise SystemExit(f'check_layering: duplicate baseline site {describe(key)}')
        entries[key] = int(item.get('count', 1))
    declared_total = data.get('total')
    if declared_total is not None and int(declared_total) != sum(entries.values()):
        raise SystemExit(
            f'check_layering: baseline total says {declared_total}, '
            f'sites sum to {sum(entries.values())}'
        )
    return entries


def describe(key: tuple[str, str, str]) -> str:
    package, file, module = key
    return f'{package}/{file}: imports {module}'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=DEFAULT_BASELINE,
                        help='baseline JSON (default: scripts/layering-baseline.json)')
    parser.add_argument('--capabilities', type=Path, default=ROOT / 'packages' / 'capabilities',
                        help='capability package directory')
    args = parser.parse_args()

    baseline = baseline_entries(args.baseline)
    current = collect(args.capabilities)
    baseline_total = sum(baseline.values())
    current_total = sum(current.values())

    new_sites = sorted(key for key in current if key not in baseline)
    grown = sorted(
        (key, baseline[key], current[key])
        for key in current if key in baseline and current[key] > baseline[key]
    )
    resolved = sorted(key for key in baseline if key not in current)

    for key in new_sites:
        print(f'NEW      {describe(key)} ({current[key]}x)', file=sys.stderr)
    for key, allowed, actual in grown:
        print(f'GROWN    {describe(key)} ({actual}x > baseline {allowed}x)', file=sys.stderr)

    if new_sites or grown:
        print(f'check_layering: FAILED ({current_total} violations, baseline {baseline_total}; '
              f'{len(new_sites)} new site(s), {len(grown)} grown site(s))', file=sys.stderr)
        return 1

    if resolved:
        print(f'check_layering: {len(resolved)} baseline site(s) resolved; update the baseline to lock the gain')
    print(f'check_layering: ok ({current_total} violations, baseline {baseline_total})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
