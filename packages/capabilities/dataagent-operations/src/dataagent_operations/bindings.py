"""Trusted endpoint and effect policy, separate from candidate workflow data."""

from hashlib import sha256
from pathlib import Path
import json
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dataagent_contracts.intake import WorkSpec
from dataagent_contracts.workflow import Pointer, Predicate

PATH_PARAMETER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(encode(value).encode()).hexdigest()


def check_path(value):
    if not re.fullmatch(r"/[A-Za-z0-9_./{}-]+", value):
        raise ValueError(f"invalid relative API path {value!r}")
    if "//" in value or any(segment in {".", ".."} for segment in value.split("/")):
        raise ValueError(f"invalid relative API path {value!r}")
    remaining = PATH_PARAMETER.sub("", value)
    if "{" in remaining or "}" in remaining:
        raise ValueError(f"invalid API path parameter in {value!r}")


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EffectPolicy(ConfigModel):
    action: str = Field(min_length=1)
    lookup_operation: str
    collection_pointer: Pointer
    record_key_pointer: Pointer = "/business_key"
    record_id_pointer: Pointer = "/id"
    applied: Predicate
    before: Predicate | None = None
    partial: Predicate | None = None
    definitive_not_applied: Predicate | None = None
    business_key_field: str | None = None
    record_id_parameter: str | None = None
    request_key_field: str | None = None
    match_fields: dict[Pointer, Pointer] = Field(default_factory=dict)
    remote_idempotency: bool = False
    remote_fencing: bool = False
    browser_lookup_page: str | None = None

    @model_validator(mode="after")
    def check_effect(self):
        if not (self.business_key_field or self.record_id_parameter):
            raise ValueError("an effect must target the scoped business key or resolved record ID")
        if self.record_id_parameter and self.before is None:
            raise ValueError("record actions need a business precondition")
        if self.business_key_field and self.business_key_field == self.request_key_field:
            raise ValueError("business and request keys require separate fields")
        if self.definitive_not_applied and not self.remote_idempotency:
            raise ValueError("resuming an action after definitive negative proof requires remote idempotency")
        if self.remote_fencing:
            raise ValueError("this API connector has no remote fencing protocol")
        if self.browser_lookup_page and (self.applied.pointer != "/status" or self.match_fields):
            raise ValueError("browser reconciliation can only verify a configured status effect")
        return self


class OperationPolicy(ConfigModel):
    method: str
    path: str
    business_key_parameter: str | None = None
    record_lookup: str | None = None
    collection_pointer: Pointer | None = None
    record_key_pointer: Pointer = "/business_key"
    record_id_pointer: Pointer = "/id"
    record_id_parameter: str | None = None
    effect: EffectPolicy | None = None

    @model_validator(mode="after")
    def check_operation(self):
        check_path(self.path)
        if self.method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            raise ValueError(f"unsupported API method {self.method}")
        if (self.method != "GET") != (self.effect is not None):
            raise ValueError("each write needs an effect policy, and reads cannot declare one")
        if self.record_lookup and (self.collection_pointer is None or not self.record_id_parameter):
            raise ValueError("record lookup needs a collection pointer and path parameter")
        if self.record_id_parameter and not self.record_lookup:
            raise ValueError("record reads need a scoped lookup")
        parameter = self.effect.record_id_parameter if self.effect else self.record_id_parameter
        if parameter and parameter not in PATH_PARAMETER.findall(self.path):
            raise ValueError("record ID parameter must be in the configured path")
        return self


class BrowserLookup(ConfigModel):
    key_parameter: str = Field(pattern=r'^[A-Za-z_][A-Za-z_0-9]*$')
    row: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=200)


class BrowserConfig(ConfigModel):
    node: Path
    playwright_module: Path
    channel: str | None = None
    pages: dict[str, str] = Field(min_length=1, max_length=30)
    lookups: dict[str, BrowserLookup] = Field(default_factory=dict)
    read_resources: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def check_browser(self):
        if not self.node.is_absolute() or not self.playwright_module.is_absolute():
            raise ValueError("browser executable and module must be host-owned absolute paths")
        for path in [*self.pages.values(), *self.read_resources]:
            check_path(path)
            if "{" in path or "}" in path:
                raise ValueError("browser pages must be explicit local paths")
        if set(self.lookups) - self.pages.keys():
            raise ValueError("browser lookup requires a configured page")
        return self


class EnvironmentConfig(ConfigModel):
    base_url: str
    tenant: str = Field(min_length=1)
    openapi_path: str = "/openapi.json"
    business_key_prefix: str = ""
    operations: dict[str, OperationPolicy] = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    browser: BrowserConfig | None = None

    @model_validator(mode="after")
    def check_environment(self):
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"http", "https"} or not url.hostname or url.username is not None
            or url.password is not None or url.path not in {"", "/"} or url.query or url.fragment
        ):
            raise ValueError("base_url must be a trusted HTTP(S) origin")
        self.base_url = self.base_url.rstrip("/")
        if self.browser and url.hostname != "127.0.0.1":
            raise ValueError("offline browser discovery requires an IPv4 loopback environment")
        check_path(self.openapi_path)
        if "{" in self.openapi_path:
            raise ValueError("openapi_path cannot contain path parameters")
        if any(key.lower() in {"host", "content-length", "transfer-encoding"} for key in self.headers):
            raise ValueError("transport headers are managed by the API connector")
        effects = set()
        for name, operation in self.operations.items():
            lookup_id = operation.effect.lookup_operation if operation.effect else operation.record_lookup
            if lookup_id:
                lookup = self.operations.get(lookup_id)
                if not lookup or not lookup.business_key_parameter or lookup.method != "GET" or lookup.record_lookup:
                    raise ValueError(f"{name}: business lookup must be a configured, scoped GET")
            if operation.effect:
                page = operation.effect.browser_lookup_page
                if page and (self.browser is None or page not in self.browser.lookups):
                    raise ValueError("action requires a configured browser status lookup")
                if operation.effect.action in effects:
                    raise ValueError("action semantics must have a unique API binding per environment")
                effects.add(operation.effect.action)
        return self

    @property
    def identity(self):
        url = urlsplit(self.base_url)
        port = url.port or (443 if url.scheme == "https" else 80)
        return digest([url.scheme, url.hostname.lower(), port, self.tenant])


class HostConfig(ConfigModel):
    scope_ref: str = Field(min_length=1)
    authorization_ref: str = Field(min_length=1)
    environments: dict[str, EnvironmentConfig] = Field(min_length=1)
    work_specs: list[WorkSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_work_specs(self):
        if len({work.id for work in self.work_specs}) != len(self.work_specs):
            raise ValueError("duplicate configured WorkSpec ID")
        for work in self.work_specs:
            if work.authorization_ref != self.authorization_ref:
                raise ValueError(f"WorkSpec {work.id!r} has a different authorization")
        return self
