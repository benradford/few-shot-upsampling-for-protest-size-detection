from bs4 import BeautifulSoup
import pandas as pd
import re 
from newspaper import Article, Config
import newspaper
from pymongo import MongoClient
from bson.objectid import ObjectId
import justext


def populate_mongo(ccc, collection):
    """
    Create a record for each article in the Mongo.
    """
    urls = ccc['source_1'].to_list() + ccc['source_2'].to_list() +  ccc['source_3'].to_list()
    urls = [i for i in urls if not pd.isna(i)]

    domains = [re.findall("https?://(.+?)/", i) for i in urls]
    domains = [i[0] if i else "" for i in domains]

    docs = [{"url": i, "domain": j} for i, j in zip(urls, domains)]
    collection.insert_many(docs)


def insert_article(record, collection, config):
    """
    Iterate through the articles in Mongo and scrape each.
    """
    skip_list = ['twitter.com', 'www.instagram.com', 'www.facebook.com']
    if record['domain'] in skip_list:
        return
    if not re.match("http", record['url']):
        return
    if 'error' in record.keys():
        print("skipping old error")
        return
    if 'html' in record.keys():
        print("skipping existing html...")
        
    try:
        print(record['url'])
        article = Article(record['url'],
                         config=config)
        try:
            article.download()
            article.parse()
        except Exception as e:
            error = e
            collection.find_one_and_update({'_id': record['_id']},
                        {'$set':
                         {"error" : str(error)}})
            return
        soup = BeautifulSoup(article.html)
        text = soup.text.strip()
        try:
            text2 = newspaper.fulltext(article.html)
        except:
            text2 = ""
        html = article.html
        title = article.title
        publish_date = article.publish_date
        body = article.text
        images = list(article.images)
        print(article.title)
        # third try, this time with justext
        paragraphs = justext.justext(article.html, 
                             justext.get_stoplist("English"))

        paras = []
        for paragraph in paragraphs:
            if not paragraph.is_boilerplate:
                paras.append(paragraph.text)
        text3 = "\n\n".join(paras)
        
    except Exception as e:
        error = e
        collection.find_one_and_update({'_id': record['_id']},
                        {'$set':
                         {"error" : str(error)}})
        
    if html:
        collection.find_one_and_update({'_id': record['_id']},
                        {'$set':
                         {"html": html,
                          "text": text,     
                          "text2": text2,
                          "text3": text3,
                          "title": title,
                          "publish_date": publish_date,
                          "body": body,
                          "images": images}})
        

if __name__ == "__main__":
    connection = MongoClient()
    db = connection.text
    collection = db['ccc']

    ccc = pd.read_csv("ccc_compiled.csv",
                     #encoding = "UTF-8",
                     engine='python')

    populate_mongo(ccc, collection)

    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
    config = Config()
    config.browser_user_agent = user_agent

    for record in collection.find({"html": {"$exists": False}}):
        insert_article(record, collection)
        