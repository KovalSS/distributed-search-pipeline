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


def run_search(server_url: str, query: str, mode: str, top: int) -> dict:
    payload = json.dumps({"query": query, "mode": mode, "top": top}).encode("utf-8")
    request = urllib.request.Request(
        server_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def print_results(data: dict, query: str, mode: str, show_raw: bool = False) -> None:
    results = data.get("results", [])
    time_ms = data.get("time_ms", "?")
    synonyms = data.get("synonyms")

    print("\n" + "-" * 60)
    print(f"Search results for: \"{query}\"")
    print(f"Found: {len(results)} | Response time: {time_ms} ms | Mode: {mode.upper()}")
    if synonyms:
        print(f"Synonyms (Ollama): {', '.join(synonyms)}")
    print("-" * 60)

    if not results:
        print("No results found for this query.\n")
        return

    for i, item in enumerate(results, start=1):
        title = item.get("snippet") or "(No product title)"
        score = item.get("score", 0.0)
        doc_id = item.get("doc_id", "?")
        print(f"{i:>2}. [{score:>5.1f}] {title}")
        print(f"     Document ID: {doc_id}")

        if show_raw and item.get("raw"):
            raw_str = json.dumps(item["raw"], indent=2, ensure_ascii=False)
            print("     Raw Document Data:")
            for line in raw_str.splitlines():
                print(f"       {line}")
        print()


def execute_single_search(url: str, query: str, mode: str, top: int, show_raw: bool = False):
    try:
        data = run_search(url, query, mode, top)
        print_results(data, query, mode, show_raw)
        return 0
    except urllib.error.URLError as e:
        print(f"[ERROR] Failed to connect to server ({url}): {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError:
        print("[ERROR] Server returned invalid JSON.", file=sys.stderr)
        return 1


def interactive_mode(url: str, mode: str, top: int, show_raw: bool = False):
    current_mode = mode
    current_show_raw = show_raw

    print("=" * 65)
    print("                INTERACTIVE SEARCH MODE (CLI)")
    print(f"  Mode: {current_mode.upper()} | Show Raw Data: {'ON' if current_show_raw else 'OFF'}")
    print("  Commands:")
    print("    :keyword  / :kw   - switch to Keyword mode")
    print("    :expanded / :exp  - switch to Expanded (AI) mode")
    print("    :raw              - toggle raw data display (ON/OFF)")
    print("    q / exit          - quit")
    print("=" * 65 + "\n")

    while True:
        try:
            raw_indicator = "+raw" if current_show_raw else ""
            prompt_mode = f"{current_mode}{raw_indicator}"
            query = input(f"Search [{prompt_mode}] > ").strip()
            if not query:
                continue
            if query.lower() in ("q", "quit", "exit"):
                print("Exiting search.")
                break
            if query.lower() in (":keyword", ":kw"):
                current_mode = "keyword"
                print("Switched to mode: KEYWORD\n")
                continue
            if query.lower() in (":expanded", ":exp"):
                current_mode = "expanded"
                print("Switched to mode: EXPANDED\n")
                continue
            if query.lower() in (":raw", ":show_raw", ":show-raw"):
                current_show_raw = not current_show_raw
                print(f"Raw data display: {'ON' if current_show_raw else 'OFF'}\n")
                continue

            execute_single_search(url, query, current_mode, top, current_show_raw)
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
        "--mode", "-m",
        choices=["keyword", "expanded"],
        default="keyword",
        help="Search mode: 'keyword' (pure fast index lookup) or 'expanded' (AI Query Expansion via Ollama)"
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
    parser.add_argument(
        "--show-raw", "--raw", "-r",
        action="store_true",
        help="Display full raw product document JSON for each search result"
    )

    args = parser.parse_args()
    effective_mode = args.mode.lower()

    server_ok, doc_count = check_index_status(args.stats_url)
    if not server_ok:
        print(f"[WARNING] Failed to check index status at {args.stats_url}. Make sure backend is running.", file=sys.stderr)
    elif doc_count == 0:
        print("[WARNING] Index in server memory is empty (0 documents).")
        print("  Search will yield empty results. Build the index first:")
        print("  python cli-client/index.py --threads 8\n")

    if args.query:
        return execute_single_search(args.url, args.query, effective_mode, args.top, args.show_raw)
    else:
        return interactive_mode(args.url, effective_mode, args.top, args.show_raw)


if __name__ == "__main__":
    sys.exit(main())
