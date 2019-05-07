# encoding: utf-8

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

from discord.ext.commands import CommandError, UserInputError

class CautiousMemoryError(CommandError):
	"""Generic error with the bot. This can be used to catch all bot errors."""
	pass

class PageError(CautiousMemoryError, UserInputError):
	"""Abstract error while dealing with a page."""
	pass

class PageExistsError(PageError):
	def __init__(self):
		super().__init__(f'A page with that name already exists.')

class PageNotFoundError(PageError):
	def __init__(self, name=None):
		self.name = name
		if name is None:
			super().__init__('That page does not exist.')
		else:
			super().__init__(f'A page called {name} does not exist.')

class PermissionDeniedError(PageError):
	def __init__(self, required_permissions):
		super().__init__(
			"You don't have the needed permissions to perform this action. "
			f"{required_permissions.name.title()} permissions needed!")
