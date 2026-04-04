"""
Quantum hardware credential management.

Resolves API tokens from environment variables.
Supports IBM Quantum (IBMQ_TOKEN) and IonQ (IONQ_TOKEN).

Security: tokens are never logged or serialized — only length is logged.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("scientificstate.daemon.quantum_hw.credential")

# Minimum acceptable token length (short tokens are almost certainly invalid)
_MIN_TOKEN_LENGTH = 8


class CredentialError(Exception):
    """Raised when a required credential is missing or invalid."""


# ---------------------------------------------------------------------------
# Token format validation
# ---------------------------------------------------------------------------

def _validate_token_format(token: str, provider: str) -> None:
    """Validate basic token format rules.

    Raises:
        CredentialError: If the token fails format checks.
    """
    if len(token) < _MIN_TOKEN_LENGTH:
        logger.warning(
            "%s token too short (length=%d, minimum=%d)",
            provider, len(token), _MIN_TOKEN_LENGTH,
        )
        raise CredentialError(
            f"{provider} token is too short (length={len(token)}). "
            f"Expected at least {_MIN_TOKEN_LENGTH} characters."
        )

    if any(ch.isspace() for ch in token):
        logger.warning("%s token contains whitespace (length=%d)", provider, len(token))
        raise CredentialError(
            f"{provider} token contains whitespace characters, which is invalid."
        )


# ---------------------------------------------------------------------------
# Token getters
# ---------------------------------------------------------------------------

def get_ibmq_token() -> str | None:
    """Return IBM Quantum token from environment, or None if not set."""
    token = os.environ.get("IBMQ_TOKEN")
    if token:
        # Security: log length only, never the actual value
        logger.debug("IBMQ_TOKEN found (length=%d)", len(token))
    return token


def get_ionq_token() -> str | None:
    """Return IonQ token from environment, or None if not set."""
    token = os.environ.get("IONQ_TOKEN")
    if token:
        # Security: log length only, never the actual value
        logger.debug("IONQ_TOKEN found (length=%d)", len(token))
    return token


# ---------------------------------------------------------------------------
# Token requirers (with format validation)
# ---------------------------------------------------------------------------

def require_ibmq_token() -> str:
    """Return IBM Quantum token or raise CredentialError."""
    token = get_ibmq_token()
    if not token:
        raise CredentialError(
            "IBMQ_TOKEN environment variable not set. "
            "Set it to your IBM Quantum API token to use real QPU hardware."
        )
    _validate_token_format(token, "IBMQ")
    return token


def require_ionq_token() -> str:
    """Return IonQ token or raise CredentialError."""
    token = get_ionq_token()
    if not token:
        raise CredentialError(
            "IONQ_TOKEN environment variable not set. "
            "Set it to your IonQ API key to use IonQ hardware."
        )
    _validate_token_format(token, "IONQ")
    return token


# ---------------------------------------------------------------------------
# Connectivity tests
# ---------------------------------------------------------------------------

def test_ibmq_connectivity() -> dict:
    """Validate that the IBMQ token can authenticate with the service.

    Returns:
        dict with "ok" bool and optional "error" string.
    """
    try:
        token = require_ibmq_token()
    except CredentialError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService

        service = QiskitRuntimeService(channel="ibm_quantum", token=token)
        backends = service.backends(min_num_qubits=1, operational=True)
        logger.info(
            "IBMQ connectivity OK — %d operational backends found", len(backends)
        )
        return {"ok": True, "backend_count": len(backends)}
    except ImportError:
        return {"ok": False, "error": "qiskit-ibm-runtime not installed"}
    except Exception as exc:
        # Security: never include the token in the error output
        logger.warning("IBMQ connectivity test failed (token length=%d)", len(token))
        return {"ok": False, "error": str(exc)}


def test_ionq_connectivity() -> dict:
    """Validate that the IonQ token can authenticate with the API.

    Returns:
        dict with "ok" bool and optional "error" string.
    """
    try:
        token = require_ionq_token()
    except CredentialError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        import requests

        resp = requests.get(
            "https://api.ionq.co/v0.3/backends",
            headers={"Authorization": f"apiKey {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        backends = resp.json()
        logger.info("IonQ connectivity OK — response received")
        return {"ok": True, "backends": backends}
    except ImportError:
        return {"ok": False, "error": "requests library not installed"}
    except Exception as exc:
        # Security: never include the token in the error output
        logger.warning("IonQ connectivity test failed (token length=%d)", len(token))
        return {"ok": False, "error": str(exc)}
