-- Development initialization for MEISTROVERSE

-- Create test data for development
INSERT IGNORE INTO projects (name, description, is_active, created_at, updated_at) VALUES
('MEISTROVERSE Core', 'Main MEISTROVERSE project for core functionality', true, NOW(), NOW()),
('Development Testing', 'Project for development and testing purposes', true, NOW(), NOW());

-- Create sample agents
INSERT IGNORE INTO agents (name, agent_type, description, system_prompt, is_active, created_at, updated_at) VALUES
('Prompt QC Agent', 'prompt_qc_agent', 'Analyzes and improves prompt quality', 'You are a prompt quality control agent...', true, NOW(), NOW()),
('Code Mutation Agent', 'code_mutation_agent', 'Analyzes code for improvements', 'You are a code analysis and improvement agent...', true, NOW(), NOW());

-- Create sample prompt templates
INSERT IGNORE INTO prompt_templates (name, template, agent_type, version, is_active, performance_score, created_at, updated_at) VALUES
('Default QC Analysis', 'Analyze the following prompt for quality and effectiveness: {prompt}', 'prompt_qc_agent', 1, true, 85.5, NOW(), NOW()),
('Code Review Template', 'Review this code for potential improvements: {code}', 'code_mutation_agent', 1, true, 92.3, NOW(), NOW());

-- Log development initialization
SELECT 'MEISTROVERSE development environment initialized' as status;