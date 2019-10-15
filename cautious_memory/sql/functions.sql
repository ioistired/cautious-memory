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

CREATE FUNCTION coalesce_agg_statefunc(state anyelement, value anyelement) RETURNS anyelement AS $$
	SELECT coalesce(value, state); $$
LANGUAGE SQL;

CREATE AGGREGATE coalesce_agg(anyelement) (
	SFUNC = coalesce_agg_statefunc,
	STYPE = anyelement);

CREATE FUNCTION permissions_for(
	p_page_id pages.page_id%TYPE,
	p_role_ids BIGINT[],
	p_default_permissions role_permissions.permissions%TYPE
) RETURNS role_permissions.permissions%TYPE AS $$
	DECLARE
		everyone_role BIGINT := p_role_ids[1];
		everyone_perms role_permissions.permissions%TYPE := (
			SELECT permissions
			FROM role_permissions
			WHERE entity = everyone_role);
		computed role_permissions.permissions%TYPE;
	BEGIN
		WITH all_permissions AS (
				SELECT
					permissions,
					0 AS allow,
					0 AS deny
				FROM role_permissions
				WHERE entity = ANY ($2)
			UNION ALL
				SELECT
					0 AS permissions,
					allow,
					deny
				FROM page_permissions
				WHERE entity = ANY ($2) OR page_id = $1)
		SELECT bit_or(permissions) | bit_or(allow) | (coalesce(everyone_perms, p_default_permissions)) & ~bit_or(deny)
		INTO computed
		FROM all_permissions;
		RETURN COALESCE(computed, p_default_permissions); END; $$ LANGUAGE plpgsql;
