CREATE TABLE process_ai.workspaces (
	id VARCHAR(36) NOT NULL, 
	slug VARCHAR(64) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	tenant_id VARCHAR(100), 
	workspace_type VARCHAR(20) NOT NULL, 
	country VARCHAR(2), 
	business_type VARCHAR(50), 
	language_style VARCHAR(50), 
	default_audience VARCHAR(50), 
	default_detail_level VARCHAR(50), 
	context_text TEXT, 
	description TEXT, 
	metadata_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_process_ai_workspaces_slug ON process_ai.workspaces (slug);
CREATE INDEX ix_process_ai_workspaces_business_type ON process_ai.workspaces (business_type);
CREATE INDEX ix_process_ai_workspaces_country ON process_ai.workspaces (country);
CREATE UNIQUE INDEX ix_process_ai_workspaces_tenant_id ON process_ai.workspaces (tenant_id);
CREATE TABLE process_ai.documents (
	id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(36) NOT NULL, 
	domain VARCHAR(20) NOT NULL, 
	document_type VARCHAR(50) DEFAULT 'procedimiento' NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	approved_version_id VARCHAR(36), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	folder_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_process_ai_documents_folder_id ON process_ai.documents (folder_id);
CREATE INDEX ix_process_ai_documents_approved_version_id ON process_ai.documents (approved_version_id);
CREATE INDEX ix_process_ai_documents_workspace_id ON process_ai.documents (workspace_id);
CREATE TABLE process_ai.users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(200) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	external_id VARCHAR(255), 
	auth_provider VARCHAR(50), 
	auth_metadata_json TEXT NOT NULL, 
	metadata_json TEXT NOT NULL, 
	phone_e164 VARCHAR(20), 
	phone_verified BOOLEAN NOT NULL, 
	phone_verified_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_process_ai_users_external_id ON process_ai.users (external_id);
CREATE UNIQUE INDEX ix_process_ai_users_email ON process_ai.users (email);
CREATE INDEX ix_process_ai_users_phone_e164 ON process_ai.users (phone_e164);
CREATE TABLE process_ai.roles (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	workspace_type VARCHAR(20), 
	is_system BOOLEAN NOT NULL, 
	metadata_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_process_ai_roles_name ON process_ai.roles (name);
CREATE TABLE process_ai.permissions (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	metadata_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_process_ai_permissions_name ON process_ai.permissions (name);
CREATE INDEX ix_process_ai_permissions_category ON process_ai.permissions (category);
CREATE TABLE process_ai.runs (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	domain VARCHAR(20) NOT NULL, 
	profile VARCHAR(50) NOT NULL, 
	input_manifest_json TEXT NOT NULL, 
	prompt_hash VARCHAR(64) NOT NULL, 
	model_text VARCHAR(100) NOT NULL, 
	model_transcribe VARCHAR(100) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	validation_id VARCHAR(36), 
	is_approved BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_process_ai_runs_is_approved ON process_ai.runs (is_approved);
CREATE INDEX ix_process_ai_runs_validation_id ON process_ai.runs (validation_id);
CREATE INDEX ix_process_ai_runs_document_id ON process_ai.runs (document_id);
CREATE TABLE process_ai.validations (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	run_id VARCHAR(36), 
	validator_user_id VARCHAR(36), 
	status VARCHAR(20) NOT NULL, 
	observations TEXT NOT NULL, 
	checklist_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_process_ai_validations_validator_user_id ON process_ai.validations (validator_user_id);
CREATE INDEX ix_process_ai_validations_run_id ON process_ai.validations (run_id);
CREATE INDEX ix_process_ai_validations_document_id ON process_ai.validations (document_id);
CREATE TABLE process_ai.document_versions (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	run_id VARCHAR(36), 
	version_number INTEGER NOT NULL, 
	version_status VARCHAR(20) NOT NULL, 
	supersedes_version_id VARCHAR(36), 
	content_type VARCHAR(20) NOT NULL, 
	content_json TEXT NOT NULL, 
	content_markdown TEXT NOT NULL, 
	content_html TEXT, 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	approved_by VARCHAR(36), 
	validation_id VARCHAR(36), 
	rejected_at TIMESTAMP WITHOUT TIME ZONE, 
	rejected_by VARCHAR(36), 
	is_current BOOLEAN NOT NULL, 
	pdf_storage_key TEXT, 
	pdf_sha256 VARCHAR(64), 
	pdf_generated_at TIMESTAMP WITHOUT TIME ZONE, 
	pdf_render_engine VARCHAR(50), 
	created_by VARCHAR(36), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_process_ai_document_versions_approved_by ON process_ai.document_versions (approved_by);
CREATE INDEX ix_process_ai_document_versions_document_id ON process_ai.document_versions (document_id);
CREATE INDEX ix_process_ai_document_versions_run_id ON process_ai.document_versions (run_id);
CREATE INDEX ix_process_ai_document_versions_is_current ON process_ai.document_versions (is_current);
CREATE INDEX ix_process_ai_document_versions_rejected_by ON process_ai.document_versions (rejected_by);
CREATE INDEX ix_process_ai_document_versions_supersedes_version_id ON process_ai.document_versions (supersedes_version_id);
CREATE INDEX ix_process_ai_document_versions_validation_id ON process_ai.document_versions (validation_id);
CREATE INDEX ix_process_ai_document_versions_created_by ON process_ai.document_versions (created_by);
CREATE TABLE process_ai.subscription_plans (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	display_name VARCHAR(100) NOT NULL, 
	description TEXT NOT NULL, 
	plan_type VARCHAR(20) NOT NULL, 
	price_monthly FLOAT NOT NULL, 
	price_yearly FLOAT NOT NULL, 
	max_users INTEGER, 
	max_documents INTEGER, 
	max_documents_per_month INTEGER, 
	max_storage_gb FLOAT, 
	features_json TEXT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	sort_order INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_process_ai_subscription_plans_name ON process_ai.subscription_plans (name);
CREATE TABLE process_ai.catalog_option (
	id SERIAL NOT NULL, 
	domain VARCHAR(50) NOT NULL, 
	value VARCHAR(50) NOT NULL, 
	label VARCHAR(200) NOT NULL, 
	prompt_text VARCHAR(2000) NOT NULL, 
	sort_order INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_catalog_domain_value UNIQUE (domain, value)
);
CREATE TABLE process_ai.processes (
	id VARCHAR(36) NOT NULL, 
	audience VARCHAR(50) NOT NULL, 
	detail_level VARCHAR(50) NOT NULL, 
	context_text TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES process_ai.documents (id)
);
CREATE TABLE process_ai.recipes (
	id VARCHAR(36) NOT NULL, 
	cuisine VARCHAR(50) NOT NULL, 
	difficulty VARCHAR(20) NOT NULL, 
	servings INTEGER NOT NULL, 
	prep_time VARCHAR(50) NOT NULL, 
	cook_time VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES process_ai.documents (id)
);
CREATE TABLE process_ai.context_folders (
	id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	path VARCHAR(500) NOT NULL, 
	parent_id VARCHAR(36), 
	sort_order INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES process_ai.workspaces (id), 
	FOREIGN KEY(parent_id) REFERENCES process_ai.context_folders (id)
);
CREATE INDEX ix_process_ai_context_folders_workspace_id ON process_ai.context_folders (workspace_id);
CREATE INDEX ix_process_ai_context_folders_parent_id ON process_ai.context_folders (parent_id);
CREATE TABLE process_ai.folders (
	id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	path VARCHAR(500) NOT NULL, 
	parent_id VARCHAR(36), 
	sort_order INTEGER NOT NULL, 
	inherits_permissions BOOLEAN NOT NULL, 
	metadata_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES process_ai.workspaces (id), 
	FOREIGN KEY(parent_id) REFERENCES process_ai.folders (id)
);
CREATE INDEX ix_process_ai_folders_parent_id ON process_ai.folders (parent_id);
CREATE INDEX ix_process_ai_folders_workspace_id ON process_ai.folders (workspace_id);
CREATE TABLE process_ai.role_permissions (
	role_id VARCHAR(36) NOT NULL, 
	permission_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES process_ai.roles (id), 
	FOREIGN KEY(permission_id) REFERENCES process_ai.permissions (id)
);
CREATE TABLE process_ai.workspace_memberships (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(36) NOT NULL, 
	role_id VARCHAR(36) NOT NULL, 
	role VARCHAR(20), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES process_ai.users (id), 
	FOREIGN KEY(workspace_id) REFERENCES process_ai.workspaces (id), 
	FOREIGN KEY(role_id) REFERENCES process_ai.roles (id)
);
CREATE INDEX ix_process_ai_workspace_memberships_user_id ON process_ai.workspace_memberships (user_id);
CREATE INDEX ix_process_ai_workspace_memberships_workspace_id ON process_ai.workspace_memberships (workspace_id);
CREATE INDEX ix_process_ai_workspace_memberships_role_id ON process_ai.workspace_memberships (role_id);
CREATE TABLE process_ai.operational_roles (
	id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	description TEXT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES process_ai.workspaces (id)
);
CREATE INDEX ix_process_ai_operational_roles_workspace_id ON process_ai.operational_roles (workspace_id);
CREATE INDEX ix_process_ai_operational_roles_slug ON process_ai.operational_roles (slug);
CREATE TABLE process_ai.audit_logs (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	run_id VARCHAR(36), 
	user_id VARCHAR(36), 
	action VARCHAR(50) NOT NULL, 
	entity_type VARCHAR(20), 
	entity_id VARCHAR(36), 
	changes_json TEXT NOT NULL, 
	metadata_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES process_ai.documents (id), 
	FOREIGN KEY(run_id) REFERENCES process_ai.runs (id), 
	FOREIGN KEY(user_id) REFERENCES process_ai.users (id)
);
CREATE INDEX ix_process_ai_audit_logs_run_id ON process_ai.audit_logs (run_id);
CREATE INDEX ix_process_ai_audit_logs_user_id ON process_ai.audit_logs (user_id);
CREATE INDEX ix_process_ai_audit_logs_document_id ON process_ai.audit_logs (document_id);
CREATE TABLE process_ai.workspace_subscriptions (
	id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(36) NOT NULL, 
	plan_id VARCHAR(36) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	current_period_start TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	current_period_end TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	current_users_count INTEGER NOT NULL, 
	current_documents_count INTEGER NOT NULL, 
	current_documents_this_month INTEGER NOT NULL, 
	current_storage_gb FLOAT NOT NULL, 
	payment_provider VARCHAR(50), 
	payment_provider_subscription_id VARCHAR(255), 
	payment_metadata_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES process_ai.workspaces (id), 
	FOREIGN KEY(plan_id) REFERENCES process_ai.subscription_plans (id)
);
CREATE UNIQUE INDEX ix_process_ai_workspace_subscriptions_workspace_id ON process_ai.workspace_subscriptions (workspace_id);
CREATE INDEX ix_process_ai_workspace_subscriptions_plan_id ON process_ai.workspace_subscriptions (plan_id);
CREATE TABLE process_ai.workspace_invitations (
	id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(36) NOT NULL, 
	invited_by_user_id VARCHAR(36) NOT NULL, 
	email VARCHAR(200) NOT NULL, 
	role_id VARCHAR(36) NOT NULL, 
	token VARCHAR(64) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	accepted_at TIMESTAMP WITHOUT TIME ZONE, 
	accepted_by_user_id VARCHAR(36), 
	message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES process_ai.workspaces (id), 
	FOREIGN KEY(invited_by_user_id) REFERENCES process_ai.users (id), 
	FOREIGN KEY(role_id) REFERENCES process_ai.roles (id), 
	FOREIGN KEY(accepted_by_user_id) REFERENCES process_ai.users (id)
);
CREATE INDEX ix_process_ai_workspace_invitations_email ON process_ai.workspace_invitations (email);
CREATE INDEX ix_process_ai_workspace_invitations_invited_by_user_id ON process_ai.workspace_invitations (invited_by_user_id);
CREATE UNIQUE INDEX ix_process_ai_workspace_invitations_token ON process_ai.workspace_invitations (token);
CREATE INDEX ix_process_ai_workspace_invitations_role_id ON process_ai.workspace_invitations (role_id);
CREATE INDEX ix_process_ai_workspace_invitations_workspace_id ON process_ai.workspace_invitations (workspace_id);
CREATE TABLE process_ai.context_files (
	id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(36) NOT NULL, 
	folder_id VARCHAR(36), 
	name VARCHAR(255) NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	content TEXT, 
	file_type VARCHAR(50) NOT NULL, 
	size INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES process_ai.workspaces (id), 
	FOREIGN KEY(folder_id) REFERENCES process_ai.context_folders (id)
);
CREATE INDEX ix_process_ai_context_files_workspace_id ON process_ai.context_files (workspace_id);
CREATE INDEX ix_process_ai_context_files_folder_id ON process_ai.context_files (folder_id);
CREATE TABLE process_ai.user_operational_roles (
	id VARCHAR(36) NOT NULL, 
	workspace_membership_id VARCHAR(36) NOT NULL, 
	operational_role_id VARCHAR(36) NOT NULL, 
	assigned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	assigned_by VARCHAR(36), 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_membership_id) REFERENCES process_ai.workspace_memberships (id) ON DELETE CASCADE, 
	FOREIGN KEY(operational_role_id) REFERENCES process_ai.operational_roles (id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_by) REFERENCES process_ai.users (id) ON DELETE SET NULL
);
CREATE INDEX ix_process_ai_user_operational_roles_operational_role_id ON process_ai.user_operational_roles (operational_role_id);
CREATE INDEX ix_process_ai_user_operational_roles_workspace_membership_id ON process_ai.user_operational_roles (workspace_membership_id);
CREATE TABLE process_ai.folder_permissions (
	id VARCHAR(36) NOT NULL, 
	folder_id VARCHAR(36) NOT NULL, 
	operational_role_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(folder_id) REFERENCES process_ai.folders (id) ON DELETE CASCADE, 
	FOREIGN KEY(operational_role_id) REFERENCES process_ai.operational_roles (id) ON DELETE CASCADE
);
CREATE INDEX ix_process_ai_folder_permissions_operational_role_id ON process_ai.folder_permissions (operational_role_id);
CREATE INDEX ix_process_ai_folder_permissions_folder_id ON process_ai.folder_permissions (folder_id);
ALTER TABLE process_ai.document_versions ADD FOREIGN KEY(document_id) REFERENCES process_ai.documents (id) ON DELETE CASCADE;
ALTER TABLE process_ai.document_versions ADD FOREIGN KEY(created_by) REFERENCES process_ai.users (id) ON DELETE SET NULL;
ALTER TABLE process_ai.documents ADD FOREIGN KEY(workspace_id) REFERENCES process_ai.workspaces (id);
ALTER TABLE process_ai.document_versions ADD FOREIGN KEY(rejected_by) REFERENCES process_ai.users (id) ON DELETE SET NULL;
ALTER TABLE process_ai.document_versions ADD FOREIGN KEY(approved_by) REFERENCES process_ai.users (id) ON DELETE SET NULL;
ALTER TABLE process_ai.runs ADD FOREIGN KEY(document_id) REFERENCES process_ai.documents (id);
ALTER TABLE process_ai.document_versions ADD FOREIGN KEY(run_id) REFERENCES process_ai.runs (id) ON DELETE SET NULL;
ALTER TABLE process_ai.documents ADD FOREIGN KEY(folder_id) REFERENCES process_ai.folders (id);
ALTER TABLE process_ai.document_versions ADD FOREIGN KEY(validation_id) REFERENCES process_ai.validations (id) ON DELETE SET NULL;
ALTER TABLE process_ai.documents ADD FOREIGN KEY(approved_version_id) REFERENCES process_ai.document_versions (id);
ALTER TABLE process_ai.runs ADD FOREIGN KEY(validation_id) REFERENCES process_ai.validations (id);
ALTER TABLE process_ai.validations ADD FOREIGN KEY(validator_user_id) REFERENCES process_ai.users (id);
ALTER TABLE process_ai.validations ADD FOREIGN KEY(document_id) REFERENCES process_ai.documents (id);
ALTER TABLE process_ai.document_versions ADD FOREIGN KEY(supersedes_version_id) REFERENCES process_ai.document_versions (id) ON DELETE SET NULL;
ALTER TABLE process_ai.validations ADD FOREIGN KEY(run_id) REFERENCES process_ai.runs (id);
