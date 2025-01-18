import pymysql

# 数据库连接配置
DB_CONFIG = {
    "host": "172.18.0.2",  # Docker 容器 MySQL 地址
    "user": "user",
    "password": "password",
    "database": "says_dev",
    "port": 3306
}

# 创建表的 SQL 语句
TABLES = {
    "user": """
        CREATE TABLE IF NOT EXISTS user (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            language VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            area VARCHAR(100),
            phone VARCHAR(20),
            email VARCHAR(100)
        );
    """,
    "message_history": """
        CREATE TABLE IF NOT EXISTS message_history (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            `from` VARCHAR(100) NOT NULL,
            `to` VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content VARCHAR(1000),
            content_overview CHAR(255)
        );
    """,
    "message_push": """
        CREATE TABLE IF NOT EXISTS message_push (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            `from` VARCHAR(100) NOT NULL,
            `to` VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content VARCHAR(1000),
            delivered BOOLEAN DEFAULT FALSE
        );
    """,
    "scheduled_message": """
        CREATE TABLE IF NOT EXISTS scheduled_message (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            `from` VARCHAR(100) NOT NULL,
            `to` VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content VARCHAR(1000),
            send_at TIMESTAMP,
            sent BOOLEAN DEFAULT FALSE
        );
    """,
    "bot": """
        CREATE TABLE IF NOT EXISTS bot (
            id INT AUTO_INCREMENT PRIMARY KEY,
            model VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            status VARCHAR(50) DEFAULT 'active',
            gender VARCHAR(50),
            birth_date DATE,
            time_zone VARCHAR(50),
            city_name VARCHAR(100),
            user_id INT,
            relationship_score INT CHECK (relationship_score BETWEEN 0 AND 100),
            relationship_type VARCHAR(50),
            long_term_memory TEXT,
            short_term_memory TEXT,
            stranger_style TEXT,
            friend_style TEXT,
            confidant_style TEXT,
            lover_style TEXT,
            FOREIGN KEY (user_id) REFERENCES user(id)
        );
    """,
    "festival": """
        CREATE TABLE IF NOT EXISTS festival (
            id INT AUTO_INCREMENT PRIMARY KEY,
            festival_type VARCHAR(50),
            bot_id INT,
            festival_date DATE,
            festival_content VARCHAR(255),
            is_recurring BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (bot_id) REFERENCES bot(id)
        );
    """,
    "weather": """
        CREATE TABLE IF NOT EXISTS weather (
            id INT AUTO_INCREMENT PRIMARY KEY,
            city_name VARCHAR(100),
            country_code CHAR(2),
            city_code FLOAT,
            temperature INT,
            wind_speed FLOAT,
            weather_description VARCHAR(255),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
    """
}

def ensure_database_exists():
    try:
        # 连接到 MySQL，无需指定数据库
        connection = pymysql.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"]
        )
        cursor = connection.cursor()
        # 检查或创建数据库
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        print(f"Database '{DB_CONFIG['database']}' is ready.")
    except pymysql.MySQLError as e:
        print(f"Error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# 执行建表操作
def create_tables():
    try:
        # 连接到数据库
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor()
        for table_name, create_query in TABLES.items():
            cursor.execute(create_query)
            print(f"Table '{table_name}' created or already exists.")
        connection.commit()
    except pymysql.MySQLError as e:
        print(f"Error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

if __name__ == "__main__":
    ensure_database_exists()
    create_tables()
