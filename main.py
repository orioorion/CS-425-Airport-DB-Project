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

def register_customer(conn, email, f_name, l_name, home_iata, m_name="NULL"):
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
    # entry in list is (code, flight #, date, departure_hour, departure_min, arrival_hour, arrival_min, arriving_iata,departing iata, class, cost)
    # "_ _->"
    if len(current_list)==max_conn: # max connecting flights reached
        if current_list[-1][7]==arriving: # made it to final arrival place
            valid_flights[current_itinerary]=current_list
        return
    elif len(current_list)>0 and current_list[-1][7]==arriving: # made it to final arrival before max flight amount
        # add to dictionary
        valid_flights[current_itinerary]=current_list
        return
    else: # didn't make it or is first but still more connections to check
        # iterate through new flights from current iata to other destinations
        with conn.cursor() as cursor:
            cursor.execute(query)
            if len(current_list)==0: # this is first flight in list
                for row in cursor.fetchall():
                    new_list=[*current_list]+[(row[0],row[1],row[2],row[3],row[4],row[5],row[6],row[9],row[10],row[11],row[12])]
                    flights_rec(get_flights(row[9],row[2],row[5],row[6]),current_itinerary,max_conn,valid_flights,arriving,new_list)
            else: # not first flight
                for row in cursor.fetchall():
                    if current_list[-1][6]==row[11]: # check class is the same and add to list
                        new_list=[*current_list]+[(row[0],row[1],row[2],row[3],row[4],row[5],row[6],row[9],row[10],row[11],row[12])]
                        new_itinerary=current_itinerary+"->"+f"{row[9]}"
                        flights_rec(get_flights(row[9],row[2],row[5],row[6]),new_itinerary,max_conn,valid_flights,arriving,new_list)
    return

                                           ######################################################

def is_valid_iata(conn, iata_code):
    # Standardize input to uppercase
    iata_code = iata_code.strip().upper()
    
    query = "SELECT 1 FROM Airport WHERE iata = %s LIMIT 1;"
    
    with conn.cursor() as cursor:
        cursor.execute(query, (iata_code,))
        # fetchone() returns None if the code isn't found
        return cursor.fetchone() is not None
    
def get_total_cost(list):
    sum=0
    for l in list:
        sum+=l[10]
    return sum

def get_total_time(list):
    start_mins = list[0][3] * 60 + list[0][4]
    end_mins = list[-1][5] * 60 + list[-1][6]
    
    duration = end_mins - start_mins
    
    total_hours = duration // 60
    total_mins = duration % 60
    time=(total_hours,total_mins)
    return time
                        
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
            f_name=input("Please enter your first name:")
            l_name=input("Please enter your last name: ")
            email=input("Please enter your email: ")
            home=input("Please enter the code of the closest airport to you: ")
            middle=input("Do you have a middle name? Enter yes or no")
            if middle=="yes":
                middle=input("Enter your middle name")
                register_customer(conn,email,f_name,l_name,home,middle)
            else:
                register_customer(conn,email,f_name,l_name,home)
            
        elif user_input==2:
            #Add function later
            card_num=input("Please enter your card number")
            f_name=input("Please enter the first name on your card")
            l_name=input("Please enter the last name on your card")
            cvv=getpass.getpass("Please enter your cvv")
            exp_date=input("Please enter the expiry date (MM/YY)")
            address_id=input("Please enter street address of the card")
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT addressID FROM Address WHERE street_addr='{address_id}'")
                address_id=cursor.fetchone()[0]
            
            add_credit_card(conn, card_num, f_name, l_name, cvv, exp_date, email, address_id)
            
        elif user_input==3:
            #Add function later
            selection=input("Would you like to add or delete an address? Enter 1 for add or 2 for delete")
            if selection==1:
                email=input("Please enter your email")
                street=input("Please enter your street address")
                city=input("Please enter your city")
                state=input("Please enter your two character state code")
                country=input("Please enter your country")
                zipcode=("Please enter your zipcode")
                add_address_and_link(conn, email, street, city, state, country, zipcode)
            else:
                email=input("Please enter your email")
                
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT * FROM Address WHERE addressID IN (Select addressID FROM Lives_at WHERE email='{email}')")
                    print("\nYour Addresses:")
                    print("-" * 80)  # Prints a line of 50 hyphen (-) characters
                    # Header row: ID left-aligned 5, Full Name left-aligned 25, Salary right-aligned 15
                    print(f"{'ID':<5} {'Street Address':<20} {'City':<10}{'State':<15}{'Country':<20}{'Zipcode':>10}")
                    print("-" * 80)
                    for row in cursor.fetchall():
                        address_id,street_addr,city,state,country,zipcode=row
                        print(f"{id:<5} {street_addr:<20} {city:<10}{state:<15}{country:<20}{zipcode:>10}")
                choice=input("Enter the id of the address you wanna delete or 0 to exit")
                if choice>0:
                    delete_address(conn,email,selection)
            
        elif user_input==4:
            # ask for departing, arriving, date, and max connections
            max_conn,date_input,departing_iata,destination_iata=None,None,None,None
            return_flight=False
            print("Would you like to look for a return flight? Enter yes or no")
            while True:
                check=input()
                if check=="yes":
                    return_flight=True
                    break
                elif check=="no":
                    break
                else:
                    print("Please enter yes or no")
            print("Please enter the maximum number of connections you want (1 for direct flights only):")
            while True:
                try:
                    max_conn=int(input())
                    if 0<max_conn<3:
                        break
                    else:
                        print("Not an option. Please type number from 1-2")
                except ValueError:
                    print("Please enter a number from 1-2")
            print("Please enter the departure date of your flight MM DD YYYY separated by spaces (add leading zeros if necessary):")
            while True:
                try:
                    date_input=input().split()
                    if len(date_input)==3 and all(len(x)==2 for x in date_input[:2]) and len(date_input[2])==4 and int(date_input[0]) in range(1,32) and int(date_input[1]) in range(1,13) and int(date_input[2]) in range(1999,2051):
                        departure_date=f"{date_input[0]}-{date_input[1]}-{date_input[2]}"
                        break
                    else:
                        print("Not an option. Please follow the format MM DD YYYY with leading zeros if necessary")
                except ValueError:
                    print("Not an option. Please follow the format MM DD YYYY with leading zeros if necessary")
            if return_flight:
                print("Please enter the return date of your flight MM DD YYYY separated by spaces (add leading zeros if necessary):")
                while True:
                    try:
                        date_input=input().split()
                        if len(date_input)==3 and all(len(x)==2 for x in date_input[:2]) and len(date_input[2])==4 and int(date_input[0]) in range(1,32) and int(date_input[1]) in range(1,13) and int(date_input[2]) in range(1999,2051):
                            return_date=f"{date_input[0]}-{date_input[1]}-{date_input[2]}"
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
            while True:
                destination_iata = input("Enter destination airport IATA: ")
                if len(destination_iata)==3 and is_valid_iata(conn, destination_iata) and destination_iata!=departing_iata:
                    break
                else:
                    print(f"Error: '{destination_iata}' is not a recognized airport code. Please enter 3 character code.")
            connections={}
            flights_rec(conn,get_flights(departing_iata,departure_date),departing_iata,max_conn,connections,destination_iata)
            booked=True
            while booked:
                print("\nDeparting Connecting Flights:")
                print("-" * 60)  # Prints a line of 50 hyphen (-) characters
                # Header row: ID left-aligned 5, Full Name left-aligned 25, Salary right-aligned 15
                print(f"{'ID':<5} {'Itinerary':<15}{'Flights':<10}{'Time':<10} {'Cost':<10}{'Class':>10}")
                print("-" * 60)
                keys=connections.keys()
                for i in range(0,len(connections)):
                    id=i+1
                    itinerary=keys[i]
                    flights=len(connections[itinerary])
                    time=get_total_time(connections[itinerary])
                    time=f"{time[0]}hrs {time[1]}mins"
                    cost=get_total_cost(connections[itinerary])
                    cost="${:,.2f}".format(cost)
                    seat=connections[itinerary][0][9]
                    print(f"{id:<5} {itinerary:<15}{flights:<10}{time:<10} {cost:<10}{seat:>10}")
                print("Enter the id of a connection you want to explore or 0 to exit to menu")
                selection=0
                while True:
                    try:
                        selection=int(input())
                        if -1<selection<len(connections)+1:
                            break
                        else:
                            print("Not an option. Please type id or 0")
                    except ValueError:
                        print("Please enter an id or 0")
                if selection==0:
                    booked=False
                    break
                print("\nFlights in Connection:")
                print("-" * 75)  # Prints a line of 50 hyphen (-) characters
                # Header row: ID left-aligned 5, Full Name left-aligned 25, Salary right-aligned 15
                print(f"{'Code':<5} {'Flight #':<10}{'Date':<15}{'Departing':<5}{'Destination':<5} {'Departing Time':<7} {'Arrival Time':<8}{'Cost':<10}{'Class':>10}")
                print("-" * 75)
                for i in keys[selection-1]:
                    code=i[0]
                    flight_num=i[1]
                    date=i[2]
                    departing=i[8]
                    destination=i[7]
                    departing_time=f"{i[3]}:{i[4]:02d}"
                    arrival_time=f"{i[5]}:{i[6]:02d}"
                    cost="${:,.2f}".format(i[10])
                    seat=i[9]
                    print(f"{code:<5} {flight_num:<10}{date:<15}{departing:<5}{destination:<5} {departing_time:<7} {arrival_time:<8}{cost:<10}{seat:>10}")
                book=input("Would you like to book these flights? Type yes or no")
                if book=="no":
                    break
                email=input("Please enter your email")
                card=int(input("Please enter your card #"))
                with conn.cursor() as cursor:
                    cursor.execute(f"INSERT INTO Booking(email,card_number) VALUES ('{email}',card)")
                    for i in keys[selection-1]:
                        cursor.execute(f'''INSERT INTO Contains(bookingID,code,flight_number,date,seat_type) VALUES 
                                   ((SELECT bookingID FROM Booking WHERE email='{email}' AND card_number=card),
                                   '{i[0]}','{i[1]}','{i[2]}','{i[9]}')''')
                    conn.commit()
                if not return_flight:
                    booked=False
                    break
                connections={}
                flights_rec(conn,get_flights(destination_iata,return_date),destination_iata,max_conn,connections,departing_iata)
                booked=True
                while booked:
                    print("\nDeparting Connecting Flights:")
                    print("-" * 60)  # Prints a line of 50 hyphen (-) characters
                    # Header row: ID left-aligned 5, Full Name left-aligned 25, Salary right-aligned 15
                    print(f"{'ID':<5} {'Itinerary':<15}{'Flights':<10}{'Time':<10} {'Cost':<10}{'Class':>10}")
                    print("-" * 60)
                    keys=connections.keys()
                    for i in range(0,len(connections)):
                        id=i+1
                        itinerary=keys[i]
                        flights=len(connections[itinerary])
                        time=get_total_time(connections[itinerary])
                        time=f"{time[0]}hrs {time[1]}mins"
                        cost=get_total_cost(connections[itinerary])
                        cost="${:,.2f}".format(cost)
                        seat=connections[itinerary][0][9]
                        print(f"{id:<5} {itinerary:<15}{flights:<10}{time:<10} {cost:<10}{seat:>10}")
                    print("Enter the id of a connection you want to explore or 0 to exit to menu")
                    selection=0
                    while True:
                        try:
                            selection=int(input())
                            if -1<selection<len(connections)+1:
                                break
                            else:
                                print("Not an option. Please type id or 0")
                        except ValueError:
                            print("Please enter an id or 0")
                    if selection==0:
                        booked=False
                        break
                    print("\nFlights in Connection:")
                    print("-" * 75)  # Prints a line of 50 hyphen (-) characters
                    # Header row: ID left-aligned 5, Full Name left-aligned 25, Salary right-aligned 15
                    print(f"{'Code':<5} {'Flight #':<10}{'Date':<15}{'Departing':<5}{'Destination':<5} {'Departing Time':<7} {'Arrival Time':<8}{'Cost':<10}{'Class':>10}")
                    print("-" * 75)
                    for i in keys[selection-1]:
                        code=i[0]
                        flight_num=i[1]
                        date=i[2]
                        departing=i[8]
                        destination=i[7]
                        departing_time=f"{i[3]}:{i[4]:02d}"
                        arrival_time=f"{i[5]}:{i[6]:02d}"
                        cost="${:,.2f}".format(i[10])
                        seat=i[9]
                        print(f"{code:<5} {flight_num:<10}{date:<15}{departing:<5}{destination:<5} {departing_time:<7} {arrival_time:<8}{cost:<10}{seat:>10}")
                    book=input("Would you like to book these flights? Type yes or no")
                    if book=="no":
                        break
                    email=input("Please enter your email")
                    card=int(input("Please enter your card #"))
                    with conn.cursor() as cursor:
                        cursor.execute(f"INSERT INTO Booking(email,card_number) VALUES ('{email}',card)")
                        for i in keys[selection-1]:
                            cursor.execute(f'''INSERT INTO Contains(bookingID,code,flight_number,date,seat_type) VALUES 
                                    ((SELECT bookingID FROM Booking WHERE email='{email}' AND card_number=card),
                                    '{i[0]}','{i[1]}','{i[2]}','{i[9]}')''')
                        conn.commit()
                    booked=False
                
        elif user_input==5:
            email=input("Please enter your email")
            deleted=False
            while not deleted:
                with conn.cursor() as cursor:
                    cursor.execute(f"Select bookingID FROM Booking WHERE email='{email}'")
                    for row in cursor.fetchall():
                        # Displaying the results in a formatted manner
                        print(f"ID: {row[0]}")
                selection=int(input("Please select an id to look at or 0 to exit"))
                if selection==0:
                    deleted=True
                    break
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT code,flight_number,date,seat_type FROM Contains WHERE bookingID={selection}")
                    bookings = cursor.fetchall()
                    if not bookings:
                        print("There are no bookings for this email")
                        deleted=True
                        break
                    for row in bookings:
                        print(f"Code: {row[0]}  Flight #: {row[1]}  Date: {row[2]}  Seat Type: {row[3]}")
                choice=input("Would you like to cancel this booking? Enter yes or no")
                if choice=="yes":
                    with conn.cursor() as cursor:
                        cursor.execute(f"DELETE FROM Contains WHERE bookingID = {selection}")
            
                        # Step B: Delete the main booking record
                        cursor.execute(f"DELETE FROM Booking WHERE bookingID = {selection}")
                        
                        conn.commit()
                    deleted=True
            
        elif user_input==6:
            print(f"Thank you for using our flight booking website!")
            close_connection(conn)
            stay=False
        
    
if __name__=="__main__":
    main()
