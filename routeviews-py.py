#!/usr/bin/python

# Python script to record changes in BGP data from routeviews.org

from __future__ import division
import requests
import bz2
import sqlite3
import csv
import sys
import getopt
import re
import time
import datetime
import os.path
import operator

url = 'http://archive.routeviews.org/oix-route-views/oix-full-snapshot-latest.dat.bz2'
ts = time.time()
output_format = 'sqlite' # Default output. Don't change this.

# Download data, write to a file
print "[!] Downloading latest Route Views BGP data"
r = requests.get(url)
with open("oix-full-snapshot-latest.dat.bz2", "wb") as code:
	code.write(r.content)

# Extract the bzip2 file
print "[!] Extracting bzip"
zipfile = bz2.BZ2File("oix-full-snapshot-latest.dat.bz2") # open the file
data = zipfile.read() # get the decompressed data
open("oix-full-snapshot-latest.dat", 'wb').write(data) # write an uncompressed file

def help():
	print 'Usage: ./routeviews-py.py -a <comma-seperated list of ASNs> -o <sqlite,csv>'
	print 'Example: ./routeviews-py.py -a 100,200,300 -o csv'
	print 'Notes: -a flag is required. -o flag is optional. Default output is SQLite.'
	return

def options():
	if len(sys.argv) == 1:
		print ''
	try: 
		opts, args = getopt.getopt(sys.argv[1:], "ha:o:", ["autosys=", "output="])
	except getopt.GetoptError as err:
		print 'usage goes here'
		print str(err)
		sys.exit(2)
	for opt, arg in opts:
		if opt == '-h':
			help()
			sys.exit()
		elif opt in ("-a", "--autosys"):
			global autonomous_systems
			autonomous_systems = arg
			print '[!] Target Autonomous Systems:', autonomous_systems
		elif opt in ("-o", "--output"):
			global output_format
			output_format = arg

def search_route_views_data(as_number):
	routeviews_data = open('oix-full-snapshot-latest.dat','r')
	file_data = routeviews_data.readlines()
	routeviews_data.close()

	as_match_count = 0
	regex = r"\s" + re.escape(as_number) + r"\s"
	for line in file_data:
		if re.search(regex, line):
			as_match_count += 1
	
	return as_match_count

def sqlite_calculate_change(as_number):
	current_as_count = search_route_views_data(as_number)
#	c.execute('SELECT COUNT FROM BGP_DATA WHERE ASN = '+as_number+' ORDER BY DATE DESC LIMIT 1')
	c.execute("SELECT COUNT FROM BGP_DATA WHERE ASN=:as_number ORDER BY DATE DESC LIMIT 1", {"as_number": as_number})
	sql_output = c.fetchone()
	if sql_output:
		last_as_count = sql_output[0]
		print '[!] Previous AS matches:', last_as_count
		print '[!] Current AS matches:', current_as_count
		if last_as_count == 0:
			change = 0 # Avoid dividing by 0
		else:
			change = round(((current_as_count/last_as_count)-1),2)
			#print change
	else:
		print '[!] Autonomous System not yet in database. Adding with a change value of 1.'
		change = 1
	return (current_as_count, change)

def sqlite_update_database(as_number):
	timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d-%H:%M')
	data_to_insert = sqlite_calculate_change(as_number)
	count = data_to_insert[0] # current_as_count
	change = data_to_insert[1] # change
	print '[!] Inserting the following: ', timestamp, as_number, count, change
	c.execute("INSERT INTO BGP_DATA (DATE, ASN, COUNT, CHANGE) VALUES (?, ?, ?, ?)", (timestamp, as_number, count, change))
	return

def csv_calculate_change(as_number):
	current_as_count = search_route_views_data(as_number)
	asn_matches = []
	with open('bgp.csv', 'rb') as csvfile:
		reader = csv.reader(csvfile, delimiter=',')
		sortedlist = sorted(reader, key=operator.itemgetter(0), reverse=True)
		for line in sortedlist:
			if line[1] == as_number:
				asn_matches.append(line)
	#print asn_matches[0]
	if asn_matches:
		last_as_count = int(asn_matches[0][2])
		print '[!] Previous AS matches:', last_as_count
		print '[!] Current AS matches:', current_as_count
		if last_as_count == 0:
			change = 0 # Avoid dividing by 0
		else:
			change = round(((current_as_count/last_as_count)-1),2)
			#print change
	else:
		print '[!] Autonomous System not yet in database. Adding with a change value of 1.'
		change = 1
	return (current_as_count, change)

def update_csv(as_number):
	timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d-%H:%M')
	data_to_insert = csv_calculate_change(as_number)
	count = data_to_insert[0] # current_as_count
	change = data_to_insert[1] # change
	#data = [["timestamp", "asn", "count", "change"], [timestamp, as_number, count, change]]
	data = [timestamp, as_number, count, change]
	print '[!] Inserting the following:', data
	#print fieldnames
	with open('bgp.csv', 'a+') as csvfile:
			#fieldnames = ['timestamp', 'asn', 'count', 'change']
			writer = csv.writer(csvfile)
			writer.writerow(data) # put the data into the csv here
	return

options()

if output_format == 'csv':
	#do csv stuff
	print '[!] Results being written to CSV format\n'
	#Check if Autonomous Systems have been defined using -a.
	try:
		autonomous_systems
	except NameError:
		print '[!] Error: No Autonomous Systems defined.'
		help()
	else:
		csv_exists = os.path.isfile('bgp.csv')
		with open('bgp.csv', 'a+') as csvfile:
			fieldnames = ['timestamp', 'asn', 'count', 'change']
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
			if not csv_exists:
				print '[!] CSV file not found. Creating CSV.'
				writer.writeheader()
		# Loop through ASNs identified with -a flag
		for asn in autonomous_systems.split(','):
			print '[!] Looking at ASN #', asn
			update_csv(asn)
else:
	print '[!] Results being written to SQLite format'
	#Check if Autonomous Systems have been defined using -a.
	try:
		autonomous_systems
	except NameError:
		print '[!] Error: No Autonomous Systems defined.'
		help()
	else:
		conn = sqlite3.connect(r"bgp.db") # Connect to our database. If it doesn't exist, create it.
		c = conn.cursor()
		c.execute('CREATE TABLE IF NOT EXISTS BGP_DATA (DATE TEXT, ASN INT, COUNT INT, CHANGE TEXT)')

		# Loop through ASNs identified with -a flag
		for asn in autonomous_systems.split(','):
			print '[!] Looking at ASN #', asn
			sqlite_update_database(asn)

		conn.commit() #Write changes to SQLite
		conn.close() #close database

print '\n[!] All done.'