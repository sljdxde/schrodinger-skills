#!/usr/bin/env python3
"""
多线程下载工具 — curl 引擎版 (mtd-download)

用法:
    python3 mtd.py <URL> [-t 线程数(默认16)] [-o 输出文件名]
                       [--sha256 HEX] [--no-checksum] [--no-clear-quarantine]

特性:
    - 自动探测文件大小与服务器是否支持 Range(分段下载)
    - 支持分段时用多线程并行下载；不支持、文件过小或大小未知时退回单线程
    - 每个线程使用「原始 URL + curl -L」独立跟随 CDN 重定向，规避带鉴权参数
      的 CDN URL 过期问题（不会把 HTML 错误页当作文件内容写入磁盘）
    - Range 内容非零校验：部分国产 CDN 声称支持 Range 且返回 206，但 body 是全
      零字节。探测阶段实测一块数据，若 >95% 为零则判定该 CDN 的 Range 实现有
      缺陷，自动退化为单线程整文件下载
    - 下载后可选 SHA256 校验（--sha256 比对官方值；默认打印实际 SHA256 供核对）
    - macOS 上下载完成后自动清除 Gatekeeper 隔离标记（com.apple.quarantine），
      避免双击 DMG 报「磁盘映像已损坏」；可用 --no-clear-quarantine 关闭
    - 实时进度条（进度/已下/速度/ETA），输出走 stderr，不污染 stdout
    - 纯标准库 + 系统自带 curl，无需 pip 安装任何依赖
    - 下载未完成时自动清理不完整的输出文件，避免留下损坏文件
"""
from __future__ import annotations

import argparse
import hashlib
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
RANGE_PROBE_LEN = 16384           # Range 内容非零探测长度
RANGE_ZERO_RATIO = 0.05           # 非零字节占比低于此值(即 >95% 为零)判定 CDN 缺陷


def _have_curl() -> bool:
    return shutil.which("curl") is not None


def _have_xattr() -> bool:
    return sys.platform == "darwin" and shutil.which("xattr") is not None


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
    """通过 curl 获取文件大小和是否支持分段下载。

    返回 (size, supports_range)。探测统一使用原始 URL + -L 跟随重定向，
    避免依赖一次性的 CDN 鉴权 URL。
    """
    # 跟随重定向，拿最终响应的 content-length 与 accept-ranges
    result = subprocess.run(
        ["curl", "-sIL", "--max-time", "15", "-o", "/dev/null",
         "-w", "SIZE:%header{content-length}\nRANGE:%header{accept-ranges}\nCODE:%{response_code}",
         url],
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

    if size and supports_range:
        # 第一步稳健性: 很多服务器响应头写 accept-ranges: bytes，但对 Range 请求
        # 却返回 200 整文件。光看响应头会误判，导致多线程把「文件头部」错写进每个
        # 分块。这里实测发一个 1 字节 Range 请求，只有真正返回 206 才继续。
        # 带 -L：对需要 302 跳转到 CDN 签名的原始 URL（如 JetBrains/Cloudflare China），
        # 必须跟随重定向才能在最终地址上验证 Range，否则会误判为不支持而退化单线程。
        probe = subprocess.run(
            ["curl", "-sL", "-o", "/dev/null", "--max-time", "15",
             "-r", "0-0", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=20)
        if probe.stdout.strip() != "206":
            supports_range = False

        # 第二步稳健性(针对国产 CDN 缺陷): 部分 CDN 返回 206 但 body 全是零字节。
        # 实测下载一块数据，若 >95% 为零则判定该 CDN 的 Range 实现有缺陷，
        # 退化为单线程整文件下载(整文件下载不受 Range 缺陷影响)。
        if supports_range and not _range_content_ok(url, size):
            supports_range = False

    return size, supports_range


def _range_content_ok(url, total_size) -> bool:
    """实测一块 Range 数据，判断是否真的返回了有效内容。

    为降低误判(某些正常文件开头恰好是零区)，优先测试文件「中部」区间；
    文件过小则测试开头。
    """
    if total_size <= 0:
        return True
    if total_size > RANGE_PROBE_LEN * 2:
        start = total_size // 2
    else:
        start = 0
    end = min(start + RANGE_PROBE_LEN, total_size) - 1
    try:
        proc = subprocess.run(
            ["curl", "-sLf", "--max-time", "15", "-r", f"{start}-{end}", url],
            capture_output=True, timeout=20)
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    data = proc.stdout
    if not data:
        return False
    non_zero = sum(1 for b in data if b != 0)
    return non_zero >= len(data) * RANGE_ZERO_RATIO


def download_part(url, start, end, part_id, fd, bar, errors):
    """下载 [start, end) 区间。

    关键稳健性: 无论服务器是否真的遵守 Range，本函数都只把属于自己区间的数据
    写入 fd（用 os.pwrite 按绝对偏移写），并丢弃区间外的多余数据，避免越界覆盖
    其它线程的分块。

    每个线程使用原始 URL + -L 独立跟随 CDN 重定向（不共用一次性鉴权 URL），
    并带 -f 使 HTTP 错误(>=400)时返回非 0 退出码，避免把错误页当作文件数据。
    """
    remaining = end - start
    for attempt in range(RETRIES):
        try:
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
    """单线程流式下载，兼容已知大小与未知大小（total_size==0）。

    带 -f: CDN 返回错误页时 curl 非 0 退出，不会把错误页当作文件内容。
    """
    sys.stderr.write("  单线程下载...\n")
    bar = Bar(total_size, out_path.name)
    printer = threading.Thread(target=bar.print_thread, daemon=True)
    printer.start()

    proc = subprocess.Popen(["curl", "-sLf", "--max-time", "600", url],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    ok = True
    try:
        with open(out_path, "wb") as f:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                bar.add(len(chunk))
        ret = proc.wait()
        if ret != 0:
            ok = False
            sys.stderr.write(f"  ⚠ curl 返回非 0 退出码 ({ret})，下载可能不完整\n")
    except Exception as e:
        ok = False
        sys.stderr.write(f"  ⚠ 单线程下载异常: {e}\n")
    finally:
        bar.alive = False
        printer.join(timeout=1)

    if ok and total_size > 0 and out_path.stat().st_size != total_size:
        ok = False
        sys.stderr.write("  ⚠ 文件大小与预期不符，可能下载不完整\n")

    if not ok:
        try:
            out_path.unlink()
            sys.stderr.write("  下载未完成，已删除不完整的文件\n")
        except OSError:
            pass
        return False

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
    sys.stderr.write(f"  启动 {len(parts)} 个线程(多线程分段下载)...\n")

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


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def clear_quarantine(path: Path) -> None:
    """macOS: 清除 Gatekeeper 隔离标记，避免双击 DMG 报「磁盘映像已损坏」。"""
    if not _have_xattr():
        return
    try:
        subprocess.run(["xattr", "-c", str(path)], capture_output=True, timeout=10)
    except Exception:
        pass


def download(url, out_name=None, threads=THREADS,
             expected_sha256=None, compute_checksum=True,
             clear_quarantine_flag=True):
    if not _have_curl():
        sys.stderr.write("❌ 未找到 curl，无法下载（需要系统自带 curl）\n")
        return False

    # 1. 探测
    sys.stderr.write("  正在探测服务器... ")
    sys.stderr.flush()
    total_size, supports_range = get_remote_info(url)
    if total_size == 0:
        sys.stderr.write("⚠ 无法获取文件大小，改用单线程流式下载\n")
    else:
        mode = "多线程分段" if (supports_range and total_size > PART_THRESHOLD) else "单线程"
        sys.stderr.write(f"OK ({total_size/1024/1024:.0f}MB, {mode})\n")

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
        ok = _download_multi(url, out_path, total_size, threads)
    else:
        ok = _download_single(url, out_path, total_size)

    if not ok:
        return False

    # 4. SHA256 校验
    if compute_checksum:
        sys.stderr.write("  计算 SHA256... ")
        actual = compute_sha256(out_path)
        sys.stderr.write(f"{actual}\n")
        if expected_sha256:
            if actual.lower() == expected_sha256.lower():
                sys.stderr.write("  ✅ SHA256 校验通过\n")
            else:
                sys.stderr.write("  ❌ SHA256 不匹配！文件可能损坏，已保留文件供排查\n")
                return False

    # 5. macOS 清除隔离标记
    if clear_quarantine_flag:
        clear_quarantine(out_path)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="多线程下载工具 (curl 引擎) — mtd-download",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="下载地址")
    parser.add_argument("-t", "--threads", type=int, default=THREADS,
                        help=f"线程数 (默认 {THREADS})")
    parser.add_argument("-o", "--output", default=None,
                        help="输出文件名 (默认从 URL 推断)")
    parser.add_argument("--sha256", default=None,
                        help="官方 SHA256 值，下载后自动比对")
    parser.add_argument("--no-checksum", action="store_true",
                        help="不计算/打印 SHA256")
    parser.add_argument("--no-clear-quarantine", action="store_true",
                        help="macOS 上下载后不清除 Gatekeeper 隔离标记")
    args = parser.parse_args()

    ok = download(args.url, args.output, args.threads,
                  expected_sha256=args.sha256,
                  compute_checksum=not args.no_checksum,
                  clear_quarantine_flag=not args.no_clear_quarantine)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
