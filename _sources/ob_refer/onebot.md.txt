# OneBot 协议和实现

melobot 无法直接作为 qq 客户端与 qq 服务器直接通信。因此需要一个“媒介”作为客户端与 qq 服务器通信，melobot 与此“媒介”交流，即可间接完成与 qq 服务器的互动。

在 melobot 中内置支持 OneBot 协议，因此后续与“媒介”的数据交换可以遵循 [OneBot-v11 协议](https://github.com/botuniverse/onebot-11/tree/master)。OneBot 协议规定的标准，被称为 OneBot 标准。实现 OneBot 协议，满足 OneBot 标准的“媒介”，被称为“OneBot 实现”或“OneBot 实现程序”。

具体的 OneBot 实现项目，现在流行的有很多种：

- [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) （如果你过去就使用它，且目前仍工作良好，推荐；否则不推荐使用）
- [OpenShamrock](https://github.com/whitechi73/OpenShamrock)
- [Lagrange.Core](https://github.com/KonataDev/Lagrange.Core)
- [LLOneBot](https://github.com/LLOneBot/LLOneBot)
- ...

你可自行查阅这些项目的文档，了解和学习它们的配置方法。
