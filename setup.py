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
		'aiocontextvars',
		'asyncpg',
		'ben_cogs[sql]>=0.14.0,<1.0.0',
		'discord.py>=1.2.2,<2.0.0',
		'jishaku>=1.14.0',
		'json5',
		'querypp>=0.1.0.post1,<1.0.0',
	],
)
