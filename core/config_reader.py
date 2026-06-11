import json
import os
import sys


def load_config():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    config_path = os.path.join(base_path, "config.json")

    with open(config_path, "r") as file:
        return json.load(file)