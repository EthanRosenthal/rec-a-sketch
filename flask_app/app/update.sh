#!/bin/bash
PATH=/home/ubuntu/miniconda2/envs/recasketch/bin
cd ~/rec-a-sketch/flask_app/app
python helpers.py --config ../../config.yml --task update_mids
