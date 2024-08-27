from tests.base import *


@aiofixture
async def current_loop() -> aio.AbstractEventLoop:
    return aio.get_running_loop()
