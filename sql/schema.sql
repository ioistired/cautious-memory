SET TIME ZONE UTC;

CREATE TABLE pages(
	page_id SERIAL PRIMARY KEY,
	title VARCHAR(200) NOT NULL,
	-- lets us find the text of the page
	latest_revision INTEGER,
	guild BIGINT NOT NULL,
	-- this information could be gotten by just looking at the date of the oldest revision
	-- but this way is easier
	created TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP);

CREATE UNIQUE INDEX pages_uniq_idx ON pages (lower(title), guild);
CREATE INDEX pages_name_trgm_idx ON pages USING GIN (title gin_trgm_ops);

CREATE TABLE revisions(
	revision_id SERIAL PRIMARY KEY,
	-- what page is this a revision of?
	page_id INTEGER NOT NULL REFERENCES pages ON DELETE CASCADE,
	-- the user ID who created this revision
	author BIGINT NOT NULL,
	content VARCHAR(2000) NOT NULL,
	revised TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP);

ALTER TABLE pages ADD CONSTRAINT "pages_latest_revision_fkey" FOREIGN KEY (latest_revision) REFERENCES revisions;

CREATE TABLE role_permissions(
	role BIGINT PRIMARY KEY,
	permissions INTEGER NOT NULL);

CREATE TABLE page_permissions(
	page_id INTEGER NOT NULL REFERENCES pages ON DELETE CASCADE,
	-- either a role ID or a member ID
	entity BIGINT NOT NULL,
	-- permissions to allow which overwrite role permissions
	allow INTEGER NOT NULL DEFAULT 0,
	-- permissions to deny
	deny INTEGER NOT NULL DEFAULT 0,

	-- you may not allow and deny a permission
	CHECK (allow & deny = 0),
	PRIMARY KEY (page_id, entity));
