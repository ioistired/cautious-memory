import re

import discord
from discord.ext import commands
from bot_bin.sql import connection

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
		async with self.bot.pool.acquire() as conn, conn.transaction():
			connection.set(conn)
			page = await self.wiki_db.get_page(ctx.author, title)
			await self.db.bind(message, page.page_id)
		await message.edit(content=page.content)
		await ctx.message.add_reaction(self.bot.config['success_emojis'][True])

def setup(bot):
	bot.add_cog(MessageBinding(bot))
