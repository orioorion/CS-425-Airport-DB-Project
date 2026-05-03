import os
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv
import getpass

def get_db_connection():
    """Create and return database connection"""
    
    # Connection parameters
    params = {
        "dbname": os.environ.get('PGDATABASE'),
        "user": os.environ.get('PGUSER'),
        "password": os.environ.get('PGPASSWORD'),
        "host": os.environ.get('PGHOST', 'localhost'),
        "port": os.environ.get('PGPORT', '5432')
    }
    
    # Validate credentials
    for key, value in params.items():
        if key in ['dbname', 'user', 'password'] and not value:
            print(f" Missing {key} in environment")
            return None
    
    try:
        # Connect to database
        conn = psycopg2.connect(**params)
        print(" Connected to database")
        return conn
        
    except OperationalError as e:
        print(f" Connection error: {e}")
        return None
    
def close_connection(conn):
    """
    Safely close database connection
    """
    if conn:
        try:
            if not conn.closed:
                conn.close()
                print(" Connection closed")
            else:
                print(" Connection already closed")
        except Exception as e:
            print(f" Error: {e}")
    else:
        print(" No connection to close")

def main():
    # Load credentials from .env file
    ## Looks for '.env' in current directory
    load_dotenv()   # Loads only from .env

    print("Loading credentials...")
    print(f"Database: {os.environ.get('PGDATABASE')}")
    print(f"Host: {os.environ.get('PGHOST')}")
    print(f"Port: {os.environ.get('PGPORT')}")
    print(f"User: {os.environ.get('PGUSER')}")

    print(f"Password: {'Set' if os.environ.get('PGPASSWORD') else 'Not set'}")
    
    conn=get_db_connection()
    if conn:
        close_connection(conn)
    
if __name__=="__main__":
    main()