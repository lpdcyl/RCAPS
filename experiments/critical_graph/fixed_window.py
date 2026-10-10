"""Compatibility import; implementation lives in benchmarks.fixed_window."""

from benchmarks.fixed_window import *  # noqa: F401,F403


if __name__ == "__main__":
    from benchmarks.fixed_window import main

    main()
