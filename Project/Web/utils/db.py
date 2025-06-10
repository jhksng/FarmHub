# utils/db.py
import mysql.connector
from flask import current_app, g

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=current_app.config['MYSQL_HOST'],
            user=current_app.config['MYSQL_USER'],
            password=current_app.config['MYSQL_PASSWORD'],
            database=current_app.config['MYSQL_DB']
        )
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def get_latest_records(table_name, limit=50):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    query = f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT %s"
    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    cursor.close()
    return results
