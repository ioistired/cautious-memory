#!/usr/bin/env python3

# Copyright © 2019 lambda#0987
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import contextlib
import logging
import traceback
from pathlib import Path

import asyncpg
import discord
import json5
try:
	import uvloop
except ImportError:
	pass  # Windows
else:
	asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from ben_cogs.bot import BenCogsBot
from discord.ext import commands

from . import utils

BASE_DIR = Path(__file__).parent
SQL_DIR = BASE_DIR / 'sql'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

class CautiousMemory(BenCogsBot):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, setup_db=True, **kwargs)

	def process_config(self):
		self.owners = set(self.config.get('extra_owners', []))
		self.config['success_emojis'] = {False: self.config['failure_emoji'], True: self.config['success_emoji']}

		super().process_config()

	def initial_activity(self):
		prefixes = self.config['prefixes']
		return discord.Game(name=prefixes[0] + 'help')

	### Utility functions

	async def is_privileged(self, member):
		return member.guild_permissions.administrator or await self.is_owner(member)

	### Init / Shutdown

	async def init_db(self):
		credentials = self.config['database']
		self.pool = await asyncpg.create_pool(**credentials)

		self.listener_conn = await self.pool.acquire()
		def on_page_edit(connection, pid, channel, revision_id):
			# convert an asyncpg event into a discord event
			self.dispatch('page_edit', int(revision_id))
		self.listener_conn_callback = on_page_edit
		await self.listener_conn.add_listener('page_edit', on_page_edit)

	async def close(self):
		await self.listener_conn.remove_listener('page_edit', self.listener_conn_callback)
		await self.listener_conn.close()
		await super().close()

	startup_extensions = (
		'cautious_memory.cogs.permissions.db',
		'cautious_memory.cogs.permissions.commands',
		'cautious_memory.cogs.wiki.db',
		'cautious_memory.cogs.wiki.commands',
		'cautious_memory.cogs.api',
		'cautious_memory.cogs.meta',
		'jishaku',
		'ben_cogs.misc',
		'ben_cogs.debug',
		'ben_cogs.sql',
		'ben_cogs.stats',
	)
