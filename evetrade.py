#!/usr/bin/env python3

import os
import sys
import time
import requests
import logging
from operator import itemgetter, attrgetter

from functools import lru_cache

import sqlitetools
import dotlanroutescraper

DBFILE_ORDERS = 'orders.sqlite'
DBFILE_AUX = 'auxdata.sqlite'

contraband_types = ('17796', '17796', '17796', '17796', '17796', '17796', '17796', '17796', '12478', '12478', '12478', '11855', '11855', '11855', '11855', '9844', '9844', '9844', '9844', '9844', '9844', '3729', '3729', '3729', '3729', '3729', '3729', '3729', '3729', '3729', '3729', '3729', '3727', '3727', '3727', '3727', '3727', '3721', '3721', '3721', '3721', '3721', '3721', '3721', '3721', '3721', '3721', '3721', '3713', '3713')
	
def initorderDB():
	if os.path.isfile(DBFILE_ORDERS): os.remove(DBFILE_ORDERS)
	sqlitetools.createtable(DBFILE_ORDERS, 'orders', ('orderID INT PRIMARY KEY', 'itemID INT', 'locationID INT', 'orderType TEXT', 'price REAL', 'orderQty INT'))
	logger.debug('Initialised order DB')

def initauxDB():
	if os.path.isfile(DBFILE_AUX): os.remove(DBFILE_AUX)
	sqlitetools.createtable(DBFILE_AUX, 'locations', ('locationID INT PRIMARY KEY', 'systemID INT', 'locationName TEXT'))
	sqlitetools.createtable(DBFILE_AUX, 'systems', ('systemID INT PRIMARY KEY', 'systemName TEXT', 'security REAL'))
	sqlitetools.createtable(DBFILE_AUX, 'jumps', ('system1 INT', 'system2 INT', 'highsecOnly BOOL', 'jumps INT'))
	sqlitetools.createtable(DBFILE_AUX, 'items', ('itemID INT PRIMARY KEY', 'itemName TEXT', 'volume REAL'))
	logger.debug('Initialised aux DB')

def reqget(url, params=None, timeout=10, max_attempts=5, wait_between_attempts=2, session=None):
	attempts = 0
	while attempts < max_attempts:
		attempts += 1
		
		try:
			t1 = time.time()
			if session is not None:
				resp = session.get(url, params=params, timeout=timeout)
			else:
				resp = requests.get(url, params=params, timeout=timeout)

			t2 = time.time() - t1

			if resp.status_code != requests.codes.ok:
				resp.raise_for_status()
			else:
				logger.debug('Request time: {:.3f} sec'.format(t2))

		except Exception as e:
			if attempts >= max_attempts:
				logger.error('GET request failed: url={}, params={}'.format(url, params))
				raise
			else:
				logger.warning('GET request failed ({}). Retrying {}/{}'.format(e.__class__.__name__, attempts+1, max_attempts))
				time.sleep(wait_between_attempts)

		else:
			return resp

def CREST_getallpages(url):
	resp = reqget(url)
	data = resp.json()
	items = data['items']

	while 'next' in data.keys():
		resp = reqget(data['next']['href'])
		data = resp.json()
		items.extend(data['items'])

	return items

def CREST_getregions(regiontype='all'):
	null_regions = ('Branch','Cache','Catch','Cloud Ring','Cobalt Edge','Curse','Deklein','Delve','Detorid','Esoteria','Etherium Reach','Fade','Feythabolis','Fountain','Geminate','Great Wildlands','Immensea','Impass','Insmother','The Kalevala Expanse','Malpais','Oasa','Omist','Outer Passage','Outer Ring','Paragon Soul','Period Basis','Perrigen Falls','Providence','Pure Blind','Querious','Scalding Pass','The Spire','Stain','Syndicate','Tenal','Tenerifis','Tribute','Vale of the Silent','Venal','Wicked Creek')
	jove_regions = ('A821-A', 'J7HZ-F', 'UUA-F4')

	url = 'https://crest-tq.eveonline.com/regions/'

	data = CREST_getallpages(url)

	allregions = {int(ii['id']): ii['name'] for ii in data}

	if regiontype == 'all':
		return allregions
	elif regiontype == 'empire':
		return {k:allregions[k] for k in allregions if (allregions[k] not in null_regions + jove_regions) and ('000' not in allregions[k])}
	elif regiontype == 'null':
		return {k:allregions[k] for k in allregions if allregions[k] in null_regions}
	elif regiontype == 'jove':
		return {k:allregions[k] for k in allregions if allregions[k] in jove_regions}
	else:
		raise Exception('Invalid regiontype')

def pyswagger_retry(swaggerclient, op, max_retries=5, wait_between_attempts=2, **kwargs):
	retries = 0
	while retries <= max_retries:
		resp = swaggerclient.request(app.op[op](**kwargs))
		if resp.status == 200:
			return resp
		else:
			logger.debug('Swagger request failed (status code: {}), retrying {}/{}'.format(resp.status, retries, max_retries))
			time.sleep(wait_between_attempts)
			retries += 1

	raise Exception('Swagger request failed, op: {}, args: {}, status code: {}'.format(op, kwargs, resp.status))

def getinfobyID(swaggerclient, ID):
	info = pyswagger_retry(swaggerclient, op='post_universe_names', ids=[ID]).data[0]
	return info

def getIDbyname(swaggerclient, name, IDtype, strict=True):
	if IDtype == 'item': IDtype = 'inventorytype'

	ID = pyswagger_retry(swaggerclient, op='get_search', search=name, categories=[IDtype], strict=strict).data[IDtype]

	if not ID:
		raise Exception('Could not find ID for name: {}'.format(name))

	if len(ID): ID = ID[0]

	return ID

def isstructureID(locationID):
	# crude test to see if a locationID is for a structure
	# !TODO: improve this when more ESI operations become available

	locationID = str(locationID)

	if len(locationID) == 13 and locationID.startswith('102'):
		return True
	else:
		return False

@lru_cache(maxsize=None)
def getlocationinfo(locationID):
	def getstationinfo(swaggerclient, stationID):
		data = swaggerclient.request(app.op['get_universe_stations_station_id'](station_id=stationID)).data

		if not data: raise Exception('Could not find system for station: {}'.format(stationID))

		return {'systemID': data['solar_system_id'], 'locationname': data['station_name']}

	def getstructureinfo(swaggerclient, structureID):
		# data = swaggerclient.request(app.op['get_universe_structures_structure_id'](structure_id=structureID)).data

		# !TODO: get structure info
		logger.warning('Structure info not implemented (locationID: {})'.format(structureID))

		# if not data: raise Exception('Could not find system for station: {}'.format(structureID))

		return {'systemID': None, 'locationname': None}

	if not os.path.isfile(DBFILE_AUX): initauxDB()

	with sqlitetools.sqlite3.connect(DBFILE_AUX) as conn:
		c = conn.cursor()
		locationinfo = c.execute('''SELECT systemID,locationName FROM locations WHERE locationID = ?''', (locationID, )).fetchall()

		if locationinfo:
			locationinfo = locationinfo[0]
			locationinfo = {'systemID': locationinfo[0], 'locationname': locationinfo[1]}

		else:
			try:
				if not isstructureID(locationID):
					locationinfo = getstationinfo(swaggerclient, locationID)
				else:
					locationinfo = getstructureinfo(swaggerclient, locationID)
			except:
				logger.error('Encountered error at location {}'.format(locationID))
				raise

			else:
				c.execute('''INSERT INTO locations VALUES (?,?,?)''', (locationID, locationinfo['systemID'], locationinfo['locationname']))
				conn.commit()
				
				logger.debug('{} -> {} ({}) (locations DB updated)'.format(locationID, locationinfo['systemID'], locationinfo['locationname']))

	conn.close()

	return locationinfo

@lru_cache(maxsize=None)
def getsysteminfo(systemID):
	if not os.path.isfile(DBFILE_AUX): initauxDB()

	with sqlitetools.sqlite3.connect(DBFILE_AUX) as conn:
		c = conn.cursor()
		systeminfo = c.execute('''SELECT systemName,security FROM systems WHERE systemID=?''', (systemID,)).fetchall()

		if systeminfo:
			systeminfo = systeminfo[0]
			systeminfo = {'name': systeminfo[0], 'security': systeminfo[1]}

		else:
			try:
				url = 'https://crest-tq.eveonline.com/solarsystems/{}/'.format(systemID)
				data = reqget(url).json()
				systeminfo = {'name': data['name'], 'security': data['securityStatus']}
			except:
				logger.error('Encountered error for system: {}'.format(systemID))
				raise
			else:
				c.execute('''INSERT INTO systems VALUES (?,?,?)''', (systemID, systeminfo['name'], systeminfo['security']))
				conn.commit()
				
				logger.debug('{} -> {}, {:.1f} (system DB updated)'.format(systemID, systeminfo['name'], systeminfo['security']))

	conn.close()

	return systeminfo

@lru_cache(maxsize=None)
def getjumps(waypoints, highseconly):
	if len(waypoints) > 2: raise Exception('Not implemented')

	system1, system2 = min(waypoints), max(waypoints)

	if not os.path.isfile(DBFILE_AUX): initauxDB()

	with sqlitetools.sqlite3.connect(DBFILE_AUX) as conn:
		c = conn.cursor()
		jumps = c.execute('''SELECT jumps FROM jumps WHERE system1=? AND system2=? AND highsecOnly=?''', (system1, system2, highseconly)).fetchall()

		if jumps:
			jumps = len(jumps[0])

		else:
			try:
				jumps = len(dotlanroutescraper.getroute((system1, system2), highseconly))
			except:
				logger.error('Encountered error for waypoints: {}'.format(waypoints))
				raise

			else:
				c.execute('''INSERT INTO jumps VALUES (?,?,?,?)''', (system1, system2, highseconly, jumps))
				conn.commit()
				
				logger.debug('{} -> {} ({}) is {} jumps (jumps DB updated)'.format(system1, system2, ('safest' if highseconly else 'shortest'), jumps))

	conn.close()

	return jumps

@lru_cache(maxsize=None)
def getiteminfo(itemID):
	if not os.path.isfile(DBFILE_AUX): initauxDB()

	with sqlitetools.sqlite3.connect(DBFILE_AUX) as conn:
		c = conn.cursor()
		iteminfo = c.execute('''SELECT itemName,volume FROM items WHERE itemID=?''', (itemID,)).fetchall()

		if iteminfo:
			iteminfo = iteminfo[0]
			iteminfo = {'name': iteminfo[0], 'volume': iteminfo[1]}

		else:
			try:
				url = 'https://crest-tq.eveonline.com/inventory/types/{}/'.format(itemID)
				data = reqget(url).json()
				iteminfo = {'name': data['name'], 'volume': data['volume']}

			except:
				logger.error('Encountered error for item: {}'.format(itemID))
				raise

			else:
				c.execute('''INSERT INTO items VALUES (?,?,?)''', (itemID, iteminfo['name'], iteminfo['volume']))
				conn.commit()
				
				logger.debug('{} -> {} ({} m3) (item DB updated)'.format(itemID, iteminfo['name'], iteminfo['volume']))

	conn.close()

	return iteminfo

def getregionorders_swagger(swaggerclient, region, item=None, ordertype=None, page='all'):
	if page == 'all':
		orders = []
		page = 1
		thispage = getregionorders_swagger(swaggerclient, region, item, ordertype, page)
		while thispage:
			orders.extend(thispage)
			page += 1
			thispage = getregionorders_swagger(swaggerclient, region, item, ordertype, page)

	else:
		orders = pyswagger_retry(swaggerclient, op='get_markets_region_id_orders', region_id=region, type_id=item, order_type=ordertype, page=page).data

	return orders

def getregionorders_req(region, item=None, ordertype='all', page='all', session=None, API=None):
	if ordertype not in ('buy', 'sell', 'all'): raise Exception('ordertype must be "buy", "sell" or "all"')
	
	API = API.lower()

	if API == 'esi':
		if page == 'all':
			orders = []
			page = 1
			thispage = getregionorders_req(region, item, ordertype, page, session=session)
			while thispage:
				orders.extend(thispage)
				page += 1
				thispage = getregionorders_req(region, item, ordertype, page, session=session)

		else:
			url = 'https://esi.tech.ccp.is/latest/markets/{}/orders/'.format(region)
			params = {'type_id': item, 'order_type': ordertype, 'page': page}

			resp = reqget(url, params, session=session)
			orders = resp.json()

			orders_trim = tuple(Order(orderID=ii['order_id'],
										itemID=ii['type_id'],
										orderType=('buy' if ii['is_buy_order'] else 'sell'),
										price=ii['price'],
										orderQty=ii['volume_remain'],
										locationID=ii['location_id'])
								for ii in orders)

	elif API == 'crest':
		if item in ('all', None):
			itemURL_CREST = 'all'
		else:
			itemURL_CREST = 'https://crest-tq.eveonline.com/inventory/types/{}/'.format(item)

		url = 'https://crest-tq.eveonline.com/market/{}/orders/{}/'.format(region, itemURL_CREST)
		params = ({'page': page} if page != 'all' else None)

		resp = reqget(url, params, session=session)
		data = resp.json()
		orders = data['items']

		if page == 'all':
			uniq_orderids = set()
			while 'next' in data:
				url = data['next']['href']
				resp = reqget(url, params, session=session)
				data = resp.json()
				# sometimes we get orders duplicated between pages - this will ignore duplicates, giving preference to the earlier appearance
				for oo in data['items']:
					oo_id = oo['id']
					if oo_id not in uniq_orderids:
						uniq_orderids.add(oo_id)
						orders.append(oo)

		if ordertype != 'all':
			ordertype = (True if ordertype == 'buy' else False)
			orders = [ii for ii in orders if ii['buy'] == ordertype]

		orders_trim = tuple(Order(orderID=ii['id'],
									itemID=ii['type'],
									orderType=('buy' if ii['buy'] else 'sell'),
									price=ii['price'],
									orderQty=ii['volume'],
									locationID=ii['stationID'])
							for ii in orders)

	orders_trim = tuple(ii for ii in orders_trim if ii.systemID) # strip orders where system is unknown

	return orders_trim

def getorderdata(ignore_contraband, API, use_swagger_interface=False):
	regionlist = CREST_getregions('empire')
	orders = []
	with requests.Session() as sesh:
		for regionID in regionlist:
			logger.debug('Doing region: {}'.format(regionlist[regionID]))
			if API == 'ESI' and use_swagger_interface:
				orders.extend(getregionorders_swagger(regionID, session=sesh, API=API))
			else:
				orders.extend(getregionorders_req(regionID, session=sesh, API=API))
			logger.debug('Got {} orders'.format(len(orders)))

			if ignore_contraband: orders = [ii for ii in orders if ii.itemID not in contraband_types]
	
	return orders

def writeorderstoDB(orders):
	initorderDB()
	sqlitetools.insertmany(DBFILE_ORDERS, 'orders', [(ii.orderID, ii.itemID, ii.locationID, ii.orderType, ii.price, ii.orderQty) for ii in orders])

def readordersfromDB():
	with sqlitetools.sqlite3.connect(DBFILE_ORDERS) as conn:
		c = conn.cursor()
		allorders = c.execute('''SELECT orderID,itemID,locationID,orderType,price,orderQty FROM orders''').fetchall()
	conn.close()

	allorders = [Order(orderID=ii[0], itemID=ii[1], locationID=ii[2], orderType=ii[3], price=ii[4], orderQty=ii[5]) for ii in allorders]

	logger.debug('Read {} orders from DB'.format(len(allorders)))

	return allorders

def findtrades(orders):
	alltrades = []

	idc_dict = {ii.itemID:{'buy':{}, 'sell':{}} for ii in orders}
	for ii,oo in enumerate(orders):
		if oo.systemID not in idc_dict[oo.itemID][oo.orderType]: idc_dict[oo.itemID][oo.orderType][oo.systemID] = []
		idc_dict[oo.itemID][oo.orderType][oo.systemID].append(ii)

	for this_item in idc_dict:
		itemtrades = []
		minsell, maxbuy = {}, {}

		for sellsystem in idc_dict[this_item]['sell']:
			for buysystem in idc_dict[this_item]['buy']:
				sellorders, buyorders = [orders[ii] for ii in idc_dict[this_item]['sell'][sellsystem]], [orders[ii] for ii in idc_dict[this_item]['buy'][buysystem]]

				if sellsystem not in minsell: minsell[sellsystem] = min(ii.price for ii in sellorders)
				if buysystem not in maxbuy: maxbuy[buysystem] = max(ii.price for ii in buyorders)

				if minsell[sellsystem] < maxbuy[buysystem]:
					itemtrades.extend(fillorders(sellorders, buyorders))

		logger.debug('Item {}: found {} trades'.format(this_item, len(itemtrades)))

		alltrades.extend(itemtrades)

	return alltrades

def fillorders(sellorders, buyorders):
	if len(set(ii.systemID for ii in sellorders)) > 1: raise Exception('Mismatched sell systems: {}'.format(set(ii.systemID for ii in sellorders)))
	if len(set(ii.systemID for ii in buyorders)) > 1: raise Exception('Mismatched buy systems: {}'.format(set(ii.systemID for ii in buyorders)))
	if len(set(ii.itemID for ii in (sellorders+buyorders))) > 1: raise Exception('Mismatched items: {}'.format(set(ii.itemID for ii in (sellorders+buyorders))))

	sellorders = sorted(sellorders, key=attrgetter('price'), reverse=False) # sell orders low -> high
	buyorders = sorted(buyorders, key=attrgetter('price'), reverse=True) # buy orders high -> low

	trades = []

	tracker = {}
	for order in (sellorders + buyorders):
		tracker[order.orderID] = order.orderQty

	# logger.debug('Item: {}, sell system: {}, buysystem: {}'.format(sellorders[0].itemID, sellorders[0].systemID, buyorders[0].systemID))
	for bb in buyorders:
		for ss in sellorders:
			if tracker[bb.orderID] <= 0: break
			if ss.price >= bb.price: break

			if tracker[ss.orderID] <= 0: continue

			tradeqty = min(tracker[ss.orderID], tracker[bb.orderID])

			trades.append(Trade(ss, bb, tradeqty))

			# logger.debug('Sell order: {}, {}/{} units @ {} -> Buy order: {}, {}/{} units @ {}'.format(ss.orderID, tradeqty, tracker[ss.orderID], ss.price, bb.orderID, tradeqty, tracker[bb.orderID], bb.price))

			tracker[ss.orderID] -= tradeqty
			tracker[bb.orderID] -= tradeqty
	
	return trades

def findtrips(trades, maxvol, minprofitpertrip, minprofitpertrade, minprofitperjump, highseconly):

	alltrips = []

	idc_dict = {}
	for ii,trade in enumerate(trades):
		ss, bb = trade.sellorder.systemID, trade.buyorder.systemID

		if ss not in idc_dict: idc_dict[ss] = {}
		if bb not in idc_dict[ss]: idc_dict[ss][bb] = []

		idc_dict[ss][bb].append(ii)

	for startsystem in idc_dict:
		for endsystem in idc_dict[startsystem]:
			this_trip = Trip(startsystem, endsystem)

			trades_thistrip = [trades[ii] for ii in idc_dict[startsystem][endsystem]]
			trades_thistrip.sort(key=lambda x: x.profitperm3(), reverse=True)

			vol_remaining = maxvol
			ii = -1
			while vol_remaining > 0:
				ii += 1
				if ii >= len(trades_thistrip): break
				
				this_trade = trades_thistrip[ii]
				if this_trade.profit() < minprofitpertrade: continue

				if this_trade.totalvol() > vol_remaining:
					tradeqty_reduced = int(vol_remaining / this_trade.itemvol())
					if tradeqty_reduced <= 0:
						continue
					else:
						this_trade.tradeqty = tradeqty_reduced

				this_trip.addtrade(this_trade)
				vol_remaining -= this_trade.totalvol()

			if this_trip.profit() >= minprofitpertrip:
				if this_trip.profitperjump(highseconly) >= minprofitperjump:
					alltrips.append(this_trip)

	return alltrips

class Order:

	def __init__(self, orderID, itemID, orderType, price, orderQty, locationID):
		self.orderID = orderID
		self.itemID = itemID
		self.orderType = orderType
		self.price = price
		self.orderQty = orderQty
		self.locationID = locationID

		self.systemID = getlocationinfo(self.locationID)['systemID']

class Trade:

	def __init__(self, sellorder, buyorder, tradeqty):
		self.sellorder = sellorder
		self.buyorder = buyorder
		self.tradeqty = tradeqty
		self.itemID = sellorder.itemID

	def __str__(self):
		return 'Item: {}, {} ({}) -> {} ({}), {:,.2f} x {} units = {:,.2f} ISK'.format(self.itemID, self.sellorder.systemID, self.sellorder.orderID, self.buyorder.systemID, self.buyorder.orderID, self.buyorder.price - self.sellorder.price, self.tradeqty, self.profit())

	def profitperunit(self):
		return round(self.buyorder.price - self.sellorder.price, 2)

	def profit(self):
		return self.profitperunit() * self.tradeqty

	def profitperm3(self):
		return round(self.profitperunit() / getiteminfo(self.itemID)['volume'], 2)

	def itemvol(self):
		return getiteminfo(self.itemID)['volume']

	def totalvol(self):
		return self.itemvol() * self.tradeqty
	
class Trip:

	def __init__(self, startsystem, endsystem):
		self.startsystem = startsystem
		self.endsystem = endsystem

		self.trades = []

	def addtrade(self, trade):
		if isinstance(trade, Trade):
			if trade.sellorder.systemID == self.startsystem and trade.buyorder.systemID == self.endsystem:
				self.trades.append(trade)
			else:
				raise Exception('Trade does not fit with this trip. Expected systems: {} -> {}. Trade: {} -> {}'.format(self.startsystem, self.endsystem,
																														trade.sellsystem, trade.buysystem))
		else:
			raise Exception('Not a trade: {}'.format(trade))

	def profit(self):
		return round(sum([ii.profit() for ii in self.trades]), 2)

	def totalvol(self):
		return sum([ii.totalvol() for ii in self.trades])

	def profitperjump(self, highseconly):
		if self.startsystem == self.endsystem:
			ppj = self.profit()
		else:
			ppj = round(self.profit() / getjumps((self.startsystem, self.endsystem), highseconly), 2)
		
		return ppj

	def attr_dict(self, highseconly):
		return {
				'startsystem': self.startsystem,
				'endsystem': self.endsystem,
				'profit': self.profit(),
				'jumps': getjumps((self.startsystem, self.endsystem), highseconly),
				'profitperjump': self.profitperjump(highseconly),
				'totalvol': self.totalvol(),
				}

if __name__ == '__main__':

	import customlog
	logger = customlog.initlogger('mylogger', console=True, loglevel='debug')

	from pyswagger import App
	from pyswagger.contrib.client.requests import Client
	app = App.create('https://esi.tech.ccp.is/latest/swagger.json?datasource=tranquility')
	swaggerclient = Client()

	# initorderDB()
	# t1 = time.time()
	# orders = getorderdata(API='CREST')
	# logger.info('Pulled {} orders in {:.2f} seconds'.format(len(orders), time.time()-t1))

	# writeorderstoDB(orders)

	t1 = time.time()
	orders = readordersfromDB()
	logger.info('Read orders from DB in {:.2f} sec'.format(time.time() - t1))

	t1 = time.time()
	trades = findtrades(orders)
	logger.info('Found {} total trades in {:.2f} seconds'.format(len(trades), time.time()-t1))

	highseconly = False

	t1 = time.time()
	trips = findtrips(trades, maxvol=60e3, minprofitpertrip=20e6, minprofitpertrade=900e3, minprofitperjump=900e3, highseconly=highseconly)
	logger.info('Found {} trips in {:.2f} seconds'.format(len(trips), time.time()-t1))

	for trip in trips:
		print('{} -> {}'.format(getsysteminfo(trip.startsystem)['name'], getsysteminfo(trip.endsystem)['name']))
		for trade in trip.trades: print('{}: sell @ {:,}, buy @ {:,} x {:,} units => {:,.2f} ISK profit'.format(getiteminfo(trade.itemID)['name'],
																												trade.sellorder.price,
																												trade.buyorder.price,
																												trade.tradeqty,
																												trade.profit()))
		print('Total volume: {:,.2f} m3, max profit: {:,.2f} ISK, profit/jump: {:,.2f} ISK'.format(trip.totalvol(), trip.profit(), trip.profitperjump(highseconly=highseconly)))
		print('')

else:
	logger = logging.getLogger('mylogger')