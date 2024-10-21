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
ONWER = 10001
SUPER = [12345, 12346]
WHTIE = [12347, 12348]
BLACK = []

@on_message(checker=MsgChecker(
    role=LevelRole.OWNER, 
    owner=ONWER, 
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
    owner=ONWER, 
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
    owner=ONWER, 
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
    owner=ONWER, 
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

其他高级特性请参考文档 [内置检查器与检查器工厂](onebot_v11_check)。

除了这些接口，melobot 内部其实也有一种隐式检查，这就是**基于依赖注入的自动重载**：

```python
from melobot.protocols.onebot.v11 import on_message, on_event
from melobot.protocols.onebot.v11.adapter.event import GroupMessageEvent, PrivateMessageEvent

@on_message(...)
async def msg_handle(ev: GroupMessageEvent):
    # 只有触发事件属于 群聊消息事件 时，才会进入这个处理方法
    ...

@on_message(...)
async def msg_handle(ev: PrivateMessageEvent):
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

匹配只对消息事件的文本内容生效。只有在匹配通过后，才能进入事件处理。其他事件绑定方法无法指定匹配器。

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

## 解析

```{admonition} 施工中
:class: note
内容等待补充中...
```
