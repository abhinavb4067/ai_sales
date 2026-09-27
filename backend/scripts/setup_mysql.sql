-- Run this once as a MySQL admin (e.g. root) to provision the Phase 1 dev database.
CREATE DATABASE IF NOT EXISTS ai_sales CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'ai_sales'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON ai_sales.* TO 'ai_sales'@'localhost';
FLUSH PRIVILEGES;
