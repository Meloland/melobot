#!/bin/bash
DIR=$( cd "$(dirname "${BASH_SOURCE[0]}")" && pwd);
cd $DIR
pip3 install .
rm -rf ./build
rm -rf ./melobot.egg-info