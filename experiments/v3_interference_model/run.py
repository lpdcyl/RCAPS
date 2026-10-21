"""T0.6 directory entry point; all phases are offline and create no windows."""

from __future__ import annotations

import argparse
import unittest

from . import analyze, test_model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("smoke", "formal", "report"), required=True)
    phase = parser.parse_args().phase
    if phase == "smoke":
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_model)
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
            raise SystemExit(1)
    else:
        analyze.main()


if __name__ == "__main__":
    main()
