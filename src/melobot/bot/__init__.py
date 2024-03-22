from .init import BOT_LOCAL as thisbot
from .init import MeloBot

#: 指向当前上下文 bot 实例的全局变量，运行时使用。使用时当做 bot 实例（:class:`MeloBot` 对象）使用即可
thisbot: "MeloBot"  # type: ignore

__all__ = ("thisbot", "MeloBot")
