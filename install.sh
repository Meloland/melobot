#!/bin/bash
DIR=$( cd "$(dirname "${BASH_SOURCE[0]}")" && pwd);
cd $DIR
pip install .
rm -rf ./build
rm -rf ./*.egg-info