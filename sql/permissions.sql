-- :name permissions_for
-- params: guild_id, title, role_ids, Permissions.default.value
WITH
	page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2)),
	everyone_perms AS (SELECT permissions FROM role_permissions WHERE role = $1)
SELECT
	coalesce(bit_or(permissions), $4)
	& ~coalesce(bit_or(deny), 0)
	| coalesce(bit_or(allow), 0)
	| coalesce((SELECT * FROM everyone_perms), $4)
FROM
	role_permissions
	FULL OUTER JOIN page_permissions ON (role = entity)
WHERE
	entity = ANY ($3)
	OR role = ANY ($3)
	AND (
		page_id = (SELECT * FROM page_id)
		OR page_id IS NULL)  -- in case there's no page permissions for some role

-- :name member_permissions
-- params: role_ids, guild_id, Permissions.default.value
WITH everyone_perms AS (SELECT permissions FROM role_permissions WHERE role = $2)
SELECT bit_or(permissions) | coalesce((SELECT * FROM everyone_perms), $3)
FROM role_permissions
WHERE role = ANY ($1)

-- :name highest_manage_permissions_role
-- params: role_ids, Permissions.manage_permissions.value
SELECT role
FROM role_permissions
WHERE role = ANY ($1) AND role & $2 != 0

-- :name get_role_permissions
-- params: role_id
SELECT permissions
FROM role_permissions
WHERE role = $1

-- :name set_role_permissions
-- params: role_id, perms
INSERT INTO role_permissions(role, permissions)
VALUES ($1, $2)
ON CONFLICT (role) DO UPDATE SET
	permissions = EXCLUDED.permissions

-- :name allow_role_permissions
-- params: role_id, new_perms.value, new_perms | Permissions.default
INSERT INTO role_permissions(role, permissions)
VALUES ($1, $3)
ON CONFLICT (role) DO UPDATE SET
	permissions = role_permissions.permissions | $2
RETURNING permissions

-- :name deny_role_permissions
-- params: role_id, perms
UPDATE role_permissions
SET permissions = role_permissions.permissions & ~$2::INTEGER
WHERE role = $1
RETURNING permissions

-- :name get_page_overwrites
-- params: guild_id, title
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
SELECT allow, deny
FROM page_permissions
WHERE page_id = (SELECT * FROM page_id)

-- :name set_page_overwrites
-- params: guild_id, title, entity_id, allowed_perms, denied_perms
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
INSERT INTO page_permissions (page_id, entity, allow, deny)
VALUES ((SELECT * FROM page_id), $3, $4, $5)
ON CONFLICT (page_id, entity) DO UPDATE SET
	allow = EXCLUDED.allow,
	deny = EXCLUDED.deny

-- :name unset_page_overwrites
-- guild_id, title, entity_id
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
DELETE FROM page_permissions
WHERE
	page_id = (SELECT * FROM page_id)
	AND entity = $3

-- :name add_page_permissions
-- params: guild_id, title, entity_id, new_allow_perms, new_deny_perms
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
INSERT INTO page_permissions (page_id, entity, allow, deny)
VALUES ((SELECT * FROM page_id), $3, $4, $5)
ON CONFLICT (page_id, entity) DO UPDATE SET
	allow = (page_permissions.allow | EXCLUDED.allow) & ~EXCLUDED.deny,
	deny = (page_permissions.deny | EXCLUDED.deny) & ~EXCLUDED.allow
RETURNING allow, deny

-- :name unset_page_permissions
-- params: guild_id, title, entity_id, perms
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
UPDATE page_permissions SET
	allow = allow & ~$4::INTEGER,
	deny = deny & ~$4::INTEGER
WHERE page_id = (SELECT * FROM page_id) AND entity = $3
RETURNING allow, deny
