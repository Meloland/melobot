<div align="center">
<img width=200 src="https://proj.glowmem.com/MeloBot/images/icon.png" />
<h1>MeloBot</h1>
<p><strong>插件化管理、基于异步会话机制的 python 的 qbot 开发框架</strong></p>
<p>郑重承诺和提示：<strong>本项目一切开发旨在学习，请勿用于商业用途和非法用途。任何使用本项目的用户群体，有义务遵守其所在国家或地区的相关法律规定。</strong></p>
</div>

## 🎉 关于 MeloBot

MeloBot 是一个基于 Python 的 qbot 开发框架。其以**实现了 Onebot 标准的适配器**作为前端，通过对来自适配器的各种“事件”的处理，再产生“行为”，最后提交给适配器与 qq 服务器进行通信，实现各类复杂的功能。

v1 版本（[main](https://github.com/AiCorein/Qbot-MeloBot/tree/main) 分支）已经完成。它本质上不是一个开发框架，只是一个可用的 qq 机器人项目。只支持 windows 平台，且需要 go-cq 作为适配器，现已经停止更新和维护。

目前正开发 v2 版本（[v2-dev](https://github.com/AiCorein/Qbot-MeloBot/tree/v2-dev) 分支）。v2 版本已经实现完毕，目前正在进行验证工作，验证完成后会发布 release。你可以参考用于本项目验证的具体机器人项目（[MeloInf](https://github.com/AiCorein/meloinf)），这里有详细的使用示例。

此外，你可以在 pypi.org 预先获得 MeloBot 的 pre-release 版本：

```bash
pip install --pre melobot
```

## 🚧 MeloBot v2 的开发工作

- ✅ 封装建立内部数据结构，与底层数据解耦
- ✅ 取消线程池设计，全部使用协程设计
- ✅ 事件接口、事件分发与事件回送
- ✅ 权限检查、规则校验、解析组件等中间件设计
- ✅ 完整的会话控制机制
- ✅ 插件化管理
- ✅ 插件交互
- ✅ 生命周期 hook 设计
- ⬜ 后期验证

## 📦️ 版本支持

- python >= 3.8
- platform == All（mac 平台未测试）
- OneBot 标准 >= 11

## 💬 更多

请参阅文档（v1 版本）：[MeloBot 文档](https://proj.glowmem.com/MeloBot/)

文档开源（v1 版本）：[MeloBot-docs](https://github.com/AiCorein/Qbot-MeloBot-docs)
