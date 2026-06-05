import sqlite3

def init_db():
    conn = sqlite3.connect('zenith_esports.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captain_id INTEGER UNIQUE,
            team_name TEXT NOT NULL,
            game TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

async def add_team(captain_id: int, team_name: str, game: str):
    conn = sqlite3.connect('zenith_esports.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO teams (captain_id, team_name, game) VALUES (?, ?, ?)', 
                       (captain_id, team_name, game))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()