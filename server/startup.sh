#!/bin/bash
# Railway 启动脚本
pip install --upgrade zhipuai>=2.0.1
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
