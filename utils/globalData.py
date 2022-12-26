import os
import json
from .globalPattern import *
from .config import ConfigManager


BOT_STORE = {}


# 加载基本配置
BOT_STORE = ConfigManager().get_config()


# 加载关键词词表并简单处理
corpus_path = os.path.join(
    os.path.dirname(__file__), '..', 'corpus', 'key_ans.json'
)
with open(corpus_path, encoding='utf-8') as fp:
    raw_dict = json.load(fp)
mapped_dict = {}
for rule in raw_dict:
    for keyword in rule['keys']:
        mapped_dict[keyword] = {
            "prob": rule['prob'],
            "ans": rule['ans']
        }
# data 键下，用来存放全局可用的数据
BOT_STORE['data'] = {}
BOT_STORE['data']['KEY_ANS'] = mapped_dict


# 加载其他核心配置
if BOT_STORE['operation']['WORKING_TIME'] <= 0:
    BOT_STORE['operation']['WORKING_TIME'] = None

BOT_KERNEL_INFO = {
    'VERSION': '1.2.0',
    # 可以更改，但请同时注明 律回MelodyEcho 的名字
    'DEVELOPER': '律回MelodyEcho',
    # 也可以更改，但请同时保留原地址或注明原项目名
    'PROJ_NAME': 'Qbot-MeloBot',
    'PROJ_URL': 'https://github.com/AiCorein/Qbot-MeloBot',
    'KERNEL_TIMEOUT': 5,
    'PRIOR_QUEUE_LEN': 2,
    "EVENT_HANDLER_NUM": 8,
    'THREAD_NUM': 8,
    'WORKING_STATUS': True,
    'EVENT_TYPE': {
        'eq_full': 'bot_eventq_full',
    },
    'ACTION_TYPE': {},
}
BOT_STORE['kernel'] = BOT_KERNEL_INFO
# kernel 键下，为 bot 内核信息，不对外提供配置，但需要在内部或命令模板中使用