"""Atomic checkpoints for the simulator's otherwise unpicklable event queue."""

from __future__ import annotations

import copyreg
import gzip
import os
import pickle
from pathlib import Path
from queue import PriorityQueue


def _restore_priority_queue(items, maxsize, unfinished_tasks):
    queue = PriorityQueue(maxsize=maxsize)
    queue.queue = items
    queue.unfinished_tasks = unfinished_tasks
    return queue


def _reduce_priority_queue(queue):
    return (_restore_priority_queue,
            (list(queue.queue), queue.maxsize, queue.unfinished_tasks))


copyreg.pickle(PriorityQueue, _reduce_priority_queue)


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", compresslevel=1) as compressed:
            pickle.dump(payload, compressed, protocol=pickle.HIGHEST_PROTOCOL)
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(path)


def load(path: Path) -> dict:
    with gzip.open(path, "rb") as handle:
        return pickle.load(handle)
