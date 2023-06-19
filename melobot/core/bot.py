from ..interface.core import IBot
from ..interface.typing import *


class Bot(IBot):
    """
    bot 对象
    """
    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}

    def after_plugins_load() -> None:
        pass
    
    def before_connect() -> None:
        pass
    
    def after_connect() -> None:
        pass
    
    def before_event_dispatch() -> None:
        pass
    
    def before_action_send() -> None:
        pass
    
    def after_event_match() -> None:
        pass
    
    def after_event_verify() -> None:
        pass
    