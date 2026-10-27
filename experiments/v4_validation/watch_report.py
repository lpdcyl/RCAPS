"""Refresh counts on state changes; reconcile once all queues are terminal."""
import time
from pathlib import Path
from experiments.v4_formal.run import read
from .summarize import main

HERE=Path(__file__).resolve().parent
previous=None
while True:
    names=['external_continue_index.json','diagnostic_index.json','neighbor_index.json']
    signature=tuple((name,(HERE/name).stat().st_mtime_ns if (HERE/name).exists() else None) for name in names)
    if signature!=previous:
        try: main()
        except BaseException as e: print('REPORT_REFRESH_ERROR',repr(e),flush=True)
        previous=signature
    if all((HERE/n).exists() and read(HERE/n)['status'] in
           ['completed','blocked_preflight','blocked_controller'] for n in names):
        break
    time.sleep(30)
