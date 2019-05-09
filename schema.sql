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

CREATE UNIQUE INDEX IF NOT EXISTS pages_uniq_idx ON pages (LOWER(title), guild);
CREATE INDEX IF NOT EXISTS pages_name_trgm_idx ON pages USING GIN (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS revisions(
	revision_id SERIAL PRIMARY KEY,
	-- what page is this a revision of?
	page_id INTEGER REFERENCES pages NOT NULL,
	-- the user ID who created this revision
	author BIGINT NOT NULL,
	content VARCHAR(2000) NOT NULL,
	revised TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS role_permissions(
	role BIGINT PRIMARY KEY
	-- not strictly necessary but it lets us delete by guild
	guild BIGINT NOT NULL,
	permissions BIGINT NOT NULL);

CREATE TABLE IF NOT EXISTS page_permissions(
	page_id INTEGER REFERENCES pages NOT NULL ON DELETE CASCADE,
	role BIGINT REFERENCES role_permissions NOT NULL ON DELETE CASCADE,
	-- permissions to allow which overwrite role permissions
	allow BIGINT NOT NULL,
	-- permissions to deny
	deny BIGINT NOT NULL,

	PRIMARY KEY (page_id, role));
