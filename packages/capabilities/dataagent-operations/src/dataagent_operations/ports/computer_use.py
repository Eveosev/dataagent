from typing import Protocol

from dataagent_contracts.environment import UIObservation


class ComputerUsePort(Protocol):
    def observe(self, environment_id: str, page_ref: str, scope_ref: str) -> UIObservation: ...
