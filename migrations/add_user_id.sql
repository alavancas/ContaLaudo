-- Adiciona a coluna user_id à tabela procedimento
ALTER TABLE procedimento ADD COLUMN user_id INTEGER REFERENCES "user" (id);
