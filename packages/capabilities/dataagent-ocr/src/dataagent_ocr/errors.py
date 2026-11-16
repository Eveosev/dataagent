"""OCR setup and runtime errors with stable codes.

``needs_input`` errors ask the user/agent for something (credentials, a
confirmation, an egress decision); they are never retried automatically and
never trigger a provider switch.
"""

from __future__ import annotations


class OcrError(Exception):
    code = "ocr.error"
    needs_input = False
    retryable = False

    def __init__(self, message: str, *, action: str | None = None):
        super().__init__(message)
        self.message = message
        self.action = action

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "action": self.action,
            "needs_input": self.needs_input,
            "retryable": self.retryable,
        }


class NotConfigured(OcrError):
    code = "ocr.not_configured"
    needs_input = True


class NotVerified(OcrError):
    code = "ocr.not_verified"
    needs_input = True


class PinMismatch(OcrError):
    code = "ocr.pin_mismatch"
    needs_input = True


class CredentialsError(OcrError):
    code = "ocr.credentials"
    needs_input = True


class ConfigError(OcrError):
    code = "ocr.config"
    needs_input = True


class ProviderUnavailable(OcrError):
    code = "ocr.unavailable"
    retryable = True


class EgressRequired(OcrError):
    code = "ocr.egress_required"
    needs_input = True


class SwitchRefused(OcrError):
    code = "ocr.switch_refused"
    needs_input = True


class InstallRefused(OcrError):
    code = "ocr.install_refused"
    needs_input = True


class EngineMissing(OcrError):
    code = "ocr.engine_missing"
    needs_input = True
