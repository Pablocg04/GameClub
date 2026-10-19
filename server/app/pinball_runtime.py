import json
from pathlib import Path
from .native import NativeAssets


class PinballAssets(NativeAssets):
    def __init__(self, data):
        self.directory = data/'pinball-runtime/v1'
        self.info = json.loads((Path(__file__).parent/'pinball_runtime.json').read_text(encoding='utf-8'))
        self.metadata = {platform: {'vpx': entry} for platform, entry in self.info['platforms'].items()}
        self.locks = {}
        self.verified = set()
