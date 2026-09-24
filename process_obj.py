import os
import time
from multiprocessing import Manager, Pool, cpu_count
from pathlib import Path

MODELS_DIR = r"H:\GameAssets\3D模型库_发布包\models"
BASE_DIR = r"H:\GameAssets\3D模型库_发布包"


shared_counters = None
shared_lock = None


def js_escape(text):
    return text.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "")


def process_single_obj(obj_path, counters, lock):
    obj_path = Path(obj_path)
    try:
        if not obj_path.is_file():
            with lock:
                counters["skipped"] += 1
            return ("skip", str(obj_path), "not a regular file")

        js_path = obj_path.with_suffix(".obj.js")

        rel_path = obj_path.relative_to(BASE_DIR).as_posix()
        key = rel_path

        try:
            content = obj_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001 单文件读失败按失败计数，批量转换继续
            with lock:
                counters["failed"] += 1
            return ("fail", str(obj_path), f"read error: {e}")

        escaped = js_escape(content)

        js_content = (
            f"window.__OBJ_STORE=window.__OBJ_STORE||{{}}; "
            f"window.__OBJ_STORE[\"{key}\"] = \"{escaped}\";"
        )

        try:
            js_path.write_text(js_content, encoding="utf-8")
        except Exception as e:  # noqa: BLE001 单文件写失败按失败计数，批量转换继续
            with lock:
                counters["failed"] += 1
            return ("fail", str(obj_path), f"write error: {e}")

        with lock:
            counters["success"] += 1
            if counters["success"] <= 3:
                counters["samples"].append((str(obj_path), js_content[:200]))
        return ("success", str(obj_path), "")

    except Exception as e:  # noqa: BLE001 最外层兜底：意外异常只影响当前文件
        with lock:
            counters["failed"] += 1
        return ("fail", str(obj_path), f"unexpected: {e}")


def find_all_obj_files(models_dir):
    result = []
    for root, _dirs, files in os.walk(models_dir):
        for f in files:
            if f.lower().endswith(".obj"):
                full_path = os.path.join(root, f)
                result.append(full_path)
    return result


def init_worker(counters, lock_obj):
    global shared_counters, shared_lock
    shared_counters = counters
    shared_lock = lock_obj


def worker_wrapper(obj_path):
    return process_single_obj(obj_path, shared_counters, shared_lock)


def main():
    print(f"Scanning {MODELS_DIR} for .obj files...")
    start_time = time.time()

    obj_files = find_all_obj_files(MODELS_DIR)
    total = len(obj_files)
    print(f"Found {total} .obj files.")

    if total == 0:
        print("No .obj files found. Exiting.")
        return

    manager = Manager()
    counters = manager.dict()
    counters["success"] = 0
    counters["failed"] = 0
    counters["skipped"] = 0
    counters["samples"] = manager.list()

    lock = manager.Lock()

    num_workers = min(cpu_count(), 16)
    print(f"Using {num_workers} worker processes...")

    processed = 0
    last_report = 0

    with Pool(processes=num_workers, initializer=init_worker, initargs=(counters, lock)) as pool:
        for _ in pool.imap_unordered(worker_wrapper, obj_files, chunksize=20):
            processed += 1
            if processed - last_report >= 1000:
                last_report = processed
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 else 0
                print(f"  Progress: {processed}/{total} ({100*processed/total:.1f}%) | "
                      f"Success: {counters['success']} | Failed: {counters['failed']} | "
                      f"Skipped: {counters['skipped']} | "
                      f"Rate: {rate:.0f}/s | ETA: {eta:.0f}s")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"Processing complete in {elapsed:.1f}s ({total/elapsed:.0f} files/s)")
    print(f"Total found:   {total}")
    print(f"Success:       {counters['success']}")
    print(f"Failed:        {counters['failed']}")
    print(f"Skipped:       {counters['skipped']}")
    print("=" * 60)

    samples = list(counters["samples"])
    if samples:
        print("\nSample files (first 200 chars of .obj.js content):")
        print("-" * 60)
        for i, (path, content) in enumerate(samples[:3], 1):
            print(f"\nSample {i}: {path}")
            print(content)
            print()

    with open(os.path.join(BASE_DIR, "process_report.txt"), "w", encoding="utf-8") as f:
        f.write(f"Report generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total found:   {total}\n")
        f.write(f"Success:       {counters['success']}\n")
        f.write(f"Failed:        {counters['failed']}\n")
        f.write(f"Skipped:       {counters['skipped']}\n")
        f.write(f"Elapsed time:  {elapsed:.1f}s\n")
        f.write("\nSamples:\n")
        for i, (path, content) in enumerate(samples[:3], 1):
            f.write(f"\nSample {i}: {path}\n")
            f.write(content + "\n")

    print(f"\nReport saved to: {os.path.join(BASE_DIR, 'process_report.txt')}")


if __name__ == "__main__":
    main()
