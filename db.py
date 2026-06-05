import sqlite3

def init_db():
    conn = sqlite3.connect('zenith_esports.db')
    cursor = conn.cursor()
    
    # Таблица команд
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captain_id INTEGER UNIQUE,
            team_name TEXT NOT NULL,
            game TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # НОВАЯ Таблица пользователей (для языков)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'ru'
        )
    ''')
    
    conn.commit()
    conn.close()

def add_team(captain_id: int, team_name: str, game: str):
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

# --- ФУНКЦИИ ДЛЯ ЯЗЫКА ---

def get_user_lang(user_id: int) -> str:
    conn = sqlite3.connect('zenith_esports.db')
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_user_lang(user_id: int, lang: str):
    conn = sqlite3.connect('zenith_esports.db')
    cursor = conn.cursor()
    # Если юзер есть - обновляем язык. Если нет - создаем запись
    cursor.execute("INSERT INTO users (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang", 
                   (user_id, lang))
    conn.commit()
    conn.close()
