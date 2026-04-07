## 📦 目录结构

```
.
├── README.md              ← 项目说明（这个文件）
├── Start.yaml             ← 核心配置样例，可直接用于 Clash
└── Rules/                 ← 规则提供者（Rule‑Set）各类规则文件
    ├── Giveup_Direct.yaml
    ├── Giveup_Proxy.yaml
    └── …
```

---

## 说明：

* `giveup_direct` 和 `giveup_proxy` 是本仓库私人规则，可按需引用；

---


---

## 🚀 快速开始（Start.yaml）

仓库中的 `Start.yaml` 是一个完整的 Clash 配置样例，包含：

* 核心配置（端口、DNS、泛用设置）
* 多种策略组
* 常见规则调用
* 内置 rule‑providers 引用格式

你可以将其下载，直接在你的 Clash 客户端中加载使用。([GitHub][1])
下载配置文件修改proxy-providers下的url: "url"为自己的订阅链接导入客户端使用即可。
多机场的路由用户推荐使用sub-store聚合后导入

---

---

## 📦 贡献与建议

欢迎：

* 提交新的规则文件（通过 Pull Request）

## 📄 License

本仓库无特别声明即遵循默认 GitHub 开源许可，请在使用中注明来源并遵守版权。

---