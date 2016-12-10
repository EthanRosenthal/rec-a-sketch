from flask import render_template, request
from app import app

import sqlite3


def get_mid_data(mids, conn):
    """Get info on a list of mids"""
    c = conn.cursor()
    mids = ','.join("'{}'".format(x) for x in mids)
    sql = """
        SELECT
          mid,
          name,
          thumbnail,
          url
        FROM mid_data
        WHERE
          mid IN ({})
          AND thumbnail IS NOT NULL
    """.format(mids)
    c.execute(sql)
    conn.commit()
    results = c.fetchall()
    c.close()
    if results:
        columns = ['mid', 'name', 'thumbnail', 'url']
        mid_data = [{c: v for c, v in zip(columns, r)} for r in results]
    else:
        mid_data = []
    return mid_data


def get_recommendations(mid, conn):
    """
    Grab recommendations for a single mid.
    Returns multiple recommendation types as a dictionary.

    Example Return
    --------------
    {
        'l2r': [mid1, mid2, mid3],
        'wrmf': [mid5, mid6, mid7
    }

    """
    c = conn.cursor()
    sql = """
        SELECT
          type,
          recommended
        FROM recommendations
        WHERE
          mid = '{}'
    """.format(mid)
    c.execute(sql)
    results = c.fetchall()
    if results:
        out = []
        for r in results:
            out.append((r[0], [str(x) for x in r[1].split(',')]))
        out = dict(out)
    else:
        out = None
    return out


def get_mid_names(conn):
    """Get small list of mids and names to seed dropdown menu."""
    c = conn.cursor()
    sql = 'SELECT mid, model_name from mid_names'
    c.execute(sql)
    results = c.fetchall()
    c.close()
    # Don't feel like implementing
    # http://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
    # to make a DictCursor. Do by hand.
    return [{'mid': r[0], 'model_name': r[1]} for r in results]

def parse_mid(request):
    """
    Go through funky series of scenarios parsing out the mid
    from the GET request.
    """
    mid = request.args.get('mid')
    if mid is not None:
        return mid

    link = request.args.get('link')
    if link is None or not link:
        return None

    splits = link.split('/')
    mid = splits[-1]

    if splits[-2] != 'models':
        # Link is in funny format. Nothing we can do!
        return None

    return mid



@app.route('/')
@app.route('/index')
def index():
    conn = sqlite3.connect(app.config['DATABASE'])
    mid_names = get_mid_names(conn)
    mid = parse_mid(request)

    try:
        mid_data = get_mid_data([mid], conn)[0]
        recs = get_recommendations(mid, conn)
        rec_data = {}
        for (k, v) in recs.items():
            this_data = get_mid_data(v, conn)
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

    return render_template("index.html",
        title='Rec-a-Sketch',
        mid=mid,
        mid_data=mid_data,
        rec_data=rec_data,
        mid_and_name=mid_names,
        not_found=not_found
    )

@app.route('/about')
def about():
    return render_template("about.html")
