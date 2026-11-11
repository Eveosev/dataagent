"""HTTP transport confined to one trusted origin and exact configured routes."""

import json
import re
from urllib.parse import quote

import httpx

from ..bindings import PATH_PARAMETER


class ApiError(ValueError):
    def __init__(self, message, *, status=None):
        super().__init__(message)
        self.status = status


class ApiClient:
    def __init__(self, environment, timeout):
        self.environment = environment
        self.timeout = timeout

    def _request(self, method, path, *, query=None, body=None):
        with httpx.Client(
            base_url=self.environment.base_url,
            timeout=self.timeout,
            trust_env=False,
            follow_redirects=False,
            headers=self.environment.headers,
        ) as client:
            try:
                with client.stream(method, path, params=query, json=body) as response:
                    if not 200 <= response.status_code < 300:
                        raise ApiError(f"business API returned HTTP {response.status_code}", status=response.status_code)
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > 4 * 1024 * 1024:
                            raise ApiError("business API response exceeds 4 MiB")
                if not content and method != "GET":
                    return None
                return json.loads(content, parse_constant=self._invalid_number)
            except httpx.HTTPError as exc:
                raise ApiError(f"business API transport failed: {type(exc).__name__}") from exc
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ApiError("business API response is not valid JSON") from exc

    @staticmethod
    def _invalid_number(value):
        raise ApiError(f"business API response contains an invalid JSON number: {value}")

    def description(self):
        return self._request("GET", self.environment.openapi_path)

    def _operation(self, operation_id, arguments, *, write):
        policy = self.environment.operations[operation_id]
        if write != (policy.effect is not None):
            raise ValueError("operation is outside the connector method class")

        def path_value(match):
            name = match.group(1)
            value = arguments["path"].get(name)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                raise ValueError(f"{name!r} is not a valid path parameter")
            segment = str(value)
            if not re.fullmatch(r"[A-Za-z0-9._~-]+", segment) or segment in {".", ".."}:
                raise ValueError(f"{name!r} contains an unsupported path segment")
            return quote(segment, safe="")

        path = PATH_PARAMETER.sub(path_value, policy.path)
        return self._request(policy.method, path, query=arguments["query"], body=arguments["body"] if write else None)

    def read(self, operation_id, arguments):
        return self._operation(operation_id, arguments, write=False)

    def _dispatch(self, operation_id, arguments):
        """Called only by ActionGateway after the durable dispatch fence."""
        return self._operation(operation_id, arguments, write=True)
