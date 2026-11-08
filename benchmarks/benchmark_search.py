#!/usr/bin/env python3
import argparse
import csv
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import requests

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

DEFAULT_SAMPLE_QUERIES = [
    "scented candle",
    "essential oil",
    "laundry detergent",
    "aromatherapy diffuser",
    "hand soap",
    "organic shampoo",
    "air freshener",
    "massage oil",
    "soy candle",
    "paper towels",
    "cleaning spray",
    "vitamins supplement",
    "bath salts",
    "body wash",
    "herbal tea"
]


def load_queries(custom_path=None):
    candidates = []
    if custom_path:
        candidates.append(custom_path)
    default_file = os.path.join(os.path.dirname(__file__), "queries.txt")
    candidates.append(default_file)

    for path in candidates:
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    if lines:
                        return lines, path
            except Exception:
                pass
    return DEFAULT_SAMPLE_QUERIES, "built-in default list"


SAMPLE_QUERIES, _ = load_queries()


def check_server(base_url):
    try:
        health_resp = requests.get(f"{base_url}/health", timeout=3)
        if health_resp.status_code != 200:
            return False, "Server /api/health returned non-200"
        stats_resp = requests.get(f"{base_url}/stats", timeout=3)
        docs = stats_resp.json().get("documents", 0)
        return True, docs
    except Exception as exc:
        return False, str(exc)


def resolve_clients(range_args: list[int] | None, step_arg: int | None, clients_args: list[int] | None) -> list[int]:
    if range_args:
        if len(range_args) == 1:
            min_c = 1
            max_c = range_args[0]
            step = step_arg or (5 if max_c <= 50 else 10)
        elif len(range_args) == 2:
            min_c = range_args[0]
            max_c = range_args[1]
            step = step_arg or (5 if max_c <= 50 else 10)
        else:
            min_c = range_args[0]
            max_c = range_args[1]
            step = range_args[2]

        if min_c > max_c:
            min_c, max_c = max_c, min_c

        if step <= 0:
            step = 1

        points = []
        if min_c == 1 and step > 1:
            points.append(1)
            curr = step
            while curr <= max_c:
                points.append(curr)
                curr += step
            if points[-1] < max_c:
                points.append(max_c)
        else:
            curr = min_c
            while curr <= max_c:
                points.append(curr)
                curr += step
            if points[-1] < max_c:
                points.append(max_c)

        return sorted(list(set(points)))

    if clients_args:
        pts = []
        for item in clients_args:
            if isinstance(item, int):
                if item > 0:
                    pts.append(item)
            else:
                for part in str(item).replace(",", " ").split():
                    if part.strip().isdigit() and int(part.strip()) > 0:
                        pts.append(int(part.strip()))
        return sorted(list(set(pts))) if pts else [1, 5, 10, 20, 30, 50, 75, 100]

    return [1, 5, 10, 20, 30, 50, 75, 100]


def run_load_step(search_url, concurrency, duration_sec, warmup_sec, mode="keyword", queries=None):
    if not queries:
        queries = SAMPLE_QUERIES
    stop_event = Event()
    latencies = []
    success_count = 0
    failure_count = 0
    req_timeout = 20 if mode == "expanded" else 5

    def worker():
        nonlocal success_count, failure_count
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=concurrency, pool_maxsize=concurrency)
        session.mount("http://", adapter)

        while not stop_event.is_set():
            query = random.choice(queries)
            payload = {"query": query, "mode": mode, "top": 5}
            t0 = time.perf_counter()
            try:
                resp = session.post(search_url, json=payload, timeout=req_timeout)
                t1 = time.perf_counter()
                if resp.status_code == 200:
                    latencies.append((t1 - t0) * 1000.0)
                    success_count += 1
                else:
                    failure_count += 1
            except Exception:
                failure_count += 1

    if warmup_sec > 0:
        warmup_stop = Event()

        def warmup_worker():
            s = requests.Session()
            while not warmup_stop.is_set():
                try:
                    s.post(search_url, json={"query": "candle", "mode": mode, "top": 5}, timeout=req_timeout)
                except Exception:
                    pass

        with ThreadPoolExecutor(max_workers=min(concurrency, 4)) as pool:
            for _ in range(min(concurrency, 4)):
                pool.submit(warmup_worker)
            time.sleep(warmup_sec)
            warmup_stop.set()

    latencies.clear()
    success_count = 0
    failure_count = 0

    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for _ in range(concurrency):
            executor.submit(worker)
        time.sleep(duration_sec)
        stop_event.set()

    elapsed = time.perf_counter() - start_time
    total = success_count + failure_count
    rps = success_count / elapsed if elapsed > 0 else 0.0

    latencies.sort()
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

    return {
        "clients": concurrency,
        "total_requests": total,
        "success_requests": success_count,
        "failed_requests": failure_count,
        "duration_sec": elapsed,
        "rps": rps,
        "avg_lat_ms": avg_lat,
        "p50_lat_ms": p50,
        "p95_lat_ms": p95,
        "p99_lat_ms": p99,
    }


def print_summary_table(results: list[dict], mode: str):
    print("\n" + "=" * 92)
    print(f"               SEARCH BENCHMARK SUMMARY TABLE ({mode.upper()})")
    print("=" * 92)
    print(f"{'#':<3} | {'Clients':<8} | {'Requests':<10} | {'RPS':<10} | {'Avg Lat':<12} | {'P50':<10} | {'P95':<10} | {'Errors':<7}")
    print("-" * 92)
    for idx, r in enumerate(results, start=1):
        print(f"{idx:<3} | {r['clients']:<8} | {r['total_requests']:<10,} | {r['rps']:<10.1f} | "
              f"{r['avg_lat_ms']:>8.2f} ms | {r['p50_lat_ms']:>6.2f} ms | {r['p95_lat_ms']:>6.2f} ms | {r['failed_requests']:<7}")
    print("=" * 92 + "\n")


def save_csv(results, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["clients", "rps", "avg_lat_ms", "p50_lat_ms", "p95_lat_ms", "p99_lat_ms", "total_requests", "failed_requests"])
        for r in results:
            writer.writerow([
                r["clients"],
                f"{r['rps']:.2f}",
                f"{r['avg_lat_ms']:.2f}",
                f"{r['p50_lat_ms']:.2f}",
                f"{r['p95_lat_ms']:.2f}",
                f"{r['p99_lat_ms']:.2f}",
                r["total_requests"],
                r["failed_requests"]
            ])


def load_csv(path):
    if not os.path.exists(path):
        print(f"[ERROR] CSV file not found: {path}", file=sys.stderr)
        sys.exit(1)
    results = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                results.append({
                    "clients": int(row["clients"]),
                    "rps": float(row["rps"]),
                    "avg_lat_ms": float(row["avg_lat_ms"]),
                    "p50_lat_ms": float(row["p50_lat_ms"]),
                    "p95_lat_ms": float(row["p95_lat_ms"]),
                    "p99_lat_ms": float(row.get("p99_lat_ms", 0.0)),
                    "total_requests": int(float(row.get("total_requests", 0))),
                    "failed_requests": int(float(row.get("failed_requests", 0))),
                })
            except (ValueError, KeyError):
                continue
    return results


def plot_results(results, path):
    if not HAS_MATPLOTLIB:
        print("[WARN] matplotlib not installed; skipping plot generation.")
        return

    out_dir = os.path.dirname(os.path.abspath(path)) if path.endswith(".png") else os.path.abspath(path)
    os.makedirs(out_dir, exist_ok=True)

    unique_map = {}
    for r in results:
        c = int(r["clients"])
        if c not in unique_map:
            unique_map[c] = []
        unique_map[c].append(r)

    sorted_clients = sorted(unique_map.keys())
    clients = []
    rps = []
    avg_lat = []
    p95_lat = []

    for c in sorted_clients:
        items = unique_map[c]
        clients.append(c)
        rps.append(sum(i["rps"] for i in items) / len(items))
        avg_lat.append(sum(i["avg_lat_ms"] for i in items) / len(items))
        p95_lat.append(sum(i["p95_lat_ms"] for i in items) / len(items))

    max_c = max(clients) if clients else 100
    if max_c <= 20:
        step = 2
    elif max_c <= 50:
        step = 5
    elif max_c <= 100:
        step = 10
    elif max_c <= 250:
        step = 20
    else:
        step = 50

    ticks = list(range(0, max_c + 1, step))
    if ticks[-1] < max_c:
        ticks.append(max_c)

    throughput_path = os.path.join(out_dir, "search_throughput.png")
    fig, ax1 = plt.subplots(figsize=(10, 5.5))
    ax1.plot(clients, rps, marker="o", markersize=5, color="#2563eb", linewidth=2.0, label="Throughput (RPS)")
    ax1.set_ylabel("Throughput (requests/sec)", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Number of Concurrent Clients", fontsize=11, fontweight="bold")
    ax1.set_title("Search Scalability: Throughput vs Concurrent Clients", fontsize=12, fontweight="bold", pad=12)
    ax1.set_xticks(ticks)
    ax1.set_xlim(0, max_c * 1.02)
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(throughput_path, dpi=300)
    plt.close()
    print(f"[OK] Throughput plot saved to: {throughput_path}")

    latency_path = os.path.join(out_dir, "search_latency.png")
    fig, ax2 = plt.subplots(figsize=(10, 5.5))
    ax2.plot(clients, avg_lat, marker="s", markersize=5, color="#16a34a", linewidth=2.0, label="Average Latency (ms)")
    ax2.plot(clients, p95_lat, marker="^", markersize=5, color="#ea580c", linewidth=2.0, linestyle="--", label="95th Percentile (ms)")
    ax2.set_xlabel("Number of Concurrent Clients", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Latency (ms)", fontsize=11, fontweight="bold")
    ax2.set_title("Search Scalability: Latency vs Concurrent Clients", fontsize=12, fontweight="bold", pad=12)
    ax2.set_xticks(ticks)
    ax2.set_xlim(0, max_c * 1.02)
    ax2.grid(True, linestyle="--", alpha=0.6)
    ax2.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(latency_path, dpi=300)
    plt.close()
    print(f"[OK] Latency plot saved to: {latency_path}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Full-featured search scalability & load benchmark runner"
    )
    parser.add_argument(
        "--range",
        nargs="+",
        type=int,
        metavar=("MIN", "MAX"),
        help="Client range as: MIN MAX [STEP] (e.g. --range 1 50 or --range 10 100 10)"
    )
    parser.add_argument(
        "--step", "-s",
        type=int,
        help="Step size for client range increments"
    )
    parser.add_argument(
        "--clients", "-c",
        nargs="+",
        help="Explicit list of concurrent client levels (e.g. -c 1 5 10 20 30 50 75 100)"
    )
    parser.add_argument(
        "--duration", "-d", "--time",
        type=int,
        default=10,
        help="Test duration per concurrency level in seconds (default: 10)"
    )
    parser.add_argument(
        "--warmup", "-w",
        type=int,
        default=2,
        help="Warmup duration in seconds before measurement (default: 2)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["keyword", "expanded"],
        default="keyword",
        help="Search mode: 'keyword' (fast index lookup) or 'expanded' (Query Expansion via Ollama)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8080/api/search",
        help="Target search endpoint (default: http://localhost:8080/api/search)"
    )
    parser.add_argument(
        "--queries", "-q",
        default=None,
        help="Path to external .txt file with search queries (default: benchmarks/queries.txt)"
    )
    parser.add_argument(
        "--from-csv",
        help="Re-generate plots and summary from an existing CSV without running benchmarks"
    )
    parser.add_argument(
        "--output-csv", "--csv",
        default="benchmarks/results/search_scalability.csv",
        help="CSV output path (default: benchmarks/results/search_scalability.csv)"
    )
    parser.add_argument(
        "--output-plot", "--output-dir",
        default="docs/benchmarks/search_throughput.png",
        help="Output directory or plot path (default: docs/benchmarks/search_throughput.png)"
    )

    args = parser.parse_args()

    mode = args.mode.lower()

    if args.from_csv:
        print(f"Loading search benchmark data from: {args.from_csv}")
        results = load_csv(args.from_csv)
        print_summary_table(results, mode)
        plot_results(results, args.output_plot)
        return

    queries, queries_source = load_queries(args.queries)

    api_base = args.url.rsplit("/", 1)[0]
    ok, info = check_server(api_base)
    if not ok:
        print(f"[ERROR] Cannot connect to search server at {api_base}: {info}", file=sys.stderr)
        sys.exit(1)

    doc_count = info
    print(f"[INFO] Server is online. Indexed documents: {doc_count:,}")
    if doc_count == 0:
        print("[WARN] Index is empty! Search results may not reflect realistic load.", file=sys.stderr)

    client_list = resolve_clients(args.range, args.step, args.clients)

    print(f"[INFO] Loaded {len(queries)} sample queries from: {queries_source}")
    print(f"[INFO] Starting load test on: {args.url}")
    print(f"[INFO] Mode: {mode.upper()} | Client levels: {client_list} ({len(client_list)} points)")
    print(f"[INFO] Duration per level: {args.duration}s | Warmup: {args.warmup}s")
    print("-" * 88)

    results = []
    total_steps = len(client_list)

    for idx, c in enumerate(client_list, start=1):
        print(f"[{idx}/{total_steps}] Testing with {c} clients (duration: {args.duration}s)... ", end="", flush=True)
        res = run_load_step(args.url, c, args.duration, args.warmup, mode=mode, queries=queries)
        results.append(res)
        print(f"DONE: {res['rps']:.1f} RPS | avg: {res['avg_lat_ms']:.2f}ms | P95: {res['p95_lat_ms']:.2f}ms | errors: {res['failed_requests']}")

    print_summary_table(results, mode)

    save_csv(results, args.output_csv)
    print(f"[OK] CSV results saved to: {args.output_csv}")

    plot_results(results, args.output_plot)


if __name__ == "__main__":
    main()
