melobot API 参考
================

.. admonition:: 提示
   :class: tip

   如无特别说明，文档中所有与时间有关的参数，单位都为秒（s）

以下组件可从 melobot 命名空间直接导入：

- :class:`.MetaInfo`
- :class:`.MeloBot`
- :obj:`.thisbot`
- :class:`.ForwardWsConn`
- :class:`.ReverseWsConn`
- :class:`.HttpConn`
- :class:`.AttrSessionRule`
- :func:`.msg_event`
- :func:`.msg_text`
- :func:`.msg_args`
- :func:`.send`
- :func:`.send_wait`
- :func:`.send_reply`
- :func:`.finish`
- :func:`.reply_finish`
- :func:`.session_store`
- :func:`.pause`
- :class:`.BotPlugin`
- :class:`.GroupMsgLvlChecker`
- :class:`.PrivateMsgLvlChecker`
- :class:`.CmdParser`
- :class:`.CmdArgFormatter`
- :func:`.lock`
- :func:`.timelimit`
- :func:`.this_dir`
- :class:`.User`
- :class:`.PriorLevel`
- :class:`.SessionRule`
- :class:`.LogicMode`

melobot API 二级目录索引：

.. toctree::
   :maxdepth: 2

   melobot.meta
   melobot.bot
   melobot.io
   melobot.models
   melobot.context
   melobot.plugin
   melobot.utils
   melobot.base
