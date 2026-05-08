import os
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv
import getpass
from prettytable import PrettyTable

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

# --- 4.1 Registration ---
def register_customer(conn, email, f_name, l_name, home_iata, m_name=None):
    try:
        cur = conn.cursor()
        sql = "INSERT INTO Customer (email, first_name, last_name, middle_name, home_iata) VALUES (%s, %s, %s, %s, %s);"
        cur.execute(sql, (email, f_name, l_name, m_name, home_iata))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        cur.close()

# --- 4.2 Payment Information and Addresses ---
def add_address_and_link(conn, email, street, city, state, country, zipcode):
    try:
        cur = conn.cursor()
        addr_sql = "INSERT INTO Address (street_addr, city, state, country, zipcode) VALUES (%s, %s, %s, %s, %s) RETURNING addressID;"
        cur.execute(addr_sql, (street, city, state, country, zipcode))
        address_id = cur.fetchone()[0]

        link_sql = "INSERT INTO Lives_at (email, addressID) VALUES (%s, %s);"
        cur.execute(link_sql, (email, address_id))
        
        conn.commit()
        return address_id
    except Exception:
        conn.rollback()
        return None
    finally:
        cur.close()

def add_credit_card(conn, card_num, f_name, l_name, cvv, exp_date, email, address_id):
    try:
        cur = conn.cursor()
        sql = "INSERT INTO Credit_card (card_number, first_name, last_name, CVV, exp_date, email, addressID) VALUES (%s, %s, %s, %s, %s, %s, %s);"
        cur.execute(sql, (card_num, f_name, l_name, cvv, exp_date, email, address_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        cur.close()

def delete_address(conn, email, address_id):
    try:
        cur = conn.cursor()
        check_sql = "SELECT COUNT(*) FROM Credit_card WHERE email = %s AND addressID = %s;"
        cur.execute(check_sql, (email, address_id))
        
        if cur.fetchone()[0] > 0:
            return "LINKED_TO_CARD"

        cur.execute("DELETE FROM Lives_at WHERE email = %s AND addressID = %s;", (email, address_id))
        cur.execute("DELETE FROM Address WHERE addressID = %s;", (address_id,))
        conn.commit()
        return "SUCCESS"
    except Exception:
        conn.rollback()
        return "ERROR"
    finally:
        cur.close()

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
    
    conn = get_db_connection()
    if conn:
        close_connection(conn)
    
if __name__=="__main__":
    main()