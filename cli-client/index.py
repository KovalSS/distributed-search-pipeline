#!/usr/bin/env python3
import argparse
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


def show_status(base_url: str) -> bool:
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


def run_single_build(base_url: str, threads: int) -> int:
    print(f"Connecting to {base_url}...")
    try:
        get_health(base_url)
    except Exception as e:
        print(f"[ERROR] Server unreachable at {base_url}: {e}", file=sys.stderr)
        return 1

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


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="CLI client for building and inspecting the search index"
    )
    parser.add_argument(
        "--threads", "-t",
        type=int,
        default=8,
        help="Number of worker threads for index build (default: 8)"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Check server status and existing index status"
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"Base search server URL (default: {DEFAULT_BASE_URL})"
    )
    parser.add_argument(
        "--benchmark", "-b",
        nargs="*",
        help=argparse.SUPPRESS
    )

    args = parser.parse_args()

    if args.benchmark is not None:
        print("[INFO] Benchmarking functionality is now in: benchmarks/benchmark_index.py")
        print("Run the dedicated benchmark tool:")
        print("  python benchmarks/benchmark_index.py --range 1 32 --runs 3")
        return 0

    if args.status:
        return 0 if show_status(args.url) else 1

    return run_single_build(args.url, args.threads)


if __name__ == "__main__":
    sys.exit(main())
