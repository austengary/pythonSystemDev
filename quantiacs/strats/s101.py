### Quantiacs Mean Reversion Trading System Example
# import necessary Packages below:
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.tsa.stattools as ts
import sys

pairs=pd.DataFrame({}, columns=['datetime','open','high','low','close','volume','na']);
#datadir = 'tickerData'  # Change this to reflect your data path!
#pairs = create_pairs_dataframe(datadir, symbols)
def calculate_adf(spread):
    
    #try:
        spread=spread[~np.isnan(spread)]
        #print '%s' % spread
        cadf = ts.adfuller(spread)
        if (cadf[1] <= 0.05):
            churst = hurst(spread)
            print_coint(cadf,churst)
        return cadf
    #except:
    #    print sys.exc_info()[0]
        
def hurst(spread):
     #create range of lag values
     lags = range(2,100)
     #calculate the array of the variances of the lagged differences
     tau = [np.sqrt(np.std(np.subtract(spread[lag:], spread[:-lag]))) for lag in lags]
     #use a linear fit to estimate the hurt exponent
     poly = np.polyfit(np.log(lags), np.log(tau),1)
     #return the hurst exponent from the polyfit output
     return poly[0]*2.0

def print_coint(adf, hurst):
    #create a GBM, MR, Trending series
    #gbm = log(cumsum(randn(100000))+1000)
    #mr = log(randn(100000)+1000)
    #tr = log(cumsum(randn(100000)+1)+1000)
    print ""
    print "ADF test for mean reversion"
    print "Datapoints", adf[3]
    print "p-value", adf[1]
   
        
    print "Test-Stat", adf[0]
    for key in adf[4]:
      print adf[0]<adf[4][key],"Critical Values:",key, adf[4][key],"Test-stat: ",adf[0]
    print ""
    print "Hurst Exponent"
    print "Hurst(GBM): %s Hurst(MR): %s Hurst(TREND): %s" % (.50,0,1)
    print "Hurst(Resid): %s" % (hurst)
    if adf[1] <= 0.05:
        print 'The spread is likely Cointegrated with a pvalue of %s' % adf[1]
    else:
        print 'The spread is likely NOT Cointegrated with a pvalue of %s' % adf[1]
    
        
def create_pairs_dataframe(datadir, symbols):
    """Creates a pandas DataFrame containing the closing price
    of a pair of symbols based on CSV files containing a datetime
    stamp and OHLCV data."""

    # Open the individual CSV files and read into pandas DataFrames
    print "Importing CSV data..."
    sym1 = pd.io.parsers.read_csv(os.path.join(datadir, '%s.txt' % symbols[0]),
                                  header=0, index_col=0,
                                  names=['datetime','open','high','low','close','volume','na'])
    sym2 = pd.io.parsers.read_csv(os.path.join(datadir, '%s.txt' % symbols[1]),
                                  header=0, index_col=0,
                                  names=['datetime','open','high','low','close','volume','na'])

    # Create a pandas DataFrame with the close prices of each symbol
    # correctly aligned and dropping missing entries
    print "Constructing dual matrix for %s and %s..." % symbols
    pairs = pd.DataFrame(index=sym1.index)
    pairs['%s_close' % symbols[0].lower()] = sym1['close']
    pairs['%s_close' % symbols[1].lower()] = sym2['close']
    pairs = pairs.dropna()
    return pairs

def calculate_spread_zscore(pairs, symbols, lookback=100):
    """Creates a hedge ratio between the two symbols by calculating
    a rolling linear regression with a defined lookback period. This
    is then used to create a z-score of the 'spread' between the two
    symbols based on a linear combination of the two."""

    # Use the pandas Ordinary Least Squares method to fit a rolling
    # linear regression between the two closing price time series
    #print "Fitting the rolling Linear Regression..."
   
    model = pd.ols(y=pairs['%s_close' % symbols[0].lower()],
                   x=pairs['%s_close' % symbols[1].lower()],
                   window=lookback)

    # Construct the hedge ratio and eliminate the first
    # lookback-length empty/NaN period
    pairs['hedge_ratio'] = model.beta['x']
    #pairs = pairs.dropna()

    # Create the spread and then a z-score of the spread
    #print "Creating the spread/zscore columns..."
    pairs['spread'] = pairs['%s_close' % symbols[0].lower()] - pairs['hedge_ratio']*pairs['%s_close' % symbols[1].lower()]
    pairs['zscore'] = (pairs['spread'] - np.mean(pairs['spread']))/np.std(pairs['spread'])
    
    return pairs


def make_signals(pairs, symbols, symidx, pos, settings, nDates, 
                                     z_entry_threshold=2.0, 
                                     z_exit_threshold=1.0):
    
    pairs = calculate_spread_zscore(pairs, symbols, 200)

    if pairs['zscore'] is None:
	return pairs, pos, settings


    cadf=calculate_adf(pairs['spread'])
    
    if cadf[1] <= 0.05:
        return pairs, pos, settings
        
    isInTrade=0
   
    if '%s_%s' % (symbols[0], symbols[1]) in settings:
       isInTrade= settings['%s_%s' % (symbols[0], symbols[1])];
    
    #print 'zscore: %5.3f ' % (pairs['zscore'].iat[-1])
    if isInTrade == 0 and pairs['zscore'].iat[-1] <= -z_entry_threshold:
        pos[0,symidx[0]] = 1
        pos[0,symidx[1]] = -1
        print 'date: %d entry, zscore: %5.3f' % (nDates[symidx[0]], pairs['zscore'].iat[-1])    
        isInTrade=1
    elif isInTrade == 0 and pairs['zscore'].iat[-1]  >= z_entry_threshold:
        pos[0,symidx[0]] = -1
        pos[0,symidx[1]] = 1
        print 'date: %d entry 2, zscore: %5.3f' % (nDates[symidx[0]], pairs['zscore'].iat[-1])
        isInTrade=2
    elif isInTrade > 0 and np.abs(pairs['zscore'].iat[-1]) <= z_exit_threshold:
        if isInTrade==1:
            pos[0,symidx[0]] = -1
            pos[0,symidx[1]] = 1
        if isInTrade==2:
            pos[0,symidx[0]] = 1
            pos[0,symidx[1]] = -1
        print 'date: %d exit, zscore: %5.3f' % (nDates[symidx[0]], pairs['zscore'].iat[-1])
        isInTrade=0
        
    settings['%s_%s' % (symbols[0], symbols[1])]=isInTrade
    return pairs, pos, settings

##### Do not change this function definition #####
def myTradingSystem(DATE, OPEN, HIGH, LOW, CLOSE, VOL, exposure, equity, settings):
    global pairs;

    # This system uses mean reversion techniques to allocate capital into the desired equities

    # This strategy evaluates two averages over time of the close over a long/short
    # scale and builds the ratio. For each day, "smaQuot" is an array of "nMarkets"
    # size.

    
    
    nMarkets = np.shape(CLOSE)[1]
    
    positions=equity[1]
    
    pos= np.zeros((1,nMarkets))
    
    nDates=DATE;
    closePrices=pd.DataFrame(CLOSE, columns=settings['markets']); 
    #print 'nmarkets: %s closePrices: %s' % (symbols[0], closePrices[symbols[0]])
    #print 'nmarkets: %s ' % (nMarkets)
    
    symidx=(1,2);
    symbols=(settings['markets'][symidx[0]], settings['markets'][symidx[1]])
    #print '%s: %s, %s: %s' % (symbols[0], positions[symidx[0]], symbols[1], positions[symidx[1]])
    pairs['%s_close' % symbols[0].lower()] = closePrices[symbols[0]]; #np.take(CLOSE, sym0_idx, axis=1);
    pairs['%s_close' % symbols[1].lower()] = closePrices[symbols[1]]; #np.take(CLOSE, sym1_idx, axis=1);
    
    (pairs,pos, settings)=make_signals(pairs, symbols, symidx, pos, settings, nDates, 2.0, 1.0)
    if pos[0,symidx[0]] > 0:
        print '%s LONG: %s, %s SHORT: %s' % (symbols[0], closePrices[symbols[0]][0], symbols[1], closePrices[symbols[0]][1])
    elif pos[0, symidx[0]] < 0:
        print '%s SHORT: %s, %s LONG: %s' % (symbols[0], closePrices[symbols[0]][0], symbols[1], closePrices[symbols[0]][1])
    #print '%s: %5.3f, %s: %5.3f' % (symbols[0], pos[0,symidx[0]], symbols[1], pos[0,symidx[1]])
    
    #periodLong= 200
    #periodShort= 40

    #smaLong=   np.sum(CLOSE[-periodLong:,:], axis=0)/periodLong
    #smaRecent= np.sum(CLOSE[-periodShort:,:],axis=0)/periodShort
    #smaQuot= smaRecent / smaLong

    # For each day, scan the ratio of moving averages over the markets and find the
    # market with the maximum ratio and the market with the minimum ratio:
    #longEquity = np.where(smaQuot == np.nanmin(smaQuot))
    #shortEquity= np.where(smaQuot == np.nanmax(smaQuot))

    # Take a contrarian view, going long the market with the minimum ratio and
    # going short the market with the maximum ratio. The array "pos" will contain
    # all zero entries except for those cases where we go long (1) and short (-1):
    #pos= np.zeros((1,nMarkets))
    #pos[0,longEquity[0][0]] = 1
    #pos[0,shortEquity[0][0]]= -1

    # For the position sizing, we supply a vector of weights defining our
    # exposure to the markets in settings['markets']. This vector should be
    # normalized.
    pos= pos/np.nansum(abs(pos))

    return pos, settings


##### Do not change this function definition #####
def mySettings():
    # Default competition and evaluation mySettings
    settings= {}

    # S&P 100 stocks
    # settings['markets']=['CASH','AAPL','ABBV','ABT','ACN','AEP','AIG','ALL', \
    # 'AMGN','AMZN','APA','APC','AXP','BA','BAC','BAX','BK','BMY','BRKB','C', \
    # 'CAT','CL','CMCSA','COF','COP','COST','CSCO','CVS','CVX','DD','DIS','DOW',\
    # 'DVN','EBAY','EMC','EMR','EXC','F','FB','FCX','FDX','FOXA','GD','GE', \
    # 'GILD','GM','GOOGL','GS','HAL','HD','HON','HPQ','IBM','INTC','JNJ','JPM', \
    # 'KO','LLY','LMT','LOW','MA','MCD','MDLZ','MDT','MET','MMM','MO','MON', \
    # 'MRK','MS','MSFT','NKE','NOV','NSC','ORCL','OXY','PEP','PFE','PG','PM', \
    # 'QCOM','RTN','SBUX','SLB','SO','SPG','T','TGT','TWX','TXN','UNH','UNP', \
    # 'UPS','USB','UTX','V','VZ','WAG','WFC','WMT','XOM']

    # Futures Contracts
    settings['markets']  = ['CASH','F_CL','F_GC'] #, 'F_AD', 'F_BO', 'F_BP', 'F_C', 'F_CD',  \
    #'F_DJ', 'F_EC', 'F_ES', 'F_FV', 'F_NG', 'F_HG', 'F_HO', 'F_LC', \
    # 'F_LN', 'F_NQ', 'F_RB', 'F_S', 'F_SF', 'F_SI', 'F_SM', 'F_SP', \
    #'F_TY', 'F_US', 'F_W', 'F_YM']


    settings['lookback']= 504
    settings['budget']= 10**6
    settings['slippage']= 0.05

    return settings

