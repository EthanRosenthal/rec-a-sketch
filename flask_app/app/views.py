from flask import render_template, request
import sqlite3

from app import app
from .helpers import (get_mid_names, parse_mid, get_mid_data_from_db,
                      get_recommendations)


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


@app.route('/')
@app.route('/index')
def index():
    conn = connect_db()
    mid_names = get_mid_names(conn)
    mid = parse_mid(request)

    try:
        mid_data = get_mid_data_from_db([mid], conn)[0]
        recs = get_recommendations(mid, conn)
        rec_data = {}
        for (k, v) in recs.items():
            this_data = get_mid_data_from_db(v, conn)
            if this_data:
                rec_data[k] = this_data
        not_found = False
    except:
        mid = None
        mid_data = None
        rec_data = None
        not_found = True

    if not request.args:
        not_found = False

    return render_template('index.html',
        title='Rec-a-Sketch',
        mid=mid,
        mid_data=mid_data,
        rec_data=rec_data,
        mid_and_name=mid_names,
        not_found=not_found
    )

@app.route('/about')
def about():
    return render_template('about.html')
