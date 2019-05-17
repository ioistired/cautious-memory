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

import enum
import os.path
import typing

import asyncpg
import discord
from discord.ext import commands
import inflect
inflect = inflect.engine()

from bot import SQL_DIR
from utils import errors, load_sql

class Permissions(enum.Flag):
	# this class is the single source of truth for the permissions values
	# so DO NOT change any of them, and make sure that new ones exceed the current maximum value!
	none	= 0
	view	= 1
	rename	= 2
	edit	= 4
	create	= 8
	delete	= 16
	manage_permissions = 32
	default = create | view | rename | edit

	def __iter__(self):
		for perm in type(self).__members__.values():
			if perm is not self.default and perm is not self.none and perm in self:
				yield perm

	@classmethod
	async def convert(cls, ctx, arg):
		try:
			return cls.__members__[arg.lower().replace('-', '_')]
		except KeyError:
			valid_perms = inflect.join(list(cls.__members__), conj='or')
			raise commands.BadArgument(f'Invalid permission specified. Try one of these: {valid_perms}.')

# Permissions.__new__ is replaced after class definition
# so to replace that definition, we must also do so after class definition, not during
def __new__(cls, value=None):
	if value is None:
		return cls.none
	return enum.Flag.__new__(cls, value)

Permissions.__new__ = __new__
del __new__

class PermissionsDatabase(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		with open(os.path.join(SQL_DIR, 'permissions.sql')) as f:
			self.queries = load_sql(f)

	async def permissions_for(self, member: discord.Member, title):
		roles = [role.id for role in member.roles] + [member.id]
		perms = await self.bot.pool.fetchval(
			self.queries.permissions_for,
			member.guild.id, title, roles, Permissions.default.value)
		return Permissions(perms)

	async def member_permissions(self, member: discord.Member):
		roles = [role.id for role in member.roles]
		perms = await self.bot.pool.fetchval(
			self.queries.member_permissions,
			member.guild.id, roles, Permissions.default.value)
		return Permissions(perms)

	async def highest_manage_permissions_role(self, member: discord.Member) -> typing.Optional[discord.Role]:
		"""return the highest role that this member has that allows them to edit permissions"""
		member_roles = [role.id for role in member.roles]
		manager_roles = [
			member.guild.get_role(row[0])
			for row in await self.bot.pool.fetch(
				self.queries.manage_permissions_roles,
				member_roles, Permissions.manage_permissions.value)]
		manager_roles.sort()
		return manager_roles[-1] if manager_roles else None

	async def get_role_permissions(self, role: discord.Role):
		return Permissions(await self.bot.pool.fetchval(self.queries.get_role_permissions, role.id))

	async def set_role_permissions(self, role: discord.Role, perms: Permissions):
		await self.bot.pool.execute(self.queries.set_role_permissions, role.id, perms.value)

	async def set_default_permissions(self, guild_id, *, connection=None):
		"""If the guild has no @everyone permissions set up, set its permissions to the defailt.
		This should be called whenever role permissions are updated.
		"""
		await (connection or self.bot.pool).execute(
			self.queries.set_default_permissions,
			guild_id, Permissions.default.value)

	# no unset_role_permissions because unset means to give the default permissions
	# to deny all perms just use deny_role_permissions

	async def allow_role_permissions(self, role: discord.Role, new_perms: Permissions):
		async with self.bot.pool.acquire() as conn:
			if role.is_default:
				await self.set_default_permissions(role.guild.id, connection=conn)
			return Permissions(await conn.fetchval(self.queries.allow_role_permissions, role.id, new_perms.value))

	async def deny_role_permissions(self, role: discord.Role, perms):
		"""revoke a set of permissions from a role"""
		async with self.bot.pool.acquire() as conn:
			if role.is_default:
				await self.set_default_permissions(role.guild.id, connection=conn)
			return Permissions(await conn.fetchval(self.queries.deny_role_permissions, role.id, perms.value))

	async def get_page_overwrites(self, guild_id, title) -> typing.Mapping[int, typing.Tuple[Permissions, Permissions]]:
		"""get the allowed and denied permissions for a particular page"""
		# TODO figure out a way to raise an error on page not found instead of returning {}
		return {
			entity: (Permissions(allow), Permissions(deny))
			for entity, allow, deny in await self.bot.pool.fetch(
				self.queries.get_page_overwrites,
				guild_id, title)}

	async def set_page_overwrites(
		self,
		*,
		guild_id,
		title,
		entity_id,
		allow_perms: Permissions = Permissions.none,
		deny_perms: Permissions = Permissions.none
	):
		"""set the allowed, denied, or both permissions for a particular page and entity (role or member)"""
		if new_allow_perms & new_deny_perms != Permissions.none:
			# don't allow someone to both deny and allow a permission
			raise ValueError('allowed and denied permissions must not intersect')

		try:
			await self.bot.pool.execute(
				self.queries.set_page_overwrites,
				guild_id, title, entity_id, allow_perms.value, deny_perms.value)
		except asyncpg.NotNullViolationError:
			# the page_id CTE returned no rows
			raise errors.PageNotFoundError(title)

	async def unset_page_overwrites(self, *, guild_id, title, entity_id):
		"""remove all of the allowed and denied overwrites for a page"""
		command_tag = await self.bot.pool.execute(self.queries.unset_page_overwrites, guild_id, title, entity_id)
		count = int(command_tag.split()[-1])
		if not count:
			raise errors.PageNotFoundError(title)

	async def add_page_permissions(
		self,
		*,
		guild_id,
		title,
		entity_id,
		new_allow_perms: Permissions = Permissions.none,
		new_deny_perms: Permissions = Permissions.none
	):
		"""add permissions to the set of "allow" overwrites for a page"""
		if new_allow_perms & new_deny_perms != Permissions.none:
			# don't allow someone to both deny and allow a permission
			raise ValueError('allowed and denied permissions must not intersect')

		try:
			return tuple(map(Permissions, await self.bot.pool.fetchrow(
				self.queries.add_page_permissions,
				guild_id, title, entity_id, new_allow_perms.value, new_deny_perms.value)))
		except asyncpg.NotNullViolationError:
			# the page_id CTE returned no rows
			raise errors.PageNotFoundError(title)

	async def unset_page_permissions(self, *, guild_id, title, entity_id, perms):
		"""remove a permission from either the allow or deny overwrites for a page

		This is equivalent to the "grey check" in Discord's UI.
		"""
		return tuple(map(Permissions, await self.bot.pool.fetchrow(
			self.queries.unset_page_permissions,
			guild_id, title, entity_id, perms.value) or (None, None)))

def setup(bot):
	bot.add_cog(PermissionsDatabase(bot))
