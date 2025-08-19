# 源与适配器

## 添加源、适配器

此前的章节中，我们提到过源与适配器。实际上一个 bot 实例允许你添加任意协议，任意数量的源与适配器。

```python
from melobot import Bot

bot = Bot(...)
# 添加一个输入源
bot.add_input(...)
# 添加一个输出源
bot.add_output(...)
# 添加一个输入输出源
bot.add_io(...)
# 添加一个适配器
bot.add_adapter(...)
```

> 假设使用 in[A], out[A], io[A], @[A] 分别表示 A 协议的输入源、输出源、输入输出源和适配器
>
> 以下的 + 并无顺序之分，只是应用在同一 bot 实例上的意思

典型的组合方式：

| 组合方式 | 效果 |
| --- | --- |
| in[A] + @[A] | A 协议输入 √，A 协议输出 ×（因为有些协议不一定有输出源） |
| out[A] + @[A] | A 协议输入 ×，A 协议输出 √（因为有些协议不一定有输入源） |
| in[A] + out[A] + @[A] | A 协议输入 √，A 协议输出 √ |
| io[A] + @[A] | A 协议输入 √，A 协议输出 √ |

不太合理的组合：

| 组合方式 | 效果 |
| --- | --- |
| in[A] | A 协议输入 ×，A 协议输出 ×（没有适配器，协议无法正常工作） |
| out[A] | A 协议输入 ×，A 协议输出 ×（没有适配器，协议无法正常工作） |
| @[A] | A 协议输入 ×，A 协议输出 ×（没有源，协议无法正常工作） |
| @[A] + @[A] | A 协议输入 ×，A 协议输出 ×（同一协议的适配器不能添加第二次，且没有源） |

```{admonition} 提示
:class: tip
对 bot 实例来说，同时存在同一协议的源与适配器才能正常工作。
```

同协议多路输入、多路输出组合：

| 组合方式 | 效果 |
| --- | --- |
| in[A] + in[A] + ... + out[A] + out[A] + ... + @[A] | 产生协议 A 的多路输入和输出（例如 OneBot 协议的多个账号输入和输出） |

```{admonition} 提示
:class: tip
多路输入和输出，如何选择、分配和管理，后续的章节中会介绍。
```

多协议组合：

| 组合方式 | 效果 |
| --- | --- |
| in[A] + @[A] + out[B] + @[B] | A 协议输入 √，A 协议输出 ×；B 协议输入 ×，B 协议输出 √ |

多协议且多路的组合：

| 组合方式 | 效果 |
| --- | --- |
| io[A] + in[A] + @[A] + io[B] + io[B] + @[B] | A 协议 2 路输入，1 路输出；B 协议 2 路输入，2 路输出 |

## 添加协议栈

协议栈是一组**同协议**的源与适配器的包装，用于简化分步添加源、适配器的繁琐过程。

例如 OneBot 协议的协议栈对象，允许你直接添加源对象，内部自动添加适配器：

```python
from melobot.protocols.onebot.v11 import OneBotV11Protocol, ForwardWebSocketIO, \
    ReverseWebSocketIO

# 添加指定数量的源
protocol = OneBotV11Protocol(
    ForwardWebSocketIO(...), 
    ReverseWebSocketIO(...), 
    ...
)
# 随后把协议栈对象提供给 bot 实例
# 协议栈对象会自动完成适配器添加
bot.add_protocol(protocol)
```

其他协议的协议栈对象，可能会有更抽象的包装行为：例如简化掉源对象创建，让用户专注于输入/输出的参数本身。

## 获取适配器对象

很自然的，可以在适配器创建时获取：

```python
from melobot.protocols.onebot.v11 import Adapter
# 但一般只会在主脚本创建适配器
adapter = Adapter(...)
# 因为随后要提供给 bot 实例
bot.add_adapter(adapter)
```

在插件中，通过 bot 获取适配器：

```python
from melobot import get_bot

bot = get_bot()
adapter = bot.get_adapter(...)
```

或者通过依赖注入获取：

```python
from melobot.protocols.onebot.v11 import Adapter
@on_xxx(...)
async def _(adapter: Adapter) -> None: ...
```

## 获取源对象

很自然的，可以在源对象创建时获取：

```python
from melobot.protocols.onebot.v11 import ForwardWebSocketIO
# 但一般只会在主脚本创建源
src = ForwardWebSocketIO(...)
# 因为随后要提供给 bot 实例
bot.add_io(src)
```

在插件中，通过适配器获取源：

```python
src = adapter.get_isrc(...)
src = adapter.get_osrc(...)
```

此外，还可以在事件处理过程中，获取事件的来源适配器和来源输入源：

```python
@on_xxx(...)
async def _(event: Event) -> None:
    info = event.get_origin_info()
    adapter, src = info.adapter, info.in_src
```

## 协议标识

所有源对象和适配器对象，都拥有 `protocol` 属性，为协议字符串。表示了所适用的协议类型。

```python
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, Adapter

src = ForwardWebSocketIO(...)
adapter = Adapter(...)
assert src.protocol == "OneBot-v11@Meloland"
assert adapter.protocol == "OneBot-v11@Meloland"
```

一般协议字符串的风格为：`{PROTOCOL_NAME}-v{PROTOCOL_VERSION}@{PROTOCOL_SUPPORT_AUTHOR}`。

## 生命周期钩子

所有源对象和适配器对象都是可 hook 的。使用 {meth}`~.HookMixin.on` 方法可以绑定一个 hook 函数：

```python
# hook 函数同步异步均可
async def f1() -> None: ...
def f2() -> None: ...
```

使用 {class}`.SourceLifeSpan` 为源对象绑定 hook 函数：

```python
# 直接使用
from melobot.io import SourceLifeSpan
src.on(SourceLifeSpan.STARTED)(f1)

# 或取得装饰器
on_close = src.on(SourceLifeSpan.CLOSE)
on_close(f2)

# 或直接使用装饰器语法
@src.on(SourceLifeSpan.STOPPED)
async def f3() -> None: ...
```

使用  {class}`.AdapterLifeSpan` 为适配器对象绑定 hook 函数：

```python
# 直接使用
from melobot.adapter import AdapterLifeSpan
adapter.on(AdapterLifeSpan.STARTED)(f1)

# 或取得装饰器
on_started = adapter.on(AdapterLifeSpan.CLOSE)
on_started(f2)

# 或直接使用装饰器语法
@adapter.on(AdapterLifeSpan.STOPPED)
async def f3() -> None: ...
```

其他非通用属性与特性，请参考各个源、适配器的 API 文档。

## 总结

本篇主要说明了 melobot 源与适配器的使用方法和特性。

下一篇将重点说明：适配器层其他组件。
