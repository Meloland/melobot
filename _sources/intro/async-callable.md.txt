# 异步可调用

在正式开始我们的教程之前，需要简单讲一讲关于“异步可调用”的概念。

首先关于“可调用”或“可调用对象”，大家在过去的 Python 开发中，应该有所接触。可调用对象代指任何能被调用的东西，像是一种接口，都能使用 `()` 来触发调用行为：

```python
class Foo:
    def __call__(self, *args, **kwargs):
        ...
foo = Foo()

bar1 = lambda *_, **__: ...

def bar2(*args, **kwargs):
    ...

from functools import partial
bar3 = partial(bar2, 1, arg1=2)

# 它们都是可调用对象，因此可以：
foo()
bar1()
bar2()
bar3()
```

可调用对象一般使用 {external:class}`~collections.abc.Callable` 注解：

```python
f: Callable = ...
```

同样的思路，melobot 中提出了 {class}`.AsyncCallable` 类型。它用于许多接口的类型注解，有以下特性：

{class}`.AsyncCallable`\[{data}`.P`, {data}`.T`\] {math}`\iff` {external:class}`~collections.abc.Callable`\[{data}`.P`, {external:class}`~collections.abc.Awaitable`\[{data}`.T`\]\]

其中 P 为 {external:class}`~typing.ParamSpec` 泛型，T 为普通的无约束泛型。

典型的异步可调用对象包括：

```python
class Foo:
    async def __await__(self):
        ...

async def _any_coro_f(*args, **kwargs): ...
bar1 = lambda *_, **__: _any_coro_f(*_, **__)

async def bar2(*args, **kwargs):
    ...

from functools import partial
bar3 = partial(bar2, 1, arg1=2)

# 它们都是异步可调用对象，因此可以：
await Foo()
await bar1()
await bar2()
await bar3()
```

在 melobot 中，也提供了装饰器 {func}`.to_async` 转换可调用为异步可调用：

```python
# 在一般函数上装饰，转换为异步可调用
@to_async
def sync_func(...):
    ...

# 直接调用，适用于各种可调用对象：
async def _any_coro_f(*args, **kwargs): ...
f = to_async(lambda: _any_coro_f(1, 2, 3))

aprint = to_async(print)
```

{func}`.to_async` 只是将原对象包裹在一个异步函数中，从而满足异步可调用的接口。

**即：{func}`.to_async` 不做接口兼容外的处理，因此也就不会提供并发/并行的能力。**
