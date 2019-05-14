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
import inflect
inflect = inflect.engine()

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
	def __init__(self, name):
		self.name = name
		super().__init__(f'A page called {name} does not exist.')

class MissingPermissionsError(PageError):
	"""Raised when the user tries to perform an action they do not have permissions for."""
	def __init__(self, permissions_needed):
		joined = inflect.join([permission.name for permission in permissions_needed])
		super().__init__(f'Missing permissions to perform this action. You need these permissions: {joined}.')
