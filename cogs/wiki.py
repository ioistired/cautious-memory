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

import difflib
import io
import typing

import discord
from discord.ext import commands
from jishaku.paginators import WrappedPaginator, PaginatorInterface

import utils

class WrappedPaginator(WrappedPaginator):
	"""subclass of jishaku.paginators.WrappedPaginator
	that does not cause PaginatorInterface to complain about max_size
	"""
	def __init__(self, *args, **kwargs):
		max_size = kwargs.pop('max_size', 1991)  # constant found by binary search
		super().__init__(*args, **kwargs, max_size=max_size)

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
		# hopefully prevent someone creating a wiki page like " a" that can't be retrieved
		title = title.strip()
		await self.db.create_page(title, content, guild_id=ctx.guild.id, author_id=ctx.author.id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['revise'])
	async def edit(self, ctx, title: commands.clean_content, *, content: commands.clean_content):
		"""Edits an existing wiki page.
		If the title has spaces, you must surround it in quotes.
		"""
		await self.db.revise_page(title, content, guild_id=ctx.guild.id, author_id=ctx.author.id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command()
	async def rename(self, ctx, title: commands.clean_content, new_title: commands.clean_content):
		"""Renames a wiki page.

		If the old title or the new title have spaces in them, you must surround it in quotes.
		"""
		await self.db.rename_page(ctx.guild.id, title, new_title)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['revisions'])
	async def history(self, ctx, *, title: commands.clean_content):
		"""shows the revisions of a particular page"""
		paginator = WrappedPaginator(prefix='', suffix='')  # suppress the default code block behavior
		for revision in await self.db.get_page_revisions(ctx.guild.id, title):
			paginator.add_line(self.revision_summary(ctx.guild, revision))

		await PaginatorInterface(self.bot, paginator).send_to(ctx)

	@commands.command()
	async def revert(self, ctx, title: commands.clean_content, revision: int):
		"""Reverts a page to a previous revision ID.
		To get the revision ID, you can use the history command.
		If the title has spaces, you must surround it in quotes.
		"""
		revision, = await self.db.get_individual_revisions(ctx.guild.id, [revision])
		if revision.title != title:
			await ctx.send('Error: This revision is for another page.')
			return

		await self.db.revise_page(title, revision.content, guild_id=ctx.guild.id, author_id=ctx.author.id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['diff'], usage='<revision 1> <revision 2>')
	async def compare(self, ctx, revision_id_1: int, revision_id_2: int):
		"""Compare two page revisions by their ID.

		To get the revision ID you can use the history command.
		The revisions will always be compared from oldest to newest, regardless of the order you specify.
		"""
		old, new = await self.db.get_individual_revisions(ctx.guild.id, (revision_id_1, revision_id_2))

		diff = difflib.unified_diff(
			old.content.splitlines(),
			new.content.splitlines(),
			fromfile=self.revision_summary(ctx.guild, old),
			tofile=self.revision_summary(ctx.guild, new),
			lineterm='')

		del old, new  # save a bit of memory while we paginate
		paginator = WrappedPaginator(prefix='```diff\n')
		for line in diff:
			paginator.add_line(utils.escape_code_blocks(line))

		await PaginatorInterface(self.bot, paginator).send_to(ctx)

	@staticmethod
	def revision_summary(guild, revision):
		author = guild.get_member(revision.author) or f'unknown user with ID {revision.author}'
		return f'#{revision.revision_id} Created by {author} at {utils.format_datetime(revision.revised)}'

def setup(bot):
	bot.add_cog(Wiki(bot))
