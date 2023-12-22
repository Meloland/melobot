<div align="center">
<img width=200 src="https://proj.glowmem.com/MeloBot/images/icon.png" />
<h1>MeloBot</h1>
<p><strong>基于 go-cqhttp 前端，python 的 qbot 实现</strong></p>
</div>

## 🎉 关于 MeloBot

MeloBot 是一个基于 Python 的 qbot 实现。其以**实现了 Onebot 标准的适配器**作为前端，通过对来自适配器的各种“事件”的处理，再产生“行为”，最后提交给适配器与 qq 服务器进行通信，实现各类复杂的功能。

目前正开发 v2 版本。（详情参考 [v2-dev](https://github.com/AiCorein/Qbot-MeloBot/tree/v2-dev) 分支）

郑重承诺和提示：**本项目一切开发旨在学习，请勿用于商业用途和非法用途。任何使用本项目的用户群体，有义务遵守其所在国家或地区的相关法律规定。**

## ✨ MeloBot v1 的特点

- 异步多协程 + 多线程的并发实现，拥有较高的处理性能
- 独立备用队列、备用事件处理器组，保证主队列和主事件处理器组阻塞时，仍有备用选择
- 支持多消息的事件处理，以及单消息中的多事件处理
- 支持特定关键词，在特定条件下触发自动应答
- 对外部消息有较强的抗注入和抗干扰功能
- 事件响应超时控制
- 命令参数错误自动提醒
- 可自定义命令错误执行时的反馈

❗注意：v1 版本需要 go-cq 作为适配器。同时 v1 版本停止功能更新和维护。

## 🚧 MeloBot v2 正在进行的工作

- ✅ 架构重写，使用微内核、事件总线架构
- ✅ 封装建立内部数据结构，与底层数据解耦
- ✅ 取消线程池设计，全部使用协程设计
- ✅ 全局公共空间使用异步安全的读写锁
- ✅ cq 响应事件的分发与回送
- ✅ 事件接口与事件分发
- ✅ 响应优先级设计
- ✅ 权限检查、规则校验、解析组件等中间件设计
- ✅ 插件化管理
- ⬜ 完整的会话控制机制
- ⬜ 生命周期 hook 设计
- ⬜ 插件交互
- ⬜ 支持各种适配器协议

🌱 提示：为保证兼容性，v2 版本在所有接口实现完毕前，不会发布。你可以自行克隆 [v2-dev](https://github.com/AiCorein/Qbot-MeloBot/tree/v2-dev) 分支体验功能。

## 📦️ 版本支持

- python >= 3.8
- platform == All（注：mac 平台尚未测试，同时 v1 版本只支持 win 平台）

## 💬 更多

请参阅文档（v1 版本）：[MeloBot 文档](https://proj.glowmem.com/MeloBot/)

文档开源（v1 版本）：[MeloBot-docs](https://github.com/AiCorein/Qbot-MeloBot-docs)
