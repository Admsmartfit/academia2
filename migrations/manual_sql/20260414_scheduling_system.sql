-- Migration: Implementação do Sistema de Agendamento Inteligente
-- Data: 14/04/2026
-- Baseado no prd.md

-- 001: Adicionar campos ao User
ALTER TABLE users ADD COLUMN bio TEXT;
ALTER TABLE users ADD COLUMN specialties JSON;
ALTER TABLE users ADD COLUMN schedule_policy_json JSON;

-- 002: Atualizar campos ao Modality
-- Nota: default_duration renomeado para slot_duration_min no modelo para consistência
ALTER TABLE modalities ADD COLUMN slot_duration_min INTEGER NOT NULL DEFAULT 60;
-- credits_cost geralmente já existe, mas garantindo aqui
-- ALTER TABLE modalities ADD COLUMN credits_cost INTEGER NOT NULL DEFAULT 1;

-- 003: Criar ScheduleTemplate
CREATE TABLE schedule_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    modality_id INTEGER,
    weekdays JSON NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_duration_min INTEGER NOT NULL DEFAULT 60,
    max_capacity INTEGER NOT NULL DEFAULT 10,
    valid_from DATE NOT NULL,
    valid_until DATE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(provider_id) REFERENCES users(id),
    FOREIGN KEY(modality_id) REFERENCES modalities(id)
);

-- 004: Criar ScheduleSlot
CREATE TABLE schedule_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    template_id INTEGER,
    modality_id INTEGER,
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    max_capacity INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    cancel_reason VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(provider_id) REFERENCES users(id),
    FOREIGN KEY(template_id) REFERENCES schedule_templates(id),
    FOREIGN KEY(modality_id) REFERENCES modalities(id)
);

-- 005: Atualizar Booking (adaptar para novo slot_id)
-- Como SQLite não permite ALTER TABLE DROP COLUMN facilmente, o modelo Booking 
-- foi atualizado para referenciar slot_id.
ALTER TABLE bookings ADD COLUMN slot_id INTEGER;
ALTER TABLE bookings ADD COLUMN recurring_id INTEGER;
ALTER TABLE bookings ADD COLUMN checked_in_at DATETIME;
ALTER TABLE bookings ADD COLUMN xp_awarded INTEGER DEFAULT 0;
-- cost_at_booking e client_id (user_id) já existem na base legada, mas 
-- garantimos consistência de nomes no modelo.

-- 006: Criar RecurringBooking
CREATE TABLE recurring_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    modality_id INTEGER,
    weekday INTEGER NOT NULL,
    start_time TIME NOT NULL,
    frequency VARCHAR(20) NOT NULL DEFAULT 'weekly',
    subscription_id INTEGER,
    valid_from DATE NOT NULL,
    valid_until DATE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(client_id) REFERENCES users(id),
    FOREIGN KEY(provider_id) REFERENCES users(id),
    FOREIGN KEY(modality_id) REFERENCES modalities(id),
    FOREIGN KEY(subscription_id) REFERENCES subscriptions(id)
);

-- 007: Tabelas de Extensibilidade (Vazias)
CREATE TABLE notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE consent_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE workout_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
