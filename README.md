Repo for building [Sketchfab](https://sketchfab.com) recommendations.
Collecting data, training algorithms, and serving recommendations on a website will all be here.

This repo will likely not work for python 2 due to various encoding issues.
For some of the crawling processes, Selenium is used. You must provide a path to your browser driver in ```config.yml``` for this to work.

## Scripts

### ```crawl.py```

Use this to crawl the Sketchfab site and collect data. Currently supports 3 processes as specified by ```--type``` argument:

* urls - Grab the url of every sketchfab model with number of likes >= ```LIKE_LIMIT``` as defined in the ```config```.
* likes - Given collected model urls, collect users who have liked those models.
* features - Given collected model urls, collect categories and tags associated with those models.

All ```crawl.py``` outputs are pipe-separated csv files with ```quoting=csv.QUOTE_MINIMAL``` and ```escapecahr='\\'```

Run like
```bash
python crawl.py config.yml --type urls
```

I ran into lots of issues with timeouts when crawling features. To pick back up on a particular row of the urls file pass ```--start row_number``` as an optional argument.

### ```anonymize.py```

Used to anonymize user_id's in likes data. Granted, one could probably back this out, but this serves as a small barrier of privacy.

To run, you must define a secret key for hashing the user_id's

```bash
python anonymize.py unanonymized_likes.csv anonymized_likes.csv "SECRET KEY"
```
