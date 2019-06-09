-- :name get_page
-- params: guild_id, title
SELECT pages.page_id, created, content, coalesce(aliases.title, pages.title) AS title, aliased IS NOT NULL AS is_alias
FROM
	aliases
	RIGHT JOIN pages USING (page_id)
	INNER JOIN revisions ON pages.latest_revision = revisions.revision_id
WHERE
	(aliases.guild = $1 OR pages.guild = $1)
	AND
	(lower(aliases.title) = lower($2) OR lower(pages.title) = lower($2))

-- :name get_page_no_alias
-- params: guild_id, title
SELECT title AS target, NULL AS alias
FROM pages
WHERE
	guild = $1
	AND lower(pages.title) = lower($2)

-- :name get_alias
-- params: guild_id, title
SELECT pages.title AS target, aliases.title AS alias
FROM aliases INNER JOIN pages USING (page_id)
WHERE aliases.guild = $1 AND lower(aliases.title) = lower($2)

-- :name delete_page
-- params: guild_id, title
DELETE FROM pages
WHERE guild = $1 AND lower(title) = $2

-- :name delete_alias
-- params: guild_id, title
WITH aliases_cte AS (
	SELECT aliases.title, page_id
	FROM aliases INNER JOIN pages USING (page_id)
	WHERE aliases.guild = $1 AND lower(aliases.title) = lower($2))
DELETE FROM aliases
WHERE EXISTS (
	SELECT 1 FROM aliases_cte
	WHERE (aliases.title, aliases.page_id) = (aliases_cte.title, aliases_cte.page_id))

-- :name get_page_revisions
-- params: guild_id, title
SELECT
	page_id, revision_id, author, content, revised, pages.title AS current_title,
	coalesce_agg(new_title) OVER (PARTITION BY page_id ORDER BY revision_id ASC) AS title
FROM pages INNER JOIN revisions USING (page_id)
WHERE
	guild = $1
	AND lower(title) = lower($2)
ORDER BY revision_id DESC

-- :name get_all_pages
-- params: guild_id
SELECT * FROM (
	SELECT guild, title
	FROM pages
	UNION ALL
	SELECT guild, title
	FROM aliases ) AS why_do_subqueries_in_FROM_need_an_alias_smh_my_head
WHERE guild = $1
ORDER BY lower(title) ASC

-- :name get_recent_revisions
-- params: guild_id, cutoff
SELECT
	title AS current_title, revision_id, page_id, author, revised,
	coalesce_agg(new_title) OVER (PARTITION BY page_id ORDER BY revision_id ASC) as title
FROM revisions INNER JOIN pages USING (page_id)
WHERE guild = $1 AND revised > $2
ORDER BY revised DESC

-- :name search_pages
-- params: guild_id, query
SELECT title
FROM (
	SELECT guild, title
	FROM pages
	UNION ALL
	SELECT guild, title
	FROM aliases) AS US_opposes_UN_loli_ban_uwu
WHERE
	guild = $1
	AND title % $2
ORDER BY similarity(title, $2) DESC
LIMIT 100

-- :name get_individual_revisions
-- params: guild_id, revision_ids
WITH all_revisions AS (
	-- TODO dedupe from get_page_revisions (use a stored proc?)
	SELECT
		page_id, revision_id, author, content, revised, pages.title AS current_title,
		coalesce_agg(new_title) OVER (PARTITION BY page_id ORDER BY revision_id ASC) AS title
	FROM pages INNER JOIN revisions USING (page_id)
	WHERE
		guild = $1
		-- semi-join because the user doesn't specify a title, but we still want to filter by page
		AND EXISTS (
			SELECT 1 FROM revisions r
			WHERE r.page_id = page_id))
-- using an outer query here prevents prematurely filtering the window funcs above to the selected revision IDs
SELECT *
FROM all_revisions
WHERE revision_id = ANY ($2)
ORDER BY revision_id ASC  -- usually this is used for diffs so we want oldest-newest

-- :name create_page
-- params: guild, title
INSERT INTO pages (guild, title)
VALUES ($1, $2)
RETURNING page_id

-- :name get_page_id
-- params: title
SELECT page_id
FROM pages
WHERE
	guild = $1
	AND lower(title) = lower($2)

-- :name rename_page
-- params: guild_id, old_title, new_title
UPDATE pages
SET title = $3
WHERE
	lower(title) = lower($2)
	AND guild = $1
RETURNING page_id

-- :name alias_page
-- params: guild_id, alias_title, target_title
WITH page AS (
	SELECT page_id, guild
	FROM pages
	WHERE
		guild = $1
		AND lower(title) = LOWER($3))
INSERT INTO aliases (page_id, guild, title)
VALUES ((SELECT page_id FROM page), (SELECT guild FROM page), $2)

-- :name log_page_rename
-- params: page_id, author_id, new_title
INSERT INTO revisions (page_id, author, new_title)
VALUES ($1, $2, $3)

-- :name create_revision
-- params: page_id, author_id, content
WITH revision AS (
	INSERT INTO revisions (page_id, author, content)
	VALUES ($1, $2, $3)
	RETURNING revision_id)
UPDATE pages
SET latest_revision = (SELECT * FROM revision)
WHERE page_id = $1

-- :name create_first_revision (for creating new pages)
-- params: page_id, author_id, content, title
WITH revision AS (
	INSERT INTO revisions (page_id, author, content, new_title)
	VALUES ($1, $2, $3, $4)
	RETURNING revision_id)
UPDATE pages
SET latest_revision = (SELECT * FROM revision)
WHERE page_id = $1

-- :name log_page_use
-- params: guild_id, title
WITH page AS (
	SELECT page_id
	FROM aliases RIGHT JOIN pages USING (page_id)
	WHERE guild_id = $1 AND title = $2)
INSERT INTO page_usage_history (page_id)
VALUES ((SELECT * FROM page))
