-- Миграция: переименование колонки marzban_username -> panel_username
-- Запустить ОДИН РАЗ на существующей базе данных перед запуском нового кода.

ALTER TABLE subscriptions
    RENAME COLUMN marzban_username TO panel_username;
