# encoding: utf-8

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
from enum import IntEnum

import asyncpg
import discord
from discord.ext import commands

from utils import attrdict, errors

PageAccessLevel = IntEnum('PageAccessLevel', 'none view edit delete')

class Database(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	async def get_page(self, guild_id, title):
		row = await self.bot.pool.fetchrow("""
			SELECT *
			FROM
				pages
				INNER JOIN revisions
					ON pages.latest_revision = revisions.revision_id
			WHERE
				guild = $1
				AND LOWER(title) = LOWER($2)
		""", guild_id, title)
		if row is None:
			raise errors.PageNotFoundError(title)

		return attrdict(row)

	async def get_page_revisions(self, guild_id, title):
		async for row in self.cursor("""
			SELECT *
			FROM pages INNER JOIN revisions USING (page_id)
			WHERE
				guild = $1
				AND LOWER(title) = LOWER($2)
			ORDER BY revision_id DESC
		""", guild_id, title):
			yield row

	async def get_all_pages(self, guild_id):
		"""return an async iterator over all pages for the given guild"""
		async for row in self.cursor("""
			SELECT *
			FROM
				pages
				INNER JOIN revisions
					ON pages.latest_revision = revisions.revision_id
			WHERE guild = $1
			ORDER BY LOWER(title) ASC
		""", guild_id):
			yield row

	async def get_recent_revisions(self, guild_id, cutoff: datetime.datetime):
		"""return an async iterator over recent (after cutoff) revisions for the given guild, sorted by time"""
		async for row in self.cursor("""
			SELECT title, revision_id, page_id, author, revised
			FROM revisions INNER JOIN pages USING (page_id)
			WHERE guild = $1 AND revised > cutoff
			ORDER BY revised DESC
		""", guild_id, cutoff):
			yield row

	async def search_pages(self, guild_id, query):
		"""return an async iterator over all pages whose title is similar to query"""
		async for row in self.cursor("""
			SELECT *
			FROM
				pages
				INNER JOIN revisions
					ON pages.latest_revision = revisions.revision_id
			WHERE
				guild = $1
				AND title % $2
			ORDER BY similarity(title, $2) DESC
			LIMIT 100
		""", guild_id, query):
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
		results = list(map(attrdict, await self.bot.pool.fetch("""
			SELECT *
			FROM pages INNER JOIN revisions USING (page_id)
			WHERE
				guild = $1
				AND revision_id = ANY ($2)
			ORDER BY revision_id ASC  -- usually this is used for diffs so we want oldest-newest
		""", guild_id, revision_ids)))

		if len(results) != len(set(revision_ids)):
			raise ValueError('one or more revision IDs not found')

		return results

	async def create_page(self, title, content, *, guild_id, author_id):
		async with self.bot.pool.acquire() as conn:
			tr = conn.transaction()
			await tr.start()

			try:
				page_id = await conn.fetchval("""
					INSERT INTO pages (title, guild, latest_revision)
					VALUES ($1, $2, 0)  -- revision = 0 until we have a revision ID
					RETURNING page_id
				""", title, guild_id)
			except asyncpg.UniqueViolationError:
				await tr.rollback()
				raise errors.PageExistsError

			try:
				await self._create_revision(conn, page_id, content, author_id)
			except:
				await tr.rollback()
				raise

			await tr.commit()

	async def revise_page(self, title, new_content, *, guild_id, author_id):
		async with self.bot.pool.acquire() as conn, conn.transaction():
			page_id = await conn.fetchval("""
				SELECT page_id
				FROM pages
				WHERE
					LOWER(title) = LOWER($1)
					AND guild = $2
			""", title, guild_id)
			if page_id is None:
				raise errors.PageNotFoundError(title)

			await self._create_revision(conn, page_id, new_content, author_id)

	async def rename_page(self, guild_id, title, new_title):
		try:
			command_tag = await self.bot.pool.execute("""
				UPDATE pages
				SET title = $3
				WHERE
					LOWER(title) = LOWER($2)
					AND guild = $1
			""", guild_id, title, new_title)
		except asyncpg.UniqueViolationError:
			raise errors.PageExistsError

		# UPDATE 1 -> 1
		rows_updated = int(command_tag.split()[1])
		if not rows_updated:
			raise errors.PageNotFoundError(title)

	async def get_guild_roles(self, guild_id, *, connection=None):
		row = await (connection or self.bot.pool).fetchrow("""
			SELECT verified_role, moderator_role FROM guild_settings WHERE guild = $1
		""", guild_id)
		return row and attrdict(row)

	async def set_role(self, role_name, role_id, *, guild_id):
		"""Set the role ID for the given role name (either 'verified' or 'moderator')
		To unset it, pass None as the role_id.
		"""
		async with self.bot.pool.acquire() as conn:
			try:
				await conn.execute(f"""
					INSERT INTO guild_settings (guild, {role_name}_role)
					VALUES ($1, $2)
					ON CONFLICT (guild) DO UPDATE SET
					{role_name}_role = EXCLUDED.{role_name}_role
				""", guild_id, role_id)
			except asyncpg.CheckViolationError:
				# we tried to set both roles to NULL
				await self.clear_guild_roles(guild_id, connection=conn)

	async def clear_guild_roles(self, guild_id, *, connection=None):
		"""Unset the verified and moderator roles for the given guild."""
		await (connection or self.bot.pool).execute('DELETE FROM guild_settings WHERE guild = $1', guild_id)

	async def get_page_permissions(self, title, *, guild_id, connection=None):
		row = await (connection or self.bot.pool).fetchrow("""
			SELECT page_id, guild, title, everyone_perms, verified_perms, moderator_perms
			FROM effective_page_permissions
			WHERE guild = $1 AND LOWER(title) = LOWER($2)
		""", guild_id, title)
		if row is None:
			raise errors.PageNotFoundError(title)
		return self.convert_page_permissions(attrdict(row))

	async def get_page_permissions_for(self, title, *, guild_id, member: discord.Member):
		async with self.bot.pool.acquire() as conn:
			guild_roles = await self.get_guild_roles(guild_id, connection=conn)
			page_perms = await self.get_page_permissions(title, guild_id=guild_id, connection=conn)

		# I *could* change the parameter to type Guild, but I want to keep it consistent with the other methods
		if member == self.bot.get_guild(guild_id).owner:
			return PageAccessLevel.delete

		if guild_roles is None:
			return page_perms.everyone_perms
		return page_perms[self.user_role(member, guild_roles) + '_perms']

	@staticmethod
	def user_role(member, guild_roles):
		if guild_roles.moderator_role is not None and member._roles.has(guild_roles.moderator_role):
			return 'moderator'
		if guild_roles.verified_role is not None and member._roles.has(guild_roles.verified_role):
			return 'verified'
		return 'everyone'

	async def set_page_permissions(
		self,
		title,
		*,
		guild_id,
		everyone_perms: PageAccessLevel = PageAccessLevel.edit,
		verified_perms: PageAccessLevel = PageAccessLevel.edit,
		moderator_perms: PageAccessLevel = PageAccessLevel.edit,
	):
		tag = await self.bot.pool.execute("""
			WITH page AS (
				SELECT page_id
				FROM pages
				WHERE guild = $1 AND LOWER(title) = LOWER($2)
			)
			INSERT INTO page_permissions (page_id, everyone_perms, verified_perms, moderator_perms)
			VALUES ((SELECT page_id FROM page), $3::access_level, $4::access_level, $5::access_level)
			ON CONFLICT (page_id) DO UPDATE
			SET
				everyone_perms = EXCLUDED.everyone_perms,
				verified_perms = EXCLUDED.verified_perms,
				moderator_perms = EXCLUDED.moderator_perms
		""", guild_id, title, everyone_perms.name, verified_perms.name, moderator_perms.name)
		command_name, oid, rows_updated = tag.split()
		if not int(rows_updated):
			raise errors.PageNotFoundError(title)

	async def clear_page_permissions(self, title, *, guild_id):
		await self.bot.pool.execute("""
			WITH page AS (
				SELECT page_id
				FROM pages
				WHERE guild = $1 AND LOWER(title) = LOWER($2)
			)
			DELETE FROM page_permissions WHERE page_id = (SELECT page_id FROM page)
		""", guild_id, title)

	async def get_default_permissions(self, guild_id):
		row = await self.bot.pool.fetchrow('SELECT * FROM guild_default_permissions WHERE guild = $1', guild_id)
		if row is None:
			return attrdict.fromkeys(['default_perms', 'verified_perms', 'moderator_perms'], PageAccessLevel.edit)
		return attrdict(row)

	async def set_default_permissions(
		self,
		guild_id,
		*,
		everyone_perms: PageAccessLevel = PageAccessLevel.edit,
		verified_perms: PageAccessLevel = PageAccessLevel.edit,
		moderator_perms: PageAccessLevel = PageAccessLevel.edit,
	):
		await self.bot.pool.execute("""
			INSERT INTO guild_default_permissions (guild, everyone_perms, verified_perms, moderator_perms)
			VALUES ($1, $2::access_level, $3::access_level, $4::access_level)
			ON CONFLICT (guild) DO UPDATE
			SET
				everyone_perms = EXCLUDED.everyone_perms,
				verified_perms = EXCLUDED.verified_perms,
				moderator_perms = EXCLUDED.moderator_perms
		""", guild_id, everyone_perms.name, verified_perms.name, moderator_perms.name)

	async def clear_default_permissions(self, guild_id):
		"""reset the default permissions for a guild to the default default permissions"""
		await self.bot.pool.execute('DELETE FROM guild_default_permissions WHERE guild = $1', guild_id)

	async def _create_revision(self, connection, page_id, content, author_id):
		await connection.execute("""
			WITH revision AS (
				INSERT INTO revisions (page_id, author, content)
				VALUES ($1, $2, $3)
				RETURNING revision_id
			)
			UPDATE pages
			SET latest_revision = (SELECT revision_id FROM revision)
			WHERE page_id = $1
		""", page_id, author_id, content)

	@staticmethod
	def convert_page_permissions(row):
		for column in 'everyone_perms', 'verified_perms', 'moderator_perms':
			row[column] = PageAccessLevel[row[column]]
		return row

def setup(bot):
	bot.add_cog(Database(bot))
