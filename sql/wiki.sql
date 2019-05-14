-- :name get_page
-- params: guild_id, title
SELECT *
FROM
	pages
	INNER JOIN revisions
		ON pages.latest_revision = revisions.revision_id
WHERE
	guild = $1
	AND lower(title) = lower($2)

-- :name delete_page
-- params: guild_id, title
DELETE FROM pages
WHERE guild = $1 AND lower(title) = $2

-- :name get_page_revisions
-- params: guild_id, title
SELECT *
FROM pages INNER JOIN revisions USING (page_id)
WHERE
	guild = $1
	AND lower(title) = lower($2)
ORDER BY revision_id DESC

-- :name get_all_pages
-- params: guild_id
SELECT *
FROM
	pages
	INNER JOIN revisions
		ON pages.latest_revision = revisions.revision_id
WHERE guild = $1
ORDER BY lower(title) ASC

-- :name get_recent_revisions
-- params: guild_id, cutoff
SELECT title, revision_id, page_id, author, revised
FROM revisions INNER JOIN pages USING (page_id)
WHERE guild = $1 AND revised > $2
ORDER BY revised DESC

-- :name search_pages
-- params: guild_id, query
SELECT *
FROM
	pages
	INNER JOIN revisions
		ON pages.latest_revision = revisions.revision_id
WHERE
	guild = $1
	AND title % $2
ORDER BY similarity(title, $2) DESC
LIMIT 100

-- :name get_individual_revisions
-- params: guild_id, revision_ids
SELECT *
FROM pages INNER JOIN revisions USING (page_id)
WHERE
	guild = $1
	AND revision_id = ANY ($2)
ORDER BY revision_id ASC  -- usually this is used for diffs so we want oldest-newest

-- :name create_page
-- params: guild, title
INSERT INTO pages (guild, title, latest_revision)
VALUES ($1, $2, 0)  -- revision = 0 until we have a revision ID
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

-- :name create_revision
-- params: page_id, author_id, content
WITH revision AS (
	INSERT INTO revisions (page_id, author, content)
	VALUES ($1, $2, $3)
	RETURNING revision_id)
UPDATE pages
SET latest_revision = (SELECT * FROM revision)
WHERE page_id = $1
