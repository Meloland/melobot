# 事件与事件处理

```{admonition} 相关知识
:class: note
如果你不知道什么是“事件”，建议先浏览：[事件的相关知识](../ob_refer/event-action)
```

## 绑定方法与处理方法

除了刚才使用的 {meth}`~.BotPlugin.on_start_match` 方法，还有很多类似的方法，可以用于绑定事件处理的逻辑。

本文档将这些方法称为“绑定方法”，同时将绑定方法绑定的函数称为：“处理方法”或“处理函数”。

- 绑定一个任意事件的处理方法：{meth}`~.BotPlugin.on_event`
- 绑定一个消息事件的处理方法：{meth}`~.BotPlugin.on_message`、{meth}`~.BotPlugin.on_at_qq`、{meth}`~.BotPlugin.on_command`、{meth}`~.BotPlugin.on_start_match`、{meth}`~.BotPlugin.on_contain_match`、{meth}`~.BotPlugin.on_full_match`、{meth}`~.BotPlugin.on_end_match`、{meth}`~.BotPlugin.on_regex_match`
- 绑定一个请求事件的处理方法：{meth}`~.BotPlugin.on_request`
- 绑定一个通知事件的处理方法：{meth}`~.BotPlugin.on_notice`
- 绑定一个元事件的处理方法：{meth}`~.BotPlugin.on_meta_event`

这些绑定方法的参数很多，你可以先简单浏览。关于这些方法的使用，后续会详细讲解。现在让我们先学习一些基础知识。

绑定方法的使用都一样，直接用作装饰器即可：

```python
from melobot import BotPlugin
plugin = BotPlugin("test", "1.0.0")

@plugin.on_start_match(...)
async def func() -> None:
    # func 就是事件处理方法，必须为异步函数，且无返回值
    # func 的内容就是事件处理的逻辑
    ...
```

## 获取事件对象

现在我们已经学会绑定事件处理方法了。如果事件处理方法，能**获得触发事件的一些信息，基于这些信息做针对性处理**就更好了。

通过 {func}`.any_event`、{func}`.msg_event`、{func}`.req_event`、{func}`.notice_event`、{func}`.meta_event` 函数，即可在事件处理方法中获得触发的事件。获得的事件是一个事件对象。

当然这五个方法都只做一件事：获得当前的事件。它们唯一的不同在于，返回值的类型注解不一样。**建议在指定类型的事件处理方法中，用对应的事件获取方法**。这样可以获得精准的类型提示：

```python
@plugin.on_event(...)
async def func1():
    # on_event 绑定的处理方法，可能被各种类型的事件触发
    # 使用 any_event 可以获得所有事件类型的补全提示
    e = any_event()
    ...

@plugin.on_start_match(...)
async def func2():
    # on_start_match 绑定的处理方法，只可能被消息事件触发
    # 使用 msg_event 可以获得消息事件类型的补全提示
    e = msg_event()
    ...
```

不同类型的事件对象有哪些属性和方法可用，请参考：[事件类型](event-type)

所有类型的事件对象，都可通过 {attr}`~.BotEvent.raw` 属性获得原始的 OneBot 标准事件字典。这可能在极少数情况下有用。一般使用事件对象的属性和方法即可。

## 基于事件信息的处理逻辑

通过事件对象提供的信息，可以实现更有趣的处理逻辑：

```{code} python
:number-lines:

"""
通过消息事件对象的 time, sender.id 属性，产生不同的处理逻辑
"""
from datetime import datetime
from melobot import BotPlugin, ForwardWsConn, MeloBot, msg_event, send

plugin = BotPlugin(__name__, "1.0.0")
# 机器人主人的 qq 号
OWNER_QID = 1574260633

@plugin.on_start_match(".hello")
async def say_hi_to_owner() -> None:
    e = msg_event()
    # 如果消息不来源于机器人主人，则不做任何处理
    if e.sender.id != OWNER_QID:
        return
    # 否则根据时间，回复不同的内容
    hour = datetime.fromtimestamp(e.time).hour
    if 0 <= hour < 6:
        await send("主人凌晨好~")
    elif 6 <= hour < 12:
        await send("主人早上好~")
    elif 12 <= hour < 18:
        await send("主人下午好~")
    else:
        await send("主人晚上好~")

if __name__ == "__main__":
    bot = MeloBot(__name__)
    bot.init(ForwardWsConn("127.0.0.1", 8080))
    bot.load_plugin(plugin)
    bot.run()
```

## 消息事件相关

```{admonition} 提示
:class: tip
以下代码示例中的 `on_xxx` 代指各种事件绑定方法，实际并不存在名为 `on_xxx` 的方法。
```

对于消息事件，有一些额外的方法可以使用，这里先说最常用的 {func}`.msg_text`。

一个消息事件就象征一条消息，它最重要的信息就是**消息内容**。消息中的文本内容使用 {func}`.msg_text` 获取：

```python
from melobot.context import msg_text

@plugin.on_xxx(...)
async def _():
    # 获取消息中的文本内容
    text = msg_text()  # 等价于：msg_event().text
```

如果要获取多媒体内容，例如图片、表情等，可以使用 {meth}`~.MessageEvent.get_segments` 方法获得多媒体内容对应的**消息段对象列表**。

```{admonition} 相关知识
:class: note
如果你不知道，消息段对象是消息内容的表示方式之一，建议先浏览：[消息内容的数据结构](../ob_refer/msg)
```

需要哪种类型的消息段，就传递哪种消息段的 type 作为参数：

```python
from melobot.context import msg_event

@plugin.on_xxx(...)
async def _():
    e = msg_event()
    # 获取当前这条消息所有的图片（image 是图片消息段的类型名）
    images = e.get_segments("image")
    # 获取当前这条消息所有的 qq 表情（face 是 qq 表情消息段的类型名）
    faces = e.get_segments("face")
```

随后，读取列表中消息段对象的 data 字段可获得相关数据：

```python
# 遍历所有图片的 url 和文件名
for img in msg_event().get_segments("image"):
    print(img["data"]["url"])
    print(img["data"]["file"])
```

```{admonition} 相关知识
:class: note
所有媒体内容对应的消息段表示：[OneBot 消息段](https://github.com/botuniverse/onebot-11/blob/master/message/segment.md)

此链接也包含了每种消息段的 type 标识，及 data 字段拥有的参数。
```

如果只需要 data 字段的某一参数，使用 {meth}`~.MessageEvent.get_datas` 即可：

```python
@plugin.on_xxx(...)
async def _():
    # 获取当前这条消息，所有图片的 url
    img_urls = msg_event().get_datas("image", "url")
```

## 上下文的自动传播

实际上，以上所有获取事件相关信息的方法，可以在任意深度的，同步或异步函数调用中使用。

只要这些函数的调用都是事件处理方法发起的，它们就能获得对应的上下文信息：

```python
@plugin.on_xxx(...)
async def f1():
    e = msg_event()      # ok
    # 上下文自动传播给同步函数 a
    a()

def a():
    text = msg_text()    # ok
    # 上下文自动传播给异步函数 b
    await b()

async def b():
    e = msg_event()      # ok
```

当然，你也可以显式传参：

```python
@plugin.on_xxx(...)
async def func1():
    e = msg_event()
    func_a(e)

def func_a(event):
    ...
```

使用的相关方法太多，不想一个个导入？没问题，我们可以直接导入模块！

```python
from melobot import context as ctx

@plugin.on_xxx(...)
async def _():
    e1 = ctx.any_event()
    e2 = ctx.msg_event()
    text = ctx.msg_text()
```

习惯事件处理方法接受参数？喜欢像 nonebot2 那样的依赖注入？没问题，我们也支持！

```python
from melobot.context import msg_event, any_event, msg_text

@plugin.on_xxx(...)
async def _(e1 = any_event(), e2 = msg_event(), text = msg_text()):
    ...
```

## 总结

本篇主要说明了如何绑定事件处理方法，以及如何通过事件对象的属性和方法，来实现更丰富的处理逻辑。

下一篇将重点说明：如何构造和发送各种消息。
