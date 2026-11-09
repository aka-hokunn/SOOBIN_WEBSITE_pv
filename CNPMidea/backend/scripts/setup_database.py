import os
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASS", "123456")
DB_NAME = "cnpm"

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
schema_file = os.path.join(backend_dir, "schema.sql")
seed_file = os.path.join(backend_dir, "seed.sql")

def setup_db():
    print(f"[*] Đang kết nối tới PostgreSQL ({PG_HOST}:{PG_PORT}) bằng user '{PG_USER}'...")
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASS,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}';")
        exists = cur.fetchone()
        if not exists:
            print(f"[*] Cơ sở dữ liệu '{DB_NAME}' chưa tồn tại. Đang tạo cơ sở dữ liệu '{DB_NAME}'...")
            cur.execute(f"CREATE DATABASE {DB_NAME};")
            print(f"[+] Đã tạo cơ sở dữ liệu '{DB_NAME}' thành công!")
        else:
            print(f"[+] Cơ sở dữ liệu '{DB_NAME}' đã tồn tại.")
        cur.close()
        conn.close()

        # Connect to cnpm database
        conn_cnpm = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASS,
            database=DB_NAME
        )
        cur_cnpm = conn_cnpm.cursor()

        # Execute schema.sql
        print("[*] Đang khởi tạo các bảng từ schema.sql...")
        with open(schema_file, "r", encoding="utf-8") as f:
            cur_cnpm.execute(f.read())
        conn_cnpm.commit()
        print("[+] Khởi tạo cấu trúc 45 bảng thành công!")

        # Execute seed.sql
        print("[*] Đang nạp dữ liệu mẫu từ seed.sql...")
        with open(seed_file, "r", encoding="utf-8") as f:
            cur_cnpm.execute(f.read())
        conn_cnpm.commit()
        print("[*] Đang đồng bộ hóa sequence IDs...")
        sync_seq_sql = """
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN (
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE column_default LIKE 'nextval%'
                  AND table_schema = 'public'
            ) LOOP
                EXECUTE format('SELECT setval(pg_get_serial_sequence(%L, %L), COALESCE(MAX(%I), 0) + 1, false) FROM %I',
                               r.table_name, r.column_name, r.column_name, r.table_name);
            END LOOP;
        END $$;
        """
        cur_cnpm.execute(sync_seq_sql)
        conn_cnpm.commit()
        print("[+] Đồng bộ hóa sequence IDs thành công!")

        cur_cnpm.close()
        conn_cnpm.close()

        # Reset passwords with valid bcrypt hash
        from app.models.entities import UserAccount
        from app.core.database import SessionLocal
        from app.core.security import hash_password
        
        db = SessionLocal()
        pwd_hash = hash_password("Password123@")
        users = db.query(UserAccount).all()
        for u in users:
            u.password_hash = pwd_hash
        db.commit()
        print(f"[+] Đã kích hoạt mật khẩu 'Password123@' cho {len(users)} tài khoản demo.")
        db.close()

        print("\n============================================================")
        print("  CƠ SỞ DỮ LIỆU POSTGRESQL 'cnpm' ĐÃ HOÀN TẤT THIẾT LẬP!")
        print("============================================================\n")

    except Exception as e:
        print(f"[-] Lỗi trong quá trình thiết lập cơ sở dữ liệu: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_db()
