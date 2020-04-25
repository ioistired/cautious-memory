# Copyright © 2019–2020 lambda#0987
#
# Cautious Memory is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Cautious Memory is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Cautious Memory.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import contextlib
import logging
import traceback
from pathlib import Path

import asyncpg
import braceexpand
import discord
import jinja2
import json5
try:
	import uvloop
except ImportError:
	pass  # Windows
else:
	asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from bot_bin.bot import Bot
from discord.ext import commands

from . import utils

BASE_DIR = Path(__file__).parent
SQL_DIR = BASE_DIR / 'sql'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

class CautiousMemory(Bot):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, setup_db=True, **kwargs)
		self.jinja_env = jinja2.Environment(
			loader=jinja2.FileSystemLoader(str(SQL_DIR)),
			line_statement_prefix='-- :')

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

	def queries(self, template_name):
		return self.jinja_env.get_template(template_name).module

	### Init / Shutdown

	async def init_db(self):
		await super().init_db()
		await self.init_listener()

	async def init_listener(self):
		self.listener_conn = await asyncpg.connect(**self.config['database'])
		self.listener_conn_callbacks = []

		def listener(func):
			channel_name = func.__name__[len('on_'):]
			self.listener_conn_callbacks.append((channel_name, func))

			return func

		@listener
		def on_page_edit(connection, pid, channel, revision_id):
			# convert an asyncpg event into a discord event
			self.dispatch('cm_page_edit', int(revision_id))

		@listener
		def on_page_delete(connection, pid, channel, payload):
			guild_id, page_id, title = payload.split(',', 2)
			self.dispatch('cm_page_delete', int(guild_id), int(page_id), title)

		for channel, callback in self.listener_conn_callbacks:
			await self.listener_conn.add_listener(channel, callback)

	async def close(self):
		with contextlib.suppress(AttributeError):
			for channel, callback in self.listener_conn_callbacks:
				await self.listener_conn.remove_listener(channel, callback)
			await self.listener_conn.close()
		await super().close()

	startup_extensions = utils.expand("""{
		cautious_memory.cogs.{
			{permissions,wiki,watch_lists,binding}.{db,commands},
			api,
			meta},
		jishaku,
		bot_bin.{
			misc,
			debug,
			sql,
			stats}}
	""")
