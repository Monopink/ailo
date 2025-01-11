from fastapi import FastAPI
import mysql.connector

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, World!!!!!"}

@app.get("/db")
def test_db():
    try:
        connection = mysql.connector.connect(
            host="db",
            user="user",
            password="password",
            database="my_database"
        )
        return {"db_status": "connected"}
    except Exception as e:
        return {"db_status": "error", "error": str(e)}