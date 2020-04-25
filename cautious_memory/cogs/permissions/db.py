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

import enum
import typing

import asyncpg
import discord
from bot_bin.misc import natural_join
from bot_bin.sql import connection, optional_connection
from discord.ext import commands

from ...utils import errors

class Permissions(enum.Flag):
	# this class is the single source of truth for the permissions values
	# so DO NOT change any existing values, and make sure that new ones exceed the current maximum value!
	none	= 0
	view	= 1
	rename	= 2
	edit	= 4
	create	= 8
	delete	= 16
	manage_permissions	= 32
	manage_bindings 	= 64
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
			valid_perms = natural_join(list(cls.__members__), conj='or')
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
		self.queries = self.bot.queries('permissions.sql')

	@commands.Cog.listener()
	async def on_guild_role_delete(self, role):
		await self.delete_role_permissions(role)

	@optional_connection
	async def permissions_for(self, member: discord.Member, title):
		role_ids = [role.id for role in member.roles if role != member.guild.default_role]
		page_id = await connection().fetchval(self.queries.get_page_id(), member.guild.id, title)
		if page_id is None:
			raise errors.PageNotFoundError(title)
		perms = await connection().fetchval(
			self.queries.permissions_for(),
			page_id, member.id, role_ids, member.guild.id, Permissions.default.value)

		return Permissions(perms)

	@optional_connection
	async def member_permissions(self, member: discord.Member):
		roles = [role.id for role in member.roles]
		perms = await connection().fetchval(self.queries.member_permissions(), roles, Permissions.default.value)
		return Permissions(perms)

	@optional_connection
	async def highest_manage_permissions_role(self, member: discord.Member) -> typing.Optional[discord.Role]:
		"""return the highest role that this member has that allows them to edit permissions"""
		member_roles = [role.id for role in member.roles]
		manager_roles = [
			member.guild.get_role(row[0])
			for row in await connection().fetch(
				self.queries.manage_permissions_roles(),
				member_roles, Permissions.manage_permissions.value)]
		manager_roles.sort()
		return manager_roles[-1] if manager_roles else None

	@optional_connection
	async def get_role_permissions(self, role: discord.Role):
		return Permissions(await connection().fetchval(self.queries.get_role_permissions(), role.id))

	@optional_connection
	async def set_role_permissions(self, role: discord.Role, perms: Permissions):
		await connection().execute(self.queries.set_role_permissions(), role.id, perms.value)

	@optional_connection
	async def delete_role_permissions(self, role: discord.Role):
		await connection().execute(self.queries.delete_role_permissions(), role.id)

	@optional_connection
	async def set_default_permissions(self, guild_id):
		"""If the guild has no @everyone permissions set up, set its permissions to the defailt.
		This should be called whenever role permissions are updated.
		"""
		await connection().execute(
			self.queries.set_default_permissions(),
			guild_id, Permissions.default.value)

	# no unset_role_permissions because unset means to give the default permissions
	# to deny all perms just use deny_role_permissions

	@optional_connection
	async def allow_role_permissions(self, member, role: discord.Role, new_perms: Permissions):
		await self.check_permissions(member, role)
		if role.is_default:
			await self.set_default_permissions(role.guild.id)
		return Permissions(await connection().fetchval(
			self.queries.allow_role_permissions(),
			role.id, new_perms.value))

	@optional_connection
	async def deny_role_permissions(self, member, role: discord.Role, perms):
		"""revoke a set of permissions from a role"""
		await self.check_permissions(member, role)
		if role.is_default:
			await self.set_default_permissions(role.guild.id)
		return Permissions(await connection().fetchval(self.queries.deny_role_permissions(), role.id, perms.value))

	@optional_connection
	async def get_page_overwrites(self, guild_id, title) -> typing.Mapping[int, typing.Tuple[Permissions, Permissions]]:
		"""get the allowed and denied permissions for a particular page"""
		async with connection().transaction():
			page_id = await connection().fetchval(self.queries.get_page_id(), guild_id, title)
			if page_id is None:
				raise errors.PageNotFoundError(title)

			return {
				entity: (Permissions(allow), Permissions(deny))
				for entity, allow, deny in await connection().fetch(self.queries.get_page_overwrites(), page_id)}

	@optional_connection
	async def get_page_overwrites_for(
		self,
		guild_id,
		entity_id: int,
		title
	) -> typing.Tuple[Permissions, Permissions]:
		async with connection().transaction():
			page_id = await connection().fetchval(self.queries.get_page_id(), guild_id, title)
			if page_id is None:
				raise errors.PageNotFoundError(title)

			row = await connection().fetchrow(
				self.queries.get_page_overwrites_for(),
				page_id, entity_id)

			if row is None:
				return (Permissions.none, Permissions.none)
			return tuple(map(Permissions, row))

	@optional_connection
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
			await connection().execute(
				self.queries.set_page_overwrites(),
				guild_id, title, entity_id, allow_perms.value, deny_perms.value)
		except asyncpg.NotNullViolationError:
			# the page_id CTE returned no rows
			raise errors.PageNotFoundError(title)

	@optional_connection
	async def unset_page_overwrites(self, *, guild_id, title, entity_id):
		"""remove all of the allowed and denied overwrites for a page"""
		command_tag = await connection().execute(self.queries.unset_page_overwrites(), guild_id, title, entity_id)
		count = int(command_tag.split()[-1])
		if not count:
			raise errors.PageNotFoundError(title)

	@optional_connection
	async def add_page_permissions(
		self,
		*,
		member,
		title,
		entity_id,
		new_allow_perms: Permissions = Permissions.none,
		new_deny_perms: Permissions = Permissions.none
	):
		"""add permissions to the set of "allow" or "deny" overwrites for a page"""
		if new_allow_perms & new_deny_perms != Permissions.none:
			# don't allow someone to both deny and allow a permission
			raise ValueError('allowed and denied permissions must not intersect')

		await self.check_permissions_for(member, title)

		try:
			return tuple(map(Permissions, await connection().fetchrow(
				self.queries.add_page_permissions(),
				member.guild.id, title, entity_id, new_allow_perms.value, new_deny_perms.value)))
		except asyncpg.NotNullViolationError:
			# the page_id CTE returned no rows
			raise errors.PageNotFoundError(title)

	@optional_connection
	async def unset_page_permissions(self, *, member, title, entity_id, perms):
		"""remove a permission from either the allow or deny overwrites for a page

		This is equivalent to the "grey check" in Discord's UI.
		"""
		await self.check_permissions_for(member, title)
		return tuple(map(Permissions, await connection().fetchrow(
			self.queries.unset_page_permissions(),
			member.guild.id, title, entity_id, perms.value) or (None, None)))

	@optional_connection
	async def check_permissions(self, member, role):
		if await self.bot.is_privileged(member):
			return True

		highest_role = await self.highest_manage_permissions_role(member)
		if highest_role and role < highest_role:
			return True

		raise errors.MissingPagePermissionsError(Permissions.manage_permissions)

	@optional_connection
	async def check_permissions_for(self, member, title):
		"""raise if the member doesn't have Manage Permissions for this page"""
		if await self.bot.is_privileged(member):
			return True

		if Permissions.manage_permissions in await self.permissions_for(member, title):
			return True

		raise errors.MissingPermissionsError(Permissions.manage_permissions)

def setup(bot):
	bot.add_cog(PermissionsDatabase(bot))
