"""Development-seed, offered-load parity of original and graph-backed M3."""

from __future__ import annotations

import json

from .route_parity import HERE, verify


def main() -> None:
    rows = [verify(name, offered, seed=seed, duration=300, natural_trace=True)
            for name, offered in (("single", 700.0), ("multi", 320.0))
            for seed in (100, 101)]
    result = {"purpose": "behavior regression under offered-load traces; not formal performance evidence",
              "formal_seeds_unchanged": [0, 1, 2], "rows": rows}
    output = HERE / "stress_route_parity.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not all(row["passed"] for row in rows):
        raise ValueError(f"Stress route parity failed; inspect {output}")
    print(output)


if __name__ == "__main__":
    main()
