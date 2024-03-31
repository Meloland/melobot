# 创建第一个机器人

## 预先配置

由于 melobot 目前是基于 OneBot 协议的 bot 开发框架，因此 melobot 需要一个“OneBot 实现程序”作为“前端”，
完成与 qq 服务器的通信过程。请自行配置 OneBot 协议实现。

```{admonition} 相关知识
:class: note
[什么是 OneBot 协议和 OneBot 实现？](../references/onebot)
```

## 一个小 demo

先来运行一段 demo 代码：（不要害怕，稍后我们会讲解其中的细节）

```{code} python
:number-lines:

from melobot import MeloBot, BotPlugin, send, ForwardWsConn

plugin = BotPlugin(__name__, "1.0.0")

@plugin.on_start_match(".hello")
async def echo() -> None:
    await send("你好呀！我是 melobot >w<")

if __name__ == "__main__":
    bot = MeloBot(__name__)
    # 如果你的 OneBot 实现程序的服务的 host 和 port 不一致，请自行修改
    bot.init(ForwardWsConn("127.0.0.1", 8080))
    bot.load_plugin(plugin)
    bot.run()
```

运行后，在机器人加入的任何一个群聊或与机器人的私聊中，输入以 `.hello` 开始的消息，即可得到回复：`你好呀！我是 melobot >w<`。

## 小 demo 讲解

接下来逐行解释这个小 demo 的代码。

首先，melobot 是基于插件化管理的，因此通过 {class}`.BotPlugin` 新建一个“插件对象”，用于划分接下来的操作，应该被哪个插件管理。

```python
# 参数分别是插件名和插件版本
plugin = BotPlugin(__name__, "1.0.0")
```

接下来，使用插件对象上的装饰器成员 {meth}`~.BotPlugin.on_start_match`，即可在本插件上添加一个**字符串起始匹配的消息事件处理方法**。

```python
@plugin.on_start_match(".hello")
async def echo() -> None:
    await send("你好呀！我是 melobot >w<")
```

这个事件处理方法做了件很简单的事：事件发生时，通过 {func}`.send` 发送一条消息：`你好呀！我是 melobot >w<`。这种操作在 melobot 中被称为“行为”/“行为操作”。

```{admonition} 相关知识
:class: note
[什么是事件和行为？](../references/event-action)
```

插件初始化好了、事件处理方法也添加好了。但是还需要 bot 去加载这个插件哦，否则它无法在一个具体的 bot 上生效。但是我们连 bot 都还没有~ 所以先通过 {class}`.MeloBot` 类创建一个 bot：

```python
bot = MeloBot(__name__)
```

随后，bot 需要知道自己和哪个“OneBot 实现程序”对接，因此引入一个连接器 {class}`.ForwardWsConn` 来初始化 bot：

```python
# 这里使用一个正向 ws 连接器，与 OneBot 实现程序对接
# 如果你的 OneBot 实现程序的服务的 host 和 port 不一致，请自行修改
bot.init(ForwardWsConn("127.0.0.1", 8080))
```

```{admonition} 相关知识
:class: note
更多连接器类型，请参考：[连接器类型](../references/connector)
```

最后加载插件到 bot，启动 bot 就可以了：

```python
bot.load_plugin(plugin)
bot.run()
```

到这里，你已经学会了如何创建自己的第一个机器人。接下来，让我们来试试其他有趣的东西！
