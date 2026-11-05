# Fixtures

开发与回归样本。验收金标不入仓库（08 §3）：正式验收样本由
`isolate_acceptance_samples` 在运行时登记进本地样本库（`data_root/vault/`），
金标只经 `evaluate_business_acceptance` 读取。
