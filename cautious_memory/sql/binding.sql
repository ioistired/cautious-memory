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
