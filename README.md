<div align="center">
<img width=200 src="https://proj.glowmem.com/MeloBot/images/icon.png" />
<h1>MeloBot</h1>
<p><strong>基于 go-cqhttp 前端，python 的 qbot 实现</strong></p>
</div>

## ❗❗❗ 2023.10.20 消息
<h2>
<strong><p style="color: red;">美好的时代结束啦~</p></strong>
<strong><p>由于上游 QQ 协议解析、登录相关开源项目已停止维护。本项目也无力继续维护，将无限期停滞开发。</p></strong>
</h2>

## 🎉 关于 MeloBot

MeloBot 是一个基于 Python 的 qbot 实现。其以实现了 Onebot 标准的 go-cqhttp 接口作为前端，通过对来自 go-cqhttp 的各种“事件”的处理，再产生“行为”，最后提交给 go-cqhttp 与 qq 服务器进行通信，实现各类复杂的功能。

目前正开发 v2 版本。（详情参考 [v2-dev](https://github.com/AiCorein/Qbot-MeloBot/tree/v2-dev) 分支）

## ✨ MeloBot v1 的特点
- 异步多协程 + 多线程的并发实现，拥有较高的处理性能
- 独立备用队列、备用事件处理器组，保证主队列和主事件处理器组阻塞时，仍有备用选择
- 支持多消息的事件处理，以及单消息中的多事件处理
- 支持特定关键词，在特定条件下触发自动应答
- 对外部消息有较强的抗注入和抗干扰功能
- 事件响应超时控制
- 命令参数错误自动提醒
- 可自定义命令错误执行时的反馈

❗注意：v1 版本的更新已经停止，这意味着不会有功能新增。但其依然在维护，你仍然可以提出 issue 请求 bug 修复。

## 🚧 MeloBot v2 正在进行的工作
- ✅ 架构重写，使用微内核、事件总线架构
- ✅ 封装建立内部数据结构，与底层数据解耦
- ✅ 取消线程池设计，全部使用协程设计
- ✅ 全局公共空间使用异步安全的读写锁
- ✅ 事件响应的会话控制
- ✅ cq 响应事件的分发与回送
- ✅ 事件接口与事件分发
- ✅ 响应优先级设计
- ✅ 权限检查、规则校验、解析组件等中间件设计
- ✅ 插件化管理
- ⬜ 生命周期 hook 设计
- ⬜ 跨插件调用与插件交互
- ⬜ 基于 aiocqhttp 的连接前端（不再使用 go-cq）

🌱 提示：为保证兼容性，v2 版本在所有接口实现完毕前，不会发布。你可以自行克隆 [v2-dev](https://github.com/AiCorein/Qbot-MeloBot/tree/v2-dev) 分支体验新功能。<br />

## 📦️ 版本支持
- python >= 3.8
- go-cqhttp >= 1.0.0
- platform == All（注：mac 平台尚未测试，同时 v1 版本只支持 win 平台）

## 💬 更多
请参阅文档（目前只有 v1 版本）：[MeloBot 文档](https://proj.glowmem.com/MeloBot/)

文档开源（目前只有 v1 版本）：[MeloBot-docs](https://github.com/AiCorein/Qbot-MeloBot-docs)
