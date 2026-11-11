"""Invoke the independently installed operations package through stdio MCP."""
import json
import os
import subprocess
from pathlib import Path

from dataagent_contracts.core import CapabilityResult


def call_operations(wb, name, arguments):
    packages = list((wb.workspace / '.mint/packages/dataagent').glob('operations@*'))
    config = os.environ.get('DATAAGENT_OPERATIONS_CONFIG')
    if len(packages) != 1 or not config or not Path(config).is_absolute():
        raise ValueError('install operations and configure DATAAGENT_OPERATIONS_CONFIG in the host')
    python = packages[0] / '.venv/bin/python'
    if not python.is_file():
        raise ValueError('operations environment missing; run dataagent setup')
    env = {key: value for key, value in os.environ.items()
           if key in {'PATH', 'HOME', 'TMPDIR', 'LANG', 'TZ'} or key.startswith('LC_')}
    env.update(DATAAGENT_OPERATIONS_CONFIG=config,
               DATAAGENT_OPERATIONS_DB=str(wb.root / 'db/operations.sqlite3'),
               DATAAGENT_OPERATIONS_WORKBENCH_DB=str(wb.root / 'db/workbench.sqlite3'))
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
        'name': name, 'arguments': arguments, '_meta': {'context': wb.ctx.model_dump(mode='json')},
    }}
    try:
        result = subprocess.run([python, '-m', 'dataagent_operations', 'mcp'],
                                input=json.dumps(request)+'\n', cwd=wb.workspace, env=env,
                                capture_output=True, text=True, timeout=90, check=True)
        response = json.loads(result.stdout)['result']
        return CapabilityResult.model_validate_json(response['content'][0]['text'])
    except (OSError, subprocess.SubprocessError, KeyError, ValueError, IndexError) as exc:
        raise ValueError('operations response unavailable; check workflow status before retrying') from exc
