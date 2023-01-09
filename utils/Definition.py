import time


class Singleton:
    """
    单例类
    """
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance


class IdWorker(Singleton):
    """
    雪花算法生成 ID
    """
    def __init__(self, datacenter_id, worker_id, sequence=0) -> int:
        self.MAX_WORKER_ID = -1 ^ (-1 << 3)
        self.MAX_DATACENTER_ID = -1 ^ (-1 << 5)
        self.WOKER_ID_SHIFT = 12
        self.DATACENTER_ID_SHIFT = 12 + 3
        self.TIMESTAMP_LEFT_SHIFT = 12 + 3 + 5
        self.SEQUENCE_MASK = -1 ^ (-1 << 12)
        self.STARTEPOCH = 1064980800000
        # sanity check
        if worker_id > self.MAX_WORKER_ID or worker_id < 0:
            raise ValueError('worker_id 值越界')
        if datacenter_id > self.MAX_DATACENTER_ID or datacenter_id < 0:
            raise ValueError('datacenter_id 值越界')
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = sequence
        self.last_timestamp = -1  # 上次计算的时间戳

    def __gen_timestamp(self) -> int:
        """
        生成整数时间戳
        """
        return int(time.time() * 1000)

    def get_id(self) -> int:
        """
        获取新 ID
        """
        timestamp = self.__gen_timestamp()

        # 时钟回拨
        if timestamp < self.last_timestamp:
            raise ValueError(f'时钟回拨，{self.last_timestamp} 前拒绝 id 生成请求')
        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & self.SEQUENCE_MASK
            if self.sequence == 0:
                timestamp = self.__til_next_millis(self.last_timestamp)
        else:
            self.sequence = 0
        self.last_timestamp = timestamp
        new_id = ((timestamp - self.STARTEPOCH) << self.TIMESTAMP_LEFT_SHIFT) | (self.datacenter_id << self.DATACENTER_ID_SHIFT) | (
                    self.worker_id << self.WOKER_ID_SHIFT) | self.sequence
        return new_id

    def __til_next_millis(self, last_timestamp) -> int:
        """
        等到下一毫秒
        """
        timestamp = self.__gen_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self.__gen_timestamp()
        return timestamp


ID_WORKER = IdWorker(1, 1, 0)


class BotException(Exception):
    """
    bot 异常基类
    """
    def __init__(self, err: str):
        super().__init__(self)
        self.err = f'[{self.__class__.__name__}] {err}'
        self.origin_err = err
    
    def __str__(self):
        return self.err


class BotWrongCmdFlag(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnknownEvent(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnexpectEvent(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotCmdExecFailed(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnknownCmdName(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnexpectFormat(BotException):
    def __init__(self, err: str):
        super().__init__(err)