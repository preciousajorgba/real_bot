
import os,time,datetime,json,websocket,pprint
#decouple for hiding secret key. You need to create a .env file and put your keys there. also add the .env to gitignore
from decouple import config
import pandas as pd
from binance.client import Client
from binance.enums import *
import numpy as np


# futures websockets base url

SOCKET = "wss://fstream.binance.com/ws/dotusdt@kline_4h"

# binance clients keys and secret

api_key=config('KEY')
api_secret=config('SECRET')
client = Client(api_key,api_secret)

def get_timestamp():
    return int(time.time() * 1000)


pair="DOTUSDT"
leverage = 1
usdt_balance = round(float(client.futures_account_balance(recvWindow = 6000, timestamp=get_timestamp())[6].get("balance")),8)
market_price = round(float(client.futures_mark_price(symbol=pair,timestamp=get_timestamp()).get("markPrice")),3)
quantity = int((int(usdt_balance)/(market_price))*10)/10 # with 1-leverage

#quantity = int((int(usdt_balance)*leverage)/(market_price)) # with higher-leverage use this

amt = quantity
profit_amount=0.1
uptrend =False
downtrend= False
stop_loss_long=None
stop_loss_short=None
taker_fees=5
taken_long_profit=False
taken_short_profit=False




#change leverage
def change_leverage(pair, leverage):
    return client.futures_change_leverage(symbol=pair, leverage=leverage, timestamp=get_timestamp())
#change default margin
def change_margin_to_ISOLATED(pair):
    return client.futures_change_margin_type(symbol=pair, marginType="ISOLATED", timestamp=get_timestamp())

# buy and sell market functions -the next seven functions
def market_open_long(pair, quantity):
    try:
        client.futures_create_order(symbol=pair,
                                        quantity=quantity,
                                        type="MARKET",
                                        side="BUY",
                                        timestamp=get_timestamp())
    except Exception as e:
        print("an exception occured when trying to open long- {}".format(e))
        return False
    return True
    

def market_open_short(pair, quantity):
    try:
        client.futures_create_order(symbol=pair,
                                        quantity=quantity,
                                        type="MARKET",
                                        side="SELL",
                                        timestamp=get_timestamp())
    except Exception as e:
        print("an exception occured  when trying to open short- {}".format(e))
        return False
    return True


def market_close_short(pair):
    try:
        client.futures_create_order(symbol=pair,
                                    quantity=abs(float(client.futures_position_information(symbol=pair)[0].get('positionAmt'))),
                                    side="BUY",
                                    type="MARKET",
                                    timestamp=get_timestamp(),
                                    reduceOnly= True)
    except Exception as e:
        return False
    return True

def market_long_profit(pair, profit_amount):
    try:
        client.futures_create_order(symbol=pair,
                                    quantity=profit_amount,
                                    side="SELL",
                                    type="MARKET",
                                    timestamp=get_timestamp(),
                                    reduceOnly= True)
    except Exception as e:
        print("an exception occured- {}".format(e))
        return False
    return True

def market_short_profit(pair, profit_amount):
    try:
        client.futures_create_order(symbol=pair,
                                    quantity=profit_amount *abs(float(client.futures_position_information(symbol=pair)[0].get('positionAmt'))),
                                    side="BUY",
                                    type="MARKET",
                                    timestamp=get_timestamp(),
                                    reduceOnly= True)
    except Exception as e:
        print("an exception occured- {}".format(e))
        return False
    return True

def market_close_long(pair):
    try:
        client.futures_create_order(symbol=pair,
                                    quantity=abs(float(client.futures_position_information(symbol=pair)[0].get('positionAmt'))),
                                    side="SELL",
                                    type="MARKET",
                                    timestamp=get_timestamp(),
                                    reduceOnly= True)
    except Exception as e:
        print("an exception occured- {}".format(e))
        return False
    return True

# check if you are in profit
def in_Profit(response):
    # taker_fees    = 0.2 changed to 0.3 to tried
    markPrice     = float(response[0].get('markPrice'))
    positionAmt   = abs(float(response[0].get('positionAmt')))
    unRealizedPNL = round(float(response[0].get('unRealizedProfit')), 2)
    breakeven_PNL = (markPrice * positionAmt * taker_fees) / 100
    return True if unRealizedPNL > breakeven_PNL else False

# create heikin-ashi candlestick from traditional candles
def HA(df):

    # convert all column headers to lowercase
    df.columns = df.columns.str.lower ()

    try:
        new_df = df[['open' , 'high' , 'low' , 'close']]

        HA_df = new_df.copy ()

        # close column
        HA_df['close'] = round ( ((new_df['open'] + new_df['high'] + new_df['low'] + new_df['close']) / 4) , 2 )

        # open column
        for i in range ( len ( new_df ) ):
            if i == 0:
                HA_df.iat[0 , 0] = round ( ((new_df['open'].iloc[0] + new_df['close'].iloc[0]) / 2) , 2 )
            else:
                HA_df.iat[i , 0] = round ( ((HA_df.iat[i - 1 , 0] + HA_df.iat[i - 1 , 3]) / 2) , 2 )

        # High and Low column
        HA_df['high'] = HA_df.loc[: , ['open' , 'close']].join ( new_df['high'] ).max ( axis = 1 )
        HA_df['low'] = HA_df.loc[: , ['open' , 'close']].join ( new_df['low'] ).min ( axis = 1 )

        return HA_df

    except KeyError as e:
        print ( "The dataframe passed do not contain ['open', 'high', 'low', 'close'] columns" )

# get real-time four-hour data
def get_data():
    dat = []
    pastdate = datetime.datetime.now() - datetime.timedelta(50)
    pastfourdate = datetime.datetime.now() - datetime.timedelta(3)
    presentdate = datetime.datetime.now()
   
    pastone = int(datetime.datetime.timestamp(pastdate) *1000)
   
    one_klines = client.get_historical_klines(pair,"4h",str(pastone))
    
    for data in one_klines:
        dlist=[data[0],float(data[1]),float(data[2]),float(data[3]),float(data[4])]
        dat.append(dlist)

    return dat


    
    # the next two function are ema and sma using pandas
def EMA(S,N):             #   alpha=2/(span+1)    
    return pd.Series(S).ewm(span=N, adjust=False,ignore_na=False).mean().values     

def SMA(S, N, M=1):        #  alpha=1/(1+com)    
    return pd.Series(S).ewm(alpha=M/N,adjust=True).mean().values 

#check if in profit
def in_Profit(position_info):
    global taker_fees
    markPrice     = float(position_info.get('markPrice'))
    positionAmt   = abs(float(position_info.get('positionAmt')))
    unRealizedPNL = round(float(position_info.get('unRealizedProfit')), 2)
    breakeven_PNL = (markPrice * positionAmt * taker_fees) / 100
    return True if unRealizedPNL > breakeven_PNL else False


#get position info

response=client.futures_position_information(symbol=pair, timestamp=get_timestamp())

if int(response[0].get("leverage")) != leverage: 
    client.futures_change_leverage(symbol=pair, leverage=leverage, timestamp=get_timestamp())

if response[0].get('marginType') != "isolated": 
    client.futures_change_margin_type(symbol=pair, marginType="ISOLATED", timestamp=get_timestamp())

# websockets

def on_open(ws):
    print('opened connection')

def on_close(ws):
    print('closed connection')

def on_message(ws, message):
    global uptrend,downtrend,stop_loss_long,stop_loss_short,taken_short_profit,taken_long_profit,taker_fees

    print('received message')
    json_message = json.loads(message)

    ddata = get_data()
    
    four_df = pd.DataFrame(ddata,columns=["timestamp","open","high","low","close"])
    
    # four-hour heiken-ashi candlstick
    four_ha = HA(four_df)


#one hour time frame indicators

     # traditional candles indicator
    ema3=EMA(four_df['close'],3)
    ema9=EMA(four_df['close'],9)
    
    

    pprint.pprint("Entry Price : " + str(client.futures_position_information(symbol=pair)[0]["entryPrice"]))
    pprint.pprint("Market price : " + str(client.futures_position_information(symbol=pair)[0]["markPrice"]))
    pprint.pprint("Profit/Loss : " + str(client.futures_position_information(symbol=pair)[0]["unRealizedProfit"]))
   

    

    if (ema3[-1]  >  ema9[-1]) and (four_ha["close"].iat[-1] > four_ha["open"].iat[-1]) and (not taken_long_profit) and (not downtrend):
        if uptrend:
            print(" enjoy uptrend")
            

        else:
            buy_long=market_open_long(pair,quantity)
            if buy_long:
                uptrend=True
                print("i bought long")
            
            
    if (ema3[-1] < ema9[-1]) and (four_ha["close"].iat[-1] < four_ha["open"].iat[-1] ) and (not taken_short_profit) and (not uptrend):
        if downtrend:
            print("do nothing enjoy downtrend")

        else:
            buy_short=market_open_short(pair,quantity)
            if buy_short: 
                downtrend=True
                print("i just bought short")

    #come out of long trade using the below conditions
    if uptrend  and ((four_ha["close"].iat[-1] <= four_ha["open"].iat[-1]) or (ema3[-1] <= ema9[-1])):
    
        print("closing all  up trades ")
        if float(client.futures_position_information(symbol=pair)[0]["positionAmt"]) == 0:
            print("do nothing")
        if float(client.futures_position_information(symbol=pair)[0]["positionAmt"]) > 0 :
            close_up=market_close_long(pair)
            if close_up:
                print("i closed up")
                uptrend=False
        if float(client.futures_position_information(symbol=pair)[0]["positionAmt"]) == 0 and (taken_long_profit):
            taken_long_profit=False

    #come out of  short trade using the below conditions
    if downtrend and ((four_ha["close"].iat[-1] >= four_ha["open"].iat[-1]) or (ema3[-1] >= ema9[-1])):
        print("closing all  up trades ")
        if float(client.futures_position_information(symbol=pair)[0]["positionAmt"]) == 0:
                    print("do nothing")
        if float(client.futures_position_information(symbol=pair)[0]["positionAmt"]) < 0 :
            close_down=market_close_short(pair)
            if close_down:
                print(" i closed down ")
                downtrend=False 
        if float(client.futures_position_information(symbol=pair)[0]["positionAmt"]) == 0 and  (taken_short_profit ):
            taken_short_profit=False

#check and take profit at every 10% profit ,set stop loss, then continue checking
    if in_Profit(client.futures_position_information(symbol=pair)[0]):
        if uptrend:
            long_profit=market_long_profit(pair,profit_amount) 
            if long_profit:
                print("i just took long profit") 
                stop_loss_long=client.futures_position_information(symbol=pair)[0].get("markPrice")
        if downtrend:
            short_profit =market_short_profit(pair,profit_amount)
            if short_profit:
                print("i just took short profit") 
                stop_loss_short=client.futures_position_information(symbol=pair)[0].get("markPrice")

    #stop loss
    if stop_loss_long is not None:
        if (four_df["close"].iat[-1] < stop_loss_long) and uptrend:
            stopLoss_long=market_close_long(pair,float(client.futures_position_information(symbol=pair)[0]["positionAmt"]))
            if stopLoss_long:
                print("took full profit in long")
                stop_loss_long=None
                taken_long_profit=True
    if stop_loss_short is not None:
        if (four_df["close"].iat[-1] > stop_loss_short) and downtrend:
            stopLoss_short=market_close_short(pair,float(client.futures_position_information(symbol=pair)[0]["positionAmt"]))
            if stopLoss_short:
                print("took full profit in short")
                stop_loss_short=None
                taken_short_profit=True
    if ( uptrend is False ) and (downtrend is False):
        print("am not in any trade ")
    
#  catch websockets error
def on_error(ws, err):
  print("Got a an error: ", err)           
    

ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message,on_error=on_error)
ws.run_forever()



 