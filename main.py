#Importing libraries

import random
from flask import Flask, request, render_template, session, redirect, url_for
import firebase_admin
from firebase_admin import db
from mysql.connector import pooling
from jproperties import Properties
from flask_session import Session
import smtplib
import requests
import hashlib
from flask_caching import Cache

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

global mydb, conn, mycursor

try:

  # Connecting to MySQL DB

  mydb = pooling.MySQLConnectionPool(
          pool_name="my_pool",
          pool_size=32,
          host=dbHost,
          user=dbUser,
          password=dbPassword,
          database=dbSchema
      )

  conn = mydb.get_connection()
  mycursor = conn.cursor()

except:
  print("Error connecting to DB, Please check the allCreds/DBCreds.properties file")
  print("Make sure the DB is running and the credentials are correct")
  print("Exiting the program")
  exit()

  # Configure the properties file to get the SMTP credentials

firebase_configs = Properties()
with open('allCreds/firebaseCreds.properties', 'rb') as firebase_config_file:
    firebase_configs.load(firebase_config_file)

#preparing credentials and logging into firebase databse to set and get the data

global firebaseFile, dbURL

firebaseFile = firebase_configs.get("firebaseFile").data
dbURL = firebase_configs.get("dbURL").data

try:
  cred_obj = firebase_admin.credentials.Certificate(firebaseFile)
  default_app = firebase_admin.initialize_app(cred_obj, {'databaseURL':dbURL})
except:
  print("Error connecting to Firebase, Please check the allCreds/firebaseCreds.properties file")
  print("Make sure the firebaseFile is correct and the credentials are correct")
  print("Exiting the program")
  exit()

global ref
ref = db.reference("/")

# Configure the properties file to get the SMTP credentials

smtp_configs = Properties()
with open('allCreds/smtpCreds.properties', 'rb') as smtp_config_file:
    smtp_configs.load(smtp_config_file)

# Getting DB crdentials from the properties file

global smtpEmail, smtpPassword

smtpEmail = smtp_configs.get("smtpEmail").data
smtpPassword = smtp_configs.get("smtpPassword").data

try:

  #Logging into SMTP for emailing

  s = smtplib.SMTP("smtp.gmail.com", 587)
  s.starttls()
  s.login(smtpEmail, smtpPassword)

except:
  print("Error connecting to SMTP, Please check the allCreds/smtpCreds.properties file")
  print("Make sure the SMTP is running and the credentials are correct")
  print("Exiting the program")
  exit()

#Initializing the flask app

app = Flask(__name__)

# Configuring the flask cache
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
cache.init_app(app)

# Initializing flask Sessions

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route('/', methods = ["GET", "POST"])
def index():

  try:
    if session["userType"] == "user":
      return user()

  except:
    # Setting the userType as None to make the software know that the user isn't logged in
    session["userType"] = ""


  if request.method == "POST":
       # get the email from user input
       email = request.form.get("email")
       session["email"] = email
       print(email)

       #check if email is not empty to prevent errors from smtplib library
       if email != None:
        freshEmail = session["email"].replace(".", ",")
        session["freshEmail"] = freshEmail

       # getting the password from user input on the login page
       session["password"] = request.form.get("password")
       session["password"] = hashlib.sha256(session["password"].encode())
       session["password"] = session["password"].hexdigest()
       print(session["password"])

       if session["freshEmail"] != "" and session["password"] != "":

        # Getting the password data of user from the database
        
        DBpasswordUser = ref.child("Users/" + session["freshEmail"]).get()

        # A condition to check if the user is an Employee
        if DBpasswordUser == session["password"]:
          session["userType"] = "user"
          insertIntoAuditTrail(session["email"], "Login")
          return user()
        
        # A condition to tell if the credentials entered are invalid
        else:
          return invalid()

    # rendering the form.html for the login page
  return render_template("index.html")

  # This funtion is for the user

def user(): 
  # Using the global variables
  global conn, mycursor

  # Try and except block to handle DB connection timeout
  try:
    mycursor = conn.cursor()
    sql = "SELECT balance from balances where username = " + "'" + session["email"] + "'"
    mycursor.execute(sql)
    vcoins = mycursor.fetchone()
  except:
    # Connecting to MySQL DB

    mydb = pooling.MySQLConnectionPool(
            pool_name="my_pool",
            pool_size=32,
            host=dbHost,
            user=dbUser,
            password=dbPassword,
            database=dbSchema
        )

    conn = mydb.get_connection()
    mycursor = conn.cursor()
    
  try:
    session["vcoins"] = vcoins[0]
  except:
    session["vcoins"] = 0

  mycursor = conn.cursor()

  sql = "SELECT * from coins"
  mycursor.execute(sql)
  tasks = mycursor.fetchall()

  body=""
  for k in tasks:
    body += (
        "<div class='card'> <img src='"
        + k[3]
        + "'> <h3>"
        + k[1]
        + " ("
        + k[2]
        + ") </h3> <a href=/buy/"
        + str(k[0])
        + "> <button class='buy'> Buy </button> </a> <a href=/sell/"
        + str(k[0])
        + "> <button class='sell'> Sell </button> </a> </div> <br> <br>"
    )

  return render_template("user.html", vcoins = session["vcoins"], tasks=tasks, body=body, profileSeed=session["email"].split("@")[0])


@app.route('/myHoldings', methods = ["GET", "POST"])
def myHoldings(): 

  mycursor = conn.cursor()

  sql = "SELECT * \
         FROM holdings\
         JOIN coins\
         ON holdings.coin_id = coins.id\
        WHERE holdings.username = " + "'" + session["email"] + "' and holdings.coin_amount > 0"

  mycursor.execute(sql)
  tasks = mycursor.fetchall()

  session["netWorth"] = 0

  body=""
  for k in tasks:
    session["netWorth"] = session["netWorth"] + float(k[3])*getCoinPriceFromId(k[4]) + session["vcoins"]
    body += "<div class='card'> <img src='"+ k[7] +"'> <h3>"+ k[5]+" ("+ k[6] +") </h3> <h4>Total Value(INR):- "+ str(round(float(k[3]), 2)*getCoinPriceFromId(k[4])) +"</h4> <a href=/buy/"+ str(k[4]) +"> <button class='buy'> Buy More </button> </a> <a href=/sell/"+ str(k[4]) +"> <button class='sell'> Sell </button> </a> </div> <br> <br>"  

  return render_template("myHoldings.html", vcoins = session["vcoins"], tasks=tasks, body=body, profileSeed=session["email"].split("@")[0], netWorth=round(session["netWorth"], 2))

# This function is to log out the user

@app.route('/logout', methods = ["GET", "POST"])
def logout():
  insertIntoAuditTrail(session["email"], "Logout")
  session.clear()
  return redirect(url_for("index"))

# This function shows if the credentials entered by a user are incorrect
def invalid():

  # rendering the invalid.html which shows the text about invalid credentials
  return redirect("/#openModal")

# This function is for signing up a new user

@app.route('/signup', methods = ["GET", "POST"])
def signup():

  if request.method == "POST":
    createEmail = request.form.get("email")
    createPassword = request.form.get("password")

    if createEmail != None:
      firebaseCreateEmail = createEmail.replace(".", ",")

      session["firebaseCreateEmail"] = firebaseCreateEmail
      session["createEmail"] = createEmail
      session["createPassword"] = createPassword
      session["createPassword"] = hashlib.sha256(session["createPassword"].encode())
      session["createPassword"] = session["createPassword"].hexdigest()

      checkAccount = ref.child("Users/" + firebaseCreateEmail).get()

      if createEmail != None and createPassword != None:
        if "@" and "," in firebaseCreateEmail:
          if checkAccount == None or checkAccount == "":

            session["emailFlag"] = 1
            insertIntoAuditTrail(session["createEmail"], "Verify Email")
            return redirect(url_for("verifyEmail"))

          else:
            return accountExistsSignup()
      
        else:
          return invalidEmailSignup()

  return render_template("signup.html")

def invalidEmailSignup():
  return redirect("/signup#invalidEmailModal")

def accountExistsSignup():
  return redirect("/signup#haveAccountModal")

@app.route('/changePassword', methods = ["GET", "POST"])
def changePassword():
  oldPassword = request.form.get("oldPassword")
  if oldPassword != None:
    oldPassword = hashlib.sha256(oldPassword.encode())
    oldPassword = oldPassword.hexdigest()
  newPassword = request.form.get("newPassword")
  if newPassword != None:
    newPassword = hashlib.sha256(newPassword.encode())
    newPassword = newPassword.hexdigest()
  DBpasswordUser = ref.child("Users/" + session["freshEmail"]).get()

  if oldPassword and newPassword != None:
    if oldPassword == DBpasswordUser:
      ref.child("Users/" + session["freshEmail"]).set(newPassword)
      insertIntoAuditTrail(session["email"], "Password Changed")
      return redirect("/changePassword#successModal")
        
    else:
      return redirect("/changePassword#incorrectPasswordModal")
  return render_template("changePassword.html")

def generatePin():
  return random.randint(1000, 9999)

@app.route('/verifyEmail', methods = ["GET", "POST"])
def verifyEmail():

  if session["emailFlag"] == 1:

    session["pin"] = generatePin()
    session["tries"] = 0

    try:
      s.sendmail(smtpEmail, session["createEmail"], "Subject: Email Verification pin for CryptoPlay \n\n Your CryptoPlay pin is: " + str(session["pin"]) + "\n\n If you did not request this pin, please ignore this email. \n\n Thank you for using CryptoPlay! \n\n - CryptoPlay Team \n\n Visit CryptoPlay at https://cryptoplay.aaj227.repl.co/")
    
    except:
      #Logging into SMTP for emailing

      s = smtplib.SMTP("smtp.gmail.com", 587)
      s.starttls()
      s.login(smtpEmail, smtpPassword)

      s.sendmail(smtpEmail, session["createEmail"], "Subject: Email Verification pin for CryptoPlay \n\n Your CryptoPlay pin is: " + str(session["pin"]) + "\n\n If you did not request this pin, please ignore this email. \n\n Thank you for using CryptoPlay! \n\n - CryptoPlay Team \n\n Visit CryptoPlay at https://cryptoplay.aaj227.repl.co/")

    session["emailFlag"] = 0
  
  if request.method == "POST":
    pin = request.form.get("pin")
    if session["tries"] > 4:
      insertIntoAuditTrail(session["createEmail"], "Too Many Tries")
      return redirect("/verifyEmail#tooManyTriesModal")

    if pin != None:
   
      if pin == str(session["pin"]):
        ref.child("Users/" + session["firebaseCreateEmail"]).set(session["createPassword"])

        mycursor = conn.cursor()

        try:

          sql = "INSERT INTO balances (username, balance) VALUES (%s, %s)"
          val = (session["createEmail"], 1000000)

          mycursor.execute(sql, val)

          conn.commit()

        except:
          return redirect("/verifyEmail#refreshModal")
        session["tries"] = 0
        insertIntoAuditTrail(session["createEmail"], "Signup")
        return redirect("signup#accountCreatedModal")
      else:
        session["tries"] = session["tries"] + 1
        return redirect("/verifyEmail#incorrectPinModal")

  return render_template("verifyEmail.html")

@app.route('/buy/<id>', methods = ["GET", "POST"])
def buy(id):
  mycursor = conn.cursor()
  sql = "SELECT * from coins where id = " + id
  mycursor.execute(sql)
  coin = mycursor.fetchone()

  coinName = coin[1]
  coinPrice = getCoinPrice(coinName)
  coinInit = coin[2]
  coinId = coin[0]

  mycursor = conn.cursor()
  sql = "SELECT * from balances where username = '" + session["email"] + "'"
  mycursor.execute(sql)
  balance = mycursor.fetchone()

  balance = balance[2]

  return render_template("buy.html", coinInit=coinInit, vcoins=session["vcoins"], url_for=url_for, coinPrice=coinPrice, coinName=coinName, coinId=coinId, balance=balance)

@app.route('/sell/<id>', methods = ["GET", "POST"])
def sell(id):
  mycursor = conn.cursor()
  sql = "SELECT * from coins where id = " + id
  mycursor.execute(sql)
  coin = mycursor.fetchone()

  coinName = coin[1]
  coinPrice = getCoinPrice(coinName)
  coinInit = coin[2]
  coinId = coin[0]

  mycursor = conn.cursor()
  sql = "SELECT * from holdings where username = '" + session["email"] + "' and coin_id = " + str(coinId)
  mycursor.execute(sql)
  coinBal = mycursor.fetchone()

  # Try to get the coin balance, if it doesn't exist, set it to 0

  try:
    coinBal = coinBal[3]
    coinBal = float(coinBal)
  except:
    coinBal = 0

  return render_template("sell.html", coinInit=coinInit, vcoins=session["vcoins"], url_for=url_for, coinPrice=coinPrice, coinName=coinName, coinId=coinId, coinBal=coinBal)

@cache.cached(timeout=300)
def getCoinPrice(coinName):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coinName}&vs_currencies=inr"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    data = response.json()
    print(data)
    price = data[coinName.lower()]['inr']
    
    price = float(price)
    price = round(price, 2)
    return price

@cache.cached(timeout=300)
def getCoinPriceFromId(coinId):

  mycursor = conn.cursor()
  sql = "SELECT * from coins where id = " + str(coinId)
  mycursor.execute(sql)
  coin = mycursor.fetchone()

  coinName = coin[1]

  url = f"https://api.coingecko.com/api/v3/simple/price?ids={coinName}&vs_currencies=inr"
  headers = {'User-Agent': 'Mozilla/5.0'}
  response = requests.get(url, headers=headers)
  data = response.json()
  print(data)
  price = data[coinName.lower()]['inr']

  price = float(price)
  price = round(price, 2)

  return price

@app.route('/buyOrder/<id>/<inrVal>', methods = ["GET", "POST"])
def buyOrder(id, inrVal):

  session["balance"] = getUserBalance(session["email"])

  if float(inrVal) > session["balance"]:
    return redirect("/buy/" + id + "#insufficientFundsModal")

  else:

    mycursor = conn.cursor()
    sql = "update balances set balance = balance - "+ inrVal +" where username = '"+ session["email"] +"'"

    mycursor.execute(sql)
    conn.commit()

    session["coinAmt"] = float(inrVal)/getCoinPriceFromId(id)

    mycursor = conn.cursor()
    sql = "select * from holdings where username = '"+ session["email"] +"' and coin_id = "+ id
    mycursor.execute(sql)
    result = mycursor.fetchall()

    if len(result) <= 0:

      sql = "insert into holdings (holding_id, username, coin_id, coin_amount) Values (default, '"+ session["email"] +"', "+ id +", "+ str(session["coinAmt"]) +")"
      mycursor.execute(sql)
      conn.commit()

    else:

      sql = "update holdings set coin_amount = coin_amount + "+ str(session["coinAmt"]) +" where username = '"+ session["email"] +"' and coin_id = "+ id
      mycursor.execute(sql)
      conn.commit()

    mycursor = conn.cursor()
    sql = "insert into transactions (transaction_id, username, value, coin_id, coin_amount, transaction_type) Values (default, '"+ session["email"] +"', "+ inrVal +", "+ id +", "+ str(session["coinAmt"]) +", 'buy')"
    mycursor.execute(sql)
    conn.commit()

    insertIntoAuditTrail(session["email"], "Buy")

    return redirect("/buy/" + id + "#successModal")

@app.route('/sellOrder/<id>/<coinAmt>', methods = ["GET", "POST"])
def sellOrder(id, coinAmt):

  session["coinBal"] = getCoinHoldings(session["email"], id)

  if float(coinAmt) > session["coinBal"]:
    return redirect("/sell/" + id + "#insufficientFundsModal")

  else:

    session["coinVal"] = getCoinPriceFromId(id) * float(coinAmt)

    mycursor = conn.cursor()
    sql = "update balances set balance = balance + "+ str(session["coinVal"]) +" where username = '"+ session["email"] +"'"

    mycursor.execute(sql)
    conn.commit()

    sql = "update holdings set coin_amount = coin_amount - "+ coinAmt +" where username = '"+ session["email"] +"' and coin_id = "+ id
    mycursor.execute(sql)
    conn.commit()

    mycursor = conn.cursor()
    sql = "insert into transactions (transaction_id, username, value, coin_id, coin_amount, transaction_type) Values (default, '"+ session["email"] +"', "+ str(session["coinVal"]) +", "+ id +", "+ coinAmt +", 'sell')"
    mycursor.execute(sql)
    conn.commit()

    insertIntoAuditTrail(session["email"], "Sell")

    return redirect("/sell/" + id + "#successModal")

def getUserBalance(username):
  mycursor = conn.cursor()
  sql = "SELECT * from balances where username = '" + username + "'"
  mycursor.execute(sql)
  balance = mycursor.fetchone()

  return balance[2]

def getCoinHoldings(username, coinId):
  mycursor = conn.cursor()
  sql = "SELECT * from holdings where username = '" + username + "' and coin_id = " + str(coinId)
  mycursor.execute(sql)
  holdings = mycursor.fetchone()

  #Adding try catch to handle the case when the user has no holdings of the coin
  
  try:
    return holdings[3]
  except:
    return 0
  
@app.route('/transactions')
def transactions():
  mycursor = conn.cursor()
  sql = "SELECT * FROM transactions WHERE username = '" + session["email"] + "' ORDER BY transaction_id DESC LIMIT 10"
  mycursor.execute(sql)
  transactions = mycursor.fetchall()

  body = ""

  for transaction in transactions:
    coin = getCoinNameFromId(transaction[3])
    if transaction[5] == "buy":
      body += "<div class='card' style='color:green'> <h3> You bought " + str(transaction[4]) + " " + coin + " for ₹" + str(transaction[2]) + " </h3> </div> <br><br>"
    else:
      body += "<div class='card' style='color:red'> <h3> You sold " + str(transaction[4]) + " " + coin + " for ₹" + str(transaction[2]) + " </h3> </div> <br><br>"

  return render_template("transactions.html", transactions=transactions, body=body, vcoins=session["vcoins"], profileSeed=session["email"].split("@")[0])

def getCoinNameFromId(coinId):
  mycursor = conn.cursor()
  sql = "SELECT * from coins where id = " + str(coinId)
  mycursor.execute(sql)
  coin = mycursor.fetchone()

  return coin[1]

@app.route('/leaderboard')
def leaderboard():
  mycursor = conn.cursor()
  sql = "SELECT * FROM balances ORDER BY balance DESC LIMIT 10"
  mycursor.execute(sql)
  balances = mycursor.fetchall()

  body = ""

  for balance in balances:
    body += "<div class='card'> <h3> " + str(obfuscate_email(balance[1])) + " - ₹" + str(balance[2]) + " </h3> </div> <br><br>"

  return render_template("leaderboard.html", body=body, vcoins=session["vcoins"], profileSeed=session["email"].split("@")[0])
  
def obfuscate_email(email):
    parts = email.split('@')
    username = parts[0]
    domain = parts[1]
    obfuscated = username[0] + '*'*(len(username)-2) + username[-1] + '@' + domain
    return obfuscated

# Audit trail function

def insertIntoAuditTrail(username, action):
  try:
    mycursor = conn.cursor()
    sql = "insert into audit_trail (audit_id, username, action) Values (default, '"+ username +"', '"+ action +"')"
    mycursor.execute(sql)
    conn.commit()
  except:
    mydb = pooling.MySQLConnectionPool(
          pool_name="my_pool",
          pool_size=32,
          host=dbHost,
          user=dbUser,
          password=dbPassword,
          database=dbSchema
      )

    conn = mydb.get_connection()
    mycursor = conn.cursor()
    sql = "insert into audit_trail (audit_id, username, action) Values (default, '"+ username +"', '"+ action +"')"
    mycursor.execute(sql)
    conn.commit()

@app.route('/visit', methods = ["GET", "POST"])
def visiting():
  return render_template("visiting.html")

# Configure the properties file to get the DB credentials

configs = Properties()
with open('allCreds/config.properties', 'rb') as config_file:
    configs.load(config_file)

# Getting DB crdentials from the properties file

global production

production = configs.get("production").data

if production == "true" or production == "True":
  
  #running the app on server
  app.run(host='0.0.0.0', port=443, ssl_context=('cert.pem', 'private.key'))
else:

  #running the app on server
  app.run(host='0.0.0.0')