"""
IonQ backend — REST API integration.

Main_Source §9A.3: Quantum runs are automatically exploratory.
Requires IONQ_TOKEN environment variable for hardware access.
Without the token, raises CredentialError (caller handles fallback).

IonQ API docs: https://docs.ionq.com/api-reference
"""
from __future__ import annotations

import logging
import time

from .credential import CredentialError, require_ionq_token

logger = logging.getLogger("scientificstate.daemon.quantum_hw.ionq")

_IONQ_BASE_URL = "https://api.ionq.co/v0.3"
_POLL_INTERVAL_S = 2.0
_MAX_POLL_ATTEMPTS = 300  # 10 minutes max wait


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
            Result dict with counts, quantum_metadata, and exploratory=True.

        Raises:
            CredentialError: If IONQ_TOKEN is not set.
        """
        import requests

        token = require_ionq_token()
        start_time = time.monotonic()
        headers = {
            "Authorization": f"apiKey {token}",
            "Content-Type": "application/json",
        }

        # Submit job
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
            submit_resp.raise_for_status()
            job_data = submit_resp.json()
            job_id = job_data["id"]
            logger.info("IonQ job submitted: %s (target=%s)", job_id, target)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("IonQ job submission failed: %s", exc)
            return {
                "status": "error",
                "error_code": "IONQ_SUBMIT_ERROR",
                "error": str(exc),
                "quantum_metadata": {
                    "provider": "ionq",
                    "target": target,
                    "execution_time_ms": elapsed_ms,
                },
                "exploratory": True,
            }

        # Poll for completion
        for attempt in range(_MAX_POLL_ATTEMPTS):
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
                        "status": "error",
                        "error_code": "IONQ_EXECUTION_ERROR",
                        "error": error_msg,
                        "quantum_metadata": {
                            "provider": "ionq",
                            "target": target,
                            "job_id": job_id,
                            "execution_time_ms": elapsed_ms,
                        },
                        "exploratory": True,
                    }

                time.sleep(_POLL_INTERVAL_S)
            except Exception as exc:
                logger.warning("IonQ poll attempt %d failed: %s", attempt, exc)
                time.sleep(_POLL_INTERVAL_S)
        else:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return {
                "status": "error",
                "error_code": "IONQ_TIMEOUT",
                "error": f"Job {job_id} did not complete within timeout",
                "quantum_metadata": {
                    "provider": "ionq",
                    "target": target,
                    "job_id": job_id,
                    "execution_time_ms": elapsed_ms,
                },
                "exploratory": True,
            }

        # Fetch results
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
                "status": "error",
                "error_code": "IONQ_RESULT_FETCH_ERROR",
                "error": str(exc),
                "quantum_metadata": {
                    "provider": "ionq",
                    "target": target,
                    "job_id": job_id,
                    "execution_time_ms": elapsed_ms,
                },
                "exploratory": True,
            }

        # IonQ returns probabilities → convert to counts
        counts = {}
        for bitstring, probability in raw_results.items():
            counts[str(bitstring)] = int(round(probability * shots))

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        qubit_count = job_status.get("qubits", 0)

        return {
            "status": "ok",
            "counts": counts,
            "quantum_metadata": {
                "backend_name": target,
                "shots": shots,
                "execution_time_ms": elapsed_ms,
                "qubit_count": qubit_count,
                "circuit_depth": job_status.get("circuit_depth", 0),
                "provider": "ionq",
                "job_id": job_id,
            },
            "exploratory": True,
        }
