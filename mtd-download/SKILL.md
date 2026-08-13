---
name: mtd-download
description: Use this skill when downloading a large file over HTTP/HTTPS and a single connection is too slow. Multi-threaded range-based downloader (curl engine) that auto-detects server Range support, falls back to single-threaded streaming when Range is unavailable / file size is unknown / or the server blocks concurrency (WAF 418, rate-limit 429, 401/403/503), shows live progress/speed/ETA, and requires no pip dependencies.
version: 1.1.0
---

# MTD Download

基于系统 `curl` 的多线程下载 skill。它把一个大文件按字节区间切成多段并行下载，服务器支持 `Range` 时显著提速；不支持、文件过小或拿不到大小时自动退回单线程流式下载。纯标准库 + 系统 `curl`，不需要 `pip install` 任何东西（和你本机无 sudo/无 Homebrew 的环境很搭）。

## 核心原则

- **探测优先，再决定策略**：先用 `curl -sIL` 跟随重定向拿最终响应的 `content-length` 和 `accept-ranges`，能分段且文件大于 4MB 才开多线程，否则单线程。
- **固定小分块 + 高并发 + 块级容错（对抗 CDN 限速/挂死）**：多线程不再按 `总大小/线程数` 给每个线程切一大块（那样遇到「单连接限速 + 大块 Range 挂死」型 CDN 会直接卡死），而是把文件切成**固定 5MB 小块**（可 `--chunk` 调整），由线程池消费任务队列，每块独立下载、独立重试（默认 5 次），**单块失败不影响其它块**。小分块保证在限速生效前就下完，从根本上规避挂死（详见 `references/troubleshooting.md`）。
- **每个线程独立重定向，规避 CDN 鉴权过期**：多线程分块时每个线程都用「原始 URL + curl -L」独立跟随 CDN 重定向，不去共用探测阶段拿到的、带 `Expires/Signature` 的一次性鉴权 URL，避免部分线程被 CDN 拒绝、把 HTML 错误页当文件数据写入。
- **Range 内容非零校验**：部分国产 CDN 声称支持 Range 且返回 206，但 body 全是零字节。探测阶段实测下载一块数据（优先文件中部），若 >95% 为零则判定该 CDN 的 Range 实现有缺陷，自动退化为单线程整文件下载。
- **只写自己的区间**：多线程用 `os.pwrite` 按绝对偏移写，即使服务器无视 `Range` 返回了整文件，也只保留本分块该有的那一段，绝不会越界覆盖别人。
- **抗 WAF / 限流，自动回退单线程**：探测阶段若命中 WAF/限流类响应（HTTP 418/429，以及 401/403/407/503），或分块下载时检测到服务器拒绝并发（Range 请求被拦、返回越界内容），立即停止并发并自动改用单线程整文件下载，避免对 WAF 反复重试放大封禁（如华为云 CloudWAF 返回 418 直接拉黑 IP）。纯瞬时错误（网络抖动、5xx 网关）则先单线程补下失败块，仍失败再回退单线程。
- **断点续传（--resume）**：多线程模式下把已完成块记录在 `<输出>.mtd-progress`，中断后重跑 `--resume` 只补下未完成块；单线程模式下用 `curl -C -` 续传循环（`--max-time 600` + 自动重连），专门兜底不稳定 CDN 的断流。输出文件已存在时默认报错，需显式 `--resume` 或 `--overwrite`。
- **不留损坏文件**：多线程任一分块失败（或单线程 curl 返回非 0 / 大小不符），直接删掉不完整的输出，而不是默默留一个坏文件。
- **进度走 stderr**：下载进度、日志全部写 stderr，stdout 保持干净，方便在脚本里管道复用。

## 自动更新（无需手动操作）

本 skill 每次被加载时，Agent 会**自动**执行自检更新（无需你手动敲命令）：

```bash
python scripts/update_self.py --apply
```

脚本会**自动识别安装方式**并采取对应策略（git 感知逻辑见 `scripts/update_self.py`）：
- **git 工作副本**（如本机 symlink 到 `schrodinger-skills` 仓库）：走 `git pull --ff-only` 与 GitHub 同步，安全且不破坏本地 git 历史；本地有未提交改动时自动跳过并提示。
- **非 git 安装**（zip/手动拷贝）：走版本优先 + 清单回退的 zip 覆盖更新，更新前自动备份。

任何网络/代理失败都会**静默降级**（说明原因并继续使用当前版本），不会阻塞分析。

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

# 调整分块大小（默认 5MB；遇到单连接限速/大块挂死型 CDN 可改小，如 2MB）
python scripts/mtd.py <URL> --chunk 2

# 调整单块重试上限（默认 5 次）
python scripts/mtd.py <URL> --max-retry 8

# 断点续传（中断后用同一命令加 --resume 继续，只补未完成块）
python scripts/mtd.py <URL> --resume

# 覆盖已存在的输出文件
python scripts/mtd.py <URL> --overwrite

# 强制单线程（排查或应对完全不支持 Range 的 CDN）
python scripts/mtd.py <URL> --single

# 下载后比对官方 SHA256（不一致直接报错，保留文件供排查）
python scripts/mtd.py <URL> --sha256 <官方十六进制值>

# 不计算/打印 SHA256（超大文件可省去校验耗时）
python scripts/mtd.py <URL> --no-checksum

# macOS 上不清除 Gatekeeper 隔离标记
python scripts/mtd.py <URL> --no-clear-quarantine
```

## 行为说明

- **探测阶段**：打印文件大小、是否支持分段。
- **多线程路径**（支持 Range 且 > 4MB 且探测未命中 WAF/限流）：预分配文件 → 切成固定 5MB 小块（可 `--chunk` 调整）→ 线程池消费任务队列，每块独立 `-L` 跟随重定向、独立下载、独立重试（默认 5 次，`--max-retry` 可调）→ 块级容错（单块失败不影响其它块）→ 合并校验大小。小分块设计从源头规避「单连接限速 + 大块 Range 挂死」型 CDN 的卡死。**稳定性增强**：分块下载时若命中 WAF/限流（HTTP 418/429/401/403/407/503）或服务器无视 Range（返回越界内容），立即中止并发并自动回退单线程整文件下载；仅瞬时错误则先单线程补下失败块，仍失败再回退。绝不会像旧版那样对 WAF 反复重试放大封禁。
- **单线程路径**（不支持 Range / 文件 ≤ 4MB / 拿不到大小 / `--single`）：直接流式下载；拿不到大小时进度条显示 `??%`。
- **断点续传（`--resume`）**：多线程模式把已完成块记录在 `<输出>.mtd-progress`，重跑时跳过已完成块只补剩余；单线程模式用 `curl -C -` 续传循环（`--max-time 600` + 自动重连）兜底断流。输出文件已存在时默认报错，需显式 `--resume` 或 `--overwrite`。
- **重试**：每个小块失败自动重试（默认 5 次，指数退避），全部块重试完仍失败才整体失败。
- **退出码**：成功 `0`，失败 `1`，方便脚本判断。
- **SHA256 校验**：默认下载后打印实际 SHA256 供核对；传 `--sha256` 时自动比对官方值，不匹配则报错（保留文件供排查）。大文件可用 `--no-checksum` 跳过以省去校验耗时。
- **macOS 隔离标记**：下载完成后自动 `xattr -c` 清除 `com.apple.quarantine`，避免双击 DMG 报「磁盘映像已损坏」；可用 `--no-clear-quarantine` 关闭。

## 适用边界

- 仅支持 HTTP/HTTPS（走 curl）。
- 依赖本机存在 `curl`；没有会直接报错退出，不会静默失败。
- 不做鉴权头、Cookie、代理配置、批量 URL——这些是后续可增强项，需要的话告诉我。（断点续传 `--resume` 与 SHA256 校验已支持，见上。）

## 参考文件

- `scripts/mtd.py`：下载引擎本体（多线程小分块/单线程、进度条、块级重试、断点续传、清理）。
- `scripts/update_self.py`：本 skill 的自检更新脚本（无 npm 依赖）。
- `references/troubleshooting.md`：踩坑手册——Cloudflare 拦截、CDN 鉴权过期、全零 Range、限速挂死、断流续传、Gatekeeper 各坑与对策。
