# Application package scaffolds

每个应用目录代表一个独立的 AgentOS/Mint 应用包组装边界：

```text
<app>/
├── mint.toml                 # 应用工程阶段的 Mint 清单脚手架
├── README.md
├── packaging/                # 外部源码引用和后续构建映射
│   ├── README.md
│   └── source-ref.toml
└── files.manifest            # 稳定后记录进入制品的文件边界
```

产品源码仍在外部仓库；完成构建、安装和 conformance 后，才生成并发布 Mint `kind = "app"` 制品。
