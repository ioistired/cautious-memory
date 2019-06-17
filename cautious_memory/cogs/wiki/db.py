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

from ... import SQL_DIR
from ..permissions.db import Permissions
from ...utils import attrdict, connection, errors, load_sql, optional_connection

class WikiDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.permissions_db = self.bot.cogs['PermissionsDatabase']
		with open(os.path.join(SQL_DIR, 'wiki.sql')) as f:
			self.queries = load_sql(f)

	@optional_connection
	async def get_page(self, member, title):
		await self.check_permissions(member, Permissions.view, title)
		row = await connection.get().fetchrow(self.queries.get_page, member.guild.id, title)
		if row is None:
			raise errors.PageNotFoundError(title)

		return attrdict(row)

	@optional_connection
	async def get_page_revisions(self, member, title):
		await self.check_permissions(member, Permissions.view, title)
		async for row in self.cursor(self.queries.get_page_revisions, member.guild.id, title):
			yield row

	@optional_connection
	async def get_all_pages(self, member):
		"""return an async iterator over all pages for the given guild"""
		await self.check_permissions(member, Permissions.view)
		async for row in self.cursor(self.queries.get_all_pages, member.guild.id):
			yield row

	@optional_connection
	async def get_recent_revisions(self, member, cutoff: datetime.datetime):
		"""return an async iterator over recent (after cutoff) revisions for the given guild, sorted by time"""
		await self.check_permissions(member, Permissions.view)
		async for row in self.cursor(self.queries.get_recent_revisions, member.guild.id, cutoff):
			yield row

	@optional_connection
	async def resolve_page(self, member, title):
		# XXX if a user is denied permissions for a page, that applies to its aliases too.
		# So if a user is denied view permissions for a single page, and they request info on an alias to that page,
		# the fact that they were denied permission to view that alias would leak information about what
		# page it is an alias to. Consider allowing anyone to resolve an alias, or only denying those who
		# were globally denied view permissions.
		await self.check_permissions(member, Permissions.view, title)
		row = await connection.get().fetchrow(self.queries.get_alias, member.guild.id, title)
		if row is not None:
			return attrdict(row)

		row = await connection.get().fetchrow(self.queries.get_page_no_alias, member.guild.id, title)
		if row is not None:
			return attrdict(row)

		raise errors.PageNotFoundError(title)

	@optional_connection
	async def search_pages(self, member, query):
		"""return an async iterator over all pages whose title is similar to query"""
		await self.check_permissions(member, Permissions.view)
		async for row in self.cursor(self.queries.search_pages, member.guild.id, query):
			yield row

	@optional_connection
	async def cursor(self, query, *args):
		"""return an async iterator over all rows matched by query and args. Lazy equivalent to fetch()"""
		async with connection.get().transaction():
			async for row in connection.get().cursor(query, *args):
				yield attrdict(row)

	@optional_connection
	async def get_individual_revisions(self, guild_id, revision_ids):
		"""return a list of page revisions for the given guild.
		the revisions are sorted by their revision ID.
		"""
		results = list(map(attrdict, await connection.get().fetch(
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
		editors = list(map(attrdict, await (connection or self.bot.pool).fetch(
			self.queries.top_page_editors,
			guild_id, title, cutoff)))
		if not editors:
			raise errors.PageNotFoundError(title)
		return editors

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

	@optional_connection
	async def create_page(self, member, title, content):
		async with connection.get().transaction():
			await self.check_permissions(member, Permissions.create)
			try:
				page_id = await connection.get().fetchval(self.queries.create_page, member.guild.id, title)
			except asyncpg.UniqueViolationError:
				raise errors.PageExistsError

			await connection.get().execute(self.queries.create_first_revision, page_id, member.id, content, title)

	@optional_connection
	async def alias_page(self, member, alias_title, target_title):
		async with connection.get().transaction():
			await self.check_permissions(member, Permissions.create)
			await self.check_permissions(member, Permissions.view, target_title)

			try:
				await connection.get().execute(self.queries.alias_page, member.guild.id, alias_title, target_title)
			except asyncpg.NotNullViolationError:
				# the CTE returned no rows
				raise errors.PageNotFoundError(target_title)
			except asyncpg.UniqueViolationError:
				raise errors.PageExistsError

	@optional_connection
	async def revise_page(self, member, title, new_content):
		async with connection.get().transaction():
			await self.check_permissions(member, Permissions.edit, title)

			page_id = await connection.get().fetchval(self.queries.get_page_id, member.guild.id, title)
			if page_id is None:
				raise errors.PageNotFoundError(title)

			try:
				await connection.get().execute(self.queries.create_revision, page_id, member.id, new_content)
			except asyncpg.StringDataRightTruncationError as exc:
				# XXX dumb way to do it but it's the only way i've got
				limit = int(re.search(r'character varying\((\d+)\)', exc.message)[1])
				raise errors.PageContentTooLongError(title, len(new_content), limit)

	@optional_connection
	async def rename_page(self, member, title, new_title):
		async with connection.get().transaction():
			try:
				page_id = await connection.get().fetchval(self.queries.rename_page, member.guild.id, title, new_title)
			except asyncpg.UniqueViolationError:
				raise errors.PageExistsError

			if page_id is None:
				raise errors.PageNotFoundError(title)

			await connection.get().execute(self.queries.log_page_rename, page_id, member.id, new_title)

	@optional_connection
	async def delete_page(self, member, title) -> bool:
		"""delete a page or alias

		return whether an alias was deleted
		"""
		async with connection.get().transaction():
			await self.check_permissions(member, Permissions.delete, title)
			command_tag = await connection.get().execute(self.queries.delete_alias, member.guild.id, title)
			if command_tag.split()[-1] != '0':
				return True

			command_tag = await connection.get().execute(self.queries.delete_page, member.guild.id, title)
			if command_tag.split()[-1] != '0':
				return False

		raise errors.PageNotFoundError(title)

	@optional_connection
	async def check_permissions(self, member, required_permissions, title=None):
		if title is None:
			actual_perms = await self.permissions_db.member_permissions(member)
		else:
			actual_perms = await self.permissions_db.permissions_for(member, title)
		if required_permissions in actual_perms or await self.bot.is_privileged(member):
			return True
		raise errors.MissingPermissionsError(required_permissions)

	@optional_connection
	async def log_page_use(self, guild_id, title):
		await connection.get().execute(self.queries.log_page_use, guild_id, title)

	## Permissions

def setup(bot):
	bot.add_cog(WikiDatabase(bot))
