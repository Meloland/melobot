# OneBot 消息操作

```{admonition} 相关知识
:class: note
如果你不知道什么是 OneBot “行为”和“行为操作”，建议先浏览：[行为的相关知识](../ob_refer/event-action)
```

消息操作作为 melobot 中最主要的行为操作，十分常用。

## 单条消息的构造

一般来说，发送纯文本内容是最普遍的，可以直接使用 melobot 的通用文本输出接口：

```python
from melobot import send_text
from melobot.protocols.onebot.v11 import on_message

@on_message(...)
async def _():
    await send_text("你好啊")
```

也可以使用具体协议的适配器的接口：

```python
from melobot.protocols.onebot.v11 import Adapter, on_message

@on_message(...)
async def _(adapter: Adapter):
    await adapter.send("你好啊")
```

如果要发送多媒体内容，则只能使用适配器的 {meth}`~.v11.Adapter.send` 接口。首先构造**消息段对象**，然后传入 {meth}`~.v11.Adapter.send` 作为参数。例如：

```python
from melobot.protocols.onebot.v11 import Adapter, on_message
from melobot.protocols.onebot.v11.adapter.segment import ImageSegment

@on_message(...)
async def _(adapter: Adapter):
    # 构造一个“图片”消息段，然后发送
    img = ImageSegment(file="https://www.glowmem.com/static/avatar.jpg")
    await adapter.send(img)
```

或者传递原始的 OneBot v11 消息段字典：

```python
from melobot.protocols.onebot.v11 import Adapter, on_message

@on_message(...)
async def _(adapter: Adapter):
    # 构造一个“图片”消息段字典，然后发送
    img = {
        "type": "image",
        "data": {
            "url": "https://www.glowmem.com/static/avatar.jpg"
        }
    }
    await adapter.send(img)
```

其他消息段参考：[消息段对象](onebot_v11_segment)

单条消息中，自然可能有多种类型的消息段同时存在。此时这样处理：

```python
from melobot.protocols.onebot.v11 import Adapter, on_message
from melobot.protocols.onebot.v11.adapter.segment import ImageSegment, TextSegment

@on_message(...)
async def _():
    # 例如文本和图片同时存在：
    await send([
        TextSegment("给你分享一张图片哦，这是 melobot 项目作者的头像"),
        ImageSegment(file="https://www.glowmem.com/static/avatar.jpg")
    ])
```

## 消息段的继承关系

在文档中，你会发现诸如 {class}`~.v11.adapter.segment.ImageSegment` 这样的类型，还会存在子类（{class}`~.v11.adapter.segment.ImageSendSegment` 和 {class}`~.v11.adapter.segment.ImageRecvSegment`）。这是为了提供更加精准的类型注解而产生的。所有这些类型只要有 `__init__` 方法，即可手动实例化并使用。

## 自定义消息段的构造

通过 {class}`~.v11.adapter.segment.Segment` 创建**自定义消息段**。

例如在某些 OneBot 实现端项目，存在一种自定义的消息段：touch 消息（戳一戳，双击头像）。对应的消息段数据结构如下：

```json
{
    "type": "touch",
    "data": {
        "id": "1574260633"
    }
}
```

如何让 melobot 发送这种自定义的消息段？非常简单：

```python
from melobot.protocols.onebot.v11.adapter.segment import Segment
# 临时构造自定义消息段
seg = Segment(type="touch", id="1574260633")
```

或者构造一种新的消息段类型：

```python
from melobot.protocols.onebot.v11.adapter.segment import Segment
from typing import Literal, TypedDict

class _TouchData(TypedDict):
    id: str

# 返回新类型 TouchSegment
# 后续的事件中，会自动将对应消息段初始化为 TouchSegment 类型
TouchSegment = Segment.add_type(Literal['touch'], _TouchData)
# 使用新的消息段类型来构造：
seg = TouchSegment(id="1574260633")
```

## 单条消息的其他发送方法

{meth}`~.v11.Adapter.send` 可根据当前触发事件，自动定位向何处发送消息。如果想要自定义发送目标，也很容易。只需要将 {meth}`~.v11.Adapter.send` 换成 {meth}`~.v11.Adapter.send_custom` 即可，它的第一参数与 {meth}`~.v11.Adapter.send_custom` 完全相同。

```python
from melobot.protocols.onebot.v11 import Adapter, on_message

@on_message(...)
async def _(adapter: Adapter):
    # 发送一个自定义目标的私聊消息，user_id 为 qq 号
    await adapter.send_custom(..., user_id=1574260633)
    # 发送一个自定义目标的群聊消息，group_id 为群号
    await adapter.send_custom(..., group_id=535705163)
```

## 获取 CQ 字符串

除使用消息段对象外，也可以使用**CQ 字符串**直接表示单条消息的所有消息内容。但你必须先构造消息段对象，然后才能生成 cq 字符串：

```python
from melobot.protocols.onebot.v11.adapter.segment import ImageSegment

img_cq: str = ImageSegment(file="https://example.com/test.jpg").to_cq()
```

```{admonition} 警告
:class: attention
CQ 字符串存在注入攻击的安全隐患。因此 melobot 不提供将 cq 字符串转为消息段的方法，也不允许接口直接发送 cq 字符串。
```

## 转发消息的构造

```{admonition} 相关知识
:class: note
如果你不知道转发消息的表示，主要依托于转发消息段和消息结点，建议先浏览：[转发消息与消息结点](../ob_refer/forward-msg.md)
```

### 转发消息段构造

构造转发消息段：

```python
from melobot.protocols.onebot.v11.adapter.segment import ForwardSegment

# forward_id 是转发 id，可通过消息事件的 get_datas("forward", "id") 获得
seg = ForwardSegment(forward_id)
```

此时，`seg` 变量已经是一条转发消息的等价表达了，直接使用适配器的 {meth}`~.v11.Adapter.send` 或 {meth}`~.v11.Adapter.send_custom` 发送即可。

### 消息结点构造

构造合并转发结点：

```python
from melobot.protocols.onebot.v11.adapter.segment import NodeSegment

# 这里的 msg_id 是已存在的消息的 id，可通过消息事件的 id 获得
refer_node = NodeSegment(id=msg_id)
```

构造合并转发自定义结点：

```python
from melobot.protocols.onebot.v11.adapter.segment import NodeSegment

# content 是消息内容，与上述消息段发送方法（例如 send, send_custom）的第一参数相同
# 后续参数是在转发消息中显示的，发送人昵称 和 发送人的qq号（int 类型）
node1 = NodeSegment(content="你好", name="melobot instance", uin=10001)

node2 = NodeSegment(
    content=ImageSegment(...),
    name="melobot instance",
    uin=10001
)

node3 = NodeSegment(
    content=[TextSegment(...), ImageSegment(...)],
    name="melobot instance",
    uin=10001
)
```

将消息结点组成列表，就是一条转发消息的等价表达了，使用 {meth}`~.v11.Adapter.send_forward` 来发送它：

```python
from melobot.protocols.onebot.v11 import Adapter, on_message

@on_message(...)
async def _(adapter: Adapter):
    await adapter.send_forward([refer_node, node1, node2, node3])
```

## 转发消息的其他发送方法

{meth}`~.v11.Adapter.send_forward` 可根据当前触发事件，自动定位要向何处发送消息。同理，要自定义发送目标，将 {meth}`~.v11.Adapter.send_forward` 换成 {meth}`~.v11.Adapter.send_forward_custom` 即可。

```python
from melobot.protocols.onebot.v11 import Adapter, on_message

@on_message(...)
async def _(adapter: Adapter):
    # 发送一个自定义目标的私聊转发消息，user_id 为 qq 号
    await adapter.send_forward_custom(..., user_id=1574260633)
    # 发送一个自定义目标的群聊转发消息，group_id 为群号
    await adapter.send_forward_custom(..., group_id=535705163)
```

## 总结

本篇主要说明了如何构造和发送各种消息。

下一篇将重点说明：其他行为操作及行为操作的等待与响应。
