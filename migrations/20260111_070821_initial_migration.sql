-- Migration generated at 2026-01-11T07:08:21.017788
-- Message: Initial migration


CREATE TABLE users (
	id INTEGER NOT NULL, 
	telegram_id INTEGER NOT NULL, 
	username VARCHAR(255), 
	email VARCHAR(255), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE UNIQUE INDEX ix_users_telegram_id ON users (telegram_id);

CREATE INDEX ix_users_email ON users (email);

