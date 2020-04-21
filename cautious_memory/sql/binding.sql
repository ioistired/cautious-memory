-- Copyright © 2020 lambda#0987
--
-- Cautious Memory is free software: you can redistribute it and/or modify
-- it under the terms of the GNU Affero General Public License as published
-- by the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- Cautious Memory is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU Affero General Public License for more details.
--
-- You should have received a copy of the GNU Affero General Public License
-- along with Cautious Memory.  If not, see <https://www.gnu.org/licenses/>.

-- :macro get_revision()
-- params: revision_id
SELECT revisions.content, pages.guild, page_id
FROM
	revisions
	INNER JOIN pages USING (page_id)
WHERE revision_id = $1
-- :endmacro

-- :macro bound_messages()
-- params: page_id
SELECT channel_id, message_id
FROM bound_messages
WHERE page_id = $1
-- :endmacro

-- :macro guild_bindings()
-- params: guild_id
SELECT title, page_id, channel_id, message_id
FROM
	bound_messages
	INNER JOIN pages USING (page_id)
WHERE pages.guild = $1
ORDER BY page_id
-- :endmacro

-- :macro bind()
-- params: channel_id, message_id, page_id
INSERT INTO bound_messages (channel_id, message_id, page_id)
VALUES ($1, $2, $3)
ON CONFLICT (message_id) DO UPDATE
	SET page_id = EXCLUDED.page_id
-- :endmacro

-- :macro get_bound_page()
-- params: message_id
SELECT pages.title, page_id
FROM
	bound_messages
	INNER JOIN pages USING (page_id)
WHERE message_id = $1
-- :endmacro

-- :macro unbind()
-- params: message_id
DELETE FROM bound_messages
WHERE message_id = $1
-- :endmacro

-- :macro delete_all_bindings()
-- params: page_id
DELETE FROM bound_messages
WHERE page_id = $1
-- :endmacro
