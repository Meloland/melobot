# 适配器层其他组件

## 通用行为操作

对于所有协议支持，都会实现一些基础的行为操作。例如“输出文本”这一操作：

```python
from melobot import send_text
# 实际上它来源于：
from melobot.adapter.generic import send_text
```

在模块 `melobot.adapter.generic` 中还有 {func}`~.generic.send_media`, {func}`~.generic.send_image` 等通用行为方法，具体用法参考 [这些方法的 API 文档](adapter_generic_methods)。

值得注意的是，所有协议支持必然实现“输出文本”这一操作。但其余通用行为操作若未实现，内部会自动回退到“输出文本”这一操作，然后输出相关内容的简短提示。

例如 {func}`~.generic.send_media` 方法，在协议支持未实现时，内部回退到输出以下字符串文本：`"[melobot media: xxx]"`。

## 事件

各种协议支持的“事件”类型，显然会有不同实现。但它们都继承于 melobot 内部基类型 {class}`~melobot.adapter.model.Event`。

```python
# 从原始位置导入
from melobot.adapter.model import Event
# 或从更高层的模块导入
from melobot.adapter import Event
```

基事件类型的重要属性字段包括：
- `time`：创建的时间（浮点时间戳）
- `id`：唯一 id，若协议支持未重写 id 生成逻辑，则使用内部雪花算法生成
- `protocol`：协议字符串标识，与对应适配器、源的协议字符串一致

其他属性和方法参阅对应 API 文档： {class}`~melobot.adapter.model.Event`。

### 内容字段

事件还有一重要属性 `contents`，用于保存“通用内容信息”。

各协议支持显然拥有自己的逻辑，来存储和处理事件中存在的各种内容信息，例如：文本，图像，音频等信息内容。假设需要实现一个“查询天气”的功能，但希望它同时对协议 A 和 B 生效，第一步就需要从事件中提取对应的“消息内容”（文本内容），但两种协议获取这一内容的方法，一般是不同的。

问题显而易见：**适配越多协议，处理输入和处理输出的逻辑就越复杂，编写和维护代码的工作量也越大**。

melobot 对于减轻“处理输入”工作的一个思路是：允许各种协议支持，内部自行组织、管理各种内容信息，并提供独特的接口。但需要填充“通用内容字段”，以减轻获取关键信息的繁琐工作。这一字段便是 `contents`。

```python
# 此字段的类型注解如以下所示：
# 由于是序列，所以可以包含“多个内容”
contents: Sequence[Content] | None

# Content 对象一般称为“通用内容实体”
# 而 Content 类是所有通用内容的基类:
from melobot.adapter.content import Content, TextContent
```

对于多协议实现“查询天气”功能的例子，可以利用 {class}`.TextContent` 实现:

```python
from melobot import send_text
from melobot.adapter import Event
# 文本内容实体
from melobot.adapter.content import TextContent
# 使用通用事件绑定方法，处理来自各种协议的事件
from melobot.handle import on_event

@on_event(...)
async def handle_text_in_event(event: Event) -> None:
    if event.contents is None:
        return
    msg = "".join(
        [c.text for c in event.contents if isinstance(c, TextContent)]
    )
    # 接下来就是处理文本，决定是否需要查询天气，如何查询天气
    # 此时已经与特定协议无关
    ...

    # 需要进行任何输出？别忘了通用行为操作
    await send_text(...)
```

其他内容实体，例如图像、视频、音频等，请参考： [内容实体的 API 文档](generic_content_entities)。

### 文本事件

大多数协议支持中，一般都有一些事件主要包含字符串内容，即文本内容。例如 OneBot 协议中的消息事件，Console 协议中的标准输入流事件。

这种情况过于常见，melobot 额外提供抽象类：{class}`.TextEvent`。所有协议支持中，如有满足此接口的事件，即可通过事件绑定方法 {func}`.on_text` 进行处理。

```python
from melobot.adapter import TextEvent
from melobot.handle import on_text

@on_text(...)
async def _(e: TextEvent):
    # 获取事件中的所有文本内容
    msg: str = e.text
    # 获取事件中的所有文本内容（逐行）
    msg_lines: list[str] = e.textlines
```

## 行为

各种协议支持的“行为”类型，显然会有不同实现。但它们都继承于 melobot 内部基类型 {class}`~melobot.adapter.model.Action`。

```python
# 从原始位置导入
from melobot.adapter.model import Action
# 或从更高层的模块导入
from melobot.adapter import Action
```

基行为类型的重要属性字段包括：
- `time`：创建的时间（浮点时间戳）
- `id`：唯一 id，若协议支持未重写 id 生成逻辑，则使用内部雪花算法生成
- `protocol`：协议字符串标识，与对应适配器、源的协议字符串一致
- `trigger`：触发此行为的事件，一般为创建行为对象时当前上下文中的事件。但部分协议支持可能重写逻辑，请勿过度依赖默认情况。

其他属性和方法参阅对应 API 文档： {class}`~melobot.adapter.model.Action`。

## 回应

各种协议支持的“回应”类型，显然会有不同实现。但它们都继承于 melobot 内部基类型 {class}`~melobot.adapter.model.Echo`。

```python
# 从原始位置导入
from melobot.adapter.model import Echo
# 或从更高层的模块导入
from melobot.adapter import Echo
```

基回应类型的重要属性字段包括：
- `time`：事件创建的时间（浮点时间戳）
- `id`：唯一 id，若协议支持未重写 id 生成逻辑，则使用内部雪花算法生成
- `protocol`：协议字符串标识，与对应适配器、源的协议字符串一致

其他属性和方法参阅对应 API 文档： {class}`~melobot.adapter.model.Echo`。

## 行为句柄与行为句柄组

此前已经介绍过行为句柄、行为句柄组的用法。

如果你忘了，请回到这一部分：[行为句柄、行为句柄组](action_handle_usage)

或许再看一遍，也会有更深刻的理解 :)

## 总结

本篇主要说明了 melobot 适配器层其他部件的功能和特性。

下一篇将重点说明：事件处理流与机制。
