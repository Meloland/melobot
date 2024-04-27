# 其他行为操作

```{admonition} 相关知识
:class: note
如果你不知道什么是“行为”和“行为操作”，建议先浏览：[行为的相关知识](../references/event-action)
```

其他行为操作都由对应的行为操作函数产生。关于这些函数和它们的参数，参考：[行为操作函数](action-operations)

它们的用法，与上一篇文章中的消息行为函数基本一致。都是异步函数，可在事件处理方法中直接调用。例如 {func}`.msg_recall` 这个行为操作函数：

```python
from melobot.context import msg_recall

@plugin.on_xxx(...)
async def _():
    # 直接在事件处理过程中使用（具体参数自行点击查看）
    await msg_recall(...)
```

## 行为响应

通过 API 参考文档，可以发现：大多数行为操作函数都有参数 `wait`。当设置 `wait=False` 时，产生的行为操作将不会被等待，自然也就无法再获得响应。

如果我们不关心行为操作何时完成、也不需要响应，那么直接令 `wait=False`。此时的行为操作将尽快完成：

```python
@plugin.on_xxx(...)
async def _():
    # 以下可以是任何拥有 wait 参数的行为操作函数
    await send(..., wait=False)
    await msg_recall(..., wait=False)
```

当我们需要行为的响应时，令 `wait=True`，并异步等待 {attr}`~.ActionHandle.resp` 属性：

```python
@plugin.on_xxx(...)
async def _():
    # response 是响应
    response = await send(..., wait=True).resp

    # 不想行为操作一执行就立刻等待？没问题！
    # 先获取 action handle
    handle = send(..., wait=True)
    # do something else now
    ...

    # 需要这个响应时：
    response = await handle.resp
```

接下来可以用响应判断行为操作是否成功，并获得响应数据：

```python
# 判断是否成功
if response.is_ok():
    print("行为操作成功")
    print(f"响应数据为：{response.data}")
elif response.is_failed():
    print("行为操作失败")
```

响应对象的 {attr}`~.ResponseEvent.data` 属性是一个字典。不同的行为操作函数，返回数据的格式不同。这些格式在 API 文档有标注：[行为操作函数](action-operations)

有时候，我们只是希望一个行为操作被 OneBot 实现程序完成后，再执行之后的代码。我们实际上不关心响应。这时就不需要 {attr}`~.ActionHandle.resp` 属性了：

```python
@plugin.on_xxx(...)
async def _():
    # 与等待 resp 属性不同，它返回 None
    await send(..., wait=True).wait()

    # 不想行为操作一执行就立刻等待？没问题！
    # 先获取 action handle
    handle = send(..., wait=True)
    # now do something else
    ...

    # 需要等待这个行为操作完成时
    await handle.wait()
```

```{admonition} 提示
:class: tip
**不建议频繁等待行为操作**。等待总是需要更多时间，大量使用会降低运行效率。

建议只在**必须等待此操作完成才能继续执行**，或**需要返回数据**时才去等待。
```

```{admonition} 注意
:class: caution
某些时候，你可能会想要行为操作以任务方式执行，而不直接 await：`asyncio.create_task(send(...))`

**但是行为操作函数并不能转化为任务**。需要创建为任务执行，只需要以同步方式调用：`send(...)`
```

## 魔改行为对象

实际上，行为操作函数的逻辑分为两步：

- 产生一个 {class}`.BotAction` 对象（行为对象）
- 将这个行为提交给 OneBot 实现程序执行

某些情况下，我们可能不希望行为对象构建完成后，就被直接发送。大多数行为操作函数都拥有 `auto` 参数。`auto=False` 时，行为操作函数产生行为对象后，就会立即返回：

```python
@plugin.on_xxx(...)
async def _():
    # 以下可以是任何拥有 auto 参数的行为操作函数
    handle1 = send(..., auto=False)
    # 当前这个操作的行为对象
    handle1.action
```

随后可以修改这个行为对象（做一些操作），再手动提交这个行为操作即可：

```python
@plugin.on_xxx(...)
async def _():
    handle = send(..., auto=False)
    handle.action.params = {...}    # 例如此处修改行为的参数
    # 手动提交
    handle.execute()
```

需要等待这个行为操作？没问题！

```python
@plugin.on_xxx(...)
async def _():
    handle = send(..., wait=True, auto=False)
    handle.action.params = {...}    # 对 action 操作

    # 手动提交并等待响应
    await handle.execute().resp
    # 或者手动提交并等待
    await handle.execute().wait()

    # 或者手动提交不立刻等待
    await handle.execute()
    # now do something else
    ...
    # 开始等待
    await handle.resp
    await handle.wait()
```

## 自定义行为操作

和之前提到的自定义消息段一样，如果需要发送 OneBot 标准中不存在的自定义行为操作，可以使用 {func}`.custom_action` 完成：

```python
from melobot.context import custom_action

# 因为有参数 wait 和 auto，因此可以等待
action = custom_action(type="custom_type", 
                       params={"param1": 123, "param2": "12345"}, 
                       wait=True)
# 作为行为操作函数的一种，之后的用法类似
```

当然，你也可以再自行封装一下 :)

```python
from functools import partial

def my_action(param1: int, param2: str, wait: bool=False):
    return custom_action(type="custom_type", 
                         params={"param1": param1, "param2": param2}, 
                         wait=wait)

@plugin.on_xxx(...)
async def _():
    await my_action(123, "12345")
    await my_action(123, "12345", wait=True).wait()
    await my_action(456, "hello", wait=True).resp
```

## 总结

本篇主要说明了行为操作函数的用法，及行为操作的流程控制。

下一篇将重点说明：事件预处理过程。
