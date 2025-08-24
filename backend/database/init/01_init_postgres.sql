-- PostgreSQL Database Initialization Script
-- This script creates the database schema for the AI chat application
-- Optimized for PostgreSQL 16 with JSONB and performance enhancements
-- File naming: 01_ prefix ensures this runs first in Docker initialization

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Set timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Success message for initialization start
DO $$
BEGIN
    RAISE NOTICE 'Starting PostgreSQL database initialization...';
    RAISE NOTICE 'Target database: %', current_database();
    RAISE NOTICE 'PostgreSQL version: %', version();
END $$;
