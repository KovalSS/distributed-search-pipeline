import argparse
import csv
import os
import sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

def plot_indexing_speedup(csv_path: str, output_path: str):
    if not HAS_MATPLOTLIB:
        print("[ERROR] matplotlib is not installed. Run: pip install matplotlib")
        return 1

    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        return 1

    threads = []
    times_s = []
    speedups = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = int(row["Threads"])
                ts = float(row["Time_s"])
                sp = float(row["Speedup"])
                threads.append(t)
                times_s.append(ts)
                speedups.append(sp)
            except (ValueError, KeyError):
                continue

    if not threads:
        print("[ERROR] No valid data found in CSV.")
        return 1

    out_dir = os.path.dirname(os.path.abspath(output_path)) if output_path.endswith(".png") else os.path.abspath(output_path)
    os.makedirs(out_dir, exist_ok=True)

    max_t = max(threads) if threads else 40
    step = 5 if max_t <= 50 else 10
    thread_ticks = [1] + [t for t in range(step, max_t + 1, step)]
    if thread_ticks[-1] < max_t:
        thread_ticks.append(max_t)

    time_path = os.path.join(out_dir, "index_build_time.png")
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(threads, times_s, marker="o", markersize=4.5, color="#2563eb", linewidth=1.8, label="Actual Build Time (s)")
    ax1.set_xlabel("Number of Worker Threads", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Execution Time (seconds)", fontsize=11, fontweight="bold")
    ax1.set_title("Index Build Time vs Threads (400k Documents)", fontsize=12, fontweight="bold", pad=12)
    ax1.set_xticks(thread_ticks)
    ax1.set_xlim(0, max_t * 1.02)
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(time_path, dpi=300)
    plt.close()
    print(f"[OK] Build time plot saved to: {time_path}")

    speedup_path = os.path.join(out_dir, "index_speedup.png")
    fig, ax2 = plt.subplots(figsize=(10, 5))
    ax2.plot(threads, speedups, marker="s", markersize=4.5, color="#16a34a", linewidth=1.8, label="Speedup ($S = T_1 / T_p$)")
    ax2.set_xlabel("Number of Worker Threads", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Speedup Factor ($S_p$)", fontsize=11, fontweight="bold")
    ax2.set_title("Speedup vs Worker Threads", fontsize=12, fontweight="bold", pad=12)
    ax2.set_xticks(thread_ticks)
    ax2.set_xlim(0, max_t * 1.02)
    ax2.grid(True, linestyle="--", alpha=0.6)
    ax2.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(speedup_path, dpi=300)
    plt.close()
    print(f"[OK] Speedup plot saved to: {speedup_path}")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Plot index build speedup from benchmark CSV")
    parser.add_argument("--csv", default="benchmarks/results/indexing_results.csv", help="Input CSV path")
    parser.add_argument("--output", default="docs/benchmarks/index_speedup.png", help="Output PNG path")
    args = parser.parse_args()
    return plot_indexing_speedup(args.csv, args.output)

if __name__ == "__main__":
    sys.exit(main() or 0)
