-- PKWT Dashboard Database Schema
-- PostgreSQL Schema for Contract Management System

-- Create schema
CREATE SCHEMA IF NOT EXISTS contract_pkwt;

-- Campaign table - stores campaign information
CREATE TABLE IF NOT EXISTS contract_pkwt.campaign (
    campaign_id SERIAL PRIMARY KEY,
    company VARCHAR(255),
    created_at DATE NOT NULL,
    send_at DATE NOT NULL,
    due_date DATE NOT NULL,
    pdf_total INTEGER DEFAULT 0,
    pdf_generated INTEGER DEFAULT 0,
    pdf_status VARCHAR(50) DEFAULT 'pending'
);

-- List contract table - stores employee contract data
-- Note: This table structure is dynamic based on Excel file columns
-- Fallback structure provided below
CREATE TABLE IF NOT EXISTS contract_pkwt.list_contract (
    contract_id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES contract_pkwt.campaign(campaign_id),
    contract_num_detail VARCHAR(255) UNIQUE NOT NULL,
    NIP VARCHAR(10),
    name VARCHAR(100) NOT NULL,
    job_description VARCHAR(100) NOT NULL,
    location VARCHAR(100) NOT NULL,
    birthplace VARCHAR(100) NOT NULL,
    birthdate DATE NOT NULL,
    marriage_status VARCHAR(100) NOT NULL,
    gender VARCHAR(100) NOT NULL,
    address VARCHAR(255) NOT NULL,
    nik VARCHAR(20) NOT NULL,
    tax_status VARCHAR(100) NOT NULL,
    npwp VARCHAR(100) NOT NULL,
    mobile_number VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    mothers_name VARCHAR(100) NOT NULL,
    bank_account VARCHAR(100) NOT NULL,
    gt INTEGER NOT NULL,
    job_position VARCHAR(100) NOT NULL
);

-- Contract status table - tracks contract sending and signing status
CREATE TABLE IF NOT EXISTS contract_pkwt.contract_status (
    status_id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES contract_pkwt.campaign(campaign_id),
    contract_id INTEGER REFERENCES contract_pkwt.list_contract(contract_id),
    send_status BOOLEAN DEFAULT FALSE,
    signed_status BOOLEAN DEFAULT FALSE,
    signed_at TIMESTAMP DEFAULT NULL,
    send_at TIMESTAMP DEFAULT NULL,
    pdf_data BYTEA
);

-- Users table - stores user authentication data
CREATE TABLE IF NOT EXISTS contract_pkwt.users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User sessions table - tracks active user sessions
CREATE TABLE IF NOT EXISTS contract_pkwt.user_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES contract_pkwt.users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- User logs table - logs user activity
CREATE TABLE IF NOT EXISTS contract_pkwt.user_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES contract_pkwt.users(user_id),
    action VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    details TEXT
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_contract_status_campaign ON contract_pkwt.contract_status(campaign_id);
CREATE INDEX IF NOT EXISTS idx_contract_status_contract ON contract_pkwt.contract_status(contract_id);
CREATE INDEX IF NOT EXISTS idx_campaign_send_at ON contract_pkwt.campaign(send_at);
CREATE INDEX IF NOT EXISTS idx_campaign_due_date ON contract_pkwt.campaign(due_date);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON contract_pkwt.user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_logs_user_id ON contract_pkwt.user_logs(user_id);