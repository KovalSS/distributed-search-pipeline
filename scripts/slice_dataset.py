import argparse
import json
import os
import sys
import time
from pathlib import Path


def find_input_files(input_path: Path):
    if input_path.is_file():
        return [input_path]
    elif input_path.is_dir():
        files = sorted(input_path.glob("*.jsonl"))
        if not files:
            files = sorted(input_path.glob("*.json"))
        return files
    return []


def write_batch(lines: list, output_dir: Path, batch_index: int):
    output_filename = output_dir / f"batch_{batch_index:04d}.jsonl"
    with open(output_filename, "w", encoding="utf-8") as outfile:
        outfile.write("\n".join(lines) + "\n")
    return output_filename


def slice_dataset(input_path: str, output_dir: str, batch_size: int, max_documents: int, start_batch: int = 1):
    in_path = Path(input_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    input_files = find_input_files(in_path)
    if not input_files:
        print(f"[ERROR] No .jsonl files found at path: {in_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("Dataset Slicer (Parallel Pipeline Preprocessing)")
    print("=" * 60)
    print(f"Input source      : {in_path} ({len(input_files)} file(s))")
    print(f"Output directory  : {out_dir}")
    print(f"Batch size        : {batch_size:,} docs/file")
    print(f"Max documents     : {max_documents:,}" if max_documents else "Max documents     : Unlimited")
    print("=" * 60)

    start_time = time.time()
    batch_count = start_batch
    total_docs = 0
    corrupted_lines = 0
    current_batch_lines = []

    for file_idx, file_path in enumerate(input_files, 1):
        print(f"\n[{file_idx}/{len(input_files)}] Reading: {file_path.name}...")
        try:
            with open(file_path, "r", encoding="utf-8") as infile:
                for line in infile:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        json.loads(line)
                        current_batch_lines.append(line)
                        total_docs += 1

                        if len(current_batch_lines) >= batch_size:
                            batch_file = write_batch(current_batch_lines, out_dir, batch_count)
                            elapsed = time.time() - start_time
                            rate = total_docs / elapsed if elapsed > 0 else 0
                            print(f"  [+] Saved {batch_file.name} ({len(current_batch_lines):,} docs) | Total: {total_docs:,} docs ({rate:,.0f} docs/s)")
                            batch_count += 1
                            current_batch_lines = []

                        if max_documents and total_docs >= max_documents:
                            break

                    except json.JSONDecodeError:
                        corrupted_lines += 1

                if max_documents and total_docs >= max_documents:
                    print(f"\n[INFO] Reached requested limit of {max_documents:,} documents.")
                    break

        except Exception as e:
            print(f"[ERROR] Failed to read {file_path}: {e}", file=sys.stderr)

    if current_batch_lines:
        batch_file = write_batch(current_batch_lines, out_dir, batch_count)
        print(f"  [+] Saved {batch_file.name} ({len(current_batch_lines):,} docs, last batch)")
        batch_count += 1

    total_time = time.time() - start_time
    created_batches = batch_count - start_batch

    total_size_bytes = sum(f.stat().st_size for f in out_dir.glob("batch_*.jsonl"))
    total_size_mb = total_size_bytes / (1024 * 1024)

    print("\n" + "=" * 60)
    print("Slicing Completed Successfully!")
    print(f"  Total valid documents : {total_docs:,}")
    print(f"  Corrupted lines skipped: {corrupted_lines}")
    print(f"  Batches generated     : {created_batches} files")
    print(f"  Total dataset size    : {total_size_mb:.2f} MB ({total_size_mb / 1024:.2f} GB)")
    print(f"  Total execution time  : {total_time:.2f} s")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Split large .jsonl datasets into batches for parallel search indexing.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i",
        default=r"data\raw",
        help="Path to raw .jsonl file or directory containing .jsonl files",
    )
    parser.add_argument(
        "--output", "-o",
        default=r"data\batched",
        help="Directory where batch_XXXX.jsonl files will be saved",
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=5000,
        help="Number of JSON documents per batch file",
    )
    parser.add_argument(
        "--max-docs", "-m",
        type=int,
        default=400000,
        help="Maximum total documents to slice (0 for unlimited)",
    )
    parser.add_argument(
        "--start-batch",
        type=int,
        default=1,
        help="Starting index for batch filename numbering",
    )

    args = parser.parse_args()
    max_docs = None if args.max_docs <= 0 else args.max_docs

    slice_dataset(
        input_path=args.input,
        output_dir=args.output,
        batch_size=args.batch_size,
        max_documents=max_docs,
        start_batch=args.start_batch,
    )


if __name__ == "__main__":
    main()
