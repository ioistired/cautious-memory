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
