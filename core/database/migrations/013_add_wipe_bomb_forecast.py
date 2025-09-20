from datetime import datetime
from peewee import TextField
from ..migration import Migration

def upgrade(db):
    """
    Adds the wipe_bomb_forecast column to the users table.
    """
    with db.atomic():
        db.execute_sql('ALTER TABLE users ADD COLUMN wipe_bomb_forecast TEXT')

def downgrade(db):
    """
    Removes the wipe_bomb_forecast column from the users table.
    """
    with db.atomic():
        # SQLite doesn't directly support DROP COLUMN.
        # A common workaround is to create a new table and copy data.
        # For simplicity, we'll assume this downgrade path is for development.
        # In production, a more robust data migration strategy is needed.
        
        # 1. Get existing columns
        cursor = db.execute_sql('PRAGMA table_info(users)')
        columns = [row[1] for row in cursor.fetchall() if row[1] != 'wipe_bomb_forecast']
        
        # 2. Create new table without the column
        db.execute_sql('CREATE TABLE users_new AS SELECT {} FROM users'.format(','.join(columns)))
        
        # 3. Drop old table
        db.execute_sql('DROP TABLE users')
        
        # 4. Rename new table
        db.execute_sql('ALTER TABLE users_new RENAME TO users')
