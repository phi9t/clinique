"""Canonical sample-size engine via a pinned R Docker image running rpact (RFC-0003 §5.4).

rpact is regulatory-validated, so it is the canonical engine. This adapter runs ``power.R`` inside
the pinned image, passing parameters as JSON on stdin and parsing JSON from stdout. The image
digest and rpact version are recorded in the EngineResult for provenance (RFC-0000 §6).

The pure-Python ``ReferenceEngine`` remains an independent cross-check oracle; Docker cross-check
tests skip when the daemon is unreachable.
"""

from __future__ import annotations

import json
import subprocess

from ..substrate.records import EngineResult

DEFAULT_IMAGE = "clinique-r-engine:0.1.0"
_SCRIPT = "/opt/clinique/power.R"


class RpactDockerEngine:
    name = "rpact"

    def __init__(self, image: str = DEFAULT_IMAGE, docker: str = "docker", timeout: int = 180):
        self.image = image
        self.version = image
        self.docker = docker
        self.timeout = timeout

    @staticmethod
    def available(docker: str = "docker") -> bool:
        """True if the docker daemon is reachable."""
        try:
            proc = subprocess.run(
                [docker, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return proc.returncode == 0 and bool(proc.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            return False

    def _run(self, payload: dict) -> dict:
        proc = subprocess.run(
            [self.docker, "run", "--rm", "-i", self.image, "Rscript", _SCRIPT],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"rpact docker engine failed: {proc.stderr.strip()}")
        return json.loads(proc.stdout)

    def _result(self, method: str, inputs: dict, data: dict) -> EngineResult:
        tools = [
            {"name": "rpact", "version": str(data.get("rpact_version", "unknown"))},
            {"name": "image", "version": self.image},
        ]
        return EngineResult(
            engine=self.name,
            version=self.version,
            method=method,
            inputs=inputs,
            outputs={k: float(v) for k, v in data["outputs"].items()},
            achieved={k: float(v) for k, v in data.get("achieved", {}).items()},
            tools=tools,
        )

    def two_sample_means(self, *, delta, sd, alpha, power, ratio=1.0, sides=2) -> EngineResult:
        inputs = {"delta": delta, "sd": sd, "alpha": alpha, "power": power, "ratio": ratio, "sides": sides}
        return self._result("two_sample_means", inputs, self._run({"method": "two_sample_means", **inputs}))

    def two_proportions(self, *, p1, p2, alpha, power, ratio=1.0, sides=2) -> EngineResult:
        inputs = {"p1": p1, "p2": p2, "alpha": alpha, "power": power, "ratio": ratio, "sides": sides}
        return self._result("two_proportions", inputs, self._run({"method": "two_proportions", **inputs}))

    def survival_logrank(self, *, hazard_ratio, alpha, power, allocation=0.5, sides=2) -> EngineResult:
        inputs = {"hazard_ratio": hazard_ratio, "alpha": alpha, "power": power,
                  "allocation": allocation, "sides": sides}
        return self._result("survival_logrank", inputs, self._run({"method": "survival_logrank", **inputs}))
