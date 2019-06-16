CREATE FUNCTION coalesce_agg_statefunc(state anyelement, value anyelement) RETURNS anyelement AS $$
	SELECT coalesce(value, state); $$
LANGUAGE SQL;

CREATE AGGREGATE coalesce_agg(anyelement) (
	SFUNC = coalesce_agg_statefunc,
	STYPE = anyelement);
