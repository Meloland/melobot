import os
import json
from .Config import ConfigManager


BOT_STORE = {}


BOT_KERNEL_INFO = {
    'VERSION': '2-dev#6',
    # 可以更改，但请同时注明 律回MelodyEcho 的名字
    'DEVELOPER': '律回MelodyEcho',
    # 也可以更改，但请同时保留原地址或注明原项目名
    'PROJ_NAME': 'Qbot-MeloBot',
    'PROJ_URL': 'https://github.com/AiCorein/Qbot-MeloBot',
    'ROOT_PATH': '\\'.join(os.path.dirname(__file__).split('\\')[:-1]),
    'KERNEL_TIMEOUT': 5,
    'PRIOR_QUEUE_LEN': 2,
    "EVENT_HANDLER_NUM": 8,
    'THREAD_NUM': 20,
    'WORKING_STATUS': True,
}
# kernel 键下，为 bot 内核信息，不对外提供配置，但需要在内部或命令模板中使用
BOT_STORE['kernel'] = BOT_KERNEL_INFO


# 加载关键词词表并简单处理
corpus_path = os.path.join(
    BOT_KERNEL_INFO['ROOT_PATH'], 'corpus', 'key_ans.json'
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


# 加载基本配置
config_dict = ConfigManager(
    os.path.join(BOT_KERNEL_INFO['ROOT_PATH'], 'config')
).get_config()
BOT_STORE.update(config_dict)
