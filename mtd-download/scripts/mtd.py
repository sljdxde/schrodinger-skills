#!/usr/bin/env python3
"""
多线程下载工具 — curl 引擎版 (mtd-download)

用法:
    python3 mtd.py <URL> [-t 线程数(默认16)] [-o 输出文件名]
                       [--chunk 分块MB(默认5)] [--max-retry 次数(默认5)]
                       [--sha256 HEX] [--no-checksum] [--no-clear-quarantine]
                       [--resume] [--overwrite] [--single]

特性:
    - 自动探测文件大小与服务器是否支持 Range(分段下载)
    - 多线程「固定小分块 + 高并发 + 块级重试容错」下载：默认把文件切成 5MB 小块，
      由线程池消费任务队列，每块独立下载、独立重试(默认5次)，单块失败不影响其他块。
      ——专门解决国产 CDN「单连接限速 + 大块 Range 挂死」问题(见 references/troubleshooting.md)
    - 每个线程使用「原始 URL + curl -L」独立跟随 CDN 重定向，规避带鉴权参数
      的 CDN URL 过期问题（不会把 HTML 错误页当作文件内容写入磁盘）
    - Range 内容非零校验：部分国产 CDN 声称支持 Range 且返回 206，但 body 是全
      零字节。探测阶段实测一块数据，若 >95% 为零则判定该 CDN 的 Range 实现有
      缺陷，自动退化为单线程整文件下载
    - 抗 WAF / 限流自动回退：探测阶段若命中 WAF/限流类响应(如 418/429/401/403/503)，
      或分块下载时检测到服务器拒绝并发(Range 请求被拦)，立即停止并发并自动改用
      单线程整文件下载，避免对 WAF 反复重试放大封禁（详见 references/troubleshooting.md 坑七）
    - 断点续传(--resume)：多线程模式下跳过已完成的块(进度记录在 <输出>.mtd-progress)；
      单线程模式下用 curl -C - 续传循环(--max-time 600 + 自动重连)，专门兜底
      不稳定 CDN 的断流问题
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
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse

THREADS = 16
CHUNK_MB = 5                         # 多线程固定分块大小(MB)，小分块抗 CDN 限速挂死
MAX_RETRY = 5                        # 单块重试上限
PART_THRESHOLD = 4 * 1024 * 1024     # 小于此大小不分段(直接用单线程)
RANGE_PROBE_LEN = 16384              # Range 内容非零探测长度
RANGE_ZERO_RATIO = 0.05              # 非零字节占比低于此值(即 >95% 为零)判定 CDN 缺陷
PROGRESS_SUFFIX = ".mtd-progress"    # 断点续传进度文件后缀

# WAF / 限流 / 鉴权拦截类响应码：命中即说明服务器在主动拒绝并发或 Range，
# 应直接改用单线程整文件下载，避免反复重试放大封禁（如华为云 CloudWAF 返回 418 直接拉黑 IP）。
HTTP_HOSTILE = {401, 403, 407, 418, 429, 503}
# 网关/瞬态类响应码：可重试，持续失败再回退单线程。
HTTP_TRANSIENT = {408, 500, 502, 504, 509,
                  520, 521, 522, 523, 524, 525, 526, 527, 530}
RANGE_BROKEN = -2                    # 哨兵：服务器无视 Range，返回远超本块的内容


def _have_curl() -> bool:
    return shutil.which("curl") is not None


def _have_xattr() -> bool:
    return sys.platform == "darwin" and shutil.which("xattr") is not None


def _parse_status(hdr_path) -> int:
    """从 curl -D 写出的响应头文件里取最终 HTTP 状态码。

    带 -L 时文件里会有每一跳的响应头，取最后一行 HTTP 状态（即最终响应）。
    网络错误 / 无头文件时返回 -1。
    """
    try:
        text = Path(hdr_path).read_text(errors="replace")
    except Exception:
        return -1
    code = -1
    for line in text.splitlines():
        m = re.match(r"^HTTP/\S+\s+(\d{3})", line, re.IGNORECASE)
        if m:
            code = int(m.group(1))
    return code


class Bar:
    def __init__(self, total, label="", initial=0):
        self.total = total
        self.done = initial
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
    """通过 curl 获取文件大小、是否支持分段下载、以及是否存在 WAF/限流特征。

    返回 (size, supports_range, hostile)。探测统一使用原始 URL + -L 跟随重定向，
    避免依赖一次性的 CDN 鉴权 URL。hostile 为 True 表示已明确命中 WAF/限流类响应，
    上层应直接走单线程下载，避免对服务器发起并发 Range 请求而被封。
    """
    result = subprocess.run(
        ["curl", "-sIL", "--max-time", "15", "-o", "/dev/null",
         "-w", "SIZE:%{size_download}\nCL:%header{content-length}\n"
               "RANGE:%header{accept-ranges}\nCODE:%{response_code}",
         url],
        capture_output=True, text=True, timeout=20)
    size = 0
    supports_range = False
    hostile = False
    code = -1
    for line in result.stdout.strip().split("\n"):
        if line.startswith("SIZE:"):
            try:
                size = int(line.split(":", 1)[1])
            except ValueError:
                pass
        elif line.startswith("CL:"):
            if size == 0:
                try:
                    size = int(line.split(":", 1)[1])
                except ValueError:
                    pass
        elif line.startswith("RANGE:"):
            supports_range = "bytes" in line.lower()
        elif line.startswith("CODE:"):
            try:
                code = int(line.split(":", 1)[1])
            except ValueError:
                code = -1

    # HEAD 直接命中明确的 WAF/限流码(418/429)：直接判 hostile，不再发任何探测请求，
    # 避免对 WAF 发起后续 Range 请求触发 IP 封禁。
    if code in (418, 429):
        return size, False, True

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
        pcode = probe.stdout.strip()
        if pcode != "206":
            if pcode.isdigit() and int(pcode) in HTTP_HOSTILE:
                hostile = True
            supports_range = False

        # 第二步稳健性(针对国产 CDN 缺陷): 部分 CDN 返回 206 但 body 全是零字节。
        # 实测下载一块数据，若 >95% 为零则判定该 CDN 的 Range 实现有缺陷，
        # 退化为单线程整文件下载(整文件下载不受 Range 缺陷影响)。
        if supports_range and not _range_content_ok(url, size):
            supports_range = False

    return size, supports_range, hostile


def _range_content_ok(url, total_size) -> bool:
    """实测一块 Range 数据，判断是否真的返回了有效内容。

    为降低误判(某些正常文件开头恰好是零区)，优先测试文件「中部」区间；
    文件过小则测试开头。

    双重校验：
    1) 先用响应头看 Content-Length：若服务器无视 Range、把整文件塞回来，
       其 Content-Length 会是 total_size 而非请求段长度 → 识别「撒谎 Range」，
       直接判定不支持分段（否则多线程会把文件头部错写进每个分块）。
    2) 再下载一小段确认非零（防全零缺陷）。
    """
    if total_size <= 0:
        return True
    if total_size > RANGE_PROBE_LEN * 2:
        start = total_size // 2
    else:
        start = 0
    end = min(start + RANGE_PROBE_LEN, total_size) - 1
    expected = end - start + 1

    try:
        head = subprocess.run(
            ["curl", "-sL", "--max-time", "15", "-D", "-", "-o", "/dev/null",
             "-r", f"{start}-{end}", url],
            capture_output=True, text=True, timeout=20)
    except Exception:
        return False
    if head.returncode != 0:
        return False
    cl = 0
    for line in head.stdout.split("\n"):
        if line.lower().startswith("content-length:"):
            try:
                cl = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
    if cl > expected * 2:
        return False

    try:
        proc = subprocess.run(
            ["curl", "-sLf", "--max-time", "15", "-r", f"{start}-{end}", url],
            capture_output=True, timeout=20)
    except Exception:
        return False
    if proc.returncode != 0 or not proc.stdout:
        return False
    if len(proc.stdout) > expected * 4:
        return False
    non_zero = sum(1 for b in proc.stdout if b != 0)
    return non_zero >= len(proc.stdout) * RANGE_ZERO_RATIO


def _download_block(url, start, end, fd, max_retry):
    """下载单个固定小块 [start, end]。返回 (ok, code)。

    code 为服务器最终 HTTP 状态码(解析自 -D 响应头)；网络错误为 -1；
    服务器无视 Range 返回越界内容为 RANGE_BROKEN(-2)。

    关键稳健性:
    - 每个块都用「原始 URL + curl -L」独立重定向，规避 CDN 鉴权 URL 过期。
    - 精确读取本块字节数(need)，用 os.pwrite 按绝对偏移写，排空多余的响应体，
      避免越界覆盖其它块。
    - 探测阶段已校验非全零，流式写入安全；重试时重新整块覆盖同一偏移即可。
    - 命中 WAF/限流类码(HTTP_HOSTILE)立即返回，不再块内重试——
      由上层统一决策是否回退单线程，避免对 WAF 反复重试放大封禁。
    """
    need = end - start + 1
    for attempt in range(max_retry):
        hdr_name = None
        try:
            fd_h, hdr_name = tempfile.mkstemp(suffix=".hdr", prefix="mtd_")
            os.close(fd_h)
            proc = subprocess.Popen(
                ["curl", "-sL", "-D", hdr_name, "-o", "-", "--max-time", "60",
                 "-r", f"{start}-{end}", url],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            pos = start
            got = 0
            while got < need:
                buf = proc.stdout.read(min(65536, need - got))
                if not buf:
                    break
                os.pwrite(fd, buf, pos)
                pos += len(buf)
                got += len(buf)
            # 排空剩余数据（若服务器无视 Range 返回了超出本块的内容）
            while proc.stdout.read(65536):
                pass
            ret = proc.wait()
            code = _parse_status(hdr_name)
            if ret == 0 and got == need:
                return True, code
            if code in HTTP_HOSTILE:
                return False, code          # 立刻上报，停止重试
            if got > need * 4:
                return False, RANGE_BROKEN  # 撒谎 Range：返回了远超本段的内容
            # 其余(transient / 网络错 / 其它)按指数退避重试
        except Exception:
            pass
        finally:
            if hdr_name and os.path.exists(hdr_name):
                try:
                    os.unlink(hdr_name)
                except OSError:
                    pass
        time.sleep(min(2 ** attempt, 8))
    return False, -1


def _save_progress(progress_file: Path, done_set, total_chunks):
    """原子写入已完成块集合，供断点续传恢复。"""
    try:
        tmp = progress_file.parent / (progress_file.name + ".tmp")
        tmp.write_text(json.dumps({"total": total_chunks, "done": sorted(done_set)}))
        os.replace(tmp, progress_file)
    except Exception:
        pass


def _download_multi(url, out_path, total_size, threads, chunk_size, max_retry, resume):
    """多线程固定小分块下载 + 块级重试容错 + 断点续传。

    稳定性增强：分块下载时若检测到 WAF/限流/鉴权拦截(HTTP_HOSTILE)或服务端
    无视 Range(RANGE_BROKEN)，立即停止并发并自动回退单线程整文件下载；
    仅瞬时错误则先单线程补下失败块，仍失败再回退单线程。
    """
    chunks = []
    pos = 0
    cid = 0
    while pos < total_size:
        end = min(pos + chunk_size, total_size) - 1
        chunks.append((cid, pos, end))
        pos = end + 1
        cid += 1
    total_chunks = len(chunks)
    sys.stderr.write(
        f"  多线程小分块下载: {total_chunks} 块 × {chunk_size/1024/1024:.0f}MB, 并发 {threads}\n")

    # 预分配：resume 且文件已存在时保留已完成数据（用 r+b），
    # 否则新建并清空（wb）。注意 "wb" 会截断已有内容，续传时绝不能用。
    if resume and out_path.exists():
        f = open(out_path, "r+b")
    else:
        f = open(out_path, "wb")
    with f:
        f.truncate(total_size)
    fd = os.open(str(out_path), os.O_WRONLY)

    progress_file = out_path.with_name(out_path.name + PROGRESS_SUFFIX)
    done: set = set()
    if resume and progress_file.exists():
        try:
            j = json.loads(progress_file.read_text())
            if j.get("total") == total_chunks:
                done = set(j.get("done", []))
        except Exception:
            done = set()
    elif progress_file.exists():
        try:
            progress_file.unlink()
        except OSError:
            pass

    done_bytes = sum(e - s + 1 for (_, s, e) in chunks if _ in done)
    bar = Bar(total_size, out_path.name, initial=done_bytes)
    printer = threading.Thread(target=bar.print_thread, daemon=True)
    printer.start()

    errors = []
    failed_chunks = []
    saw_hostile = None          # 首个 hostile 码（None 表示未命中）
    saw_range_broken = False
    prog_lock = threading.Lock()
    try:
        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = {}
            for cid, s, e in chunks:
                if cid in done:
                    continue
                futures[pool.submit(_download_block, url, s, e, fd, max_retry)] = (cid, s, e)
            for fut in as_completed(futures):
                cid, s, e = futures[fut]
                ok, code = fut.result()
                if ok:
                    bar.add(e - s + 1)
                    with prog_lock:
                        done.add(cid)
                        _save_progress(progress_file, done, total_chunks)
                else:
                    errors.append(f"  分块{cid}({s}-{e}) 失败(code={code})")
                    failed_chunks.append((cid, s, e))
                    if code in HTTP_HOSTILE:
                        saw_hostile = code
                    elif code == RANGE_BROKEN:
                        saw_range_broken = True
                    # 命中 WAF/限流：立刻取消其余未开始任务，停止对 WAF 施压
                    if saw_hostile is not None:
                        for f2 in futures:
                            if f2 is not fut:
                                f2.cancel()
                        break
    finally:
        bar.alive = False
        printer.join(timeout=1)

    if not failed_chunks:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            progress_file.unlink()
        except OSError:
            pass
        if out_path.stat().st_size != total_size:
            sys.stderr.write("  ⚠ 文件大小与预期不符，可能下载不完整\n")
            return False
        sys.stderr.write(f"\n  ✅ 完成 → {out_path}\n")
        return True

    # 需要回退到单线程的情况
    if saw_hostile is not None:
        sys.stderr.write(
            f"  ⚠ 检测到服务器拒绝并发(WAF/限流, HTTP {saw_hostile})，"
            f"自动切换单线程下载避免被封\n")
    elif saw_range_broken:
        sys.stderr.write(
            "  ⚠ 检测到服务器无视 Range(返回越界内容)，自动切换单线程下载\n")
    else:
        # 仅瞬时失败：已完成的块保留，先尝试单线程逐个补下失败块
        sys.stderr.write(
            f"  ⚠ {len(failed_chunks)} 个分块持续失败，尝试单线程补下\n")
        refill_all_ok = True
        for cid, s, e in failed_chunks:
            ok, _ = _download_block(url, s, e, fd, max_retry)
            if ok:
                bar.add(e - s + 1)
                with prog_lock:
                    done.add(cid)
                    _save_progress(progress_file, done, total_chunks)
            else:
                refill_all_ok = False
        if refill_all_ok:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                progress_file.unlink()
            except OSError:
                pass
            if out_path.stat().st_size != total_size:
                sys.stderr.write("  ⚠ 文件大小与预期不符，可能下载不完整\n")
                return False
            sys.stderr.write(f"\n  ✅ 完成 → {out_path}\n")
            return True
        sys.stderr.write("  ⚠ 单线程补下仍失败，回退整文件单线程下载\n")

    # —— 回退：整文件单线程流式下载（覆盖半成品）——
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        out_path.unlink()
    except OSError:
        pass
    try:
        progress_file.unlink()
    except OSError:
        pass
    fb_bar = Bar(total_size, out_path.name)
    fb_printer = threading.Thread(target=fb_bar.print_thread, daemon=True)
    fb_printer.start()
    try:
        ok = _download_single(url, out_path, total_size, False, fb_bar)
    finally:
        fb_bar.alive = False
        fb_printer.join(timeout=1)
    if not ok:
        sys.stderr.write("  单线程回退下载也失败，已删除不完整的文件\n")
    return ok


def _curl_stream(url, out_path, total_size, bar):
    """单线程流式下载（从头），带 -f 防止错误页写入。"""
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
    if ok and total_size > 0 and out_path.stat().st_size != total_size:
        ok = False
        sys.stderr.write("  ⚠ 文件大小与预期不符，可能下载不完整\n")
    if not ok:
        try:
            out_path.unlink()
        except OSError:
            pass
        sys.stderr.write("  下载未完成，已删除不完整的文件\n")
    return ok


def _download_single(url, out_path, total_size, resume, bar):
    """单线程路径：不支持 Range / 文件过小 / 未知大小 / 强制单线程 / 多线程回退。

    支持 --resume 续传循环（curl -C - + --max-time 600 + 自动重连）。
    """
    if resume:
        attempt = 0
        while True:
            attempt += 1
            cur = out_path.stat().st_size if out_path.exists() else 0
            if total_size and cur >= total_size:
                bar.done = cur
                break
            sys.stderr.write(
                f"  [第{attempt}次续传] {cur/1024/1024:.0f}MB"
                + (f"/{total_size/1024/1024:.0f}MB" if total_size else "")
                + "\n")
            ret = subprocess.run(
                ["curl", "-sL", "--max-time", "600", "--connect-timeout", "30",
                 "-C", "-", "-o", str(out_path), url],
                capture_output=True).returncode
            new = out_path.stat().st_size if out_path.exists() else 0
            bar.done = new
            if total_size:
                if new >= total_size:
                    break
            else:
                if ret == 0:
                    break
            if ret != 0 and new <= cur:
                time.sleep(3)
        ok = (total_size == 0) or (out_path.stat().st_size == total_size)
        if not ok:
            try:
                out_path.unlink()
            except OSError:
                pass
            sys.stderr.write("  续传未完成，已删除文件\n")
        return ok
    else:
        # 从头下载（若已存在则覆盖）
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass
        sys.stderr.write("  单线程下载...\n")
        return _curl_stream(url, out_path, total_size, bar)


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


def download(url, out_name=None, threads=THREADS, chunk_mb=CHUNK_MB,
             max_retry=MAX_RETRY, expected_sha256=None, compute_checksum=True,
             clear_quarantine_flag=True, resume=False, overwrite=False,
             force_single=False):
    if not _have_curl():
        sys.stderr.write("❌ 未找到 curl，无法下载（需要系统自带 curl）\n")
        return False

    # 1. 探测
    sys.stderr.write("  正在探测服务器... ")
    sys.stderr.flush()
    total_size, supports_range, hostile = get_remote_info(url)
    if total_size == 0:
        sys.stderr.write("⚠ 无法获取文件大小，改用单线程流式下载\n")
    else:
        mode = "多线程分段" if (supports_range and total_size > PART_THRESHOLD and not hostile) else "单线程"
        sys.stderr.write(f"OK ({total_size/1024/1024:.0f}MB, {mode})\n")
        if hostile:
            sys.stderr.write("  ⚠ 探测到 WAF/限流特征，将使用单线程下载\n")

    # 2. 文件名
    if not out_name:
        path = urlparse(url).path
        out_name = unquote(path.split("/")[-1].split("?")[0])
        if not out_name:
            out_name = "download"
    out_path = Path(out_name).resolve()
    sys.stderr.write(f"  输出: {out_path}\n")

    # 3. 已存在文件策略
    progress_file = out_path.with_name(out_path.name + PROGRESS_SUFFIX)
    if out_path.exists():
        if overwrite:
            try:
                out_path.unlink()
            except OSError:
                pass
            try:
                progress_file.unlink()
            except OSError:
                pass
        elif resume:
            pass  # 保留文件，进入续传逻辑
        else:
            sys.stderr.write(
                f"❌ 输出文件已存在: {out_path}\n"
                f"   使用 --resume 断点续传，或 --overwrite 覆盖\n")
            return False

    # 4. 多线程 or 单线程
    use_multi = (total_size > 0 and supports_range
                 and total_size > PART_THRESHOLD and not force_single and not hostile)
    if use_multi:
        ok = _download_multi(url, out_path, total_size, threads,
                             chunk_mb * 1024 * 1024, max_retry, resume)
    else:
        bar = Bar(total_size, out_path.name)
        printer = threading.Thread(target=bar.print_thread, daemon=True)
        printer.start()
        try:
            ok = _download_single(url, out_path, total_size, resume, bar)
        finally:
            bar.alive = False
            printer.join(timeout=1)

    if not ok:
        return False

    # 5. SHA256 校验
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

    # 6. macOS 清除隔离标记
    if clear_quarantine_flag:
        clear_quarantine(out_path)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="多线程下载工具 (curl 引擎) — mtd-download",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="下载地址")
    parser.add_argument("-t", "--threads", type=int, default=THREADS,
                        help=f"并发数 (默认 {THREADS})")
    parser.add_argument("-o", "--output", default=None,
                        help="输出文件名 (默认从 URL 推断)")
    parser.add_argument("--chunk", type=int, default=CHUNK_MB,
                        help=f"多线程固定分块大小 MB (默认 {CHUNK_MB})，"
                             f"小分块抗 CDN 限速挂死")
    parser.add_argument("--max-retry", type=int, default=MAX_RETRY,
                        help=f"单块重试上限 (默认 {MAX_RETRY})")
    parser.add_argument("--single", action="store_true",
                        help="强制单线程下载")
    parser.add_argument("--resume", action="store_true",
                        help="断点续传（多线程跳过已完成块 / 单线程 curl -C - 续传循环）")
    parser.add_argument("--overwrite", action="store_true",
                        help="覆盖已存在的输出文件")
    parser.add_argument("--sha256", default=None,
                        help="官方 SHA256 值，下载后自动比对")
    parser.add_argument("--no-checksum", action="store_true",
                        help="不计算/打印 SHA256")
    parser.add_argument("--no-clear-quarantine", action="store_true",
                        help="macOS 上下载后不清除 Gatekeeper 隔离标记")
    args = parser.parse_args()

    ok = download(args.url, args.output, args.threads, args.chunk,
                  args.max_retry, expected_sha256=args.sha256,
                  compute_checksum=not args.no_checksum,
                  clear_quarantine_flag=not args.no_clear_quarantine,
                  resume=args.resume, overwrite=args.overwrite,
                  force_single=args.single)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
