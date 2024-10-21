# OneBot 协议实现端类型

配置好其中一种 OneBot 实现后，melobot 就可以与它通信了。从而也就可以间接与 qq 服务器交互，完成各类复杂的功能。通信的建立，在 melobot 中需要实例化[源对象](../api/melobot.io)。对应到 OneBot 协议支持部分，可用的源有三种：

- {class}`.ForwardWebSocketIO`：正向 websocket（melobot 作 ws 客户端，OneBot 实现程序作 ws 服务端）
- {class}`.ReverseWebSocketIO`：反向 websocket（melobot 作 ws 服务端，OneBot 实现程序作 ws 客户端）
- {class}`.HttpIO`：HTTP 全双工（OneBot 实现程序开启一个 HTTP GET/POST 服务供 melobot 调用，而 melobot 开启一个 HTTP POST 服务供 OneBot 实现程序调用）

就功能上来说，三种源都能完整地支持 melobot 与 OneBot 实现端的所有通信需求。但是 websocket 的通信方式显然效率会更高一些。对比 HTTP 通信，websocket 还可以及时察觉连接的关闭。
