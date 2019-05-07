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

	@commands.group(invoke_without_command=False)
	async def roles(self, ctx):
		"""Show the configured roles on this server."""
		roles = await self.db.get_guild_roles(ctx.guild.id)
		if not roles:
			await ctx.send('No roles have been configured for this server.')

		verified_role = self.format_role(ctx.guild, roles.verified_role)
		moderator_role = self.format_role(ctx.guild, roles.moderator_role)

		await ctx.send(discord.utils.escape_mentions(
			f'Verified role: {verified_role}\n'
			f'Moderator role: {moderator_role}'))

	async def set_role(self, ctx, role_name, role: discord.Role):
		if not role < ctx.author.top_role and ctx.guild.owner != ctx.author:
			await ctx.send('You may only configure roles lower than your highest role on this server.')

		await self.db.set_role(role_name, role.id, guild_id=ctx.guild.id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(name='set-verified-role')
	@commands.has_permissions(manage_roles=True)
	async def set_verified_role(self, ctx, *, verified_role: discord.Role):
		"""Set the verified role for your server. All people with this role will get verified permissions."""
		await self.set_role(ctx, 'verified', verified_role)

	@commands.command(name='set-moderator-role')
	@commands.has_permissions(manage_roles=True)
	async def set_moderator_role(self, ctx, *, moderator_role: discord.Role):
		"""Set the moderator role for your server. All people with this role will get moderator permissions."""
		await self.set_role(ctx, 'moderator', moderator_role)

	async def unset_role(self, ctx, role_name):
		roles = await self.db.get_guild_roles(ctx.guild.id)
		attr = role_name + '_role'
		if not roles or not roles[attr]:
			await ctx.send(f'{role_name.title()} role is already cleared.')
			return

		role = ctx.guild.get_role(roles[attr])
		# allow anyone to clear a deleted role
		if not role or role < ctx.author.top_role or ctx.guild.owner == ctx.author:
			await self.db.set_role(role_name, None, guild_id=ctx.guild.id)
			await ctx.message.add_reaction(self.bot.config['success_emoji'])
			return

		await ctx.send('You may only configure roles lower than your highest role on this server.')

	@commands.command(name='unset-verified-role')
	@commands.has_permissions(manage_roles=True)
	async def unset_verified_role(self, ctx):
		"""Clear the verified role for your server. Nobody will get verified permissions."""
		await self.unset_role(ctx, 'verified')

	@commands.command(name='unset-moderator-role')
	@commands.has_permissions(manage_roles=True)
	async def unset_moderator_role(self, ctx):
		"""Clear the moderator role for your server. Nobody will get moderator permissions."""
		await self.unset_role(ctx, 'moderator')

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
