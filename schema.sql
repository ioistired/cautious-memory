SET TIME ZONE UTC;

CREATE TABLE IF NOT EXISTS pages(
	page_id SERIAL PRIMARY KEY,
	title VARCHAR(200) NOT NULL,
	-- lets us find the text of the page
	latest_revision INTEGER NOT NULL,
	-- whether to restrict editing this page to moderators
	guild BIGINT NOT NULL,
	-- this information could be gotten by just looking at the date of the oldest revision
	-- but this way is easier
	created TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP);

CREATE UNIQUE INDEX IF NOT EXISTS pages_uniq_idx ON pages (LOWER(title), guild);
CREATE INDEX IF NOT EXISTS pages_name_trgm_idx ON pages USING GIN (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS revisions(
	revision_id SERIAL PRIMARY KEY,
	-- what page is this a revision of?
	page_id INTEGER REFERENCES pages NOT NULL,
	-- the user ID who created this revision
	author BIGINT NOT NULL,
	content VARCHAR(2000) NOT NULL,
	revised TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP);

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'access_level') THEN
	-- what action are people allowed to perform?
	-- for instance, to "delete" a page, you could deny view access to everyone but moderators
	CREATE TYPE access_level AS ENUM ('none', 'view', 'edit', 'delete'); END IF; END; $$;

CREATE TABLE IF NOT EXISTS guild_default_permissions(
	guild BIGINT PRIMARY KEY,

	everyone_perms access_level NOT NULL DEFAULT 'edit',
	verified_perms access_level NOT NULL DEFAULT 'edit',
	moderator_perms access_level NOT NULL DEFAULT 'edit');

CREATE TABLE IF NOT EXISTS page_permissions(
	page_id INTEGER REFERENCES pages PRIMARY KEY,

	everyone_perms access_level NOT NULL DEFAULT 'edit',
	verified_perms access_level NOT NULL DEFAULT 'edit',
	moderator_perms access_level NOT NULL DEFAULT 'edit');

CREATE OR REPLACE VIEW effective_page_permissions AS (
	WITH raw_permissions AS (
		SELECT
			page_id, title, guild,
			gdp.everyone_perms AS gep, gdp.verified_perms AS gvp, gdp.moderator_perms AS gmp,
			pp.everyone_perms AS ep, pp.verified_perms AS vp, pp.moderator_perms AS mp
		FROM
			pages
			LEFT JOIN guild_default_permissions AS gdp USING (guild)
			LEFT JOIN page_permissions AS pp USING (page_id))
	SELECT
		page_id,
		title,
		guild,
		COALESCE(ep, gep, 'edit'::access_level) AS everyone_perms,
		COALESCE(vp, gvp, 'edit'::access_level) AS verified_perms,
		COALESCE(mp, gmp, 'edit'::access_level) AS moderator_perms
	FROM raw_permissions);

CREATE TABLE IF NOT EXISTS guild_settings(
	guild BIGINT PRIMARY KEY,
	verified_role BIGINT,
	moderator_role BIGINT,

	CHECK (COALESCE(verified_role, moderator_role) IS NOT NULL));
