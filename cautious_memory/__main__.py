import json5

from . import CautiousMemory, BASE_DIR

with open(BASE_DIR.parent / 'config.json5') as f:
	config = json5.load(f)

CautiousMemory(config=config).run()
