## Instructions for scraping news stories from the Crowd Counting Consortium

The stories are stored in a Mongo database. You can set up a Mongo DB using Docker
with the following command:

```
docker run -d -p 127.0.0.1:27017:27017 -v $PWD/db:/data/db --name mongodb_ccc mongo
```

You'll also need to download the Crowd Counting Consortium data from their Github repo: https://github.com/nonviolent-action-lab/crowd-counting-consortium/blob/master/ccc_compiled.csv

You can then scrape the articles using `scrape_ccc.py`.