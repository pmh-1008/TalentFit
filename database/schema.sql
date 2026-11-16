-- Schema MySQL cho TalentFit (sinh từ backend/models.py; backend cũng tự tạo bảng khi khởi động)
CREATE DATABASE IF NOT EXISTS recruitment_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE recruitment_ai;

CREATE TABLE companies (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	industry VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE jobs (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT NOT NULL, 
	requirements JSON NOT NULL, 
	location VARCHAR(120) NOT NULL, 
	job_type VARCHAR(40) NOT NULL, 
	salary_range VARCHAR(80) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	phone VARCHAR(30) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	opened_at DATETIME NOT NULL, 
	open_date DATE NOT NULL,
	closed_at DATETIME, 
	decisions_finalized BOOL NOT NULL DEFAULT 0,
	deadline DATE, 
	benefits TEXT NOT NULL,
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_jobs_company_id ON jobs (company_id);
CREATE INDEX ix_jobs_status ON jobs (status);

CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	full_name VARCHAR(150) NOT NULL, 
	phone VARCHAR(30) NOT NULL, 
	company_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE applications (
	id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(36) NOT NULL, 
	cv_data JSON NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	applied_at DATETIME NOT NULL, 
	decided_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_application UNIQUE (job_id, candidate_id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
	FOREIGN KEY(candidate_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_applications_candidate_id ON applications (candidate_id);
CREATE INDEX ix_applications_job_id ON applications (job_id);

CREATE TABLE candidate_profiles (
	user_id VARCHAR(36) NOT NULL, 
	summary TEXT NOT NULL, 
	education JSON NOT NULL, 
	experience JSON NOT NULL, 
	skills JSON NOT NULL, 
	certifications_awards JSON NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE custom_cvs (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	data JSON NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_custom_cv UNIQUE (user_id, job_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_custom_cvs_job_id ON custom_cvs (job_id);
CREATE INDEX ix_custom_cvs_user_id ON custom_cvs (user_id);

CREATE TABLE match_results (
	id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	jd_hash VARCHAR(32) NOT NULL, 
	cv_hash VARCHAR(32) NOT NULL, 
	skill_match FLOAT NOT NULL, 
	experience_match FLOAT NOT NULL, 
	education_match FLOAT NOT NULL, 
	overall_fit FLOAT NOT NULL, 
	explanations JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_match UNIQUE (job_id, user_id, jd_hash, cv_hash), 
	FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_match_results_job_id ON match_results (job_id);
CREATE INDEX ix_match_results_user_id ON match_results (user_id);

CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	message TEXT NOT NULL, 
	is_read BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_notifications_user_id ON notifications (user_id);
