"""D4 HTTP surface: registry counts and published-instance pages."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app
from test_query import _published_model, _save_sales_order, saved_rows


def _client(wb):
    return TestClient(create_app(wb), headers={'x-dataagent-token': wb.token})


ROWS = [
    {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
    {'number': 'INV-2', 'amount_minor': '20000', 'currency': 'CNY'},
    {'number': 'INV-3', 'amount_minor': '30000', 'currency': 'USD'},
]


def test_registry_merges_published_instance_counts(tmp_path):
    wb, _ = saved_rows(tmp_path, ROWS)
    response = _client(wb).get('/api/ontologies')
    assert response.status_code == 200
    data = response.json()
    entry, = [item for item in data['ontologies'] if item['id'] == 'procurement']
    assert entry['published_instance_count'] == 3
    assert entry['instance_counts']['PurchaseDocument'] == 3
    assert entry['current_revision_instance_counts']['PurchaseDocument'] == 3
    assert 'last_published_at' in entry


def test_instances_endpoint_filters_pages_and_rejects_bad_where(tmp_path):
    wb, _ = saved_rows(tmp_path, ROWS)
    api = _client(wb)

    first = api.get('/api/ontologies/procurement/instances',
                    params={'concept': 'PurchaseDocument', 'limit': 2})
    assert first.status_code == 200, first.json()
    page = first.json()
    assert page['total'] == 3 and page['count'] == 2 and page['has_more'] is True
    assert page['deactivated'] is False
    assert page['concept'] == 'PurchaseDocument'
    cursor = page['next_cursor']
    assert cursor
    seen = [item['instance_id'] for item in page['items']]
    while cursor:
        follow = api.get('/api/ontologies/procurement/instances',
                         params={'concept': 'PurchaseDocument', 'limit': 2,
                                 'cursor': cursor})
        assert follow.status_code == 200, follow.json()
        seen += [item['instance_id'] for item in follow.json()['items']]
        cursor = follow.json()['next_cursor']
    assert len(seen) == 3 and len(set(seen)) == 3

    filtered = api.get('/api/ontologies/procurement/instances',
                       params={'where': json.dumps([
                           {'property': 'currency', 'op': 'in', 'value': ['USD']}])})
    assert filtered.status_code == 200
    assert filtered.json()['total'] == 1
    assert filtered.json()['items'][0]['values']['number'] == 'INV-3'

    shorthand = api.get('/api/ontologies/procurement/instances',
                        params={'where': json.dumps({'number': 'INV-2'})})
    assert shorthand.status_code == 200
    assert shorthand.json()['items'][0]['values']['number'] == 'INV-2'

    row = api.get('/api/ontologies/procurement/instances',
                  params={'where': json.dumps([{'property': 'secret',
                                                'op': 'eq', 'value': 'x'}])})
    assert row.status_code == 422
    assert 'not defined' in row.json()['detail']

    invalid = api.get('/api/ontologies/procurement/instances',
                      params={'where': 'not-json'})
    assert invalid.status_code == 422

    missing = api.get('/api/ontologies/not-registered/instances')
    assert missing.status_code == 404


def test_instances_endpoint_requires_the_local_token(tmp_path):
    wb, _ = saved_rows(tmp_path, ROWS)
    unauthenticated = TestClient(create_app(wb))
    assert unauthenticated.get('/api/ontologies/procurement/instances').status_code == 401


def test_multi_concept_endpoint_requires_a_concept_and_retired_still_reads(tmp_path):
    wb = _published_model(tmp_path)
    _save_sales_order(wb, tmp_path, 'orders.csv', 1001)
    api = _client(wb)

    without = api.get('/api/ontologies/sales-model/instances')
    assert without.status_code == 422
    assert 'name one' in without.json()['detail']

    orders = api.get('/api/ontologies/sales-model/instances',
                     params={'concept': 'SalesOrder'})
    assert orders.status_code == 200, orders.json()
    assert orders.json()['total'] == 1

    registry = api.get('/api/ontologies').json()
    entry, = [item for item in registry['ontologies'] if item['id'] == 'sales-model']
    retired = api.post('/api/ontologies/sales-model/retire', json={
        'reason': '测试停用后的只读查询', 'confirmed': True,
        'expected_revision': entry['registry_revision']})
    assert retired.status_code == 200

    after = api.get('/api/ontologies/sales-model/instances',
                    params={'concept': 'SalesOrder'})
    assert after.status_code == 200, after.json()
    assert after.json()['deactivated'] is True
    assert after.json()['total'] == 1

    # The HTTP registry keeps D1's compatibility default (all entries) and
    # exposes the D4 active-only view explicitly.
    default_entries = {item['id']: item for item in
                       api.get('/api/ontologies').json()['ontologies']}
    assert 'sales-model' in default_entries
    assert default_entries['sales-model']['state'] == 'retired'
    assert default_entries['sales-model']['deactivated'] is True
    active_ids = {item['id'] for item in api.get(
        '/api/ontologies',
        params={'include_deactivated': False}).json()['ontologies']}
    assert 'sales-model' not in active_ids


def test_unknown_ontology_is_404_not_an_empty_page(tmp_path):
    wb = Workbench(tmp_path)
    missing = _client(wb).get('/api/ontologies/does-not-exist/instances')
    assert missing.status_code == 404


def test_instances_endpoint_supports_ordered_conditions_and_related_objects(tmp_path):
    from test_query import expense_model
    wb = expense_model(tmp_path)
    api = _client(wb)

    over = api.get('/api/ontologies/expense-model/instances',
                   params={'concept': 'ExpenseLine', 'limit': 200,
                           'where': json.dumps([
                               {'property': 'amount', 'op': 'gt', 'value': '500'}])})
    assert over.status_code == 200, over.json()
    assert over.json()['total'] == 1
    assert over.json()['items'][0]['values']['amount'] == '600'

    dated = api.get('/api/ontologies/expense-model/instances',
                    params={'concept': 'ExpenseLine', 'limit': 200,
                            'where': json.dumps([
                                {'property': 'spent_on', 'op': 'gte',
                                 'value': '2026-03-02'}])})
    assert dated.status_code == 200
    assert dated.json()['total'] == 3

    page = api.get('/api/ontologies/expense-model/instances',
                   params={'concept': 'ExpenseLine', 'limit': 200,
                           'include_related': json.dumps({
                               'relation': 'usesStandard', 'fields': ['limit']})})
    assert page.status_code == 200, page.json()
    body = page.json()
    assert body['related_stats'] == {
        'relation': 'usesStandard', 'matched': 3, 'missing': 1, 'ambiguous': 0,
    }
    limits = sorted(item['related']['fields']['limit']
                    for item in body['items'] if item['related'])
    assert limits == ['500', '500', '80']
    assert body['related_missing_count'] == 1
    assert body['related_missing'][0]['values']['category'] == '交通'

    shorthand = api.get('/api/ontologies/expense-model/instances',
                        params={'concept': 'ExpenseLine', 'limit': 200,
                                'related': 'usesStandard',
                                'related_fields': 'limit'})
    assert shorthand.status_code == 200, shorthand.json()
    assert shorthand.json()['related_stats']['matched'] == 3
    assert sorted(item['related']['fields']['limit']
                  for item in shorthand.json()['items']
                  if item['related']) == ['500', '500', '80']

    # FDE3-02: slim rows by default, anchors on demand, comparison in one call.
    assert 'source' in body['items'][0]
    assert 'source_anchors' not in body['items'][0]
    detail = api.get('/api/ontologies/expense-model/instances',
                     params={'concept': 'ExpenseLine', 'limit': 1,
                             'detail': 'anchors'})
    assert detail.status_code == 200, detail.json()
    assert detail.json()['items'][0]['source_anchors']
    assert 'source' not in detail.json()['items'][0]

    compared = api.get('/api/ontologies/expense-model/instances',
                       params={'concept': 'ExpenseLine', 'limit': 200,
                               'include_related': json.dumps({
                                   'relation': 'usesStandard'}),
                               'where': json.dumps([
                                   {'field': 'amount', 'op': 'gt',
                                    'related_field': 'limit'}])})
    assert compared.status_code == 200, compared.json()
    assert compared.json()['total'] == 2
    assert compared.json()['comparison']['missing'] == 1

    invalid = api.get('/api/ontologies/expense-model/instances',
                      params={'concept': 'ExpenseLine',
                              'include_related': 'not-json'})
    assert invalid.status_code == 422
    unknown = api.get('/api/ontologies/expense-model/instances',
                      params={'concept': 'ExpenseLine',
                              'include_related': json.dumps({
                                  'relation': 'missing', 'fields': ['limit']})})
    assert unknown.status_code == 422
    assert 'unknown relation' in unknown.json()['detail']
