## 最终代码与附件

正式代码 commit：`a9e536fc1bba53d287e6d75cce32600b0daadffc`，分支 `codex/rsi-toolkit-delivery`，本机仓库工作区干净。

| 附件 | 内容 |
| --- | --- |
| [对应源码](https://modelbest.feishu.cn/file/QCtlburGNoHlkrxOax3crBv2n8g) | 完整源码、宿主包、使用资料、设计和测试 |
| [Git bundle](https://modelbest.feishu.cn/file/XtXPbOLTGo5uR3xxTmNcnXsonGf) | 完整可恢复提交历史与交付分支 |
| [服务 wheel](https://modelbest.feishu.cn/file/JY99bzTjEoVQYAxXvX7c6nl3nme) | Python 3.13 服务发行包；宿主包由源码安装 |
| [服务 sdist](https://modelbest.feishu.cn/file/I9hFbzJGboWi9YxLoSgc9liunoe) | 可重新构建 wheel 的源码发行包 |
| [实验与测试证据](https://modelbest.feishu.cn/file/FiFwbJEyMoKNhNxO7ZdcTgP0nMe) | 153 份筛选证据、截图、视频、原始失败、二轮和 JUnit |
| [制品 manifest](https://modelbest.feishu.cn/file/JiFdb47u5oOb6Ixj2L1cHbzFnIe) | commit、逐文件 SHA-256、字节数与扫描范围 |
| [SHA256SUMS](https://modelbest.feishu.cn/file/UX7lb5a6wo1B0Dx9cZpcKfc1nxb) | 六个归档文件的完整校验和 |
| [实验与二轮回放，39.72 秒](https://modelbest.feishu.cn/file/NIhabFn1tojdTbxKmBTcarrWnTd) | 保存事件回放，含 diff、生命周期、冻结对照与真实第二轮 |
| [双宿主插件回放，21.96 秒](https://modelbest.feishu.cn/file/CIsybWEQrokbnax7oJAcepeRnId) | 真实 Skill/MCP 消费与明确标记的 scripted 探针 |

全部上传调用明确指定用户给定文件夹。9 个附件 token 均通过 Drive 元数据回查，文件名和链接一致。目录列表接口缺少 `space:document:retrieve` scope，因此没有声称完成目录列表回读；无需为已完成上传重新授权。

本地制品：`/private/tmp/rsi-delivery-20261027/`。源码包和 Git bundle 均已校验，bundle 包含完整历史，全部 SHA-256 校验通过。归档检查了 5 个实际私密值，证据、源码与 Git 全部对象无匹配；私人配置和 token 文件未上传。

证据包 SHA-256：`0f2ab19d8e316e6bdc7a602aebf6a944668a9a2839b1f758c8687b7b37abcf29`。

恢复仓库可执行：

```sh
git clone rsi-toolkit.git.bundle rsi-toolkit
git -C rsi-toolkit checkout codex/rsi-toolkit-delivery
```

源码、文件名和命令以本地制品为准；云端附件名称增加了交付日期或短 SHA 便于辨认。服务与查看器的本机地址仅供同一台机器访问，其他机器按产品 README 启动。
