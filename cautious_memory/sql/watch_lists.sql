-- Copyright © 2019 lambda#0987
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU Affero General Public License as published
-- by the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU Affero General Public License for more details.
--
-- You should have received a copy of the GNU Affero General Public License
-- along with this program.  If not, see <https://www.gnu.org/licenses/>.

-- :name watch_page
-- params: guild_id, user_id, title
INSERT INTO page_subscribers (page_id, user_id)
VALUES ((SELECT page_id FROM pages WHERE lower(title) = lower($3) AND guild = $1), $2)
ON CONFLICT (page_id, user_id) DO UPDATE
-- why this bogus upsert? so that it only says 0 rows updated if the page doesn't exist
SET user_id = page_subscribers.user_id

-- :name unwatch_page
-- params: guild_id, user_id, title
DELETE FROM page_subscribers
WHERE (page_id, user_id) = ((SELECT page_id FROM pages WHERE lower(title) = lower($3) AND guild = $1), $2)

-- :name watch_list
-- params: guild_id, user_id
SELECT ps.page_id, title
FROM
	page_subscribers AS ps
	INNER JOIN pages AS p ON (ps.page_id = p.page_id AND p.guild = $1)
WHERE user_id = $2
ORDER BY lower(title)

-- :name page_subscribers
-- params: page_id
SELECT user_id
FROM page_subscribers
WHERE page_id = $1

-- :name get_revision_and_previous
-- params: revision_id
-- TODO dedupe from wiki.get_page_revisions and wiki.get_individual_revisions
SELECT
	guild, page_id, revision_id, author, content, revised, pages.title AS current_title,
	coalesce_agg(new_title) OVER (PARTITION BY page_id ORDER BY revision_id) AS title,
	coalesce_agg(new_title) OVER (
		PARTITION BY page_id
		ORDER BY revision_id
		ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS old_title
FROM pages INNER JOIN revisions USING (page_id)
WHERE
	page_id = (SELECT page_id FROM revisions WHERE revision_id = $1)
	AND revision_id <= $1
ORDER BY revision_id DESC
LIMIT 2
