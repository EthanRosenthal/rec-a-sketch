import argparse
import collections
import csv
import json
import os
import requests
import time

import pandas as pd
import sqlite3
import yaml


def get_app_base_path():
    return os.path.dirname(os.path.realpath(__file__))


def get_instance_folder_path():
    return os.path.join(get_app_base_path(), 'instance')


def get_mid_data_from_db(mids, conn):
    """Get info on a list of mids"""
    c = conn.cursor()
    midlist = ','.join("'{}'".format(x) for x in mids)
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
    """.format(midlist)
    c.execute(sql)
    conn.commit()
    results = c.fetchall()
    c.close()
    if results:
        ordering = {mid: i for (i, mid) in enumerate(mids)}
        columns = ['mid', 'name', 'thumbnail', 'url']
        mid_data = [{c: v for c, v in zip(columns, r)} for r in results]
        mid_data = sorted(mid_data, key=lambda x: ordering.get(x['mid'], 1000))
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


def load_recs(filename, N=None):
    if N is not None:
        N += 1
    recs = {}
    with open(filename, 'r') as f:
        for line in f:
            lines_recs = line.rstrip('\n').split('|')
            recs[lines_recs[0]] = lines_recs[1:N]
    return recs


def load_mid_and_name(filename):
    mid_and_name = pd.read_csv(filename, sep='|', quoting=csv.QUOTE_MINIMAL,
                               quotechar='\\', names=['model_name', 'mid'])
    mid_and_name = mid_and_name.to_dict('records')
    mid_and_name = sorted(mid_and_name, key=lambda x: x['model_name'])
    return mid_and_name


def load_mid_data(filename):
    return json.load(open(filename), 'r')


def get_mid_data(mid):
    response = requests.get('https://sketchfab.com/i/models/{}'.format(mid))
    status = response.status_code
    response = response.json()
    if status != 200:
        thumb = None
        name = 'NA'
        url = 'NA'
    else:
        thumb = [x['url'] for x in response['thumbnails']['images']
                 if x['width'] == 200 and x['height'] == 200]
        name = response['name']
        url = response['viewerUrl']
        if thumb:
            thumb = thumb[0]
        else:
            thumb = None
    return {'thumbnail': thumb, 'name': name, 'url': url}


def compile_all_mid_data(mid_list):
    all_mid_data = []
    t0 = time.time()
    for i, mid in enumerate(mid_list):
        if i % 50 == 0:
            t1 = time.time()
            print('mid count {}, {} seconds/mid'.format(i, (t1 - t0) / 50))
            t0 = time.time()
        all_mid_data.append(get_mid_data(mid))
    return all_mid_data


def get_and_update_mid_data_table(sqlite_file, mid_data_filename, mid_list):
    all_mid_data = compile_all_mid_data(mid_list)
    df = pd.DataFrame.from_records(all_mid_data)
    df['mid'] = mid_list
    df = df[['mid', 'name', 'thumbnail', 'url']]
    df.to_csv(mid_data_filename, index=False, sep='|', quotechar='\\',
              quoting=csv.QUOTE_MINIMAL)
    create_mid_data_table(sqlite_file, mid_data_filename)


def create_mid_data_table(sqlite_file, mid_data_filename):
    conn = sqlite3.connect(sqlite_file)
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS mid_data')
    conn.commit()
    sql = """
          CREATE TABLE IF NOT EXISTS mid_data (
            mid TEXT PRIMARY KEY,
            name TEXT,
            thumbnail TEXT,
            url TEXT
          )
          """
    c.execute(sql)
    conn.commit()

    df = pd.read_csv(mid_data_filename,
                     sep='|', quotechar='\\',
                     quoting=csv.QUOTE_MINIMAL)
    df.to_sql('mid_data', con=conn, index=False, if_exists='append')
    conn.close()


def filter_recs(recs, mid_data_filename, N=6):
    mid_data = pd.read_csv(mid_data_filename)
    filtered = collections.defaultdict(list)
    for mid, others in recs.iteritems():
        ctr = 0
        idx = 0
        if others:
            while ctr < N:
                other = others[idx]
                if mid_data[mid_data.mid == other].thumbnail is not None:
                    filtered[mid].append(other)
                    ctr += 1
                idx += 1
        else:
            print('No recs for mid = {}'.format(mid))
    return filtered


def write_recs(recs, filename):
    with open(filename, 'w') as f:
        for k, v in recs.items():
            line = '{},{}\n'.format(k, ','.join(x for x in v))
            f.write(line)


def insert_recs(rec_type, filename, sqlite_file):
    """Write recommendations to database as string'd list."""
    recs = load_recs(filename)
    for (k, v) in recs.items():
        recs[k] = ','.join(str(x) for x in v)
    recs = pd.DataFrame(pd.Series(recs), columns=['recommended'])
    recs['type'] = rec_type
    recs.index.name = 'mid'
    conn = sqlite3.connect(sqlite_file)
    recs.to_sql('recommendations', con=conn, if_exists='append')


def insert_modelnames(filename, sqlite_file):
    mid_and_name = pd.read_csv(filename, sep='|', quoting=csv.QUOTE_MINIMAL,
                               quotechar='\\', names=['model_name', 'mid'])
    conn = sqlite3.connect(sqlite_file)
    mid_and_name.to_sql('mid_names', con=conn, index=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='recasketch helpers')
    parser.add_argument('--config',
                        help='Configuration file with data locations.',
                        default='../config.yml')
    parser.add_argument('--task',
                        help='Which helper function to call.\nAvailable '
                             'options include "update_mids", "insert_recs", '
                             'and "insert_modelnames.')
    args = parser.parse_args()

    # Parse config file
    config = yaml.load(open(args.config, 'r'))

    # All data files output from crawl.py
    data_dir = config['data_dir']
    parent_dir = '../..'
    data_files = config['data_files']
    model_url_file = data_files['model_url_file']
    model_url_file = os.path.join(parent_dir, data_dir, model_url_file)

    # All db files associated with recasketch app.
    db_files = config['db_files']
    db_dir = config['db_dir']
    sqlite_file = os.path.join(db_dir, db_files['sqlite_file'])
    mid_data_file = os.path.join(db_dir, db_files['mid_data_file'])
    mid_names_file = os.path.join(db_dir, db_files['mid_names_file'])

    if args.task == 'update_mids':
        model_urls = pd.read_csv(model_url_file, sep='|',
                                 quoting=csv.QUOTE_MINIMAL,
                                 quotechar='\\')
        mid_list = model_urls['mid'].unique().tolist()
        get_and_update_mid_data_table(sqlite_file, mid_data_file, mid_list)
    elif args.task == 'insert_recs':
        for key, filename in db_files['recs'].items():
            filename = os.path.join(db_dir, filename)
            insert_recs(key, filename, sqlite_file)
    elif args.task == 'insert_modelnames':
        insert_modelnames(mid_names_file, sqlite_file)
