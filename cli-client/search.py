#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_SEARCH_URL = "http://localhost:8080/api/search"
DEFAULT_STATS_URL = "http://localhost:8080/api/stats"


def check_index_status(stats_url: str) -> tuple[bool, int]:
    try:
        req = urllib.request.Request(stats_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            docs = data.get("documents", 0)
            return True, docs
    except Exception:
        return False, 0


def run_search(server_url: str, query: str, top: int) -> dict:
    payload = json.dumps({"query": query, "mode": "keyword", "top": top}).encode("utf-8")
    request = urllib.request.Request(
        server_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def print_results(data: dict, query: str) -> None:
    results = data.get("results", [])
    time_ms = data.get("time_ms", "?")

    print("\n" + "-" * 60)
    print(f"Search results for: \"{query}\"")
    print(f"Found: {len(results)} | Response time: {time_ms} ms")
    print("-" * 60)

    if not results:
        print("No results found for this query.\n")
        return

    for i, item in enumerate(results, start=1):
        title = item.get("snippet") or "(No product title)"
        score = item.get("score", 0.0)
        doc_id = item.get("doc_id", "?")
        print(f"{i:>2}. [{score:>5.1f}] {title}")
        print(f"     Document ID: {doc_id}\n")


def execute_single_search(url: str, query: str, top: int):
    try:
        data = run_search(url, query, top)
        print_results(data, query)
        return 0
    except urllib.error.URLError as e:
        print(f"[ERROR] Failed to connect to server ({url}): {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError:
        print("[ERROR] Server returned invalid JSON.", file=sys.stderr)
        return 1


def interactive_mode(url: str, top: int):
    print("=" * 60)
    print("           INTERACTIVE SEARCH MODE (CLI)")
    print("  Enter search query and press Enter.")
    print("  To exit, type 'q', 'exit' or press Ctrl+C.")
    print("=" * 60 + "\n")

    while True:
        try:
            query = input("Search > ").strip()
            if not query:
                continue
            if query.lower() in ("q", "quit", "exit"):
                print("Exiting search.")
                break
            execute_single_search(url, query, top)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting search.")
            break
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="CLI client for search in distributed pipeline"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query (runs interactive mode if omitted)"
    )
    parser.add_argument(
        "--top", "-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)"
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_SEARCH_URL,
        help=f"Search endpoint URL (default: {DEFAULT_SEARCH_URL})"
    )
    parser.add_argument(
        "--stats-url",
        default=DEFAULT_STATS_URL,
        help=f"Stats endpoint URL (default: {DEFAULT_STATS_URL})"
    )

    args = parser.parse_args()

    server_ok, doc_count = check_index_status(args.stats_url)
    if not server_ok:
        print(f"[WARNING] Failed to check index status at {args.stats_url}. Make sure backend is running.", file=sys.stderr)
    elif doc_count == 0:
        print("[WARNING] Index in server memory is empty (0 documents).")
        print("  Search will yield empty results. Build the index first:")
        print("  python cli-client/index.py --threads 8\n")

    if args.query:
        return execute_single_search(args.url, args.query, args.top)
    else:
        return interactive_mode(args.url, args.top)


if __name__ == "__main__":
    sys.exit(main())
