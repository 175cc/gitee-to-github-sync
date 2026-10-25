# Gitee to GitHub Sync

定时检查 Gitee 个人仓库，并在 GitHub 个人账号下创建缺少的同名仓库后镜像推送分支和标签。

## 配置

1. 在 GitHub 创建用于运行 Actions 的仓库，并将本项目文件放入仓库。
2. 在仓库的 **Settings → Secrets and variables → Actions** 中添加两个 Repository secrets：
	- `GH_TOKEN`：GitHub Personal Access Token。Classic token 需要 `repo`；Fine-grained token 需要创建仓库权限及目标仓库内容写入权限。
	- `GITEE_TOKEN`：有权读取目标 Gitee 仓库的私人令牌。
3. 在同一设置页的 **Variables** 中添加 `GITEE_USER`，值为 Gitee 用户名（不是显示名称）。
4. 在 Actions 页面手动运行 **Gitee to GitHub Sync** 工作流。验证无误后，它会每 6 小时自动运行一次。

工作流通过 GitHub API 获取当前令牌所属账号，因此不需要额外配置 GitHub 用户名。Gitee API 会读取令牌可访问的个人仓库。

## 同步行为

- 目标仓库不存在时，按 Gitee 仓库的名称、公开/私有状态和描述创建。
- 对已有或刚创建的目标仓库执行镜像推送，包含所有分支和标签；后续运行会推送更新。
- 不会删除 GitHub 上多余的仓库，但 `git push --mirror` 会让目标仓库的 refs 与 Gitee 对齐，可能删除只存在于 GitHub 的分支或标签。请勿在目标仓库单独维护 refs。
- 这里只同步 Git 数据，不复制 Issues、Pull Requests、Wiki 设置或其他平台元数据。

首次使用建议先用一个测试仓库验证令牌权限、私有仓库访问和同步结果。不要把 Token 写入仓库文件。
