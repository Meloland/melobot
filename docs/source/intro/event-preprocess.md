# OneBot 事件预处理

现在，通过事件绑定方法我们可以绑定事件处理逻辑。

在处理方法中，依靠事件对象、行为操作方法等接口，我们可以让机器人实现各种丰富的功能。

但接下来的**事件预处理**，会让整个过程更加简洁和优雅。

```{admonition} 相关知识
:class: note
建议先阅读：[什么是事件预处理？](../ob_refer/preprocess)
```

## 内置检查

有些时候，我们需要事件满足某些条件，才决定处理它。这就是检查器需要做的事。

内置支持基于两种权限等级的检查：{class}`.LevelRole` 和 {class}`.GroupRole`。

{class}`.LevelRole` 总共分为五级权限（OWNER > SUPER > WHITE > NORMAL > BLACK）。使用例子如下所示：

```python
from melobot.protocols.onebot.v11 import on_message
from melobot.protocols.onebot.v11.utils import MsgChecker, LevelRole

# 这些整型值都代表 qq 号
OWNER = 10001
SUPER = [12345, 12346]
WHTIE = [12347, 12348]
BLACK = []

@on_message(checker=MsgChecker(
    role=LevelRole.OWNER, 
    owner=OWNER, 
    super_users=SUPER, 
    white_users=WHITE, 
    black_users=BLACK
))
async def _():
    # 只有在消息事件发送者 id 达到 OWNER 级时才能进入处理方法
    ...

WHITEG = [1000000]

@on_message(checker=GroupMsgChecker(
    role=LevelRole.OWNER, 
    owner=OWNER, 
    super_users=SUPER, 
    white_users=WHITE, 
    black_users=BLACK,
    white_gruops=WHITEG
))
async def _():
    # 只有在消息事件发送者 id 达到 OWNER 级，且同时为群聊消息，且群号在 WHITEG 中时，才能进入处理方法
    # white_groups 参数为空时，不启用群白名单校验，所有群消息只要通过其他校验条件即可触发
    ...

@on_message(checker=PrivateMsgChecker(
    role=LevelRole.OWNER, 
    owner=OWNER, 
    super_users=SUPER, 
    white_users=WHITE, 
    black_users=BLACK,
    white_gruops=WHITEG
))
async def _():
    # 只有在消息事件发送者 id 达到 OWNER 级，且同时为私聊消息时，才能进入处理方法
    ...
```

频繁地传入各个等级包含的 id 很不方便，因此可以使用工厂类 {class}`.MsgCheckerFactory`：

```python
from melobot.protocols.onebot.v11.utils import MsgCheckerFactory

checker_ft = MsgCheckerFactory(
    role=LevelRole.OWNER, 
    owner=OWNER, 
    super_users=SUPER, 
    white_users=WHITE, 
    black_users=BLACK,
    white_gruops=WHITEG
)

# 获得一个 OWNER 级别的通用校验
uni_checker: MsgChecker = checker_ft.get_base(role=LevelRole.OWNER)
# 获得一个 NORMAL 级别的群聊校验
grp_checker: GroupMsgChecker = checker_ft.get_group(role=LevelRole.NORMAL)
# 获得一个 WHITE 级别的私聊校验
priv_checker: PrivateMsgChecker = checker_ft.get_private(role=LevelRole.WHITE)
```

{class}`.GroupRole` 分为三种：（OWNER、ADMIN、MEMBER）。使用例子如下：

```python
from melobot.protocols.onebot.v11 import on_message
from melobot.protocols.onebot.v11.utils import MsgChecker, GroupRole

# 与刚才的 LevelRole 类似，但此时其他参数传递无效
@on_message(checker=MsgChecker(role=GroupRole.OWNER))
async def _():
    # 只有在消息事件是群消息，而且发送者是群主，才能进入处理方法
    ...

@on_message(checker=MsgChecker(role=GroupRole.ADMIN))
async def _():
    # 只有在消息事件是群消息，而且发送者是群主或群管理员，才能进入处理方法
    ...

@on_message(checker=MsgChecker(role=GroupRole.MEMBER))
async def _():
    # 只有在消息事件是群消息，而且发送者只是普通群员，才能进入处理方法
    ...
```

显然，{class}`.GroupRole` 也可以从检查器工厂的方法中获得。这与前面是一致的。不过第一参数改为 {class}`.GroupRole` 对象而已。

此外，检查器之间也支持逻辑或与非，及逻辑异或运算，利用这一特性可以构建精巧的检查逻辑：

```python
from melobot.protocols.onebot.v11.utils import MsgCheckerFactory, LevelRole, GroupRole

# 构建一个常用的检查逻辑：
# 私聊只有 SUPER 级别可以使用；在群聊白名单的群中，成员白名单中的成员或任何群管可以使用
checker_ft = MsgCheckerFactory(
    role=LevelRole.OWNER, 
    owner=OWNER, 
    super_users=SUPER, 
    white_users=WHITE, 
    black_users=BLACK,
    white_gruops=WHITEG
)
priv_c = checker_ft.get_private(LevelRole.SUPER)
grp_c1 = checker_ft.get_group(LevelRole.WHITE)
grp_c2 = checker_ft.get_group(GroupRole.ADMIN)

final_checker = priv_c | grp_c1 | grp_c2
```

其他高级特性：自定义检查成功回调，自定义检查失败回调等，请参考 [内置检查器与检查器工厂](onebot_v11_check) 中各种对象的参数。

除了这些接口，melobot 内部其实也有一种隐式检查，这就是**基于依赖注入的区分调用**：

```python
from melobot.protocols.onebot.v11 import on_message, on_event
from melobot.protocols.onebot.v11.adapter.event import GroupMessageEvent, PrivateMessageEvent

@on_message(...)
async def msg_handle1(ev: GroupMessageEvent):
    # 只有触发事件属于 群聊消息事件 时，才会进入这个处理方法
    ...

@on_message(...)
async def msg_handle2(ev: PrivateMessageEvent):
    # 只有触发事件属于 私聊消息事件 时，才会进入这个处理方法
    ...

from melobot.protocols.onebot.v11 import on_event
from melobot.protocols.onebot.v11.adapter.event import MessageEvent
from melobot.log import Logger as MeloLogger

@on_event(...)
async def xxx_handle(event: GroupMessageEvent, logger: MeloLogger):
    # 必须所有参数对应的值，都属于注解指定的类型时，才会进入这个处理方法
    ...
```

## 自定义检查

可以使用以下方法自定义检查器：

```python
from melobot.protocols.onebot.v11 import on_message

OWNER_QID = 10001

# 通过可调用对象初始化一个检查器，这里给了一个匿名函数
# 即使使用匿名函数，也会有良好的类型注解哦！
@on_message(checker=lambda e: e.sender.user_id == 10001)
async def owner_only_echo():
    ...
```

或者使用更高级的方法（实现子类），这适用于更复杂的需求，例如检查/验证时需要保存某些状态信息：

```python
from melobot.protocols.onebot.v11 import on_message
from melobot.protocols.onebot.v11.adapter.event import MessageEvent
from melobot.protocols.onebot.v11.utils import Checker

class FreqGuard(Checker):
    def __init__(self) -> None:
        super().__init__()
        self.freq = 0

    async def check(self, event: MessageEvent) -> bool:
        if event.sender.user_id != 10001 or self.freq >= 10:
            return False
        self.freq += 1
        return True

@on_message(checker=FreqGuard())
async def _():
    ...
```

所有自定义的检查器，同样也自动支持检查器的逻辑运算。

## 匹配

匹配只对消息事件的文本内容生效。只有在匹配通过后，才能运行后续操作。其他事件绑定方法无法指定匹配。

常用的几个事件绑定接口，就是内置了匹配的流程：{func}`~.v11.handle.on_command`、{func}`~.v11.handle.on_start_match`、{func}`~.v11.handle.on_contain_match`、{func}`~.v11.handle.on_full_match`、{func}`~.v11.handle.on_end_match`、{func}`~.v11.handle.on_regex_match`。

对应的匹配器可查看文档：[内置匹配器](onebot_v11_match)。你也可以自定义匹配器：

```python
from melobot.protocols.onebot.v11 import on_message
from melobot.protocols.onebot.v11.utils import Matcher

class StartEndMatch(Matcher):
    def __init__(self, start: str, end: str) -> None:
        self.start = start
        self.end = end

    async def match(text: str) -> bool:
        return text.startswith(self.start) or text.endswith(self.end)

@on_message(checker=StartEndMatch())
async def _():
    ...
```

其他高级特性：自定义匹配成功回调，自定义匹配失败回调等，请参考 [内置匹配器](onebot_v11_match) 中各种对象的参数。

## 解析

解析只对消息事件的文本内容生效。解析完成后将会生成一个 {class}`.ParseArgs` 对象。其他事件绑定方法无法指定解析。

想象一个典型的使用案例，你需要：

- 机器人响应指令：`.天气 杭州 7`
- 匹配到“天气”指令的处理方法
- 传递参数列表 `["杭州", "7"]` 给处理方法，实现具体的逻辑。

显然，自己编写指令解析是比较费劲的。可以使用 {class}`.CmdParser`，并利用 {func}`~.v11.handle.GetParseArgs` 获取解析参数：

```python
from melobot.protocols.onebot.v11 import on_message, ParseArgs
from melobot.protocols.onebot.v11.utils import CmdParser
from melobot.protocols.onebot.v11.handle import GetParseArgs

@on_message(parser=CmdParser(cmd_start='.', cmd_sep=' ', targets='天气'))
# 使用 GetParseArgs 进行依赖注入
async def _(args: ParseArgs = GetParseArgs()):
    assert args.name == "天气"
    assert args.vals == ["杭州", "7"]
```

需要多个指令起始符，多个指令间隔符，多个匹配的目标？这些也同样支持：

```python
from melobot.protocols.onebot.v11 import on_message, ParseArgs
from melobot.protocols.onebot.v11.utils import CmdParser
from melobot.protocols.onebot.v11.handle import GetParseArgs

@on_message(parser=CmdParser(
    cmd_start=[".", "~"], 
    cmd_sep=[" ", "#"], 
    targets=["天气", "weather"]
))
async def _(args: ParseArgs = GetParseArgs()):
    ...
```

此时，以下字符串都可以产生与刚才类似的解析结果：

- `~天气#杭州  7` -> `name='天气', vals=['杭州', '7']`
- `~天气##杭州    7` -> `name='天气', vals=['杭州', '7']`
- `.weather#杭州#7` -> `name='weather', vals=['杭州', '7']`
- `.天气   杭州      7` -> `name='天气', vals=['杭州', '7']`

实际上，利用 targets 参数可以给定多个值的特点，你可以一次解析一组指令，然后再处理：

```python
@on_message(parser=CmdParser(
    cmd_start="/", 
    cmd_sep=[" ", "#"], 
    targets=["功能1", "功能2", "功能3"]
))
async def _(args: ParseArgs = GetParseArgs()):
    match args.name:
        case "功能1":
            func1(args.vals)
        case "功能2":
            func2(args.vals)
        case "功能3":
            func3(args.vals)
        case _:
            return
```

同理也可以实现子命令支持，这里不再演示。

使用 {func}`.on_message` 手动给定 {class}`.CmdParser` 还是略显麻烦。一般的情景，更建议使用 {func}`.on_command`：

```python
from melobot.protocols.onebot.v11 import on_command, ParseArgs
from melobot.protocols.onebot.v11.handle import GetParseArgs

@on_command(cmd_start=[".", "~"], cmd_sep=[" ", "#"], targets=["天气", "weather"])
async def _(args: ParseArgs = GetParseArgs()):
    ...
```

为了进一步简化重复操作，同样有命令解析器工厂 {class}`.CmdParserFactory`。

## 解析格式化

解析得到的结果，还可以进行参数格式化（类型转换、校验）。

下面是一个例子。这个 `add` 指令，接受两个浮点数，且第二参数可以有默认值：

```python
from melobot.protocols.onebot.v11 import on_command, ParseArgs
from melobot.protocols.onebot.v11.handle import GetParseArgs
from melobot.protocols.onebot.v11.utils import CmdArgFormatter as Fmtter

@on_command(
    cmd_start=".",
    cmd_sep=" ",
    targets="add",
    fmtters=[
        Fmtter(
            # 转换函数，接受字符串再返回一个值，不需要则空
            convert=float,
            # 校验函数，在格式化之后执行，不需要则空
            validate=lambda i: 0 <= i <= 100,
            # 此参数的描述（可供回调使用）
            src_desc="操作数1",
            # 此参数期待值的说明（可供回调使用）
            src_expect="[0, 100] 的浮点数",
        ),
        Fmtter(
            convert=float,
            validate=lambda i: 0 <= i <= 100,
            src_desc="操作数2",
            src_expect="[0, 100] 的浮点数",
            # 默认值
            default=0,
        ),
    ],
)
async def _(args: ParseArgs = GetParseArgs()):
    pass
```

解析情况如下：

- `.add 12 24` -> `vals=[12.0, 24.0]`
- `.add 12` -> `vals=[12.0, 0]`
- `.add 12 24 asfdja` -> `vals=[12.0, 24.0]`（多余参数被忽略）
- `.add` -> 日志输出内置的“参数缺少”提示，不进入事件处理
- `.add ajfa` -> 日志输出内置的“参数格式化失败”提示，不进入事件处理
- `.add 120` -> 日志输出内置的“参数验证失败”提示，不进入事件处理

如果某一个参数不需要任何格式化呢？

```python
# 对第二参数不运行格式化
fmtters = [Fmtter(...), None, Fmtter(...)]
```

此外，你还可以自定义“参数转换失败”、“参数验证失败”、“参数缺少”时的回调。比如直接静默，而不是在日志提示：

```python
from melobot.utils import to_async

nothing = to_async(lambda *_: None)

fmtters = [
    Fmtter(
        ..., 
        convert_fail=nothing, 
        validate_fail=nothing, 
        arg_lack=nothing
    ),
    ...
]
```

或者利用回调函数 {class}`.FormatInfo` 参数提供的信息，给用户回复提示：

```python
from melobot import send_text
from melobot.protocols.onebot.v11.utils import FormatInfo

async def convert_fail(self, info: FormatInfo) -> None:
    e_class = f"{info.exc.__class__.__module__}.{info.exc.__class__.__qualname__}"
    src = repr(info.src) if isinstance(info.src, str) else info.src

    tip = f"第 {info.idx + 1} 个参数"
    tip += (
        f"（{info.src_desc}）无法处理，给定的值为：{src}。"
        if info.src_desc
        else f"给定的值 {src} 无法处理。"
    )

    tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
    tip += f"\n详细错误描述：[{e_class}] {info.exc}"
    tip = f"命令 {info.name} 参数格式化失败：\n{tip}"
    # 回复提示
    await send_text(tip)

async def validate_fail(self, info: FormatInfo) -> None:
    src = repr(info.src) if isinstance(info.src, str) else info.src

    tip = f"第 {info.idx + 1} 个参数"
    tip += (
        f"（{info.src_desc}）不符合要求，给定的值为：{src}。"
        if info.src_desc
        else f"给定的值 {src} 不符合要求。"
    )

    tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
    tip = f"命令 {info.name} 参数格式化失败：\n{tip}"
    # 回复提示
    await send_text(tip)

async def arg_lack(self, info: FormatInfo) -> None:
    tip = f"第 {info.idx + 1} 个参数"
    tip += f"（{info.src_desc}）缺失。" if info.src_desc else "缺失。"
    tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
    tip = f"命令 {info.name} 参数格式化失败：\n{tip}"
    # 回复提示
    await send_text(tip)


fmtters = [
    Fmtter(
        ..., 
        convert_fail=convert_fail, 
        validate_fail=validate_fail, 
        arg_lack=arg_lack
    ),
    ...
]
```

## 自定义解析器

使用内置的抽象类来自定义解析器：

```python
from melobot.protocols.onebot.v11 import on_message
from melobot.protocols.onebot.v11.utils import Parser

class MyParser(Parser):
    async def parse(text: str) -> ParseArgs | None:
        # 返回 None 代表没有有效的解析结果
        ...

@on_message(parser=MyParser())
async def _():
    ...
```

## 总结

本篇主要说明了预处理机制中的检查、匹配和解析。

消息事件绑定方法，检查、匹配和解析可以同时指定。顺序是：先检查，再匹配，最后解析。其他事件绑定方法，只能指定检查。

再次提醒，所有内置预处理机制，**均不是异步安全的**。若需要异步安全，请实现自定义类。

同时，读者也无需拘泥于文档所给的示例。充分利用 OOP 的编程思路，可以创造出更多有趣的玩法。
