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

import datetime
import enum
import operator
import os.path
import typing

import asyncpg
import discord
from discord.ext import commands

from bot import SQL_DIR
from utils import attrdict, errors, load_sql

class WikiDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		with open(os.path.join(SQL_DIR, 'wiki.sql')) as f:
			self.queries = load_sql(f)

	async def get_page(self, guild_id, title, *, connection=None):
		row = await (connection or self.bot.pool).fetchrow(self.queries.get_page, guild_id, title)
		if row is None:
			raise errors.PageNotFoundError(title)

		return attrdict(row)

	async def get_page_revisions(self, guild_id, title):
		async for row in self.cursor(self.queries.get_page_revisions, guild_id, title):
			yield row

	async def get_all_pages(self, guild_id):
		"""return an async iterator over all pages for the given guild"""
		async for row in self.cursor(self.queries.get_all_pages, guild_id):
			yield row

	async def get_recent_revisions(self, guild_id, cutoff: datetime.datetime):
		"""return an async iterator over recent (after cutoff) revisions for the given guild, sorted by time"""
		async for row in self.cursor(self.queries.get_recent_revisions, guild_id, cutoff):
			yield row

	async def resolve_page(self, guild_id, title, *, connection=None):
		async def inner(conn):
			row = await conn.fetchrow(self.queries.get_alias, guild_id, title)
			if row is not None:
				return attrdict(row)

			row = await conn.fetchrow(self.queries.get_page_no_alias, guild_id, title)
			if row is not None:
				return attrdict(row)

			raise errors.PageNotFoundError(title)

		if connection is None:
			async with self.bot.pool.acquire() as conn, conn.transaction():
				return await inner(conn)

		return await inner(connection)

	async def search_pages(self, guild_id, query):
		"""return an async iterator over all pages whose title is similar to query"""
		async for row in self.cursor(self.queries.search_pages, guild_id, query):
			yield row

	async def cursor(self, query, *args):
		"""return an async iterator over all rows matched by query and args. Lazy equivalent to fetch()"""
		async with self.bot.pool.acquire() as conn, conn.transaction():
			async for row in conn.cursor(query, *args):
				yield attrdict(row)

	async def get_individual_revisions(self, guild_id, revision_ids):
		"""return a list of page revisions for the given guild.
		the revisions are sorted by their revision ID.
		"""
		results = list(map(attrdict, await self.bot.pool.fetch(
			self.queries.get_individual_revisions,
			guild_id, revision_ids)))

		if len(results) != len(set(revision_ids)):
			raise ValueError('one or more revision IDs not found')

		return results

	async def page_count(self, guild_id, *, connection=None):
		return await (connection or self.bot.pool).fetchval(self.queries.page_count, guild_id)

	async def revisions_count(self, guild_id, *, connection=None):
		return await (connection or self.bot.pool).fetchval(self.queries.revisions_count, guild_id)

	async def page_uses(self, guild_id, title, *, cutoff=None, connection=None):
		cutoff = cutoff or datetime.datetime.utcnow() - datetime.timedelta(weeks=4)
		return await (connection or self.bot.pool).fetchval(self.queries.page_uses, guild_id, title, cutoff)

	async def page_revisions_count(self, guild_id, title, *, connection=None):
		return await (connection or self.bot.pool).fetchval(self.queries.page_revisions_count, guild_id, title)

	async def top_page_editors(self, guild_id, title, *, cutoff=None, connection=None):
		cutoff = cutoff or datetime.datetime.utcnow() - datetime.timedelta(weeks=4)
		return list(map(attrdict, await (connection or self.bot.pool).fetch(
			self.queries.top_page_editors,
			guild_id, title, cutoff)))

	async def total_page_uses(self, guild_id, *, cutoff=None, connection=None):
		cutoff = cutoff or datetime.datetime.utcnow() - datetime.timedelta(weeks=4)
		return await (connection or self.bot.pool).fetchval(self.queries.total_page_uses, guild_id, cutoff)

	async def top_pages(self, guild_id, *, cutoff=None, connection=None):
		cutoff = cutoff or datetime.datetime.utcnow() - datetime.timedelta(weeks=4)
		return list(map(attrdict, await (connection or self.bot.pool).fetch(self.queries.top_pages, guild_id, cutoff)))

	async def top_editors(self, guild_id, *, cutoff=None, connection=None):
		cutoff = cutoff or datetime.datetime.utcnow() - datetime.timedelta(weeks=4)
		return list(map(attrdict, await (connection or self.bot.pool).fetch(
			self.queries.top_editors,
			guild_id, cutoff)))

	async def create_page(self, title, content, *, guild_id, author_id):
		async with self.bot.pool.acquire() as conn, conn.transaction():
			try:
				page_id = await conn.fetchval(self.queries.create_page, guild_id, title)
			except asyncpg.UniqueViolationError:
				raise errors.PageExistsError

			await conn.execute(self.queries.create_first_revision, page_id, author_id, content, title)

	async def alias_page(self, guild_id, alias_title, target_title):
		try:
			await self.bot.pool.execute(self.queries.alias_page, guild_id, alias_title, target_title)
		except asyncpg.NotNullViolationError:
			# the CTE returned no rows
			raise errors.PageNotFoundError(target_title)
		except asyncpg.UniqueViolationError:
			raise errors.PageExistsError

	async def revise_page(self, title, new_content, *, guild_id, author_id):
		async with self.bot.pool.acquire() as conn, conn.transaction():
			page_id = await conn.fetchval(self.queries.get_page_id, guild_id, title)
			if page_id is None:
				raise errors.PageNotFoundError(title)

			await conn.execute(self.queries.create_revision, page_id, author_id, new_content)

	async def rename_page(self, guild_id, title, new_title, *, author_id):
		async with self.bot.pool.acquire() as conn, conn.transaction():
			try:
				page_id = await conn.fetchval(self.queries.rename_page, guild_id, title, new_title)
			except asyncpg.UniqueViolationError:
				raise errors.PageExistsError

			if page_id is None:
				raise errors.PageNotFoundError(title)

			await conn.execute(self.queries.log_page_rename, page_id, author_id, new_title)

	async def delete_page(self, guild_id, title) -> bool:
		"""delete a page or alias

		return whether an alias was deleted
		"""
		async with self.bot.pool.acquire() as conn, conn.transaction():
			command_tag = await conn.execute(self.queries.delete_alias, guild_id, title)
			if command_tag.split()[-1] != '0':
				return True

			command_tag = await conn.execute(self.queries.delete_page, guild_id, title)
			if command_tag.split()[-1] != '0':
				return False

		raise errors.PageNotFoundError(title)

	async def log_page_use(self, guild_id, title, *, connection=None):
		await (connection or self.bot.pool).execute(self.queries.log_page_use, guild_id, title)

	## Permissions

def setup(bot):
	bot.add_cog(WikiDatabase(bot))
