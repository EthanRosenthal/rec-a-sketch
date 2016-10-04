import argparse
import csv
import hmac

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Anonymize user ids')
    parser.add_argument('urls', help='Output of crawl.py --type urls')
    parser.add_argument('anonymized', help='Anonymized output filename')
    parser.add_argument('key', help='Secret key for hashing of user ids')

    args = parser.parse_args()
    with open(args.urls, 'r') as fin:
        with open(args.anonymized, 'w') as fout:
            reader = csv.reader(fin, delimiter='|', quoting=csv.QUOTE_MINIMAL,
                                quotechar='\\')
            writer = csv.writer(fout, delimiter='|', quoting=csv.QUOTE_MINIMAL,
                                quotechar='\\')
            writer.writerow(['modelname', 'mid', 'uid'])
            key = bytes(args.key, 'utf-8')
            for row in reader:
                # Throw away user name
                modelname, mid, uid = row[0], row[1], row[2]
                uid = hmac.new(key, bytes(uid, 'utf8')).hexdigest()
                writer.writerow([modelname, mid, uid])
