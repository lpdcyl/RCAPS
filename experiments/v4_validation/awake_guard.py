"""Keep this overnight run awake without changing the Windows power plan."""
import ctypes
import json
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
names=['external_continue_index.json','diagnostic_index.json','neighbor_index.json']
set_state=ctypes.windll.kernel32.SetThreadExecutionState
started=time.monotonic()
try:
    result=set_state(0x80000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; display may sleep.
    print('KEEP_SYSTEM_AWAKE',bool(result),'maximum 12 hours',flush=True)
    while time.monotonic()-started<12*3600:
        if all((HERE/n).exists() and json.loads((HERE/n).read_text(encoding='utf-8'))['status']
               in ['completed','blocked_preflight','blocked_controller'] for n in names):
            break
        time.sleep(30)
finally:
    set_state(0x80000000)
    print('POWER_REQUEST_RELEASED',flush=True)
