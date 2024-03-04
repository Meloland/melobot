<div align="center">
<img width=200 src="https://aicorein.github.io/Qbot-MeloBot-docs/images/icon.png" />
<h1>MeloBot</h1>
<p><strong>插件化管理、基于异步会话机制的 python 的 qbot 开发框架</strong></p>
<p>郑重承诺和提示：<strong>本项目一切开发旨在学习，请勿用于商业用途和非法用途。任何使用本项目的用户群体，有义务遵守其所在国家或地区的相关法律规定。</strong></p>
</div>

## 🎉 关于

MeloBot 是一个基于 Python 的 qbot 开发框架。其以**实现了 Onebot 标准的适配器**作为前端，通过对来自适配器的各种“事件”的处理，再产生“行为”，最后提交给适配器与 qq 服务器进行通信，实现各类复杂的功能。

使用示例：你可以参考使用本框架的项目 [MeloInf](https://github.com/aicorein/meloinf)，这里有详细的接口调用示范。

## ✨ 特色

- 基于 asyncio 的高性能异步
- 插件化管理
- 异步的自动上下文（会话）
- 可高度自定义的中间件功能
    - 权限检查、规则校验、解析组件等
- 支持生命周期 hook
- 人性化、丰富的接口设计

## 📦️ 安装使用

```python
pip install melobot
```

版本支持：
- python >= 3.8
- platform == All（mac 平台未测试）
- OneBot 标准 >= 11

## 💬 更多

项目文档正在构建中，敬请期待...
