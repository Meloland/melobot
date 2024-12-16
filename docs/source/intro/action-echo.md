# OneBot 行为操作

```{admonition} 相关知识
:class: note
如果你不知道什么是“行为”和“行为操作”，建议先浏览：[行为的相关知识](../ob_refer/event-action)
```

其他行为操作，和 {meth}`~.v11.Adapter.send` 类似，都由对应的行为操作方法产生。关于这些方法和它们的参数，参考 [OneBot v11 适配器的 API](onebot_v11_adapter)

它们的用法，与上一篇文章中的消息行为方法基本一致。可在事件处理方法中直接调用。

## 行为句柄

当直接使用行为方法时，默认是尽快完成的。即不等待也不关心 OneBot 实现端是否成功完成了行为：

```python
# 发送消息而不等待，也不关心是否成功
await adapter.send(...)

# 因此在某些情况下，以下的一系列行为操作可能是无序的：
await adapter.send("我想要这条消息先被看到")
await adapter.send("但是这条可能才是先被发出去的")
await adapter.send("也可能是这条")

# 而且有些行为需要响应数据
await adapter.get_group_list()
# 如何等待返回的数据呢？
```

此时就需要行为句柄了：

```python
# 使用 with_echo 装饰原行为方法
waited_send = adapter.with_echo(adapter.send)
# 获得一个元组，其中每个元素就是行为句柄
# 因为 melobot 支持多个输出源，因此会有多个句柄
handles = await waited_send(...)

# 如果像教程开始那样，只使用 add_io 添加了一个输入输出源
# 那么就是一个输入，一个输出源。因此取第一个元素即可
hs = await waited_send(...)
handle = hs[0]

# 等待句柄，即是等待被 OneBot 实现端通知行为已完成
# 等待并获取返回值，即是这个行为的响应结果，这在 melobot 中一般称作回应对象
echo = await handle
# 访问需要的响应数据（data 字段与 OneBot 中的数据结构一致）
# 依然建议使用下标访问，因为会有精确的类型注解
msg_id = echo.data['message_id']
```

关于回应对象，更多请参考 API 文档中的内容：[OneBot v11 回应](onebot_v11_echo)

当然，有时候你可能有大量的行为操作需要等待，那这时可以使用更方便的上下文管理器：

```python
from melobot.protocols.onebot.v11 import Adapter, on_message, EchoRequireCtx

@on_message(...)
async def _(adapter: Adapter):
    with EchoRequireCtx().unfold(True):
        # 全部都会等待
        await adapter.send("我一定先被看到")
        await adapter.send("我一定是第二条消息")
```

一整个函数都需要等待时，可以使用 {func}`.unfold_ctx` 装饰器：

```python
from melobot.protocols.onebot.v11 import Adapter, on_message, EchoRequireCtx
from melobot.utils import unfold_ctx

@on_message(...)
@unfold_ctx(lambda: EchoRequireCtx().unfold(True))
async def _(adapter: Adapter):
    # 全部都会等待
    await adapter.send("我一定先被看到")
    await adapter.send("我一定是第二条消息")
```

```{admonition} 提示
:class: tip
**不建议频繁等待行为操作**。等待总是需要更多时间，大量使用会降低运行效率。

建议只在**行为操作必须有序**，或**需要返回数据**时才去等待。
```

```{admonition} 提示
:class: tip
句柄的本质是将操作和等待解耦。由此你可以发散自己的思维来使用它：

例如安排一批操作，后续再集中等待，实现并发操作。
```

## 自定义行为

和自定义消息段类似，有时候我们总是会需要自定义的 OneBot 行为类型的。一般这样构造：

```python
from melobot.protocols.onebot.v11.adapter.action import Action

# 临时构造一个自定义行为
action = Action(type="action_type", params={"param1": 123456})

# 继承并构造一个新的 Action 类
class MyAction(Action):
    def __init__(self, param1: int) -> None:
        super().__init__("action_type", {"param1": 123456})

action = MyAction(123456)

# 通过 adapter 的通用 action 输出方法输出
await adapter.call_output(action)

# 需要等待时，这样设置：
action.set_echo(True)
handles = await adapter.call_output(action)
```

实际上，适配器所有行为操作，都是先在内部构建 {class}`~.v11.adapter.action.Action` 对象，再通过 {meth}`~.v11.Adapter.call_output` 输出。

而所有内置行为对象，也可以在文档 [OneBot v11 行为类型](onebot_v11_action) 中找到。你完全可以手动构造，再使用 {meth}`~.v11.Adapter.call_output` 输出，这适用于更精细的控制需求。

## 总结

本篇主要说明了行为操作函数的用法，及行为操作的流程控制。

下一篇将重点说明：事件预处理。
