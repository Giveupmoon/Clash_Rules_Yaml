# Clash Rule Management Telegram Bot

一个轻量级、无状态的自适应 Telegram Bot，用于在移动端或桌面端随时随地管理 GitHub 仓库中的规则文件。

该机器人采用单文件架构设计，支持 Docker 容器化一键部署，适合作为个人网络规则库的自动化无人值守管家。

## ✨ 核心特性

* **📱 极简交互**：直接向机器人发送 域名、IPv4 或 IPv6 即可触发流程，无需繁琐的命令。
* **🔍 全局查重**：跨文件自动检索目标规则，若存在则直达“删除确认”面板，防止规则冗余。
* **✍️ 强制备注注释**：添加新规则时强制要求输入用途备注，自动格式化为 `规则 # 备注` 追加到 YAML 中，让规则后期拥有可读性并保证解析安全。
* **🌐 智能协议识别**：自动判断 IPv4 与 IPv6，并精准映射至 `IP-CIDR` 和 `IP-CIDR6`，支持网段解析。
* **🛡️ 鉴权与安全**：基于私有 `User ID` 的严格访问控制，并内置 60 秒会话超时机制，避免资源与状态长期挂起。
* **🐳 Docker 开箱即用**：一行命令即可拉起服务。

---

## 🚀 快速部署 (Docker Compose)

推荐使用 Docker Compose 部署，能够完美隔离运行环境。

### 1. 获取配置文件（⭐ 核心步骤）

请先在你的服务器新建一个存放机器人的目录，并下载本仓库中提供的环境变量模板 `.env` 与容器编排文件 `docker-compose.yml`。

你可以通过 `wget` 直接下载，或者克隆本仓库：

```bash
mkdir clash-bot && cd clash-bot
wget https://raw.githubusercontent.com/Giveupmoon/Clash_Rules_Yaml/main/Rule-Bot/docker-compose.yml
wget https://raw.githubusercontent.com/Giveupmoon/Clash_Rules_Yaml/main/Rule-Bot/.env

```

### 2. 修改环境变量

打开刚刚下载的 `.env` 文件，填入你自己的专属配置：

```bash
nano .env

```

---

## ⚙️ 环境变量配置参考字典

| 变量名 | 是否必填 | 说明 |
| --- | --- | --- |
| `TG_BOT_TOKEN` | ✅ | Telegram Bot 访问凭证 |
| `ALLOWED_USER_ID` | ✅ | 你的 Telegram 用户 ID（可通过 @userinfobot 获取） |
| `GITHUB_TOKEN` | ✅ | GitHub 个人访问令牌 |
| `GITHUB_REPO` | ✅ | 目标规则仓库路径 |
| `RULES_DIR` | ❌ | 规则文件在仓库中的相对目录，留空表示仓库根目录。|
| `RULE_FILES` | ✅ | 挂载文件列表，格式为 `面板别名:仓库文件名, 别名2:文件名2`。|

---

### 3. 启动容器

确保 `.env` 与 `docker-compose.yml` 在同一目录下，执行以下命令拉取镜像并后台启动：

```bash
docker compose up -d

```

使用 `docker compose logs -f` 可查看实时运行日志。



## 📖 使用指南

### 支持的快捷指令

* `/start` 或 `/menu`：呼出图形化常驻主面板，显示当前仓库与挂载的规则文件。
* `/view`：选择并拉取查看指定文件的最新 8 条规则预览与总条数。
* `/help`：查看详细的操作提示。
* `/cancel`：立刻中断当前正在进行的等待操作。

### 核心工作流

1. **添加规则**：向 Bot 发送 `google.com` 或 `1.1.1.1`，Bot 将确认该规则不存在，随后询问你追加至哪个文件、采用何种规则格式（如 `DOMAIN-SUFFIX`）。选定后输入文本备注，Bot 将自动完成 GitHub 提交。
2. **删除规则**：直接发送要删除的域名或 IP，如果查重命中，Bot 会列出所有匹配项。点击指定项进行二次确认后，Bot 会自动从仓库抹除该条规则。

---

## 👨‍💻 二次开发与源码运行

如需在不使用 Docker 的情况下直接运行源码：

1. 克隆本仓库目录并进入 `Rule-Bot` 文件夹。
2. 配置虚拟环境并安装依赖：
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

```


3. 编辑本地的 `.env` 文件填入各项参数。
4. 执行启动命令：
```bash
python bot.py

```