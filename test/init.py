"""
请保证 cq 连接正常
"""
import websockets
import asyncio as aio
import time
from base.Typing import *
from base.Event import *
from base.Action import *


class TestConfig:
    """
    测试配置
    """
    def __init__(self) -> None:
        self.cq_host = 'localhost'
        self.cq_port = '8083'
        self.msg_interval = 0.5
        self.buf_len = 10
        self.this_qq = 2245046708
        self.tested_qq = 2083583287
        self.tested_group = 174720233
        # 这里可以指定被测试号使用的命令起始符和间隔符
        self.cmd_start = '~'
        self.cmd_sep = '#'
        # 之后的测试代码里，起始和间隔写为 '~', '#'
        # 如果不同，发送测试前会自动替换为上方的起始和间隔


class BotTester:
    """
    测试器。
    建立简单的收发功能，用于测试 bot 号发送测试消息
    """
    def __new__(cls, *args, **kwargs) -> "BotTester":
        if not hasattr(cls, '__instance__'):
            cls.__instance__ = super(BotTester, cls).__new__(cls)
        return cls.__instance__
    
    def __init__(self) -> None:
        self.config = TestConfig()
        self.linker = self.open()
        self.buf = aio.Queue(maxsize=self.config.buf_len)
        self.link_lock = aio.Lock()
        self.link_flag = False
        self.send_lock = aio.Lock()
        self.ws = None
        self.pre_send_t = None
    
    async def open(self) -> None:
        """
        启动测试器，即建立 websockets 连接
        """
        async with self.link_lock:
            if not self.link_flag:
                self.ws = await websockets.connect(f'ws://{self.config.cq_host}:{self.config.cq_port}')
                await self.ws.recv()
                aio.create_task(self._receive())
                self.link_flag = True

    async def _receive(self) -> None:
        """
        接收并放置到缓存队列
        """
        while True:
            raw_e = await self.ws.recv()
            event = BotEvent(raw_e)
            if self.buf.full(): 
                raise RuntimeError("缓存队列满，尝试增大队列最大长度")
            await self.buf.put(event)

    async def send(
        self, 
        content: Union[str, Msg, MsgSegment], 
        isPrivate: bool=True,
        respNum: int=1, 
        allTimeout: int=10
    ) -> Union[BotEvent, List[BotEvent], None]:
        """
        发送内容进行测试
        """
        async def send_and_wait():
            action = msg_action(
                content,
                isPrivate,
                self.config.tested_qq,
                self.config.tested_group
            )
            action_str = action.flatten()
            await self.ws.send(action_str)
            res = []
            i = 0
            while i < respNum:
                event: BotEvent = await self.buf.get()
                if event.is_resp(): continue
                res.append(event)
                i += 1
            return res
        
        async with self.send_lock:
            try:
                if self.pre_send_t is not None:
                    await aio.sleep(self.config.msg_interval-(time.time()-self.pre_send_t))
                resp = await aio.wait_for(send_and_wait(), timeout=allTimeout)
                self.pre_send_t = time.time()
                return resp if respNum != 1 else resp[0]
            except aio.TimeoutError:
                return None


TESTER = BotTester()


async def send_test(
    self, 
    content: str, 
    isPrivate: bool=True,
    respNum: int=1, 
    allTimeout: int=10
) -> Union[BotEvent, List[BotEvent], None]:
    """
    发送一个测试
    """
    await TESTER.open()
    content.replace('~', TESTER.config.cmd_start).replace('#', TESTER.config.cmd_sep)
    return TESTER.send(content, isPrivate, respNum, allTimeout)
