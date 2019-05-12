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

import discord
from discord.ext import commands

from cogs.db import Permissions

class WikiPermissions(commands.Cog, name='Wiki Permissions'):
	"""Commands that let you manage the permissions on pages.

	Each role on your server can have certain permissions associated with it that
	are related to this bot. The permissions are as follows:
	• View pages
	• Edit pages
	• Create pages
	• Rename pages
	• Delete pages
	• Manage permissions

	Each page can also have "permission overwrites", which override the permissions granted by a role.
	For example, you could have a role called "Wiki Mod" have view, edit, rename and deletion permissions,
	except on an important page where you could deny the deletion permission for them.

	Each member's permission on each page is calculated as follows:
	1.) All of the permissions for all of their roles are combined.
	2.) All of the "allowed" permission overwrites for that page are added to that member's permissions,
	and all of the "denied" permission overwrites for that page are removed from them.

	By default, nobody can edit the wiki permissions of other roles except for server administrators.
	This is to provide a higher level of security.
	If you want to allow people with a certain role to edit wiki permissions of other roles,
	grant the role the "Manage Permissions" permission.

	For high security, it is recommended to create two roles.
	One of them would serve as the "Wiki Admin", and it would get the "Manage Roles" permission so that it can grant
	"Wiki Mod" to others.
	"Wiki Admin" would get no wiki permissions.
	"Wiki Mod" would get no special Discord permissions and all of the wiki permissions.
	"""
	def __init__(self, bot):
		self.bot = bot
		self.db = self.bot.get_cog('Database')

def setup(bot):
	bot.add_cog(WikiPermissions(bot))
