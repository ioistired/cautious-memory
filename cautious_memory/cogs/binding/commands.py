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

class OwnMessageOrNewMessage(commands.Converter):
	async def convert(self, ctx, arg):
		m = CHANNEL_MENTION_RE.search(arg)
		if m:
			ch = ctx.guild.get_channel(int(m[1]))
			if ch is None:
				raise commands.UserInputError('Channel not found.')

			self._check_permissions(ctx, ch)

			try:
				return await ch.send('\N{zero width space}')
			except discord.Forbidden:
				raise commands.UserInputError(f"I can't send messages to {ch.mention}.")

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
	async def bind(self, ctx, message: OwnMessageOrNewMessage, *, title: clean_content):
		"""Bind a message to a page. Whenever the page is edited, the message will be edited too.

		You can supply either a message that the bot has sent, or a #channel mention.
		Messages can be provided by ID, channel_id-message_id (obtained via shift clicking on "Copy ID"),
		or by a link to the message.

		If a binding already exists for the given message, it will be updated.
		"""
		page = await self.db.bind(ctx.author, message, title)
		await message.edit(content=page.content)
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
