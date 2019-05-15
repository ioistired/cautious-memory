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
import difflib
import io
import typing

from ben_cogs.misc import Misc
natural_time = Misc.natural_time
import discord
from discord.ext import commands

from cogs.permissions.db import Permissions
import utils
from utils import errors
from utils.paginator import Pages, TextPages

class WikiPage(commands.Converter):
	def __init__(self, required_perms: Permissions):
		self.required_perms = required_perms

	async def convert(self, ctx, title):
		title = await commands.clean_content().convert(ctx, title)
		actual_perms = await ctx.cog.permissions_db.permissions_for(ctx.author, title)
		if self.required_perms in actual_perms or await ctx.is_privileged(ctx.author):
			return title
		raise errors.MissingPermissionsError(self.required_perms)

def has_wiki_permissions(required_perms):
	async def pred(ctx):
		member_perms = await ctx.cog.permissions_db.member_permissions(ctx.author)
		if required_perms in member_perms or await ctx.is_privileged(ctx.author):
			return True
		raise errors.MissingPermissionsError(required_perms)
	return commands.check(pred)

class Wiki(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.get_cog('WikiDatabase')
		self.permissions_db = self.bot.get_cog('PermissionsDatabase')

	def cog_check(self, ctx):
		return bool(ctx.guild)

	@commands.command(aliases=['wiki'])
	async def show(self, ctx, *, title: commands.clean_content):
		"""Shows you the contents of the page requested."""
		page = await self.db.get_page(ctx.guild.id, title)
		await ctx.send(page.content)

	@commands.command(aliases=['pages'])
	async def list(self, ctx):
		"""Shows you a list of all the pages on this server."""
		paginator = Pages(ctx, entries=[p.title async for p in self.db.get_all_pages(ctx.guild.id)])

		if not paginator.entries:
			await ctx.send(f'No pages have been created yet. Use the {ctx.prefix}create command to make a new one.')
			return

		await paginator.begin()

	@commands.command(name='recent-revisions', aliases=['recent', 'recent-changes'])
	@has_wiki_permissions(Permissions.view)
	async def recent_revisions(self, ctx):
		"""Shows you a list of the most recent revisions to pages on this server.

		Revisions shown were made within the past two weeks.
		"""
		cutoff_delta = datetime.timedelta(weeks=2)
		cutoff = datetime.datetime.utcnow() - cutoff_delta

		entries = [
			self.revision_summary(ctx.guild, revision, include_title=True)
			async for revision in self.db.get_recent_revisions(ctx.guild.id, cutoff)]

		if not entries:
			delta = natural_time(cutoff_delta.total_seconds())
			await ctx.send(f'No pages have been created or revised within the past {delta}.')
			return

		await Pages(ctx, entries=entries).begin()

	@commands.command()
	@has_wiki_permissions(Permissions.view)
	async def search(self, ctx, *, query):
		"""Searches this server's wiki pages for titles similar to your query."""
		paginator = Pages(ctx, entries=[p.title async for p in self.db.search_pages(ctx.guild.id, query)])

		if not paginator.entries:
			await ctx.send(f'No pages have been created yet. Use the {ctx.prefix}create command to make a new one.')
			return

		await paginator.begin()

	@commands.command(aliases=['add'])
	@has_wiki_permissions(Permissions.create)
	async def create(self, ctx, title: commands.clean_content, *, content: commands.clean_content):
		"""Adds a new page to the wiki.
		If the title has spaces, you must surround it in quotes.
		"""
		# hopefully prevent someone creating a wiki page like " a" that can't be retrieved
		title = title.strip()
		await self.db.create_page(title, content, guild_id=ctx.guild.id, author_id=ctx.author.id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['revise'])
	async def edit(self, ctx, title: WikiPage(Permissions.edit), *, content: commands.clean_content):
		"""Edits an existing wiki page.
		If the title has spaces, you must surround it in quotes.
		"""
		await self.db.revise_page(title, content, guild_id=ctx.guild.id, author_id=ctx.author.id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['remove'])
	async def delete(self, ctx, title: WikiPage(Permissions.delete)):
		"""Deletes a wiki page. This deletes all of its revisions, as well.

		You must have the "delete pages" permission.
		"""
		await self.db.delete_page(ctx.guild.id, title)
		await ctx.send(f'{self.bot.config["success_emoji"]} Page and all revisions successfully deleted.')

	@commands.command()
	async def rename(self, ctx, title: WikiPage(Permissions.rename), new_title: commands.clean_content):
		"""Renames a wiki page.

		If the old title or the new title have spaces in them, you must surround it in quotes.
		"""
		await self.db.rename_page(ctx.guild.id, title, new_title)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['revisions'])
	async def history(self, ctx, *, title: WikiPage(Permissions.view)):
		"""Shows the revisions of a particular page"""

		entries = [
			self.revision_summary(ctx.guild, revision)
			async for revision in self.db.get_page_revisions(ctx.guild.id, title)]
		if not entries:
			raise errors.PageNotFoundError(title)

		await Pages(ctx, entries=entries, numbered=False).begin()

	@commands.command()
	async def revert(self, ctx, title: WikiPage(Permissions.edit), revision: int):
		"""Reverts a page to a previous revision ID.
		To get the revision ID, you can use the history command.
		If the title has spaces, you must surround it in quotes.
		"""
		try:
			revision, = await self.db.get_individual_revisions(ctx.guild.id, [revision])
		except ValueError:
			await ctx.send(f'Error: revision not found. Try using the {ctx.prefix}history command to find revisions.')
			return

		if revision.title.lower() != title.lower():
			await ctx.send('Error: This revision is for another page.')
			return

		await self.db.revise_page(title, revision.content, guild_id=ctx.guild.id, author_id=ctx.author.id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['diff'], usage='<revision 1> <revision 2>')
	async def compare(self, ctx, revision_id_1: int, revision_id_2: int):
		"""Compares two page revisions by their ID.

		To get the revision ID you can use the history command.
		The revisions will always be compared from oldest to newest, regardless of the order you specify.
		"""
		if revision_id_1 == revision_id_2:
			await ctx.send('Provided revision IDs must be distinct.')
			return

		try:
			old, new = await self.db.get_individual_revisions(ctx.guild.id, (revision_id_1, revision_id_2))
		except ValueError:
			await ctx.send(
				'One or more provided revision IDs were invalid. '
				f'Use the {ctx.prefix}history command to get valid revision IDs.')
			return

		if Permissions.edit not in await self.permissions_db.permissions_for(ctx.author, new.title):
			raise errors.MissingPermissionsError(Permissions.edit)

		if old.page_id != new.page_id:
			await ctx.send('You can only compare revisions of the same page.')
			return

		diff = difflib.unified_diff(
			old.content.splitlines(),
			new.content.splitlines(),
			fromfile=self.revision_summary(ctx.guild, old),
			tofile=self.revision_summary(ctx.guild, new),
			lineterm='')

		if not diff:
			await ctx.send('These revisions appear to be identical.')
			return

		del old, new  # save a bit of memory while we paginate
		await TextPages(ctx, '\n'.join(map(utils.escape_code_blocks, diff)), prefix='```diff\n').begin()

	@staticmethod
	def revision_summary(guild, revision, *, include_title=False):
		author = guild.get_member(revision.author) or f'unknown user with ID {revision.author}'
		author_at = f'{author} at {utils.format_datetime(revision.revised)}'
		if include_title:
			return f'{revision.title} was revised by {author_at}'
		return f'#{revision.revision_id}, revised by {author_at}'

def setup(bot):
	bot.add_cog(Wiki(bot))
