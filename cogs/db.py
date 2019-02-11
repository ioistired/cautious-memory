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

import asyncpg

from utils import attrdict, errors

class Database:
	def __init__(self, bot):
		self.bot = bot

	async def get_page(self, guild_id, title):
		row = await self.bot.pool.fetchrow("""
			SELECT *
			FROM pages
			INNER JOIN revisions
			ON pages.latest_revision = revision_id
			WHERE
				guild = $1
				AND LOWER(title) = LOWER($2)
		""", guild_id, title)
		if row is None:
			raise errors.PageNotFoundError(title)

		return attrdict(row)

	async def get_page_revisions(self, guild_id, title):
		revisions = await self.bot.pool.fetch("""
			SELECT *
			FROM pages
			INNER JOIN revisions
			ON pages.page_id = revisions.page_id
			WHERE
				guild = $1
				AND LOWER(title) = LOWER($2)
			ORDER BY revision_id DESC
		""", guild_id, title)
		if not revisions:
			raise errors.PageNotFoundError(title)

		return list(map(attrdict, revisions))

	async def get_all_pages(self, guild_id):
		"""return an async iterator over all pages for the given guild"""
		async for row in self.cursor("""
			SELECT *
			FROM pages
			INNER JOIN revisions
			ON pages.latest_revision = revision_id
			WHERE guild = $1
			ORDER BY LOWER(title) ASC
		""", guild_id):
			yield row

	async def search_pages(self, guild_id, query):
		"""return an async iterator over all pages whose title is similar to query"""
		async for row in self.cursor("""
			SELECT *
			FROM pages
			INNER JOIN revisions
			ON pages.latest_revision = revision_id
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
			FROM pages
			INNER JOIN revisions
			ON pages.page_id = revisions.page_id
			WHERE
				guild = $1
				AND revision_id = ANY ($2)
			ORDER BY revision_id ASC  -- usually this is used for diffs so we want oldest-newest
		""", guild_id, revision_ids)))

		if len(results) != len(revision_ids):
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

	async def set_guild_roles(self, guild_id, *, moderator_role_id, verified_role_id):
		"""
		set the role IDs for the Moderator and Verified status
		to unset a role, set the respective role to None.
		"""

		if moderator_role_id is None and verified_role_id is None:
			await self.bot.pool.execute("""
				DELETE FROM guild_settings
				WHERE guild = $1
			""", guild_id)
		else:
			await self.bot.pool.execute("""
				INSERT INTO guild_settings (guild, moderator_role, verified_role)
				VALUES ($1, $2, $3)
				ON CONFLICT (guild)
				DO UPDATE SET
					moderator_role = EXCLUDED.moderator_role,
					verified_role = EXCLUDED.verified_role
			""", guild_id, moderator_role_id, verified_role_id)

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

def setup(bot):
	bot.add_cog(Database(bot))
