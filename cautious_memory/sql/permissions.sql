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

-- :macro permissions_for()
-- params: page_id, member_id, role_ids, guild_id, Permissions.default.value
-- role_ids must include member_id for member specific page overwrites, and the first element must be the guild ID
SELECT * FROM permissions_for($1, $2, $3, $4, $5)
-- :endmacro

-- :macro member_permissions()
-- params: role_ids, Permissions.default.value
-- role_ids must have the guild ID as the first element
WITH everyone_perms AS (SELECT permissions FROM role_permissions WHERE entity = ($1::BIGINT[])[1])
SELECT coalesce(bit_or(permissions), 0) | coalesce((SELECT * FROM everyone_perms),  $2)
FROM role_permissions
WHERE entity = ANY ($1)
-- :endmacro

-- :macro manage_permissions_roles()
-- params: role_ids, Permissions.manage_permissions.value
-- role_ids must include guild_id in case the default role has manage permissions
SELECT entity
FROM role_permissions
WHERE entity = ANY ($1) AND permissions & $2 != 0
-- :endmacro

-- :macro get_role_permissions()
-- params: role_id
SELECT permissions
FROM role_permissions
WHERE entity = $1
-- :endmacro

-- :macro set_role_permissions()
-- params: role_id, perms
INSERT INTO role_permissions(entity, permissions)
VALUES ($1, $2)
ON CONFLICT (entity) DO UPDATE SET
	permissions = EXCLUDED.permissions
-- :endmacro

-- :macro delete_role_permissions()
-- params: role_id
DELETE FROM role_permissions
WHERE entity = $1
-- :endmacro

-- :macro set_default_permissions()
-- params: guild_id, Permissions.default.value
INSERT INTO role_permissions(entity, permissions)
VALUES ($1, $2)
ON CONFLICT DO NOTHING
-- :endmacro

-- :macro allow_role_permissions()
-- params: role_id, new_perms
INSERT INTO role_permissions(entity, permissions)
VALUES ($1, $2)
ON CONFLICT (entity) DO UPDATE SET
	permissions = role_permissions.permissions | $2
RETURNING permissions
-- :endmacro

-- :macro deny_role_permissions()
-- params: role_id, perms
UPDATE role_permissions
SET permissions = role_permissions.permissions & ~$2::INTEGER
WHERE entity = $1
RETURNING permissions
-- :endmacro

-- :macro get_page_overwrites()
-- params: page_id
SELECT entity, allow, deny
FROM page_permissions
WHERE page_id = $1
-- :endmacro

-- :macro get_page_overwrites_for()
-- params: page_id, entity_id
SELECT allow, deny
FROM page_permissions
WHERE page_id = $1 AND entity = $2
-- :endmacro

-- :macro set_page_overwrites()
-- params: guild_id, title, entity_id, allowed_perms, denied_perms
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
INSERT INTO page_permissions (page_id, entity, allow, deny)
VALUES ((SELECT * FROM page_id), $3, $4, $5)
ON CONFLICT (page_id, entity) DO UPDATE SET
	allow = EXCLUDED.allow,
	deny = EXCLUDED.deny
-- :endmacro

-- :macro unset_page_overwrites()
-- params: guild_id, title, entity_id
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
DELETE FROM page_permissions
WHERE
	page_id = (SELECT * FROM page_id)
	AND entity = $3
-- :endmacro

-- :macro add_page_permissions()
-- params: guild_id, title, entity_id, new_allow_perms, new_deny_perms
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
INSERT INTO page_permissions (page_id, entity, allow, deny)
VALUES ((SELECT * FROM page_id), $3, $4, $5)
ON CONFLICT (page_id, entity) DO UPDATE SET
	allow = (page_permissions.allow | EXCLUDED.allow) & ~EXCLUDED.deny,
	deny = (page_permissions.deny | EXCLUDED.deny) & ~EXCLUDED.allow
RETURNING allow, deny
-- :endmacro

-- :macro unset_page_permissions()
-- params: guild_id, title, entity_id, perms
WITH page_id AS (SELECT page_id FROM pages WHERE guild = $1 AND lower(title) = lower($2))
UPDATE page_permissions SET
	allow = allow & ~$4::INTEGER,
	deny = deny & ~$4::INTEGER
WHERE page_id = (SELECT * FROM page_id) AND entity = $3
RETURNING allow, deny
-- :endmacro

-- :macro get_page_id()
-- params: guild_id, title
SELECT page_id
FROM aliases RIGHT JOIN pages USING (page_id)
WHERE pages.guild = $1 AND (lower(aliases.title) = lower($2) OR lower(pages.title) = lower($2))
-- :endmacro
