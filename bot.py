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
import os.path
import re
import traceback
import uuid

import asyncpg
import discord
from discord.ext import commands
import json5
try:
	import uvloop
except ImportError:
	pass  # Windows
else:
	asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

import utils

BASE_DIR = os.path.dirname(__file__)
SQL_DIR = os.path.join(BASE_DIR, 'sql')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot')

class CautiousMemory(commands.AutoShardedBot):
	def __init__(self, *args, **kwargs):
		self.config = kwargs.pop('config')
		self.process_config()
		self._fallback_prefix = str(uuid.uuid4())

		super().__init__(
			command_prefix=self.get_prefix_,
			description=self.config.get('description'),
			help_command=commands.MinimalHelpCommand(),
			activity=self.activity,
			*args, **kwargs)

	def process_config(self):
		self.owners = set(self.config.get('extra_owners', ()))
		if self.config.get('primary_owner'):
			self.owners.add(self.config['primary_owner'])

		with contextlib.suppress(KeyError):
			self.config['copyright_license_file'] = os.path.join(BASE_DIR, self.config['copyright_license_file'])

		self.config['success_emoji'] = utils.convert_emoji(self.config['success_emoji'])
		self.config['failure_emoji'] = utils.convert_emoji(self.config['failure_emoji'])

	@property
	def activity(self):
		prefixes = self.config['prefixes']
		return discord.Game(name=prefixes[0] + 'help')

	def get_prefix_(self, bot, message):
		match = self.prefix_re.search(message.content)

		if match is None:
			# Callable prefixes must always return at least one prefix,
			# but no prefix was found in the message,
			# so we still have to return *something*.
			# Use a UUID because it's practically guaranteed not to be in the message.
			return self._fallback_prefix
		else:
			return match[0]

	@property
	def prefix_re(self):
		prefixes = self.config['prefixes']

		prefixes = list(prefixes)  # ensure it's not a tuple
		if self.is_ready():
			prefixes.extend([f'<@{self.user.id}>', f'<@!{self.user.id}>'])

		prefixes = '|'.join(map(re.escape, prefixes))
		prefixes = f'(?:{prefixes})'

		return re.compile(f'{prefixes}\\s*', re.IGNORECASE)

	### Events

	async def on_ready(self):
		separator = '━' * 44
		logger.info(separator)
		logger.info('Logged in as: %s', self.user)
		logger.info('ID: %s', self.user.id)
		logger.info(separator)

	async def on_message(self, message):
		if self.should_reply(message):
			await self.process_commands(message)

	async def process_commands(self, message):
		# overridden because the default process_commands ignores bots now
		context = await self.get_context(message)
		await self.invoke(context)

	async def get_context(self, message, cls=None):
		return await super().get_context(message, cls=cls or CustomContext)

	# based on https://github.com/Rapptz/RoboDanny/blob/ca75fae7de132e55270e53d89bc19dd2958c2ae0/bot.py#L77-L85
	async def on_command_error(self, context, error):
		if isinstance(error, commands.NoPrivateMessage):
			await context.author.send('This command cannot be used in private messages.')
		elif isinstance(error, commands.DisabledCommand):
			message = 'Sorry. This command is disabled and cannot be used.'
			try:
				await context.author.send(message)
			except discord.Forbidden:
				await context.send(message)
		elif isinstance(error, commands.NotOwner):
			logger.error('%s tried to run %s but is not the owner', context.author, context.command.name)
			await context.message.add_reaction(self.config['failure_emoji'])
		elif isinstance(error, (commands.UserInputError, commands.CheckFailure)):
			await context.send(error)
		elif (
			isinstance(error, commands.CommandInvokeError)
			and not hasattr(context.cog, 'cog_command_error')
		):
			logger.error('"%s" caused an exception', context.message.content)
			logger.error(''.join(traceback.format_tb(error.original.__traceback__)))
			# pylint: disable=logging-format-interpolation
			logger.error('{0.__class__.__name__}: {0}'.format(error.original))

			await context.send('An internal error occured while trying to run that command.')

	### Utility functions

	def should_reply(self, message):
		"""return whether the bot should reply to a given message"""
		return not (
			message.author == self.user
			or (message.author.bot and not self._should_reply_to_bot(message)))

	def _should_reply_to_bot(self, message):
		should_reply = not self.config['ignore_bots'].get('default')
		overrides = self.config['ignore_bots']['overrides']

		def check_override(location, overrides_key):
			return location and location.id in overrides[overrides_key]

		if check_override(message.guild, 'guilds') or check_override(message.channel, 'channels'):
			should_reply = not should_reply

		return should_reply

	async def is_owner(self, user):
		return user.id in self.owners or await super().is_owner(user)

	### Init / Shutdown

	async def start(self):
		await self._init_db()
		self._load_extensions()

		await super().start(self.config['tokens'].pop('discord'))

	async def logout(self):
		with contextlib.suppress(AttributeError):
			await self.pool.close()
		await super().logout()

	async def _init_db(self):
		credentials = self.config['database']
		self.pool = await asyncpg.create_pool(**credentials)

	def _load_extensions(self):
		for extension in (
			'cogs.permissions.db',
			'cogs.permissions.commands',
			'cogs.wiki.db',
			'cogs.wiki.commands',
			'cogs.meta',
			'jishaku',
			'ben_cogs.misc',
			'ben_cogs.debug',
			'ben_cogs.stats',
		):
			self.load_extension(extension)
			logger.info('Successfully loaded %s', extension)

class CustomContext(commands.Context):
	async def is_privileged(self, member):
		return member.guild_permissions.administrator or await self.bot.is_owner(member)

if __name__ == '__main__':
	with open(os.path.join(BASE_DIR, 'config.json5')) as f:
		config = json5.load(f)

	CautiousMemory(config=config).run()
