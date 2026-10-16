# Maryland GitHub 备份

最新主要工作快照为 `codex/maryland-main-work-20261016`，入口和恢复方法见 [2026-10-16 主要工作](MAIN_WORK_20261016.md)。下文保留 9 月 14 日完整备份的说明。

本次备份包含代码、PROJECT_MEMORY.md、研究数据、正式报告、图表和演示文稿。研究数据和二进制成果使用 Git LFS；现有 Git 提交历史作为备份提交的祖先保留。

## 恢复

安装 Git 与 Git LFS 后执行：

```sh
git lfs install
git clone --branch codex/maryland-backup-20260914 git@github.com:zhuangbige/Enso_space_23_24.git Maryland
cd Maryland
git lfs pull
```

恢复后先阅读根目录的 PROJECT_MEMORY.md。本机 Python/Conda 环境、安装包缓存、临时预览和工作树副本不纳入上传；请按项目 README 和 experiments/isca_runtime/environment-macos-arm64.yml 重建运行环境。

Isca 源代码按普通文件保存，包含本机已有的兼容性修改，不携带该依赖自身的 .git 目录。

清理记录见 reports/archive_cleanup_20260914.json。备份清单见 reports/github_backup_manifest_20260914.json。
