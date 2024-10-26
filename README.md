<div align="center">
  <img width=256 src="https://github.com/Meloland/melobot/blob/main/docs/source/_static/logo.png?raw=true" />
  <h1>melobot</h1>
  <p>
    <strong>支持多协议、多路 IO 与其他高级特性的机器人开发框架</strong>
  </p>
  <p align="center">
    <a href="https://github.com/Meloland/melobot/tree/main/LICENSE-BSD"><img src="https://img.shields.io/badge/license-BSD--3--Clause-2ea44f" alt="license - BSD-3-Clause"></a>
    <a href="https://github.com/Meloland/melobot/tree/main/LICENSE-CC"><img src="https://img.shields.io/badge/license-CC--BY--SA--4.0-2ea44f" alt="license - CC-BY-SA-4.0"></a>
    <a href="https://docs.melobot.org/"><img src="https://img.shields.io/badge/doc-latest-blue.svg" alt="melobot docs"></a>
    <a href="https://github.com/Meloland/melobot"><img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/Meloland/melobot"></a>
  </p>
  <p align="center">
    <a href="https://python.org" title="Go to Python homepage"><img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-2ea44f?logo=python&logoColor=white" alt="Made with Python"></a>
    <a href="https://pypi.org/project/melobot/"><img alt="PyPI" src="https://img.shields.io/pypi/v/melobot"></a>
    <a href="https://pdm-project.org"><img src="https://img.shields.io/badge/PDM-Managed-purple?logo=pdm&logoColor=white" alt="PDM - Managed"></a>
  </p>
  <p>
    <a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
    <a href="https://mypy-lang.org/"><img src="https://www.mypy-lang.org/static/mypy_badge.svg" alt="Checked with mypy"></a>
    <a href="https://github.com/pylint-dev/pylint"><img src="https://img.shields.io/badge/Pylint-checked-blue" alt="Pylint - checked"></a>
  </p>
</div>

## 🔄 工作计划

melobot v3 pre-release 已发布。v3 支持各种协议以扩展至各种平台提供机器人服务。

v3 目前可用的协议实现：

- **OneBot**（melobot 内置支持，但尚未支持 v12 版本）

其他计划支持的协议：

- **Console**（melobot 内置支持，跨平台的控制台输入输出协议）
- **Satori**
- **Kritor**
- **qq 官方协议**
- ...

有任何对 melobot 项目的意见或建议，欢迎加入 qq 群与我们讨论：`535705163`

## ⚠️ 声明

melobot 是由热爱技术的开发者共同维护的开源项目。我们致力于提供一个可靠、高效的软件工具，以促进技术交流和创新。以下简称 melobot 项目为“本项目”。

本项目严禁用于任何非法目的，包括但不限于侵犯版权、商标、商业机密或其他知识产权，以及违反任何适用的法律和法规。我们不对因非法使用本项目而产生的任何直接、间接、附带、特殊、惩罚性或后果性损害承担责任。

<!-- start elevator-pitch -->

## 🎉 特色

melobot v3 是跨平台、跨协议、支持多路 IO 及其他高级特性的 bot 开发框架。为什么选择 melobot？因为 melobot 更**自由、优雅和强大**：

| 特性           | 描述                                                         |
| -------------- | ------------------------------------------------------------ |
| 实用接口       | 封装高频使用的异步逻辑，使业务开发更简洁                     |
| 插件管理       | 低耦合度、无序的插件加载与通信                               |
| 处理流设计     | 可自由组合“处理中间件”为处理流，提升了各组件的复用率         |
| 热插拔/重启 | 事件处理器支持动态热插拔，支持 bot 级别的重启                   |
| 会话支持       | 可在处理流中自动传递的、可自定义的会话上下文                 |
| 协议支持       | 所有协议被描述为 IO 过程，因此支持各类协议                   |
| 跨平台         | 更简洁的跨平台接口，便捷实现跨平台插件开发                   |
| 多路 IO        | 支持多个协议实现端同时输入，自由输出到指定协议实现端         |
| 日志支持       | 日志记录兼容标准库和绝大多数日志框架，可自行选择             |


使用本框架的机器人项目如下：

- [MeloInf](https://github.com/aicorein/meloinf)
- [MarshoAI](https://github.com/LiteyukiStudio/marshoai-melo)

你可以将这些项目作为 melobot 使用的实例参考。欢迎你基于 melobot 实现完整的机器人项目后，向本文档提出 PR，在此处展示。

## 💬 文档

项目文档：[melobot 文档](https://docs.melobot.org)

对于文档可能出现的纰漏，恳请各位包涵。欢迎提出修正和优化文档的 PR：[文档源文件](https://github.com/Meloland/melobot/tree/main/docs/source)

## 📦️ 安装使用

> Python 版本需求：>= 3.10

如果您对 melobot 完全不熟悉，建议配合文档开始学习。文档以 OneBot v11 协议为例，通过以下命令安装所有必要的组件：

```shell
pip install 'melobot[onebot]>=3.0.0rc13'
```

如果您对 melobot 已经十分了解，请自由地安装核心+任何可选依赖。

也可以通过源码构建：（对于普通用户不推荐）

> 本项目使用 pdm 管理，你首先需要安装 [pdm](https://pdm-project.org/latest/#installation)。

```shell
pdm install
pdm build
```

之后可在 `.pdm-build` 目录获取本地构建，pip 本地安装即可。

<!-- end elevator-pitch -->

## 💻 其他

**贡献指南与行为准则**：

- [CONTRIBUTING](CONTRIBUTING.md)
- [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md)

**安全政策**：

- [SECURITY POLICY](SECURITY.md)

## 📜 开源许可

本项目使用双许可证。

[docs](https://github.com/Meloland/melobot/tree/main/docs) 目录内除 melobot 项目 logo，所有内容在 CC-BY-SA-4.0 许可下发行。此部分版权主体为：**melobot 文档的所有贡献者**

<a href="http://creativecommons.org/licenses/by-sa/4.0/" rel="nofollow"><img src="https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/by-sa.svg" style="width: 150px"></a>

[docs](https://github.com/Meloland/melobot/tree/main/docs) 目录外所有内容在 BSD 3-Clause 许可下发行。此部分版权主体为：**melobot 项目代码的所有贡献者**

<a href="https://opensource.org/license/bsd-3-clause"><img src="https://upload.wikimedia.org/wikipedia/commons/d/d5/License_icon-bsd-88x31.svg" style="width: 150px"></a>

## ❤️ 鸣谢

> [PyCharm](https://zh.wikipedia.org/wiki/PyCharm) 是一款流行的、强大的、适用于数据科学与 Web 开发的 Python IDE。

特别感谢由 [JetBrains](https://www.jetbrains.com/?from=melobot) 提供的 [PyCharm](https://www.jetbrains.com/pycharm/?from=melobot) 等相关软件/程序的免费授权许可证。这些软件/程序用于本项目的开发与 IDE 兼容性测试。

<img src="https://resources.jetbrains.com/storage/products/company/brand/logos/PyCharm.png" alt="PyCharm logo." style="width: 310px">

> 此外特别感谢 [@mldkouo](https://github.com/mldkouo) 为 melobot 项目绘制 logo 图标。

<img width=192 src="https://github.com/Meloland/melobot/blob/main/docs/source/_static/logo.png?raw=true" />

此图标版权归属于 [@meloland](https://github.com/meloland) 组织，在非商业盈利情景下可自由使用，但请标注版权所属。其他使用情景请致电邮件：[contact@meloland.org](mailto:contact@meloland.org)
