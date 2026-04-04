"""
Quantum hardware credential management.

Resolves API tokens from environment variables.
Supports IBM Quantum (IBMQ_TOKEN) and IonQ (IONQ_TOKEN).

Security: tokens are never logged or serialized.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("scientificstate.daemon.quantum_hw.credential")


class CredentialError(Exception):
    """Raised when a required credential is missing or invalid."""


def get_ibmq_token() -> str | None:
    """Return IBM Quantum token from environment, or None if not set."""
    token = os.environ.get("IBMQ_TOKEN")
    if token:
        logger.debug("IBMQ_TOKEN found (length=%d)", len(token))
    return token


def get_ionq_token() -> str | None:
    """Return IonQ token from environment, or None if not set."""
    token = os.environ.get("IONQ_TOKEN")
    if token:
        logger.debug("IONQ_TOKEN found (length=%d)", len(token))
    return token


def require_ibmq_token() -> str:
    """Return IBM Quantum token or raise CredentialError."""
    token = get_ibmq_token()
    if not token:
        raise CredentialError(
            "IBMQ_TOKEN environment variable not set. "
            "Set it to your IBM Quantum API token to use real QPU hardware."
        )
    return token


def require_ionq_token() -> str:
    """Return IonQ token or raise CredentialError."""
    token = get_ionq_token()
    if not token:
        raise CredentialError(
            "IONQ_TOKEN environment variable not set. "
            "Set it to your IonQ API key to use IonQ hardware."
        )
    return token
