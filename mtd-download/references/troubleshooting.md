# 多线程下载踩坑手册（troubleshooting）

本文件沉淀真实环境下用自写多线程下载器拉大文件（Windows ISO、IntelliJ IDEA、麒麟 ARM64 ISO）时遇到的坑，以及 `mtd.py` 现在的对策。改下载引擎前先读一遍，避免把已修的坑再踩一遍。

---

## 坑一：Python urllib 被 Cloudflare CDN 拦截

**现象**：`python3 mtd.py "https://download.jetbrains.com/..."` 报 `HTTP Error 404`，但 `curl` 正常。

**根因**：JetBrains 的 CDN 后端是 **Cloudflare China**（响应头 `cf-ray` / `cf-cache-status: HIT`）。Cloudflare 按 TLS 指纹（JA3）拦截非浏览器客户端；Python `urllib`/`http.client`（macOS SecureTransport）的指纹不在白名单，直接被 404。

**对策（已实现）**：彻底不用 urllib，所有 HTTP 请求走**系统 `curl` 子进程**。

---

## 坑二：CDN 鉴权 URL 过期导致把 HTML 错误页当文件写入

**现象**：JetBrains IDEA 下载完 SHA256 不匹配，macOS 报"磁盘映像已损坏"。

**根因**：国内用户被 302 重定向到 Cloudflare China CDN，带 `Expires/Signature/Key-Pair-Id` 的鉴权 URL 有时效性。脚本若开始下载前取一次 CDN URL、多线程共用，部分线程的 Range 请求被 CDN 拒绝，返回 **HTML 错误页**；老脚本没开 `-f`，错误页被当文件内容写盘。

**对策（已实现）**：
- curl 带 `-f`：HTTP 错误码（≥400）返回非零退出码，错误页不会被写入。
- 每个线程传入**原始 URL + `-L`**，各自独立跟随重定向拿新的 CDN 签名 URL，不共用一次性的鉴权 URL。

---

## 坑三：CDN Range 请求返回全零数据

**现象**：麒麟 ARM64 ISO 下载完文件大小精确匹配，但 SHA256 完全不对；手动 `xxd` 发现 Range 返回的内容全是 `00`。

**根因**：部分国产 CDN（如 `iso.kylinos.cn`）的 HTTP Range 实现有缺陷——HEAD 声称支持 Range、Range GET 返回包含零填充的 body、Content-Length 仍正确、curl 退出码 0。

**对策（已实现）**：探测阶段实测下载一块数据（优先文件**中部**，避免正常文件开头恰好是零区），若 **>95% 为零**则判定该 CDN 的 Range 实现有缺陷，自动退化为**单线程整文件下载**（整文件下载不受 Range 缺陷影响）。

---

## 坑四（新）：CDN 单连接限速 + 大块 Range 挂死（间歇性）

**现象**：麒麟 ISO 单线程约每 10 分钟断流一次且越恢复越慢（330MB→19MB→11MB→挂死）；16 线程多线程一次就死（curl 退出码 56）。

**排查（Range 大小梯度测试）**：

| Range 大小 | 20 秒内下载量 | 结论 |
|-----------|------------|------|
| 5MB | 5MB（~0.8MB/s） | ✅ 正常 |
| 10MB | 7~8MB（0.4MB/s） | ⚠️ 开始限速 |
| 100MB | 0MB（挂死） | ❌ 直接挂死 |
| 1.2GB（旧 mtd.py 默认分块） | 卡死 | ❌ 挂死 |

**根因**：该 CDN 对**每个连接**限速 ~0.5MB/s，且 Range 请求越大越容易触发挂死（服务器停止发数据但连接不断开，curl 傻等超时）。旧 `mtd.py` 按 `总大小/线程数` 给每个线程切一大块（麒麟下 ≈1.2GB/块），挂死一块就阻塞整个线程池。

**附带发现**：该 CDN 故障是**间歇性**的——上午测 Range 返回全零（坑三），下午测数据正常。遇到"多线程失败"先重测一次当前状态，别急着换方案。

**对策（已实现 · 核心改进）**：多线程改为**固定 5MB 小分块 × 高并发线程池**，每块独立下载、独立重试（默认 5 次），**块级容错**——单块失败不影响其它块。小分块保证在限速生效前就下完，从根本上规避挂死。可用 `--chunk 2` 进一步调小分块、`--max-retry 8` 提高重试上限。

实测：从单线程 0.3MB/s 提升到 2.5MB/s（稳定），无卡死。

---

## 坑五（新）：下载中断与断点续传（不稳定 CDN 兜底）

**现象**：单线程下载时 CDN 断流，curl 进程 CPU 0% 傻等（`--max-time` 设太长），进度长期停滞。

**对策（已实现）**：
- **单线程**：`curl -C - --max-time 600 --connect-timeout 30` 续传循环，限制单次连接时长防无限傻等，断了自动重连直到 ≥ 总大小。用法：`python mtd.py <URL> --resume`（单线程路径自动走续传循环）。
- **多线程**：已完成块记录在 `<输出>.mtd-progress`，中断后同一命令加 `--resume` 只补下未完成块，不重下已完成的。

注意：`pgrep -f` 可能匹配到 zsh 包装进程导致监控误判"完成"，盯进度用日志里的百分比为准。

---

## 坑六：macOS Gatekeeper 隔离标记

**现象**：下载完成的 DMG 双击提示"磁盘映像已损坏"。

**根因**：macOS 为所有从网络下载的文件添加 `com.apple.quarantine` 隔离属性，对非 App Store 签名的 DMG 有时无法正确验证，直接报"损坏"。

**对策（已实现）**：下载完成后自动 `xattr -c` 清除隔离标记；可用 `--no-clear-quarantine` 关闭。

---

## 工具演进

| 版本 | 引擎 | 解决 |
|------|------|------|
| v1 | Python urllib | —（被 Cloudflare 拦，弃用） |
| v2 | curl subprocess | 坑一 Cloudflare 拦截 |
| v3 | curl subprocess | 坑二 鉴权 URL 过期（`-Lf` + 原 URL） |
| v4 | curl subprocess | 坑三 全零 Range（预检测 + 退化单线程） |
| **mtd-download 当前** | curl + 线程池 | 坑四 小分块高并发 + 块级容错；坑五 断点续传；坑六 Gatekeeper 清除 |

## 各文件 CDN 经验参考

| 文件 | CDN | Range 可用 | 建议方式 |
|------|------|------|------|
| 微软 Windows ISO | Azure CDN | ✅ | 多线程（默认） |
| JetBrains IDEA | Cloudflare China | ✅（需 `-L` 重定向） | 多线程（默认） |
| 麒麟 ISO | iso.kylinos.cn | ⚠️ 间歇性异常（全零/限速挂死） | `--chunk 2 --max-retry 8`；若探测判全零则自动单线程 |
