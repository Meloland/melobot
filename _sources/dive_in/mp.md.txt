# 多进程支持

异步适合等待网络和文件 IO，但 CPU 密集型计算仍会长时间占用事件循环所在的线程。图像处理、压缩、复杂解析或大量数值计算等任务，可以交给独立进程执行。`melobot.mp` 在 Python 多进程接口之上提供了适合 melobot 程序的 spawn 模式进程、进程池和 pickle 包装器。

## 原理简介

spawn 模式不会复制父进程的完整内存，而是启动一个新的 Python 解释器。父进程需要把目标函数和参数序列化，子进程再导入入口模块、反序列化对象并开始执行。因此它有两个重要特点：

1. 父子进程不共享普通全局变量，各自拥有独立的解释器和模块状态；
2. 发送到子进程的目标函数和参数，以及进程池返回给父进程的结果，必须可以被 pickle。

普通 spawn 会重新准备主模块。对已经加载协议、插件和生命周期逻辑的 bot 程序而言，不受控制的重复导入可能产生级联初始化。melobot 的多进程组件要求显式提供一个**子进程入口文件**，并让子进程在受控的工作目录、`sys.path` 和 `sys.argv` 下加载它。melobot 管理的子进程还会忽略常见终止信号，由父进程统一管理退出。

只要不使用本篇的进程创建组件，标准库 `multiprocessing` 仍按原有方式工作。

```{admonition} 听不懂也没关系
:class: tip
日常使用只需记住三点：准备一个轻量的 worker 入口文件；在主进程创建 `SpawnProcessPoolExecutor`；对象无法按原模块来源在子进程还原时用 `PBox` 包装。其余细节可以等遇到跨进程问题时再回来查阅。
```

## 判断当前进程

{func}`.in_main_process()` 判断当前进程是否是 Python 主进程；{func}`.in_melobot_sub_process()` 判断当前进程是否由 melobot 的 `SpawnProcess` 系列组件管理。

```python
from melobot.mp import in_main_process, in_melobot_sub_process

if in_main_process():
    print("运行在主进程")
elif in_melobot_sub_process():
    print("运行在 melobot 管理的子进程")
else:
    print("运行在其他方式创建的子进程")
```

| 所处位置 | `in_main_process()` | `in_melobot_sub_process()` |
| --- | --- | --- |
| 主进程 | `True` | `False` |
| melobot 管理的子进程 | `False` | `True` |
| 其他多进程库创建的子进程 | `False` | `False` |

`SpawnProcess` 不允许在 melobot 管理的子进程中继续创建下一层子进程。若这里抛出异常，通常意味着把创建进程的代码放进了 worker 入口顶层，或入口路径指向了不合适的主程序文件。

## 准备 worker 入口

以下示例都使用一个单独的 `worker.py`：

```python
# worker.py
from collections.abc import Callable

def square(number: int) -> int:
    return number * number

def print_square(number: int) -> None:
    print(square(number))

class Multiplier:
    def __init__(self, factor: int) -> None:
        self.factor = factor

    def __call__(self, number: int) -> int:
        return self.factor * number
```

worker 需要的函数和类必须定义在模块顶层。不要把它们放在 `if __name__ == "__main__":` 中，因为子进程加载入口时的模块名并不是 `__main__`。

主程序通过文件路径指定入口：

```python
from pathlib import Path

WORKER_ENTRY = Path(__file__).with_name("worker.py").resolve()
```

`entry` 必须指向存在且可加载的模块文件，而不是目录。可选的 `argv` 会完整地作为子进程 `sys.argv`；不提供时默认使用仅包含入口路径的列表。

## SpawnProcess

{class}`.SpawnProcess` 对应一个 spawn 子进程，接口与 `multiprocessing.Process` 接近，额外要求首个参数 `entry`：

```python
from melobot.mp import PBox, SpawnProcess

if __name__ == "__main__":
    process = SpawnProcess(
        entry=WORKER_ENTRY,
        target=PBox(name="print_square", entry=WORKER_ENTRY),
        args=(12,),
        name="square-worker",
    )
    process.start()
    process.join()

    if process.exitcode != 0:
        raise RuntimeError(f"子进程异常退出：{process.exitcode}")
```

`start()` 启动进程，`join()` 等待结束，`exitcode` 用于检查退出状态。单进程接口适合一次性的、需要独立生命周期或自定义守护属性的任务。若需要提交许多短任务，反复创建进程开销较大，应使用进程池。

## SpawnProcessPool

{class}`.SpawnProcessPool` 对应传统的 `multiprocessing.pool.Pool`，适合已有代码正在使用 `map`、`apply_async` 等 API 的情况：

```python
from melobot.mp import PBox, SpawnProcessPool

if __name__ == "__main__":
    square = PBox(name="square", entry=WORKER_ENTRY)

    with SpawnProcessPool(
        entry=WORKER_ENTRY,
        processes=4,
        maxtasksperchild=500,
    ) as pool:
        results = pool.map(square, range(10))
        result = pool.apply_async(square, (20,)).get(timeout=5)

    assert results == [n * n for n in range(10)]
    assert result == 400
```

`processes` 控制 worker 数量；`initializer` 和 `initargs` 可在每个 worker 启动时初始化只属于该进程的资源；`maxtasksperchild` 可在执行指定数量的任务后替换 worker，适合缓解第三方计算库长期运行造成的资源累积。

新代码通常不必选择这个接口。它的异步结果类型和管理习惯较旧，和 `asyncio` 配合也不如下一节直接。

## SpawnProcessPoolExecutor

{class}`.SpawnProcessPoolExecutor` 基于 `concurrent.futures.ProcessPoolExecutor`，是最推荐使用的多进程组件。同步代码可以使用 `submit` 和 `map`，异步代码可以把它传给事件循环的 `run_in_executor`：

```python
import asyncio

from melobot.mp import PBox, SpawnProcessPoolExecutor

async def calculate() -> list[int]:
    square = PBox(name="square", entry=WORKER_ENTRY)

    with SpawnProcessPoolExecutor(
        entry=WORKER_ENTRY,
        max_workers=4,
    ) as executor:
        loop = asyncio.get_running_loop()
        return await asyncio.gather(
            *(loop.run_in_executor(executor, square, n) for n in range(10))
        )

if __name__ == "__main__":
    print(asyncio.run(calculate()))
```

对于持续运行的 bot，建议在 bot 启动 hook 或插件就绪 hook 中创建执行器，在停止 hook 中调用 `shutdown()`，而不是每处理一个事件就创建新池。进程池本身也不应隐藏在每次调用都会重新执行的函数内部。

同步环境可直接提交任务：

```python
if __name__ == "__main__":
    square = PBox(name="square", entry=WORKER_ENTRY)
    with SpawnProcessPoolExecutor(entry=WORKER_ENTRY, max_workers=2) as executor:
        future = executor.submit(square, 25)
        assert future.result(timeout=5) == 625
```

`initializer` 和 `initargs` 可用于初始化每个 worker，例如建立进程私有的模型或解析器。不要在 initializer 中创建依赖父进程事件循环的对象，也不要假设 worker 之间共享初始化结果。

```{admonition} 进程不是异步函数加速器
:class: note
进程池主要解决 CPU 密集型工作。网络请求、数据库访问等 IO 密集型任务优先使用原生异步接口；将它们放进进程池通常只会增加序列化和进程通信开销。
```

## PBox：改变对象的 pickle 来源

Python pickle 通常不保存函数和类的完整代码，而是保存“模块名 + 限定名称”，反序列化时重新导入模块并查找对象。这对 melobot 的自定义入口会产生一个问题：父进程看到的模块名，可能与子进程加载 worker 入口后的模块名不同。

{class}`.PBox` 在自身被 pickle 时，先指定子进程应该加载哪个模块，再把包装对象还原出来。它不是函数代理：在父进程里不能直接调用 `PBox`，只有把它作为进程目标、任务函数或参数提交后，它才会在子进程反序列化成真正对象。

### 两种包装模式

`value` 和 `name` 必须二选一：

| 模式 | 示例 | 子进程得到什么 |
| --- | --- | --- |
| 按名称获取 | `PBox(name="square", ...)` | 加载模块后执行 `getattr(module, "square")` |
| 携带对象值 | `PBox(Multiplier(3), ...)` | pickle 对象状态，并从指定模块恢复其函数或类来源 |

按名称获取是包装顶层函数、类或模块常量时最简单、最稳定的方式。它取得的是子进程新加载模块中的值，不会携带父进程对该全局变量所做的运行时修改：

```python
if __name__ == "__main__":
    # worker.py 中存在：DEFAULT_SIZE = 128
    default_size = PBox(name="DEFAULT_SIZE", entry=WORKER_ENTRY)

    # 把 default_size 作为参数提交后，子进程得到 worker.py 自己的 128
    process = SpawnProcess(
        entry=WORKER_ENTRY,
        target=print,
        args=(default_size,),
    )
    process.start()
    process.join()
```

携带对象值适合需要保存实例状态的可调用对象。以下 `Multiplier(3)` 的 `factor` 会随 pickle 数据发送到 worker，类则从入口模块恢复：

```python
from worker import Multiplier

if __name__ == "__main__":
    multiply_by_three = PBox(Multiplier(3), entry=WORKER_ENTRY)

    with SpawnProcessPoolExecutor(entry=WORKER_ENTRY, max_workers=2) as executor:
        results = list(executor.map(multiply_by_three, [1, 2, 3, 4]))

    assert results == [3, 6, 9, 12]
```

普通整数、字符串、列表和字典本来就能 pickle，应直接作为参数传递，不需要套 `PBox`。`PBox(value=...)` 主要用于需要修正函数或用户自定义类来源的对象。

### module 与 entry

`module` 和 `entry` 决定子进程去哪里找对象：

| 参数组合 | 行为 | 适用场景 |
| --- | --- | --- |
| 仅 `entry` | 入口按特殊模块名 `__mp_main__` 加载 | 单文件 worker，最常用 |
| 仅 `module` | 按正常 Python 规则导入模块 | 已安装或已在子进程 `sys.path` 中的包 |
| `module` + `entry` | 从指定文件位置按给定模块名加载 | 未安装的包、需要明确定位的模块 |

例如，一个已安装包中的顶层函数可以只指定模块名：

```python
from my_project.workers import normalize

normalize_for_child = PBox(
    normalize,
    module="my_project.workers",
)
```

若同时给出文件路径，模块名必须与路径尾部一致。例如模块 `my_project.workers` 对应 `/srv/app/my_project/workers.py`，不能随意指定为不相关的别名：

```python
normalize_for_child = PBox(
    name="normalize",
    module="my_project.workers",
    entry="/srv/app/my_project/workers.py",
)
```

当 worker 入口就是本篇示例的单个 `worker.py` 时，省略 `module` 并提供 `entry=WORKER_ENTRY` 最清晰。

### 包装作为参数的对象

`PBox` 不只可作为 target，也能嵌套在进程参数中。下面让子进程收到真正的 `Multiplier` 实例，再由另一个顶层函数调用它：

```python
# worker.py 再增加：
def apply_and_print(worker: Callable[[int], int], number: int) -> None:
    print(worker(number))
```

```python
from worker import Multiplier

if __name__ == "__main__":
    apply_and_print = PBox(name="apply_and_print", entry=WORKER_ENTRY)
    multiplier = PBox(Multiplier(5), entry=WORKER_ENTRY)

    process = SpawnProcess(
        entry=WORKER_ENTRY,
        target=apply_and_print,
        args=(multiplier, 8),
    )
    process.start()
    process.join()
```

这里 `apply_and_print` 在 target 位置还原为函数，`multiplier` 在 args 中还原为带有 `factor=5` 状态的实例，最终输出 `40`。这展示了一个关键点：每个 `PBox` 会在反序列化时独立还原，因而 target 和 args 中都可以使用。

### PBox 的边界

`PBox` 解决的是**对象来源映射**，不是把任意 Python 运行时状态变成可序列化数据。使用时应遵守以下规则：

- 优先包装模块顶层定义的函数、类和可调用实例；
- lambda、嵌套函数和捕获外部变量的闭包通常无法在子进程入口中按限定名称重建；
- 类方法和实例绑定方法会被拒绝。需要传递状态时，包装整个类或实例；需要调用方法时，可让实例实现 `__call__`，或增加顶层包装函数；
- 文件句柄、锁、事件循环、网络连接等系统资源通常不能 pickle，应在 worker initializer 或任务内部创建；
- `name` 与 `value` 不能同时提供，也不能同时为空；
- pickle 错误可能在 `start()`、`submit()` 或 `map()` 真正序列化任务时才出现，而不是创建 `PBox` 时立即出现。

```{admonition} 安全提醒
:class: attention
pickle 可以在反序列化时执行代码。只应接收并反序列化当前程序自己产生、通过可信进程通道传递的数据，不要对外部不可信字节使用 pickle 或 `PBox`。
```

## 组件选型

| 需求 | 推荐组件 |
| --- | --- |
| 判断代码运行在哪类进程 | `in_main_process` / `in_melobot_sub_process` |
| 启动一个有独立生命周期的任务 | `SpawnProcess` |
| 兼容已有 `multiprocessing.Pool` 代码 | `SpawnProcessPool` |
| 新项目、同步任务批处理或与 asyncio 集成 | `SpawnProcessPoolExecutor` |
| 修正函数、类或实例在子进程中的 pickle 来源 | `PBox` |

模块也提供 `Process`、`ProcessPool` 和 `ProcessPoolExecutor` 作为上述三个 Spawn 类的短别名。文档和公共库代码中使用完整名称通常更容易看出其 spawn 语义。

## 总结

准备轻量 worker 入口，把 CPU 密集任务提交给长期复用的 `SpawnProcessPoolExecutor`，是最常见的使用方式。函数可直接从入口按名称取得时使用 `PBox(name=...)`；需要携带可调用实例状态时使用 `PBox(value=...)`。始终用主模块保护创建进程的代码，并把数据库连接、事件循环和其他进程私有资源留到 worker 内初始化。
