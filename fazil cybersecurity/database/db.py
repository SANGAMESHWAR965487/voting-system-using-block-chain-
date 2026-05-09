import sqlite3

DB_NAME= "voting.db"

def get_connection():
    conn = sqlite3.connect("voting.db")
    conn.row_factory = sqlite3.Row
    return conn

# ── ADD THIS FUNCTION TO database/db.py ──────────────────────────────────────
# Paste it anywhere after the existing functions
 
def clear_all_votes():
    """Delete all votes AND reset the voted flag on all users."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM votes")
    cursor.execute("UPDATE users SET voted = 0")
    conn.commit()
    conn.close()


def create_users_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        rollno TEXT UNIQUE,
        mobile TEXT,
        email TEXT,
        password TEXT,
        voted INTEGER DEFAULT 0,
        photo TEXT,
        approved INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

def create_candidates_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        symbol TEXT,
        position TEXT,
        image TEXT
    )
    """)

    conn.commit()
    conn.close()

# Add image column to existing candidates table if it doesn't exist
def migrate_candidates_table():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if image column exists
    cursor.execute("PRAGMA table_info(candidates)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'image' not in columns:
        cursor.execute("ALTER TABLE candidates ADD COLUMN image TEXT")
        conn.commit()
    
    conn.close()

# Add approved column to existing users table if it doesn't exist
def migrate_users_table():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if approved column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'approved' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN approved INTEGER DEFAULT 0")
        conn.commit()
    
    conn.close()

def symbol_exists(position, symbol):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM candidates WHERE position=? AND symbol=?",
        (position, symbol)
    )

    candidate = cursor.fetchone()

    conn.close()

    return candidate


def add_candidate(name, symbol, position, image=None):

    if symbol_exists(position, symbol):
        return False

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO candidates(name,symbol,position,image) VALUES(?,?,?,?)",
        (name, symbol, position, image)
    )

    conn.commit()
    conn.close()

    return True


def user_exists(rollno):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE rollno=?", (rollno,))
    user = cursor.fetchone()

    conn.close()

    return user


def register_user(name, rollno, mobile, email, password, photo=None, approved=False):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO users(name,rollno,mobile,email,password,photo,approved) VALUES(?,?,?,?,?,?,?)",
        (name, rollno, mobile, email, password, photo, 1 if approved else 0)
    )

    conn.commit()
    conn.close()


def is_user_approved(rollno):
    """Check if user is approved by admin"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT approved FROM users WHERE rollno=?", (rollno,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return result["approved"] == 1
    return False


def approve_user_by_rollno(rollno):
    """Approve a user by rollno"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET approved=1 WHERE rollno=?", (rollno,))
    conn.commit()
    conn.close()


def delete_user(rollno):
    """Delete a user by rollno"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE rollno=?", (rollno,))
    conn.commit()
    conn.close()


def get_pending_users():
    """Get all pending (not approved) users"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE approved=0")
    users = cursor.fetchall()
    conn.close()

    return users


def get_all_users():
    """Get all registered users"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()

    return users


def validate_login(rollno, mobile, password):

    conn = get_connection()
    cursor = conn.cursor()

    # Get user by rollno and mobile first
    cursor.execute(
        "SELECT * FROM users WHERE rollno=? AND mobile=?",
        (rollno, mobile)
    )

    user = cursor.fetchone()

    # If user exists, check password
    if user:
        stored_password = user["password"]
        
        # Check if stored password is hashed (SHA-256 = 64 chars) or plain text
        if len(stored_password) == 64:
            # Hash the input password and compare
            import hashlib
            hashed_input = hashlib.sha256(password.encode()).hexdigest()
            if hashed_input != stored_password:
                conn.close()
                return None
        else:
            # Plain text comparison (for backward compatibility)
            if stored_password != password:
                conn.close()
                return None

    conn.close()
    return user

def get_user_by_rollno(rollno):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE rollno=?",
        (rollno,)
    )

    user = cursor.fetchone()

    conn.close()

    return user

def get_candidates_by_position(position):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM candidates WHERE position=?",
        (position,)
    )

    candidates = cursor.fetchall()
    conn.close()

    return candidates

def has_voted(rollno):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT voted FROM users WHERE rollno=?",
        (rollno,)
    )

    result = cursor.fetchone()
    conn.close()

    if result and result["voted"] == 1:
        return True

    return False

def mark_voted(rollno):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET voted=1 WHERE rollno=?",
        (rollno,)
    )

    conn.commit()
    conn.close()

def create_votes_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rollno TEXT,
        position TEXT,
        candidate TEXT
    )
    """)

    conn.commit()
    conn.close()

def save_vote(rollno, position, candidate):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO votes(rollno,position,candidate) VALUES(?,?,?)",
        (rollno, position, candidate)
    )

    conn.commit()
    conn.close()

def get_results(position):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT candidate, COUNT(*) as votes
    FROM votes
    WHERE position=?
    GROUP BY candidate
    """, (position,))

    results = cursor.fetchall()

    conn.close()

    return results


# Settings table for configuration
def create_settings_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()


def get_setting(key):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return result["value"]
    return None


def update_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, value))

    conn.commit()
    conn.close()

def clear_all_candidates():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM candidates")
    conn.commit()
    conn.close()
