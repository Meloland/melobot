#!/bin/bash
# 请先保证 go-cq 已经启动
DIR=$( cd "$(dirname "${BASH_SOURCE[0]}")" && pwd);
cd $DIR
cd "../../bot"
python3 ./main.py

