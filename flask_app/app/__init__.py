import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash

DATABASE = './app/db/recasketch.sqlite'

def connect_db():
    return sqlite3.connect(app.config['DATABASE'])

app = Flask(__name__)
app.config.from_object(__name__)
from app import views
