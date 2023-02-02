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