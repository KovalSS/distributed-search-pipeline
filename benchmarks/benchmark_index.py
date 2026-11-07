#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_CSV_PATH = "benchmarks/results/index_speedup.csv"
DEFAULT_DOCS_DIR = "docs/benchmarks"


def make_request(url: str, method: str = "GET", payload: dict = None, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_health(base_url: str) -> bool:
    try:
        data = make_request(f"{base_url}/api/health", method="GET", timeout=5)
        return data.get("status") == "ok"
    except Exception:
        return False


def build_index(base_url: str, threads: int) -> dict:
    return make_request(f"{base_url}/api/index", method="POST", payload={"threads": threads}, timeout=600)


def resolve_threads(range_args: list[int] | None, thread_args: list[str] | None) -> list[int]:
    threads = []
    if range_args:
        if len(range_args) == 1:
            threads = list(range(1, range_args[0] + 1))
        elif len(range_args) == 2:
            threads = list(range(range_args[0], range_args[1] + 1))
        elif len(range_args) >= 3:
            threads = list(range(range_args[0], range_args[1] + 1, range_args[2]))
    elif thread_args:
        for item in thread_args:
            for part in str(item).replace(",", " ").split():
                if part.strip().isdigit() and int(part.strip()) > 0:
                    threads.append(int(part.strip()))
    else:
        threads = [1, 2, 4, 8, 12, 16, 20, 24, 28, 32]

    threads = sorted(list(set(threads)))
    if 1 not in threads:
        print("[INFO] Thread 1 automatically prepended as the baseline (T1) for speedup calculations.")
        threads = [1] + threads
    return threads


def run_benchmark(base_url: str, thread_list: list[int], runs: int) -> list[dict]:
    if not check_health(base_url):
        print(f"[ERROR] Search server unreachable at {base_url}. Ensure Docker container is running.", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 78)
    print("             PARALLEL INDEXING SCALABILITY BENCHMARK")
    print(f"  Target Server : {base_url}")
    print(f"  Thread Points : {thread_list} ({len(thread_list)} test points)")
    print(f"  Runs per Point: {runs}{' (with statistical averaging)' if runs > 1 else ''}")
    print("=" * 78 + "\n")

    results = []
    total_points = len(thread_list)

    for p_idx, t in enumerate(thread_list, start=1):
        thread_runs_ms = []
        docs_indexed = 0

        for r in range(1, runs + 1):
            if runs > 1:
                progress = f"[{r}/{runs}] [{p_idx}/{total_points}]"
            else:
                progress = f"[{p_idx}/{total_points}]"

            print(f"{progress} Building with {t} threads... ", end="", flush=True)
            t_start = time.time()
            try:
                res = build_index(base_url, t)
                elapsed_wall = time.time() - t_start
                docs = res.get("documents_indexed", 0)
                server_ms = res.get("time_ms", int(elapsed_wall * 1000))
                time_s = server_ms / 1000.0
                thread_runs_ms.append(server_ms)
                docs_indexed = docs
                print(f"DONE: {server_ms} ms ({time_s:.2f} s) | {docs:,} docs")
            except Exception as e:
                print(f"ERROR: {e}")
                break

        if not thread_runs_ms:
            continue

        avg_ms = sum(thread_runs_ms) / len(thread_runs_ms)
        avg_s = avg_ms / 1000.0
        min_s = min(thread_runs_ms) / 1000.0
        max_s = max(thread_runs_ms) / 1000.0

        if runs > 1:
            print(f"   ↳ Average for {t} threads: {avg_ms:.1f} ms ({avg_s:.2f} s) [min: {min_s:.2f} s, max: {max_s:.2f} s]\n")

        results.append({
            "threads": t,
            "docs": docs_indexed,
            "runs": len(thread_runs_ms),
            "avg_ms": avg_ms,
            "avg_s": avg_s,
            "min_s": min_s,
            "max_s": max_s,
            "raw_ms": thread_runs_ms
        })

    return results


def print_summary_table(results: list[dict], runs: int) -> float:
    t1_item = next((item for item in results if item["threads"] == 1), None)
    base_time_s = t1_item["avg_s"] if t1_item and t1_item["avg_s"] > 0 else (results[0]["avg_s"] if results else 1.0)

    for item in results:
        item["speedup"] = (base_time_s / item["avg_s"]) if item["avg_s"] > 0 else 1.0

    print("\n" + "=" * 78)
    print("                     BENCHMARK SUMMARY TABLE")
    print("=" * 78)

    if runs > 1:
        print(f"{'#':<3} | {'Threads':<7} | {'Documents':<11} | {'Avg (ms)':<9} | {'Avg (s)':<8} | {'Min (s)':<8} | {'Max (s)':<8} | {'Speedup':<10}")
        print("-" * 78)
        for idx, item in enumerate(results, start=1):
            sp_str = f"{item['speedup']:.2f}x"
            if item["threads"] == 1:
                sp_str += " (base)"
            print(f"{idx:<3} | {item['threads']:<7} | {item['docs']:<11,} | {item['avg_ms']:<9.1f} | {item['avg_s']:<8.2f} | {item['min_s']:<8.2f} | {item['max_s']:<8.2f} | {sp_str:<10}")
    else:
        print(f"{'#':<3} | {'Threads':<7} | {'Documents':<11} | {'Time (ms)':<10} | {'Time (s)':<9} | {'Speedup':<12}")
        print("-" * 78)
        for idx, item in enumerate(results, start=1):
            sp_str = f"{item['speedup']:.2f}x"
            if item["threads"] == 1:
                sp_str += " (base)"
            print(f"{idx:<3} | {item['threads']:<7} | {item['docs']:<11,} | {int(item['avg_ms']):<10} | {item['avg_s']:<9.2f} | {sp_str:<12}")

    print("=" * 78)
    return base_time_s


def save_csv(results: list[dict], csv_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Threads", "Documents", "Time_ms", "Time_s", "Speedup", "Runs", "Min_s", "Max_s"])
        for item in results:
            writer.writerow([
                item["threads"],
                item["docs"],
                f"{item['avg_ms']:.1f}",
                f"{item['avg_s']:.2f}",
                f"{item['speedup']:.2f}",
                item.get("runs", 1),
                f"{item.get('min_s', item['avg_s']):.2f}",
                f"{item.get('max_s', item['avg_s']):.2f}"
            ])
    print(f"\n[INFO] Benchmark CSV saved to: {csv_path}")


def load_csv(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    results = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = int(row["Threads"])
                docs = int(float(row.get("Documents", 0)))
                avg_ms = float(row.get("Time_ms", 0))
                avg_s = float(row.get("Time_s", avg_ms / 1000.0))
                sp = float(row.get("Speedup", 1.0))
                runs = int(row.get("Runs", 1))
                min_s = float(row.get("Min_s", avg_s))
                max_s = float(row.get("Max_s", avg_s))
                results.append({
                    "threads": t,
                    "docs": docs,
                    "avg_ms": avg_ms,
                    "avg_s": avg_s,
                    "speedup": sp,
                    "runs": runs,
                    "min_s": min_s,
                    "max_s": max_s
                })
            except (ValueError, KeyError):
                continue
    return results


def plot_results(results: list[dict], output_dir: str):
    if not HAS_MATPLOTLIB:
        print("[WARNING] matplotlib is not installed. Skipping plot generation.")
        return

    if not results:
        return

    os.makedirs(output_dir, exist_ok=True)
    threads = [item["threads"] for item in results]
    avg_times = [item["avg_s"] for item in results]
    min_times = [item["min_s"] for item in results]
    max_times = [item["max_s"] for item in results]
    speedups = [item["speedup"] for item in results]
    docs_cnt = results[0]["docs"] if results else 0
    max_t = max(threads)

    step = 2 if max_t <= 16 else (4 if max_t <= 32 else 8)
    ticks = [1] + [t for t in range(step, max_t + 1, step)]
    if ticks[-1] < max_t:
        ticks.append(max_t)

    # 1. Execution Time Plot
    time_path = os.path.join(output_dir, "index_build_time.png")
    fig, ax1 = plt.subplots(figsize=(10, 5.5))
    has_range = any(mx > mn for mx, mn in zip(max_times, min_times))
    if has_range:
        ax1.fill_between(threads, min_times, max_times, color="#2563eb", alpha=0.18, label="Min-Max Range across runs")
    ax1.plot(threads, avg_times, marker="o", markersize=5, color="#2563eb", linewidth=2.0, label="Average Build Time (s)")
    ax1.set_xlabel("Number of Worker Threads", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Execution Time (seconds)", fontsize=11, fontweight="bold")
    subtitle = f" ({docs_cnt:,} Documents)" if docs_cnt > 0 else ""
    ax1.set_title(f"Parallel Index Build Time vs Worker Threads{subtitle}", fontsize=12, fontweight="bold", pad=12)
    ax1.set_xticks(ticks)
    ax1.set_xlim(0, max_t * 1.02)
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(time_path, dpi=300)
    plt.close()
    print(f"[OK] Build time plot saved to: {time_path}")

    # 2. Speedup Plot
    speedup_path = os.path.join(output_dir, "index_speedup.png")
    fig, ax2 = plt.subplots(figsize=(10, 5.5))
    ax2.plot(threads, speedups, marker="s", markersize=5, color="#16a34a", linewidth=2.0, label="Speedup ($S = T_1 / T_p$)")

    ax2.set_xlabel("Number of Worker Threads", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Speedup Factor ($S_p$)", fontsize=11, fontweight="bold")
    ax2.set_title("Speedup vs Number of Worker Threads", fontsize=12, fontweight="bold", pad=12)
    ax2.set_xticks(ticks)
    ax2.set_xlim(0, max_t * 1.02)
    ax2.grid(True, linestyle="--", alpha=0.6)
    ax2.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(speedup_path, dpi=300)
    plt.close()
    print(f"[OK] Speedup plot saved to: {speedup_path}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Full-featured parallel indexing scalability benchmark & visualizer"
    )
    parser.add_argument(
        "--range",
        nargs="+",
        type=int,
        metavar=("MIN", "MAX"),
        help="Thread range as: MIN MAX [STEP] (e.g., --range 1 32 or --range 2 32 2)"
    )
    parser.add_argument(
        "--threads", "-t",
        nargs="+",
        help="Explicit thread counts to test (e.g., -t 1 2 4 8 16 32)"
    )
    parser.add_argument(
        "--runs", "-r", "--repeat",
        type=int,
        default=1,
        help="Number of runs per thread count for averaging (default: 1)"
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"Base search server URL (default: {DEFAULT_BASE_URL})"
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV_PATH,
        help=f"Path to export/import benchmark results CSV (default: {DEFAULT_CSV_PATH})"
    )
    parser.add_argument(
        "--from-csv",
        help="Re-generate plots and summary from an existing CSV without running benchmarks"
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_DOCS_DIR,
        help=f"Directory to save generated plots (default: {DEFAULT_DOCS_DIR})"
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Run benchmarks and export CSV without plotting images"
    )

    args = parser.parse_args()

    if args.from_csv:
        print(f"Loading benchmark data from: {args.from_csv}")
        results = load_csv(args.from_csv)
        runs_count = results[0].get("runs", 1) if results else 1
        print_summary_table(results, runs_count)
        if not args.no_plot:
            plot_results(results, args.output_dir)
        return 0

    thread_list = resolve_threads(args.range, args.threads)
    results = run_benchmark(args.url, thread_list, args.runs)
    if not results:
        print("[ERROR] No benchmark runs completed successfully.", file=sys.stderr)
        return 1

    print_summary_table(results, args.runs)
    save_csv(results, args.csv)

    if not args.no_plot:
        plot_results(results, args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
