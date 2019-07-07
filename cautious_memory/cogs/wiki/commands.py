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
import re
import typing

from ben_cogs.misc import natural_time
import discord
from discord.ext import commands

from ..permissions.db import Permissions
from ... import utils
from ...utils import connection, errors
from ...utils.paginator import Pages, TextPages

# if someone names a page with an @mention, we should use the username of that user
# instead of a nickname, because pages are usually longer-lived than nicknames
clean_content = commands.clean_content(use_nicknames=False)

class RevisionID(commands.Converter):
	async def convert(self, ctx, arg):
		try:
			title, revision = arg.rsplit(None, 1)
		except ValueError:
			raise commands.BadArgument('A revision ID is required.')

		try:
			self.revision = int(revision)
		except ValueError:
			raise commands.BadArgument('Invalid revision ID specified.')

		self.title = await clean_content.convert(ctx, title)
		return self

class Wiki(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.cogs['WikiDatabase']
		self.permissions_db = self.bot.cogs['PermissionsDatabase']

	def cog_check(self, ctx):
		return bool(ctx.guild)

	@commands.command(aliases=['view'])
	async def show(self, ctx, *, title: clean_content):
		"""Shows you the contents of the page requested."""
		async with self.bot.pool.acquire() as conn, conn.transaction():
			connection.set(conn)
			page = await self.db.get_page(ctx.author, title)
			await self.db.log_page_use(ctx.guild.id, title)
		await ctx.send(page.content)

	@commands.command(aliases=['readlink'])
	async def info(self, ctx, *, title: clean_content):
		"""Tells you whether a page is an alias."""
		page = await self.db.resolve_page(ctx.author, title)

		if page.alias:
			await ctx.send(f'“{page.alias}” is an alias to “{page.target}”.')
		else:
			await ctx.send(
				f'“{page.target}” is not an alias. Use the {ctx.prefix}history command for more information on it.')

	@commands.command()
	async def stats(self, ctx, *, title: clean_content = None):
		"""Shows server-wide statistics on page usage and revision."""
		if title is None:
			await self.guild_stats(ctx)
		else:
			await self.page_stats(ctx, title)

	async def guild_stats(self, ctx):
		cutoff = datetime.datetime.utcnow() - datetime.timedelta(weeks=4)
		e = discord.Embed(title='Page stats')
		# no transaction because maybe doing a lot of COUNTing would require table wide locks
		# to maintain consistency (dunno, just a hunch)
		async with self.bot.pool.acquire() as conn:
			connection.set(conn)
			page_count = await self.db.page_count(ctx.guild.id)
			revisions_count = await self.db.revisions_count(ctx.guild.id)
			total_page_uses = await self.db.total_page_uses(ctx.guild.id, cutoff=cutoff)
			e.description = f'{page_count} pages, {revisions_count} revisions, {total_page_uses} recent page uses'

			first_place = ord('🥇')

			top_pages = await self.db.top_pages(ctx.guild.id, cutoff=cutoff)
			if top_pages:
				value = '\n'.join(
					f'{chr(first_place + i)} {page.title} ({page.count} recent uses)'
					for i, page in enumerate(top_pages))
			else:
				value = 'No recent page uses.'

			e.add_field(name='Top pages', inline=False, value=value)

			top_editors = await self.db.top_editors(ctx.guild.id, cutoff=cutoff)
			if top_editors:
				value = '\n'.join(
					f'{chr(first_place + i)} <@{editor.id}> ({editor.count} revisions)'
					for i, editor in enumerate(top_editors))
			else:
				value = 'No recent page edits.'

			e.add_field(name='Top editors', inline=False, value=value)

		await ctx.send(embed=e)

	async def page_stats(self, ctx, title):
		cutoff = datetime.datetime.utcnow() - datetime.timedelta(weeks=4)
		e = discord.Embed(title=f'Stats for “{title}”')
		async with self.bot.pool.acquire() as conn:
			connection.set(conn)
			await self.db.check_permissions(ctx.author, Permissions.view, title)
			# top editors is first so that it can detect PageNotFound
			top_editors = await self.db.top_page_editors(ctx.guild.id, title)
			revisions_count = await self.db.page_revisions_count(ctx.guild.id, title)
			usage_count = await self.db.page_uses(ctx.guild.id, title, cutoff=cutoff)

		e.description = f'{revisions_count} all time revisions, {usage_count} recent uses'

		first_place = ord('🥇')
		e.add_field(name='Top editors', inline=False, value='\n'.join(
			f'{chr(first_place + i)} <@{editor.id}> authored {editor.rank * 100}% ({editor.count}) revisions recently'
			for i, editor in enumerate(top_editors)))

		await ctx.send(embed=e)

	emoji_escape_regex = re.compile(r'<a?(:\w+:)\d+>', re.ASCII)
	emoji_remove_escaped_underscores_regex = re.compile(r':(?:\w|\\_)+:', re.ASCII)

	@commands.command()
	async def raw(self, ctx, *, title: clean_content):
		"""Shows the raw contents of a page.

		This is with markdown escaped, which is useful for editing.
		"""
		async with self.bot.pool.acquire() as conn, conn.transaction():
			connection.set(conn)
			page = await self.db.get_page(ctx.author, title)
			await self.db.log_page_use(ctx.guild.id, title)

		# replace emojis with their names for mobile users, since on android at least, copying a message
		# with emojis in it copies just the name, not the name and colons
		# we also don't want the user to see the raw <:name:1234> form because they can't send that directly
		escaped = self.emoji_escape_regex.sub(r'\1', page.content)
		if len(escaped) > 2000:
			# in this case we don't want to send the fully escaped version
			# since there is no markdown in a plaintext file
			await ctx.send(discord.File(io.StringIO(escaped), page.title + '.md'))
		else:
			# escape_markdown messes up emojis for mobile users
			escaped2 = self.emoji_remove_escaped_underscores_regex.sub(
				lambda m: m[0].replace(r'\_', '_'), discord.utils.escape_markdown(escaped))
			if len(escaped2) > 2000:
				await ctx.send(file=discord.File(io.StringIO(escaped), page.title + '.md'))
			await ctx.send(escaped2)

	@commands.command()
	async def altraw(self, ctx, *, title: clean_content):
		"""Shows the raw contents of a page in a code block.

		This is for some tricky markdown that is hard to show outside of a code block, like ">" at the end of a link.
		"""
		async with self.bot.pool.acquire() as conn, conn.transaction():
			connection.set(conn)
			page = await self.db.get_page(ctx.author, title)
			await self.db.log_page_use(ctx.guild.id, title)

		emoji_escaped = self.emoji_escape_regex.sub(r'\1', page.content)
		code_blocked = utils.code_block(utils.escape_code_blocks(emoji_escaped))
		if len(code_blocked) > 2000:
			await ctx.send(file=discord.File(io.StringIO(emoji_escaped), page.title + '.md'))
		else:
			await ctx.send(code_blocked)

	@commands.command(aliases=['pages'])
	async def list(self, ctx):
		"""Shows you a list of all the pages on this server."""
		paginator = Pages(ctx, entries=[p.title async for p in self.db.get_all_pages(ctx.author)])

		if not paginator.entries:
			await ctx.send(f'No pages have been created yet. Use the {ctx.prefix}create command to make a new one.')
			return

		await paginator.begin()

	@commands.command(name='recent-revisions', aliases=['recent', 'recent-changes'])
	async def recent_revisions(self, ctx):
		"""Shows you a list of the most recent revisions to pages on this server.

		Revisions shown were made within the past two weeks.
		"""
		cutoff_delta = datetime.timedelta(weeks=2)
		cutoff = datetime.datetime.utcnow() - cutoff_delta

		entries = [
			self.revision_summary(ctx.guild, revision)
			async for revision in self.db.get_recent_revisions(ctx.author, cutoff)]

		if not entries:
			delta = natural_time(cutoff_delta.total_seconds())
			await ctx.send(f'No pages have been created or revised within the past {delta}.')
			return

		await Pages(ctx, entries=entries, numbered=False).begin()

	@commands.command()
	async def search(self, ctx, *, query):
		"""Searches this server's wiki pages for titles similar to your query."""
		paginator = Pages(ctx, entries=[p.title async for p in self.db.search_pages(ctx.author, query)])

		if not paginator.entries:
			await ctx.send(f'No pages matched your search.')
			return

		await paginator.begin()

	@commands.command(aliases=['add'])
	async def create(self, ctx, title: clean_content, *, content: clean_content):
		"""Adds a new page to the wiki.
		If the title has spaces, you must surround it in quotes.
		"""
		# hopefully prevent someone creating a wiki page like " a" that can't be retrieved
		title = title.strip()
		await self.db.create_page(ctx.author, title, content)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['revise'])
	async def edit(self, ctx, title: clean_content, *, content: clean_content):
		"""Edits an existing wiki page.
		If the title has spaces, you must surround it in quotes.
		"""
		await self.db.revise_page(ctx.author, title, content)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['remove', 'rm', 'del'])
	async def delete(self, ctx, *, title: clean_content):
		"""Deletes a wiki page. This deletes all of its revisions and aliases, as well.

		You must have the "delete pages" permission.
		"""
		was_alias = await self.db.delete_page(ctx.author, title)
		if was_alias:
			await ctx.send(f'{self.bot.config["success_emoji"]} Page alias successfully deleted.')
		else:
			await ctx.send(f'{self.bot.config["success_emoji"]} Page and all revisions and aliases successfully deleted.')

	@commands.command(ignore_extra=False)
	async def alias(self, ctx, new_name: clean_content, old_name: clean_content):
		# this docstring is used under the MIT License
		# Copyright © 2015 Rapptz
		# https://github.com/Rapptz/RoboDanny/blob/27304f6/cogs/tags.py#L305–L313
		"""Creates an alias for a pre-existing page.

		You own the page alias. However, when the original page is deleted the alias is deleted as well.
		Page aliases cannot be edited. You must delete the alias and remake it to point it to a new location.

		You must have the "create pages" permission, and must be able to view the page you are trying to alias.
		Any page name that has spaces must be surrounded in quotes.
		"""
		new_name = new_name.strip()
		await self.db.alias_page(ctx.author, new_name, old_name)
		await ctx.send(f'Page alias “{new_name}” that points to “{old_name}” succesfully created.')

	@commands.command(ignore_extra=False)
	async def ln(self, ctx, target: clean_content, link_name: clean_content):
		"""Creates an alias for a pre-existing page.

		This command is identical to the alias command except for the argument order.
		"""
		await ctx.invoke(self.alias, link_name, target)

	@commands.command(ignore_extra=False)  # in case someone tries to not quote the new_title
	async def rename(self, ctx, title: clean_content, new_title: clean_content):
		"""Renames a wiki page.

		If the old title or the new title have spaces in them, you must surround them in quotes.
		"""
		new_title = new_title.strip()
		await self.db.rename_page(ctx.author, title, new_title)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['revisions'])
	async def history(self, ctx, *, title: clean_content):
		"""Shows the revisions of a particular page"""

		entries = [
			self.revision_summary(ctx.guild, revision)
			async for revision in self.db.get_page_revisions(ctx.author, title)]
		if not entries:
			raise errors.PageNotFoundError(title)

		await Pages(ctx, entries=entries, numbered=False).begin()

	@commands.command(usage='<title> <revision ID>')
	async def revert(self, ctx, *, arg: RevisionID):
		"""Reverts a page to a previous revision ID.
		To get the revision ID, you can use the history command.
		"""
		title, revision = arg.title, arg.revision

		async with self.bot.pool.acquire() as conn, conn.transaction():
			connection.set(conn)
			try:
				revision, = await self.db.get_individual_revisions(ctx.guild.id, [revision])
			except ValueError:
				await ctx.send(f'Error: revision not found. Try using the {ctx.prefix}history command to find revisions.')
				return

			if revision.current_title.lower() != title.lower():
				await ctx.send('Error: This revision is for another page.')
				return

			await self.db.revise_page(ctx.author, title, revision.content)

		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@commands.command(aliases=['diff'], usage='<revision 1> <revision 2>')
	async def compare(self, ctx, revision_id_1: int, revision_id_2: int):
		"""Compares two page revisions by their ID.

		To get the revision ID you can use the history command.
		The revisions will always be compared from oldest to newest, regardless of the order you specify.
		You need the "edit pages" permission to use this command.
		"""
		if revision_id_1 == revision_id_2:
			await ctx.send('Provided revision IDs must be distinct.')
			return

		async with self.bot.pool.acquire() as conn:
			connection.set(conn)
			try:
				old, new = await self.db.get_individual_revisions(ctx.guild.id, (revision_id_1, revision_id_2))
			except ValueError:
				await ctx.send(
					'One or more provided revision IDs were invalid. '
					f'Use the {ctx.prefix}history command to get valid revision IDs.')
				return
			await self.db.check_permissions(ctx.author, Permissions.edit, new.title)

		if new.content is None or old.content is None:
			return await ctx.send(self.renamed_revision_summary(ctx.guild, new, old_title=old.title))

		if old.page_id != new.page_id:
			await ctx.send('You can only compare revisions of the same page.')
			return

		diff = list(difflib.unified_diff(
			old.content.splitlines(),
			new.content.splitlines(),
			fromfile=self.revision_summary(ctx.guild, old),
			tofile=self.revision_summary(ctx.guild, new),
			lineterm=''))

		if not diff:
			await ctx.send('These revisions appear to be identical.')
			return

		del old, new  # save a bit of memory while we paginate
		await TextPages(ctx, '\n'.join(map(utils.escape_code_blocks, diff)), prefix='```diff\n').begin()

	@classmethod
	def revision_summary(cls, guild, revision):
		author = cls.format_member(guild, revision.author)
		author_at = f'{author} at {utils.format_datetime(revision.revised)}'
		title = (
			f'“{revision.current_title}”'
			if revision.title == revision.current_title or revision.title is None
			else f'“{revision.current_title}” (then called “{revision.title}”)')
		return f'#{revision.revision_id}) {title} was revised by {author_at}'

	@classmethod
	def renamed_revision_summary(cls, guild, revision, *, old_title):
		author = cls.format_member(guild, revision.author)
		author_at = f'{author} at {utils.format_datetime(revision.revised)}'
		return f'“{old_title}” was renamed to “{revision.title}” by {author_at} with no changes'

	@classmethod
	def format_member(cls, guild, member_id):
		return guild.get_member(member_id) or f'unknown user with ID {member.id}'

def setup(bot):
	bot.add_cog(Wiki(bot))
