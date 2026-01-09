CREATE TABLE IF NOT EXISTS question_bank (
  id INT AUTO_INCREMENT PRIMARY KEY,
  category VARCHAR(255),
  type VARCHAR(50) NOT NULL DEFAULT '자동생성',
  question_text TEXT NOT NULL,
  keyword VARCHAR(255),
  UNIQUE KEY uq_question_text (question_text(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS survey_info (
  id INT AUTO_INCREMENT PRIMARY KEY,
  client_name VARCHAR(255) NOT NULL,
  course_name VARCHAR(255) NOT NULL,
  manager VARCHAR(255) NOT NULL,
  date DATE NOT NULL,
  category VARCHAR(255) NOT NULL,
  survey_name VARCHAR(255) NOT NULL,
  UNIQUE KEY uq_survey (client_name, course_name, manager, date, category, survey_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS responses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  survey_id INT NOT NULL,
  respondent_id VARCHAR(255) NOT NULL,
  question_id INT NOT NULL,
  answer_value TEXT,
  UNIQUE KEY uq_response (respondent_id, question_id),
  CONSTRAINT fk_responses_survey
    FOREIGN KEY (survey_id) REFERENCES survey_info (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_responses_question
    FOREIGN KEY (question_id) REFERENCES question_bank (id)
    ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
