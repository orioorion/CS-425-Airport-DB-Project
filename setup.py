import getpass
def main():
    # Create .env file with database credentials
    env_content = """
# PostgreSQL Database Credentials
PGDATABASE="""+input("Please enter the name of your database: ")+"""
PGUSER=postgres
PGPASSWORD="""+getpass.getpass("Please enter your database password: ")+"""
PGHOST=localhost
PGPORT="""+input("Please enter your port number: ")
    
    with open('.env', 'w') as f:  # Opens/creates .env file in write mode
        f.write(env_content.strip())  #  Writes content to file, strip() removes extra whitespace
    
    print(".env file created")

if __name__=="__main__":
    main()