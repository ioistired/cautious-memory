# Copyright © 2020 lambda#0987
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
import logging
from typing import List, Awaitable

import discord
from discord.ext import commands
from bot_bin.sql import connection, optional_connection

from ..wiki.db import Permissions
from ...utils import AttrDict, errors

logger = logging.getLogger(__name__)

class MessageBindingDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.wiki_db = bot.cogs['WikiDatabase']
		self.queries = bot.queries('binding.sql')

	@commands.Cog.listener()
	async def on_cm_page_edit(self, revision_id):
		async with self.bot.pool.acquire() as conn, conn.transaction():
			try:
				revision = await self.get_revision(revision_id)
			except ValueError:
				logger.error('on_cm_page_edit: revision ID %s not found!', revision_id)
				return

			if not self.bot.get_guild(revision.guild):
				logger.error(
					'on_cm_page_edit: page ID %s is part of guild ID %s, which we are not in!',
					revision.page_id,
					revision.guild,
				)
				return

			coros = []
			async for binding in self._bound_messages(revision.page_id):
				coros.append(self.bot.http.edit_message(
					channel_id=binding.channel_id, message_id=binding.message_id, content=revision.content,
				))

		await asyncio.gather(*coros)

	@commands.Cog.listener()
	async def on_cm_page_delete(self, guild_id, page_id, title):
		if not self.bot.get_guild(guild_id):
			logger.error(
				'on_cm_page_delete: page %r (ID %s) is part of guild ID %s, which we are not in!',
				title, page_id, guild_id,
			)
			return

		async with self.bot.pool.acquire() as conn, conn.transaction():
			coros = []
			async for binding in self._bound_messages(page_id):
				coros.append(self.bot.http.delete_message(channel_id=binding.channel_id, message_id=binding.message_id))
			await self.delete_all_bindings(page_id)

		await asyncio.gather(*coros, return_exceptions=True)

	@optional_connection
	async def get_revision(self, revision_id):
		row = await connection().fetchrow(self.queries.get_revision(), revision_id)
		if row is None:
			raise ValueError('revision_id not found')
		return AttrDict(row)

	@optional_connection
	async def bound_messages(self, member, title):
		async with connection().transaction():
			page = await self.wiki_db.get_page(member, title, partial=True)
			async for row in self._bound_messages(page.page_id):
				yield row

	@optional_connection
	async def _bound_messages(self, page_id):
		async with connection().transaction():
			async for row in connection().cursor(self.queries.bound_messages(), page_id):
				yield AttrDict(row)

	@optional_connection
	async def guild_bindings(self, member):
		"""Return all bound messages for guild_id."""
		async with connection().transaction():
			await self.wiki_db.check_permissions(member, Permissions.view)
			async for row in connection().cursor(self.queries.guild_bindings(), member.guild.id):
				yield AttrDict(row)

	@optional_connection
	async def bind(self, member, message: discord.Message, title):
		async with connection().transaction():
			page = await self.wiki_db.get_page(member, title, check_permissions=False)
			await self.wiki_db.check_permissions(member, Permissions.edit, title)
			await connection().execute(self.queries.bind(), message.channel.id, message.id, page.page_id)
		binding = page
		binding.channel_id = message.channel.id
		binding.message_id = message.id
		return binding

	@optional_connection
	async def get_bound_page(self, message: discord.Message):
		row = await connection().fetchrow(self.queries.get_bound_page(), message.id)
		if row is None:
			raise errors.BindingNotFoundError
		return AttrDict(row)

	@optional_connection
	async def unbind(self, member, message: discord.Message):
		"""Unbind a message. Return whether the message was successfully unbound."""
		async with connection().transaction():
			page = await self.get_bound_page(message)
			await self.wiki_db.check_permissions(member, Permissions.edit, page.title)
			tag = await connection().execute(self.queries.unbind(), message.id)
		return tag == 'DELETE 1'

	@optional_connection
	async def delete_all_bindings(self, page_id):
		"""Return how many bindings were deleted."""
		tag = await connection().execute(self.queries.delete_all_bindings(), page_id)
		return int(tag.rsplit(None, 1)[-1])

def setup(bot):
	bot.add_cog(MessageBindingDatabase(bot))
