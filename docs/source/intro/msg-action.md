# 消息操作

```{admonition} 相关知识
:class: note
如果你不知道什么是“行为”和“行为操作”，建议先浏览：[行为的相关知识](../references/event-action)
```

消息操作作为 melobot 中最主要的行为操作，十分常用。

## 单条消息的构造

```{admonition} 相关知识
:class: note
如果你不知道单条消息的表示方式，有“cq 字符串”和“消息段”两种格式，建议先浏览：[消息内容的数据结构](../references/msg)
```

一般来说，发送纯文本内容是最普遍的，方法也十分简单：

```python
from melobot.context import send

@plugin.on_xxx(...)
async def _():
    await send("你好啊")
```

如果要发送多媒体内容，首先要通过各自的消息段构造函数构造**消息段对象**，然后直接传入 {func}`.send` 作为参数。

例如使用 {func}`.image_msg` 构造图片内容：

```python
from melobot.models import image_msg

@plugin.on_xxx(...)
async def _():
    # 构造一个“图片”消息段，然后发送
    img = image_msg("https://www.glowmem.com/static/avatar.jpg")
    await send(img)
```

其他消息段构造函数，及这些函数的参数，参考：[消息段构造函数](#msg-build)

单条消息中，自然可能有多种类型的消息段同时存在。此时这样处理：

```python
from melobot.models import text_msg, image_msg

@plugin.on_xxx(...)
async def _():
    # 例如文本和图片同时存在：
    await send([
        text_msg("给你分享一张图片哦，这是 melobot 项目作者的头像"),
        image_msg("https://www.glowmem.com/static/avatar.jpg")
    ])
```

## 自定义消息段的构造

一般来说，melobot 自带的消息段构造函数已足够使用。但是某些 OneBot 实现程序，可能会支持自定义的消息段，**这些自定义消息段，是 OneBot 标准中没有的**。

这时你可以使用 {func}`.custom_type_msg` 来构造这些**自定义消息段**。

例如在知名 OneBot 实现项目 [OpenShamrock](https://github.com/whitechi73/OpenShamrock) 中，存在一种自定义的消息段 [touch 消息](https://whitechi73.github.io/OpenShamrock/message/special.html#%E6%88%B3%E4%B8%80%E6%88%B3-%E5%8F%8C%E5%87%BB%E5%A4%B4%E5%83%8F)（戳一戳，双击头像）。对应的消息段数据结构如下：

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
from melobot.models import custom_type_msg

@plugin.on_xxx(...)
async def _():
    touch = custom_type_msg("touch", {"id": "1574260633"})
    await send(touch)

# 或者再自行封装一下 :)
def touch_msg(uid: int):
    return custom_type_msg("touch", {"id": str(uid)})

@plugin.on_xxx(...)
async def _():
    await send(touch_msg(1574260633))
```

## 单条消息的其他发送方法

{func}`.send` 可根据当前触发事件，自动定位向何处发送消息。如果想要自定义发送目标，也很容易。只需要将{func}`.send` 换成 {func}`.send_custom` 即可，它的第一参数与 {func}`.send` 完全相同。

```python
from melobot.context import send_custom

@plugin.on_xxx(...)
async def _():
    # 发送一个自定义目标的私聊消息，userId 为 qq 号
    await send_custom(..., isPrivate=True, userId=1574260633)
    # 发送一个自定义目标的群聊消息，groupId 为群号
    await send_custom(..., isPrivate=False, groupId=535705163)
```

如果要回复消息事件对应的那条消息，按照之前学到的，应该这样做：

```python
from melobot.models import reply_msg, text_msg

@plugin.on_xxx(...)
async def _(e = msg_event()):
    # reply_msg 是消息段构造函数之一，用于构造回复消息段
    # 消息事件的 id 属性值存储消息的 id
    await send([reply_msg(e.id), text_msg("你好哇")])
```

这是十分繁琐的，但是“发送回复消息”这一行为也很普遍。使用 {func}`.send_reply` 简化：

```python
from melobot.context import send_reply

@plugin.on_xxx(...)
async def _():
    # send_reply 第一参数与 send 完全相同
    await send_reply("你好哇")
```

想要提前结束事件处理方法，一般会用 `return`：

```python
@plugin.on_xxx(...)
async def _(e = msg_event()):
    if e.sender.id != 1574260633:
        await send("你好~ 你不是我的主人哦")
        return
    # 接下来是机器人主人的处理逻辑
    await send("主人好")
```

用 {func}`.finish` 可以把 `return` 简化掉：

```python
from melobot.context import finish

# 刚才的代码，使用 finish 优化后
@plugin.on_xxx(...)
async def _(e = msg_event()):
    if e.sender.id != 1574260633:
        # finish 运行完就返回啦，不需要显式 return
        await finish("你好~ 你不是我的主人哦")
    await send("主人好")
```

在嵌套函数调用中，{func}`.finish` 实际上可以退出任意深度的嵌套函数调用：

```python
@plugin.on_xxx(...)
async def _():
    await a()
    await b()
    ...

async def a() -> None:
    ...
    # 退出 a 函数后，直接从 say_hi 的 a 函数调用点直接退出
    await finish(...)

async def b() -> None:
    ...
    # 退出 b 函数后，直接从 say_hi 的 b 函数调用点直接退出
    await finish(...)
```

同理，{func}`.send_reply` 对应的提前结束版本是：{func}`.reply_finish`。使用方法与 {func}`.finish` 基本一致。但是它发送的是回复消息。

```{admonition} 提示
:class: tip
{func}`.finish` 和 {func}`.reply_finish`，只能在事件处理过程中使用。
```

## 使用 CQ 字符串

除使用消息段对象外，也可以使用**CQ 字符串**直接表示单条消息的所有消息内容。

只要是有 `cq_str` 参数的行为操作函数，设置 `cq_str=True` 后，此行为操作函数将不再认为字符串是纯文本内容。而认为字符串是可解释的 CQ 字符串。

```python
@plugin.on_xxx(...)
async def _():
    # 第一参数是字符串，无论内容是什么，都是纯文本消息内容
    await send("[CQ:face,id=178]你好啊")
    # 启用了 cq_str 后，第一参数如果是字符串，将会被解释为 CQ 字符串
    # 如果存在有效的 CQ 字符串，将会被直接应用
    await send("[CQ:face,id=178]你好啊", cq_str=True)
```

```{admonition} 提示
:class: tip
你可自行浏览 API 文档：[行为操作函数](action-operations)，查看哪些支持 `cq_str` 参数。
```

```{admonition} 警告
:class: attention
发送 CQ 字符串存在潜在的安全问题：

如果将用户输入（如 {func}`.msg_text` 获得的字符串）作为 CQ 字符串的一部分发送出去，这将会造成“注入攻击”！用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

任何时候启用 `cq_str` 选项，**如果拼接了用户输入，务必校验**。
```

## 转发消息的构造

```{admonition} 相关知识
:class: note
如果你不知道转发消息的表示，主要依托于转发消息段和消息结点，建议先浏览：[转发消息与消息结点](../references/forward-msg.md)
```

### 转发消息段构造

构造“转发消息段”，使用 {func}`.forward_msg` 函数：

```python
from melobot.models import forward_msg

# forward_id 是转发 id，可通过 msg_event().get_datas("forward", "id") 获得
msg = forward_msg(forward_id)
```

此时，`msg` 变量已经是一条转发消息的等价表达了，直接使用 `send` 发送：

```python
@plugin.on_xxx(...)
async def _():
    # 这里也可以使用其他能发送消息段的方法：send_reply, finish...
    await send(msg)
```

### 消息结点构造

构造“合并转发结点”，使用 {func}`.refer_msg_node` 函数：

```python
from melobot.models import refer_msg_node

# 这里的 msg_id 是已存在的消息的 id，可通过 msg_event().id 获得
refer_node = refer_msg_node(msg_id)
```

构造“合并转发自定义结点”，使用 {func}`.custom_msg_node` 函数：

```python
from melobot.models import custom_msg_node

# 第一参数是消息内容，与上述消息段发送方法的第一参数相同
# 后续参数是在转发消息中显示的，发送人昵称 和 发送人的qq号（int 类型）
node1 = custom_msg_node("你好", sendName="机器人", sendId=xxxxxx)

node2 = custom_msg_node(
    image_msg(...),
    sendName="机器人",
    sendId=xxxxxx
)

node3 = custom_msg_node(
    [text_msg(...), image_msg(...)],
    sendName="机器人",
    sendId=xxxxxx
)
```

将消息结点组成列表，就是一条转发消息的等价表达了，使用 {func}`.send_forward` 来发送它：

```python
from melobot.context import send_forward

@plugin.on_xxx(...)
async def _():
    await send_forward([refer_node, node1, node2, node3])
```

## 转发消息的其他发送方法

{func}`.send_forward` 可根据当前触发事件，自动定位要向何处发送消息。同理，要自定义发送目标，将{func}`.send_forward` 换成 {func}`.send_custom_forward` 即可，它的第一参数与 {func}`.send_forward` 完全相同。

```python
from melobot.context import send_custom_forward

@plugin.on_xxx(...)
async def _():
    # 发送一个自定义目标的私聊转发消息，userId 为 qq 号
    await send_custom_forward(..., isPrivate=True, userId=1574260633)
    # 发送一个自定义目标的群聊转发消息，groupId 为群号
    await send_custom_forward(..., isPrivate=False, groupId=535705163)
```

## 总结

本篇主要说明了如何构造和发送各种消息。

下一篇将重点说明：其他行为操作及行为操作的等待与响应。
