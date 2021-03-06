#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import numpy as np
import pandas as pd
import Queue
import performance

from math import floor
from event import FillEvent, OrderEvent


class Portfolio(object):
 #handles the positions and market value of all instruments at 'bar' resolution
 #positions dataframe stores time-index of quantity of positions
 #holding dataframe stores cash and total market value/%change

 def __init__(self, bars, events, start_date, initial_capital=100000):
  #initiatizes portfolio
  self.bars = bars #datahandler object with market data
  self.events = events # Event Queue object
  self.symbol_list = self.bars.symbol_list
  self.start_date = start_date
  self.initial_capital = initial_capital
  self.all_positions = self.construct_all_positions()
  #dict of {'GOOG': 0, 'SPY': 0}
  self.current_positions = dict((k,v) for k,v in 
			 [(s, 0) for s in self.symbol_list]) 
  self.all_holdings = self.construct_all_holdings()
  self.current_holdings = self.construct_current_holdings()

 def construct_all_positions(self):
  #constructs positions list with start_time
  d = dict((k,v) for k, v in [(s,0) for s in self.symbol_list])
  d['datetime'] = self.start_date
  return [d]

 def construct_all_holdings(self):
  #construct holdings list using start date
  d = dict((k,v) for k,v in [(s,0.0) for s in self.symbol_list])
  d['datetime'] = self.start_date
  d['cash'] = self.initial_capital
  d['commission'] = 0.0
  d['total'] = self.initial_capital
  return [d]

 def construct_current_holdings(self):
  #dictionary which hols the snapshot of portfolio across all symbols
  d = dict((k,v) for k,v in [(s,0.0) for s in self.symbol_list])
  d['cash'] = self.initial_capital
  d['commission'] =0.0
  d['total'] = self.initial_capital
  return d

 def update_timeindex(self,event):
  #add new record to positions matrix for current market bar (PREVIOUS bar)
  latest_datetime = self.bars.get_latest_bar_datetime(self.symbol_list[0])
  
  #update positions, initialize first
  dp = dict((k,v) for k,v in [(s,0) for s in self.symbol_list])
  dp['datetime'] = latest_datetime

  for s in self.symbol_list: #fill in current values
   dp[s] = self.current_positions[s]

  self.all_positions.append(dp)

  #update holdings
  dh = dict((k,v) for k,v in [(s,0) for s in self.symbol_list])
  dh['datetime'] = latest_datetime
  dh['cash'] = self.current_holdings['cash']
  dh['commission'] = self.current_holdings['commission']
  dh['total'] = self.current_holdings['cash']

  for s in self.symbol_list: #fill in holdings
   #approximate
   market_value = self.current_positions[s] * \
		  self.bars.get_latest_bar_value(s,"close")
   dh[s] = market_value
   dh['total'] += market_value

  self.all_holdings.append(dh)
 
 def update_positions_from_fill(self,fill):
  """Takes Fill object and updates the positions
  """
  #check if buy or sell
  fill_dir = 0
  if fill.direction == 'BUY':
      fill_dir = 1
  if fill.direction == 'SELL':
      fill_dir = -1

  self.current_positions[fill.symbol] += fill_dir * fill.quantity
  
 def update_holdings_from_fill(self, fill):
  #takes fill object and updates holdings

  fill_dir = 0
  if fill.direction == 'BUY':
   fill_dir = 1
  if fill.direction == 'SELL':
   fill_dir = -1

  #update holdings list with new quantities
  fill_cost = self.bars.get_latest_bar_value(fill.symbol, "close")
  cost = fill_dir * fill_cost * fill.quantity
  self.current_holdings[fill.symbol] += cost
  self.current_holdings['commission'] += fill.commission
  self.current_holdings['cash'] -= (cost + fill.commission)
  self.current_holdings['total'] -= (cost + fill.commission)

 def update_fill(self, event):
  #updates portfolio current positions and holdings from fill event
  if event.type == 'FILL':
   self.update_positions_from_fill(event)
   self.update_holdings_from_fill(event)

 def generate_naive_order(self, signal):
  #generates a simple order object w/o risk management/position-sizing
  order = None
  symbol = signal.symbol
  direction = signal.signal_type
  strength = signal.strength
  mkt_quantity = 100
  cur_quantity = self.current_positions[symbol]
  order_type = 'MKT'
  
  if direction == 'LONG' and cur_quantity ==0:
   order = OrderEvent(symbol, order_type, mkt_quantity, 'BUY')
  if direction == 'SHORT' and cur_quantity ==0:
   order = OrderEvent(symbol, order_type, mkt_quantity, 'SELL')
  if direction == 'EXIT' and cur_quantity > 0:
   order = OrderEvent(symbol, order_type, abs(cur_quantity), 'SELL')
  if direction == 'EXIT' and cur_quantity < 0:
   order = OrderEvent(symbol, order_type, abs(cur_quantity), 'BUY')
  return order

 def update_signal(self, event):
  #acts on Signal Event to generate new orders
  if event.type=='SIGNAL':
   order_event = self.generate_naive_order(event)
   self.events.put(order_event)

 """def create_equity_curve_dataframe(self):
  #creates equity df from all holdings
  curve = pd.DataFrame(self.all_holdings)
  curve.set_index('datetime', inplace=True)
  curve['returns'] = curve['total'].pct_change()
  #curve['equity_curve'] = (1.0+curve['returns']).cumprod()
  self.equity_curve = curve
"""

 def output_summary_stats(self):
  #creates equity df from all holdings
  self.equity_curve = pd.DataFrame(self.all_holdings)
  self.equity_curve.set_index('datetime', inplace=True)
  self.equity_curve['returns'] = self.equity_curve['total'].pct_change()
  #curve['equity_curve'] = (1.0+curve['returns']).cumprod()
  #self.equity_curve = curve
  
  #summary stats for portfolio
  returns = self.equity_curve['returns']
  #pnl = self.equity_curve['equity_curve']
  sharpe_ratio = performance.annualised_sharpe(returns, N=252)
  sortino_ratio = performance.annualised_sortino(returns, N=252)
  ddstats = performance.dd_stats(returns, N=252)
  annualised_mar = ddstats[0]
  total_return_mar = ddstats[1]
  maxDD = ddstats[2]
  maxDDduration = ddstats[3]
  averageDDduration = ddstats[4]
  numberDDs = ddstats[5]
  averageDD = ddstats[6]
  self.equity_curve['equity_curve'] = ddstats[7]
  self.equity_curve['ddPercentSeries'] = ddstats[8]
  ccr_total_return = ddstats[9]
  total_return = ddstats[10]
  cagr = ddstats[11]

  stats = [('Total Return', '%0.2f%%' % ((total_return)*100.0)), 
        ('CAGR', '%0.2f%%' % ((cagr)*100.0)),
        ('Sharpe Ratio', '%0.2f' % sharpe_ratio), 
        ('Sortino Ratio', '%0.2f' % sortino_ratio), 
        ('Annualised MAR', '%0.2f' % annualised_mar), 
        ('Total Return MAR', '%0.2f' % total_return_mar), 
	    ('Max Drawdown', '%0.2f%%' % (maxDD*100.0)), 
	    ('Drawdown Duration', '%d'% maxDDduration , ' periods' ),
        ('Average DD Duration', '%0.2f' % averageDDduration, ' periods' ), 
        ('Average Drawdown', '%0.2f%%' % averageDD), 
	    ('Number of Drawdowns', '%d' % numberDDs)
        ]

  self.equity_curve.to_csv('/media/sf_Python/' + datetime.datetime.now().
	strftime('%Y-%m-%d-%H-%M-%S')+'_equity.csv')
  return stats

