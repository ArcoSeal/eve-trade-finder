import requests
from bs4 import BeautifulSoup

def getroute(waypoints, highseconly):
	# waypoints may be either names or systemIDs

	waypoints = tuple(str(ii) for ii in waypoints)
	url = 'http://evemaps.dotlan.net/route/{}{}'.format( ('2:' if highseconly else ''), ':'.join(waypoints))

	resp = requests.get(url)

	soup = BeautifulSoup(resp.text, 'html.parser')

	routetable = soup.find('table', class_='tablelist table-tooltip')

	try:
		headers = [ii.find(text=True) for ii in routetable()[0].findAll('th')]
	except:
		import pdb
		pdb.set_trace()

	systemcol = headers.index('SolarSystem')

	systemnames = []
	for row in routetable.findAll('tr')[1:]:
		cells = row.findAll('td')
		systemnames.append(cells[systemcol].getText().strip())

	return(systemnames)
