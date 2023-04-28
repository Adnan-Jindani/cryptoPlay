import mysql.connector
from jproperties import Properties

# Configure the properties file to get the DB credentials

configs = Properties()
with open('allCreds/DBCreds.properties', 'rb') as config_file:
    configs.load(config_file)

# Getting DB crdentials from the properties file

global dbHost, dbUser, dbPassword, dbSchema

dbHost = configs.get("dbHost").data
dbUser = configs.get("dbUser").data
dbPassword = configs.get("dbPassword").data
dbSchema = configs.get("dbSchema").data

# MySQL database configuration
db_config = {
    'host': dbHost,
    'user': dbUser,
    'password': dbPassword,
    'database': dbSchema
}

# MySQL dump file location
dump_file = 'dump.sql'

# Establishing MySQL database connection
try:
    conn = mysql.connector.connect(**db_config)
    if conn.is_connected():
        print('Connected to MySQL database')

except:
  print("Error connecting to DB, Please check the allCreds/DBCreds.properties file")
  print("Make sure the DB is running and the credentials are correct")
  print("Exiting the program")
  exit()

cursor = conn.cursor()

# Open SQL dump file and read contents
with open('dump.sql', 'r') as f:
    sql_dump = f.read()

# Split SQL dump into individual statements
sql_statements = sql_dump.split(';')

# Execute each SQL statement in the database
for statement in sql_statements:
    try:
        cursor.execute(statement)
    except mysql.connector.Error as e:
        print(f"Error executing SQL statement: {e}")
        continue

# Commit changes and close connection
conn.commit()
conn.close()

print("Dump file has been executed successfully")