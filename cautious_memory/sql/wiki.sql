-- Copyright © 2019–2020 lambda#0987
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

-- :macro get_page()
-- params: guild_id, title
SELECT
	pages.page_id, created, content, pages.title,
	-- tfw condition repeated three times
	CASE WHEN aliases.title IS NOT NULL AND lower(aliases.title) = lower($2) THEN aliases.title ELSE NULL END AS alias,
	aliases.title IS NOT NULL AND lower(aliases.title) = lower($2) AS is_alias
FROM
	aliases
	RIGHT JOIN pages USING (page_id)
	INNER JOIN revisions ON pages.latest_revision_id = revisions.revision_id
	INNER JOIN contents USING (content_id)
WHERE
	pages.guild_id = $1
	AND
	(lower(aliases.title) = lower($2) OR lower(pages.title) = lower($2))
-- :endmacro

-- :macro get_page_basic()
-- params: guild_id, title
-- for when you don't need the revisions but still need to resolve aliases
SELECT
	pages.page_id, created, pages.title AS original_title,
	CASE WHEN aliases.title IS NOT NULL AND lower(aliases.title) = lower($2) THEN aliases.title ELSE NULL END AS alias
FROM
	aliases
	RIGHT JOIN pages USING (page_id)
WHERE
	pages.guild_id = $1
	AND
	(lower(aliases.title) = lower($2) OR lower(pages.title) = lower($2))
-- :endmacro

-- :macro get_page_no_alias()
-- params: guild_id, title
SELECT title AS target, NULL AS alias
FROM pages
WHERE
	guild_id = $1
	AND lower(pages.title) = lower($2)
-- :endmacro

-- :macro get_alias()
-- params: guild_id, title
SELECT pages.title AS target, aliases.title AS alias
FROM aliases INNER JOIN pages USING (page_id)
WHERE aliases.guild_id = $1 AND lower(aliases.title) = lower($2)
-- :endmacro

-- :macro delete_page()
-- params: guild_id, title
DELETE FROM pages
WHERE guild_id = $1 AND lower(title) = lower($2)
-- :endmacro

-- :macro delete_alias()
-- params: guild_id, title
WITH aliases_cte AS (
	SELECT aliases.title, page_id
	FROM aliases INNER JOIN pages USING (page_id)
	WHERE aliases.guild_id = $1 AND lower(aliases.title) = lower($2))
DELETE FROM aliases
WHERE EXISTS (
	SELECT 1 FROM aliases_cte
	WHERE (aliases.title, aliases.page_id) = (aliases_cte.title, aliases_cte.page_id))
-- :endmacro

-- :macro get_page_revisions()
-- params: guild_id, title
SELECT
	page_id, revision_id, author_id, content, revised, pages.title AS current_title, revisions.title,
	lag(revision_id) OVER (PARTITION BY page_id ORDER BY revision_id) IS NULL AS first
FROM
	pages
	INNER JOIN revisions USING (page_id)
	INNER JOIN contents USING (content_id)
WHERE
	guild_id = $1
	AND lower(pages.title) = lower($2)
ORDER BY revision_id DESC
-- :endmacro

-- :macro get_all_pages()
-- params: guild_id
-- TODO dedupe
SELECT * FROM (
	SELECT guild_id, title
	FROM pages
	UNION ALL
	SELECT guild_id, title
	FROM aliases) AS why_do_subqueries_in_FROM_need_an_alias_smh_my_head
WHERE guild_id = $1
ORDER BY lower(title) ASC
-- :endmacro

-- :macro get_recent_revisions()
-- params: guild_id, cutoff
SELECT
	pages.title AS current_title, revision_id, page_id, author_id, revised, revisions.title,
	lag(revision_id) OVER (PARTITION BY page_id ORDER BY revision_id) IS NULL AS first
FROM revisions INNER JOIN pages USING (page_id)
WHERE guild_id = $1 AND revised > $2
ORDER BY revised DESC
-- :endmacro

-- :macro search_pages()
-- params: guild_id, query
-- TODO dedupe
SELECT title
FROM (
	SELECT guild_id, title
	FROM pages
	UNION ALL
	SELECT guild_id, title
	FROM aliases) AS US_opposes_UN_loli_ban_uwu
WHERE
	guild_id = $1
	AND title % $2
ORDER BY similarity(title, $2) DESC
LIMIT 100
-- :endmacro

-- :macro get_individual_revisions()
-- params: guild_id, revision_ids
WITH all_revisions AS (
	-- TODO dedupe from get_page_revisions (use a stored proc?)
	SELECT
		page_id, revision_id, author_id, content, revised, pages.title AS current_title,
		revisions.title AS title,
		lag(revisions.title) OVER w AS prev_title,
		lag(revision_id) OVER w IS NULL AS first
	FROM
		pages
		INNER JOIN revisions USING (page_id)
		INNER JOIN contents USING (content_id)
	WHERE guild_id = $1
	WINDOW w AS (
		PARTITION BY page_id
		ORDER BY revision_id
		ROWS 1 PRECEDING))
-- using an outer query here prevents prematurely filtering the window funcs above to the selected revision IDs
SELECT *
FROM all_revisions
WHERE revision_id = ANY ($2)
ORDER BY revision_id ASC  -- usually this is used for diffs so we want oldest-newest
-- :endmacro

-- :macro create_page()
-- params: guild_id, title
INSERT INTO pages (guild_id, title)
VALUES ($1, $2)
RETURNING page_id
-- :endmacro

-- :macro get_page_id()
-- params: guild_id, title
SELECT page_id
FROM pages
WHERE
	guild_id = $1
	AND lower(title) = lower($2)
-- :endmacro

-- :macro get_content_id()
-- params: page_id
SELECT content_id
FROM
	pages
	INNER JOIN revisions ON pages.latest_revision_id = revisions.revision_id
WHERE pages.page_id = $1
-- :endmacro

-- :macro rename_page()
-- params: guild_id, old_title, new_title
UPDATE pages
SET title = $3
WHERE
	lower(title) = lower($2)
	AND guild_id = $1
RETURNING page_id
-- :endmacro

-- :macro alias_page()
-- params: guild_id, alias_title, target_title
WITH page AS (
	SELECT page_id, guild_id
	FROM pages
	WHERE guild_id = $1 AND lower(title) = LOWER($3))
INSERT INTO aliases (page_id, guild_id, title)
VALUES ((SELECT page_id FROM page), (SELECT guild_id FROM page), $2)
-- :endmacro

-- :macro log_page_rename()
-- params: page_id, author_id, content_id, new_title
INSERT INTO revisions (page_id, author_id, content_id, title)
VALUES ($1, $2, $3, $4)
-- :endmacro

-- :macro create_revision()
-- params: page_id, author_id, title, content_id
WITH revision AS (
	INSERT INTO revisions (page_id, author_id, title, content_id)
	VALUES ($1, $2, $3, $4)
	RETURNING revision_id)
UPDATE pages
SET latest_revision_id = (SELECT * FROM revision)
WHERE page_id = $1
-- :endmacro

-- :macro create_content()
-- params: content
INSERT INTO contents (content)
VALUES ($1)
RETURNING content_id
-- :endmacro

-- :macro create_first_revision()
-- for creating new pages
-- params: page_id, author_id, content_id, title
WITH revision AS (
	INSERT INTO revisions (page_id, author_id, content_id, title)
	VALUES ($1, $2, $3, $4)
	RETURNING revision_id)
UPDATE pages
SET latest_revision_id = (SELECT * FROM revision)
WHERE page_id = $1
-- :endmacro

-- :macro log_page_use()
-- params: guild_id, title
-- TODO dedupe this CTE
WITH page AS (
	SELECT page_id
	FROM aliases RIGHT JOIN pages USING (page_id)
	WHERE pages.guild_id = $1 AND (lower(aliases.title) = lower($2) OR lower(pages.title) = lower($2))
	LIMIT 1)
INSERT INTO page_usage_history (page_id)
VALUES ((SELECT * FROM page))
-- :endmacro

-- STATS

-- :macro page_uses()
-- params: guild_id, title, cutoff_date
WITH page AS (
	SELECT page_id
	FROM aliases RIGHT JOIN pages USING (page_id)
	WHERE pages.guild_id = $1 AND
	(lower(aliases.title) = lower($2) OR lower(pages.title) = lower($2))
	LIMIT 1)
SELECT count(*)
FROM page_usage_history
WHERE page_id = (SELECT * FROM page) AND time > $3
-- :endmacro

-- :macro page_revisions_count()
-- params: guild_id, title
WITH page AS (
	SELECT page_id
	FROM aliases RIGHT JOIN pages USING (page_id)
	WHERE pages.guild_id = $1 AND
	(lower(aliases.title) = lower($2) OR lower(pages.title) = lower($2))
	LIMIT 1)
SELECT count(*)
FROM revisions
WHERE page_id = (SELECT * FROM page)
-- :endmacro

-- :macro page_count()
-- params: guild_id
SELECT count(*)
FROM pages
WHERE guild_id = $1
-- :endmacro

-- :macro revisions_count()
-- params: guild_id
SELECT count(*)
FROM revisions INNER JOIN pages USING (page_id)
WHERE guild_id = $1
-- :endmacro

-- :macro total_page_uses()
-- params: guild_id, cutoff_date
SELECT count(*)
FROM pages LEFT JOIN page_usage_history USING (page_id)
WHERE guild_id = $1 AND time > $2
-- :endmacro

-- :macro top_pages()
-- params: guild_id, cutoff_date
SELECT title, count(time) AS count
FROM pages LEFT JOIN page_usage_history USING (page_id)
WHERE guild_id = $1 AND time > $2
GROUP BY page_id
ORDER BY count DESC
LIMIT 3
-- :endmacro

-- :macro top_editors()
-- params: guild_id, cutoff_date
-- TODO dedupe from top_pages
SELECT author_id AS id, count(revision_id) AS count
FROM revisions INNER JOIN pages USING (page_id)
WHERE guild_id = $1 AND revised > $2
GROUP BY author_id
ORDER BY count DESC
LIMIT 3
-- :endmacro

-- :macro top_page_editors()
-- params: guild_id, title, cutoff_date
WITH page_id AS (
	SELECT page_id
	FROM pages LEFT JOIN aliases USING (page_id)
	WHERE pages.guild_id = $1 AND (lower(aliases.title) = lower($2) OR lower(pages.title) = lower($2))
	LIMIT 1)
SELECT author_id AS id, count(*) AS count, count(*)::float8 / sum(count(*)) OVER () AS rank
FROM revisions
WHERE page_id = (SELECT * FROM page_id) AND revised > $3
GROUP BY author_id
ORDER BY rank DESC
LIMIT 3
-- :endmacro
