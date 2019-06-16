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

import textwrap

from discord.ext import commands
import discord.utils

class Meta(commands.Cog):
	"""Commands pertaining to the bot itself."""

	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	async def about(self, ctx):
		"""Tells you about the bot."""
		await ctx.send(textwrap.dedent(f"""
			Hello! I'm a bot created by lambda#0987 to bring wikis to your server.
			Wiki pages are like tags from other bots, but anyone can edit them, and nobody owns them.
			You can find out more about me by doing "{ctx.prefix}help", and you can find my source code by doing
			"{ctx.prefix}source".
		"""))

	@commands.command()
	async def support(self, ctx):
		"""Gives you a link to the support server, where you can get help with the bot."""
		await ctx.send('https://discord.gg/' + self.bot.config['support_server_invite_code'])

	@commands.command()
	async def source(self, ctx):
		"""Links you to my source code."""
		await ctx.send(self.bot.config['repo'])

	@commands.command()
	async def invite(self, ctx):
		"""Sends you a link to invite me to your server."""
		await ctx.send('<' + discord.utils.oauth_url(self.bot.user.id) + '>')

def setup(bot):
	bot.add_cog(Meta(bot))
	if not bot.config.get('support_server_invite_code'):
		bot.remove_command('support')
