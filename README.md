# routeviews-py
Python script to record changes in BGP data from routeviews.org

Usage: ./routeviews-py.py -a <comma-seperated list of ASNs> -o <sqlite,csv>

Example: ./routeviews-py.py -a 100,200,300 -o csv

Notes: -a flag is required. -o flag is optional. Default output is SQLite.