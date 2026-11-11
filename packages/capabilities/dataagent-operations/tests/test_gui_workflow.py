from pathlib import Path
import shutil

import pytest

from dataagent_operations.service import OperationsService


def test_observes_real_page_and_detects_changed_required_field(configured, business):
    path, config = configured
    env = config['environments']['test-orders']
    packages = Path(__file__).resolve().parents[2]
    env['browser'] = {
        'node': shutil.which('node'),
        'playwright_module': str(packages/'dataagent-workbench/web/node_modules/playwright'),
        'channel': 'chrome',
        'pages': {'new_order': '/ui/orders/records/new'},
    }
    service = OperationsService(path, config)
    first = service.observe_web('test-orders', 'new_order')
    assert first.state == 'observed'
    assert (path.parent/first.screenshot_ref).read_bytes().startswith(b'\x89PNG')
    assert any(control.name == 'Supplier' for control in first.controls)
    assert business[1].get('/api/orders/records').json()['total'] == 0
    changed = business[2].post('/config', headers={'X-Admin-Token':'evaluation-only'}, json={
        'domain':'orders', 'required_field':{'name':'cost_center','label':'Cost center','type':'string'},
    })
    assert changed.status_code == 200
    latest = service.observe_web('test-orders', 'new_order')
    assert latest.page_version != first.page_version
    assert any(control.name == 'Cost center' and control.required for control in latest.controls)
    assert service.web_observation(first.id) == first
    with pytest.raises(ValueError, match='configured'):
        service.observe_web('test-orders', '/ui/orders/records/new?unapproved')


def test_browser_blocks_unapproved_requests_and_rejects_hidden_status(configured, dispatch_fault):
    from dataagent_operations.adapters.playwright_browser import PlaywrightBrowser
    from dataagent_operations.bindings import EnvironmentConfig
    path, config = configured
    env = config['environments']['test-orders']
    packages = Path(__file__).resolve().parents[2]
    env['browser'] = {
        'node': shutil.which('node'),
        'playwright_module': str(packages/'dataagent-workbench/web/node_modules/playwright'),
        'channel': 'chrome',
        'pages': {'observer_probe': '/ui/observer-probe'},
        'lookups': {'observer_probe': {'key_parameter':'business_key','row':'tr',
                                      'key':'td:first-child','status':'td:last-child'}},
    }
    browser = PlaywrightBrowser(EnvironmentConfig.model_validate(env), path.parent)
    observed = browser.observe('test-orders','observer_probe','finance',business_key='po-work')
    assert observed.state == 'observed'
    assert observed.record_evidence is None
    assert 'unapproved_read' not in dispatch_fault
