#!/usr/bin/env python3
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://localhost:8080"


def make_request(url: str, method: str = "GET", payload: dict = None, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_health(base_url: str) -> dict:
    return make_request(f"{base_url}/api/health", method="GET", timeout=5)


def get_stats(base_url: str) -> dict:
    return make_request(f"{base_url}/api/stats", method="GET", timeout=5)


def build_index(base_url: str, threads: int) -> dict:
    return make_request(f"{base_url}/api/index", method="POST", payload={"threads": threads}, timeout=600)


def show_status(base_url: str):
    print(f"Checking server status ({base_url})...")
    try:
        health = get_health(base_url)
        ollama_status = "Ready" if health.get("ollama") else "Disabled / unreachable"
        print("  Server: Online")
        print(f"  Ollama (LLM): {ollama_status}")
    except Exception as e:
        print(f"  [ERROR] Server unreachable: {e}")
        return False

    try:
        stats = get_stats(base_url)
        docs = stats.get("documents", 0)
        time_ms = stats.get("index_build_time_ms", 0)
        threads = stats.get("threads_used", 0)
        time_s = time_ms / 1000.0

        if docs > 0:
            print(f"  Index: Built ({docs:,} documents)")
            print(f"  Last build time: {time_ms} ms ({time_s:.2f} s)")
            print(f"  Worker threads used: {threads}")
        else:
            print("  Index: Empty (0 documents). Build required.")
    except Exception as e:
        print(f"  [ERROR] Failed to retrieve statistics: {e}")
        return False

    return True


def run_single_build(base_url: str, threads: int, force: bool = False):
    print(f"Connecting to {base_url}...")
    try:
        get_health(base_url)
    except Exception as e:
        print(f"[ERROR] Server unreachable at {base_url}: {e}", file=sys.stderr)
        return 1

    if not force:
        try:
            stats = get_stats(base_url)
            docs = stats.get("documents", 0)
            if docs > 0:
                print(f"Warning: Index is already built ({docs:,} documents).")
                ans = input(f"Rebuild index with {threads} threads? [y/N]: ").strip().lower()
                if ans not in ("y", "yes"):
                    print("Cancelled by user.")
                    return 0
        except Exception:
            pass

    print(f"\nStarting index build with {threads} threads...")
    start_time = time.time()
    try:
        result = build_index(base_url, threads)
    except Exception as e:
        print(f"\n[ERROR] Failed to build index: {e}", file=sys.stderr)
        return 1

    elapsed_wall = time.time() - start_time
    docs = result.get("documents_indexed", 0)
    server_ms = result.get("time_ms", 0)
    server_s = server_ms / 1000.0

    print(f"\n[SUCCESS] Index built successfully!")
    print(f"  Documents indexed : {docs:,}")
    print(f"  Worker threads    : {threads}")
    print(f"  Server build time : {server_ms} ms ({server_s:.2f} s)")
    print(f"  Total wall time   : {elapsed_wall:.2f} s")
    return 0


def run_benchmark(base_url: str, thread_list: list[int], output_file: str = None):
    if 1 not in thread_list:
        print("[INFO] Thread 1 was automatically prepended to measure baseline execution time (T1) for Speedup calculation.")
        thread_list = [1] + [t for t in thread_list if t != 1]
    print(f"Checking server availability ({base_url})...")
    try:
        get_health(base_url)
    except Exception as e:
        print(f"[ERROR] Server unreachable at {base_url}: {e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 65)
    print("           INDEX BUILD SPEED BENCHMARK")
    print(f"  Threads test list: {thread_list}")
    print("=" * 65 + "\n")

    results = []
    base_time_s = None

    for idx, t in enumerate(thread_list, start=1):
        print(f"[{idx}/{len(thread_list)}] Building with {t} threads... ", end="", flush=True)
        t_start = time.time()
        try:
            res = build_index(base_url, t)
            t_elapsed = time.time() - t_start
            docs = res.get("documents_indexed", 0)
            time_ms = res.get("time_ms", int(t_elapsed * 1000))
            time_s = time_ms / 1000.0

            if t == 1:
                base_time_s = time_s

            results.append({
                "run": idx,
                "threads": t,
                "docs": docs,
                "time_ms": time_ms,
                "time_s": time_s,
            })
            print(f"DONE: {time_ms} ms ({time_s:.2f} s) | {docs:,} docs")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "run": idx,
                "threads": t,
                "docs": 0,
                "time_ms": -1,
                "time_s": -1,
            })

    if base_time_s is None and results and results[0]["time_s"] > 0:
        base_time_s = results[0]["time_s"]

    print("\n" + "=" * 70)
    print("                     BENCHMARK SUMMARY TABLE")
    print("=" * 70)
    print(f"{'#':<3} | {'Threads':<7} | {'Documents':<12} | {'Time (ms)':<10} | {'Time (s)':<10} | {'Speedup':<12}")
    print("-" * 70)

    for item in results:
        if item["time_s"] < 0:
            print(f"{item['run']:<3} | {item['threads']:<7} | {'ERROR':<12} | {'-':<10} | {'-':<10} | {'-':<12}")
            continue

        speedup_str = "-"
        if base_time_s and base_time_s > 0 and item["time_s"] > 0:
            sp = base_time_s / item["time_s"]
            speedup_str = f"{sp:.2f}x"
            if item["threads"] == 1:
                speedup_str += " (base)"

        print(f"{item['run']:<3} | {item['threads']:<7} | {item['docs']:<12,}"
              f" | {item['time_ms']:<10} | {item['time_s']:<9.2f} s | {speedup_str:<12}")

    print("=" * 70)

    if output_file:
        try:
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Threads", "Documents", "Time_ms", "Time_s", "Speedup"])
                for item in results:
                    if item["time_s"] > 0:
                        sp = (base_time_s / item["time_s"]) if base_time_s else 1.0
                        writer.writerow([item["threads"], item["docs"], item["time_ms"], f"{item['time_s']:.2f}", f"{sp:.2f}"])
            print(f"\n[INFO] Benchmark results saved to: {output_file}")
        except Exception as e:
            print(f"\n[WARNING] Failed to save CSV: {e}")

    return 0


def parse_thread_args(val: str) -> list[int]:
    threads = []
    for part in val.replace(",", " ").split():
        if part.strip().isdigit() and int(part.strip()) > 0:
            threads.append(int(part.strip()))
    if not threads:
        raise argparse.ArgumentTypeError("Provide at least one thread count > 0 (e.g., 1,2,4,8)")
    return threads


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="CLI client for building and benchmarking the inverted index"
    )
    parser.add_argument(
        "--threads", "-t",
        type=int,
        default=8,
        help="Number of worker threads for single build (default: 8)"
    )
    parser.add_argument(
        "--benchmark", "-b",
        nargs="*",
        help="Run batch benchmark for specified threads (e.g., --benchmark 1 2 4 8 12 16)"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Check server status and existing index status"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Rebuild index without confirmation if it already exists"
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"Base search server URL (default: {DEFAULT_BASE_URL})"
    )
    parser.add_argument(
        "--output", "-o",
        help="Path to CSV file to export benchmark results"
    )

    args = parser.parse_args()

    if args.status:
        return 0 if show_status(args.url) else 1

    if args.benchmark is not None:
        if len(args.benchmark) == 0:
            thread_list = [1, 2, 4, 8, 12, 16]
        else:
            thread_list = []
            for item in args.benchmark:
                thread_list.extend(parse_thread_args(item))
        return run_benchmark(args.url, thread_list, args.output)

    return run_single_build(args.url, args.threads, args.force)


if __name__ == "__main__":
    sys.exit(main())
