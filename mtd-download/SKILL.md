---
name: mtd-download
description: Use this skill when downloading a large file over HTTP/HTTPS and a single connection is too slow. Multi-threaded range-based downloader (curl engine) that auto-detects server Range support, falls back to single-threaded streaming when Range is unavailable or file size is unknown, shows live progress/speed/ETA, and requires no pip dependencies.
---

# MTD Download

基于系统 `curl` 的多线程下载 skill。它把一个大文件按字节区间切成多段并行下载，服务器支持 `Range` 时显著提速；不支持、文件过小或拿不到大小时自动退回单线程流式下载。纯标准库 + 系统 `curl`，不需要 `pip install` 任何东西（和你本机无 sudo/无 Homebrew 的环境很搭）。

## 核心原则

- **探测优先，再决定策略**：先用 `curl -sIL` 跟随重定向拿最终响应的 `content-length` 和 `accept-ranges`，能分段且文件大于 4MB 才开多线程，否则单线程。
- **每个线程独立重定向，规避 CDN 鉴权过期**：多线程分块时每个线程都用「原始 URL + curl -L」独立跟随 CDN 重定向，不去共用探测阶段拿到的、带 `Expires/Signature` 的一次性鉴权 URL，避免部分线程被 CDN 拒绝、把 HTML 错误页当文件数据写入。
- **Range 内容非零校验**：部分国产 CDN 声称支持 Range 且返回 206，但 body 全是零字节。探测阶段实测下载一块数据（优先文件中部），若 >95% 为零则判定该 CDN 的 Range 实现有缺陷，自动退化为单线程整文件下载。
- **只写自己的区间**：多线程用 `os.pwrite` 按绝对偏移写，即使服务器无视 `Range` 返回了整文件，也只保留本分块该有的那一段，绝不会越界覆盖别人。
- **不留损坏文件**：多线程任一分块失败（或单线程 curl 返回非 0 / 大小不符），直接删掉不完整的输出，而不是默默留一个坏文件。
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

# 下载后比对官方 SHA256（不一致直接报错，保留文件供排查）
python scripts/mtd.py <URL> --sha256 <官方十六进制值>

# 不计算/打印 SHA256（超大文件可省去校验耗时）
python scripts/mtd.py <URL> --no-checksum

# macOS 上不清除 Gatekeeper 隔离标记
python scripts/mtd.py <URL> --no-clear-quarantine
```

## 行为说明

- **探测阶段**：打印文件大小、是否支持分段。
- **多线程路径**（支持 Range 且 > 4MB）：预分配文件 → 按线程数切片 → 各线程独立 `-L` 跟随重定向下载自己的区间 → 合并校验大小。
- **单线程路径**（不支持 Range / 文件 ≤ 4MB / 拿不到大小）：直接流式下载；拿不到大小时进度条显示 `??%`。
- **重试**：每个分块失败自动重试 3 次（递增退避）。
- **退出码**：成功 `0`，失败 `1`，方便脚本判断。
- **SHA256 校验**：默认下载后打印实际 SHA256 供核对；传 `--sha256` 时自动比对官方值，不匹配则报错（保留文件供排查）。大文件可用 `--no-checksum` 跳过以省去校验耗时。
- **macOS 隔离标记**：下载完成后自动 `xattr -c` 清除 `com.apple.quarantine`，避免双击 DMG 报「磁盘映像已损坏」；可用 `--no-clear-quarantine` 关闭。

## 适用边界

- 仅支持 HTTP/HTTPS（走 curl）。
- 依赖本机存在 `curl`；没有会直接报错退出，不会静默失败。
- 不做鉴权头、Cookie、断点续传（resume）、批量 URL、代理配置——这些是后续可增强项，需要的话告诉我。（SHA256 校验已支持，见上。）

## 参考文件

- `scripts/mtd.py`：下载引擎本体（多线程/单线程、进度条、重试、清理）。
- `scripts/update_self.py`：本 skill 的自检更新脚本（无 npm 依赖）。
