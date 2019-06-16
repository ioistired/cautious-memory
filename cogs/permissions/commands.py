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

import functools, operator
import typing

import discord
from discord.ext import commands
import inflect
inflect = inflect.engine()

from cogs.permissions.db import Permissions
from utils.errors import MissingPermissionsError

class UserEditableRole(commands.Converter):
	@classmethod
	async def convert(cls, ctx, arg):
		try:
			role = await commands.RoleConverter().convert(ctx, arg)
		except commands.BadArgument:
			if arg == 'everyone':
				role = ctx.guild.default_role
			else:
				raise

		if await ctx.is_privileged(ctx.author):
			return role

		highest_role = await ctx.cog.db.highest_manage_permissions_role(ctx.author)
		if highest_role and role < highest_role:
			return role

		raise MissingPermissionsError(Permissions.manage_permissions)

Entity = typing.Union[UserEditableRole, discord.Member]

class WikiPermissions(commands.Cog, name='Wiki Permissions'):
	"""Commands that let you manage the permissions on pages.

	Each role on your server can have certain permissions associated with it that
	are related to this bot. The permissions are as follows:
	• View pages
	• Edit pages
	• Create pages
	• Rename pages
	• Delete pages
	• Manage permissions

	Each page can also have "permission overrides", which override the permissions granted by a role.
	For example, you could have a role called "Wiki Mod" have view, edit, rename and deletion permissions,
	except on an important page where you could deny the deletion permission for them.

	Each member's permission on each page is calculated as follows:
	1.) All of the permissions for all of their roles are combined.
	2.) All of the "allowed" permission overrides for that page are added to that member's permissions,
	and all of the "denied" permission overrides for that page are removed from them.

	By default, nobody can edit the wiki permissions of other roles except for server administrators.
	This is to provide a higher level of security.
	If you want to allow people with a certain role to edit wiki permissions of other roles,
	grant the role the "Manage Permissions" permission.

	For high security, it is recommended to create two roles.
	One of them would serve as the "Wiki Admin", and it would get the "Manage Roles" permission so that it can grant
	"Wiki Mod" to others.
	"Wiki Admin" would get no wiki permissions.
	"Wiki Mod" would get no special Discord permissions and all of the wiki permissions.
	"""
	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.get_cog('PermissionsDatabase')

	def cog_check(self, ctx):
		return bool(ctx.guild)

	@commands.command(name='grant')
	async def grant_permissions(self, ctx, role: UserEditableRole, *permissions: Permissions):
		"""Grant wiki permissions to a Discord role.

		To grant permissions to everyone, just specify "everyone" as the role.
		"""
		perms = functools.reduce(operator.or_, permissions, Permissions.none)
		new_perms = await self.db.allow_role_permissions(role, perms)
		await ctx.send(self.new_permissions_message(role, new_perms))

	@commands.command(name='deny', aliases=['revoke'])
	async def deny_permissions(self, ctx, role: UserEditableRole, *permissions: Permissions):
		"""Deny wiki permissions to a Discord role.

		To deny permissions to everyone, just specify "everyone" as the role.
		"""
		perms = functools.reduce(operator.or_, permissions, Permissions.none)
		new_perms = await self.db.deny_role_permissions(role, perms)
		await ctx.send(self.new_permissions_message(role, new_perms))

	@commands.command(name='grant-page')
	async def grant_page_permissions(
		self,
		ctx,
		role_or_member: Entity,
		page_title: commands.clean_content,
		*permissions: Permissions
	):
		"""Grant permissions to a certain role on a certain page.

		Their permissions on this page will override any permissions given to them by their role.
		To grant permissions to everyone, just specify "everyone" as the role.
		"""
		perms = functools.reduce(operator.or_, permissions, Permissions.none)
		new_allow, new_deny = await self.db.add_page_permissions(
			guild_id=ctx.guild.id, entity_id=role_or_member.id, title=page_title, new_allow_perms=perms)
		await ctx.send(self.new_overwrites_message(role_or_member, page_title, new_allow, new_deny))

	@commands.command(name='deny-page')
	async def deny_page_permissions(
		self,
		ctx,
		role_or_member: Entity,
		page_title: commands.clean_content,
		*permissions: Permissions
	):
		"""Deny permissions to a certain role or member on a certain page.

		Their permissions on this page will override any permissions given to them by their role.
		To deny permissions to everyone, just specify "everyone" as the role.
		"""
		perms = functools.reduce(operator.or_, permissions, Permissions.none)
		new_allow, new_deny = await self.db.add_page_permissions(
			guild_id=ctx.guild.id, entity_id=role_or_member.id, title=page_title, new_deny_perms=perms)
		await ctx.send(self.new_overwrites_message(role_or_member, page_title, new_allow, new_deny))

	@commands.command(name='uncheck-page')
	async def unset_page_permissions(
		self,
		ctx,
		role_or_member: Entity,
		page_title: commands.clean_content,
		*permissions: Permissions
	):
		""""Uncheck" (neither allow nor deny) certain permissions for a role or member on a page.

		This is equivalent to the "grey check mark" in Discord.
		To unset page permissions for everyone, just specify "everyone" as the role.
		"""
		perms = functools.reduce(operator.or_, permissions, Permissions.none)
		new_allow, new_deny = await self.db.unset_page_permissions(
			guild_id=ctx.guild.id, entity_id=role_or_member.id, title=page_title, perms=perms)
		await ctx.send(self.new_overwrites_message(role_or_member, page_title, new_allow, new_deny))

	def new_permissions_message(self, role, new_perms):
		joined = inflect.join([perm.name for perm in new_perms])
		response = f"""{self.bot.config["success_emoji"]} @{role}'s new permissions: {joined}"""
		return discord.utils.escape_mentions(response)

	def new_overwrites_message(self, entity, title, new_allow, new_deny):
		joined_allow = inflect.join([perm.name for perm in new_allow])
		joined_deny = inflect.join([perm.name for perm in new_deny])

		if isinstance(entity, discord.Role):
			entity_str = '@' + entity.name if entity.name != '@everyone' else entity.name
		else:  # discord.Member
			entity_str = '@' + entity.display_name

		response = (
			f"""{self.bot.config["success_emoji"]} {entity_str}'s new permissions on {title}:\n"""
			f'Allowed: {joined_allow}\n'
			f'Denied: {joined_deny}')
		return discord.utils.escape_mentions(response)

def setup(bot):
	bot.add_cog(WikiPermissions(bot))
