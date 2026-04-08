-- 初始化数据库扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 创建应用用户（可选，用于最小权限原则）
-- CREATE USER xhs_app WITH PASSWORD 'xhs_app_password';
-- GRANT CONNECT ON DATABASE xhs_marketing TO xhs_app;
