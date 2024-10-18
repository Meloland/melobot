protocols.onebot API 参考
================================

.. admonition:: 提示
    :class: tip

    - 如无特别说明，文档中所有与时间有关的参数，单位都为秒（s）
    - 如无特别说明，API 文档中没有给出 __init__ 方法的类，用户不应该手动初始化

.. admonition:: 提示
    :class: tip
    
    - 目前只支持 OneBot v11，以下所有 API 均为 v11 的 API

以下组件可从 `melobot.protocols.onebot.v11` 命名空间直接导入：

- :data:`.PROTOCOL_IDENTIFIER`
- :class:`~.v11.adapter.base.Adapter`, :class:`.EchoRequireCtx`
- :class:`.ForwardWebSocketIO`, :class:`.ReverseWebSocketIO`, :class:`.HttpIO`
- :class:`~.adapter.event.Event`, :class:`~.adapter.segment.Segment`, :class:`~.adapter.action.Action`, :class:`~.adapter.echo.Echo`
- :func:`.on_event`, :func:`.on_message`, :func:`.on_notice`, :func:`.on_request`, :func:`.on_meta`
- :class:`.LevelRole`, :class:`.GroupRole`, :class:`.ParseArgs`

各模块 API 文档索引：

.. toctree::
    :maxdepth: 1

    v11.const
    v11.adapter
    v11.io
    v11.handle
    v11.utils
