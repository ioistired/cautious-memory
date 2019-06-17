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

import base64
import contextlib
import os.path
import secrets

import discord
from discord.ext import commands

from .. import SQL_DIR
from .. import utils

class API(commands.Cog):
	TOKEN_DELIMITER = b';'

	def __init__(self, bot):
		self.bot = bot
		with open(os.path.join(SQL_DIR, 'api.sql')) as f:
			self.queries = utils.load_sql(f)

	@staticmethod
	def any_parent_command_is(command, parent_command):
		while command is not None:
			if command is parent_command:
				return True
			command = command.parent
		return False

	async def cog_check(self, ctx):
		# we're doing this as a local check because
		# A) if invoke_without_command=True, checks don't propagate to subcommands
		# B) even if invoke_without_command=False, checks still don't propagate to sub-sub-commands
		# AFAIK
		if self.any_parent_command_is(ctx.command, self.api_token):
			# bots may not have API tokens
			return not ctx.author.bot
		return True

	@commands.group(name='api-token', aliases=['api'], hidden=True, invoke_without_command=True, ignore_extra=False)
	async def api_token(self, ctx):
		"""Commands related to the Cautious Memory API.

		This command on its own will tell you a bit about the API. All other functionality is in subcommands.
		"""
		if ctx.invoked_subcommand is None:
			await ctx.send(
				'I have a RESTful API available. The docs for it are located at '
				f'{self.bot.config["api"]["docs_url"]}.')

	@api_token.command(name='list')
	async def token_list(self, ctx):
		"""Lists your API applications."""
		out = []
		for id, name in await self.list_apps(ctx.author.id):
			out.append(f'{id}) “{name}”')

		if not out:
			await ctx.send(f"You don't have any apps yet. Use the __{ctx.prefix}api-token new__ command to make one.")
			return

		await ctx.send('\n'.join(out))

	@api_token.command(name='new')
	async def token_new(self, ctx, *, app_name: commands.clean_content):
		"""Creates a new API application and DMs you the token."""
		token = await self.new_token(ctx.author.id, app_name)
		await self.send_token(ctx, token, app_name, new=True)

	@api_token.command(name='delete', aliases=['rm'])
	async def token_delete(self, ctx, app_id: int):
		"""Deletes an API application."""
		await self.delete_app(ctx.author.id, app_id)
		await ctx.message.add_reaction(self.bot.config['success_emoji'])

	@api_token.command(name='show', aliases=['get'])
	async def token_show(self, ctx, *, app_id: int):
		"""Sends you your token for a particular API application."""
		app_name, token = await self.existing_token(ctx.author.id, app_id)
		if token is None:
			await ctx.send('Error: no such app found.')
			return

		print(token)
		await self.send_token(ctx, token, app_name)

	async def send_token(self, ctx, token, app_name, *, new=False):
		message = (
			(f'Your new API token for “{app_name}” is:\n' if new else f'Your API token for “{app_name}” is:\n')
			+ f'`{token.decode()}`\n'
			+ 'Do **not** share it with anyone!')

		try:
			await ctx.author.send(message)
		except discord.Forbidden:
			await ctx.send('Error: I could not send you your token via DMs.')
		else:
			with contextlib.suppress(discord.HTTPException):
				await ctx.message.add_reaction('📬')

	async def list_apps(self, user_id):
		return await self.bot.pool.fetch(self.queries.list_apps, user_id)

	async def existing_token(self, user_id, app_id):
		row = await self.bot.pool.fetchrow(self.queries.existing_token, user_id, app_id)
		if row is None:
			return None
		app_name, secret = row
		return app_name, self.encode_token(user_id, app_id, secret)

	async def new_token(self, user_id, app_name):
		secret = secrets.token_bytes()
		app_id = await self.bot.pool.fetchval(self.queries.new_token, user_id, app_name, secret)
		return self.encode_token(user_id, app_id, secret)

	async def regenerate_token(self, user_id, app_id):
		await self.delete_app(user_id, app_id)
		return await self.new_token(user_id)

	async def validate_token(self, token, user_id=None, app_id=None):
		try:
			token_user_id, token_app_id, secret = self.decode_token(token)
		except:
			secrets.compare_digest(token, token)
			return False

		if user_id is None:
			user_id = token_user_id
		if app_id is None:
			app_id = token_app_id

		db_secret = await self.bot.pool.fetchval(self.queries.get_secret, user_id, app_id)
		if db_secret is None:
			secrets.compare_digest(token, token)
			return False

		db_token = self.encode_token(user_id, db_secret)
		return (user_id, app_id) if secrets.compare_digest(token, db_token) else (None, None)

	async def delete_user_account(self, user_id):
		await self.bot.pool.execute(self.queries.delete_user_account, user_id)

	async def delete_app(self, user_id, app_id):
		await self.bot.pool.execute(self.queries.delete_app, user_id, app_id)

	def generate_token(self, user_id, app_id):
		secret = base64.b64encode(secrets.token_bytes())
		return self.encode_token(user_id, app_id, secret)

	def encode_token(self, user_id, app_id, secret: bytes):
		user_id, app_id = map(utils.int_to_bytes, [user_id, app_id])
		return self.TOKEN_DELIMITER.join(map(base64.b64encode, [user_id, app_id, secret]))

	def decode_token(self, token):
		user_id, app_id, secret = map(base64.b64decode, token.split(self.TOKEN_DELIMITER))
		user_id, app_id = map(utils.bytes_to_int, [user_id, app_id])

		return user_id, app_id, secret

def setup(bot):
	if bot.config.get('api'):
		bot.add_cog(API(bot))
