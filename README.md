<div align="center">
  <img width=200 src="https://github.com/Meloland/melobot/blob/main/docs/source/_static/logo.png?raw=true" />
  <h1>melobot</h1>
  <p>
    <strong>插件化管理、基于异步会话机制的机器人开发框架</strong>
  </p>
  <p align="center">
    <a href="https://github.com/Meloland/melobot/tree/main/LICENSE-BSD"><img src="https://img.shields.io/badge/license-BSD--3--Clause-2ea44f" alt="license - BSD-3-Clause"></a>
    <a href="https://github.com/Meloland/melobot/tree/main/LICENSE-CC"><img src="https://img.shields.io/badge/license-CC--BY--SA--4.0-2ea44f" alt="license - CC-BY-SA-4.0"></a>
    <a href="https://docs.melobot.org/"><img src="https://img.shields.io/badge/doc-latest-blue.svg" alt="melobot docs"></a>
    <a href="https://github.com/Meloland/melobot"><img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/Meloland/melobot"></a>
    <a href="https://github.com/botuniverse/onebot-11"><img src="https://img.shields.io/badge/OneBot-v11-blue?style=flat&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABABAMAAABYR2ztAAAAIVBMVEUAAAAAAAADAwMHBwceHh4UFBQNDQ0ZGRkoKCgvLy8iIiLWSdWYAAAAAXRSTlMAQObYZgAAAQVJREFUSMftlM0RgjAQhV+0ATYK6i1Xb+iMd0qgBEqgBEuwBOxU2QDKsjvojQPvkJ/ZL5sXkgWrFirK4MibYUdE3OR2nEpuKz1/q8CdNxNQgthZCXYVLjyoDQftaKuniHHWRnPh2GCUetR2/9HsMAXyUT4/3UHwtQT2AggSCGKeSAsFnxBIOuAggdh3AKTL7pDuCyABcMb0aQP7aM4AnAbc/wHwA5D2wDHTTe56gIIOUA/4YYV2e1sg713PXdZJAuncdZMAGkAukU9OAn40O849+0ornPwT93rphWF0mgAbauUrEOthlX8Zu7P5A6kZyKCJy75hhw1Mgr9RAUvX7A3csGqZegEdniCx30c3agAAAABJRU5ErkJggg==" alt="cqhttp"></a>
  </p>
  <p align="center">
    <a href="https://python.org" title="Go to Python homepage"><img src="https://img.shields.io/badge/Python-%3E=3.10-green?logo=python&logoColor=white" alt="Made with Python"></a>
    <a href="https://pdm-project.org"><img src="https://img.shields.io/badge/PDM-Managed-purple?logo=pdm&logoColor=white" alt="PDM - Managed"></a>
    <a href="https://pypi.org/project/melobot/"><img alt="PyPI" src="https://img.shields.io/pypi/v/melobot"></a>
    <a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
    <a href="https://mypy-lang.org/"><img src="https://www.mypy-lang.org/static/mypy_badge.svg" alt="Checked with mypy"></a>
  </p>
</div>

## 🔄 工作计划

主分支为 melobot v2 的代码，melobot v3 仍在开发中。v3 计划支持各种协议以扩展至各种平台提供机器人服务。

main 分支可接受**不与未来 v3 预期目标冲突**的 bug 修复与功能新增。

因此您可以向 main 分支发起 PR，如果被合并，我们会努力将新特性移植到 v3 中。

## ⚠️ 声明

melobot 是由热爱技术的开发者共同维护的开源项目。我们致力于提供一个可靠、高效的软件工具，以促进技术交流和创新。以下简称 melobot 项目为“本项目”。

本项目严禁用于任何非法目的，包括但不限于侵犯版权、商标、商业机密或其他知识产权，以及违反任何适用的法律和法规。我们不对因非法使用本项目而产生的任何直接、间接、附带、特殊、惩罚性或后果性损害承担责任。

<!-- start elevator-pitch -->

## 🎉 简介

melobot 是基于 Python 的机器人开发框架。目前开发版本号为 v2，只适用于搭建 qq 机器人，v3 仍在开发中。

melobot v2 以**Onebot 标准的实现项目**作为前端，通过对来自“前端”的各种“事件”的处理，产生“行为”，最后提交给“前端”与 qq 服务器交互，从而实现各种复杂的功能。

## ✨ 特色

- 高性能异步：基于 asyncio，但使用性能更优秀的事件循环策略：[uvloop](https://github.com/MagicStack/uvloop)/[winloop](https://github.com/Vizonex/Winloop)
- 插件管理：更低耦合度的插件加载、通信模式
- 会话控制：自动传递上下文（会话）、可自定义的会话
- 流程与生命周期：支持事件预检查、预匹配和预解析；支持添加生命周期 hook
- 多实例协同：多 bot 实例运行，跨实例通信
- 异步接口：封装了部分常用的异步控制流

使用本框架的机器人项目如下：

- [MeloInf](https://github.com/aicorein/meloinf)

你可以将这些项目作为 melobot 使用的实例参考。欢迎你基于 melobot 实现完整的机器人项目后，向本文档提出 PR，在此处展示。

## 💬 文档

项目文档：[melobot 文档](https://docs.melobot.org)

对于文档可能出现的纰漏，恳请各位包涵。欢迎提出修正和优化文档的 PR：[文档源文件](https://github.com/Meloland/melobot/tree/main/docs/source)

## 📦️ 安装使用

通过 `pip` 命令安装：

```shell
pip install melobot
```

或从源码构建：

本项目通过 pdm 管理，你首先需要安装 [pdm](https://pdm-project.org/latest/#installation)。

```shell
# 随后在本项目根目录：
pdm install
pdm build
```

之后可在 `.pdm-build` 目录获取本地构建，pip 本地安装即可。提示：首次运行 pdm 需要初始化虚拟环境，请参照 pdm 文档操作。

## 🪄 版本特性

- python 版本需要 `>=3.10`
- 可跨平台使用
- 通信标准：[OneBot v11](https://github.com/botuniverse/onebot-11)

<!-- end elevator-pitch -->

## 📜 开源许可

本项目使用双许可证。

[docs](https://github.com/Meloland/melobot/tree/main/docs) 目录内所有内容在 CC-BY-SA-4.0 许可下发行。

<a href="http://creativecommons.org/licenses/by-sa/4.0/" rel="nofollow"><img src="https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/by-sa.svg" style="width: 150px"></a>

此部分版权主体为：

> **melobot 文档的所有贡献者**

[docs](https://github.com/Meloland/melobot/tree/main/docs) 目录外所有内容在 BSD 3-Clause 许可下发行。

<a href="https://opensource.org/license/bsd-3-clause"><img src="https://upload.wikimedia.org/wikipedia/commons/d/d5/License_icon-bsd-88x31.svg" style="width: 150px"></a>

此部分版权主体为：

> **melobot 项目的所有贡献者（此处不包含只对文档有贡献的）**

