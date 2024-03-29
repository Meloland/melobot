# OneBot 协议和实现

melobot 无法直接作为 qq 客户端与 qq 服务器直接通信。因此需要一个“媒介”作为客户端与 qq 服务器通信，melobot 与此“媒介”交流，即可间接完成与 qq 服务器的互动。

melobot 目前版本与“媒介”的数据交换，必须遵循一种特定的协议，即：[OneBot-v11 协议](https://github.com/botuniverse/onebot-11/tree/master)。OneBot 协议规定的标准，被称为 OneBot 标准。实现 OneBot 协议，满足 OneBot 标准的“媒介”，被称为“OneBot 实现”或“OneBot 实现程序”。

具体的 OneBot 实现项目，现在流行的有很多种：

- [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) （如果你过去就使用它，且目前仍工作良好，推荐；否则不推荐使用）
- [OpenShamrock](https://github.com/whitechi73/OpenShamrock)
- [Lagrange.Core](https://github.com/KonataDev/Lagrange.Core)
- ...

你可自行查阅这些项目的文档，了解和学习它们的配置方法。

配置好其中一种 OneBot 实现后，melobot 就可以与它通信了，从而也就可以间接与 qq 服务器交互，完成各类复杂的功能了。通信的建立，在 melobot 中需要实例化[连接器对象](../api/melobot.io)。melobot 中连接器主要分为三种：

- {class}`.ForwardWsConn`：正向 websocket（melobot 作 ws 客户端，OneBot 实现程序作 ws 服务端）
- {class}`.ReverseWsConn`：反向 websocket（melobot 作 ws 服务端，OneBot 实现程序作 ws 客户端）
- {class}`.HttpConn`：HTTP 全双工（OneBot 实现程序开启一个 HTTP GET/POST 服务供 melobot 调用，而 melobot 开启一个 HTTP POST 服务供 OneBot 实现程序调用）

就功能上来说，三种方式都能完整地支持 melobot 与 OneBot 实现程序的所有通信需求。但是 websocket 的通信方式显然效率会更高一些。
