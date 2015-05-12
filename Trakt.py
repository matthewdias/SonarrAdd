# SonarrAdd

import urllib2
import sqlite3
import os.path
import json
from StringIO import StringIO
import requests

# Trakt Configuration
trakt_list_url = "https://api-v2launch.trakt.tv/users/{user}/lists/{list}/items"
trakt_apikey = ".."

# SonarrAdd configuration
db_name = "sonarradd.db"
install_path = "/Users/{user}/.config/sonarradd"  # Directory where sonarradd.db will be created
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
    c.execute('''CREATE TABLE trakt_list (tvdb_id TEXT PRIMARY KEY, trakt_name TEXT, in_sonarr INTEGER DEFAULT '0')''')
    c.execute('''CREATE TABLE db_info (db_version NUM)''')
    c.execute("INSERT INTO db_info VALUES (1)")
    conn.commit()
    conn.close()
    print "Database has been created"


def imdb_processing(trakt_list_url):
    headers = {"Content-type": "applications/json", "trakt-api-key": trakt_apikey, "trakt-api-version": "2"}
    response = requests.get(trakt_list_url, headers=headers)
    if response.status_code != 200:
        print "Trakt cannot be contacted(. Cancelling Trakt processing"
        return
    trakt_data = response.json()
    print "Checking Trakt list"
    conn = sqlite3.connect(sonarradd_db)
    c = conn.cursor()
    added = 0
    for i in range(0, len(trakt_data)):
        if trakt_data[i]['type'] == 'show':
            c.execute("INSERT OR IGNORE INTO trakt_list VALUES (?,?,?)", (trakt_data[i]['show']['ids']['tvdb'], trakt_data[i]['show']['title'], None))
            conn.commit()
        if c.rowcount > 0:
            added += 1
    if added > 0:
        print "Added %d new show(s) to SonarrAdd database" % added
    else:
        print "Nothing to add!"
    conn.close()
    response.close()


def sonarr_get_list_of_shows():
    print "Retrieving list of series already in Sonarr"
    r = requests.get(sonarr_url+":"+sonarr_port+"/api/series/?apikey="+sonarr_apikey)
    #print r.text
    shows = []
    for i in range(0, len(r.json())):
        shows.append(dict(title=r.json()[i]['title'], tvdbId=r.json()[i]['tvdbId']))
    #print shows
    return shows


def update_db_in_sonarr(shows):
    print "Updating database: setting state of shows"
    conn = sqlite3.connect(sonarradd_db)
    c = conn.cursor()
    c.execute('UPDATE trakt_list SET in_sonarr = NULL')
    conn.commit()
    if len(shows) > 0:
        for show in shows:
            show_tvdb_id = show['tvdbId']
            c.execute('UPDATE trakt_list SET in_sonarr = 2 WHERE tvdb_id = ?', [show_tvdb_id])
            conn.commit()
    conn.close()


def push_to_sonarr():
    print "Adding new series to Sonarr"
    conn = sqlite3.connect(sonarradd_db)
    c = conn.cursor()
    c.execute("SELECT tvdb_id FROM trakt_list WHERE in_sonarr IS NULL OR in_sonarr != 2")
    result_set = c.fetchall()
    if len(result_set) > 0:
        for tvdb_id_list in result_set:
            tvdbid = tvdb_id_list[0]
            print "Adding '"+tvdbid+"' to Sonarr"
            data = sonarr_api_series_lookup(tvdbid)
            sonarr_api_add_new_show(data)
    else:
        print "Nothing to add!"


def sonarr_api_series_lookup(tvdbid):
    results = requests.get(sonarr_url+":"+sonarr_port+"/api/series/lookup?term=tvdb: "+tvdbid+"&apikey="+sonarr_apikey)
    print tvdbid
    print results.text
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
imdb_processing(trakt_list_url)
update_db_in_sonarr(sonarr_get_list_of_shows())
push_to_sonarr()
update_db_in_sonarr(sonarr_get_list_of_shows())
