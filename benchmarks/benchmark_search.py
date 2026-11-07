import argparse
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

def run_load_step(search_url, concurrency, duration_sec, warmup_sec, mode="keyword", queries=None):
    if not queries:
        queries = SAMPLE_QUERIES
    stop_event = Event()
    latencies = []
    success_count = 0
    failure_count = 0
    req_timeout = 15 if mode == "expanded" else 5

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

def save_csv(results, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("clients,rps,avg_lat_ms,p50_lat_ms,p95_lat_ms,p99_lat_ms,total_requests,failed_requests\n")
        for r in results:
            f.write(f"{r['clients']},{r['rps']:.2f},{r['avg_lat_ms']:.2f},{r['p50_lat_ms']:.2f},"
                    f"{r['p95_lat_ms']:.2f},{r['p99_lat_ms']:.2f},{r['total_requests']},{r['failed_requests']}\n")

def plot_results(results, path):
    if not HAS_MATPLOTLIB:
        print("[WARN] matplotlib not installed; skipping plot generation.")
        return

    out_dir = os.path.dirname(os.path.abspath(path)) if path.endswith(".png") else os.path.abspath(path)
    os.makedirs(out_dir, exist_ok=True)

    # Deduplicate and sort by client count
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
    elif max_c <= 500:
        step = 50
    else:
        step = 100

    ticks = list(range(0, max_c + 1, step))
    if ticks[-1] < max_c:
        ticks.append(max_c)

    throughput_path = os.path.join(out_dir, "search_throughput.png")
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(clients, rps, marker="o", markersize=4.5, color="#2563eb", linewidth=1.8, label="Throughput (RPS)")
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
    fig, ax2 = plt.subplots(figsize=(10, 5))
    ax2.plot(clients, avg_lat, marker="s", markersize=4.5, color="#16a34a", linewidth=1.8, label="Average Latency (ms)")
    ax2.plot(clients, p95_lat, marker="^", markersize=4.5, color="#ea580c", linewidth=1.8, linestyle="--", label="95th Percentile (ms)")
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
    parser = argparse.ArgumentParser(description="Search Scalability & Load Benchmark")
    parser.add_argument("--url", default="http://localhost:8080/api/search", help="Target search endpoint")
    parser.add_argument("--clients", nargs="+", type=int, default=[1, 5, 10, 20, 30, 50, 75],
                        help="List of concurrent client levels")
    parser.add_argument("--duration", type=int, default=10, help="Test duration per level (seconds)")
    parser.add_argument("--warmup", type=int, default=2, help="Warmup duration (seconds)")
    parser.add_argument("--mode", "-m", choices=["keyword", "expanded"], default="keyword",
                        help="Search mode: 'keyword' (fast direct index lookup) or 'expanded' (AI Query Expansion via Ollama)")
    parser.add_argument("--queries", "-q", default=None,
                        help="Path to external .txt file with search queries (default: benchmarks/queries.txt)")
    parser.add_argument("--output-csv", default="benchmarks/results/search_scalability.csv", help="CSV output path")
    parser.add_argument("--output-plot", default="docs/benchmarks/search_throughput.png", help="Plot PNG output path")
    args = parser.parse_args()

    mode = args.mode.lower()
    queries, queries_source = load_queries(args.queries)

    api_base = args.url.rsplit("/", 1)[0]
    ok, info = check_server(api_base)
    if not ok:
        print(f"[ERROR] Cannot connect to search server at {api_base}: {info}")
        sys.exit(1)

    doc_count = info
    print(f"[INFO] Server is online. Indexed documents: {doc_count:,}")
    if doc_count == 0:
        print("[WARN] Index is empty! Search results may not reflect realistic load.")

    print(f"[INFO] Loaded {len(queries)} sample queries from: {queries_source}")
    print(f"[INFO] Starting load test on {args.url}")
    print(f"[INFO] Mode: {mode.upper()} | Levels: {args.clients} | Duration per step: {args.duration}s | Warmup: {args.warmup}s")
    print("-" * 85)
    print(f"{'Clients':>8} | {'Requests':>10} | {'RPS':>10} | {'Avg Lat':>10} | {'P50':>8} | {'P95':>8} | {'P99':>8} | {'Errors':>7}")
    print("-" * 85)

    results = []
    for c in args.clients:
        res = run_load_step(args.url, c, args.duration, args.warmup, mode=mode, queries=queries)
        results.append(res)
        print(f"{res['clients']:>8} | {res['total_requests']:>10} | {res['rps']:>10.1f} | "
              f"{res['avg_lat_ms']:>8.2f}ms | {res['p50_lat_ms']:>6.2f}ms | {res['p95_lat_ms']:>6.2f}ms | "
              f"{res['p99_lat_ms']:>6.2f}ms | {res['failed_requests']:>7}")

    print("-" * 85)
    save_csv(results, args.output_csv)
    print(f"[OK] CSV results saved to: {args.output_csv}")
    plot_results(results, args.output_plot)

if __name__ == "__main__":
    main()
