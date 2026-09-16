CREATE TABLE projects (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	financial_code VARCHAR(50), 
	project_code VARCHAR(50), 
	project_type VARCHAR(50), 
	leader VARCHAR(50), 
	start_date DATE, 
	end_date DATE, 
	total_budget FLOAT, 
	director VARCHAR(50), 
	PRIMARY KEY (id)
);
CREATE TABLE budget_plans (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	create_date DATE, 
	total_amount FLOAT, 
	remarks VARCHAR(200), 
	PRIMARY KEY (id)
);
CREATE TABLE academic_activities (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	type VARCHAR(10) NOT NULL, 
	status VARCHAR(9), 
	organizer VARCHAR(200), 
	start_date DATE, 
	end_date DATE, 
	location VARCHAR(200), 
	participants VARCHAR(500), 
	description VARCHAR(500), 
	attachment_path VARCHAR(500), 
	PRIMARY KEY (id)
);
CREATE TABLE budgets (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	year INTEGER, 
	total_amount FLOAT, 
	spent_amount FLOAT, 
	PRIMARY KEY (id), 
	CONSTRAINT uix_project_year UNIQUE (project_id, year) ON CONFLICT FAIL, 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);
CREATE TABLE budget_plan_items (
	id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	parent_id INTEGER, 
	category VARCHAR(13), 
	name VARCHAR(100), 
	specification VARCHAR(100), 
	unit_price FLOAT, 
	quantity INTEGER, 
	amount FLOAT, 
	remarks VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES budget_plans (id), 
	FOREIGN KEY(parent_id) REFERENCES budget_plan_items (id)
);
CREATE TABLE gantt_tasks (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	gantt_id VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	code VARCHAR(50), 
	level INTEGER, 
	status VARCHAR(50), 
	start_date DATETIME, 
	duration INTEGER, 
	end_date DATETIME, 
	start_is_milestone BOOLEAN, 
	end_is_milestone BOOLEAN, 
	progress FLOAT, 
	progress_by_worklog BOOLEAN, 
	description VARCHAR(500), 
	collapsed BOOLEAN, 
	has_child BOOLEAN, 
	responsible VARCHAR(50), 
	"order" INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uix_project_gantt_id UNIQUE (project_id, gantt_id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);
CREATE INDEX ix_gantt_tasks_gantt_id ON gantt_tasks (gantt_id);
CREATE TABLE gantt_dependencies (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	predecessor_gantt_id VARCHAR(50) NOT NULL, 
	successor_gantt_id VARCHAR(50) NOT NULL, 
	type VARCHAR(10), 
	PRIMARY KEY (id), 
	CONSTRAINT uix_project_dependency UNIQUE (project_id, predecessor_gantt_id, successor_gantt_id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);
CREATE TABLE project_documents (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	doc_type VARCHAR(13) NOT NULL, 
	version VARCHAR(20), 
	description VARCHAR(500), 
	file_path VARCHAR(500), 
	upload_time DATETIME, 
	keywords VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);
CREATE TABLE project_outcome (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	type VARCHAR(8) NOT NULL, 
	status VARCHAR(9), 
	authors VARCHAR(200), 
	submit_date DATE, 
	publish_date DATE, 
	journal VARCHAR(200), 
	description VARCHAR(500), 
	remarks VARCHAR(200), 
	attachment_path VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);
CREATE TABLE budget_items (
	id INTEGER NOT NULL, 
	budget_id INTEGER NOT NULL, 
	category VARCHAR(13) NOT NULL, 
	amount FLOAT, 
	spent_amount FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(budget_id) REFERENCES budgets (id)
);
CREATE TABLE expenses (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	budget_id INTEGER NOT NULL, 
	category VARCHAR(13) NOT NULL, 
	content VARCHAR(200) NOT NULL, 
	specification VARCHAR(100), 
	supplier VARCHAR(100), 
	amount FLOAT, 
	date DATE, 
	remarks VARCHAR(200), 
	voucher_path VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(budget_id) REFERENCES budgets (id)
);
CREATE TABLE actionlogs (
	id INTEGER NOT NULL, 
	project_id INTEGER, 
	budget_id INTEGER, 
	expense_id INTEGER, 
	gantt_task_id INTEGER, 
	project_document_id INTEGER, 
	project_outcome_id INTEGER, 
	type VARCHAR(50) NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	description VARCHAR(200) NOT NULL, 
	operator VARCHAR(50) NOT NULL, 
	timestamp DATETIME, 
	old_data VARCHAR(500), 
	new_data VARCHAR(500), 
	category VARCHAR(50), 
	amount FLOAT, 
	related_info VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(budget_id) REFERENCES budgets (id), 
	FOREIGN KEY(expense_id) REFERENCES expenses (id), 
	FOREIGN KEY(gantt_task_id) REFERENCES gantt_tasks (id), 
	FOREIGN KEY(project_document_id) REFERENCES project_documents (id), 
	FOREIGN KEY(project_outcome_id) REFERENCES project_outcome (id)
);
