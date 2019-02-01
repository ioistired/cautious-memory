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
	created TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP);

CREATE INDEX IF NOT EXISTS pages_title_idx ON pages (title);
CREATE UNIQUE INDEX IF NOT EXISTS pages_uniq_idx ON pages (title, guild);

CREATE TABLE IF NOT EXISTS revisions(
	revision_id SERIAL PRIMARY KEY,
	-- what page is this a revision of?
	page_id INTEGER REFERENCES pages(page_id) NOT NULL,
	-- the user ID who created this revision
	author BIGINT NOT NULL,
	content VARCHAR(2000) NOT NULL,
	revised TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP);

-- who can perform a certain action on a page
-- this is ordered by hierarchy: moderators can do everything verified users can do
CREATE TYPE page_restriction AS ENUM ('verified_users', 'moderators');
-- what action are these people allowed to perform?
-- for instance, to delete a page, deny view access to everyone but moderators
CREATE TYPE page_restriction_level AS ENUM ('view', 'edit', 'delete');

CREATE TABLE IF NOT EXISTS page_restrictions(
	pr_id SERIAL PRIMARY KEY,
	page_id INTEGER REFERENCES pages(page_id) NOT NULL,
	pr_type page_restriction NOT NULL,
	pr_level page_restriction_level NOT NULL);

CREATE UNIQUE INDEX IF NOT EXISTS page_restrictions_uniq_idx ON page_restrictions(page_id, pr_type, pr_level);

CREATE TABLE IF NOT EXISTS guild_settings(
	guild BIGINT PRIMARY KEY,
	moderator_role BIGINT,
	verified_role BIGINT,

	CHECK (moderator_role IS NOT NULL OR verified_role IS NOT NULL));
