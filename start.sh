#!/usr/bin/bash

set -euxo pipefail

pip install --pre yt-dlp
python main.py
