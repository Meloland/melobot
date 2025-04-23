# 交互式处理与会话的使用

## 命令式与交互式

某些情况下，我们更希望 bot 能够与用户进行“交互式操作”，而不一定是一次到位的“命令式操作”。

对比 `.天气 北京 7` 这样一句命令，更适合普通大众的也许是这样的交互逻辑：

```text
>>> 天气
输入您想要查询的城市哦，亲~
>>> 北京
想要查看多少天的天气预报呢？
>>> 7
为您查询中，请稍后...
查询结果为：
(此处省略结果文字或图像)
如果您对服务满意，请给我们 5 星好评哦 ^ ^
```

仔细一想，事情似乎没有那么容易了！交互意味着需要停下来等待，但是此时 bot 也应该能做别的事（处理别的事件）才对，似乎情况比较复杂。

你说的对，但是 melobot 是一款**拥有丰富功能的异步机器人开发框架**。当然会帮你处理好这些~ 只需要一个名为“会话”的魔法。

## 使用会话

什么是会话？会话是“事件处理”的**高阶状态**，使得事件处理可以暂时停止（异步停止，因此可以去处理别的事件，停止也可以被叫做挂起）。而随后，当满足特定规则的事件发生后（例如限制要在同一个对话域：同一群聊或同一对象的私聊），**就可以从中恢复（恢复也可以被叫做被唤醒），把新来的事件更新为处理流的“当前事件”，并继续处理流的执行**。

没有会话状态的事件处理过程，就像 HTTP 服务一样没有“记忆”，但交互式往往就需要“记忆”。会话封装了“如何记忆”、“如何暂停并切换”以及“如何恢复”的逻辑，使你不需要在事件处理之外，去维护交互的上下文信息（状态信息）。由此就不需要去与“异步安全”这些可怕的字眼打交道。

让我们看看魔法如何发生，这里以实现上面的例子为目标。先看看所有代码，稍后我们会仔细解析：

```{code} python
:number-lines:

from typing import Annotated

from melobot import send_text
from melobot.handle import on_start_match
from melobot.session import suspend
from melobot.di import Reflect
from melobot.protocols.onebot.v11 import MessageEvent

# 简化一下，先做成只适用于 OneBot 协议的处理逻辑
@on_start_match(["天气", "weather", "查天气"], legacy_session=True)
async def query_weather(event: Annotated[MessageEvent, Reflect()]) -> None:
    await send_text("输入您想要查询的城市哦，亲~")
    # 十秒没有下一条消息就结束事件处理
    if not await suspend(timeout=10):
        return
    
    city = event.text
    await send_text("想要查看多少天的天气预报呢？")
    if not await suspend(timeout=10):
        return
    
    days = event.text
    # 先回复一条“正在运行”的提示
    await send_text("为您查询中，请稍后...")
    # 查询的逻辑
    result = _a_simple_query_func(city, days)
    await send_text(
        "查询结果为：\n"
        f"{result}\n"
        "如果您对服务满意，请给我们 5 星好评哦 ^ ^"
    )
```

### 会话规则与会话判断

先来看看最开始的装饰器：

```python
@on_start_match(["天气", "weather", "查天气"], legacy_session=True)
```

第一参数 `target` 可以接受一个列表，看一眼 api 文档就懂了，应该不难。后续将 `legacy_session` 参数置为 `True`，这是告诉 melobot，这个处理过程需要启用一个“传统会话”的规则。

什么是规则？首先我们说过，会话的重要特性是**暂时停止，并稍后恢复**，稍候是什么时候？当然是出现**一个可以让会话恢复的事件**的时候，因为不是所有事件都能让会话“恢复”。

melobot 如何知道哪些事件可以让某个会话恢复？就是凭借“会话规则”。会话规则是一种判断规则，让 melobot 在**已经存在一个挂起的会话的前提下，对新来的事件进行是否可以唤醒会话的判断**。这种判断称为“会话判断”。进行判断后如果返回真值，则认为可以唤醒。会话被唤醒，处理流中的“当前事件”将被更新，处理流的代码也将继续执行。

那这里为什么是传统规则？melobot 基事件类型有一个实例属性 `scope`（{external:class}`~.collections.abc.Hashable` 类型）。而传统规则是一种内置的规则，会话判断即**判断两个事件的 `scope` 是否 `==`**。举例来说，在 OneBot v11 协议支持中，scope 属性会被设置为 `(群组 id | None, 用户 id)` 二元组，用于指示当前的“对话域”。此时的会话与其他 bot 开发框架中狭义的“会话”几乎是一个语义，所以此时的规则取名“传统规则”，此时的会话也就是“传统会话”。

### 依赖注入 + 反射

```python
async def query_weather(event: Annotated[MessageEvent, Reflect()]) -> None:
```

在使用依赖注入时，我们使用了 [`Annotated`](https://docs.python.org/3/library/typing.html#typing.Annotated) + {class}`.Reflect` 附加项的方式，这是告诉 melobot 对 `event` 进行反射式的依赖注入。处理流在启用会话后，内部的“当前事件”记录会被更新。如果使用常规的依赖注入，那么 `event` 实参在会话暂停、又恢复后并不会自动被更新。而使用反射式的获取，就可以实时映射到最新的事件。

需要特别注意的是，反射式的依赖注入，**只适用于获取某些属性并使用**的情景，如果要对对象做比较底层的操作，请使用 `__origin__` 属性获取原始对象：

```python
# 读取 text 是没有关系的，因为通过反射获取：
text = event.text

# 但是进行 isinstance, issubclass 判断，需要获取原对象
# 因为当前拿到的 event 不是 Event 类型，而是“代理对象”类型：
is_msg_event = isinstance(event.__origin__, MessageEvent)
# 传入你不清楚实现细节的函数，或其他位置，请一定获取原始对象
whatever = i_dont_know_how_this_running(event.__origin__)
```

如果不用依赖注入，用上下文方法 {func}`.get_event` 可以自动映射到最新的事件。但需要在函数体里反复调用 {func}`.get_event`，非常不方便，而且没有精确类型注解。

除了上下文获取方法，上下文变量也是实时映射的：

```python
import melobot.handle as mb_handle

@on_start_match(...)
async def query_weather() -> None:
    # 需要使用事件时：
    first_text = mb_handle.event.text
    # 随后历经下一次的“暂停、恢复”
    ...
    # 再次使用事件获取新的文本内容
    second_text = mb_handle.event.text
```

坏处是依然没有精确类型注解。

### 会话暂停、恢复

```python
await send_text("输入您想要查询的城市哦，亲~")
```

因为设置 `legacy_session` 参数为 `True`，在进入到事件处理过程前，就生成了一个会话。进入会话后，开始正常运行：输出一行提示语，提示用户输入。

```python
# 十秒没有下一条消息就结束事件处理
if not await suspend(timeout=10):
    # 10s 超时，没有符合要求的事件来唤醒
    # 那么就结束
    return
```

随后调用了异步函数 {func}`.suspend`，从而暂时陷入到**会话暂停**中，此时整个处理过程就被暂停了，bot 可以转向处理其他事件。当有新事件发生，并且“传统会话”的会话规则判断通过，那这个 `await` 行为便会完成并返回 `True`。这使得整个事件处理过程得以恢复执行。

如果一直没有符合要求的事件发生，且超时 10s，那 `await` 将返回 `False`，指示“超时”。注意“超时”发生时，处理流的“当前事件”不会被更新。

如果你需要无限期的暂停，不提供参数即可：

```python
# 无限期等待一定只能返回 True，因此不再需要分支
await suspend()
```

在恢复后，自然可以获取新的文本内容：

```python
# 有符合要求的事件，也就是同一“对话域”的事件发生
# 才会执行到这一句
city = event.text
```

后续的过程不过是“暂停、恢复”的周期，不再赘述。

## 其他注意事项

`legacy_session` 参数只有文本事件的“绑定函数”拥有。其他“绑定函数”一般只会有 `rule` 参数。这是因为其他“绑定函数”对应处理的事件类型，一般而言搞“传统会话”没有太大意义。因此必须提供具体的规则。会话规则的自定义、调整会话创建的时机等属于高级特性与用法，将会在后面的教程中慢慢揭晓。

在拥有 `legacy_session` 参数的“绑定函数”中，你也可以同时使用 `checker`, `matcher` 和 `parser`。但是有以下的先后运行规则：

- 事件预处理
    - 检查（check）
    - 匹配（match）
    - 解析（parse）
- 如果需要会话，创建并进入
- 事件处理过程
    - <你的事件处理函数的逻辑>

```{admonition} 提示
:class: tip

如果使用这些“绑定函数”，`checker`, `matcher` 和 `parser` 运行时是不存在会话状态的。

但如果你调整了会话创建的时机，这些组件运行时也可以实现“暂停”、“恢复”。
```

## 总结

本篇主要说明了如何使用会话开启交互式事件处理。

恭喜你读完了 melobot intro 部分的所有内容。这些内容应该让你对 melobot 有了基础了解，并能基于此构建基础的、适配 OneBot 的机器人程序。 

**这便是 melobot 的全部了吗？实际上，一切才刚刚开始 :)**

从下一章开始，我们将深入了解 melobot 的各层架构与各种机制。从而解锁**无序插件加载、自定义会话**等高级玩法，并**使用裸处理流像搭积木一样，实现多路输入输出**等独家玩法，以及**使用 melobot 妙妙小工具，便捷完成各种需求**等有趣玩法。
