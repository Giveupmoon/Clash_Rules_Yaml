# Clash Rules & Config

专为 **Clash** 内核及 OpenWrt (Nikki / OpenClash) 等环境量身定制的高性能模块化分流配置。

本项目结合 **Sub-store** 订阅管理、**MRS 高性能二进制规则集** 以及精选应用图标，提供轻量、低内存占用且清晰的分流体验。

---

## 🌟 特性

* ⚡ **高性能 MRS 规则**：全面采用 Meta 二进制规则集（`format: mrs`），显著降低规则解析内存占用，毫秒级加载。
* 🎯 **精准分流设计**：内置 AI 服务（ChatGPT/Gemini）、流媒体平台（YouTube/Netflix/Disney+）、游戏平台与国外媒体的细分策略组。
* 🛡️ **TUN & 透明代理优化**：适配路由环境的 TUN 混合模式（Mixed Stack）与流量嗅探（Sniffer），支持端点独立 NAT 与 Fake-IP 防污染。
* 🎨 **策略组视觉美化**：内置自托管与社区精选应用图标，仪表盘（Zashboard/Metacubexd）展示清晰统一。
* 🧩 **锚点模块化**：高度复用 YAML 锚点（Anchors），便于快速调整订阅筛选正则与策略排序。

---

## 📁 目录结构说明

```text
.
├── Rules/                          # 私人规则
│   ├── Giveup_Direct/              # 直连规则
│   └── Giveup_Proxy/               # 代理规则
├── Icon/                           # 策略组与分类图标资源
│   ├── HOMOMIX/                    # 彩色应用与国家/地区图标
│   └── IconResource/               # 高清矢量/应用大图标
├── Start.yaml                      # Clash / Nikki 完整主配置文件
├── Clash-auto-update-nikki.sh      # 自动内核更新脚本
├── My-config.yaml                  # 个人配置
└── README.md

```

两份配置文件仅格式不同 内容完全相同

---

## 🚀 快速上手

### 1. 修改订阅节点

在主配置文件 `Start.yaml` 中找到 `proxy-providers`，替换为你的实际订阅地址（推荐配合 Sub-store 产出的通用订阅使用）：

```yaml
proxy-providers:
  Sub-store:
    <<: *BaseProvider
    url: "订阅链接请复制通用订阅"

```

### 2. 核心分流架构

* **前置分流**：局域网私有网段直连、自定义直连/代理规则、国内特定服务（Google CN、Steam CDN、下载平台）。
* **业务分流**：
* 💬 **即时通讯 / 社交媒体**：Telegram、Twitter、Facebook 等（默认优先香港节点）。
* 🤖 **AI 与生产力**：ChatGPT、Claude、Gemini、GitHub（针对性路由至稳定地区）。
* 🎬 **流媒体影音**：YouTube、Netflix、Disney+、Spotify、Bahamut（巴哈姆特走台湾节点，其余走新加坡/香港）。


* **兜底策略**：规则之外的走 `漏网之鱼` 兜底，非特殊需求建议兜底代理保证流畅的外网体验。

---

## ⚙️ 常见适配建议

* **OpenWrt / Nikki 环境**：
* 本配置基于裸核环境运行，其他运行环境自行测试。
* 请确认已通过面板或命令行下载最新的 `GeoSite.dat` 与 `GeoIP.dat`。
(虽然说用不到就是了 但是自行下载能减少一行日志警告   bushi)



---

## 📜 鸣谢与规则来源

* 内核引擎：[MetaCubeX/Clash](https://www.google.com/search?q=https://github.com/MetaCubeX/Clash)
* 规则数据集：[MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat)
* 社区规则补充：[Aethersailor/Custom_OpenClash_Rules](https://github.com/Aethersailor/Custom_OpenClash_Rules)
* Web 面板：[Zephyruso/zashboard](https://github.com/Zephyruso/zashboard)