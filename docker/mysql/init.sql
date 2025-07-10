-- MEISTROVERSE Database Initialization
-- This script sets up the initial database configuration

-- Ensure proper character set and collation
ALTER DATABASE meistroverse CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Create additional indexes for performance
-- These will be created by SQLAlchemy, but we can add custom ones here

-- Set MySQL configuration for better performance
SET GLOBAL innodb_buffer_pool_size = 268435456; -- 256MB
SET GLOBAL innodb_log_file_size = 67108864; -- 64MB
SET GLOBAL max_connections = 200;
SET GLOBAL query_cache_size = 16777216; -- 16MB
SET GLOBAL query_cache_type = 1;

-- Create a user for monitoring (optional)
CREATE USER IF NOT EXISTS 'monitoring'@'%' IDENTIFIED BY 'monitoring123';
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'monitoring'@'%';

-- Log initialization
INSERT INTO mysql.general_log (event_time, user_host, thread_id, server_id, command_type, argument)
VALUES (NOW(), 'meistroverse-init', 0, 1, 'Init', 'MEISTROVERSE database initialized successfully');

-- Flush privileges
FLUSH PRIVILEGES;