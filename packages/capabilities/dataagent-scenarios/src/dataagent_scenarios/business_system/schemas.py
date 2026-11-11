"""Configurable domain assets and strict request/response schemas."""
from copy import deepcopy
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

DEFAULT_CONFIG = {
    'domains': {
        'expenses': {
            'title': 'Expense claims', 'fields': [
                {'name': 'employee', 'label': 'Employee', 'type': 'string', 'required': True},
                {'name': 'amount', 'label': 'Amount', 'type': 'decimal', 'required': True},
                {'name': 'currency', 'label': 'Currency', 'type': 'string', 'required': True},
                {'name': 'purpose', 'label': 'Purpose', 'type': 'string', 'required': True}],
        },
        'orders': {
            'title': 'Purchase orders', 'fields': [
                {'name': 'supplier', 'label': 'Supplier', 'type': 'string', 'required': True},
                {'name': 'total', 'label': 'Total', 'type': 'decimal', 'required': True},
                {'name': 'currency', 'label': 'Currency', 'type': 'string', 'required': True}],
        },
    },
}


def domain_config(config: dict | None = None) -> dict:
    result = deepcopy(config if config is not None else DEFAULT_CONFIG)
    for domain in result['domains'].values():
        for key, value in {'layout': 'table', 'submit_label': 'Submit for approval',
                           'pagination': 'offset', 'page_size': 20, 'collection_field': 'items',
                           'require_attachment': False, 'approval_delay_seconds': None,
                           'approval_outcome': 'approved'}.items():
            domain.setdefault(key, value)
    return result


def data_model(name: str, config: dict, *, partial: bool = False):
    fields = {}
    for item in config['fields']:
        typ = {'string': str, 'decimal': Decimal, 'integer': int, 'boolean': bool}[item['type']]
        if item['type'] == 'string':
            constraint = {'min_length': 1}
        elif item['type'] == 'decimal':
            constraint = {'gt': 0}
        else:
            constraint = {}
        required = item.get('required', False) and not partial
        fields[item['name']] = (typ if required else typ | None,
                                Field(... if required else None, title=item['label'], **constraint))
    return create_model(name, __config__=ConfigDict(extra='forbid'), **fields)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    business_key: str = Field(min_length=1)
    data: dict[str, Any]


class PatchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data: dict[str, Any]


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: str = Field(min_length=1, description='Stable idempotency key for this business action')


class AttachmentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filename: str = Field(min_length=1)
    content_type: str = 'application/octet-stream'
    content_base64: str
    request_key: str = Field(min_length=1)


class Record(BaseModel):
    id: str
    domain: str
    business_key: str
    data: dict[str, Any]
    status: Literal['draft', 'submitted', 'waiting_approval', 'approved', 'rejected']
    native_status: str
    created_at: str
    updated_at: str
    observed_at: str
    attachments: list[dict[str, Any]]


class Event(BaseModel):
    sequence: int
    record_id: str
    status: str
    native_status: str
    occurred_at: str


class EventPage(BaseModel):
    items: list[Event]
    cursor: int
    has_more: bool
