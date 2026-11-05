"""DataAgent S0 core contracts.

Public surface is intentionally narrow: import from ``dataagent_contracts.core``.
"""

from .core import *  # noqa: F401,F403
from .core import __all__ as _core_all

__version__ = "0.1.0"
__all__ = list(_core_all) + ["__version__"]
