#Importing libraries

import random
from flask import Flask, request, render_template, session, redirect, url_for
import firebase_admin
from firebase_admin import db
import mysql.connector
from jproperties import Properties
from flask_session import Session
import smtplib
from pycoingecko import CoinGeckoAPI

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

global mydb

# Connecting to MySQL DB

mydb = mysql.connector.connect(
                host=dbHost,
                user=dbUser,
                password=dbPassword,
                database=dbSchema)


#preparing credentials and logging into firebase databse to set and get the data

cred_obj = firebase_admin.credentials.Certificate('virtual-crypto-1cfa5-firebase-adminsdk-uwgpx-e9d125f3d5.json')
default_app = firebase_admin.initialize_app(cred_obj, {'databaseURL':"https://virtual-crypto-1cfa5-default-rtdb.firebaseio.com/"})

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

#Logging into SMTP for emailing

s = smtplib.SMTP("smtp.gmail.com", 587)
s.starttls()
s.login(smtpEmail, smtpPassword)

#Initializing the flask app

app = Flask(__name__)

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
       print(session["password"])

       if session["freshEmail"] != "" and session["password"] != "":

        # Getting the password data of user from the database
        
        DBpasswordUser = ref.child("Users/" + session["freshEmail"]).get()

        # A condition to check if the user is an Employee
        if DBpasswordUser == session["password"]:
          session["userType"] = "user"
          return user()
        
        # A condition to tell if the credentials entered are invalid
        else:
          return invalid()

    # rendering the form.html for the login page
  return render_template("index.html")

  # This funtion is for the user

def user():
  mydb = mysql.connector.connect(
                host=dbHost,
                user=dbUser,
                password=dbPassword,
                database=dbSchema)

  mycursor = mydb.cursor()
  sql = "SELECT balance from balances where username = " + "'" + session["email"] + "'"
  mycursor.execute(sql)
  vcoins = mycursor.fetchone()
  try:
    session["vcoins"] = vcoins[0]
  except:
    session["vcoins"] = 0

  mycursor = mydb.cursor()

  sql = "SELECT * from coins"
  mycursor.execute(sql)
  tasks = mycursor.fetchall()

  body=""
  for k in tasks:
    body += "<div class='card'> <h3>"+ k[1]+" ("+ k[2] +") </h3> <a href=/buy/"+ str(k[0]) +"> <button class='buy'> Buy </button> </a> <a href=/sell/"+ str(k[0]) +"> <button class='sell'> Sell </button> </a> </div> <br> <br>"  

  return render_template("user.html", vcoins = session["vcoins"], tasks=tasks, body=body, profileSeed=session["email"].split("@")[0])

# This function is to log out the user

@app.route('/logout', methods = ["GET", "POST"])
def logout():
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

      checkAccount = ref.child("Users/" + firebaseCreateEmail).get()

      if createEmail != None and createPassword != None:
        if "@" and "," in firebaseCreateEmail:
          if checkAccount == None or checkAccount == "":

            session["emailFlag"] = 1
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
  newPassword = request.form.get("newPassword")
  DBpasswordUser = ref.child("Users/" + session["freshEmail"]).get()

  if oldPassword and newPassword != None:
    if oldPassword == DBpasswordUser:
      ref.child("Users/" + session["freshEmail"]).set(newPassword)
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

    try:
      s.sendmail(smtpEmail, session["createEmail"], "Subject: Email Verification pin for Todofy \n\n Your Todofy pin is: " + str(session["pin"]) + "\n\n If you did not request this pin, please ignore this email. \n\n Thank you for using Todofy! \n\n - Todofy Team \n\n Visit Todofy at https://todofy.live/")
    
    except:
      #Logging into SMTP for emailing

      s = smtplib.SMTP("smtp.gmail.com", 587)
      s.starttls()
      s.login(smtpEmail, smtpPassword)

      s.sendmail(smtpEmail, session["createEmail"], "Subject: Email Verification pin for Todofy \n\n Your Todofy pin is: " + str(session["pin"]) + "\n\n If you did not request this pin, please ignore this email. \n\n Thank you for using Todofy! \n\n - Todofy Team \n\n Visit Todofy at https://todofy.live/")

    session["emailFlag"] = 0
  
  if request.method == "POST":
    pin = request.form.get("pin")

    if pin != None:
   
      if pin == str(session["pin"]):
        ref.child("Users/" + session["firebaseCreateEmail"]).set(session["createPassword"])

        mydb = mysql.connector.connect(
            host=dbHost,
            user=dbUser,
            password=dbPassword,
            database=dbSchema)

        mycursor = mydb.cursor()

        sql = "INSERT INTO balances (username, balance) VALUES (%s, %s)"
        val = (session["createEmail"], 10000000)

        mycursor.execute(sql, val)

        mydb.commit()

        return redirect("signup#accountCreatedModal")
      else:
        return redirect("/verifyEmail#incorrectPinModal")

  return render_template("verifyEmail.html")

@app.route('/buy/<id>', methods = ["GET", "POST"])
def buy(id):
  mycursor = mydb.cursor()
  sql = "SELECT * from coins where id = " + id
  mycursor.execute(sql)
  coin = mycursor.fetchone()

  coinName = coin[1]
  coinPrice = getCoinPrice(coinName)
  coinInit = coin[2]
  coinId = coin[0]

  mycursor = mydb.cursor()
  sql = "SELECT * from balances where username = '" + session["email"] + "'"
  mycursor.execute(sql)
  balance = mycursor.fetchone()

  balance = balance[2]

  return render_template("buy.html", coinInit=coinInit, vcoins=session["vcoins"], url_for=url_for, coinPrice=coinPrice, coinName=coinName, coinId=coinId, balance=balance)

@app.route('/sell/<id>', methods = ["GET", "POST"])
def sell(id):
  mycursor = mydb.cursor()
  sql = "SELECT * from coins where id = " + id
  mycursor.execute(sql)
  coin = mycursor.fetchone()

  coinName = coin[1]
  coinPrice = getCoinPrice(coinName)
  coinInit = coin[2]
  coinId = coin[0]

  mycursor = mydb.cursor()
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

def getCoinPrice(coinName):
  
  cg_client = CoinGeckoAPI()
  price = cg_client.get_price(ids = coinName, vs_currencies = "inr")
  
  return price[coinName.lower()]["inr"]

def getCoinPriceFromId(coinId):

  mycursor = mydb.cursor()
  sql = "SELECT * from coins where id = " + str(coinId)
  mycursor.execute(sql)
  coin = mycursor.fetchone()

  coinName = coin[1]
  
  cg_client = CoinGeckoAPI()
  price = cg_client.get_price(ids = coinName, vs_currencies = "inr")
  
  return price[coinName.lower()]["inr"]

@app.route('/buyOrder/<id>/<inrVal>', methods = ["GET", "POST"])
def buyOrder(id, inrVal):

  session["balance"] = getUserBalance(session["email"])

  if float(inrVal) > session["balance"]:
    return redirect("/buy/" + id + "#insufficientFundsModal")

  else:

    mycursor = mydb.cursor()
    sql = "update balances set balance = balance - "+ inrVal +" where username = '"+ session["email"] +"'"

    mycursor.execute(sql)
    mydb.commit()

    session["coinAmt"] = float(inrVal)/getCoinPriceFromId(id)

    mycursor = mydb.cursor()
    sql = "select * from holdings where username = '"+ session["email"] +"' and coin_id = "+ id
    mycursor.execute(sql)
    result = mycursor.fetchall()

    if len(result) <= 0:

      sql = "insert into holdings (holding_id, username, coin_id, coin_amount) Values (default, '"+ session["email"] +"', "+ id +", "+ str(session["coinAmt"]) +")"
      mycursor.execute(sql)
      mydb.commit()

    else:

      sql = "update holdings set coin_amount = coin_amount + "+ str(session["coinAmt"]) +" where username = '"+ session["email"] +"' and coin_id = "+ id
      mycursor.execute(sql)
      mydb.commit()

    return redirect("/buy/" + id + "#successModal")

@app.route('/sellOrder/<id>/<coinAmt>', methods = ["GET", "POST"])
def sellOrder(id, coinAmt):

  session["coinBal"] = getCoinHoldings(session["email"], id)

  if float(coinAmt) > session["coinBal"]:
    return redirect("/sell/" + id + "#insufficientFundsModal")

  else:

    session["coinVal"] = getCoinPriceFromId(id) * float(coinAmt)

    mycursor = mydb.cursor()
    sql = "update balances set balance = balance + "+ str(session["coinVal"]) +" where username = '"+ session["email"] +"'"

    mycursor.execute(sql)
    mydb.commit()

    sql = "update holdings set coin_amount = coin_amount - "+ coinAmt +" where username = '"+ session["email"] +"' and coin_id = "+ id
    mycursor.execute(sql)
    mydb.commit()

    return redirect("/sell/" + id + "#successModal")

def getUserBalance(username):
  mycursor = mydb.cursor()
  sql = "SELECT * from balances where username = '" + username + "'"
  mycursor.execute(sql)
  balance = mycursor.fetchone()

  return balance[2]

def getCoinHoldings(username, coinId):
  mycursor = mydb.cursor()
  sql = "SELECT * from holdings where username = '" + username + "' and coin_id = " + str(coinId)
  mycursor.execute(sql)
  holdings = mycursor.fetchone()

  #Adding try catch to handle the case when the user has no holdings of the coin
  
  try:
    return holdings[3]
  except:
    return 0
  

#running the app on server
app.run(host='0.0.0.0')