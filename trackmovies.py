#!/usr/bin/python3

import configparser
import datetime
import glob
import os
import sqlite3
import sys

try:
    from imdbpie import Imdb
except:
    sys.stderr.write('Whoa! I had an issue loading the imdbpie Python module. You might want to install that first!\n')
    sys.exit(-1)

__version__ = '0.1'
__author__ = 'Martino Jones'


# This script will monitor the movies in a directory and let you know when new movies are added
def main():
    sys.stdout.write('Starting Track Movies '
                     + __version__
                     + ' by: '
                     + __author__ + '\n')

    SCRIPTPATH = os.path.dirname(os.path.realpath(sys.argv[0]))

    # Read in the config file, unless it doesn't exist then check ARGS
    if os.path.isfile(SCRIPTPATH + '/config'):
        paths = parseconfig(SCRIPTPATH + '/config')

    if len(sys.argv) > 1:
        paths = paths + sys.argv[1:]

    # Make sure we have paths to work with
    if len(paths) == 0:
        sys.stderr.write(
            'Whoa! I couldn\'t find a path.\n Please make a config file with the path in it, or pass the path in as an argument.\n')
        sys.stderr.write('The layout for the config file should look something like:\n'
                         '[NAME OF LIB]\n'
                         'path = ROOT LOCATION OF MOVIES\n'
                         '\n'
                         'Example: \n'
                         '[movies1]\n'
                         'path = /home/martino/movies/\n')
        sys.exit(-11)

    # Display the paths found
    sys.stdout.write('Found the following paths for your content:\n')
    for PATH in paths:
        sys.stdout.write(PATH + '\n')

    # Empty until we get a database connection
    connection = ''

    # Check to see if the database exists
    if not os.path.isfile(SCRIPTPATH + '/movies.db'):
        sys.stdout.write('No database exists, I\'ll make a new one.\n')

        database = makeDatabase(SCRIPTPATH)
    else:
        database = sqlite3.connect(SCRIPTPATH + '/movies.db')

    # Get the files needed
    moviePaths = []
    for PATH in paths:
        moviePaths = moviePaths + getFiles(PATH)

    # Make sure we actually have movies we can work with, or this script is pointless
    if len(moviePaths) == 0:
        sys.stderr.write('Could not find any movies, there\'s nothing else for me to do!\n')
        sys.exit(-2)

    # Add all the movies found to the database
    newMovies, currentMovies = addMoviesToDatabase(moviePaths, database)

    # Write all new movies to a file with thier poster
    if len(newMovies) > 0:
        buildNewMoviesHtml(newMovies)

    recordedMovies = getAllMoviesInDatabase(database)

    lostMovies = findLostMovies(currentMovies, recordedMovies)

    for MOVIES in lostMovies:
        sys.stdout.write('LOST: '
                         + MOVIES
                         + '\n')

    # Build the lost movies HTML file
    buildRemovedMoviesHtml(lostMovies)


def makeDatabase(PATH):
    __doc__ = 'This method will create an Sqlite3 with the movies table database and return the database'

    try:
        database = sqlite3.connect(PATH + '/movies.db')
    except Exception as e:
        sys.stderr.write('There was an error making the database!\n' + str(e))
        return -100

    database.execute('''
        CREATE TABLE movies(path TEXT PRIMARY KEY,
                           name TEXT, found TEXT)
    ''')

    database.commit()
    # Return the database connection to main
    return database


def getFiles(PATH):
    __doc__ = 'This will recursivly get all files the path provided, then return those files in a list.'

    movies = []

    try:
        for filename in glob.iglob(PATH + '**/*.mkv', recursive=True):
            movies.append(filename)
    except:
        sys.stderr.write('Could not parse the files in the directory!')
        sys.exit(-200)

    return movies


def addMoviesToDatabase(movies, database):
    __doc__ = 'This method accepts '

    newMovies = []
    allMovies = []

    if len(movies) != 0:
        for MOVIEPATH in sorted(movies):
            MOVIENAME = str(MOVIEPATH).split('/')[-1].split('.')[0]
            DATETIME = str(datetime.datetime.now())

            code = addToDatabase(MOVIEPATH, MOVIENAME, DATETIME, database)

            allMovies.append(MOVIENAME)

            if code == 0:
                newMovies.append(MOVIENAME)
                sys.stdout.write('Added ' + MOVIENAME + ' to the database at ' + DATETIME + '\n')
                # elif code == 150:
                # sys.stdout.write(MOVIENAME + ' already in the database.\n')


    else:
        sys.stderr.write('There are no movies to add!\n')
        return -300

    return newMovies, allMovies


def addToDatabase(PATH, NAME, FOUND, database):
    cursor = database.cursor()

    try:
        cursor.execute('''
        INSERT INTO movies(path, name, found)
        VALUES(?,?,?)''', (str(PATH), str(NAME), str(FOUND)))
    except sqlite3.IntegrityError:
        return 150

    # Commit the changes
    database.commit()

    return 0


def findLostMovies(currentMovies, recordedMovies):
    __doc__ = 'This will look through the database and compare the list to the list of movies'

    lostMovies = []

    for MOVIE in recordedMovies:
        if not MOVIE[0] in currentMovies:
            lostMovies.append(MOVIE[0])

    return lostMovies


def getAllPathsInDatabase(database):
    __doc__ = 'This returns all movies in the database'

    cursor = database.cursor()

    cursor.execute('SELECT path FROM movies')

    paths = cursor.fetchall()

    return paths


def getAllMoviesInDatabase(database):
    __doc__ = 'This returns all movies in the database'

    cursor = database.cursor()

    cursor.execute('SELECT name FROM movies')

    movies = cursor.fetchall()

    return movies


def deleteFromDatabase(movie, database):
    __doc__ = "This will search for all entries in the database with the movie name and remove it"

    cursor = database.cursor()

    try:
        cursor.execute('''
            DELETE FROM movies WHERE name = ?'''(movie))
    except:
        return -400

    # Commit the changes
    database.commit()

    return 0


def getMoviePoster(movie):
    __doc__ = 'This will try it\'s best to get the poster for the movie provided.'

    imdb = Imdb()

    try:
        imdbMovie = imdb.search_for_title(movie)[0]
        imdbTitle = imdb.get_title_by_id(imdbMovie['imdb_id'])
        image = imdbTitle.poster_url
    except:
        return ''

    return image


def buildNewMoviesHtml(newMovies):
    NEWMOVIES = open('newmovies.html', 'w')

    # Format
    NEWMOVIES.write('<h2>There are new movies available. Below are the new movies available.</h2>\n')
    NEWMOVIES.write('There are ' + str(len(newMovies)) + ' new movies!!!\n')

    for MOVIE in newMovies:
        NEWMOVIES.write(formatMovieHtml(MOVIE))


def buildRemovedMoviesHtml(removedMovies):
    NEWMOVIES = open('removedmovies.html', 'w')

    # Format
    NEWMOVIES.write('<h2>Movies have been removed. Below are the movies removed.</h2>\n')
    NEWMOVIES.write('There were ' + str(len(removedMovies)) + ' movies removed!!!\n')

    for MOVIE in removedMovies:
        NEWMOVIES.write(formatMovieHtml(MOVIE))


def formatMovieHtml(movie):
    HTML = '<p> ' + str(movie) + '<p><img src="' + str(
        getMoviePoster(movie)) + '" alt="' + movie + '" style="width:304px;height:400px;"></p>' + '</p>'

    return HTML


def parseconfig(PATH):
    __doc__ = 'This will parse the config file and return the config as dict'

    paths = []

    if os.path.isfile(PATH):
        config = configparser.ConfigParser()
        config.read(PATH)
    else:
        return ''

    # Get the path of the movies
    for KEY in config.keys():
        if 'path' in config[KEY]:
            if os.path.isdir(config[KEY]['path']):
                paths.append(config[KEY]['path'])

    return paths


if __name__ == '__main__':
    main()
