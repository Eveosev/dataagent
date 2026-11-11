"""Read-only local browser observations with content-addressed screenshots."""
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode
from uuid import uuid4

from dataagent_contracts.environment import UIControl, UIObservation

from ..bindings import digest


class PlaywrightBrowser:
    def __init__(self, environment, evidence_root):
        self.environment = environment
        self.evidence_root = Path(evidence_root)

    def observe(self, environment_id, page_ref, scope_ref, *, business_key=None):
        config = self.environment.browser
        if config is None or page_ref not in config.pages:
            raise ValueError('select a browser page configured by the host')
        target = self.environment.base_url + config.pages[page_ref]
        env = {key: value for key, value in os.environ.items()
               if key in {'PATH', 'HOME', 'TMPDIR', 'LANG', 'TZ'} or key.startswith('LC_')}
        request = {'modulePath': str(config.playwright_module), 'channel': config.channel, 'url': target,
                   'readResources': [self.environment.base_url + path for path in config.read_resources]}
        if business_key is not None:
            lookup = config.lookups.get(page_ref)
            if lookup is None:
                raise ValueError('select a status lookup configured by the host')
            request['url'] += '?'+urlencode({lookup.key_parameter: business_key})
            request['lookup'] = {**lookup.model_dump(mode='json'), 'business_key': business_key}
        worker = Path(__file__).with_name('playwright_observe.cjs')
        try:
            result = subprocess.run([config.node, worker], input=json.dumps(request), capture_output=True,
                                    text=True, timeout=25, env=env, check=True)
            data = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise ValueError('local browser observation unavailable; check the configured browser') from exc
        controls = [UIControl(id=digest([index, control])[:20], **control)
                    for index, control in enumerate(data['controls'])]
        screenshot_ref = screenshot_digest = None
        if data.get('screenshot'):
            png = base64.b64decode(data['screenshot'], validate=True)
            if not png.startswith(b'\x89PNG\r\n\x1a\n') or len(png) > 4 * 1024 * 1024:
                raise ValueError('invalid browser screenshot evidence')
            screenshot_digest = sha256(png).hexdigest()
            directory = self.evidence_root/'browser-evidence'
            if directory.is_symlink():
                raise ValueError('browser evidence directory must not be a symlink')
            directory.mkdir(exist_ok=True)
            path = directory/(screenshot_digest+'.png')
            if path.is_symlink():
                raise ValueError('browser evidence must not be a symlink')
            try:
                with path.open('xb') as stream:
                    stream.write(png)
            except FileExistsError:
                if path.read_bytes() != png:
                    raise ValueError('browser evidence digest mismatch')
            screenshot_ref = str(path.relative_to(self.evidence_root))
        return UIObservation(
            id=uuid4().hex, environment_id=environment_id, page_ref=page_ref,
            scope_ref=scope_ref, observed_at=datetime.now(timezone.utc), state=data['state'],
            page_version=digest([self.environment.identity, config.pages[page_ref], data['state'], data['controls']]),
            controls=controls, status_text=data['status_text'], screenshot_ref=screenshot_ref,
            screenshot_digest=screenshot_digest, record_evidence=data.get('record_evidence'),
        )
