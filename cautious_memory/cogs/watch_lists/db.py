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
import datetime as dt
import logging

import discord
from discord.ext import commands
from bot_bin.sql import connection, optional_connection

from ..permissions.db import Permissions
from ...utils import AttrDict, errors

logger = logging.getLogger(__name__)

class WatchListsDatabase(commands.Cog):
	NOTIFICATION_EMBED_COLOR = discord.Color.from_hsv(262/360, 55/100, 76/100)

	def __init__(self, bot):
		self.bot = bot
		self.wiki_commands = self.bot.cogs['Wiki']
		self.wiki_db = self.bot.cogs['WikiDatabase']
		self.queries = self.bot.queries('watch_lists.sql')

	@commands.Cog.listener()
	@optional_connection
	async def on_cm_page_edit(self, revision_id):
		async with connection().transaction():
			old, new = await self.get_revision_and_previous(revision_id)
			guild = self.bot.get_guild(new.guild)
			if guild is None:
				logger.warning(f'on_cm_page_edit: guild_id {new.guild} not found!')
				return

			coros = []
			async for user_id in self.page_subscribers(new.page_id):
				# editing a page you subscribe to should not notify yourself
				if user_id == new.author:
					continue

				member = guild.get_member(user_id)
				if member is None: continue

				try:
					await self.wiki_db.check_permissions(member, Permissions.view, new.current_title)
				except errors.MissingPagePermissionsError:
					return

				coros.append(member.send(embed=self.page_edit_notification(member, old, new)))

			await asyncio.gather(*coros)

	@commands.Cog.listener()
	@optional_connection
	async def on_cm_page_delete(self, guild_id, page_id, title):
		guild = self.bot.get_guild(guild_id)
		if guild is None:
			logger.warning(f'on_cm_page_delete: guild_id {guild_id} not found!')
			return

		coros = []
		async for user_id in self.page_subscribers(page_id):
			member = guild.get_member(user_id)
			if member is None: continue
			coros.append(member.send(embed=self.page_delete_notification(guild, title)))
		await asyncio.gather(*coros)
		await self.delete_page_subscribers(page_id)

	def page_edit_notification(self, member, old, new):
		embed = discord.Embed()
		embed.title = f'Page “{new.current_title}” was edited in server {member.guild}'
		embed.color = self.NOTIFICATION_EMBED_COLOR
		embed.set_footer(text='Edited')
		embed.timestamp = new.revised
		author = member.guild.get_member(new.author)
		if author is not None:
			embed.set_author(name=author.name, icon_url=author.avatar_url_as(static_format='png', size=64))
		try:
			embed.description = self.wiki_commands.diff(member.guild, old, new)
		except commands.UserInputError as exc:
			embed.description = str(exc)
		return embed

	def page_delete_notification(self, guild, title):
		embed = discord.Embed()
		embed.title = f'Page “{title}” was deleted in server {guild}'
		embed.color = self.NOTIFICATION_EMBED_COLOR
		embed.set_footer(text='Deleted')
		embed.timestamp = dt.datetime.utcnow()  # ¯\_(ツ)_/¯
		return embed

	@optional_connection
	async def watch_page(self, member, title) -> bool:
		"""subscribe the given user to the given page.
		return success, ie True if they were not a subscriber before.
		"""
		async with connection().transaction():
			title = (await self.wiki_db.resolve_page(member, title)).target
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
	async def watch_list(self, member):
		async with connection().transaction():
			async for page_id, title in connection().cursor(self.queries.watch_list(), member.guild.id, member.id):
				yield page_id, title

	@optional_connection
	async def page_subscribers(self, page_id):
		async with connection().transaction():
			async for user_id, in connection().cursor(self.queries.page_subscribers(), page_id):
				yield user_id

	@optional_connection
	async def delete_page_subscribers(self, page_id):
		await connection().execute(self.queries.delete_page_subscribers(), page_id)

	@optional_connection
	async def get_revision_and_previous(self, revision_id):
		rows = await connection().fetch(self.queries.get_revision_and_previous(), revision_id)
		if not rows: return rows
		if len(rows) == 1: return None, AttrDict(rows[0])
		return list(map(AttrDict, rows[::-1]))  # old to new

def setup(bot):
	bot.add_cog(WatchListsDatabase(bot))
