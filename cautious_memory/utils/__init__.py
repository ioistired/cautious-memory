# Copyright © 2019–2020 lambda#0987
#
# Cautious Memory is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Cautious Memory is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Cautious Memory.  If not, see <https://www.gnu.org/licenses/>.

import math
import re
from inspect import isawaitable as _isawaitable
from typing import (
	Union,
	Callable,
	AsyncIterable,
	AsyncIterator,
	Awaitable,
	TypeVar,
	Tuple,
	List,
	Any,
	Optional,
	overload,
)

import braceexpand
import discord

from . import converter

R = TypeVar('R')
T = TypeVar('T')
KeyFunction = Union[Callable[[T], R], Callable[[T], Awaitable[R]]]

def escape_code_blocks(s):
	return s.replace('```', '``\N{zero width non-joiner}`')

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

def expand(text):
	return list(braceexpand.braceexpand(text.replace('\n', '').replace('\t', '')))

def message_url(guild_id, channel_id, message_id):
	return f'https://discordapp.com/channels/{guild_id}/{channel_id}/{message_id}'

class AttrDict:
	def __init__(self, *args, **kwargs):
		vars(self).update(dict(*args, **kwargs))

def round_down(n, *, multiple):
	"""round n down to the nearest multiple of multiple"""
	return n // multiple * multiple

async def maybe_await(x):
	if _isawaitable(x):
		return await x
	else:
		return x

async def fetch_member(guild, user_id):
	member = guild.get_member(user_id)
	if member is not None:
		return member
	member = await guild.fetch_member(user_id)
	guild._add_member(member)
	return member

# agroupby modified from groupby in aioitertools @ 14f5faa7edb614de1287da6bc9c49226e14cfc1d
# Copyright (c) 2018 John Reese
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

@overload
def agroupby(it: AsyncIterable[T]) -> AsyncIterator[Tuple[T, List[T]]]:
	pass

@overload
def agroupby(
	it: AsyncIterable[T], key: KeyFunction[T, R]
) -> AsyncIterator[Tuple[R, List[T]]]:
	pass

async def agroupby(
	it: AsyncIterable[T], key: Optional[KeyFunction[T, R]] = None
) -> AsyncIterator[Tuple[Any, List[T]]]:
	"""
	Yield consecutive keys and groupings from the given iterable.
	Items will be grouped based on the key function, which defaults to
	the identity of each item.	Accepts both standard functions and
	coroutines for the key function.  Suggest sorting by the key
	function before using groupby.
	Example:
		data = ["A", "a", "b", "c", "C", "c"]
		async for key, group in groupby(data, key=str.lower):
			key	 # "a", "b", "c"
			group  # ["A", "a"], ["b"], ["c", "C", "c"]
	"""
	if key is None:
		key = lambda x: x

	grouping: List[T] = []

	try:
		item = await it.__anext__()
	except StopAsyncIteration:
		return

	grouping = [item]

	j = await maybe_await(key(item))
	async for item in it:
		k = await maybe_await(key(item))
		if k != j:
			yield j, grouping
			grouping = [item]
		else:
			grouping.append(item)
		j = k

	yield j, grouping
