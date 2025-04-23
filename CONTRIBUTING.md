[fork]: /fork
[pr]: /compare
[pep8]: https://peps.python.org/pep-0008/
[code-of-conduct]: CODE_OF_CONDUCT.md
[uv]: https://docs.astral.sh/uv/
[pep484]: https://peps.python.org/pep-0484/

# 贡献指南

你好！我们很高兴你愿意为这个项目做出贡献。你的帮助对于保持该项目的良好发展至关重要。

请注意，该项目发布时附带[贡献者行为准则][code-of-conduct]。参与该项目即表示同意遵守其条款。

## 问题和 PR

如果对如何改进该项目有任何建议，或者想要报告错误，请打开 Issues！我们欢迎所有贡献。如果你有建议，我们也乐意听取。

我们也喜欢 PR。不过，如果你正在考虑大型 PR，我们建议你先打开一个问题来讨论它！如果不确定如何进行 PR，请查看下面的链接。

## 提交拉取请求

1. [Fork][fork] 并克隆存储库
2. 在项目根目录，使用 [uv][uv] 配置并安装依赖项：`uv venv -p 3.10 && uv sync --all-extras --all-groups`
3. 切换到虚拟环境：`source ./.venv/bin/activate`
4. 确保测试在你的机器上通过：`uv run poe test` 或 `pytest -c pytest.ini`
5. 创建新分支：`git checkout -b your-branch-name`
6. 进行更改，添加测试，并确保测试仍然通过
7. 使用 GPG 密钥签名提交，或使用 Github 在线编辑器来对提交自动签名
8. 推送到你的 fork 并 [提交拉取请求][pr]
9. 等待拉取请求被审核和合并

以下几件事可以增加拉取请求被接受的可能性：

- 遵循 [PEP8 样式指南][pep8] 并为代码添加类型注解 ([PEP 484][pep484])
- 进行格式化和代码检查，使用 `uv run poe all_lint`。这可能需要一些时间。
- 编写和更新测试。
- 尽可能集中更改。如果你想提交多个不相互依赖的更改，请考虑将它们作为单独的拉取请求提交。
- 填写清晰的提交消息，应该包含必要的解释说明。

我们也欢迎使用“仍在进行的拉取请求”，以便尽早获得反馈。

## 相关链接

- [如何为开源做出贡献](https://opensource.guide/how-to-contribute/)
- [使用 Pull Requests](https://help.github.com/articles/about-pull-requests/)
- [GitHub 帮助](https://help.github.com)

## Contributing

Hi there! We're thrilled that you'd like to contribute to this project. Your help is essential for keeping it great.

Please note that this project is released with a [Contributor Code of Conduct][code-of-conduct]. By participating in this project you agree to abide by its terms.

## Issues and PRs

If you have suggestions for how this project could be improved, or want to report a bug, open an issue! We'd love all and any contributions. If you have questions, too, we'd love to hear them.

We'd also love PRs. If you're thinking of a large PR, we advise opening up an issue first to talk about it, though! Look at the links below if you're not sure how to open a PR.

## Submitting a pull request

1. [Fork][fork] and clone the repository.
2. Use [uv][uv] Configure and install the dependencies: `uv venv -p 3.10 && uv sync --all-extras --all-groups` in the project root dir.
3. Run `source ./.venv/bin/activate` to activate venv.
4. Make sure the tests pass on your machine: `uv run poe test` or `pytest -c pytest.ini`
5. Create a new branch: `git checkout -b your-branch-name`.
6. Make your change, add tests, and make sure the tests still pass.
7. Sign your commits with a GPG key, or use the Github online editor to sign commits automatically.
8. Push to your fork and [submit a pull request][pr]. 
9. Pat your self on the back and wait for your pull request to be reviewed and merged.

Here are a few things you can do that will increase the likelihood of your pull request being accepted:

- Follow the [PEP8 style guide][pep8] and adding type hints ([PEP 484][pep484]) for your code
- For linting, use `uv run poe all_lint`. It may be takes a few seconds.
- Write and update tests.
- Keep your changes as focused as possible. If there are multiple changes you would like to make that are not dependent upon each other, consider submitting them as separate pull requests.
- Write a clear commit message, should including necessary comments.

Work in Progress pull requests are also welcome to get feedback early on, or if there is something blocked you.

## Resources

- [How to Contribute to Open Source](https://opensource.guide/how-to-contribute/)
- [Using Pull Requests](https://help.github.com/articles/about-pull-requests/)
- [GitHub Help](https://help.github.com)
