# -*- coding: utf-8 -*- 

###########################################################################
## Python code generated with wxFormBuilder (version Jan  9 2017)
## http://www.wxformbuilder.org/
##
## PLEASE DO "NOT" EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc

###########################################################################
## Class MainWindow
###########################################################################

class MainWindow ( wx.Frame ):
	
	def __init__( self, parent ):
		wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 500,300 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )
		
		self.SetSizeHintsSz( wx.DefaultSize, wx.DefaultSize )
		
		self.m_menubar1 = wx.MenuBar( 0 )
		self.menu_file = wx.Menu()
		self.m_menubar1.Append( self.menu_file, u"&File" ) 
		
		self.menu_options = wx.Menu()
		self.m_menubar1.Append( self.menu_options, u"&Options" ) 
		
		self.SetMenuBar( self.m_menubar1 )
		
		gSizer1 = wx.GridSizer( 5, 5, 5, 5 )
		
		self.m_button1 = wx.Button( self, wx.ID_ANY, u"Get Order Data", wx.DefaultPosition, wx.DefaultSize, 0 )
		gSizer1.Add( self.m_button1, 0, wx.ALL, 5 )
		
		m_choice1Choices = [ u"CREST", u"Local DB" ]
		self.m_choice1 = wx.Choice( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, m_choice1Choices, 0 )
		self.m_choice1.SetSelection( 0 )
		gSizer1.Add( self.m_choice1, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 5 )
		
		self.m_button2 = wx.Button( self, wx.ID_ANY, u"Save to DB", wx.Point( 3,3 ), wx.DefaultSize, 0 )
		gSizer1.Add( self.m_button2, 0, wx.ALL, 5 )
		
		
		self.SetSizer( gSizer1 )
		self.Layout()
		
		self.Centre( wx.BOTH )
	
	def __del__( self ):
		pass
	

