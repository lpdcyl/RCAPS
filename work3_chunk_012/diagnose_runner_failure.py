"""Capture failing ModelLayer frame locals from the frozen runner without changing it."""

from __future__ import annotations

import json
import traceback

from work3_chunk_012.run import HERE, PROTOCOL, run_one


def main() -> None:
    try:
        run_one(2, PROTOCOL["duration_s"], "runs")
        result = {"status": "completed"}
    except Exception as error:
        frames = []
        tb = error.__traceback__
        while tb is not None:
            frame = tb.tb_frame
            item = {"file": frame.f_code.co_filename, "function": frame.f_code.co_name,
                    "line": tb.tb_lineno}
            if frame.f_code.co_filename.endswith("model.py") and \
                    frame.f_code.co_name == "get_inference_statistics":
                local = frame.f_locals
                layer = local.get("self")
                item.update({
                    "layer_id": getattr(layer, "layer_id", None),
                    "prompt_tokens": local.get("prompt_phase_tokens"),
                    "decode_tokens": local.get("decode_phase_tokens"),
                    "decode_left": local.get("decode_left"),
                    "decode_right": local.get("decode_right"),
                    "prompt_time_type": type(local.get("prompt_time")).__name__,
                    "decode_time_type": type(local.get("decode_time")).__name__,
                    "prompt_profile_types": {str(k): type(v).__name__ for k, v in
                                             getattr(layer, "prompt_bs2time", {}).items()},
                    "decode_profile_types": {str(k): type(v).__name__ for k, v in
                                             getattr(layer, "decode_bs2time", {}).items()},
                    "prompt_time_repr": repr(local.get("prompt_time"))[:200],
                    "decode_time_repr": repr(local.get("decode_time"))[:200],
                })
            frames.append(item)
            tb = tb.tb_next
        result = {"status": "failed", "error": repr(error),
                  "traceback": traceback.format_exc(), "frames": frames}
    output = HERE / "diagnostic_runner_failure.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(result["status"])


if __name__ == "__main__":
    main()
