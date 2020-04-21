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

CREATE FUNCTION coalesce_agg_statefunc(state anyelement, value anyelement) RETURNS anyelement AS $$
	SELECT coalesce(value, state); $$
LANGUAGE SQL;

CREATE AGGREGATE coalesce_agg(anyelement) (
	SFUNC = coalesce_agg_statefunc,
	STYPE = anyelement);

CREATE FUNCTION permissions_for(
	p_page_id pages.page_id%TYPE,
	p_member_id BIGINT,
	p_role_ids BIGINT[],
	p_guild_id BIGINT,
	p_default_permissions role_permissions.permissions%TYPE
) RETURNS role_permissions.permissions%TYPE AS $$
	DECLARE
		v_everyone_perms role_permissions.permissions%TYPE := (
			SELECT permissions
			FROM role_permissions
			WHERE entity = p_guild_id);
		v_base role_permissions.permissions%TYPE;
		v_allow role_permissions.permissions%TYPE;
		v_deny role_permissions.permissions%TYPE;
	BEGIN
		SELECT permissions
		FROM role_permissions
		WHERE entity = p_guild_id
		INTO v_base;
		v_base := coalesce(v_base, p_default_permissions);

		-- apply role permissions
		v_base := v_base | coalesce((
			SELECT bit_or(permissions)
			FROM role_permissions
			WHERE entity = ANY (p_role_ids)), 0);

		-- apply @everyone overwrites first since it's special
		SELECT allow, deny
		FROM page_permissions
		WHERE
			entity = p_guild_id
			AND page_id = p_page_id
		INTO v_allow, v_deny;

		v_allow := coalesce(v_allow, 0);
		v_deny := coalesce(v_deny, 0);

		v_base := (v_base & ~v_deny) | v_allow;

		v_allow := v_allow | coalesce((
			SELECT bit_or(allow)
			FROM page_permissions
			WHERE entity = ANY (p_role_ids) AND page_id = p_page_id), 0);

		v_deny := v_deny | coalesce((
			SELECT bit_or(deny)
			FROM page_permissions
			WHERE entity = ANY (p_role_ids) AND page_id = p_page_id), 0);

		v_base := (v_base & ~v_deny) | v_allow;

		-- member specific overwrites
		v_base := v_base & ~coalesce((
			SELECT deny
			FROM page_permissions
			WHERE entity = p_member_id AND page_id = p_page_id), 0);

		v_base := v_base | coalesce((
			SELECT allow
			FROM page_permissions
			WHERE entity = p_member_id AND page_id = p_page_id), 0);

		RETURN v_base; END; $$ LANGUAGE plpgsql;
