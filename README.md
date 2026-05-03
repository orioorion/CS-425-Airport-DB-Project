# CS-425-Airport-DB-Project

# Airline Flight Booking System

## Setup Instructions

### 1. Database Configuration
1. Open pgAdmin and create a database named `airline_db`.
2. Run the `schema.sql` script located in the `/db` folder to create tables.
3. (Optional) Run `seed.sql` to populate initial data.

### 2. Python Environment
1. Clone the repository.
2. Install dependencies:
   `pip install -r requirements.txt`

### 3. Environment Variables
Create a file named `.env` in the root directory and add:
DB_NAME=airline_db
DB_USER=your_username
DB_PASS=your_password
DB_HOST=localhost
DB_PORT=5432

### 4. Running the App
Run the following command:
`python main.py`
