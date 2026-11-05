"""``agent_provided`` inference adapter.

The data layer never calls a model. The Agent produces a structured proposal
under a Skill and passes it back in the second call. This adapter is the
explicit seam for hosts that want to drive that exchange through
``InferencePort`` instead of embedding the proposal in the tool input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from dataagent_runtime.errors import dependency_unavailable


@dataclass
class AgentProvidedInference:
    """Wrap a host callback that returns a Skill-shaped proposal."""

    provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    adapter_ref: str = "dataagent-data/inference@0.1.0#agent_provided"

    def infer(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.provider is None:
            raise dependency_unavailable(
                "agent_provided inference needs a host callback; no model is called here",
                action="call the tool again with the proposal from the Agent side",
            )
        result = self.provider(request)
        if not isinstance(result, dict):
            raise dependency_unavailable(
                "agent_provided inference callback must return a JSON object"
            )
        return result
