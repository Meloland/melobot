<div align="center">
  <img width=200 src="https://github.com/aicorein/melobot/blob/main/docs/source/_static/logo.png?raw=true" />
  <h1>MeloBot</h1>
  <p>
    <strong>插件化管理、基于异步会话机制的 qbot 开发框架</strong>
  </p>
  <p align="center">
    <a href="https://raw.githubusercontent.com/aicorein/melobot/main/LICENSE">
      <img src="https://img.shields.io/github/license/aicorein/melobot" alt="license">
    </a>
    <a href="https://docs.melobot.org/">
      <img src="https://img.shields.io/badge/doc-latest-blue.svg" alt="MeloBot docs">
    </a>
    <a href="https://github.com/aicorein/melobot">
      <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/aicorein/melobot">
    </a>
  </p>
  <p align="center">
    <a href="https://python.org" title="Go to Python homepage">
      <img src="https://img.shields.io/badge/Python-%3E=3.10-green?logo=python&logoColor=white" alt="Made with Python">
    </a>
    <a href="https://pypi.org/project/melobot/">
      <img alt="PyPI" src="https://img.shields.io/pypi/v/melobot">
    </a>
    <a href="https://github.com/psf/black">
      <img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg">
    </a>
    <a href="https://mypy-lang.org/">
      <img src="https://www.mypy-lang.org/static/mypy_badge.svg" alt="Checked with mypy">
    </a>
    <a href="https://github.com/howmanybots/onebot/blob/master/README.md">
      <img src="https://img.shields.io/badge/OneBot-v11-blue?style=flat&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABABAMAAABYR2ztAAAAIVBMVEUAAAAAAAADAwMHBwceHh4UFBQNDQ0ZGRkoKCgvLy8iIiLWSdWYAAAAAXRSTlMAQObYZgAAAQVJREFUSMftlM0RgjAQhV+0ATYK6i1Xb+iMd0qgBEqgBEuwBOxU2QDKsjvojQPvkJ/ZL5sXkgWrFirK4MibYUdE3OR2nEpuKz1/q8CdNxNQgthZCXYVLjyoDQftaKuniHHWRnPh2GCUetR2/9HsMAXyUT4/3UHwtQT2AggSCGKeSAsFnxBIOuAggdh3AKTL7pDuCyABcMb0aQP7aM4AnAbc/wHwA5D2wDHTTe56gIIOUA/4YYV2e1sg713PXdZJAuncdZMAGkAukU9OAn40O849+0ornPwT93rphWF0mgAbauUrEOthlX8Zu7P5A6kZyKCJy75hhw1Mgr9RAUvX7A3csGqZegEdniCx30c3agAAAABJRU5ErkJggg==" alt="cqhttp">
    </a>
  </p>
  <p>
    郑重承诺和提示：
    <strong>本项目一切开发旨在学习，请勿用于商业用途和非法用途。任何使用本项目的用户群体，有义务遵守其所在国家或地区的相关法律规定。</strong>
  </p>
</div>

<!-- start elevator-pitch -->

## 🎉 简介

MeloBot 是一个基于 Python 的 qq 机器人开发框架。其以**Onebot 标准的实现项目**作为前端，通过对来自“前端”的各种“事件”的处理，再产生“行为”，最后提交给“前端”与 qq 服务器交互，即可实现各类复杂的功能。

使用本框架的机器人项目如下：

- [MeloInf](https://github.com/aicorein/meloinf)

你可以将这些项目作为 melobot 的使用参考之一。我们也欢迎你基于 melobot 实现机器人后，向文档提出 PR，在此处展示。

## ✨ 特色

- 基于 asyncio 的高性能异步
- 支持插件交互的插件化管理
- 异步会话控制、自动的会话上下文
- 事件预检查、预匹配和预解析
- 支持 bot 生命周期 hook
- 支持多 bot 协同工作
- 丰富的接口设计

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
```

提示：首次运行 pdm 可能需要初始化虚拟环境，请按照 pdm 文档操作。

## 🪄 版本支持

- python >= 3.10
- platform == All
- OneBot 标准 == 11

<!-- end elevator-pitch -->

## 💬 更多

项目文档：[MeloBot 文档](https://docs.melobot.org)
