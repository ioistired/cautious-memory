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

import discord
from discord.ext import commands

from cogs.db import PageAccessLevel

class PageAccessLevelConverter(commands.Converter):
	@staticmethod
	async def convert(ctx, argument):
		try:
			return PageAccessLevel[argument.lower()]
		except KeyError:
			valid = ', '.join(PageAccessLevel.__members__.keys())
			raise commands.BadArgument(f'Invalid permission level. The valid ones are {valid}.')

class WikiPermissions(commands.Cog, name='Wiki Permissions'):
	"""Commands that configure the permissions for particular pages or the entire server.

	The permissions system in this bot works like so.
	There are three roles any member can be in: everyone (the default), Verified, or Moderator.
	Of these, Verified and Moderator can be tied to a role on your server.
	When a role is set, everyone in that role will have the permissions of it, as determined by the server's
	default permissions and individual page permission overrides.

	Permissions have a hierarchy: none (no permissions), view, edit, and delete, with later permissions including
	all earlier permissions. For example, anyone who can edit a page can also view it, but cannot delete it.

	For example:
	- "head honcho" is configured as the moderator role
	- Riley has this role.
	- The server's default permissions are set to: everyone=edit, verified=edit, moderator=delete
	- The permission overrides for page "smoke on the water" are everyone=view, verified=view, moderator=edit

	In this situation, Riley can delete, edit, and view any page,
	except for "smoke on the water", which they can only edit.
	"""

	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.get_cog('Database')

	def cog_check(self, ctx):
		return bool(ctx.guild)

	@commands.command(aliases=['permissions', 'perms'])
	async def roles(self, ctx):
		"""Show the configured roles on this server and their permissions."""
		roles = await self.db.get_guild_roles(ctx.guild.id)
		if not roles:
			await ctx.send('No roles have been configured for this server.')

		verified_role = self.format_role(ctx.guild, roles.verified_role)
		moderator_role = self.format_role(ctx.guild, roles.moderator_role)
		perms = await self.db.get_default_permissions(ctx.guild.id)

		await ctx.send(discord.utils.escape_mentions(
			f"Everyone's permissions: {perms.everyone_perms}\n"
			f'Verified role: {verified_role}, Permissions: {perms.verified_perms}\n'
			f'Moderator role: {moderator_role}, Permissions: {perms.moderator_perms}'))

	@commands.command(name='set-role')
	@commands.has_permissions(manage_roles=True)
	async def set_role(self, ctx, role_name, *, discord_role: discord.Role):
		"""Set the given role to correspond to a discord role on your server.
		All members with that role will get its permissions.
		"""
		role_name = role_name.lower()
		if role_name not in {'verified', 'moderator'}:
			await ctx.send('Invalid role specified.')
			return

		if not discord_role < ctx.author.top_role and not ctx.author.guild_permissions.administrator:
			await ctx.send('You may only configure roles lower than your highest role on this server.')
			return

		await self.db.set_role(role_name, discord_role.id, guild_id=ctx.guild.id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(name='unset-role')
	@commands.has_permissions(manage_roles=True)
	async def unset_role(self, ctx, role_name):
		"""Clear the given role on your server. Nobody will get the permissions of that role."""
		role_name = role_name.lower()
		# it's very important that this role name gets validated to avoid SQL injection
		if role_name not in {'verified', 'moderator'}:
			await ctx.send('Invalid role specified.')
			return

		roles = await self.db.get_guild_roles(ctx.guild.id)
		attr = role_name + '_role'
		if not roles or not roles[attr]:
			await ctx.send(f'{role_name.title()} role is already cleared.')
			return

		role = ctx.guild.get_role(roles[attr])
		if not role or role < ctx.author.top_role:  # allow anyone to clear a deleted role
			await self.db.set_role(role_name, None, guild_id=ctx.guild.id)
			await ctx.message.add_reaction(self.bot.config['success_emoji'])
			return

		await ctx.send('You may only configure roles lower than your highest role on this server.')

	@commands.command(name='set-role-permissions')
	async def set_role_permissions(self, ctx, role_name, permissions: PageAccessLevelConverter):
		"""Set the permissions that people of a certain role (or everyone) gets by default.

		For the role argument you may pass either "everyone", "verified", or "moderator".
		"""
		role_name = role_name.lower()
		if role_name not in {'everyone', 'verified', 'moderator'}:
			await ctx.send('Invalid role specified.')
			return

		roles = await self.db.get_guild_roles(ctx.guild.id)

		if role_name != 'everyone' and not roles.get(f'{role_name}_role'):
			await ctx.send(
				f'{role_name.title()} role not set. Use the {ctx.prefix}set-role command to set it up.')
			return

		role_names = ['everyone', 'verified', 'moderator']
		highest_role = self.db.member_role(ctx.author, roles)
		i = role_names.index(highest_role)
		editable_roles = set(role_names[:i])  # allow editing all roles up to highest
		uneditable_roles = role_names[i:]

		perms = await self.db.get_default_permissions(ctx.guild.id)
		role = ctx.guild.default_role if role_name == 'everyone' else ctx.guild.get_role(roles[f'{role_name}_role'])

		if not permissions <= perms.get(highest_role, perms.get('everyone', PageAccessLevel.edit)):
			await ctx.send('You may not grant permissions you do not have.')
			return

		author_perms = ctx.author.guild_permissions

		if (
			author_perms.administrator
			# sometimes the role doesn't exist in the server anymore
			# in this case we need some sort of baseline guild permission to allow them to edit it
			or (author_perms.manage_roles and not role)
			or (role_name in editable_roles)
			or (role and (
				(author_perms.manage_roles and role < ctx.author.top_role)  # whether they can edit the role in the UI
				or (not role.is_default and ctx.author._roles.has(role.id))))  # do they have the role
		):
			await self.db.set_default_permissions(role_name, permissions, guild_id=ctx.guild.id)
			await ctx.message.add_reaction(self.bot.config['success_emoji'])
		else:
			if role_name == 'everyone':
				await ctx.send(
					'You must have the verified or moderator role '
					'or the Manage Roles permissions to edit the default permissions.')
				return
			await ctx.send(
				f'You must have one of these roles: {", ".join(uneditable_roles)}'
				' or have Manage Roles permissions to edit this role.')

	@staticmethod
	def format_role(guild, role_id):
		if role_id is None:
			return '*Not configured*'
		role = guild.get_role(role_id)
		if role is None:
			return 'Unknown role with ID {role_id}'
		return f'@{role}'

def setup(bot):
	bot.add_cog(WikiPermissions(bot))
