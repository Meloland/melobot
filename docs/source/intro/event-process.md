# OneBot 事件处理

## 绑定方法与处理方法

除了刚才使用的 {func}`.on_start_match` 方法，还有很多类似的方法，可以用于绑定事件处理的逻辑。

本文档将这些方法称为“绑定方法”，同时将绑定方法绑定的函数称为：“处理方法”或“处理函数”。

协议独立的绑定方法有：

- 绑定一个来自任意协议的，任意事件的处理方法：{func}`~melobot.handle.on_event`
- 绑定一个来自任意协议的，任意文本事件的处理方法：{func}`~melobot.handle.on_text`, {func}`~melobot.handle.on_command`、{func}`~melobot.handle.on_start_match`、{func}`~melobot.handle.on_contain_match`、{func}`~melobot.handle.on_full_match`、{func}`~melobot.handle.on_end_match`、{func}`~melobot.handle.on_regex_match`

OneBot v11 协议特有的绑定方法有：

- 绑定一个任意 OneBot v11 事件的处理方法：{func}`~.v11.handle.on_event`
- 绑定一个消息事件的处理方法：{func}`~.v11.handle.on_message`、{func}`~.v11.handle.on_at_qq`、
- 绑定一个请求事件的处理方法：{func}`~.v11.handle.on_request`
- 绑定一个通知事件的处理方法：{func}`~.v11.handle.on_notice`
- 绑定一个元事件的处理方法：{func}`~.v11.handle.on_meta`

这些绑定方法的参数很多，你可以先简单浏览。关于这些方法的使用，后续会详细讲解。现在让我们先学习一些基础知识。绑定方法的使用都一样，直接用作装饰器即可：

```python
from melobot.handle import on_start_match

@on_start_match(...)
async def func() -> None:
    # func 就是事件处理方法，可以是同步或异步函数，无返回值
    # func 的内容就是事件处理的逻辑
    ...
```

提示：所有绑定方法绑定处理方法后，都不提供异步安全担保。这意味着**处理方法完全可能被并发调用**。

后续章节中会介绍如何处理异步安全的问题。

## 获取 OneBot 事件对象

现在我们已经学会绑定事件处理方法了。如果事件处理方法，能**获得触发事件的一些信息，基于这些信息做针对性处理**就更好了。

通过类型注解驱动的依赖注入，即可方便地在处理方法中获得触发的事件。例如使用 {class}`.MessageEvent` 注解参数，melobot 将知道你需要一个消息事件作为 event 参数的值：

```python
from melobot.protocols.onebot.v11 import MessageEvent, on_message

@on_message(...)
async def func1(event: MessageEvent):
    ...
```

或者使用通用接口获取：

```python
from melobot.protocols.onebot.v11 import on_message
from melobot.handle import get_event

@on_message(...)
async def func1():
    e = get_event()
    ...
```

或者使用通用上下文变量获取：

```python
from melobot.protocols.onebot.v11 import on_message
from melobot.handle import event

@on_message(...)
async def func1():
    e = event
    ...
```

需要注意的是，通用接口以及通用上下文变量，将标注为 melobot 的事件基类型 {class}`~melobot.adapter.model.Event`，这可能不是你想要的，因此可以自行添加标注：

```python
e: MessageEvent = get_event()
```

其他 OneBot v11 事件类型也同样可以用于注解。详情请参考 API 文档：[OneBot v11 事件类型](onebot_v11_event)

这些事件也有着各自的属性和方法，API 文档中也已说明。

## 通用绑定函数与依赖注入

另外，通用的绑定方法，依然可以使用协议特定的事件进行注入：

```python
from melobot.handle import on_event
from melobot.protocols.onebot.v11 import MessageEvent

# 此通用接口支持任意事件类型，因此可以接收到 MessageEvent 这种子类型
@on_event(...)
async def func(event: MessageEvent) -> None:
    # 依赖注入会有类型担保，由于标注了 MessageEvent 类型，
    # 因此 event 如果不是 MessageEvent 子类型，则不会进入处理方法
    # 由此实现了智能的类型收窄
    ...
```

同理，对于上面提到的，通用的文本事件的绑定接口，由于 {class}`.MessageEvent` 是文本事件基类 {class}`.TextEvent` 的子类，因此这样也是可以的：

```python
from melobot.handle import on_start_match
from melobot.protocols.onebot.v11 import MessageEvent

# 此接口首先限制必须为 TextEvent
@on_start_match(...)
async def func(event: MessageEvent) -> None:
    # 随后注解将其收窄到 MessageEvent 类型
    ...
```

但这样显然就不太可以了：

```python
from melobot.handle import on_start_match
from melobot.protocols.onebot.v11 import NoticeEvent

# 此接口首先限制必须为 TextEvent
@on_start_match(...)
async def func(event: NoticeEvent) -> None:
    # NoticeEvent 不是 TextEvent 子类，
    # NoticeEvent 还没到依赖注入类型收窄，就过不了 on_start_match 这一关
    ...
```

注意：OneBot v11 协议中，只有 {class}`.MessageEvent` 是 {class}`.TextEvent` 的子类。

## 基于事件信息的处理

通过事件对象提供的信息，可以实现更有趣的处理逻辑：

```{code} python
from melobot.protocols.onebot.v11 import on_start_match, MessageEvent
from melobot import send_text

OWNER_QID = 10001

@on_start_match(".sayhi")
async def say_hi(e: MessageEvent) -> None:
    # 如果消息不来源于机器人主人，则不做任何处理
    if e.sender.user_id != OWNER_QID:
        return

    # 否则根据时间，回复不同的内容
    hour = ... # 获取当前 hour 的逻辑

    if 0 <= hour < 6:
        await send_text("主人凌晨好~")
    elif 6 <= hour < 12:
        await send_text("主人早上好~")
    elif 12 <= hour < 18:
        await send_text("主人下午好~")
    else:
        await send_text("主人晚上好~")
```

## OneBot 消息段

多数 OneBot 事件结构较为简单，查询文档即可使用。但需要额外提一下 OneBot 消息事件。

获取消息中的所有纯文本内容，使用 {meth}`~.MessageEvent.text` 或 {meth}`~.MessageEvent.textlines` 即可。

如果要获取多媒体内容，例如图片、表情等，可以使用 {meth}`~.MessageEvent.get_segments` 方法获得对应的**消息段对象列表**。

```{admonition} 相关知识
:class: note
如果你不知道，消息段对象是消息内容的表示方式之一，建议先浏览：[消息内容的数据结构](../ob_refer/msg)
```

需要哪种类型的消息段，就传递哪种消息段的 `type` 作为参数：

```python
from melobot.protocols.onebot.v11 import MessageEvent, ImageSegment, on_message

@on_message(...)
async def _(e: MessageEvent):
    # 获取当前这条消息所有的图片（image 是图片消息段的类型名）
    images = e.get_segments("image")
    # 或传递消息段类型来获取
    images = e.get_segments(ImageSegment)
```

随后，读取消息段对象的 data 字段可获得相关数据。data 字段与 OneBot 协议规定一致。

```python
# 遍历所有图片的 url 和文件名
for img in e.get_segments("image"):
    # 更建议使用下标获取，而不是 get，这样类型提示就可以完美工作
    print(img.data["url"])
    print(img.data["file"])
```

```{admonition} 相关知识
:class: note
所有媒体内容对应的消息段表示：[OneBot 消息段](https://github.com/botuniverse/onebot-11/blob/master/message/segment.md)

此链接也包含了每种消息段的 type 标识，及 data 字段拥有的参数。
```

如果只需要 data 字段的某一参数，使用 {meth}`~.MessageEvent.get_datas` 即可：

```python
from melobot.protocols.onebot.v11 import MessageEvent, on_message

@on_message(...)
async def _(e: MessageEvent):
    # 获取当前这条消息，所有图片的 url
    img_urls = e.get_datas("image", "url")
    # 类似的方法
    img_urls = e.get_datas(ImageSegment, "url")
```

## 总结

本篇主要说明了如何绑定事件处理方法，以及如何通过事件对象的属性和方法，来实现更丰富的处理逻辑。

下一篇将重点说明：如何构造和发送各种消息。
