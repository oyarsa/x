#!/usr/bin/env python3
# pyright: strict
import argparse
import re
import socket
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime

BAR_W = 30

reply_re = re.compile(r"icmp_seq=(\d+).*time=([\d.]+)")
summary_re = re.compile(r"(\d+) packets transmitted, (\d+) (?:packets )?received")


@dataclass
class Stats:
    """Running totals across all batches, updated live so a mid-batch
    Ctrl-C still leaves accurate partial data behind."""

    times: list[float] = field(default_factory=list[float])
    sent: int = 0
    received: int = 0


def fmt_bar(done: int, total: int, loss: float) -> str:
    # color by loss: green<1%, yellow<5%, red otherwise
    color = "\033[32m" if loss < 1 else "\033[33m" if loss < 5 else "\033[31m"
    filled = int(BAR_W * done / total)
    return f"{color}{'█' * filled}{'░' * (BAR_W - filled)}\033[0m"


def run_batch(n: int, host: str, count: int, interval: float, agg: Stats) -> None:
    proc = subprocess.Popen(
        ["ping", "-c", str(count), "-i", str(interval), host],
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None

    ts = datetime.now().strftime("%H:%M:%S")
    cw = len(str(count))  # pad the reply count so x/y columns line up
    times: list[float] = []
    received = 0
    sent = 0
    recv_final = None
    transmitted = None

    for line in proc.stdout:
        if m := reply_re.search(line):
            received += 1
            prev_sent = sent
            sent = int(m.group(1)) + 1
            times.append(float(m.group(2)))

            # mirror into the global aggregate live, so Ctrl-C mid-batch
            # still counts this reply
            agg.times.append(float(m.group(2)))
            agg.received += 1
            agg.sent += sent - prev_sent

            # live bar (rough progress; ping's own summary is authoritative below)
            loss = 100 * (sent - received) / sent if sent else 0
            bar = fmt_bar(sent, count, loss)
            avg = statistics.mean(times) if times else 0

            # \r overwrites the *current* line only
            sys.stdout.write(
                f"\r{ts} #{n:>3} {bar} {received:>{cw}}/{count}  loss {loss:4.1f}%  avg {avg:6.2f}ms"
            )
            sys.stdout.flush()

            continue

        if s := summary_re.search(line):
            transmitted = int(s.group(1))
            recv_final = int(s.group(2))

    proc.wait()

    # trailing packets that were lost produce no reply line, so the live
    # agg.sent undercounts them; reconcile with ping's authoritative total
    if transmitted is not None and transmitted > sent:
        agg.sent += transmitted - sent

    # use ping's authoritative count for loss; keep parsed times for latency stats
    if transmitted and recv_final is not None:
        loss = 100 * (transmitted - recv_final) / transmitted
    else:
        loss = 100 * (count - len(times)) / count  # fallback

    # finalise this line, then newline so the next batch starts fresh
    if times:
        stats = (
            f"loss {loss:4.1f}%  "
            f"min {min(times):.2f}  "
            f"med {statistics.median(times):.2f}  "
            f"avg {statistics.mean(times):.2f}  "
            f"max {max(times):.2f}  "
            f"std {statistics.pstdev(times):.2f}"
        )
    else:
        stats = "loss 100.0%  (no replies)"

    sys.stdout.write(
        f"\r{ts} #{n:>3} {fmt_bar(count, count, loss)} {recv_final or len(times):>{cw}}/{count}  {stats}\n"
    )
    sys.stdout.flush()


def print_overall(agg: Stats) -> None:
    if agg.sent == 0:
        return

    loss = 100 * (agg.sent - agg.received) / agg.sent
    print("─" * 50)

    if agg.times:
        print(
            f"overall: {agg.received}/{agg.sent} replies  "
            f"loss {loss:.1f}%  "
            f"min {min(agg.times):.2f}  "
            f"med {statistics.median(agg.times):.2f}  "
            f"avg {statistics.mean(agg.times):.2f}  "
            f"max {max(agg.times):.2f}  "
            f"std {statistics.pstdev(agg.times):.2f}"
        )
    else:
        print(f"overall: {agg.received}/{agg.sent} replies  loss {loss:.1f}%  (no replies)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ping a host in batches, showing per-batch latency stats."
    )
    parser.add_argument("host", help="host to ping")
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=100,
        help="number of pings per loop (default: 100)",
    )
    parser.add_argument(
        "-l",
        "--loops",
        type=int,
        default=0,
        help="number of loops (default: 0 = forever)",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=0.2,
        help="seconds between pings (default: 0.2)",
    )
    args = parser.parse_args()

    # resolve once up front so a bad hostname fails fast instead of
    # busy-spinning the loop (ping exits instantly on resolve failure)
    try:
        socket.getaddrinfo(args.host, None)
    except socket.gaierror as e:
        sys.exit(f"cannot resolve {args.host!r}: {e}")

    agg = Stats()
    n = 1
    try:
        while args.loops == 0 or n <= args.loops:
            run_batch(n, args.host, args.count, args.interval, agg)
            n += 1
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        print_overall(agg)


if __name__ == "__main__":
    main()
