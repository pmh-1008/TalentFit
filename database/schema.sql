-- Schema MySQL cho TalentFit (sinh từ backend/models.py; backend cũng tự tạo bảng và bổ sung cột khi khởi động)
-- Tạo lại file này sau khi sửa models.py: python -m scripts.export_schema
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
	created_at DATETIME NOT NULL, 
	open_date DATE NOT NULL, 
	closed_at DATETIME, 
	decisions_finalized BOOL NOT NULL DEFAULT '0', 
	deadline DATE NOT NULL, 
	benefits TEXT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_jobs_status CHECK (status IN ('open', 'closed')), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_jobs_company_id ON jobs (company_id);
CREATE INDEX ix_jobs_company_status_deadline ON jobs (company_id, status, deadline);
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
	CONSTRAINT ck_users_role CHECK (role IN ('candidate', 'recruiter')), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE applications (
	id VARCHAR(36) NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(36) NOT NULL, 
	cv_data JSON NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	draft_decision VARCHAR(10), 
	applied_at DATETIME NOT NULL, 
	decided_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_application UNIQUE (job_id, candidate_id), 
	CONSTRAINT ck_applications_status CHECK (status IN ('pending', 'approved', 'rejected')), 
	CONSTRAINT ck_applications_draft_decision CHECK (draft_decision IS NULL OR draft_decision IN ('approved', 'rejected')), 
	FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
	FOREIGN KEY(candidate_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_applications_candidate_id ON applications (candidate_id);
CREATE INDEX ix_applications_job_id ON applications (job_id);

CREATE TABLE candidate_profiles (
	user_id VARCHAR(36) NOT NULL, 
	github VARCHAR(255) NOT NULL, 
	linkedin VARCHAR(255) NOT NULL, 
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
CREATE INDEX ix_notifications_user_read ON notifications (user_id, is_read);

DELIMITER //
CREATE TRIGGER trg_cv_profiles_validate_insert BEFORE INSERT ON candidate_profiles FOR EACH ROW
BEGIN
  IF NEW.education IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"array","items":{"type":"object","required":["degree","school","year"],"properties":{"degree":{"type":"string","minLength":1,"pattern":"\\\\S"},"school":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}}', NEW.education) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
  END IF;
  IF NEW.experience IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"array","items":{"type":"object","required":["title","company","duration_months"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"company":{"type":"string","minLength":1,"pattern":"\\\\S"},"duration_months":{"type":"integer","minimum":0}}}}', NEW.experience) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
  END IF;
  IF NEW.skills IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"array","minItems":1,"items":{"type":"string","minLength":1,"pattern":"\\\\S"}}', NEW.skills) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
  END IF;
  IF NEW.certifications_awards IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"array","items":{"type":"object","required":["title","year"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}}', NEW.certifications_awards) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
  END IF;
END//
CREATE TRIGGER trg_cv_profiles_validate_update BEFORE UPDATE ON candidate_profiles FOR EACH ROW
BEGIN
  IF NOT (NEW.education <=> OLD.education AND NEW.experience <=> OLD.experience AND NEW.skills <=> OLD.skills AND NEW.certifications_awards <=> OLD.certifications_awards) THEN
    IF NEW.education IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"array","items":{"type":"object","required":["degree","school","year"],"properties":{"degree":{"type":"string","minLength":1,"pattern":"\\\\S"},"school":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}}', NEW.education) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
    END IF;
    IF NEW.experience IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"array","items":{"type":"object","required":["title","company","duration_months"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"company":{"type":"string","minLength":1,"pattern":"\\\\S"},"duration_months":{"type":"integer","minimum":0}}}}', NEW.experience) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
    END IF;
    IF NEW.skills IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"array","minItems":1,"items":{"type":"string","minLength":1,"pattern":"\\\\S"}}', NEW.skills) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
    END IF;
    IF NEW.certifications_awards IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"array","items":{"type":"object","required":["title","year"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}}', NEW.certifications_awards) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
    END IF;
  END IF;
END//
CREATE TRIGGER trg_custom_cvs_validate_insert BEFORE INSERT ON custom_cvs FOR EACH ROW
BEGIN
  IF NEW.data IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"object","required":["education","experience","skills","certifications_awards"],"properties":{"education":{"type":"array","items":{"type":"object","required":["degree","school","year"],"properties":{"degree":{"type":"string","minLength":1,"pattern":"\\\\S"},"school":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}},"experience":{"type":"array","items":{"type":"object","required":["title","company","duration_months"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"company":{"type":"string","minLength":1,"pattern":"\\\\S"},"duration_months":{"type":"integer","minimum":0}}}},"skills":{"type":"array","minItems":1,"items":{"type":"string","minLength":1,"pattern":"\\\\S"}},"certifications_awards":{"type":"array","items":{"type":"object","required":["title","year"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}}}}', NEW.data) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
  END IF;
END//
CREATE TRIGGER trg_custom_cvs_validate_update BEFORE UPDATE ON custom_cvs FOR EACH ROW
BEGIN
  IF NOT (NEW.data <=> OLD.data) THEN
    IF NEW.data IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"object","required":["education","experience","skills","certifications_awards"],"properties":{"education":{"type":"array","items":{"type":"object","required":["degree","school","year"],"properties":{"degree":{"type":"string","minLength":1,"pattern":"\\\\S"},"school":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}},"experience":{"type":"array","items":{"type":"object","required":["title","company","duration_months"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"company":{"type":"string","minLength":1,"pattern":"\\\\S"},"duration_months":{"type":"integer","minimum":0}}}},"skills":{"type":"array","minItems":1,"items":{"type":"string","minLength":1,"pattern":"\\\\S"}},"certifications_awards":{"type":"array","items":{"type":"object","required":["title","year"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}}}}', NEW.data) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
    END IF;
  END IF;
END//
CREATE TRIGGER trg_applications_validate_insert BEFORE INSERT ON applications FOR EACH ROW
BEGIN
  IF NEW.cv_data IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"object","required":["education","experience","skills","certifications_awards"],"properties":{"education":{"type":"array","items":{"type":"object","required":["degree","school","year"],"properties":{"degree":{"type":"string","minLength":1,"pattern":"\\\\S"},"school":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}},"experience":{"type":"array","items":{"type":"object","required":["title","company","duration_months"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"company":{"type":"string","minLength":1,"pattern":"\\\\S"},"duration_months":{"type":"integer","minimum":0}}}},"skills":{"type":"array","minItems":1,"items":{"type":"string","minLength":1,"pattern":"\\\\S"}},"certifications_awards":{"type":"array","items":{"type":"object","required":["title","year"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}}}}', NEW.cv_data) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
  END IF;
END//
CREATE TRIGGER trg_applications_validate_update BEFORE UPDATE ON applications FOR EACH ROW
BEGIN
  IF NOT (NEW.cv_data <=> OLD.cv_data) THEN
    IF NEW.cv_data IS NULL OR NOT JSON_SCHEMA_VALID('{"type":"object","required":["education","experience","skills","certifications_awards"],"properties":{"education":{"type":"array","items":{"type":"object","required":["degree","school","year"],"properties":{"degree":{"type":"string","minLength":1,"pattern":"\\\\S"},"school":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}},"experience":{"type":"array","items":{"type":"object","required":["title","company","duration_months"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"company":{"type":"string","minLength":1,"pattern":"\\\\S"},"duration_months":{"type":"integer","minimum":0}}}},"skills":{"type":"array","minItems":1,"items":{"type":"string","minLength":1,"pattern":"\\\\S"}},"certifications_awards":{"type":"array","items":{"type":"object","required":["title","year"],"properties":{"title":{"type":"string","minLength":1,"pattern":"\\\\S"},"year":{"type":"integer","minimum":1}}}}}}', NEW.cv_data) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';
    END IF;
  END IF;
END//
CREATE TRIGGER trg_jobs_validate_jd_insert BEFORE INSERT ON jobs FOR EACH ROW
BEGIN
  IF NEW.title IS NULL OR CHAR_LENGTH(TRIM(NEW.title)) < 2
OR NEW.description IS NULL OR CHAR_LENGTH(TRIM(NEW.description)) = 0
OR COALESCE(JSON_TYPE(NEW.requirements), '') <> 'OBJECT'
OR COALESCE(JSON_TYPE(JSON_EXTRACT(NEW.requirements, '$.text')), '') <> 'STRING'
OR CHAR_LENGTH(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(NEW.requirements, '$.text')), ''))) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'JD cần có chức danh, mô tả công việc và yêu cầu đối với ứng viên';
  END IF;
END//
CREATE TRIGGER trg_jobs_validate_jd_update BEFORE UPDATE ON jobs FOR EACH ROW
BEGIN
  IF NOT (NEW.title <=> OLD.title AND NEW.description <=> OLD.description AND NEW.requirements <=> OLD.requirements) THEN
    IF NEW.title IS NULL OR CHAR_LENGTH(TRIM(NEW.title)) < 2
OR NEW.description IS NULL OR CHAR_LENGTH(TRIM(NEW.description)) = 0
OR COALESCE(JSON_TYPE(NEW.requirements), '') <> 'OBJECT'
OR COALESCE(JSON_TYPE(JSON_EXTRACT(NEW.requirements, '$.text')), '') <> 'STRING'
OR CHAR_LENGTH(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(NEW.requirements, '$.text')), ''))) = 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'JD cần có chức danh, mô tả công việc và yêu cầu đối với ứng viên';
    END IF;
  END IF;
END//
DELIMITER ;

CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO alembic_version (version_num) VALUES ('0004');
