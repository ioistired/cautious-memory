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

from ...utils import AttrDict, errors

logger = logging.getLogger(__name__)

class BoundMessagesDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.queries = bot.queries('bound_messages.sql')

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
			async for channel_id, message_id in self.bound_messages(revision.page_id):
				coros.append(self.bot.http.edit_message(
					channel_id=channel_id, message_id=message_id, content=revision.content,
				))

		await asyncio.gather(*coros)

	@optional_connection
	async def get_revision(self, revision_id):
		row = await connection().fetchrow(self.queries.get_revision(), revision_id)
		if row is None:
			raise ValueError('revision_id not found')
		return AttrDict(row)

	@optional_connection
	async def bound_messages(self, page_id):
		async with connection().transaction():
			async for channel_id, message_id in connection().cursor(self.queries.bound_messages(), page_id):
				yield channel_id, message_id

def setup(bot):
	bot.add_cog(BoundMessagesDatabase(bot))
