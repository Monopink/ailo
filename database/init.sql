CREATE DATABASE IF NOT EXISTS hello_world_db;
USE hello_world_db;

CREATE TABLE IF NOT EXISTS greetings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    message VARCHAR(255)
);

INSERT INTO greetings (message) VALUES ('Hello, World!');