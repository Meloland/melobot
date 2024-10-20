# -*- encoding: utf-8 -*-
# @File   : test_io_base.py
# @Time   : 2024/08/26 22:32:59
# @Author : Kariko Lin

# import asyncio as aio

from random import randint
from typing_extensions import LiteralString

from melobot.io import *
from melobot.log import Logger

from tests.base import *

# TODO: IO Source Tests
# Basically got how it works, but the __aenter__ process may crash in testing,
# just skip.
