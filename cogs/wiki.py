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

import io

from discord.ext import commands

class Wiki:
	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.get_cog('Database')

	@commands.command(aliases=['get'])
	async def show(self, ctx, *, title: commands.clean_content):
		"""Searches the wiki for the page requested."""
		page = await self.db.get_page(ctx.guild.id, title)
		await ctx.send(page.content)

	@commands.command(aliases=['add'])
	async def create(self, ctx, title: commands.clean_content, *, content: commands.clean_content):
		"""Adds a new page to the wiki.
		If the title has spaces, you must surround it in quotes.
		"""
		await self.db.create_page(title, content, guild_id=ctx.guild.id, author_id=ctx.author.id)
		await ctx.message.add_reaction(self.bot.emoji_config.success[True])

	@commands.command(aliases=['revise'])
	async def edit(self, ctx, title: commands.clean_content, *, content: commands.clean_content):
		"""Edits an existing wiki page.
		If the title has spaces, you must surround it in quotes.
		"""
		await self.db.revise_page(title, content, guild_id=ctx.guild.id, author_id=ctx.author.id)
		await ctx.message.add_reaction(self.bot.emoji_config.success[True])

	@commands.command(aliases=['revisions'])
	async def history(self, ctx, *, title: commands.clean_content):
		"""shows the revisions of a particular page"""
		message = io.StringIO()
		for revision in await self.db.get_page_revisions(ctx.guild.id, title):
			message.write(f'#{revision.revision_id} Created by ')
			message.write(str(ctx.guild.get_member(revision.author)) or "unknown user")
			# TODO support per-guild timezone
			message.write(f' at {revision.created.strftime("%I:%M:%S %p UTC")}\n')

		await ctx.send(message.getvalue())

def setup(bot):
	bot.add_cog(Wiki(bot))
