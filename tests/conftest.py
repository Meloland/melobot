from tests.base import *


@aiofixture
async def current_loop():
    return aio.get_running_loop()
