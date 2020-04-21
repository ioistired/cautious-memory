# Copyright © 2020 lambda#0987
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

import asyncio
import re
import functools
import operator
import weakref

import discord
from discord.ext import commands
from bot_bin.sql import connection

from ..wiki.db import Permissions
from ... import utils
from ...utils import paginator as pages, errors

CHANNEL_MENTION_RE = re.compile('<#(\d+)>', re.ASCII)
clean_content = commands.clean_content(use_nicknames=False)

class OwnMessageOrChannel(commands.Converter):
	async def convert(self, ctx, arg):
		m = CHANNEL_MENTION_RE.search(arg)
		if m:
			ch = ctx.guild.get_channel(int(m[1]))
			if ch is None:
				raise commands.UserInputError('Channel not found.')

			self._check_permissions(ctx, ch)
			return ch

		m = await commands.MessageConverter().convert(ctx, arg)
		self._check_permissions(ctx, m.channel)
		if m.author != ctx.bot.user:
			raise commands.UserInputError('A message sent by the bot is required.')
		return m

	def _check_permissions(self, ctx, channel):
		if not channel.permissions_for(ctx.author).send_messages:
			raise errors.MissingBindingPermissionsError(
				'You must be able to send messages in that channel to bind to it.'
			)

class MessageBinding(commands.Cog, name='Message Binding'):
	"""These commands manage message binding, a nifty way to make a message
	editable by anyone who can edit its corresponding page.

	This is useful for rules channels, for example, where any moderator can edit the rules,
	and the rules are displayed as a message in a read only channel.
	"""
	def __init__(self, bot):
		self.bot = bot
		self.db = bot.cogs['MessageBindingDatabase']
		self.wiki_db = bot.cogs['WikiDatabase']

	@commands.command(usage='<channel or message sent by the bot> <title>')
	async def bind(self, ctx, target: OwnMessageOrChannel, *, title: clean_content):
		"""Bind a message to a page. Whenever the page is edited, the message will be edited too.

		You can supply either a message that the bot has sent, or a #channel mention.
		Messages can be provided by ID, channel_id-message_id (obtained via shift clicking on "Copy ID"),
		or by a link to the message.

		If a binding already exists for the given message, it will be updated.
		"""
		if isinstance(target, discord.TextChannel):
			async with self.bot.pool.acquire() as conn, conn.transaction():
				connection.set(conn)
				# I really don't like this design as it requires me to look up the page by title three times
				# Probably some more thought has to go into the separation of concerns between
				# the DB cogs and the Commands cogs.
				await self.wiki_db.check_permissions(ctx.author, Permissions.manage_bindings, title)
				page = await self.wiki_db.get_page(ctx.author, title)

				try:
					message = await target.send(page.content)
				except discord.Forbidden:
					raise commands.UserInputError("I can't send messages to that channel.")

				await self.db.bind(ctx.author, message, title, check_permissions=False)
		else:
			page = await self.db.bind(ctx.author, target, title)
			try:
				await target.edit(content=page.content)
			except discord.Forbidden:
				raise commands.UserInput("I can't edit that message.")

		await ctx.message.add_reaction(self.bot.config['success_emojis'][True])

	@commands.command()
	async def unbind(self, ctx, message: commands.MessageConverter):
		"""Delete a message binding."""
		await self.db.unbind(ctx.author, message)
		await ctx.message.add_reaction(self.bot.config['success_emojis'][True])

		await ctx.send('Would you like to delete the bound message as well? y/n')

		def check(message): return (
			message.channel == ctx.channel
			and message.author == ctx.author
			and message.content.lower() in ('y', 'n')
		)
		m = await self.bot.wait_for('message', check=check)
		if m.content.lower() == 'n':
			return

		try:
			await message.delete()
		except discord.Forbidden:
			await ctx.send(
				'Failed to delete the message. '
				'Please make sure I can access the channel and then get a moderator to delete the message for you.'
			)
		else:
			await m.add_reaction(self.bot.config['success_emojis'][True])

	@commands.command(aliases=['binds'])
	async def bindings(self, ctx, *, title: clean_content = None):
		"""List all the bindings for a page or this server.

		If a title is provided list the bindings for that page.
		Otherwise, list all bindings.
		"""
		if title is not None:
			paginator = await self.page_bindings(ctx, title)
		else:
			paginator = await self.guild_bindings(ctx)

		await paginator.begin()

	async def page_bindings(self, ctx, title):
		formatter = functools.partial(self.format_binding, ctx.guild.id)
		entries = [formatter(b) async for b in self.db.bound_messages(ctx.author, title)]

		if not entries:
			raise commands.UserInputError(f'No bindings found for “{title}”.')

		return pages.Pages(entries=entries, ctx=ctx, use_embed=True)

	async def guild_bindings(self, ctx):
		entries = []
		all_bindings = self.db.guild_bindings(ctx.author)
		formatter = functools.partial(self.format_binding, ctx.guild.id)
		async for page_id, bindings in utils.agroupby(all_bindings, key=operator.attrgetter('page_id')):
			entries.append((bindings[0].title, '\n'.join(map(formatter, bindings))))

		if not entries:
			raise commands.UserInputError('No bindings have been created in this server.')

		return pages.FieldPages(entries=entries, ctx=ctx)

	@staticmethod
	def format_binding(guild_id, b):
		return (
			f'[{b.message_id}]({utils.message_url(guild_id, b.channel_id, b.message_id)})'
			f' in <#{b.channel_id}>'
		)

def setup(bot):
	bot.add_cog(MessageBinding(bot))
