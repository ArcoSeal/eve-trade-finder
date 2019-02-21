#!/usr/bin/env python3

from operator import itemgetter

import wx
import wx.grid

import customlog
logger = customlog.initlogger('mylogger', console=True, loglevel='debug')

import evetrade

class MainWindow(wx.Frame):

	def __init__(self, parent, **kwargs):
		displaysize = kwargs.pop('displaysize')
		super().__init__(parent, **kwargs)

		self.SetMaxSize(wx.Size(displaysize[0]*0.9,displaysize[1]*0.9))
		self.initUI()
		self.Show()

	def initUI(self):
		leftpanel = wx.Panel(self)

		# menu bar
		menubar = wx.MenuBar()
		menu_file = wx.Menu()
		menu_item_exit = menu_file.Append(wx.ID_EXIT, item='E&xit')
		
		menu_opt = wx.Menu()
		menu_opt_initDBs = wx.Menu()
		menu_item_initorderDB = menu_opt_initDBs.Append(wx.ID_ANY, item='Order DB')
		menu_item_initauxDB = menu_opt_initDBs.Append(wx.ID_ANY, item='Aux DB')
		menu_opt.AppendSubMenu(menu_opt_initDBs, 'Reinit local DBs')

		menubar.Append(menu_file, '&File')
		menubar.Append(menu_opt, 'Options')
		
		self.Bind(wx.EVT_MENU, self.OnExit, menu_item_exit)
		self.Bind(wx.EVT_MENU, self.InitOrderDB, menu_item_initorderDB)
		self.Bind(wx.EVT_MENU, self.InitAuxDB, menu_item_initauxDB)
		
		self.SetMenuBar(menubar)

		# order data controls
		self.btn_pullorders = wx.Button(leftpanel, label='Get order data')
		self.cb_datasource = wx.Choice(leftpanel, choices=['CREST', 'ESI', 'Local DB'])
		self.btn_saveorders = wx.Button(leftpanel, label='Save order DB')

		self.cb_datasource.SetSelection(0)
		self.btn_saveorders.Disable()

		self.btn_pullorders.Bind(wx.EVT_BUTTON, self.PullOrders)
		self.btn_saveorders.Bind(wx.EVT_BUTTON, self.SaveOrders)
		
		# filter controls
		self.text_maxvol = wx.TextCtrl(leftpanel)
		self.text_maxvol.SetValue('60,000')
		text_maxvol_units = wx.StaticText(leftpanel, label='m3')
		self.text_minprofitpertrip = wx.TextCtrl(leftpanel)
		self.text_minprofitpertrip.SetValue('20,000,000')
		text_minprofitpertrip_units = wx.StaticText(leftpanel, label='ISK')

		self.text_maxvol.Bind(wx.EVT_SET_FOCUS, self.NumberBoxRemoveSeps)
		self.text_maxvol.Bind(wx.EVT_KILL_FOCUS, self.NumberBoxAddSeps)

		self.text_minprofitpertrip.Bind(wx.EVT_SET_FOCUS, self.NumberBoxRemoveSeps)
		self.text_minprofitpertrip.Bind(wx.EVT_KILL_FOCUS, self.NumberBoxAddSeps)
		
		# go button
		self.btn_gettrips = wx.Button(leftpanel, label='Get Trips')
		# self.btn_gettrips.Disable()
		self.chk_highseconly = wx.CheckBox(leftpanel, label='Highsec only')

		self.btn_gettrips.Bind(wx.EVT_BUTTON, self.GetTrips)

		# results grid
		self.tripgrid = CustomGrid(leftpanel)

		# boring sizer shit
		vbox_master = wx.BoxSizer(wx.VERTICAL)
		
		hbox1 = wx.StaticBoxSizer(wx.HORIZONTAL, leftpanel, label='Order data')
		hbox1.Add(self.btn_pullorders, 1, flag=wx.ALL, border=5)
		hbox1.Add(self.cb_datasource, 1, flag=wx.ALL, border=5)
		hbox1.Add(self.btn_saveorders, 1, flag=wx.ALL, border=5)

		hbox2 = wx.StaticBoxSizer(wx.HORIZONTAL, leftpanel, label='Filters')
		hbox2.Add(self.text_maxvol, 3, flag=wx.ALL, border=5)
		hbox2.Add(text_maxvol_units, 1, flag=wx.ALL, border=5)
		hbox2.Add(self.text_minprofitpertrip, 3, flag=wx.ALL, border=5)
		hbox2.Add(text_minprofitpertrip_units, 1, flag=wx.ALL, border=5)

		hbox3 = wx.BoxSizer(wx.HORIZONTAL)
		hbox3.Add(self.btn_gettrips, 1, flag=wx.ALL, border=5)
		hbox3.Add(self.chk_highseconly, 1, flag=wx.ALL, border=5)

		hbox4 = wx.BoxSizer(wx.HORIZONTAL)
		hbox4.Add(self.tripgrid, 1, flag=wx.ALL, border=5)

		vbox_master.Add(hbox1, 1, flag=wx.EXPAND)
		vbox_master.Add(hbox2, 1, flag=wx.EXPAND)
		vbox_master.Add(hbox3, 1, flag=wx.EXPAND)
		vbox_master.Add(hbox4, 1, flag=wx.EXPAND)

		leftpanel.SetSizer(vbox_master)
		# leftpanel.SetAutoLayout(True)
		# vbox_master.Fit(leftpanel)

		self.framesizer = wx.BoxSizer(wx.HORIZONTAL)
		self.framesizer.Add(leftpanel, 1, wx.EXPAND)
		self.SetSizer(self.framesizer)
		self.Fit()

	def OnExit(self, evt):
		self.Close(True)

	def InitOrderDB(self, evt):
		evetrade.initorderDB()

	def InitAuxDB(self, evt):
		evetrade.initauxDB()

	def NumberBoxAddSeps(self, evt):
		widget = evt.GetEventObject()
		number = widget.GetValue()
		widget.ChangeValue('{:,}'.format(int(number)))
		evt.Skip()

	def NumberBoxRemoveSeps(self, evt):
		widget = evt.GetEventObject()
		number = widget.GetValue()
		widget.ChangeValue(number.replace(',',''))
		evt.Skip()

	def PullOrders(self, evt):
		waitcursor = wx.BusyCursor()

		datasource = self.cb_datasource.GetString(self.cb_datasource.GetSelection())

		try:
			if datasource == 'Local DB':
				self.orders = evetrade.readordersfromDB()
			elif datasource == 'CREST':
				self.orders = evetrade.getorderdata(API='CREST')
			elif datasource == 'ESI':
				self.orders = evetrade.getorderdata(API='ESI')
		
		except:
			pass
		
		else:
			if not self.btn_gettrips.IsEnabled(): self.btn_gettrips.Enable()
			if not self.btn_saveorders.IsEnabled(): self.btn_saveorders.Enable()

		finally:
			del waitcursor

	def SaveOrders(self, evt):
		waitcursor = wx.BusyCursor()

		evetrade.writeorderstoDB(self.orders)

		del waitcursor

	def GetTrips(self, evt):
		# waitcursor = wx.BusyCursor()

		# maxvol = float(self.text_maxvol.GetValue().replace(',',''))
		# minprofitpertrip = float(self.text_minprofitpertrip.GetValue().replace(',',''))
		
		# try:
		# 	trips = evetrade.findtrips(evetrade.findtrades(self.orders),
		# 								maxvol=maxvol,
		# 								minprofitpertrip=minprofitpertrip,
		# 								minprofitpertrade=900e3,
		# 								minprofitperjump=900e3,
		# 								highseconly=self.chk_highseconly.IsChecked())

		# finally:
		# 	del waitcursor

		import pickle
		# with open('trips_temp.pkl', 'wb') as outfile: pickle.dump(trips, outfile)
		with open('trips_temp.pkl', 'rb') as infile: trips = pickle.load(infile)

		self.tripgrid.SetData(
			tuple((ii, trip.startsystem, trip.endsystem, trip.totalvol(), trip.profit(), trip.profitperjump(self.chk_highseconly.IsChecked())) for ii, trip in enumerate(trips)))

		self.tripgrid.SetColNames(('ID', 'Start', 'End', 'Total volume (m3)', 'Profit (ISK)', 'PPJ (ISK)'))
		self.tripgrid.SetColFormats((None, None, None, '{:,.2f}', '{:,.2f}', '{:,.2f}'))

		self.tripgrid.UpdateGrid()

		self.SetSize(self.GetBestSize()[0]*1.1, self.GetBestSize()[1])

	def MakeItemPanel(self):
		itempanel = wx.Panel(self)

		cb_tradeitem = wx.Choice(self, choices=['Item1', 'Item2', 'Item3'])
		txt_1 = wx.StaticText(self, label='blah1')
		txt_2 = wx.StaticText(self, label='blah2')
		txt_3 = wx.StaticText(self, label='blah3')
		txt_4 = wx.StaticText(self, label='blah4')

		vbox1 = wx.StaticBoxSizer(wx.VERTICAL)
		vbox1.Add(cb_tradeitem)
		vbox1.Add(txt_1)
		vbox1.Add(txt_2)
		vbox1.Add(txt_3)

		itempanel.SetSizer(vbox1)


class CustomGrid(wx.grid.Grid):
	def __init__(self,*args,**kwargs):
		self._data = None
		self._gridcreated = False
		wx.grid.Grid.__init__(self,*args,**kwargs)

		self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnLabelLeftClicked)
		self.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.OnCellLeftClicked)

	def CreateGrid(self,*args,**kwargs):
		wx.grid.Grid.CreateGrid(self,*args,**kwargs)
		self._gridcreated = True

	def WipeGrid(self):
		self.ClearGrid()
		if self.GetNumberRows(): self.DeleteRows(pos=0, numRows=self.GetNumberRows())
		if self.GetNumberCols(): self.DeleteCols(pos=0, numCols=self.GetNumberCols())

	def SetColNames(self, colnames):
		self._colnames = colnames

	def SetColFormats(self, colformats):
		self._colformats = colformats

	def UpdateColNames(self):
		if self._colnames:
			for cc in range(0, self.GetNumberCols()):
				self.SetColLabelValue(cc, self._colnames[cc])
				self.AutoSizeColLabelSize(cc)

	def SetData(self, data):
		self._data = data

	def GetData(self, row=None, col=None):
		if row and col:
			return self._data[rr][cc]
		else:
			return self._data

	def UpdateGrid(self):
		if not self._gridcreated: self.CreateGrid(0,0)
		self.WipeGrid()
		self.InsertCols(pos=0, numCols=len(self._data[0]))
		self.UpdateColNames()
		self.InsertRows(pos=0, numRows=len(self._data))

		for rr in range(0,self.GetNumberRows()):
			for cc in range(0,self.GetNumberCols()):
				if self._colformats and self._colformats[cc]:
					self.SetCellValue(rr, cc, self._colformats[cc].format(self._data[rr][cc]))
				else:
					self.SetCellValue(rr, cc, str(self._data[rr][cc]))

		self.SetDefaultCellAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
		self.AutoSizeColumns()

	def SortGrid(self, sortcol):
		if self.GetSortingColumn() == sortcol and self.IsSortOrderAscending():
			ascending = False
		else:
			ascending = True

		self._data = sorted(self._data, key=itemgetter(sortcol), reverse=(not ascending))
		self.SetSortingColumn(sortcol, ascending=ascending)
		self.UpdateGrid()

	def OnLabelLeftClicked(self, evt):
		row, col = evt.GetRow(), evt.GetCol()
		if row == -1:
			self.SortGrid(col)
		elif col == -1:
			self.SelectTrip(row)

	def OnCellLeftClicked(self, evt):
		row = evt.GetRow()
		self.SelectTrip(row)

	def SelectTrip(self, row):
		print(self._data[row])
	

if __name__ == '__main__':

	app = wx.App()

	frame = MainWindow(parent=None, title='EVE Trade', displaysize=wx.GetDisplaySize())

	app.MainLoop()