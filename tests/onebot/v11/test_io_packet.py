import time

from melobot.protocols.onebot.v11.io import packet
from tests.base import *


async def test_packet():
    p = packet.InPacket(time=time.time(), data={"key": "value"})
    p = packet.OutPacket(
        time=time.time(),
        action_type="action",
        action_params={"key": "value"},
        echo_id="123456",
    )
    p = packet.EchoPacket(time=time.time(), data={"key": "value"})
