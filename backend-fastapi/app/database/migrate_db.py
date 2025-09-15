from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, DateTime
from datetime import datetime

# Połączenie z istniejącą bazą
engine = create_engine("sqlite:///./users.db", connect_args={"check_same_thread": False})
metadata = MetaData()
conn = engine.connect()

try:
    # Sprawdź, czy kolumna istnieje
    result = conn.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in result]

    if 'pin_hash' not in columns:
        print("Dodawanie kolumny pin_hash do tabeli users...")
        conn.execute("ALTER TABLE users ADD COLUMN pin_hash STRING")
        print("Kolumna pin_hash została dodana")
    else:
        print("Kolumna pin_hash już istnieje")

except Exception as e:
    print(f"Wystąpił błąd: {e}")
finally:
    conn.close()

print("Migracja zakończona")