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
import logging

import discord
from discord.ext import commands
from querypp import AttrDict, load_sql

from ..permissions.db import Permissions
from ... import SQL_DIR
from ...utils import connection, errors, optional_connection

logger = logging.getLogger(__name__)

class WatchListsDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.wiki_commands = self.bot.cogs['Wiki']
		self.wiki_db = self.bot.cogs['WikiDatabase']
		with (SQL_DIR / 'watch_lists.sql').open() as f:
			self.queries = load_sql(f)

	@commands.Cog.listener()
	@optional_connection
	async def on_page_edit(self, revision_id):
		async with connection().transaction():
			old, new = await self.get_revision_and_previous(revision_id)
			guild = self.bot.get_guild(new.guild)
			if guild is None:
				logger.warning(f'on_page_edit: guild_id {new.guild} not found!')
				return

			async def send(member, embed):
				try:
					await self.wiki_db.check_permissions(member, Permissions.view, new.current_title)
				except errors.MissingPermissionsError:
					return

				await member.send(embed=embed)

			coros = []
			async for user_id in self.page_subscribers(revision_id):
				member = guild.get_member(user_id)
				coros.append(send(member, self.page_edit_notification(member, new)))  # := when
			await asyncio.gather(*coros)

	def page_edit_notification_embed(self, member, revision):
		member = guild.get_member(user_id)
		embed = discord.Embed()
		embed.title = f'Page “{new.current_title}” was edited in server {guild}'
		embed.color = discord.Color.from_hsv(262/360, 55/100, 76/100)
		embed.set_footer(text='Edited')
		embed.timestamp = new.revised
		embed.set_author(name=member.name, icon_url=member.avatar_url_as(static_format='png', size=64))
		embed.description = self.wiki_commands.diff(guild, old, new)
		coros.append(send(member, embed))

	@optional_connection
	async def watch_page(self, member, title) -> bool:
		"""subscribe the given user to the given page.
		return success, ie True if they were not a subscriber before.
		"""
		await self.wiki_db.check_permissions(member, Permissions.view, title)
		tag = await connection().execute(self.queries.watch_page(), member.guild.id, member.id, title)
		if tag.rsplit(None, 1)[-1] == '0':
			raise errors.PageNotFoundError(title)

	@optional_connection
	async def unwatch_page(self, member, title) -> bool:
		"""unsubscribe the given user from the given page.
		return success, ie True if they were a subscriber before.
		"""
		tag = await connection().execute(self.queries.unwatch_page(), member.guild.id, member.id, title)
		return tag.split(None, 1)[-1] == '1'

	@optional_connection
	async def page_subscribers(self, revision_id):
		async with connection().transaction():
			async for user_id, in connection().cursor(self.queries.page_subscribers(), revision_id):
				yield user_id

	@optional_connection
	async def get_revision_and_previous(self, revision_id):
		rows = await connection().fetch(self.queries.get_revision_and_previous(), revision_id)
		if not rows: return rows
		if len(rows) == 1: return None, AttrDict(rows[0])
		return list(map(AttrDict, rows[::-1]))  # old to new

def setup(bot):
	bot.add_cog(WatchListsDatabase(bot))
