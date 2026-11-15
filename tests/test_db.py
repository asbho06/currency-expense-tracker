from sqlalchemy import create_engine, inspect, text

from backend.db import init_db


def test_init_db_upgrades_a_database_from_before_trips(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY, amount_original FLOAT NOT NULL, currency_original VARCHAR NOT NULL,
                amount_base FLOAT NOT NULL, base_currency VARCHAR NOT NULL, fx_rate FLOAT NOT NULL,
                category VARCHAR, expense_date DATETIME, note VARCHAR, created_at DATETIME)
        """))
        conn.execute(text("""
            INSERT INTO expenses (amount_original, currency_original, amount_base, base_currency, fx_rate, category)
            VALUES (150, 'JPY', 0.96, 'USD', 0.0064, 'food')
        """))

    init_db(engine)
    init_db(engine)  # running twice must be harmless

    insp = inspect(engine)
    assert "trips" in insp.get_table_names()
    assert {"trip_id", "status"} <= {c["name"] for c in insp.get_columns("expenses")}
    with engine.connect() as conn:
        row = conn.execute(text("SELECT trip_id, status, amount_original FROM expenses")).one()
    assert tuple(row) == (None, "spent", 150)
