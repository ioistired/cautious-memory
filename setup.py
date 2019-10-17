#!/usr/bin/env python3

import setuptools

setuptools.setup(
	name='cautious_memory',
	version='0.0.1',

	packages=[
		'cautious_memory',
		'cautious_memory.cogs',
		'cautious_memory.cogs.permissions',
		'cautious_memory.cogs.wiki',
		'cautious_memory.utils',
	],

	include_package_data=True,

	install_requires=[
		'asyncpg',
		'bot_bin[sql]>=1.1.0,<2.0.0',
		'braceexpand',
		'discord.py>=1.2.2,<2.0.0',
		'jinja2',
		'jishaku>=1.14.0',
		'json5',
	],
)
