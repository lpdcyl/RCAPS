"""Register executed-layer admission variants without changing prior evidence."""

import json
import shutil

from experiments.v3_cluster42.run import HERE, digest

ROOT = HERE / "kv_slice"
VARIANTS = (("kv_capacity", "c400k_w3_b1"),
            ("kv_capacity600", "c600k_w2_b20"),
            ("kv_capacity600", "c600k_w3_b12"))


def main():
    ROOT.mkdir(exist_ok=True)
    rows = []
    for parent, original in VARIANTS:
        name = original.replace("_w", "_slice_w")
        source = HERE / parent / original
        target = ROOT / name
        if not target.exists():
            shutil.copytree(source, target)
        placement = json.loads((source / "placement.json").read_text())
        placement.update(candidate=name, kv_reservation_mode="executed_layers",
                         parent_layout_sha256=digest(source / "placement.json"))
        (target / "placement.json").write_text(json.dumps(placement, indent=2) + "\n")
        row = next(row for row in json.loads((HERE / parent / "shortlist.json").read_text())
                   if row["name"] == original)
        rows.append({**row, "name": name, "parent": f"{parent}/{original}",
                     "kv_reservation_mode": "executed_layers"})
    (ROOT / "shortlist.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps([{k: row[k] for k in ("name", "active_gpus", "max_hops")}
                      for row in rows], indent=2))


if __name__ == "__main__":
    main()
