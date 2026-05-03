CREATE TABLE Airport(
        iata CHAR(3) PRIMARY KEY,
        name VARCHAR(50) NOT NULL,
        country VARCHAR(50) NOT NULL,
state VARCHAR(50)
);


CREATE TABLE Airline(
        code CHAR(2) PRIMARY KEY,
        name VARCHAR(50) NOT NULL,
        country_of_origin VARCHAR(50) NOT NULL
);


CREATE TABLE Address(
        addressID INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        street_addr VARCHAR(50) NOT NULL,
        city VARCHAR(30) NOT NULL,
        state CHAR(2),
        country VARCHAR(20) NOT NULL,
        zipcode CHAR(6) NOT NULL
);


CREATE TABLE Customer(
        email VARCHAR(50) PRIMARY KEY,
        first_name VARCHAR(15) NOT NULL,
        last_name VARCHAR(15) NOT NULL,
        middle_name VARCHAR(15),
        home_iata CHAR(3) NOT NULL REFERENCES Airport(iata)
);


CREATE TABLE Lives_at(
        email VARCHAR(50) REFERENCES Customer(email),
        addressID INT REFERENCES Address(addressID),
        PRIMARY KEY (email, addressID)
);


CREATE TABLE Credit_card(
        card_number CHAR(19) NOT NULL PRIMARY KEY,
        first_name VARCHAR(15) NOT NULL,
        last_name VARCHAR(15) NOT NULL,
        CVV VARCHAR(4) NOT NULL,
        exp_date CHAR(5) NOT NULL,
        email VARCHAR(50),
        addressID INT,
        FOREIGN KEY (email, addressID) REFERENCES Lives_at(email,addressID)
);


CREATE TABLE Flight(
        code CHAR(2) REFERENCES Airline(code),
flight_number VARCHAR(20),
date CHAR(10) NOT NULL,
departure_hour INT NOT NULL CHECK (departure_hour>-1 AND departure_hour<24),
departure_min INT NOT NULL CHECK (departure_min>-1 AND departure_min<60),
arrival_hour INT NOT NULL CHECK (arrival_hour>-1 AND arrival_hour<24),
arrival_min INT NOT NULL CHECK (arrival_min>-1 AND arrival_min<60),
max_e_seats INT NOT NULL,
max_f_seats INT NOT NULL,
destination_iata CHAR(3) NOT NULL REFERENCES Airport(iata),
departure_iata CHAR(3) NOT NULL REFERENCES Airport(iata),
PRIMARY KEY (code, flight_number, date)
);


CREATE TABLE Price(
        code CHAR(2),
flight_number VARCHAR(20),
date CHAR(10) NOT NULL,
class VARCHAR(20),
cost NUMERIC(10,2) NOT NULL,
FOREIGN KEY (code, flight_number, date) REFERENCES Flight(code, flight_number, date),
PRIMARY KEY(code, flight_number, date, class)
);


CREATE TABLE Booking(
        bookingID INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        email VARCHAR(50) REFERENCES Customer(email),
        card_number CHAR(19) REFERENCES Credit_card(card_number)
);


CREATE TABLE Contains(
        bookingID INT REFERENCES Booking(bookingID),
        code CHAR(2),
        flight_number VARCHAR(20),
date CHAR(10) NOT NULL,
seat_type VARCHAR(11) NOT NULL,
FOREIGN KEY (code, flight_number, date) REFERENCES Flight(code, flight_number, date),
PRIMARY KEY(bookingID, code, flight_number, date)
);