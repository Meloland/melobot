# 上下文管理

异步 bot 会同时处理许多事件。把“当前事件”“当前 bot”之类的数据放进普通全局变量，会在任务切换后彼此覆盖。melobot 的 {class}`.Context` 在 `contextvars.ContextVar` 之上提供了统一接口，适合为插件或扩展声明**当前调用链私有**的数据。

本篇只说明如何继承和使用 `Context`；框架内置的 bot、事件处理流、会话等上下文会由对应功能自动维护，业务代码通常无需直接操作。

## 声明自定义上下文

不要直接实例化 `Context`，而是为要保存的值定义一个子类。子类是单例，因此多次调用构造器会得到同一个上下文管理对象：

```python
from melobot import Context

class RequestIdCtx(Context[str]):
    def __init__(self) -> None:
        super().__init__(
            "my_plugin.request_id",  # 全局唯一的上下文名称
            LookupError,             # 未设置值时抛出的异常类型
            "当前不在请求处理过程中",    # 上述抛出异常的提示信息
        )

REQUEST_ID = RequestIdCtx()
assert REQUEST_ID is RequestIdCtx()
```

构造参数分别是上下文名称、读取失败时的异常类和可选的错误提示。名称应在项目中保持唯一且具有命名空间，例如 `"my_plugin.request_id"`，避免不同扩展产生难以诊断的混淆。

## 在作用域内设置值

最推荐的方式是 {meth}`~.Context.unfold`。它返回普通上下文管理器：即使在异步函数中，也使用 `with`，而不是 `async with`。

```python
async def process_request(request_id: str) -> None:
    with REQUEST_ID.unfold(request_id):
        await call_service()
        assert REQUEST_ID.get() == request_id

    # 退出作用域后自动恢复此前的值
    assert REQUEST_ID.try_get() is None
```

嵌套作用域会自动恢复外层值：

```python
with REQUEST_ID.unfold("outer"):
    with REQUEST_ID.unfold("inner"):
        assert REQUEST_ID.get() == "inner"
    assert REQUEST_ID.get() == "outer"
```

如果必须手动控制生命周期，可使用 {meth}`~.Context.add` 和 {meth}`~.Context.remove`；`add` 返回的 token 必须在 `finally` 中交给 `remove`。一般没有必要这样做，`unfold` 更不容易遗漏清理。

## 读取与异步边界

{meth}`~.Context.get` 在当前上下文没有值时抛出子类指定的异常，适合“这里必须处于某作用域”的场景。{meth}`~.Context.try_get` 在没有值时返回 `None` 或你提供的默认值，适合可选的诊断信息：

```python
def make_log_fields() -> dict[str, str]:
    request_id = REQUEST_ID.try_get()
    return {} if request_id is None else {"request_id": request_id}
```

`Context` 基于 Python 的 `contextvars`：异步任务创建时会继承当时的上下文副本，因此同一请求创建出的子任务通常能读取同一个值；互不相关的并发任务不会因为一次 `unfold` 而互相覆盖。上下文复制的是“绑定关系”，不是深拷贝。若存入列表、字典等可变对象，多个继承了该对象引用的任务仍可能修改同一份数据；需要隔离时请存入不可变值或自行复制。

```{admonition} 适用边界
:class: tip
`Context` 适合传递请求 id、追踪标记、临时选项等短生命周期数据，不适合保存长期业务状态。数据库连接池、缓存和跨事件会话数据应使用显式对象、插件共享对象或会话存储。
```

## 总结

继承 `Context[T]`，在构造器中声明名称和读取失败策略，再用 `with ctx.unfold(value)` 建立作用域，即可安全地在深层异步调用中取得“当前值”。优先使用 `get` 表达必需上下文，使用 `try_get` 表达可选上下文，并避免把可变的长期状态藏进上下文变量。

下一篇将介绍：[元信息](./meta)。
