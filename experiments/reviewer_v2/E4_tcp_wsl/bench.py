"""WSL2 netns/veth/netem TCP head-of-line benchmark. Standard library only."""
import argparse
import csv
import gzip
import json
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
from collections import defaultdict, deque
from pathlib import Path
from statistics import mean, stdev

import traffic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = HERE / "runs"
HEADER = struct.Struct("!cIIdI")  # kind, id, frame bytes, scheduled monotonic, total bytes
PAYLOAD = b"L" * 65536
SMALL_PAYLOAD = b"S" * traffic.SMALL_BYTES
SERVER_IP = "10.203.4.2"
PORT = 39391
T9 = 2.262157162740992
MODES = ("fifo", "priority", "chunk4", "chunk1", "two_connections")


def command(args, *, capture=False):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def exact(sock, count):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            if not data:
                return None
            raise EOFError("Truncated TCP frame")
        data.extend(chunk)
    return bytes(data)


def server(output, expected_small, expected_large, connections):
    records, cumulative, errors = {}, defaultdict(int), []
    guard = threading.Lock()

    def read_stream(sock):
        try:
            with sock:
                while True:
                    header = exact(sock, HEADER.size)
                    if header is None:
                        return
                    kind, msg_id, size, scheduled, total = HEADER.unpack(header)
                    remaining = size
                    while remaining:
                        block = sock.recv(min(remaining, 65536))
                        if not block:
                            raise EOFError("Truncated payload")
                        remaining -= len(block)
                    with guard:
                        cumulative[(kind, msg_id)] += size
                        if cumulative[(kind, msg_id)] > total:
                            raise RuntimeError("Payload exceeds declared total")
                        if cumulative[(kind, msg_id)] == total:
                            if str(msg_id) in records:
                                raise RuntimeError("Duplicate message id")
                            records[str(msg_id)] = {"kind": kind.decode("ascii"),
                                "completed_at": time.monotonic(), "scheduled_at": scheduled,
                                "payload_bytes": total}
        except BaseException as exc:
            errors.append(repr(exc))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((SERVER_IP, PORT))
        listener.listen(connections)
        listener.settimeout(15)
        threads = []
        for _ in range(connections):
            sock, _ = listener.accept()
            worker = threading.Thread(target=read_stream, args=(sock,))
            worker.start()
            threads.append(worker)
        for worker in threads:
            worker.join(timeout=180)
            if worker.is_alive():
                raise TimeoutError("TCP receiver did not finish")
    if errors:
        raise RuntimeError("; ".join(errors))
    kinds = [r["kind"] for r in records.values()]
    if kinds.count("S") != expected_small or kinds.count("L") != expected_large:
        raise RuntimeError(f"Received counts differ: {kinds.count('S')}/{expected_small} small, {kinds.count('L')}/{expected_large} large")
    output.write_text(json.dumps({"records": records}, ensure_ascii=False) + "\n", encoding="utf-8")


def connect():
    deadline = time.monotonic() + 10
    while True:
        try:
            sock = socket.create_connection((SERVER_IP, PORT), timeout=2)
            sock.settimeout(None)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            return sock
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(.05)


def send_frame(sock, event, amount, start):
    scheduled = start + event["at_s"]
    sock.sendall(HEADER.pack(event["kind"].encode("ascii"), event["id"], amount,
                             scheduled, traffic.LARGE_BYTES if event["kind"] == "L" else traffic.SMALL_BYTES))
    if event["kind"] == "S":
        sock.sendall(SMALL_PAYLOAD)
    else:
        remaining = amount
        while remaining:
            piece = min(remaining, len(PAYLOAD))
            sock.sendall(PAYLOAD[:piece])
            remaining -= piece


def send_single(events, mode, start):
    sock = connect()
    pending = deque()
    current_large = None
    cursor = 0
    chunk = 4_194_304 if mode == "chunk4" else 1_048_576 if mode == "chunk1" else traffic.LARGE_BYTES
    try:
        while cursor < len(events) or pending or current_large:
            now = time.monotonic() - start
            while cursor < len(events) and events[cursor]["at_s"] <= now:
                pending.append(dict(events[cursor]))
                cursor += 1
            if not pending and not current_large:
                time.sleep(max(0, start + events[cursor]["at_s"] - time.monotonic()))
                continue
            if mode == "fifo":
                chosen = pending.popleft()
            else:
                small_at = next((i for i, e in enumerate(pending) if e["kind"] == "S"), None)
                if small_at is not None:
                    chosen = pending[small_at]
                    del pending[small_at]
                elif current_large:
                    chosen = current_large
                    current_large = None
                else:
                    chosen = pending.popleft()
            amount = min(chosen["bytes"], chunk) if chosen["kind"] == "L" else chosen["bytes"]
            send_frame(sock, chosen, amount, start)
            chosen["bytes"] -= amount
            if chosen["kind"] == "L" and chosen["bytes"]:
                current_large = chosen
    finally:
        sock.close()


def send_two(events, start):
    large_sock, small_sock = connect(), connect()
    errors = []

    def feed(sock, subset):
        try:
            with sock:
                for event in subset:
                    time.sleep(max(0, start + event["at_s"] - time.monotonic()))
                    send_frame(sock, event, event["bytes"], start)
        except BaseException as exc:
            errors.append(repr(exc))

    a = threading.Thread(target=feed, args=(large_sock, [e for e in events if e["kind"] == "L"]))
    b = threading.Thread(target=feed, args=(small_sock, [e for e in events if e["kind"] == "S"]))
    a.start()
    b.start()
    a.join()
    b.join()
    if errors:
        raise RuntimeError("; ".join(errors))


def percentile(values, percent):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * percent / 100
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def qdisc_bytes(device):
    output = command(["tc", "-s", "qdisc", "show", "dev", device], capture=True).stdout
    match = re.search(r"Sent (\d+) bytes", output)
    if not match:
        raise RuntimeError("Cannot read tc qdisc sent bytes: " + output)
    return int(match.group(1))


def setup():
    if os.geteuid() != 0:
        raise PermissionError("Run the network benchmark with sudo/root inside WSL2")
    name = f"rcaps-e4-{os.getpid()}"
    a = f"e4a{os.getpid() % 100000}"
    b = f"e4b{os.getpid() % 100000}"
    existing = command(["ip", "netns", "list"], capture=True).stdout
    if name in existing:
        raise RuntimeError("Namespace already exists; refusing to overwrite")
    command(["ip", "netns", "add", name])
    try:
        command(["ip", "link", "add", a, "type", "veth", "peer", "name", b])
        command(["ip", "link", "set", b, "netns", name])
        command(["ip", "addr", "add", "10.203.4.1/30", "dev", a])
        command(["ip", "link", "set", a, "up"])
        command(["ip", "netns", "exec", name, "ip", "addr", "add", "10.203.4.2/30", "dev", b])
        command(["ip", "netns", "exec", name, "ip", "link", "set", "lo", "up"])
        command(["ip", "netns", "exec", name, "ip", "link", "set", b, "up"])
        return name, a
    except BaseException:
        subprocess.run(["ip", "link", "del", a], check=False)
        command(["ip", "netns", "del", name])
        raise


def teardown(name, device):
    subprocess.run(["ip", "link", "del", device], check=False)
    subprocess.run(["ip", "netns", "del", name], check=False)


def run_one(rate, mode, repetition, namespace, device, all_traffic, manifest):
    label = str(rate).replace(".", "p")
    folder = RUNS / f"{label}MBps" / mode / f"repeat{repetition['repeat']}"
    folder.mkdir(parents=True, exist_ok=True)
    result, failure = folder / "result.json", folder / "failure.json"
    if result.exists() or failure.exists():
        return "skipped_existing"
    marker = folder / "started.json"
    if marker.exists():
        traffic.write(failure, {"classification": "interrupted", "started_marker": str(marker)})
        return "failed_interrupted"
    events = repetition["events"]
    small_count = repetition["small_count"]
    large_count = repetition["large_count"]
    traffic.write(marker, {"rate_MBps": rate, "mode": mode, "repeat": repetition["repeat"],
                           "manifest_sha256": traffic.sha(traffic.MANIFEST), "started_at": time.time()})
    receiver_file = folder / "receiver.json"
    receiver_log = (folder / "receiver.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(["ip", "netns", "exec", namespace, sys.executable, str(Path(__file__).resolve()),
                             "--server", "--receiver-output", str(receiver_file),
                             "--expected-small", str(small_count), "--expected-large", str(large_count),
                             "--connections", "2" if mode == "two_connections" else "1"],
                            cwd=ROOT, stdout=receiver_log, stderr=subprocess.STDOUT)
    try:
        sent_before = qdisc_bytes(device)
        start = time.monotonic() + .25
        if mode == "two_connections":
            send_two(events, start)
        else:
            send_single(events, mode, start)
        code = proc.wait(timeout=60)
        if code != 0 or not receiver_file.exists():
            raise RuntimeError(f"Receiver failed with exit {code}; see receiver.log")
        received = traffic.read(receiver_file)["records"]
        small = [received[str(e["id"])]["completed_at"] - (start + e["at_s"])
                 for e in events if e["kind"] == "S"]
        large = [received[str(e["id"])]["completed_at"] - (start + e["at_s"])
                 for e in events if e["kind"] == "L"]
        if len(small) != small_count or len(large) != large_count or min(small + large) < 0:
            raise RuntimeError("Message count or monotonic latency invalid")
        sent_after = qdisc_bytes(device)
        received_bytes = sum(r["payload_bytes"] for r in received.values())
        expected_bytes = sum(e["bytes"] for e in events)
        if received_bytes != expected_bytes:
            raise RuntimeError("Received payload bytes do not match traffic")
        elapsed = max(r["completed_at"] for r in received.values()) - start
        model_mode = mode if mode != "two_connections" else "fair"
        prediction = (traffic.fair_prediction(events, rate * 1_000_000, .025)
                      if model_mode == "fair" else traffic.serial_prediction(events, mode, rate * 1_000_000, .025))
        predicted_small = [prediction[0][e["id"]] - e["at_s"] for e in events if e["kind"] == "S"]
        row = {"status": "completed", "rate_MBps": rate, "mode": mode, "repeat": repetition["repeat"],
               "small_count": small_count, "large_count": large_count,
               "small_mean_s": mean(small), "small_p95_s": percentile(small, 95),
               "small_p99_s": percentile(small, 99), "large_mean_s": mean(large),
               "large_p95_s": percentile(large, 95), "predicted_small_p95_s": percentile(predicted_small, 95),
               "prediction_model": model_mode, "prediction_p95_error_s": percentile(small, 95) - percentile(predicted_small, 95),
               "received_payload_bytes": received_bytes, "tc_sent_bytes": sent_after - sent_before,
               "elapsed_s": elapsed, "link_utilization": (sent_after - sent_before) / (rate * 1_000_000 * elapsed),
               "manifest_sha256": traffic.sha(traffic.MANIFEST), "traffic_sha256": traffic.sha(traffic.TRAFFIC),
               "receiver_sha256": traffic.sha(receiver_file), "kernel": os.uname().release,
               "python": sys.version.split()[0]}
        with gzip.open(folder / "raw_latency.json.gz", "wt", encoding="utf-8") as stream:
            json.dump({"small_s": small, "large_s": large, "predicted_small_s": predicted_small}, stream)
        row["raw_latency_sha256"] = traffic.sha(folder / "raw_latency.json.gz")
        traffic.write(result, row)
        return "completed"
    except BaseException as exc:
        traffic.write(failure, {"status": "failed", "rate_MBps": rate, "mode": mode,
             "repeat": repetition["repeat"], "error": repr(exc), "traceback": traceback.format_exc(),
             "manifest_sha256": traffic.sha(traffic.MANIFEST), "finished_at": time.time()})
        return "failed"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        receiver_log.close()


def report(all_traffic):
    rows, failures = [], []
    for rate in (12.5, 25, 50):
        label = str(rate).replace(".", "p")
        for repetition in all_traffic["repetitions"]:
            for mode in MODES:
                folder = RUNS / f"{label}MBps" / mode / f"repeat{repetition['repeat']}"
                result, failure = folder / "result.json", folder / "failure.json"
                if result.exists():
                    row = traffic.read(result)
                    if row["manifest_sha256"] != traffic.sha(traffic.MANIFEST):
                        raise RuntimeError(f"Manifest mismatch: {result}")
                    rows.append(row)
                elif failure.exists():
                    failed = traffic.read(failure)
                    failures.append({"rate_MBps": rate, "mode": mode, "repeat": repetition["repeat"],
                                     "status": "failed", "error": failed.get("error"),
                                     "source": failure.relative_to(ROOT).as_posix(), "sha256": traffic.sha(failure)})
                else:
                    failures.append({"rate_MBps": rate, "mode": mode, "repeat": repetition["repeat"],
                                     "status": "pending", "error": None, "source": None, "sha256": None})
    fields = ("rate_MBps", "mode", "repeat", "status", "small_count", "large_count",
              "small_mean_s", "small_p95_s", "small_p99_s", "large_mean_s", "large_p95_s",
              "predicted_small_p95_s", "prediction_p95_error_s", "received_payload_bytes",
              "tc_sent_bytes", "elapsed_s", "link_utilization", "source", "sha256", "error")
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            path = RUNS / f"{str(row['rate_MBps']).replace('.', 'p')}MBps" / row["mode"] / f"repeat{row['repeat']}" / "result.json"
            writer.writerow({k: row.get(k) for k in fields} | {"source": path.relative_to(ROOT).as_posix(), "sha256": traffic.sha(path)})
        for row in failures:
            writer.writerow(row)
    lines = ["# E4：WSL2 Linux TCP 栈队头阻塞微基准", "",
             "测量条件为 veth+netem 虚拟链路；不是物理 NIC 或真实跨机网络。Prompt 到达由已审计全局请求轨迹确定性抽样，Decode 到达按所选慢链路的平均消息率生成。", "",
             "| 速率 MB/s | 模式 | 成功 | 小消息 P95 s (均值 ± SD) | 小消息 P99 s | 大消息平均完成 s | 预测 P95 s | 利用率 |",
             "|---:|---|---:|---:|---:|---:|---:|---:|"]
    for rate in (12.5, 25, 50):
        for mode in MODES:
            good = [r for r in rows if r["rate_MBps"] == rate and r["mode"] == mode]
            if len(good) == 10:
                lines.append(f"| {rate} | {mode} | 10/10 | {mean(x['small_p95_s'] for x in good):.4f} ± {stdev(x['small_p95_s'] for x in good):.4f} | {mean(x['small_p99_s'] for x in good):.4f} | {mean(x['large_mean_s'] for x in good):.4f} | {mean(x['predicted_small_p95_s'] for x in good):.4f} | {mean(x['link_utilization'] for x in good):.3f} |")
            else:
                lines.append(f"| {rate} | {mode} | {len(good)}/10 | 不汇总 | 不汇总 | 不汇总 | 不汇总 | 不汇总 |")
    lines += ["", "## 配对差异", "", "仅完整十轮且同一 repeat 配对时，报告相对 priority 的小消息 P95 差异；负值表示更低。"]
    for rate in (12.5, 25, 50):
        baseline = {r["repeat"]: r for r in rows if r["rate_MBps"] == rate and r["mode"] == "priority"}
        for mode in ("fifo", "chunk4", "chunk1", "two_connections"):
            candidate = {r["repeat"]: r for r in rows if r["rate_MBps"] == rate and r["mode"] == mode}
            if len(baseline) != 10 or len(candidate) != 10:
                continue
            diffs = [candidate[i]["small_p95_s"] - baseline[i]["small_p95_s"] for i in range(10)]
            half = T9 * stdev(diffs) / (10 ** .5)
            lines.append(f"- {rate} MB/s {mode} vs priority：{mean(diffs):+.4f} s，95% CI [{mean(diffs)-half:+.4f}, {mean(diffs)+half:+.4f}]。")
    lines += ["", "## 论文可用表述", "", "只可据完整实测组描述单连接顺序发送时的队头阻塞及分块作用；两连接是理想化传输对照。", "预测模型使用相同消息序列，但不包含全部 TCP 拥塞、缓冲和内核调度细节。", "任何外推到真实物理网络或 GPU 系统的说法均超出本实验范围。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    traffic.write(HERE / "FINAL_AUDIT.json", {"passed": len(rows) + len(failures) == 150
                  and not any(x["status"] == "pending" for x in failures),
                  "completed": len(rows), "failed": sum(x["status"] == "failed" for x in failures),
                  "pending": sum(x["status"] == "pending" for x in failures),
                  "manifest_sha256": traffic.sha(traffic.MANIFEST),
                  "traffic_sha256": traffic.sha(traffic.TRAFFIC),
                  "individual_sha256": traffic.sha(HERE / "individual.csv"),
                  "results_sha256": traffic.sha(HERE / "RESULTS_CN.md")})


def run_all(preflight_only=False):
    manifest = traffic.prepare()
    all_traffic = traffic.read(traffic.TRAFFIC)
    namespace, device = setup()
    try:
        command(["tc", "qdisc", "replace", "dev", device, "root", "netem", "delay", "25ms", "rate", "100mbit"])
        qdisc_bytes(device)
        if preflight_only:
            print("PREFLIGHT_OK", namespace, device, os.uname().release, flush=True)
            return
        for rate in manifest["bandwidth_MBps"]:
            command(["tc", "qdisc", "replace", "dev", device, "root", "netem", "delay", "25ms",
                     "rate", f"{rate * 8:g}mbit"])
            for repetition in all_traffic["repetitions"]:
                for mode in MODES:
                    outcome = run_one(rate, mode, repetition, namespace, device, all_traffic, manifest)
                    print(rate, repetition["repeat"], mode, outcome, flush=True)
        report(all_traffic)
    finally:
        teardown(namespace, device)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--receiver-output", type=Path)
    parser.add_argument("--expected-small", type=int)
    parser.add_argument("--expected-large", type=int)
    parser.add_argument("--connections", type=int)
    args = parser.parse_args()
    if args.server:
        server(args.receiver_output, args.expected_small, args.expected_large, args.connections)
    elif args.prepare:
        print(traffic.prepare()["traffic_sha256"])
    elif args.preflight:
        run_all(preflight_only=True)
    elif args.run:
        run_all()
    elif args.report:
        traffic.prepare()
        report(traffic.read(traffic.TRAFFIC))
    else:
        parser.error("choose --prepare, --preflight, --run, --report, or --server")
