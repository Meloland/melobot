# 开始创建机器人

## 预先配置

我们先从最简单的 OneBot v11 协议开始学习如何搭建一个机器人，并以此学习 melobot 的基本特性。

虽然你可能不需要使用 OneBot v11 协议，但也可以简单浏览这部分教程，从而理解一些 melobot 中的基本概念。在后续部分，我们会拓展教程到协议通用领域。

首先需要一个“OneBot 实现程序”作为“前端”，完成与 qq 服务器的通信过程。请自行配置 OneBot 协议实现。

```{admonition} 相关知识
:class: note
[什么是 OneBot 协议和 OneBot 实现？](../ob_refer/onebot)
```

```{admonition} 相关知识
:class: note
[什么是 OneBot 事件和行为？](../ob_refer/event-action)
```

## 一个 demo

先来运行一段 demo 代码：（稍后我们会讲解其中的细节）

```{code} python
:number-lines:

from melobot import Bot, PluginPlanner, on_start_match, send_text
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol

@on_start_match(".sayhi")
async def echo_hi() -> None:
    await send_text("Hello, melobot!")

test_plugin = PluginPlanner(version="1.0.0", flows=[echo_hi])

if __name__ == "__main__":
    bot = Bot(__name__)
    bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO("ws://127.0.0.1:8080")))
    bot.load_plugin(test_plugin)
    bot.run()
```

运行后，在机器人加入的任何一个群聊中，或与机器人的私聊中，输入以 `.sayhi` 起始的消息，即可回复：`Hello, melobot!`。

##  demo 讲解

首先使用装饰器 {func}`~.on_start_match`，即可在本插件上添加一个**字符串起始匹配的，消息事件处理方法**。

```python
@on_start_match(".sayhi")
async def echo_hi() -> None:
    await send_text("Hello, melobot!")
```

这个事件处理方法做了件很简单的事：当收到一条消息时，如果消息内容以 `.sayhi` 起始，则通过 {func}`.send_text` 发送一条消息：`Hello, melobot!`。

由于 melobot 是基于插件化管理的，随后通过 {class}`.PluginPlanner` 创建一个插件管理器。插件管理器将被 melobot 用于创建插件。

```python
# version 描述插件的版本，flows 填入刚才的事件处理方法
test_plugin = PluginPlanner(version="1.0.0", flows=[echo_hi])
```

接下来开始按以下步骤创建、初始化和启动一个 bot：

1. 通过 {class}`.Bot` 创建一个 bot；
2. 通过 {meth}`~.Bot.add_protocol` 添加 OneBot v11 相关的协议栈支持，此处需要提供一个输入输出源；
4. 通过 {meth}`~.Bot.load_plugin` 创建并加载插件
5. 启动 bot

```python
bot = Bot(__name__)
bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO("ws://127.0.0.1:8080")))
bot.load_plugin(test_plugin)
bot.run()
```

```{admonition} 相关知识
:class: note
更多 OneBot v11 输入输出源类型，请参考：[输入输出源类型](../ob_refer/impl)
```

到这里，你已经学会如何创建一个 melobot 机器人。接下来，让我们试试其他有趣的操作 :)
