# 其他行为操作

```{admonition} 相关知识
:class: note
如果你不知道什么是“行为”和“行为操作”，建议先浏览：[行为的相关知识](../references/event-action)
```

其他行为操作都由对应的行为操作函数产生。关于这些函数和它们的参数，参考：[行为操作函数](action-operations)

它们的用法，与前一篇文章中发送消息的行为的函数基本一致。都是异步函数，可在事件处理方法中直接调用。例如 {func}`.msg_recall` 这个行为操作函数：

```python
await msg_recall(...)
```

## 行为响应

行为操作的响应被称为“行为响应”，以下简称“响应”。响应是 melobot 发送行为操作给 OneBot 实现程序后，等待 OneBot 完成后的结果。响应**被用来检查行为有没有被正确处理，或被用来获取返回数据**。

响应在 melobot 中是一种事件类型。参考：{class}`.ResponseEvent`。

通过 API 参考文档，可以发现：大多数行为操作函数都有参数 `wait`。当不指定这个 wait 参数，或设置 `wait=False` 时，行为操作函数在将行为传递给 OneBot 实现程序后，就**立即返回**。即使这个行为**还没有被 OneBot 实现程序“完成”**（即提交给 qq 服务器）。

```python
"""
这里可以是任何拥有 wait 参数的行为操作函数
"""
res = await send(...)                    # res 为 None
res = await msg_recall(..., wait=False)  # res 为 None
```

而如果设置了 `wait=True`，此时返回的结果会是一个响应对象（{class}`.ResponseEvent` 对象）。此时的行为操作函数，必须等待 OneBot 将这个行为“完成”了，并获得一个响应，才能产生返回值。

```python
"""
这里可以是任何拥有 wait 参数的行为操作函数
"""
resp = await msg_recall(..., wait=True)  # resp 为响应对象
```

根据响应对象，可以判断行为是否成功：

```python
if resp.is_ok():
    ...
# 或
if resp.is_failed():
    ...
```

如果行为有返回数据，还可以获得这些返回数据：

```python
if resp.is_ok():
    data = resp.data
    # 使用返回数据做一些别的事情
    ...
```

响应对象的 {attr}`~.ResponseEvent.data` 属性是一个字典。不同的行为操作函数，会有不同的返回数据。所有可以返回响应的行为操作函数，都标注了返回数据的数据结构，可自行参考 API 文档：[行为操作函数](action-operations)

```{admonition} 注意
:class: caution
对于特定的行为操作，返回数据可能为空。但是只要等待响应（`wait=True`），就一定会产生响应。

没有 `wait` 参数的行为操作函数，不支持返回响应。
```

```{admonition} 提示
:class: tip
不建议**大量使用等待响应**（`wait=True`）。等待响应总是需要更多时间，大量使用会降低运行效率。

建议只在**必须等待此行为完成才能继续执行**，或**需要返回数据**时才去等待响应。
```

## 自定义的行为操作

实际上，行为操作函数的逻辑分为两步：

- 产生一个 {class}`.BotAction` 对象（行为对象）
- 格式化这个行为对象，然后发送给 OneBot 实现程序执行

某些情况下，我们可能不希望行为对象构建完成后，就被直接发送。大多数行为操作函数都拥有 `auto` 参数，当 `auto=False` 时，行为操作函数产生行为对象后，就会立即返回。

```python
"""
这里可以是任何拥有 auto 参数的行为操作函数
"""
action = await send(..., auto=False)            # action 为行为对象
action = await get_group_list(..., auto=False)  # action 为行为对象
```

随后可以操作这个行为对象，操作完成后，使用 {func}`.take_custom_action` 手动发送这个行为：

```python
# wait=False，对应不产生响应的行为对象
action = await send(...)
# 一些对 action 的操作
...
res = await take_custom_action(action)  # res 为 None

# wait=True，对应产生响应的行为对象
action = await send(..., wait=True)
# 一些对 action 的操作
...
resp = await take_custom_action(action)  # resp 为响应对象
```

```{admonition} 注意
:class: caution
没有 `auto` 参数的行为操作函数，不支持获取行为对象后手动操作。
```

和之前提到的自定义消息段一样，如果需要发送 OneBot 标准中不存在，但 OneBot 实现程序支持的行为，使用 {func}`.make_action` 构造行为对象：

```python
# 指定 need_resp=True，则产生一个有响应的行为对象；反之则无响应
action = make_action(type="custom_type", 
                     params={"param1": 123, "param2": "12345"}, 
                     need_resp=True)
# 发送
resp = await take_custom_action(action)
```

```python
# 你也可以再自行封装一下 :)
from functools import partial

def my_action(param1: int, param2: str, wait: bool=False):
    return make_action(type="custom_type", 
                       params={"param1": param1, "param2": param2}, 
                       need_resp=wait)

await take_custom_action(my_action(123, "12345"))
await take_custom_action(my_action(123, "12345", wait=True))
```

## 总结

本篇主要说明了如何实现其他行为操作与行为操作的响应。

下一篇将重点说明：事件预处理过程和对应的方法。