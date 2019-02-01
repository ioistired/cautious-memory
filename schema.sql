SET TIME ZONE UTC;

CREATE TABLE IF NOT EXISTS pages(
	page_id SERIAL PRIMARY KEY,
	title VARCHAR(200) NOT NULL,
	-- lets us find the text of the page
	latest_revision INTEGER NOT NULL,
	-- whether to restrict editing this page to moderators
	locked BOOLEAN DEFAULT FALSE,
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

CREATE TABLE IF NOT EXISTS guild_settings(
	guild_id BIGINT PRIMARY KEY,
	moderator_role BIGINT);
