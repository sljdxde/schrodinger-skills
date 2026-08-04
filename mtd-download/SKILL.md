---
name: mtd-download
description: Use this skill when downloading a large file over HTTP/HTTPS and a single connection is too slow. Multi-threaded range-based downloader (curl engine) that auto-detects server Range support, falls back to single-threaded streaming when Range is unavailable or file size is unknown, shows live progress/speed/ETA, and requires no pip dependencies.
---

# MTD Download

基于系统 `curl` 的多线程下载 skill。它把一个大文件按字节区间切成多段并行下载，服务器支持 `Range` 时显著提速；不支持、文件过小或拿不到大小时自动退回单线程流式下载。纯标准库 + 系统 `curl`，不需要 `pip install` 任何东西（和你本机无 sudo/无 Homebrew 的环境很搭）。

## 核心原则

- **探测优先，再决定策略**：先用 HEAD 请求拿 `content-length` 和 `accept-ranges`，能分段且文件大于 4MB 才开多线程，否则单线程。
- **只写自己的区间**：多线程用 `os.pwrite` 按绝对偏移写，即使服务器无视 `Range` 返回了整文件，也只保留本分块该有的那一段，绝不会越界覆盖别人。
- **不留损坏文件**：多线程任一分块失败，直接删掉不完整的输出，而不是默默留一个坏文件。
- **进度走 stderr**：下载进度、日志全部写 stderr，stdout 保持干净，方便在脚本里管道复用。

## 使用前自检更新

每次使用本 skill 前，先运行：

```bash
python scripts/update_self.py --apply
```

该脚本会检查 GitHub 上 `mtd-download` 目录是否有更新，发现更新时先备份本地 skill，再自动同步最新文件。若脚本显示已更新，重新读取当前 `SKILL.md` 后再继续；若网络或环境导致更新失败，说明失败原因并继续使用当前版本。

## 使用方式

直接让 Agent 说：

```
用 mtd-download 下载这个大文件：https://example.com/big-file.iso
```

或者显式指定线程数与输出名：

```
用 mtd-download 下载 https://example.com/big-file.iso，开 32 个线程，存成 big-file.iso
```

Agent 会运行下面的命令完成下载：

```bash
# 基本用法（默认 16 线程，自动从 URL 推断文件名）
python scripts/mtd.py <URL>

# 指定线程数
python scripts/mtd.py <URL> -t 32

# 指定输出文件名
python scripts/mtd.py <URL> -o myfile.iso

# 两者组合
python scripts/mtd.py <URL> -t 32 -o myfile.iso
```

## 行为说明

- **探测阶段**：打印文件大小、是否支持分段。
- **多线程路径**（支持 Range 且 > 4MB）：预分配文件 → 按线程数切片 → 各线程独立 `-L` 跟随重定向下载自己的区间 → 合并校验大小。
- **单线程路径**（不支持 Range / 文件 ≤ 4MB / 拿不到大小）：直接流式下载；拿不到大小时进度条显示 `??%`。
- **重试**：每个分块失败自动重试 3 次（递增退避）。
- **退出码**：成功 `0`，失败 `1`，方便脚本判断。

## 适用边界

- 仅支持 HTTP/HTTPS（走 curl）。
- 依赖本机存在 `curl`；没有会直接报错退出，不会静默失败。
- 不做鉴权头、Cookie、断点续传（resume）、校验和验证、批量 URL、代理配置——这些是后续可增强项，需要的话告诉我。

## 参考文件

- `scripts/mtd.py`：下载引擎本体（多线程/单线程、进度条、重试、清理）。
- `scripts/update_self.py`：本 skill 的自检更新脚本（无 npm 依赖）。
