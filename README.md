<div align="center">
<img width=200 src="https://proj.glowmem.com/MeloBot/images/icon.png" />
<h1>MeloBot</h1>
<p><strong>基于 go-cqhttp 前端，python 的 qbot 实现</strong></p>
</div>

## 关于 MeloBot

MeloBot 是一个基于 Python 的 qbot 实现，其以实现了 Onebot 标准的 go-cqhttp 接口作为前端，通过对来自 cq-http 的各种“事件”的处理，再产生“行为”，最后提交给 cq-http 与 qq 服务器进行通信，完成 bot 的各种动作。

MeloBot 目前的接口设计，可以帮助使用者实现一些自定义的需求。但仍不够好，不够完善，需要进一步的迭代和更新。在未来，MeloBot 的目标是成为具有高性能、高自由度、强易用性的 qbot 开发接口和工具。

## MeloBot 能做到什么
- 异步多协程 + 多线程的并发实现，拥有较高的处理性能
- 独立备用队列、备用事件处理器组，保证主队列和主事件处理器组阻塞时，仍有备用选择
- 支持多消息的事件处理，以及单消息中的多事件处理
- 支持特定关键词，在特定条件下触发自动应答
- 对外部消息有较强的抗注入和抗干扰功能
- 事件响应超时控制
- 命令参数错误自动提醒
- 可自定义命令错误执行时的反馈

## 版本支持
- python >= 3.8
- go-cqhttp >= 1.0.0
- platform == x64

## 更多
请参阅文档：[MeloBot 文档](https://proj.glowmem.com/MeloBot/)