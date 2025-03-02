melobot.utils
=============

基础工具
----------

.. autofunction:: melobot.utils.get_obj_name

.. autofunction:: melobot.utils.singleton

.. autoclass:: melobot.utils.RWContext
    :members:

.. autofunction:: melobot.utils.get_id

.. autofunction:: melobot.utils.to_async

.. autofunction:: melobot.utils.to_coro

.. autofunction:: melobot.utils.to_sync

.. autofunction:: melobot.utils.if_not

.. autofunction:: melobot.utils.unfold_ctx

.. autofunction:: melobot.utils.lock

.. autofunction:: melobot.utils.cooldown

.. autofunction:: melobot.utils.semaphore

.. autofunction:: melobot.utils.timelimit

.. autofunction:: melobot.utils.speedlimit

.. autofunction:: melobot.utils.call_later

.. autofunction:: melobot.utils.call_at

.. autofunction:: melobot.utils.async_later

.. autofunction:: melobot.utils.async_at

.. autofunction:: melobot.utils.async_interval

检查/验证
-----------

.. autoclass:: melobot.utils.check.Checker
    :exclude-members: __init__

.. autoclass:: melobot.utils.check.WrappedChecker
    :exclude-members: __init__, check

基础检查/验证工具
------------------

.. autofunction:: melobot.utils.check.checker_join

.. _melobot_match:

匹配
------

.. autoclass:: melobot.utils.match.Matcher
    :exclude-members: __init__

.. autoclass:: melobot.utils.match.WrappedMatcher
    :exclude-members: __init__, match

基础匹配工具
-------------

.. autoclass:: melobot.utils.match.StartMatcher
    :exclude-members: match

.. autoclass:: melobot.utils.match.ContainMatcher
    :exclude-members: match

.. autoclass:: melobot.utils.match.EndMatcher
    :exclude-members: match

.. autoclass:: melobot.utils.match.FullMatcher
    :exclude-members: match

.. autoclass:: melobot.utils.match.RegexMatcher
    :exclude-members: match

.. _melobot_parse:

解析
-------

.. autoclass:: melobot.utils.parse.Parser
    :exclude-members: __init__

.. autoclass:: melobot.utils.parse.AbstractParseArgs
    :exclude-members: __init__

基础解析工具
-------------

.. autoclass:: melobot.utils.parse.CmdParser
    :exclude-members: format, parse

.. autoclass:: melobot.utils.parse.CmdArgs
    :exclude-members: __init__, vals

.. autoclass:: melobot.utils.parse.CmdParserFactory

.. autoclass:: melobot.utils.parse.CmdArgFormatter

.. autoclass:: melobot.utils.parse.CmdArgFormatInfo
    :exclude-members: __init__
