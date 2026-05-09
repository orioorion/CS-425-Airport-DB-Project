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

def get_flights(departing, date, hour=0, min=0):
    query=f"""SELECT f.*, p.class, p.cost
              FROM Flight f JOIN
               Price p ON f.code = p.code AND f.flight_number = p.flight_number AND f.date = p.date
              LEFT JOIN (SELECT code, flight_number, date, seat_type, COUNT(*) as taken
                         FROM Contains
                         GROUP BY code, flight_number, date, seat_type
              ) as counts ON f.code = counts.code AND f.flight_number = counts.flight_number AND f.date = counts.date AND p.class = counts.seat_type
              WHERE ((p.class = 'Economy' AND COALESCE(counts.taken, 0) < f.max_e_seats)
              OR (p.class = 'First' AND COALESCE(counts.taken, 0) < f.max_f_seats)) 
              AND(f.departure_iata='{departing}' AND date='{date}' AND (departure_hour>{hour} OR (departure_hour={hour} AND departure_min>{min})));"""
    return query

def flights_rec(conn, query, current_itinerary, max_conn, valid_flights, arriving, current_list=[]):
    # initial values are initial query, valid flight={}, current_itinerary is iata of first airport
    # query=string, list=list of the individual flights, itinerary=string of flight, valid_flights=dictionary, departing=current depart_iata, arriving=final arrive_iata
    # entry in list is (code, flight #, date, arrival_hour, arrival_min, arriving_iata, class, cost)
    # "_ _->"
    if len(current_list)==max_conn: # max connecting flights reached
        if current_list[-1][5]==arriving: # made it to final arrival place
            valid_flights[current_itinerary]=current_list
        return
    elif len(current_list)>0 and current_list[-1][5]==arriving: # made it to final arrival before max flight amount
        # add to dictionary
        valid_flights[current_itinerary]=current_list
        return
    else: # didn't make it or is first but still more connections to check
        # iterate through new flights from current iata to other destinations
        with conn.cursor() as cursor:
            cursor.execute(query)
            if len(current_list)==0: # this is first flight in list
                for row in cursor.fetchall():
                    new_list=[*current_list]+[(row[0],row[1],row[2],row[5],row[6],row[9],row[11],row[12])]
                    flights_rec(get_flights(row[9],row[2],row[5],row[6]),current_itinerary,max_conn,valid_flights,arriving,new_list)
            else: # not first flight
                for row in cursor.fetchall():
                    if current_list[-1][6]==row[11]: # check class is the same and add to list
                        new_list=[*current_list]+[(row[0],row[1],row[2],row[5],row[6],row[9],row[11],row[12])]
                        new_itinerary=current_itinerary+"->"+f"{row[9]}"
                        flights_rec(get_flights(row[9],row[2],row[5],row[6]),new_itinerary,max_conn,valid_flights,arriving,new_list)
    return

def browse_booking(email):
    query=f"""SELECT * FROM Booking WHERE email='{email}'""" ######################################################
    return query                                             ######################################################

def is_valid_iata(conn, iata_code):
    # Standardize input to uppercase
    iata_code = iata_code.strip().upper()
    
    query = "SELECT 1 FROM Airport WHERE iata = %s LIMIT 1;"
    
    with conn.cursor() as cursor:
        cursor.execute(query, (iata_code,))
        # fetchone() returns None if the code isn't found
        return cursor.fetchone() is not None
                        
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
    
    print("Welcome to the Airline Booking Application!\n")
    stay=True
    while stay:      
        print("""1. Create an account
2. Change payment information
3. Change address information
4. Search for/book flights
5. Browse bookings
6. Exit program

Please enter your choice (1-6)""")
        user_input=0
        while True:
            try:
                user_input=int(input())
                if 0<user_input<7:
                    break
                else:
                    print("Not an option. Please type number from 1-6")
            except ValueError:
                print("Please enter a number from 1-6")
        
        if user_input==1:
            #Add function later
            print(f"Thank you for choosing option {user_input}")
        elif user_input==2:
            #Add function later
            print(f"Thank you for choosing option {user_input}")
        elif user_input==3:
            #Add function later
            print(f"Thank you for choosing option {user_input}")
        elif user_input==4:
            #Add function later
            # ask for departing, arriving, date, and max connections
            max_conn,date_input,departing_iata,destination_iata=None,None,None,None
            print("Please enter the maximum number of connections you want (1 for direct flights only):")
            while True:
                try:
                    max_conn=int(input())
                    if 0<max_conn<4:
                        break
                    else:
                        print("Not an option. Please type number from 1-3")
                except ValueError:
                    print("Please enter a number from 1-3")
            print("Please enter the date of your flight MM DD YYYY separated by spaces (add leading zeros if necessary):")
            while True:
                try:
                    date_input=input().split()
                    if len(date_input)==3 and all(len(x)==2 for x in date_input[:2]) and len(date_input[2])==4 and int(date_input[0]) in range(1,32) and int(date_input[1]) in range(1,13) and int(date_input[2]) in range(1999,2051):
                        date=f"{date_input[0]}-{date_input[1]}-{date_input[2]}"
                        break
                    else:
                        print("Not an option. Please follow the format MM DD YYYY with leading zeros if necessary")
                except ValueError:
                    print("Not an option. Please follow the format MM DD YYYY with leading zeros if necessary")
            while True:
                departing_iata = input("Enter departing airport IATA: ")
                if len(departing_iata)==3 and is_valid_iata(conn, departing_iata):
                    break
                else:
                    print(f"Error: '{departing_iata}' is not a recognized airport code. Please enter 3 character code.")
        elif user_input==5:
            #for user in users:
            #print(f"ID: {user[0]}, Name: {user[1]}, Age: {user[2]}")
            

            #print("Type in the email accosiated with the booking:")
            #email_input=str(input())
            #for i in browse_booking(email_input):
            #    print(f"BookingId: {i[0]}, email: {i[1]}, 

            print(f"Thank you for choosing option {user_input}")
        if conn:
            close_connection(conn)
        if user_input==6:
            print(f"Thank you for using our flight booking website!")
            stay=False
        
    
if __name__=="__main__":
    main()
