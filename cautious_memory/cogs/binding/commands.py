import re

import discord
from discord.ext import commands
from bot_bin.sql import connection

from ..wiki.db import Permissions

CHANNEL_MENTION_RE = re.compile('<#(\d+)>', re.ASCII)
clean_content = commands.clean_content(use_nicknames=False)

class OwnMessageOrNewMessage(commands.Converter):
	async def convert(self, ctx, arg):
		m = CHANNEL_MENTION_RE.search(arg)
		if m:
			ch = ctx.guild.get_channel(int(m[1]))
			if ch is None:
				raise commands.UserInputError('Channel not found.')

			try:
				return await ch.send('\u200b')
			except discord.Forbidden:
				raise commands.UserInputError(f"I can't send messages to {ch.mention}.")

		m = await commands.MessageConverter().convert(ctx, arg)
		if m.author != ctx.bot.user:
			raise commands.UserInputError('A message sent by the bot is required.')
		return m

class MessageBinding(commands.Cog, name='Message Binding'):
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
		"""
		async with self.bot.pool.acquire() as conn, conn.transaction():
			connection.set(conn)
			page = await self.wiki_db.get_page(ctx.author, title)
			await self.db.bind(message, page.page_id)
		await message.edit(content=page.content)
		await ctx.message.add_reaction(self.bot.config['success_emojis'][True])

	@commands.command()
	async def unbind(self, ctx, message: commands.MessageConverter):
		"""Delete a message binding."""
		async with self.bot.pool.acquire() as conn, conn.transaction():
			connection.set(conn)
			page = await self.db.get_bound_page(message)
			await self.wiki_db.check_permissions(ctx.author, Permissions.delete, page.title)
			await self.db.unbind(message)

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

def setup(bot):
	bot.add_cog(MessageBinding(bot))
