"""Convert the downloaded UK National Grid API response to canonical CSV."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/carbon/raw/uk_grid_intensity_2025-01-01.json"
PROCESSED = ROOT / "data/carbon/processed/uk_grid_intensity_2025-01-01.csv"
METADATA = ROOT / "data/carbon/metadata/uk_grid_intensity_2025-01-01.json"
SOURCE_URL = "https://api.carbonintensity.org.uk/intensity/date/2025-01-01"


def _timestamp(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).timestamp()


def main() -> None:
    payload = json.loads(RAW.read_text(encoding="utf-8"))
    rows = []
    for item in payload["data"]:
        actual = item["intensity"].get("actual")
        if actual is None:
            continue
        rows.append(
            {
                "timestamp": _timestamp(item["from"]),
                "region": "GB",
                "carbon_intensity_g_per_kwh": float(actual),
            }
        )
    if not rows:
        raise ValueError("Historical response contains no actual intensity values")
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "region", "carbon_intensity_g_per_kwh"],
        )
        writer.writeheader()
        writer.writerows(rows)
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    METADATA.write_text(
        json.dumps(
            {
                "source": "UK National Grid Carbon Intensity API",
                "source_url": SOURCE_URL,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "raw_file": str(RAW.relative_to(ROOT)),
                "processed_file": str(PROCESSED.relative_to(ROOT)),
                "raw_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
                "row_count": len(rows),
                "source_interval_minutes": 30,
                "resampling": "none; source 30-minute intervals retained as piecewise constant",
                "unit": "gCO2e/kWh",
                "actual_field_used": True,
                "regions": ["GB"],
                "notes": "One real regional trace is mapped to both synthetic simulator regions; this is not a multi-region spatial validation.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"rows={len(rows)}")
    print(f"processed={PROCESSED}")
    print(f"metadata={METADATA}")


if __name__ == "__main__":
    main()
