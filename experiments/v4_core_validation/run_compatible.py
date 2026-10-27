"""Launch-only amendment: preserve the frozen Windows locale discovery path."""
import argparse
from types import SimpleNamespace
import subprocess

from . import run as registered


def main():
    amendment = registered.read(registered.HERE / "launch_amendment.json")
    assert amendment["manifest_sha256"] == registered.digest(registered.MANIFEST)
    for name, sha in amendment["sources_sha256"].items():
        assert registered.digest(registered.ROOT / name) == sha, name
    original_popen = subprocess.Popen

    def popen(command, **kwargs):
        # Only the registered worker invocation is changed. No simulator hooks,
        # environment checks, protocol, parameters, or data are replaced.
        command = list(command)
        if "experiments.v4_core_validation.run_compatible" in command:
            i = command.index("utf8") if "utf8" in command else -1
            if i > 0 and command[i - 1] == "-X":
                del command[i - 1:i + 1]
        return original_popen(command, **kwargs)

    registered.subprocess = SimpleNamespace(Popen=popen, CREATE_NO_WINDOW=subprocess.CREATE_NO_WINDOW)
    registered.MODULE = "experiments.v4_core_validation.run_compatible"
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["one", "queue", "status"], required=True)
    parser.add_argument("--key")
    args = parser.parse_args()
    if args.phase == "one":
        registered.one(args.key)
    else:
        getattr(registered, args.phase)()


if __name__ == "__main__":
    main()
