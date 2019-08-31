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

from discord.ext import commands

clean_content = commands.clean_content(use_nicknames=False)

class WatchLists(commands.Cog, name='Watch Lists'):
	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.cogs['WatchListsDatabase']

	@commands.command()
	async def watch(self, ctx, *, title: clean_content):
		"""Adds a page to your watch list."""
		if await self.db.watch_page(ctx.author, title):
			await ctx.message.add_reaction(self.bot.config['success_emojis'][True])
		else:
			await ctx.send('Either that page does not exist or you are already watching it.')

def setup(bot):
	bot.add_cog(WatchLists(bot))
