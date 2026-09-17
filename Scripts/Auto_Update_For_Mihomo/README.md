# Mihomo 内核自动更新与切换工具

> 脚本路径：`scripts/Auto_Update_For_Mihomo/Auto_Update.sh`
> 返回上级：[Scripts 根导航](../)

`Auto_Update.sh` 是一个用于维护 Mihomo (Clash.Meta) 内核的 Shell 脚本。支持根据当前运行环境（Nikki、OpenClash 或独立 Linux）自适应核心路径与服务启停，根据 CPU 指令集匹配最优构建，并支持 Release 稳定版与 Alpha 预发布版的双通道无缝切换与自动更新。

---

## 核心特性

* **环境与应用感知**：
* **Nikki**：核心路径 `/usr/bin/mihomo`，通过 `/etc/init.d/nikki` 启停服务。
* **OpenClash**：核心路径 `/etc/openclash/core/clash_meta`，通过 `/etc/init.d/openclash` 启停服务。
* **通用 Linux**：核心路径 `/usr/local/bin/mihomo` 或 `/usr/bin/mihomo`，适配 systemd 服务。


* **共存冲突消解**：当系统同时安装了 Nikki 与 OpenClash 时，自动检测当前正在运行的进程进行匹配；同时提供 `--nikki` 与 `--openclash` 参数支持强制指定。
* **架构与指令集优化**：x86_64 平台自动探查 CPU 是否支持 `v3` / `v2` / `v1` 并支持平滑降级；ARM / MIPS 平台自动匹配对应架构包。
* **双通道智能维护**：支持自动跟随当前分支（Release / Alpha）升级，或使用 `--switch` 实现通道一键互切。
* **安全保护**：更新前备份旧核心，遇到校验失败或损坏自动执行回滚，并维护最近指定数量的历史备份（默认保留 3 个）。

---

## 参数列表

| 参数 | 说明 |
| --- | --- |
| *(无参数)* | 默认行为：自动检测本地运行环境与通道，拉取同通道最新版本并热替换 |
| `--nikki` | 强制指定操作目标为 **Nikki**（核心路径 `/usr/bin/mihomo`） |
| `--openclash` | 强制指定操作目标为 **OpenClash**（核心路径 `/etc/openclash/core/clash_meta`） |
| `-s`, `--switch` | 通道反转：当前为 Release 则切换至最新 Alpha；当前为 Alpha 则切换回最新 Release |
| `--alpha` | 强制指定安装/更新至 GitHub 最新的 **Alpha** 预发布版本 |
| `--release` / `--stable` | 强制指定安装/更新至 GitHub 最新的 **Release** 稳定版本 |
| `-h`, `--help` | 显示命令行帮助信息 |

---

## 使用示例

### 1. 准备工作

赋予可执行权限：

```bash
chmod +x scripts/mihomo/Auto_Update.sh

```

*(可选)* 避免 GitHub API 匿名请求被限流，可提前注入 Personal Access Token：

```bash
export GITHUB_TOKEN="ghp_your_token_here"

```

### 2. 日常自动更新

保持本地通道不变（Release 升 Release，Alpha 升 Alpha）：

```bash
./scripts/mihomo/Auto_Update.sh

```

### 3. 多插件共存时指定目标

当路由器中同时安装了 Nikki 与 OpenClash 时：

```bash
# 显式更新 OpenClash 的 Meta 核心
./scripts/mihomo/Auto_Update.sh --openclash

# 显式更新 Nikki 核心并切换为 Alpha 通道
./scripts/mihomo/Auto_Update.sh --nikki --alpha

```

### 4. 通道切换

一键互切当前通道：

```bash
./scripts/mihomo/Auto_Update.sh --switch
# 或使用短参数
./scripts/mihomo/Auto_Update.sh -s

```

强制回退/更新为稳定版 Release：

```bash
./scripts/mihomo/Auto_Update.sh --release

```

---

## 定时任务配置 (Crontab)

如果希望系统定期自动静默同步最新内核，可将其加入定时任务：

```cron
# 每天凌晨 04:30 自动检查当前运行内核的同通道更新
30 4 * * * /root/scripts/mihomo/Auto_Update.sh >/dev/null 2>&1

# 若同时安装了双插件，也可分开定时维护：
0 4 * * * /root/scripts/mihomo/Auto_Update.sh --nikki >/dev/null 2>&1
30 4 * * * /root/scripts/mihomo/Auto_Update.sh --openclash >/dev/null 2>&1

```