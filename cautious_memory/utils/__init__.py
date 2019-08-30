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

import contextlib
import inspect
import math
import re

import aiocontextvars
import asyncpg
import discord

def escape_code_blocks(s):
	return s.replace('`', '`\N{zero width non-joiner}')

def format_datetime(d) -> str:
	return d.strftime("%Y-%m-%d %I:%M:%S %p UTC")

def code_block(s, *, language=''):
	return f'```{language}\n{s}\n```'

def convert_emoji(s) -> discord.PartialEmoji:
	match = re.search(r'<?(a?):([A-Za-z0-9_]+):([0-9]{17,})>?', s)
	if match:
		return discord.PartialEmoji(animated=match[1], name=match[2], id=int(match[3]))
	return discord.PartialEmoji(animated=None, name=s, id=None)

def bytes_to_int(x):
	return int.from_bytes(x, byteorder='big')

def int_to_bytes(n):
	num_bytes = int(math.ceil(n.bit_length() / 8))
	return n.to_bytes(num_bytes, byteorder='big')

_connection = aiocontextvars.ContextVar('connection')
# make the interface a bit shorter
connection = lambda: _connection.get()
connection.set = _connection.set

def optional_connection(func):
	"""Decorator that acquires a connection for the decorated function if the contextvar is not set."""
	class pool:
		def __init__(self, pool):
			self.pool = pool
		async def __aenter__(self):
			try:
				# allow someone to call a decorated function twice within the same Task
				# the second time, a new connection will be acquired
				connection().is_closed()
			except (asyncpg.InterfaceError, LookupError):
				self.connection = conn = await self.pool.acquire()
				connection.set(conn)
				return conn
			else:
				return connection()
		async def __aexit__(self, *excinfo):
			with contextlib.suppress(AttributeError):
				await self.connection.close()

	if inspect.isasyncgenfunction(func):
		async def inner(self, *args, **kwargs):
			async with pool(self.bot.pool) as conn:
				# this does not handle two-way async gens, but i don't have any of those either
				async for x in func(self, *args, **kwargs):
					yield x
	else:
		async def inner(self, *args, **kwargs):
			async with pool(self.bot.pool) as conn:
				return await func(self, *args, **kwargs)

	return inner
