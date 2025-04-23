# OneBot 行为操作

```{admonition} 相关知识
:class: note
如果你不知道什么是“行为”和“行为操作”，建议先浏览：[行为的相关知识](../ob_refer/event-action)
```

其他行为操作，和 {meth}`~.v11.Adapter.send` 类似，都由对应的行为操作方法产生。关于这些方法和它们的参数，参考 [OneBot v11 适配器的 API](onebot_v11_adapter)

它们的用法，与上一篇文章中的消息行为方法基本一致。可在事件处理方法中直接调用。

## 行为句柄

当直接使用 OneBot 的行为方法时，默认是尽快完成的。即不等待也不关心 OneBot 实现端是否成功完成了行为：

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

此时就需要行为句柄和行为句柄组了。melobot 的所有行为操作，包括刚才提及的协议特定操作，或通用的操作（例如 {func}`.send_text`），都会返回行为句柄。

melobot 是支持多源输出的。一个行为操作在通过行为操作函数创建后，会自动发送给匹配的协议适配器（一类或多类，当然同一协议只能有一个适配器），随后适配器会根据已有的输出源，以及输出源过滤规则，让指定的输出源执行行为操作。而每个行为操作函数，会返回一个“行为操作句柄组”对象，用于控制操作执行过程。

```python
from melobot.adapter import ActionHandle, ActionHandleGroup, Echo

# melobot 支持多个输出源，因此返回多个句柄组成的句柄组
handle_group: ActionHandleGroup = await adapter.send(...)

# 如果像教程开始那样，只使用添加了一个输入输出源
# 那么实际只会产生一个句柄，使用下标可以获得句柄
handle = handle_group[0]
# 使用 len 返回句柄数量
num = len(handle_group)
# 也可使用迭代语法迭代各个句柄
for handle in handle_group:
    handle: ActionHandle
    ...

# 获取句柄包含的行为对象和对应的输出源
action = handle.action
out_src = handle.out_src

# 等待句柄，即是等待被输出源通知行为已完成
# 获取返回值，即是响应结果，这在 melobot 中一般称作回应对象
echo = await handle
# 但需要注意：melobot 的机制规定，输出源可以没有回应
# 因此 echo 可能为空
echo: Echo | None
# 等待整个组，将会获得列表
echoes: list[Echo | None] = await handle_group

# 当需要确保回应不为空时，无需判空，而可以用 unwrap 方法
# 例如取出组中第一个句柄的回应，为空时自动发出异常
echo: Echo = await handle_group.unwrap(0)
# 同理，也可以一次性取出所有回应，保证它们都不为空
echoes: list[Echo] = await handle_group.unwrap_all()

# 使用异步迭代接口，可以直接以迭代方式获取回应
# 但需要注意：迭代顺序按回应完成的先后顺序
async for echo, handle in handle_group:
    echo: Echo | None
    handle: ActionHandle
    ...
# 使用 unwrap_iter 接口，具有非空保证性
# 但需要注意：迭代顺序按回应完成的先后顺序
async for echo in handle_group.unwrap_iter():
    echo: Echo
    ...
```

因此，如果只是想要保证有序性（即等待操作完成），实际上非常简单：

```python
# 保证所有输出源的操作完成后继续执行
await (await adapter.send(...))
```

对于 OneBot 的回应对象，可以使用 `data` 属性或 `result` 方法获取装有响应数据的字典。

```python
# 访问需要的响应数据（data 字段与 OneBot 中的数据结构一致）
# 依然建议使用下标访问，因为会有精确的类型注解
if echo.is_ok():
    # OneBot 的 data 字段也可能为空
    # 使用 OneBot Echo 独有的 result 方法来确保非空
    data: dict | None = echo.data
    data: dict = echo.result()
    msg_id = data['message_id']
```

关于回应对象，更多请参考 API 文档中的内容：[OneBot v11 回应](onebot_v11_echo)

```{admonition} 提示
:class: tip
**不建议频繁等待行为操作**。等待总是需要更多时间，大量使用会降低运行效率。

建议只在**行为操作必须有序**，或**需要返回数据**时才去等待。
```

句柄的本质是将操作和等待解耦。由此你可以发散自己的思维来使用它：例如安排一批操作，后续再集中等待，实现并发操作。

但只依靠行为句柄，是无法控制行为何时执行的，只能控制等待的时机。如果还需要控制执行时机，请使用 {func}`.lazy_action` 上下文管理器展开**惰性行为作用域**。

```python
from melobot.adapter import lazy_action

with lazy_action():
    # 此作用域内，所有行为操作都不会自动执行
    # 只是先产生了一个 pending 状态的句柄
    hg = await send_text(...)
    # 当需要执行时，手动调用 execute 方法
    # 直接执行整个组内所有句柄
    hg.execute()
    # 执行组内某一句柄
    handle: ActionHandle = ...
    handle.execute()
```

特别注意：**惰性行为作用域内，如果不执行 `execute` 就进行 await 会导致死锁**。但死锁在执行 `execute` 后会被解除。

## 自定义行为

和自定义消息段类似，有时候我们总是会需要自定义的 OneBot 行为类型的。一般这样构造：

```python
from melobot.protocols.onebot.v11 import Action

# 临时构造一个自定义行为
action = Action(type="action_type", params={"param1": 123456})

# 继承并构造一个新的 Action 类
class MyAction(Action):
    def __init__(self, param1: int) -> None:
        super().__init__("action_type", {"param1": 123456})

action = MyAction(123456)

# 通过 adapter 的通用 action 输出方法输出
await adapter.call_output(action)
handle_group = await adapter.call_output(action)
```

实际上，适配器所有行为操作，都是先在内部构建 {class}`~melobot.adapter.model.Action` 对象，再通过 {meth}`~melobot.adapter.base.Adapter.call_output` 输出。

而所有 OneBot v11 的行为对象，也可以在文档 [OneBot v11 行为类型](onebot_v11_action) 中找到。你完全可以手动构造，再使用 {meth}`~.v11.Adapter.call_output` 输出，这适用于更精细的控制需求。

## 总结

本篇主要说明了行为操作函数的用法，及行为操作的流程控制。

下一篇将重点说明：事件预处理。
