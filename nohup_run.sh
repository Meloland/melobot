#!/bin/bash
# 后台运行 bot，请先保证 go-cq 已经启动
DIR=$( cd "$(dirname "${BASH_SOURCE[0]}")" && pwd);
cd $DIR
nohup python3 ./main.py > /dev/null 2>&1 &
