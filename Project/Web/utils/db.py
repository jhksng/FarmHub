# utils/db.py

# 전역 MySQL 인스턴스를 저장할 변수
_mysql = None

def register_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance

def get_db():
    if _mysql is None:
        raise RuntimeError("MySQL 인스턴스가 아직 등록되지 않았습니다. register_mysql()를 먼저 호출하세요.")
    return _mysql

def get_latest_records(table_name, limit=50):
    db = get_db()
    cur = db.connection.cursor()
    cur.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT %s", (limit,))
    records = cur.fetchall()
    cur.close()
    return records
