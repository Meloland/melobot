melobot.session
===============

会话层部件
----------------

.. autoclass:: melobot.session.Session
    :members:
    :exclude-members: __init__, is_state, get, enter

.. autoclass:: melobot.session.SessionStore
    :members:

.. autoclass:: melobot.session.Rule
    :members:

.. autoclass:: melobot.session.CompareInfo
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.session.DefaultRule
    :members: __init__
    :exclude-members: compare, compare_with

.. autofunction:: melobot.session.enter_session

会话状态
-----------------

.. autofunction:: melobot.session.suspend

.. autofunction:: melobot.session.get_session

.. autofunction:: melobot.session.get_rule

.. autofunction:: melobot.session.get_session_store

依赖注入项
----------------

.. autofunction:: melobot.session.get_session_arg

上下文动态变量
----------------

.. data:: melobot.session.session

    当前上下文中的会话，类型为 :class:`~melobot.session.Session`

.. data:: melobot.session.s_store

    当前上下文中的会话存储，类型为 :class:`~melobot.session.SessionStore`

.. data:: melobot.session.rule

    当前上下文中的规则，类型为 :class:`~melobot.session.Rule`
