#!/usr/bin/env python3

from flask import Flask, render_template, jsonify
app = Flask(__name__)
 
@app.route("/")
def index():
	return render_template('index.html')

@app.route("/gettrips")
def loadtrips():
	import pickle
	# with open('trips_temp.pkl', 'wb') as outfile: pickle.dump(trips, outfile)
	with open('trips_temp.pkl', 'rb') as infile: trips = pickle.load(infile)
	
	resp = jsonify([ii.attr_dict(highseconly=True) for ii in trips])
	
	return resp

if __name__ == "__main__":
	app.run(debug=True)