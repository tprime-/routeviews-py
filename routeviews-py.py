#!/usr/bin/env python

# Python script to record changes in BGP data from routeviews.org
# @tprime_

from __future__ import division
import requests
import bz2
import sqlite3
import csv
import sys
import re
import time
import datetime
import os.path
import operator
import argparse

url = 'http://archive.routeviews.org/oix-route-views/oix-full-snapshot-latest.dat.bz2'
ts = time.time()

def search_route_views_data(as_number):
	routeviews_data = open('oix-full-snapshot-latest.dat','r')
	file_data = routeviews_data.readlines()
	routeviews_data.close()

	as_match_count = 0
	#regex = r"\s" + re.escape(as_number) + r"\s"
	regex = as_number + "\s(i|e|\?)"
	for line in file_data:
		if re.search(regex, line):
			as_match_count += 1
	return as_match_count

def sqlite_calculate_change(as_number):
	current_as_count = search_route_views_data(as_number)
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
	print '[!] Inserting the following:', timestamp, as_number, count, change
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
		print '[!] Autonomous System not yet in CSV. Adding with a change value of 1.'
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

def main(args):
	# Download data, write to a file
	print "[!] Downloading latest Route Views BGP data"
	r = requests.get(url)
	with open("oix-full-snapshot-latest.dat.bz2", "wb") as code:
		code.write(r.content)

	#Extract the bzip2 file
	print "[!] Extracting bzip"
	with open("oix-full-snapshot-latest.dat", 'wb') as extracted, bz2.BZ2File("oix-full-snapshot-latest.dat.bz2", 'rb') as file:
        	for data in iter(lambda : file.read(100 * 1024), b''):
	            extracted.write(data)

	if args.output_format == 'csv':
		print '[!] Results being written to CSV format'
		csv_exists = os.path.isfile('bgp.csv')
		with open('bgp.csv', 'a+') as csvfile:
			fieldnames = ['timestamp', 'asn', 'count', 'change']
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
			if not csv_exists:
				print '[!] CSV file not found. Creating CSV.'
				writer.writeheader()

		# Loop through ASNs identified with -a flag
		for asn in args.autonomous_systems.split(','):
			print '\n[!] Searching for ASN #', asn
			update_csv(asn)
	else:
		print '[!] Results being written to SQLite format'
		conn = sqlite3.connect(r"bgp.db") # Connect to our database. If it doesn't exist, create it.
		global c
		c = conn.cursor()
		c.execute('CREATE TABLE IF NOT EXISTS BGP_DATA (DATE TEXT, ASN INT, COUNT INT, CHANGE TEXT)')

		# Loop through ASNs identified with -a flag
		for asn in args.autonomous_systems.split(','):
			print '\n[!] Searching for ASN #', asn
			sqlite_update_database(asn)

		conn.commit() #Write changes to SQLite
		conn.close() #close database

	print '\n[!] Removing Route Views raw data'
	os.remove('oix-full-snapshot-latest.dat')
	os.remove('oix-full-snapshot-latest.dat.bz2')
	print '[!] All done'

if __name__ == '__main__':
	parser = argparse.ArgumentParser(
		description='Python script to record changes in BGP data from routeviews.org',
		usage='Usage: ./routeviews-py.py [-a ASNs] [-o sqlite|csv]',
	)
	parser.add_argument('-v', '--version',
		action='version',
		version='routeviews-py version 0.2',
	)
	parser.add_argument('-a',
		dest='autonomous_systems',
		help='ASNs to record in comma-seperated format. Ex: -a 100,200,300',
		required=True,
	)
	parser.add_argument('-o',
		dest='output_format',
		choices=['sqlite', 'csv'],
		default='sqlite',
		help='Output format: SQLite or CSV. Default is SQLite.',
#		required=True,
	)
	args = parser.parse_args()
main(args)