-- Migration generated at 2026-01-11T07:14:29.275586
-- Message: Test migration


CREATE TABLE users (
	id INTEGER NOT NULL, 
	telegram_id INTEGER NOT NULL, 
	username VARCHAR(255), 
	email VARCHAR(255), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE deadlines (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	description TEXT, 
	due_date DATETIME, 
	status VARCHAR(32) NOT NULL, 
	source VARCHAR(64), 
	source_id VARCHAR(255), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	last_notified_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE subscriptions (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	notification_type VARCHAR(64) NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE blocked_users (
	id INTEGER NOT NULL, 
	telegram_id INTEGER NOT NULL, 
	reason TEXT, 
	blocked_by INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE user_notification_settings (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	notifications_enabled BOOLEAN NOT NULL, 
	notification_hour INTEGER NOT NULL, 
	quiet_hours_start VARCHAR(5) NOT NULL, 
	quiet_hours_end VARCHAR(5) NOT NULL, 
	daily_reminders BOOLEAN NOT NULL, 
	weekly_reminders BOOLEAN NOT NULL, 
	halfway_reminders BOOLEAN NOT NULL, 
	weekly_days VARCHAR(255) NOT NULL, 
	days_before_warning INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE deadline_verifications (
	id INTEGER NOT NULL, 
	deadline_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	user_comment TEXT, 
	admin_comment TEXT, 
	verified_by INTEGER, 
	created_at DATETIME NOT NULL, 
	verified_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(deadline_id) REFERENCES deadlines (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE UNIQUE INDEX ix_users_telegram_id ON users (telegram_id);

CREATE INDEX ix_users_email ON users (email);

CREATE INDEX ix_deadlines_user_id ON deadlines (user_id);

CREATE INDEX ix_deadlines_source ON deadlines (source);

CREATE INDEX ix_deadlines_source_id ON deadlines (source_id);

CREATE INDEX ix_deadlines_status ON deadlines (status);

CREATE INDEX ix_subscriptions_active ON subscriptions (active);

CREATE INDEX ix_subscriptions_user_id ON subscriptions (user_id);

CREATE UNIQUE INDEX ix_blocked_users_telegram_id ON blocked_users (telegram_id);

CREATE UNIQUE INDEX ix_user_notification_settings_user_id ON user_notification_settings (user_id);

CREATE INDEX ix_deadline_verifications_deadline_id ON deadline_verifications (deadline_id);

CREATE INDEX ix_deadline_verifications_status ON deadline_verifications (status);

CREATE INDEX ix_deadline_verifications_user_id ON deadline_verifications (user_id);

