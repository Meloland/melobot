melobot API
================

.. admonition:: 提示
    :class: tip

    - 如无特别说明，文档中所有与时间有关的参数，单位都为秒（s）
    - 如无特别说明，API 文档中没有给出 __init__ 方法的类，用户不应该手动初始化

以下组件可从 melobot 命名空间直接导入：

- :class:`.MetaInfo`, :func:`.lazy_load`, :data:`.MODULE_EXTS`, :func:`.add_import_fallback`, :func:`.install_exc_hook`, :func:`.uninstall_exc_hook`, :func:`.set_traceback_style`
- :class:`.Bot`, :func:`.get_bot`
- :class:`.PluginPlanner`, :class:`.PluginInfo`, :class:`.PluginLifeSpan`, :class:`.AsyncShare`, :class:`.SyncShare`
- :class:`~melobot.adapter.base.Adapter`, :class:`~melobot.adapter.model.Event`, :class:`~melobot.adapter.model.Action`, :class:`~melobot.adapter.model.Echo`
- :func:`.send_text`, :func:`.send_image`
- :func:`.node`, :func:`.nextn`, :func:`.stop`, :func:`.block`, :func:`.bypass`, :func:`.flow_to`, :func:`.rewind`, :func:`.get_event`, :func:`.try_get_event`, :func:`.get_flow_arg`, :func:`.get_flow_store`
- :class:`.Flow`, :class:`.FlowDecorator`, :class:`.FlowNode`, :class:`.FlowStore`, :func:`~melobot.handle.on_event`, :func:`.on_text`, :func:`.on_start_match`, :func:`.on_contain_match`, :func:`.on_full_match`, :func:`.on_end_match`, :func:`.on_regex_match`, :func:`.on_command`
- :class:`.Depends`, :func:`.inject_deps`, :class:`.Reflect`, :class:`.MatchEvent`, :class:`.Exclude`
- :class:`.Session`, :class:`.Rule`, :class:`.DefaultRule`, :func:`.enter_session`, :func:`.suspend`, :class:`.SessionStore`, :func:`.get_session`, :func:`.get_session_arg`, :func:`.get_session_store`
- :class:`.GenericLogger`, :class:`.Logger`, :func:`.get_logger`
- :class:`.LogicMode`, :class:`.LogLevel`, :class:`.Color`
- :class:`.Context`

各模块 API 文档索引：

.. toctree::
    :maxdepth: 1

    melobot
    melobot.bot
    melobot.plugin
    melobot.adapter
    melobot.io
    melobot.protocol
    melobot.handle
    melobot.di
    melobot.session
    melobot.log
    melobot.utils
    melobot.typ
    melobot.exceptions
    melobot.mp
    melobot.ctx
    melobot.mixin
