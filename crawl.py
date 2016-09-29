import argparse
import csv
from collections import namedtuple
import io
import json
import os
import sys
import time

import requests
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from six.moves import input
import yaml

"""
Here's the plan: go through entire catalog and grab link suffixes and names
for each model. Later, I can spawn multiple browsers to go to each model's
page and grab info.

NOTE: I stopped at page 702 because there were fewer than 5 likes for the
models by that point. I ended up with 16825 models, but the last couple only
had 4 likes. Should add a check for this later on.
"""
#
# chromedriver = '/home/ethan/Documents/linkedin/chromedriver'
# os.environ["webdriver.chrome.driver"] = chromedriver
#
# # Define globals
# # BROWSER = webdriver.Chrome(chromedriver)
# # BROWSER.maximize_window()
# PARENT_CATALOG_URL = 'https://sketchfab.com/models?sort_by=-likeCount&page='
# BASE_MODEL_URL = 'https://sketchfab.com/models/'
# BASE_LIKES_URL = 'https://sketchfab.com/i/likes'

def load_config(filename):
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

def wait_for(condition_function):
    start_time = time.time()
    while time.time() < start_time + 3:
        if condition_function():
            return True
        else:
            time.sleep(0.1)
    raise Exception(
        'Timeout waiting for {}'.format(condition_function.__name__)
    )

class wait_for_page_load(object):

    def __init__(self, browser):
        self.browser = browser

    def __enter__(self):
        self.old_page = self.browser.find_element_by_tag_name('html')

    def page_has_loaded(self):
        new_page = self.browser.find_element_by_tag_name('html')
        return new_page.id != self.old_page.id

    def __exit__(self, *_):
        wait_for(self.page_has_loaded)

def load_more():
    try:
        BROWSER.find_element_by_xpath('//button[@data-action="load-next"]').click()
        return True
    except:
        print('Maybe reached the end of the catalog?')
        return False

def get_item_list():
    elem = BROWSER.find_element_by_xpath("//div[@class='infinite-grid']")
    item_list = elem.find_elements_by_xpath(".//li[@class='item']")
    if len(item_list) < 24:
        # Wait a little bit for it to load.
        time.sleep(5)
        return get_item_list()
    else:
        return item_list


def get_page_models(page):
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
    global BROWSER
    BROWSER = webdriver.Chrome(chromedriver)
    BROWSER.maximize_window()
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

def get_tags(url):
    BROWSER.get(url)
    time.sleep(1)
    # tags = BROWSER.find_elements_by_xpath("//section[@class='model-meta-row categories'].//a[@class='item tag-item]")
    tags = BROWSER.find_elements_by_xpath("//section[@class='model-meta-row categories']//ul//a")
    tags = [tag.text.encode('utf-8') for tag in tags]
    return tags

def models_likes(url):
    BROWSER.get(url)

    time.sleep(5)
    done = False
    while not done:

        like_button = BROWSER.find_element_by_xpath("//div[@class='help likes has-likes']")
        likes = like_button.find_element_by_xpath(".//span[@class='count']")\
                           .text\
                           .encode('utf-8')
        if likes.endswith('k'):
            likes = int(float(likes.rstrip('k')) * 1000)
        else:
            likes = int(likes)
        if likes > 0:
            done = True

    if likes < 5:
        return False, False

    print('number of likes ' + str(likes))
    like_button.click()
    user_set = set()
    User = namedtuple('User', ['uid', 'name'])
    user_set = batch_user_likes(user_set, User, likes)
    tags = get_tags()

    return user_set, tags

def models_likes_api(mid, User):
    """
    Just use the api
    for example: "https://sketchfab.com/i/likes?count=24&model=034a1a146e304161b7c45b9354ed2dfd&offset=48"
    returns the SECOND 24 users for the likes for model 034a1a146e304161b7c45b9354ed2dfd

    In return payload, if there's not 'next' key, then there's no more likes left.
    see http://www.gregreda.com/2015/02/15/web-scraping-finding-the-api/
    """

    done = False
    params = {'model':mid, 'count':24, 'offset':0}
    users = []
    while not done:
        try:
            response = requests.get(BASE_LIKES_URL, params=params).json()
            results = response['results']
            for result in results:
                # name = result['displayName']
                name = result['username'] # Grab username instead.
                                          # Easier for getting url later.
                uid = result['uid']
                users.append(User(name, uid))
            if not response['next']:
                done = True
                if len(users) % 24 != len(results):
                    print('Might be missing some likes on {}'.format(mid))
            else:
                params['offset'] = params['offset'] + 24

        except:
            done = True
            print('Error on mid: {}'.format(mid))
    return users

def batch_user_likes(user_set, User, likes):
    # Do some waiting
    time.sleep(.1)
    if len(user_set) < likes:
        users = BROWSER.find_elements_by_xpath("//div[@class='users suggested-follow']//li[@class='follow-item']")
        # namedtuples are hashable, so we can add them to a set.
        # Finally using something from Fluent Python :)

        # The below loop is shitty because each time we load more users we are
        # still going to loop back over all of the previous ones. Not sure of a
        # better way to handle this. At least the set prevents duplicates.
        for user in users:
            uid = user.get_attribute('data-user').encode('utf-8')
            user_name = user.find_element_by_xpath(".//div[@class='username-wrapper']").text.encode('utf-8')
            user_set.add(User(uid, user_name))
        try:
            load_more = BROWSER.find_element_by_xpath("//button[@class='button btn-small btn-secondary']")
            load_more.click()
        except:
            pass
        batch_user_likes(user_set, User, likes)

    return user_set



def write_model_likes(filename, model_name, model_suffix, user_set):
    # Cannot use io.open and unicode for this
    # http://stackoverflow.com/questions/18449233/2-7-csv-module-wants-unicode-but-doesnt-want-unicode
    with open(filename, 'ab') as fout:
        print('Likes:')
        for user in user_set:
            # line = u'{model_name}|{model_suffix}|{user_name}|{uid}\n'.\
            #        format(**{'model_name':model_name,
            #                'model_suffix':model_suffix,
            #                'user_name':user.name,
            #                'uid':user.uid}).decode('utf-8')
            line = [model_name, model_suffix, user.name, user.uid]
            print('\t' + '|'.join([x for x in line]))
            line = [x.encode('utf-8') for x in line]

            writer = csv.writer(fout, delimiter='|',
                quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(line)
            # fout.write(line)

def write_model_tags(filename, model_name, model_suffix, tags):
    # Maybe not the best way to do things, but write out as json.
    with io.open(filename, 'a', encoding='utf-8') as fout:
        print('Tags')
        line = {'name':model_name, 'mid':model_suffix, 'tags':tags}
        linejson = json.dumps(line, ensure_ascii=False, encoding='utf8') + u'\n'
        print('\t' + linejson.rstrip('\n'))
        fout.write(linejson)


def crawl_model_likes(catalog, likes_filename, tags_filename):
    with io.open(catalog, 'r', encoding='utf-8') as f:
        ctr = 0
        User = namedtuple('User', ['uid', 'name'])
        for line in f:
            print(ctr)
            line_split = line.encode('utf-8').rstrip('\n').split('|')
            name, mid = '|'.join(x for x in line_split[:-1]), line_split[-1]
            # url = BASE_MODEL_URL + mid
            # print url
            print(mid)
            print(name)

            users = models_likes_api(mid, User)

            # user_set, tags = models_likes(url)
            # print users
            # print tags
            if users:
                write_model_likes(likes_filename, name, mid, users)
                # write_model_tags(tags_filename, name, mid, tags)
            ctr += 1

def crawl_model_tags(catalog, tags_filename):
    with io.open(catalog, 'r', encoding='utf-8') as f:
        ctr = 0
        User = namedtuple('User', ['uid', 'name'])
        for line in f:
            print(ctr)
            line_split = line.encode('utf-8').rstrip('\n').split('|')
            name, mid = '|'.join(x for x in line_split[:-1]), line_split[-1]
            url = BASE_MODEL_URL + mid
            print(mid)
            print(name)
            tags = model_tags(url)
            if tags:
                write_model_tags(tags_filename, name, mid, tags)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Sketchfab Crawler')
    parser.add_argument('config', help='config file with DB and API params')
    parser.add_argument('--type', help='What\'re we gonna crawl, Brain?')
    args = parser.parse_args()

    config = load_config(args.config)

    if args.type == 'urls':
        collect_model_urls(config['model_url_file'], config['chromedriver'])
    elif args.type == 'likes':
        crawl_model_likes('catalog.psv', 'likes_v3.psv', 'tags.json')
