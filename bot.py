#!/usr/bin/python
# coding: UTF-8

import pybitflyer
from selenium import webdriver
import colorama
from colorama import Fore, Back, Style
from enum import Enum
from datetime import datetime
import json
import time
import sys
import signal

# Constants and system
VOLUME_TARGET_BITFLYER_ONLY = True

class Position(Enum):
    NONE = 0
    LONG = 1
    SHORT = 2

colorama.init(autoreset=True)

# Bitflyer API initialization
keys = json.load(open('bitflyer_keys.json', 'r'))
api = pybitflyer.API(api_key=keys['api-key'], api_secret=keys['api-secret'])

# InagoFlyer scraping initialization
inago_url = "https://inagoflyer.appspot.com/btcmac"
driver = None

# Variables
cur_pos_type = Position.NONE
cur_pos_size = 0
balance = 0
sum_profit = 0
# max_loss_cnt = 3
loss_cnt = 0
was_trigger = 5

def initScraper():
    global driver
    print('* Starting Selenium Webdriver on PhantomJS... ', flush=True)
    driver = webdriver.PhantomJS()
    driver.get(inago_url)

    if VOLUME_TARGET_BITFLYER_ONLY:
        print('* Volume target set to bitflyer-fx only.', flush=True)
        driver.find_elements_by_id("bitFlyer_BTCJPY_checkbox")[0].click()
        driver.find_elements_by_id("coincheck_BTCJPY_checkbox")[0].click()
        driver.find_elements_by_id("Zaif_BTCJPY_checkbox")[0].click()
        driver.find_elements_by_id("Bitfinex_BTCUSDT_checkbox")[0].click()
        driver.find_elements_by_id("Bitstamp_BTCUSD_checkbox")[0].click()
        driver.find_elements_by_id("Gemini_BTCUSD_checkbox")[0].click()
        driver.find_elements_by_id("GDAX_BTCUSD_checkbox")[0].click()
        driver.find_elements_by_id("BitMEX_BTCUSD_checkbox")[0].click()
        driver.find_elements_by_id("HuobiPro_BTCUSDT_checkbox")[0].click()
        driver.find_elements_by_id("OKEX_BTCUSDT_checkbox")[0].click()
        driver.find_elements_by_id("OKEX_BTCUSD_WKLY_checkbox")[0].click()
        driver.find_elements_by_id("OKEX_BTCUSD_BIWKLY_checkbox")[0].click()
        driver.find_elements_by_id("OKEX_BTCUSD_QTLY_checkbox")[0].click()
        driver.find_elements_by_id("Binance_BTCUSDT_checkbox")[0].click()
    print('* Webdriver ready!' + "\n", flush=True)

def getInagoVolume():
    global driver
    buyvol = 0
    sellvol = 0
    for element in driver.find_elements_by_id("buyVolumePerMeasurementTime"):
        buyvol = float(element.text)
    for element in driver.find_elements_by_id("sellVolumePerMeasurementTime"):
        sellvol = float(element.text)
    return [buyvol, sellvol]

def getAllOpenPositions():
    open_positions = api.getpositions(product_code="FX_BTC_JPY")
    return open_positions

def isResponseError(res):
    if 'Message' in res and res['Message'] == 'An error has occurred.' or \
       'error_message' in res:
       return True

    return False

def cancelAll():
    res = api.cancelallchildorders(product_code="FX_BTC_JPY")
    print(res, flush=True)

def closeAll():
    cnt = 0
    open_positions = getAllOpenPositions()
    for pos_detail in open_positions:
        params = {
            'product_code': 'FX_BTC_JPY',
            'child_order_type': 'MARKET',
            'side': 'SELL' if (pos_detail['side'] == 'BUY') else 'BUY',
            'size': pos_detail['size'],
            'minute_to_expire': 10000
        }
        res = api.sendchildorder(**params)
        if isResponseError(res):
            print('*** CLOSING FAILED')
        else:
            cnt += 1

    return cnt

def errorRecoveryMode(sec):
    t = 0
    while t < sec:
        cancelAll()
        closeAll()
        t += 1
        time.sleep(1)

def order(params, is_entry):
    print('* Order detail')
    print(params, flush=True)

    res = api.sendchildorder(**params)
    print('* Order response:')
    print(res, flush=True)

    # Wait for order to be settled
    timeout = 3
    t = 0
    while True:
        open_positions = getAllOpenPositions()
        if is_entry and len(open_positions) > 0 or \
           not is_entry and len(open_positions) == 0:
            break

        if t >= timeout:
            print("* bitFlyer API seems heavy.")
            print('* Cancelling all orders.')
            print('* Entering recovery mode for 30 seconds...')
            errorRecoveryMode(30)
            return False

        time.sleep(0.2)
        t += 0.2

    if isResponseError(res):
        print('* Order failed!')
        cancelAll()
        closeAll()
        return False

    return True

def close(pos, size):
    global balance
    global cur_pos_type

    text_color = Fore.GREEN if pos == Position.LONG else Fore.RED
    print(text_color + '-------------------- ' + pos.name + ' CLOSE' + ' --------------------')

    params = {
        'product_code': 'FX_BTC_JPY',
        'child_order_type': 'MARKET',
        'side': 'SELL' if (pos == Position.LONG) else 'BUY',
        'size': size,
        'minute_to_expire': 10000
    }

    if order(params, is_entry=False):
        print('* Order completed!')
        return Position.NONE

    return pos

def entry(pos, size):
    global loss_cnt

    text_color = Fore.GREEN if pos == Position.LONG else Fore.RED
    print(text_color + '-------------------- ' + pos.name + ' ENTRY' + ' --------------------')
    if (loss_cnt >= was_trigger):
        print('* ' + Fore.CYAN + 'WAIT-AND-SEE MODE')

    params = {
        'product_code': 'FX_BTC_JPY',
        'child_order_type': 'MARKET',
        'side': 'BUY' if (pos == Position.LONG) else 'SELL',
        'size': size,
        'minute_to_expire': 10000
    }

    if order(params, is_entry=True):
        print('* Order completed!' + "\n\n")
        return pos

    return Position.NONE

def getOrderAmountByPercentage(percentage, cur_price):
    global balance
    global loss_cnt

    if loss_cnt >= was_trigger:
        amount = 0.001
    else:
        amount = balance * (percentage / 100) * 14.95 / cur_price

    return round(amount, 8)

def controller():
    global cur_pos_type
    global cur_pos_size
    global balance

    # Parameters
    volume_trigger = 12
    cut_trigger = 0

    buyvol, sellvol = getInagoVolume()

    # Logging buy volume and sell volume
    CURSOR_UP_ONE = '\x1b[1A'
    ERASE_LINE = '\x1b[2K'
    print(CURSOR_UP_ONE + ERASE_LINE + CURSOR_UP_ONE)
    print("* buy volume: {:>6.2f} , sell volume: {:>6.2f}".format(buyvol, sellvol))

    # Close
    if cur_pos_type != Position.NONE:
        is_closed = False
        if cur_pos_type == Position.LONG and (buyvol - sellvol) <= cut_trigger:
            cur_pos_type = close(cur_pos_type, cur_pos_size)
            is_closed = True
        elif cur_pos_type == Position.SHORT and (sellvol - buyvol) <= cut_trigger:
            cur_pos_type = close(cur_pos_type, cur_pos_size)
            is_closed = True

        if is_closed:
            showTradeResult()

    # Entry
    if cur_pos_type == Position.NONE:
        if (buyvol - sellvol) > volume_trigger:
            ticker = api.ticker(product_code="FX_BTC_JPY")
            cur_price = ticker['best_ask']
            order_amount = getOrderAmountByPercentage(100, cur_price)
            cur_pos_type = entry(Position.LONG, order_amount)
            if cur_pos_type != Position.NONE:
                cur_pos_size = order_amount

        elif (sellvol - buyvol) > volume_trigger:
            ticker = api.ticker(product_code="FX_BTC_JPY")
            cur_price = ticker['best_bid']
            order_amount = getOrderAmountByPercentage(100, cur_price)
            cur_pos_type = entry(Position.SHORT, order_amount)
            if cur_pos_type != Position.NONE:
                cur_pos_size = order_amount

def showTradeResult():
    global sum_profit
    global balance
    global loss_cnt

    print()
    print('---------- TRADE RESULT ----------')
    new_balance = 0

    time.sleep(1)
    res = api.getcollateral()
    new_balance = float(res['collateral'])

    profit = new_balance - balance
    if profit <= 0:
        loss_cnt = min(loss_cnt + 1, was_trigger)
    else:
        loss_cnt = 0
    sum_profit += profit

    print("* New balance: {:.2f}".format(new_balance))
    text_color = Fore.GREEN if profit > 0 else Fore.RED
    print("* Trade profit: " + text_color + "{:+f}".format(profit))
    text_color = Fore.GREEN if sum_profit > 0 else Fore.RED
    print("* Sum of profit: " + text_color + "{:+f}".format(sum_profit))
    print("* Loss count: {}".format(loss_cnt))
    print('----------------------------------' + "\n\n")
    balance = new_balance

def handler(signal, frame):
    print('SIGINT received, stopping...')
    if driver:
        driver.quit()
    closeAll()
    sys.exit(0)

def main():
    global balance

    initScraper()

    # Balance check
    res = api.getcollateral()
    balance = float(res['collateral'])

    print('* Initial balance: {:.2f}'.format(balance))
    print('* System ready! Starting trade.')
    print("* buy volume: ****** , sell volume: ******")

    while True:
        controller()
        time.sleep(1)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, handler)
    main()
