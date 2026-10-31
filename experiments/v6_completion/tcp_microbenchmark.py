"""Windows loopback TCP check of application-level large-message blocking.

The rate limit is imposed by the sender, not tc/netem or the physical NIC.
"""

import csv
import hashlib
import json
import math
import random
import socket
import socketserver
import struct
import threading
import time
from pathlib import Path
from statistics import mean, stdev


HERE = Path(__file__).resolve().parent
LARGE_BYTES = 12_300_000
SMALL_BYTES = 16_384
CHUNK_BYTES = 4_194_304
RATE_BYTES_PER_S = 12_500_000
APPLICATION_PROPAGATION_S = 0.025
SMALL_ARRIVAL_RATE_PER_S = 8
REPEATS = 5
HEADER = struct.Struct("!cId")


def exact(stream, size):
    parts = bytearray()
    while len(parts) < size:
        part = stream.recv(size - len(parts))
        if not part:
            return None if not parts else (_ for _ in ()).throw(EOFError("Truncated frame"))
        parts.extend(part)
    return bytes(parts)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        while True:
            header = exact(self.request, HEADER.size)
            if header is None:
                return
            kind, length, scheduled = HEADER.unpack(header)
            remaining = length
            while remaining:
                block = self.request.recv(min(remaining, 65536))
                if not block:
                    raise EOFError("Truncated payload")
                remaining -= len(block)
            if kind == b"S":
                with self.server.records_lock:
                    self.server.records.append(time.perf_counter() - scheduled)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def connect(port):
    stream = socket.create_connection(("127.0.0.1", port), timeout=5)
    stream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return stream


def large_frame(stream, amount):
    stream.sendall(HEADER.pack(b"L", amount, 0.0))
    payload = b"L" * 65536
    remaining = amount
    while remaining:
        size = min(remaining, len(payload))
        stream.sendall(payload[:size])
        time.sleep(size / RATE_BYTES_PER_S)
        remaining -= size


def small_frame(stream, scheduled):
    stream.sendall(HEADER.pack(b"S", SMALL_BYTES, scheduled) + b"S" * SMALL_BYTES)


def arrivals(seed):
    rng = random.Random(seed)
    elapsed = 0.0
    result = []
    while True:
        elapsed += rng.expovariate(SMALL_ARRIVAL_RATE_PER_S)
        if elapsed >= LARGE_BYTES / RATE_BYTES_PER_S:
            return result
        result.append(elapsed)


def predicted_waits(mode, schedule):
    service = LARGE_BYTES / RATE_BYTES_PER_S
    boundary = CHUNK_BYTES / RATE_BYTES_PER_S
    predictions = []
    for arrival in schedule:
        if mode == "no_chunk":
            wait = service - arrival
        elif mode == "chunk":
            wait = min(service, math.ceil(arrival / boundary) * boundary) - arrival
        else:
            wait = 0.0
        predictions.append(max(0.0, wait) + SMALL_BYTES / RATE_BYTES_PER_S)
    return predictions


def one(mode, seed):
    schedule = arrivals(seed)
    assert schedule
    server = Server(("127.0.0.1", 0), Handler)
    server.records = []
    server.records_lock = threading.Lock()
    listener = threading.Thread(target=server.serve_forever, daemon=True)
    listener.start()
    port = server.server_address[1]
    large = connect(port)
    small = connect(port) if mode == "separate_connections" else large
    start = time.perf_counter() + 0.03
    schedule = [start + t for t in schedule]
    next_small = 0

    def send_due():
        nonlocal next_small
        while next_small < len(schedule) and schedule[next_small] <= time.perf_counter():
            small_frame(small, schedule[next_small])
            next_small += 1

    background = None
    if mode == "separate_connections":
        def send_other_connection():
            for target in schedule:
                time.sleep(max(0.0, target - time.perf_counter()))
                small_frame(small, target)
        background = threading.Thread(target=send_other_connection)
        background.start()
    time.sleep(max(0.0, start - time.perf_counter()))
    if mode == "chunk":
        remaining = LARGE_BYTES
        while remaining:
            amount = min(CHUNK_BYTES, remaining)
            large_frame(large, amount)
            remaining -= amount
            send_due()
    else:
        large_frame(large, LARGE_BYTES)
        if mode == "no_chunk":
            send_due()
    if background:
        background.join()
    else:
        while next_small < len(schedule):
            time.sleep(max(0.0, schedule[next_small] - time.perf_counter()))
            send_due()
    if small is not large:
        small.close()
    large.close()
    deadline = time.perf_counter() + 5
    while len(server.records) < len(schedule) and time.perf_counter() < deadline:
        time.sleep(0.005)
    server.shutdown()
    server.server_close()
    listener.join()
    assert len(server.records) == len(schedule), (mode, seed, len(server.records), len(schedule))
    measured = server.records
    predicted = predicted_waits(mode, [t - start for t in schedule])
    return {
        "mode": mode, "seed": seed, "n_small": len(measured),
        "mean_queue_s": mean(measured), "p95_queue_s": sorted(measured)[int(.95 * (len(measured) - 1))],
        "predicted_mean_queue_s": mean(predicted),
        "predicted_p95_queue_s": sorted(predicted)[int(.95 * (len(predicted) - 1))],
    }


def main():
    manifest = {
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "platform": "Windows loopback TCP with sender-side application pacing",
        "not_equivalent_to": "Linux tc netem or real 12.5 MB/s WAN",
        "large_bytes": LARGE_BYTES, "small_bytes": SMALL_BYTES, "chunk_bytes": CHUNK_BYTES,
        "sender_rate_bytes_per_s": RATE_BYTES_PER_S,
        "assumed_one_way_propagation_s_not_measured": APPLICATION_PROPAGATION_S,
        "small_arrival_rate_per_s": SMALL_ARRIVAL_RATE_PER_S,
        "seeds": list(range(REPEATS)),
    }
    path = HERE / "tcp_manifest.json"
    assert not path.exists(), path
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    rows = [one(mode, seed) for seed in range(REPEATS)
            for mode in ("no_chunk", "chunk", "separate_connections")]
    with (HERE / "tcp_individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Windows TCP 队头阻塞微基准", "",
        "本实验在 Windows loopback TCP 上用应用发送器限速 12.5 MB/s，比较单连接不分块、4 MiB 分块、双连接。每次发送 12.3 MB 大消息，并在发送期间按指数间隔产生 16 KiB 小消息；5 个随机种子。",
        "限速与 25 ms 单向传播均非网卡或 Linux tc netem 实测。下表仅报告实测的小消息排队时延，理论列采用同一应用发送规则；不称为真实 WAN/多机网络验证。", "",
        "| 方式 | 小消息排队均值(s) | P95(s) | 公式预测均值(s) |", "|---|---:|---:|---:|",
    ]
    for mode in ("no_chunk", "chunk", "separate_connections"):
        selected = [r for r in rows if r["mode"] == mode]
        lines.append(f"| {mode} | {mean(r['mean_queue_s'] for r in selected):.4f} ± {stdev(r['mean_queue_s'] for r in selected):.4f} | {mean(r['p95_queue_s'] for r in selected):.4f} | {mean(r['predicted_mean_queue_s'] for r in selected):.4f} |")
    lines += ["", "若需验证真实链路共享、TCP 拥塞及 25 ms 传播，应另在可控制网络条件的机器上运行 Linux tc netem。"]
    (HERE / "TCP_RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("TCP_BENCHMARK_COMPLETE", len(rows))


if __name__ == "__main__":
    main()
