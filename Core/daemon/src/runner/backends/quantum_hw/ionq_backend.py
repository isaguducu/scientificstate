"""
IonQ backend — REST API integration.

Main_Source §9A.3: Quantum runs are automatically exploratory.
Requires IONQ_TOKEN environment variable for hardware access.
Without the token, raises CredentialError (caller handles fallback).

IonQ API docs: https://docs.ionq.com/api-reference
"""
from __future__ import annotations

import logging
import os
import time
import uuid

from .credential import CredentialError, require_ionq_token

logger = logging.getLogger("scientificstate.daemon.quantum_hw.ionq")

_IONQ_BASE_URL = "https://api.ionq.co/v0.3"

# ---------------------------------------------------------------------------
# Configurable polling & timeout via environment
# ---------------------------------------------------------------------------
IONQ_MAX_POLL_ATTEMPTS = int(os.environ.get("IONQ_MAX_POLL_ATTEMPTS", "300"))
IONQ_POLL_INTERVAL = int(os.environ.get("IONQ_POLL_INTERVAL_SECONDS", "2"))
IONQ_TIMEOUT = int(os.environ.get("IONQ_TIMEOUT_SECONDS", "600"))

# Transient HTTP status codes eligible for submit retry
_TRANSIENT_HTTP_CODES = {429, 500, 502, 503}
_MAX_SUBMIT_RETRIES = 3


class IonQBackend:
    """IonQ quantum hardware backend via REST API."""

    def __init__(self) -> None:
        self._token: str | None = None

    def is_available(self) -> bool:
        """Check if IonQ credentials are available."""
        try:
            self._token = require_ionq_token()
            return True
        except CredentialError:
            return False

    def execute(
        self,
        circuit_qasm: str,
        shots: int = 1024,
        target: str = "qpu.harmony",
    ) -> dict:
        """
        Submit circuit to IonQ hardware and return results.

        Args:
            circuit_qasm: OpenQASM circuit string.
            shots: Number of measurement shots.
            target: IonQ target device (default: qpu.harmony).

        Returns:
            Result dict with counts, execution_witness, and exploratory=True.

        Raises:
            CredentialError: If IONQ_TOKEN is not set.
        """
        import requests

        run_id = str(uuid.uuid4())
        token = require_ionq_token()
        # Security: log only token length, never the value
        logger.debug("IONQ token resolved (length=%d)", len(token))

        start_time = time.monotonic()
        headers = {
            "Authorization": f"apiKey {token}",
            "Content-Type": "application/json",
        }

        # ------------------------------------------------------------------
        # Submit job — with retry on transient HTTP errors
        # ------------------------------------------------------------------
        job_id: str | None = None
        last_submit_exc: Exception | None = None

        for attempt in range(1, _MAX_SUBMIT_RETRIES + 1):
            try:
                submit_resp = requests.post(
                    f"{_IONQ_BASE_URL}/jobs",
                    headers=headers,
                    json={
                        "lang": "openqasm",
                        "body": circuit_qasm,
                        "shots": shots,
                        "target": target,
                    },
                    timeout=30,
                )

                # Retry on transient HTTP codes
                if submit_resp.status_code in _TRANSIENT_HTTP_CODES:
                    logger.warning(
                        "IonQ submit attempt %d/%d got HTTP %d — retrying",
                        attempt, _MAX_SUBMIT_RETRIES, submit_resp.status_code,
                    )
                    if attempt < _MAX_SUBMIT_RETRIES:
                        backoff = 2 ** attempt  # 2s, 4s, 8s
                        time.sleep(backoff)
                        continue
                    submit_resp.raise_for_status()

                submit_resp.raise_for_status()
                job_data = submit_resp.json()
                job_id = job_data["id"]
                logger.info("IonQ job submitted: %s (target=%s)", job_id, target)
                break

            except Exception as exc:
                last_submit_exc = exc
                logger.warning(
                    "IonQ submit attempt %d/%d failed: %s",
                    attempt, _MAX_SUBMIT_RETRIES, exc,
                )
                if attempt < _MAX_SUBMIT_RETRIES:
                    backoff = 2 ** attempt
                    time.sleep(backoff)

        if job_id is None:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("IonQ job submission failed after %d retries", _MAX_SUBMIT_RETRIES)
            return {
                "run_id": run_id,
                "status": "error",
                "error_code": "IONQ_SUBMIT_ERROR",
                "error": str(last_submit_exc),
                "compute_class": "quantum_hw",
                "execution_witness": {
                    "compute_class": "quantum_hw",
                    "backend_id": target,
                    "quantum_metadata": {
                        "provider": "ionq",
                        "backend_name": target,
                        "shots": shots,
                        "execution_time_ms": elapsed_ms,
                    },
                },
                "exploratory": True,
            }

        # ------------------------------------------------------------------
        # Poll for completion
        # ------------------------------------------------------------------
        job_status: dict = {}
        for poll_attempt in range(IONQ_MAX_POLL_ATTEMPTS):
            # Honour overall timeout
            elapsed = time.monotonic() - start_time
            if elapsed > IONQ_TIMEOUT:
                break

            try:
                status_resp = requests.get(
                    f"{_IONQ_BASE_URL}/jobs/{job_id}",
                    headers=headers,
                    timeout=15,
                )
                status_resp.raise_for_status()
                job_status = status_resp.json()

                if job_status["status"] == "completed":
                    break
                elif job_status["status"] == "failed":
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    error_msg = job_status.get("error", {}).get("message", "Unknown IonQ error")
                    return {
                        "run_id": run_id,
                        "status": "error",
                        "error_code": "IONQ_EXECUTION_ERROR",
                        "error": error_msg,
                        "compute_class": "quantum_hw",
                        "execution_witness": {
                            "compute_class": "quantum_hw",
                            "backend_id": target,
                            "quantum_metadata": {
                                "provider": "ionq",
                                "backend_name": target,
                                "shots": shots,
                                "job_id": job_id,
                                "execution_time_ms": elapsed_ms,
                            },
                        },
                        "exploratory": True,
                    }

                time.sleep(IONQ_POLL_INTERVAL)
            except Exception as exc:
                logger.warning("IonQ poll attempt %d failed: %s", poll_attempt, exc)
                time.sleep(IONQ_POLL_INTERVAL)
        else:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return {
                "run_id": run_id,
                "status": "error",
                "error_code": "IONQ_TIMEOUT",
                "error": f"Job {job_id} did not complete within timeout",
                "compute_class": "quantum_hw",
                "execution_witness": {
                    "compute_class": "quantum_hw",
                    "backend_id": target,
                    "quantum_metadata": {
                        "provider": "ionq",
                        "backend_name": target,
                        "shots": shots,
                        "job_id": job_id,
                        "execution_time_ms": elapsed_ms,
                    },
                },
                "exploratory": True,
            }

        # ------------------------------------------------------------------
        # Fetch results
        # ------------------------------------------------------------------
        try:
            results_resp = requests.get(
                f"{_IONQ_BASE_URL}/jobs/{job_id}/results",
                headers=headers,
                timeout=15,
            )
            results_resp.raise_for_status()
            raw_results = results_resp.json()
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return {
                "run_id": run_id,
                "status": "error",
                "error_code": "IONQ_RESULT_FETCH_ERROR",
                "error": str(exc),
                "compute_class": "quantum_hw",
                "execution_witness": {
                    "compute_class": "quantum_hw",
                    "backend_id": target,
                    "quantum_metadata": {
                        "provider": "ionq",
                        "backend_name": target,
                        "shots": shots,
                        "job_id": job_id,
                        "execution_time_ms": elapsed_ms,
                    },
                },
                "exploratory": True,
            }

        # IonQ returns probabilities -> convert to counts
        counts = {}
        for bitstring, probability in raw_results.items():
            counts[str(bitstring)] = int(round(probability * shots))

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        qubit_count = job_status.get("qubits", 0)
        circuit_depth = job_status.get("circuit_depth", 0)

        return {
            "run_id": run_id,
            "status": "succeeded",
            "counts": counts,
            "compute_class": "quantum_hw",
            "execution_witness": {
                "compute_class": "quantum_hw",
                "backend_id": target,
                "quantum_metadata": {
                    "provider": "ionq",
                    "backend_name": target,
                    "shots": shots,
                    "circuit_depth": circuit_depth,
                    "qubit_count": qubit_count,
                    "execution_time_ms": elapsed_ms,
                    "job_id": job_id,
                },
            },
            "exploratory": True,
        }
