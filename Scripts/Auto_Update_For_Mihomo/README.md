# Mihomo 内核自动更新与切换工具

> 脚本路径：`scripts/Auto_Update_For_Mihomo/Auto_Update.sh`
> 返回上级：[Scripts 根导航](../)

`Auto_Update.sh` 是一个用于维护 Mihomo (Clash.Meta) 内核的 Shell 脚本。支持根据当前运行环境（Nikki、OpenClash 或独立 Linux）自适应核心路径与服务启停，根据 CPU 指令集匹配最优构建，并支持 **官方源 (MetaCubeX)** 与 **Smart 源 (vernesong)** 双分支，以及 **Release 稳定版** 与 **Alpha 预发布版** 双通道的无缝互切与自动更新。

---

## 核心特性

* **环境与应用感知**：
* **Nikki**：核心路径 `/usr/bin/mihomo`，通过 `/etc/init.d/nikki` 启停服务。
* **OpenClash**：核心路径 `/etc/openclash/core/clash_meta`，通过 `/etc/init.d/openclash` 启停服务。
* **通用 Linux**：核心路径 `/usr/local/bin/mihomo` 或 `/usr/bin/mihomo`，适配 systemd 服务。


* **共存冲突消解**：当系统同时安装了 Nikki 与 OpenClash 时，自动检测当前正在运行的进程进行匹配；同时提供 `--nikki` 与 `--openclash` 参数支持显式指定。
* **双内核分支支持 (Flavor)**：
* **Official 官方源**：对应 `MetaCubeX/mihomo` 官方仓库。
* **Smart 源**：对应 `vernesong/mihomo` 分支仓库。
* 支持一键切换内核分支，且**互切时严格继承当前版本通道**（如：官方 Alpha $\leftrightarrow$ Smart Alpha，官方 Stable $\leftrightarrow$ Smart Stable）。


* **架构与指令集优化**：x86_64 平台自动探查 CPU 是否支持 `v3` / `v2` / `v1` 并支持平滑降级；针对 Smart 内核自动识别并适配 `alpha-smart` 构建包；ARM / MIPS 平台自动匹配对应架构包。
* **双通道智能维护**：支持自动跟随当前分支与通道（Release / Alpha）升级，或使用 `-s` / `--switch` 实现通道一键反转。
* **安全保护**：更新前备份旧核心，遇到校验失败或损坏自动执行回滚，并维护最近指定数量的历史备份（默认保留 3 个）。

---

## 参数列表

| 参数 | 说明 |
| --- | --- |
| *(无参数)* | 默认行为：自动检测本地运行环境、内核来源与通道，拉取同分支同通道最新版本并热替换 |
| `--nikki` | 强制指定操作目标为 **Nikki**（核心路径 `/usr/bin/mihomo`） |
| `--openclash` | 强制指定操作目标为 **OpenClash**（核心路径 `/etc/openclash/core/clash_meta`） |
| `-t`, `--toggle-flavor` | **内核来源互切**：在官方源与 Smart 源之间互切（严格继承当前通道：Alpha 保持 Alpha，Release 保持 Release） |
| `--official` | 强制指定使用 **MetaCubeX 官方源** 核心 |
| `--smart` | 强制指定使用 **vernesong  (Smart 内核)** |
| `-s`, `--switch` | **通道反转切换**：在 Release 稳定版与 Alpha 预发布版之间互切（保持当前内核来源不变） |
| `--alpha` | 强制指定安装/更新至 GitHub 最新的 **Alpha** 预发布版本 |
| `--release` / `--stable` | 强制指定安装/更新至 GitHub 最新的 **Release** 稳定版本 |
| `-h`, `--help` | 显示命令行帮助信息 |

---

## 使用示例

### 1. 准备工作

赋予可执行权限：

```bash
chmod +x scripts/Auto_Update_For_Mihomo/Auto_Update.sh

```

*(可选)* 避免 GitHub API 匿名请求被限流，可提前注入 Personal Access Token（临时有效）

```bash
export GITHUB_TOKEN="ghp_your_token_here"

```

也可选择写入变量文件（长期有效）

```bash
echo 'export GITHUB_TOKEN="your_actual_token_here"' >> /etc/profile && source /etc/profile

```

### 2. 日常自动更新

保持本地内核来源与通道不变（例如当前为 Smart Alpha，则自动拉取 Smart Alpha 最新构建）：

```bash
sh Auto_Update.sh

```

### 3. 内核来源切换 (Official $\leftrightarrow$ Smart)

在保持当前通道不变的前提下，一键切换内核类型：

```bash
# 若当前为官方 Alpha，执行后自动切换为 Smart Alpha
# 若当前为 Smart Release，执行后自动切换为官方 Release
sh Auto_Update.sh -t

# 也可以直接指定切换为 Smart 内核
sh Auto_Update.sh --smart

```

### 4. 版本通道切换 (Release $\leftrightarrow$ Alpha)

在保持当前内核来源（Official 或 Smart）不变的前提下反转通道：

```bash
# 当前为 Release 则切换至 Alpha；当前为 Alpha 则切换回 Release
sh Auto_Update.sh -s

# 强制切换/回退为 Release 稳定版
sh Auto_Update.sh --release

```

### 5. 多插件共存时组合操作

当路由器中同时安装了 Nikki 与 OpenClash 时：

```bash
# 显式更新 OpenClash 的 Meta 核心为 Smart Alpha 版本
sh Auto_Update.sh --openclash --smart --alpha

# 显式将 Nikki 核心在官方与 Smart 之间互切
sh Auto_Update.sh --nikki -t

```

---
