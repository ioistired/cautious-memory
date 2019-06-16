import json5

from . import CautiousMemory

with open('config.json5') as f:
	config = json5.load(f)

CautiousMemory(config=config).run()
