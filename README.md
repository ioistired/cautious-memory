# Cautious Memory
A community wiki for Discord.

[Invite it](https://discordapp.com/oauth2/authorize?client_id=541707781665718302&scope=bot)

## Self-hosting

```
$ sudo -u postgres psql
create database cm;
\c cm
create extension pg_trgm;
^D
$ psql cm -f cautious_memory/sql/schema.sql
$ psql cm -f cautious_memory/sql/functions.sql
```

Copy config.example.json5 to config.json5 and edit appropriately. Make a virtualenv for the bot,
and `pip install -e .`. Then just `python -m cautious_memory`.

### Migrations

`pip install migra`, then `migra postgresql://your-production-connection-string postgresql://your-local-connection-string --unsafe`.
Review the changes, and execute them against prod. For me this usually looks like:

```
$ dropdb cm; createdb cm
$ psql -f sql/schema.sql
$ psql -f sql/functions.sql
$ ssh -NfL 5433:localhost:5432 bots@myserver
$ migra postgresql://bots:password@localhost:5433/cm postgresql:///cm --unsafe > migrate.sql
$ edit migrate.sql  # as necessary
$ psql postgresql://bots:password@localhost:5433/cm -f migrate.sql
$ rm migrate.sql
```

## Credits

- lambda#0987 — basically everything
- Pantsu#6785 — UX testing
- A Discord User#4063 — UX testing
- mellowmarshe#0001 — UX testing

## [License](https://owo.codes/lambda/cautious-memory/blob/master/LICENSE)

Copyright ©︎ 2019 lambda#0987

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
