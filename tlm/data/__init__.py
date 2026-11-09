"""Bảng dữ liệu tĩnh đã giải mã (JSON trong thư mục này)."""
import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))


def load_table(name):
    with open(os.path.join(_DIR, name), encoding="utf-8") as f:
        return json.load(f)["data"]
