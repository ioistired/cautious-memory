-- Copyright © 2019 lambda#0987
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

-- :macro watch_page()
-- params: guild_id, user_id, title
INSERT INTO page_subscribers (page_id, user_id)
VALUES ((SELECT page_id FROM pages WHERE lower(title) = lower($3) AND guild_id = $1), $2)
ON CONFLICT (page_id, user_id) DO UPDATE
-- why this bogus upsert? so that it always says 1 row updated if the page exists
SET user_id = page_subscribers.user_id
-- :endmacro

-- :macro unwatch_page()
-- params: guild_id, user_id, title
DELETE FROM page_subscribers
WHERE (page_id, user_id) = ((SELECT page_id FROM pages WHERE lower(title) = lower($3) AND guild_id = $1), $2)
-- :endmacro

-- :macro watch_list()
-- params: guild_id, user_id
SELECT ps.page_id, title
FROM
	page_subscribers AS ps
	INNER JOIN pages AS p ON (ps.page_id = p.page_id AND p.guild_id = $1)
WHERE user_id = $2
ORDER BY lower(title)
-- :endmacro

-- :macro page_subscribers()
-- params: page_id
SELECT user_id
FROM page_subscribers
WHERE page_id = $1
-- :endmacro

-- :macro delete_page_subscribers()
-- params: page_id
DELETE FROM page_subscribers
WHERE page_id = $1
-- :endmacro

-- :macro get_revision_and_previous()
-- params: revision_id
-- TODO dedupe from wiki.get_page_revisions and wiki.get_individual_revisions
SELECT
	guild_id, page_id, revision_id, author_id, content, revised, pages.title AS current_title,
	pages.title,
	lag(revisions.title) OVER (
		PARTITION BY page_id
		ORDER BY revision_id
		ROWS 1 PRECEDING) AS prev_title
FROM
	pages
	INNER JOIN revisions USING (page_id)
	INNER JOIN contents USING (content_id)
WHERE
	page_id = (SELECT page_id FROM revisions WHERE revision_id = $1)
	AND revision_id <= $1
ORDER BY revision_id DESC
LIMIT 2
-- :endmacro
