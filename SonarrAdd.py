# SonarrAdd

import urllib2
import sqlite3
import os.path
import json
from lxml import etree
from StringIO import StringIO
import requests

# IMDB Configuration
imdb_url = "http://www.imdb.com"
imdb_watchlist_rss_url = "http://rss.imdb.com/list/ls076808359/"  # Path to RSS Watchlist

# SonarrAdd configuration
db_name = "sonarradd.db"
install_path = ".."  # Directory where sickadd.db will be created
sonarradd_db = install_path + "/" + db_name

# Sonarr Configuration
sonarr_url = "http://localhost"
sonarr_port = "8989"
sonarr_apikey = ".."
sonarr_series_folder = ".."


def db_check():
    if not os.path.isfile(sonarradd_db):
        print "Database does NOT exist"
        db_creation()
    else:
        print "Database does exist"


def db_creation():
    conn = sqlite3.connect(sonarradd_db)
    c = conn.cursor()
    c.execute('''CREATE TABLE imdb_fav (imdb_id TEXT PRIMARY KEY, imdb_name TEXT, in_sonarr INTEGER DEFAULT '0')''')
    c.execute('''CREATE TABLE db_info (db_version NUM)''')
    c.execute("INSERT INTO db_info VALUES (1)")
    conn.commit()
    conn.close()
    print "Database has been created"


def imdb_processing(imdb_watchlist_rss_url):
    imdb_http_status = urllib2.urlopen(imdb_url).getcode()
    if imdb_http_status != 200:
        print "IMDB cannot be contacted. Cancelling IMDB processing"
        return
    response = urllib2.urlopen(imdb_watchlist_rss_url)
    imdb_rss = response.read()
    response.close()
    print "Checking IMDB favorites list"
    conn = sqlite3.connect(sonarradd_db)
    c = conn.cursor()
    tree = etree.parse(StringIO(imdb_rss))
    added = 0
    for item in tree.iter('item'):
        imdb_title = item[1].text
        imdb_link = item[2].text
        imdb_guid = item[3].text
        imdb_id = (imdb_guid[-10:])[:9]
        if "TV Series" in imdb_title or "Mini-Series" in imdb_title:
            c.execute("INSERT OR IGNORE INTO imdb_fav VALUES (?,?,?)", (imdb_id, imdb_title, None))
            conn.commit()
        if c.rowcount > 0:
            added += 1
    if added > 0:
        print "Added %d new show(s) to SonarrAdd database" % added
    else:
        print "Nothing to add!"
    conn.close()


def sonarr_get_list_of_shows():
    print "Retrieving list of series already in Sonarr"
    r = requests.get(sonarr_url+":"+sonarr_port+"/api/series/?apikey="+sonarr_apikey)
    #print r.text
    shows = []
    for i in range(0, len(r.json())):
        shows.append(dict(title=r.json()[i]['title'], imdbId=r.json()[i]['imdbId']))
    #print shows
    return shows


def update_db_in_sonarr(shows):
    print "Updating database: setting state of shows"
    conn = sqlite3.connect(sonarradd_db)
    c = conn.cursor()
    c.execute('UPDATE imdb_fav SET in_sonarr = NULL')
    conn.commit()
    if len(shows) > 0:
        for show in shows:
            show_imdb_id = show['imdbId']
            c.execute('UPDATE imdb_fav SET in_sonarr = 2 WHERE imdb_id = ?', [show_imdb_id])
            conn.commit()
    conn.close()


def push_to_sonarr():
    print "Adding new series to Sonarr"
    conn = sqlite3.connect(sonarradd_db)
    c = conn.cursor()
    c.execute("SELECT imdb_name FROM imdb_fav WHERE in_sonarr IS NULL OR in_sonarr != 2")
    result_set = c.fetchall()
    if len(result_set) > 0:
        for imdb_name_list in result_set:
            imdb_name = imdb_name_list[0]
            edit_imdb_name = imdb_name[0:imdb_name.find('(')-1]
            print "Adding '"+edit_imdb_name+"' to Sonarr"
            data = sonarr_api_series_lookup(edit_imdb_name)
            sonarr_api_add_new_show(data)
    else:
        print "Nothing to add!"


def sonarr_api_series_lookup(name):
    results = requests.get(sonarr_url+":"+sonarr_port+"/api/series/lookup?term="+name+"&apikey="+sonarr_apikey)
    first_result = results.json()[0]
    title = first_result['title']
    titleSlug = first_result['titleSlug']
    qualityProfileId = 1
    tvdbId = first_result['tvdbId']
    imdbId = first_result['imdbId']
    seasons = first_result['seasons']
    for season in seasons:
        season['monitored'] = True
    seasonFolder = True
    monitored = True
    rootFolderPath = sonarr_series_folder
    needed_info_to_add = dict(title=title,
                              seasons=seasons,
                              rootFolderPath=rootFolderPath,
                              qualityProfileId=qualityProfileId,
                              seasonFolder=seasonFolder,
                              monitored=monitored,
                              tvdbId=tvdbId,
                              imdbId=imdbId,
                              titleSlug=titleSlug)
    return needed_info_to_add


def sonarr_api_add_new_show(data):
    r = requests.post(sonarr_url+":"+sonarr_port+"/api/series?apikey="+sonarr_apikey, data=json.dumps(data))
    print r.json()


# Start of script
db_check()
imdb_processing(imdb_watchlist_rss_url)
update_db_in_sonarr(sonarr_get_list_of_shows())
push_to_sonarr()
update_db_in_sonarr(sonarr_get_list_of_shows())
