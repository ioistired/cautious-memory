-- :name list_apps
-- params: user_id
SELECT app_id, app_name
FROM api_tokens
WHERE user_id = $1

-- :name existing_token
-- params: user_id, app_id
SELECT app_name, secret
FROM api_tokens
WHERE user_id = $1 AND app_id = $2

-- :name new_token
-- params: user_id, app_name, secret
INSERT INTO api_tokens (user_id, app_name, secret)
VALUES ($1, $2, $3)
RETURNING app_id

-- :name get_secret
-- params: user_id, app_id
SELECT secret
FROM api_tokens
WHERE user_id = $1 AND app_id = $2

-- :name delete_user_account
-- params: user_id
DELETE FROM api_tokens
WHERE user_id = $1

-- :name delete_app
-- params: user_id, app_id
DELETE FROM api_tokens
WHERE user_id = $1 AND app_id = $2
