"""Correct dispatch adapter; preserve all earlier failed dispatch records."""
import argparse
from types import SimpleNamespace
import subprocess

from . import run as registered


BASE = registered.HERE
AMENDMENT = BASE / "execution_amendment.json"
MODULE = "experiments.v4_core_validation.run_execution"


def install():
    amendment = registered.read(AMENDMENT)
    assert amendment["manifest_sha256"] == registered.digest(registered.MANIFEST)
    for name, sha in amendment["sources_sha256"].items():
        assert registered.digest(registered.ROOT / name) == sha, name
    original_popen = subprocess.Popen

    def popen(command, **kwargs):
        command = list(command)
        if MODULE in command:
            i = command.index("utf8") if "utf8" in command else -1
            if i > 0 and command[i - 1] == "-X":
                del command[i - 1:i + 1]
        return original_popen(command, **kwargs)

    registered.subprocess = SimpleNamespace(Popen=popen, STDOUT=subprocess.STDOUT,
                                            CREATE_NO_WINDOW=subprocess.CREATE_NO_WINDOW)
    registered.MODULE = MODULE
    registered.HERE = BASE / "execution"
    registered.HERE.mkdir(exist_ok=True)
    registered.INDEX = registered.HERE / "index.json"


def main():
    install()
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["one", "queue", "status", "launch-check"], required=True)
    parser.add_argument("--key")
    args = parser.parse_args()
    if args.phase == "one":
        registered.one(args.key)
    elif args.phase == "launch-check":
        registered.validate()
        with (BASE / "engineering/dispatch_check.log").open("x", encoding="utf-8") as log:
            process = registered.subprocess.Popen([registered.sys.executable, "-u", "-X", "utf8",
                "-m", MODULE, "--phase", "status"], cwd=registered.ROOT,
                stdout=log, stderr=registered.subprocess.STDOUT,
                creationflags=registered.subprocess.CREATE_NO_WINDOW)
            code = process.wait()
        assert code == 0, code
        print("DISPATCH_CHECK_PASSED")
    else:
        getattr(registered, args.phase)()


if __name__ == "__main__":
    main()
