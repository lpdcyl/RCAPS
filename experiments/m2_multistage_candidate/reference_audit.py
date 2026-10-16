"""Freeze and verify the scoring reference shared by each four-cell pool."""

from __future__ import annotations

import hashlib
import json
import math

from rcaps.placement.topology import TopologyModel

from .placement import HERE, ROOT, digest, measure, signature, validate
from .prepare import CASES, VARIANTS, files, legacy_state, reference_state


def audit() -> dict:
    offline = json.loads((HERE / "offline_audit.json").read_text(encoding="utf-8"))
    result = {}
    for case in CASES:
        physical, _, _ = files(case)
        model = TopologyModel(physical)
        seed = legacy_state(case, model)
        reference = reference_state(case, model, seed)
        validate(model, reference)
        metrics = measure(model, reference)
        for key in ("ttft_s", "tpot_s", "bottleneck_s"):
            if not math.isclose(metrics[key], offline[case]["reference"][key],
                                rel_tol=1e-12, abs_tol=1e-10):
                raise ValueError(f"Reference metric changed: {case}/{key}")
        for variant in VARIANTS:
            folder = HERE / "layouts" / case / variant
            placement = json.loads((folder / "placement.json").read_text(
                encoding="utf-8"))
            for key in ("ttft_s", "tpot_s", "bottleneck_s"):
                if not math.isclose(placement["reference"][key], metrics[key],
                                    rel_tol=1e-12, abs_tol=1e-10):
                    raise ValueError(f"Four-cell scoring reference differs: {case}/{variant}")
        if case.startswith("C1_"):
            source = "rcaps.placement.adaptive.reference_state"
            source_sha256 = digest(ROOT / "rcaps/placement/adaptive.py")
        else:
            path = (ROOT / "experiments/v2_resource_generalization/layouts" /
                    case / "adaptive/placement.json")
            source = str(path.relative_to(ROOT)).replace("\\", "/")
            source_sha256 = digest(path)
        result[case] = {"reference_state": reference,
                        "state_sha256": hashlib.sha256(signature(reference).encode()).hexdigest(),
                        "source": source, "source_sha256": source_sha256,
                        "metrics": metrics, "four_cells_match": True}
    (HERE / "reference_audit.json").write_text(json.dumps(result, indent=2) + "\n",
                                                 encoding="utf-8")
    return result


if __name__ == "__main__":
    print(len(audit()), "pool references checked")
