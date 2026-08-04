#!/usr/bin/env python3
"""
多线程下载工具 — curl 引擎版 (mtd-download)

用法:
    python3 mtd.py <URL> [-t 线程数(默认16)] [-o 输出文件名]

特性:
    - 自动探测文件大小与服务器是否支持 Range(断点续传)
    - 支持分段时用多线程并行下载；不支持、文件过小或大小未知时退回单线程
    - 实时进度条（进度/已下/速度/ETA），输出走 stderr，不污染 stdout
    - 纯标准库 + 系统自带 curl，无需 pip 安装任何依赖
    - 下载未完成时自动清理不完整的输出文件，避免留下损坏文件
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

THREADS = 16
RETRIES = 3
PART_THRESHOLD = 4 * 1024 * 1024  # 小于此大小不分段


def _have_curl() -> bool:
    return shutil.which("curl") is not None


class Bar:
    def __init__(self, total, label=""):
        self.total = total
        self.done = 0
        self.label = label
        self.lock = threading.Lock()
        self.start = time.time()
        self.alive = True

    def add(self, n):
        with self.lock:
            self.done += n

    def render(self):
        with self.lock:
            d, t = self.done, self.total
        pct = d / t * 100 if t else 0.0
        elapsed = time.time() - self.start
        speed = d / elapsed / 1024 / 1024 if elapsed > 0 else 0.0
        filled = int(pct / 2)
        bar_str = "█" * filled + "░" * (50 - filled)
        if t:
            size_str = f"{d/1024/1024:.1f}/{t/1024/1024:.1f}MB"
            eta = (t - d) / (speed * 1024 * 1024) if speed > 0 else 0
            eta_str = f"{int(eta//60)}m{int(eta%60)}s" if eta < 3600 else "…"
            pct_str = f"{pct:5.1f}%"
        else:
            size_str = f"{d/1024/1024:.1f}MB"
            eta_str = "…"
            pct_str = "   ??%"
        return (f"\r  {self.label}  [{bar_str}] {pct_str}  {size_str}  "
                f"{speed:.1f}MB/s  ETA:{eta_str}  ")

    def print_thread(self):
        while self.alive:
            sys.stderr.write(self.render())
            sys.stderr.flush()
            time.sleep(0.2)
        sys.stderr.write(self.render() + "\n")
        sys.stderr.flush()


def get_remote_info(url):
    """通过 curl 获取文件大小和是否支持分段。"""
    # Step 1: 跟随重定向拿到最终 CDN URL
    result = subprocess.run(
        ["curl", "-sI", "--max-time", "15", "-o", "/dev/null", "-w", "%{redirect_url}", url],
        capture_output=True, text=True, timeout=20)
    final_url = result.stdout.strip() or url

    # Step 2: 从最终 URL 取大小和 Range 支持
    result = subprocess.run(
        ["curl", "-sI", "--max-time", "15", "-o", "/dev/null",
         "-w", "SIZE:%header{content-length}\nRANGE:%header{accept-ranges}", final_url],
        capture_output=True, text=True, timeout=20)

    size = 0
    supports_range = False
    for line in result.stdout.strip().split("\n"):
        if line.startswith("SIZE:"):
            try:
                size = int(line.split(":", 1)[1])
            except ValueError:
                pass
        elif line.startswith("RANGE:"):
            supports_range = "bytes" in line.lower()

    # 关键稳健性: 很多服务器会在响应头写 accept-ranges: bytes，
    # 但对 Range 请求却返回 200 整文件。光看响应头会误判，导致多线程把
    # 「文件头部」错写进每个分块。这里实测发一个 1 字节 Range 请求，
    # 只有真正返回 206 才认定支持分段。
    if supports_range:
        probe = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "--max-time", "15",
             "-r", "0-0", "-w", "%{http_code}", final_url],
            capture_output=True, text=True, timeout=20)
        if probe.stdout.strip() != "206":
            supports_range = False

    return size, supports_range, final_url


def download_part(url, start, end, part_id, fd, bar, errors):
    """下载 [start, end) 区间。

    关键稳健性: 无论服务器是否真的遵守 Range，本函数都只把属于自己区间的数据
    写入 fd（用 os.pwrite 按绝对偏移写），并丢弃区间外的多余数据，避免越界覆盖
    其它线程的分块。
    """
    remaining = end - start
    for attempt in range(RETRIES):
        try:
            # -L: 跟随重定向（每次线程独立重新解析 CDN 鉴权链接）
            # -f: HTTP 错误时返回非 0 退出码
            # --max-time: 单个分块的超时
            proc = subprocess.Popen(
                ["curl", "-sLf", "--max-time", "60", "-r", f"{start}-{end - 1}", url],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            pos = start
            while remaining > 0:
                chunk = proc.stdout.read(min(65536, remaining))
                if not chunk:
                    break
                os.pwrite(fd, chunk, pos)
                pos += len(chunk)
                remaining -= len(chunk)
                bar.add(len(chunk))

            # 排空剩余数据（若服务器无视 Range 返回了超出本区间的内容）
            while proc.stdout.read(65536):
                pass

            ret = proc.wait()
            if ret == 0 and remaining == 0:
                return True
            if attempt < RETRIES - 1:
                time.sleep(1 + attempt)
                continue
            errors.append(f"  分块{part_id} 重试{RETRIES}次仍失败 (ret={ret}, 缺{remaining}字节)")
            return False
        except Exception as e:
            if attempt < RETRIES - 1:
                time.sleep(1 + attempt)
                continue
            errors.append(f"  分块{part_id} 异常: {e}")
            return False
    return False


def _download_single(url, out_path, total_size):
    """单线程流式下载，兼容已知大小与未知大小（total_size==0）。"""
    sys.stderr.write("  单线程下载...\n")
    bar = Bar(total_size, out_path.name)
    printer = threading.Thread(target=bar.print_thread, daemon=True)
    printer.start()

    # 用 -L 跟随重定向；单线程直接用原始 URL 即可
    proc = subprocess.Popen(["curl", "-sL", "--max-time", "600", url],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    with open(out_path, "wb") as f:
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            f.write(chunk)
            bar.add(len(chunk))

    proc.wait()
    bar.alive = False
    printer.join(timeout=1)
    sys.stderr.write(f"\n  ✅ 完成 → {out_path}\n")
    return True


def _download_multi(url, out_path, total_size, threads):
    """多线程分段下载，最后校验大小并清理失败残留。"""
    part_size = (total_size + threads - 1) // threads
    parts = []
    for i in range(threads):
        start = i * part_size
        end = min(start + part_size, total_size)
        if start < total_size:
            parts.append((start, end))
    sys.stderr.write(f"  启动 {len(parts)} 个线程...\n")

    # 预分配文件
    with open(out_path, "wb") as f:
        f.truncate(total_size)

    fd = os.open(str(out_path), os.O_WRONLY)
    errors = []
    try:
        bar = Bar(total_size, out_path.name)
        printer = threading.Thread(target=bar.print_thread, daemon=True)
        printer.start()

        workers = []
        for i, (start, end) in enumerate(parts):
            t = threading.Thread(
                target=download_part, args=(url, start, end, i, fd, bar, errors))
            t.start()
            workers.append(t)

        for t in workers:
            t.join()

        bar.alive = False
        printer.join(timeout=1)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass

    if errors:
        for e in errors:
            sys.stderr.write(f"{e}\n")
        try:
            out_path.unlink()
            sys.stderr.write("  下载未完成，已删除不完整的文件\n")
        except OSError:
            pass
        return False

    if out_path.stat().st_size != total_size:
        sys.stderr.write("  ⚠ 文件大小与预期不符，可能下载不完整\n")
        return False

    sys.stderr.write(f"\n  ✅ 完成 → {out_path}\n")
    return True


def download(url, out_name=None, threads=THREADS):
    if not _have_curl():
        sys.stderr.write("❌ 未找到 curl，无法下载（需要系统自带 curl）\n")
        return False

    # 1. 探测
    sys.stderr.write("  正在探测服务器... ")
    sys.stderr.flush()
    total_size, supports_range, _final_url = get_remote_info(url)
    if total_size == 0:
        sys.stderr.write("⚠ 无法获取文件大小，改用单线程流式下载\n")
    else:
        sys.stderr.write(f"OK ({total_size/1024/1024:.0f}MB, "
                         f"{'支持' if supports_range else '不支持'}分段)\n")

    # 2. 文件名
    if not out_name:
        path = urlparse(url).path
        out_name = unquote(path.split("/")[-1].split("?")[0])
        if not out_name:
            out_name = "download"
    out_path = Path(out_name).resolve()
    sys.stderr.write(f"  输出: {out_path}\n")

    # 3. 多线程 or 单线程
    if total_size > 0 and supports_range and total_size > PART_THRESHOLD:
        return _download_multi(url, out_path, total_size, threads)
    return _download_single(url, out_path, total_size)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]
    out_name = None
    threads = THREADS

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] in ("-t", "--threads") and i + 1 < len(sys.argv):
            threads = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] in ("-o", "--output") and i + 1 < len(sys.argv):
            out_name = sys.argv[i + 1]
            i += 2
        elif not sys.argv[i].startswith("-"):
            out_name = sys.argv[i]
            i += 1
        else:
            i += 1

    ok = download(url, out_name, threads)
    sys.exit(0 if ok else 1)
