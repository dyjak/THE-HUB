from sqlalchemy import create_engine, text


engine = create_engine("sqlite:///./users.db", connect_args={"check_same_thread": False})


def ensure_pin_hash_column() -> None:
    """Zapewnia, że tabela users ma kolumnę pin_hash."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [column[1] for column in result]

        if "pin_hash" not in columns:
            print("Dodawanie kolumny pin_hash do tabeli users...")
            conn.execute(text("ALTER TABLE users ADD COLUMN pin_hash STRING"))
            print("Kolumna pin_hash została dodana")
        else:
            print("Kolumna pin_hash już istnieje")


def ensure_projs_table() -> None:
    """Tworzy tabelę projs, jeśli nie istnieje."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS projs (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        render VARCHAR(255),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """
    with engine.connect() as conn:
        print("Zapewnienie istnienia tabeli projs...")
        conn.execute(text(create_sql))
        print("Tabela projs jest gotowa.")


if __name__ == "__main__":
    try:
        ensure_pin_hash_column()
        ensure_projs_table()
        print("Migracja zakończona")
    except Exception as e:
        print(f"Wystąpił błąd podczas migracji: {e}")