-- Copyright © 2019 lambda#0987
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU Affero General Public License as published
-- by the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU Affero General Public License for more details.
--
-- You should have received a copy of the GNU Affero General Public License
-- along with this program.  If not, see <https://www.gnu.org/licenses/>.

SET TIME ZONE UTC;

--- PAGES

CREATE TABLE pages(
	page_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
	title TEXT NOT NULL,
	-- lets us find the text of the page
	latest_revision INTEGER NOT NULL,
	guild BIGINT NOT NULL,
	-- this information could be gotten by just looking at the date of the oldest revision
	-- but this way is easier
	created TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP);

CREATE UNIQUE INDEX pages_uniq_idx ON pages (lower(title), guild);
CREATE INDEX pages_name_trgm_idx ON pages USING GIN (title gin_trgm_ops);

CREATE TABLE revisions(
	-- we START WITH 1 so that 0 is an invalid revision_id, which we will set latest_revision to temporarily
	-- as we create a new page (NOT NULL DEFERRABLE is not supported)
	revision_id INTEGER GENERATED BY DEFAULT AS IDENTITY (START WITH 1) PRIMARY KEY,
	-- what page is this a revision of?
	page_id INTEGER NOT NULL REFERENCES pages ON DELETE CASCADE,
	-- the user ID who created this revision
	author BIGINT NOT NULL,
	content VARCHAR(2000),
	new_title TEXT,
	revised TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP

	-- TODO find a way to make this conditional
	-- ideally this check would not apply to the first revision as that makes finding the then title for
	-- each revision easier
	-- CHECK (num_nonnulls(content, new_title) = 1)
);

ALTER TABLE pages ADD CONSTRAINT "pages_latest_revision_fkey" FOREIGN KEY (latest_revision) REFERENCES revisions DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION notify_page_edit() RETURNS TRIGGER AS $$ BEGIN
	PERFORM * FROM pg_notify('page_edit', new.revision_id::text);
	RETURN new; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER notify_page_edit
	AFTER INSERT ON revisions
	FOR EACH ROW
	EXECUTE PROCEDURE notify_page_edit();

CREATE TABLE aliases(
	title TEXT,
	page_id INTEGER NOT NULL REFERENCES pages ON DELETE CASCADE,
	-- denormalized a bit to make searching aliases and pages easier
	guild BIGINT NOT NULL,
	aliased TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP);

CREATE UNIQUE INDEX aliases_uniq_idx ON aliases (lower(title), guild);
CREATE INDEX aliases_name_trgm_idx ON pages USING GIN (title gin_trgm_ops);

CREATE TABLE page_usage_history(
	page_id INTEGER NOT NULL REFERENCES pages ON DELETE CASCADE,
	time TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'UTC'));

CREATE INDEX page_usage_history_idx ON page_usage_history (page_id);

--- PERMISSIONS

CREATE TABLE role_permissions(
	-- these are always roles, but the column is named "entity" to ease joining with page_permissions
	entity BIGINT PRIMARY KEY,
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

--- API

CREATE TABLE api_tokens(
	user_id BIGINT NOT NULL,
	app_id BIGINT GENERATED BY DEFAULT AS IDENTITY,
	app_name VARCHAR(200),
	secret BYTEA NOT NULL,

	PRIMARY KEY (user_id, app_id));
