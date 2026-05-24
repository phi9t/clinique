"""Cross-check: canonical rpact Docker engine vs the pure-Python ReferenceEngine.

Skipped unless the docker daemon is reachable AND the image is built. Two independent engines
agreeing within a documented tolerance is strong validation. Tolerances are loose for means
(rpact uses the t-distribution; the reference uses the z-approximation).
"""

import pytest

from clinique.power.engines import ReferenceEngine
from clinique.power.rpact_docker import DEFAULT_IMAGE, RpactDockerEngine

pytestmark = pytest.mark.skipif(
    not RpactDockerEngine.available(),
    reason="docker daemon not reachable; bring it up and build clinique-r-engine to run",
)


def _image_present() -> bool:
    import subprocess

    proc = subprocess.run(["docker", "image", "inspect", DEFAULT_IMAGE], capture_output=True)
    return proc.returncode == 0


@pytest.fixture(scope="module")
def rpact():
    if not _image_present():
        pytest.skip(
            f"image {DEFAULT_IMAGE} not built (docker build -t {DEFAULT_IMAGE} docker/r-engine)"
        )
    return RpactDockerEngine()


def _close(a, b, rel):
    return abs(a - b) <= rel * b


def test_means_agreement(rpact):
    ref = ReferenceEngine().two_sample_means(delta=0.5, sd=1.0, alpha=0.05, power=0.80)
    got = rpact.two_sample_means(delta=0.5, sd=1.0, alpha=0.05, power=0.80)
    assert _close(got.outputs["n_total"], ref.outputs["n_total"], 0.05)


def test_proportions_agreement(rpact):
    ref = ReferenceEngine().two_proportions(p1=0.6, p2=0.4, alpha=0.05, power=0.80)
    got = rpact.two_proportions(p1=0.6, p2=0.4, alpha=0.05, power=0.80)
    assert _close(got.outputs["n_total"], ref.outputs["n_total"], 0.05)


def test_survival_agreement(rpact):
    ref = ReferenceEngine().survival_logrank(hazard_ratio=0.7, alpha=0.05, power=0.80)
    got = rpact.survival_logrank(hazard_ratio=0.7, alpha=0.05, power=0.80)
    assert _close(got.outputs["events_total"], ref.outputs["events_total"], 0.03)
