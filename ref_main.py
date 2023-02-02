#Importing libraries

from flask import Flask, request, render_template, session, redirect, url_for
import firebase_admin
from firebase_admin import db
import mysql.connector
from jproperties import Properties
from flask_session import Session
import smtplib
import random
from markupsafe import Markup

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

cred_obj = firebase_admin.credentials.Certificate('strict-todo-firebase-adminsdk-zmgtw-9b2375558d.json')
default_app = firebase_admin.initialize_app(cred_obj, {'databaseURL':"https://strict-todo-default-rtdb.firebaseio.com/", 'storageBucket': 'strict-todo.appspot.com'})

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

#defining the first main function "Index"

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
          insertIntoAuditTrail("login")
          return user()
        
        # A condition to tell if the credentials entered are invalid
        else:
          return invalid()

    # rendering the form.html for the login page
  return render_template("index.html")

# This function shows if the credentials entered by a user are incorrect
def invalid():

  # rendering the invalid.html which shows the text about invalid credentials
  return redirect("/#openModal")

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

  sql = "SELECT * from tasks where username = " + "'" + session["email"] + "' and task_flag = 1"
  mycursor.execute(sql)
  tasks = mycursor.fetchall()

  body=""
  for k in tasks:
    body += "<div class='card'> <h3>"+ k[1]+"</h3> <h5> "+ k[2] +" </h5> <br> <a href='/delete/"+ str(k[0]) +"'> <button class='colored'> Delete </button> <a href='/complete/"+ str(k[0]) +"'> <button class='colored'> Mark as complete </button> </a> <a href='/wontdo/"+ str(k[0]) +"'> <button class='colored'> Won't Do </button> </a> </div> <br> <br>"  

  return render_template("user.html", vcoins = session["vcoins"], tasks=tasks, body=body, profileSeed=session["email"].split("@")[0])

@app.route('/logout', methods = ["GET", "POST"])
def logout():
  insertIntoAuditTrail("logout")
  session.clear()
  return redirect(url_for("index"))

@app.route('/createTask', methods = ["GET", "POST"])
def createTask():
  if session["vcoins"] > 20:
    if request.method == "POST":
      title = request.form.get("title")
      description = request.form.get("description")

      mydb = mysql.connector.connect(
                  host=dbHost,
                  user=dbUser,
                  password=dbPassword,
                  database=dbSchema)

      mycursor = mydb.cursor()

      sql = "INSERT INTO tasks (task_id, title, description, time, username, task_flag) VALUES (default, %s, %s, sysdate(), %s, 1)"
      val = (title, Markup(description).unescape(), session["email"])

      mycursor.execute(sql, val)

      mydb.commit()

      insertIntoAuditTrail("createTask")

      return redirect(url_for("index"))

    return render_template("createTask.html")
  
  else:
    return redirect("/#insufficientVcoinsModal")

@app.route('/delete/<id>', methods = ["GET", "POST"])
def delete(id):
  try:
    mydb = mysql.connector.connect(
                  host=dbHost,
                  user=dbUser,
                  password=dbPassword,
                  database=dbSchema)

    mycursor = mydb.cursor()

    sql = "SELECT username from tasks where task_id = " + id

    mycursor.execute(sql)

    username = mycursor.fetchone()

    print(username)

    if session["email"] == username[0]:

      sql = "UPDATE tasks SET task_flag = 0 where task_id = " + id

      mycursor.execute(sql)

      mydb.commit()

      insertIntoAuditTrail("deleteTask")

      return redirect(url_for("index"))

    else:
      return redirect(url_for("unauthorized"))

  except:
    return redirect(url_for("unauthorized"))

@app.route('/complete/<id>', methods = ["GET", "POST"])
def complete(id):
  try:

    mydb = mysql.connector.connect(
                  host=dbHost,
                  user=dbUser,
                  password=dbPassword,
                  database=dbSchema)

    mycursor = mydb.cursor()

    sql = "SELECT username from tasks where task_id = " + id

    mycursor.execute(sql)

    username = mycursor.fetchone()

    print(username)

    if session["email"] == username[0]:

      sql = "UPDATE tasks SET task_flag = 2 WHERE task_id = " + id

      mycursor.execute(sql)

      mydb.commit()

      sql = "UPDATE balances SET balance = balance + 10 WHERE username = " + "'" + session["email"] + "'"

      mycursor.execute(sql)

      mydb.commit()

      insertIntoAuditTrail("completeTask")

      return redirect(url_for("index"))

    else:

      return redirect(url_for("unauthorized"))

  except:

    return redirect(url_for("unauthorized"))

@app.route('/wontdo/<id>', methods = ["GET", "POST"])
def wontdo(id):
  try:

    mydb = mysql.connector.connect(
                  host=dbHost,
                  user=dbUser,
                  password=dbPassword,
                  database=dbSchema)

    mycursor = mydb.cursor()

    sql = "SELECT username from tasks where task_id = " + id

    mycursor.execute(sql)

    username = mycursor.fetchone()

    print(username)

    if session["email"] == username[0]:

      sql = "UPDATE tasks SET task_flag = -1 WHERE task_id = " + id

      mycursor.execute(sql)

      mydb.commit()

      sql = "UPDATE balances SET balance = balance - 20 WHERE username = " + "'" + session["email"] + "'"

      mycursor.execute(sql)

      mydb.commit()

      insertIntoAuditTrail("wontdoTask")

      return redirect(url_for("index"))

    else:

      return redirect(url_for("unauthorized"))

  except:

    return redirect(url_for("unauthorized"))

@app.route('/incomplete/<id>', methods = ["GET", "POST"])
def incomplete(id):
  try:
      
    mydb = mysql.connector.connect(
                  host=dbHost,
                  user=dbUser,
                  password=dbPassword,
                  database=dbSchema)

    mycursor = mydb.cursor()

    sql = "SELECT username from tasks where task_id = " + id

    mycursor.execute(sql)

    username = mycursor.fetchone()

    print(username)

    if session["email"] == username[0]:

      sql = "UPDATE tasks SET task_flag = 1 WHERE task_id = " + id

      mycursor.execute(sql)

      mydb.commit()

      sql = "UPDATE balances SET balance = balance - 10 WHERE username = " + "'" + session["email"] + "'"

      mycursor.execute(sql)

      mydb.commit()

      insertIntoAuditTrail("incompleteTask")

      return redirect(url_for("completedTasks"))

    else:
        return redirect(url_for("unauthorized"))

  except:
    return redirect(url_for("unauthorized"))

@app.route('/completedTasks', methods = ["GET", "POST"])
def completedTasks():
  mydb = mysql.connector.connect(
                host=dbHost,
                user=dbUser,
                password=dbPassword,
                database=dbSchema)

  mycursor = mydb.cursor()

  sql = "SELECT * from tasks where username = " + "'" + session["email"] + "' and task_flag = 2"
  mycursor.execute(sql)
  tasks = mycursor.fetchall()

  body=""
  for k in tasks:
    body += "<div class='card'> <h3>"+ k[1]+"</h3> <h5> "+ k[2] +" </h5> <br> <a href='/delete/"+ str(k[0]) +"'> <button class='colored'> Delete </button> <a href='/incomplete/"+ str(k[0]) +"'> <button class='colored'> Mark as incomplete </button> </a> </div> <br> <br>"  

  return render_template("completedTasks.html", tasks=tasks, body=body)

@app.route('/wontdoTasks', methods = ["GET", "POST"])
def wontdoTasks():
  mydb = mysql.connector.connect(
                host=dbHost,
                user=dbUser,
                password=dbPassword,
                database=dbSchema)

  mycursor = mydb.cursor()

  sql = "SELECT * from tasks where username = " + "'" + session["email"] + "' and task_flag = -1"
  mycursor.execute(sql)
  tasks = mycursor.fetchall()

  body=""
  for k in tasks:
    body += "<div class='card'> <h3>"+ k[1]+"</h3> <h5> "+ k[2] +" </h5> <br> <a href='/complete/"+ str(k[0]) +"'> <button class='colored'> Mark as Complete </button> </a> </div> <br> <br>"  

  return render_template("wontdoTasks.html", tasks=tasks, body=body)

@app.route('/trash', methods = ["GET", "POST"])
def trash():
  mydb = mysql.connector.connect(
                host=dbHost,
                user=dbUser,
                password=dbPassword,
                database=dbSchema)

  mycursor = mydb.cursor()

  sql = "SELECT * from tasks where username = " + "'" + session["email"] + "' and task_flag = 0"
  mycursor.execute(sql)
  tasks = mycursor.fetchall()

  body=""
  for k in tasks:
    body += "<div class='card'> <h3>"+ k[1]+"</h3> <h5> "+ k[2] +" </h5> <br> <a href='/deletePermanent/"+ str(k[0]) +"'> <button class='colored'> Delete Permanently </button> <a href='/restore/"+ str(k[0]) +"'> <button class='colored'> Restore </button> </a> </div> <br> <br>"  

  return render_template("trash.html", tasks=tasks, body=body)

@app.route('/restore/<id>', methods = ["GET", "POST"])
def restore(id):
  try:
    
    mydb = mysql.connector.connect(
                  host=dbHost,
                  user=dbUser,
                  password=dbPassword,
                  database=dbSchema)

    mycursor = mydb.cursor()

    sql = "SELECT username from tasks where task_id = " + id

    mycursor.execute(sql)

    username = mycursor.fetchone()

    print(username)

    if session["email"] == username[0]:

      sql = "UPDATE tasks SET task_flag = 1 WHERE task_id = " + id

      mycursor.execute(sql)

      mydb.commit()

      insertIntoAuditTrail("restoreTask")

      return redirect(url_for("trash"))
    
    else:
      return redirect(url_for("unauthorized"))

  except:
    return redirect(url_for("unauthorized"))

@app.route('/restoreAll', methods = ["GET", "POST"])
def restoreAll():
  mydb = mysql.connector.connect(
                host=dbHost,
                user=dbUser,
                password=dbPassword,
                database=dbSchema)

  mycursor = mydb.cursor()

  sql = "UPDATE tasks SET task_flag = 1 WHERE username = " + "'" + session["email"] + "'"

  mycursor.execute(sql)

  mydb.commit()

  insertIntoAuditTrail("restoreAllTasks")

  return redirect(url_for("trash"))

@app.route('/deletePermanent/<id>', methods = ["GET", "POST"])
def deletePermanent(id):
  try:
    mydb = mysql.connector.connect(
                  host=dbHost,
                  user=dbUser,
                  password=dbPassword,
                  database=dbSchema)

    mycursor = mydb.cursor()

    sql = "SELECT username from tasks where task_id = " + id

    mycursor.execute(sql)

    username = mycursor.fetchone()

    print(username)

    if session["email"] == username[0]:

      sql = "DELETE FROM tasks WHERE task_id = " + id

      mycursor.execute(sql)

      mydb.commit()

      insertIntoAuditTrail("deletePermanentTask")

      return redirect(url_for("trash"))
    
    else:
      return redirect(url_for("unauthorized"))
  
  except:
    return redirect(url_for("unauthorized"))

@app.route('/deletePermanentAll', methods = ["GET", "POST"])
def deletePermanentAll():
  mydb = mysql.connector.connect(
                host=dbHost,
                user=dbUser,
                password=dbPassword,
                database=dbSchema)

  mycursor = mydb.cursor()

  sql = "DELETE FROM tasks WHERE username = " + "'" + session["email"] + "' and task_flag = 0"

  mycursor.execute(sql)

  mydb.commit()

  insertIntoAuditTrail("deletePermanentAllTasks")

  return redirect(url_for("trash"))

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
            insertIntoAuditTrail("signup")
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
      insertIntoAuditTrail("changePassword")
      return redirect("/changePassword#successModal")
        
    else:
      return redirect("/changePassword#incorrectPasswordModal")
  return render_template("changePassword.html")

@app.route('/unauthorized', methods = ["GET", "POST"])
def unauthorized():
  return render_template("unauthorized.html")

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
        val = (session["createEmail"], 100)

        mycursor.execute(sql, val)

        mydb.commit()

        insertIntoAuditTrail("verifyEmail")
        return redirect("signup#accountCreatedModal")
      else:
        return redirect("/verifyEmail#incorrectPinModal")

  return render_template("verifyEmail.html")

def insertIntoAuditTrail(action):
  mydb = mysql.connector.connect(
    host=dbHost,
    user=dbUser,
    password=dbPassword,
    database=dbSchema)

  mycursor = mydb.cursor()

  session["ip"] = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)   

  try:
    sql = "INSERT INTO audit_trail (username, action, ip_address) VALUES (%s, %s, %s)"
    val = (session["email"], action, session["ip"])
  except:
    session["email"] = ""
    sql = "INSERT INTO audit_trail (username, action, ip_address) VALUES (%s, %s, %s)"
    val = (session["email"], action, session["ip"])

  mycursor.execute(sql, val, session["ip"])

  mydb.commit()

#running the app on server
app.run(host='0.0.0.0', port='443', ssl_context=('ssl.pem', 'private.key'))