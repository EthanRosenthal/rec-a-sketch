"""
Functions for crawling Sketchfab to grab model names, likes, or tags.
"""

import argparse
import csv
from collections import namedtuple
import os
import time

import requests
from selenium import webdriver
from six.moves import input
import yaml

def load_browser(chromedriver):
    """Start new global browser session"""
    global BROWSER
    BROWSER = webdriver.Chrome(chromedriver)
    BROWSER.maximize_window()

def load_config(filename):
    """
    Load relevant parts of configuration file into global variables
    """
    config = yaml.load(open(filename, 'r'))
    os.environ['webdriver.chrome.driver'] = config['chromedriver']
    global PARENT_CATALOG_URL
    PARENT_CATALOG_URL = config['PARENT_CATALOG_URL']
    global BASE_MODEL_URL
    BASE_MODEL_URL = config['BASE_MODEL_URL']
    global BASE_LIKES_URL
    BASE_LIKES_URL = config['BASE_LIKES_URL']
    global LIKE_LIMIT
    LIKE_LIMIT = config['LIKE_LIMIT']

    return config


def get_item_list(default_list_len=24):
    """For current page, grab all item elements"""
    elem = BROWSER.find_element_by_xpath("//div[@class='infinite-grid']")
    item_list = elem.find_elements_by_xpath(".//li[@class='item']")
    if len(item_list) < default_list_len:
        # Wait a little bit for it to load.
        time.sleep(5)
        return get_item_list()
    else:
        return item_list


def get_page_models(page):
    """For a given page number, collect urls for all models on that page"""
    # Browse all models, order by most liked
    url = PARENT_CATALOG_URL + str(page)

    BROWSER.get(url)
    item_list = get_item_list()

    model_tracker = []
    Model = namedtuple('Model', ['name', 'mid'])
    this_is_the_end = False
    for item in item_list:
        mid = item.get_attribute('data-uid')

        name = item.find_element_by_xpath(".//meta[@itemprop='name']")\
                        .get_attribute('content')
        like_class = ('help like-button star-like-button '
                      'popover-container model-card-like-button '
                      'model-card-stats')
        likes = item.find_element_by_xpath(".//div[@class='{}']".format(like_class))
        likes = likes.text
        if likes.endswith('k'):
            likes = int(float(likes.rstrip('k')) * 1000)
        else:
            likes = int(likes)

        if likes >= LIKE_LIMIT:
            model_tracker.append(Model(name, mid))
        else:
            this_is_the_end = True
            break

    return model_tracker, this_is_the_end


def collect_model_urls(fileout, chromedriver):
    """Loop from page to page grabbing urls to Sketchfab models"""
    load_browser(chromedriver)
    page = 1
    full_catalog = []
    if os.path.isfile(fileout):
        valid = False
        while not valid:
            delete = input(('Model url file {} already exists. '
                            'Do you want to overwrite it? (y/n)\n')\
                            .format(fileout))
            if delete.lower() == 'y':
                valid = True
                os.remove(fileout)
            elif delete.lower() == 'n':
                fileout = input('Please enter a new filename.\n')
                valid = True
                pass
            else:
                print('Need to enter y/n!')

    done = False
    f = open(fileout, 'a', newline='')
    modelwriter = csv.writer(f, delimiter='|', quotechar='\\',
                             quoting=csv.QUOTE_MINIMAL)
    modelwriter.writerow(['name', 'mid'])
    while True:
        time.sleep(2) # Try to be nice
        print('Grabbing info from page {}'.format(page))
        current_models, end = get_page_models(page)
        if end:
            break
        for model in current_models:
            print(model)
            modelwriter.writerow(list(model))
        page += 1
    f.close()
    print('All done.')


def get_model_likes(mid, User, count=24):
    """
    Query Sketchfab API to grab likes for each model.

    Params
    ------

    mid : str
        Unique model ID
    User : namedtuple (name, uid)
        User namedtuple class with a user name and a unique user ID
    count : int, (optional)
        Number of likes requested to be returned by the API. 24 seems to be the
        max.

    Returns
    -------
    users : list
        List of User tuples containing all users that liked mid.

    Inspired by http://www.gregreda.com/2015/02/15/web-scraping-finding-the-api/

    for example: "https://sketchfab.com/i/likes?count=24&model=034a1a146e304161b7c45b9354ed2dfd&offset=48"
    returns the SECOND 24 users for the likes for model
    034a1a146e304161b7c45b9354ed2dfd
    In return payload, if there's not 'next' key, then there's no more likes left.
    """

    done = False
    params = {'model':mid, 'count':count, 'offset':0}
    users = []
    while not done:
        try:
            response = requests.get(BASE_LIKES_URL, params=params).json()
            results = response['results']
            for result in results:
                # Grab username instead.
                # Good to store for getting url later down the line.
                name = result['username']
                uid = result['uid']
                users.append(User(name, uid))
            if not response['next']:
                done = True
                if len(users) % count != len(results):
                    print('Might be missing some likes on {}'.format(mid))
            else:
                # Grab the next batch of likes
                params['offset'] = params['offset'] + count

        except:
            done = True
            print('Error on mid: {}'.format(mid))
    return users


def write_model_likes(filename, model_name, mid, user_set):
    """Append set of model likes to filename"""
    with open(filename, 'a') as fout:
        print('Likes:')
        writer = csv.writer(fout, delimiter='|', quotechar='\\',
                            quoting=csv.QUOTE_MINIMAL)
        for user in user_set:
            line = [model_name, mid, user.name, user.uid]
            writer.writerow(line)
            print('\t' + '|'.join([x for x in line]))


def get_model_features(url, chromedriver):
    """For given model url, grab categories and tags for that model"""
    try:
        BROWSER.get(url)
        time.sleep(5)
        cats = BROWSER.find_elements_by_xpath("//section[@class='model-meta-row categories']//ul//a")
        cats = [cat.text for cat in cats]

        tags = BROWSER.find_elements_by_xpath("//section[@class='model-meta-row tags']//ul//a")
        tags = [tag.text for tag in tags]
    except:
        print('Difficulty grabbing these features {}'.format(url))
        print('Reload browser and try again')
        cats, tags = None, None
    return cats, tags


def crawl_model_likes(catalog, likes_filename):
    """
    For each model in catalog (model urls), get every user id for every user
    that liked that model
    """
    f = open(catalog, 'r')
    ctr = 0
    # I've been reading Fluent Python and was inspired to create namedtuples.
    User = namedtuple('User', ['uid', 'name'])
    reader = csv.reader(f, delimiter='|', quoting=csv.QUOTE_MINIMAL,
                        quotechar='\\')
    for row in reader:
        ctr += 1
        model_name, mid = row[0], row[1]
        print(', '.join(str(x) for x in [ctr, mid, model_name]))
        users = get_model_likes(mid, User)
        if users:
            write_model_likes(likes_filename, model_name, mid, users)


def crawl_model_features(catalog, chromedriver, features_filename, start=1):
    """
    For each model in catalog (model urls), get categories and tags for that
    model
    """
    load_browser(chromedriver)

    fin = open(catalog, 'r')
    reader = csv.reader(fin, delimiter='|', quoting=csv.QUOTE_MINIMAL,
                        quotechar='\\')
    fout = open(features_filename, 'a')
    writer = csv.writer(fout, delimiter='|', quotechar='\\',
                        quoting=csv.QUOTE_MINIMAL)
    if start == 1:
        writer.writerow(['mid', 'type', 'value'])
    ctr = 0
    for row in reader:
        ctr += 1
        if ctr < start:
            continue
        model_name, mid = row[0], row[1]
        url = BASE_MODEL_URL + mid
        print(', '.join(str(x) for x in [ctr, mid, model_name]))

        cats, tags = get_model_features(url, chromedriver)
        if cats is None and tags is None:
            load_browser(chromedriver)
            time.sleep(5)
            cats, tags = get_model_features(url, chromedriver)
            if cats is None and tags is None:
                print('Cant fix it! break')
                break

        if cats:
            for cat in cats:
                line = [mid, 'category', cat]
                print('\t' + '|'.join([x for x in line]))
                writer.writerow(line)
        if tags:
            for tag in tags:
                line = [mid, 'tag', tag]
                print('\t' + '|'.join([x for x in line]))
                writer.writerow(line)
    fin.close()
    fout.close()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Sketchfab Crawler')
    parser.add_argument('config', help='config file with DB and API params')
    parser.add_argument('--type', help='What\'re we gonna crawl tonight, Brain?')
    parser.add_argument('--start', default=1, type=int,
                        help='What row to start at')

    args = parser.parse_args()

    config = load_config(args.config)

    if args.type == 'urls':
        collect_model_urls(config['model_url_file'], config['chromedriver'])
    elif args.type == 'likes':
        crawl_model_likes(config['model_url_file'], config['likes_file'])
    elif args.type == 'features':
        crawl_model_features(config['model_url_file'], config['chromedriver'],
                         config['model_features_file'], start=args.start)
