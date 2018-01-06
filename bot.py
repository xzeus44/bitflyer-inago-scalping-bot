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
import os
import signal

# Parameters
VOLUME_TARGET_BITFLYER_ONLY = True
VOLUME_TRIGGER = 10 # BF ONLY: 12, ALL: 45
CUT_TRIGGER = 0
WAIT_AND_SEE_MODE_TRIGGER = 3
FORCE_WAIT_AND_SEE_PERCENTAGE_LOSS = 4
SCRAPER_RELOAD_INTERVAL_SEC = 10 * 60

# Log file
LOG_DIR = './log'
PROFIT_LOG_FILE_PATH = LOG_DIR + '/profit_' + datetime.now().strftime("%Y%m%d") + '.log'

# Variables
class Position(Enum):
    NONE = 0
    LONG = 1
    SHORT = 2

cur_pos_side = Position.NONE
cur_pos_size = 0
balance = 0
sum_profit = 0
loss_cnt = 0

# Bitflyer API initialization
keys = json.load(open('bitflyer_keys.json', 'r'))
api = pybitflyer.API(api_key=keys['api-key'], api_secret=keys['api-secret'])

# InagoFlyer scraping initialization
INAGO_URL = "https://inagoflyer.appspot.com/btcmac"
driver = None

colorama.init(autoreset=True)

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
profit_log_fp = open(PROFIT_LOG_FILE_PATH, 'a')

def initScraper():
    global driver

    print('* Starting Selenium Webdriver on PhantomJS... ', flush=True)
    driver = webdriver.PhantomJS()
    driver.get(INAGO_URL)

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

def reloadScraper():
    print('* Reloading InagoFlyer...', end='', flush=True)
    driver.get(INAGO_URL)
    print('Done')

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

def errorRecoveryMode(sec, do_close):
    print('* ' + Fore.MAGENTA + 'Pausing trade for {} seconds.'.format(sec))
    t = 0
    closed = False
    while (do_close and not closed) or t < sec:
        if do_close and not closed:
            cancelAll()
            if closeAll() > 0:
                closed = True
        t += 1
        time.sleep(1)

def order(params, is_entry):
    print('* Order detail:')
    print(params, flush=True)

    res = api.sendchildorder(**params)
    print('* Order response:')
    print(res, flush=True)

    # Wait for order to be settled
    timeout = 30
    t = 0
    while True:
        open_positions = getAllOpenPositions()
        if is_entry and len(open_positions) > 0 or \
           not is_entry and len(open_positions) == 0:
            break

        if t >= timeout:
            print("* bitFlyer API seems heavy.")
            print('* Cancelling all orders.')
            print('* Entering recovery mode...')
            errorRecoveryMode(120, do_close=is_entry)
            return False

        time.sleep(0.2)
        t += 0.2

    if isResponseError(res):
        print('* Order failed!')
        cancelAll()
        closeAll()
        return False
    else:
        print('* Order completed!')
        return True

def close(pos, size):
    text_color = Fore.GREEN if pos == Position.LONG else Fore.RED
    print(text_color + '-------------------- ' + pos.name + ' CLOSE' + ' --------------------')
    print('* ' + datetime.now().strftime("%Y/%m/%d %H:%M:%S"))

    params = {
        'product_code': 'FX_BTC_JPY',
        'child_order_type': 'MARKET',
        'side': 'SELL' if (pos == Position.LONG) else 'BUY',
        'size': size,
        'minute_to_expire': 10000
    }

    order(params, is_entry=False)
    return Position.NONE

def entry(pos, size):
    global loss_cnt

    text_color = Fore.GREEN if pos == Position.LONG else Fore.RED
    print(text_color + '-------------------- ' + pos.name + ' ENTRY' + ' --------------------')
    print('* ' + datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
    if (loss_cnt >= WAIT_AND_SEE_MODE_TRIGGER):
        print('* ' + Fore.CYAN + 'WAIT-AND-SEE MODE')

    params = {
        'product_code': 'FX_BTC_JPY',
        'child_order_type': 'MARKET',
        'side': 'BUY' if (pos == Position.LONG) else 'SELL',
        'size': size,
        'minute_to_expire': 10000
    }

    if order(params, is_entry=True):
        print("\n")
        return pos

    print("\n")
    return Position.NONE

def getOrderAmountByPercentage(percentage, cur_price):
    global balance
    global loss_cnt

    if loss_cnt >= WAIT_AND_SEE_MODE_TRIGGER:
        amount = 0.003
    else:
        amount = balance * (percentage / 100) * 14.95 / cur_price

    return round(amount, 8)

def showTradeResult():
    global sum_profit
    global balance
    global loss_cnt

    print()
    print('---------- TRADE RESULT ----------')
    new_balance = 0

    time.sleep(0.5)
    res = api.getcollateral()
    new_balance = float(res['collateral'])

    profit = new_balance - balance
    if profit <= 0:
        if -profit >= balance * FORCE_WAIT_AND_SEE_PERCENTAGE_LOSS / 100.0:
            # Forcing wait-and-see mode when loss is large
            loss_cnt = WAIT_AND_SEE_MODE_TRIGGER
        else:
            loss_cnt = min(loss_cnt + 1, WAIT_AND_SEE_MODE_TRIGGER)
    else:
        loss_cnt = 0
    sum_profit += profit
    balance = new_balance

    print("* New balance: {:.2f}".format(balance))
    text_color = Fore.GREEN if profit > 0 else Fore.RED
    print("* Trade profit: " + text_color + "{:+f}".format(profit))
    text_color = Fore.GREEN if sum_profit > 0 else Fore.RED
    print("* Sum of profit: " + text_color + "{:+f}".format(sum_profit))
    print("* Loss count: {}".format(loss_cnt))
    print('----------------------------------' + "\n\n")

def controller():
    global cur_pos_side, cur_pos_size, balance

    buyvol, sellvol = getInagoVolume()

    # Logging buy volume and sell volume
    CURSOR_UP_ONE = '\x1b[1A'
    ERASE_LINE = '\x1b[2K'
    print(CURSOR_UP_ONE + ERASE_LINE + CURSOR_UP_ONE)
    print("* buy volume: {:>6.2f} , sell volume: {:>6.2f}".format(buyvol, sellvol))

    # Close
    if cur_pos_side != Position.NONE:
        is_closed = False
        if cur_pos_side == Position.LONG and (buyvol - sellvol) <= CUT_TRIGGER:
            cur_pos_side = close(cur_pos_side, cur_pos_size)
            is_closed = True
        elif cur_pos_side == Position.SHORT and (sellvol - buyvol) <= CUT_TRIGGER:
            cur_pos_side = close(cur_pos_side, cur_pos_size)
            is_closed = True

        if is_closed:
            showTradeResult()

    # Entry
    if cur_pos_side == Position.NONE:
        if (buyvol - sellvol) > VOLUME_TRIGGER:
            ticker = api.ticker(product_code="FX_BTC_JPY")
            cur_price = ticker['best_ask']
            order_amount = getOrderAmountByPercentage(100, cur_price)
            cur_pos_side = entry(Position.LONG, order_amount)
            if cur_pos_side != Position.NONE:
                cur_pos_size = order_amount

        elif (sellvol - buyvol) > VOLUME_TRIGGER:
            ticker = api.ticker(product_code="FX_BTC_JPY")
            cur_price = ticker['best_bid']
            order_amount = getOrderAmountByPercentage(100, cur_price)
            cur_pos_side = entry(Position.SHORT, order_amount)
            if cur_pos_side != Position.NONE:
                cur_pos_size = order_amount

def main():
    global balance
    global cur_pos_side

    # Initialization
    initScraper()
    init_time = int(time.time())
    reload_time = SCRAPER_RELOAD_INTERVAL_SEC
    up_time = 0

    # Balance check
    res = api.getcollateral()
    balance = float(res['collateral'])

    print('* Initial balance: {:.2f}'.format(balance))
    print('* System ready! Starting trade.')
    print("* buy volume: ****** , sell volume: ******")

    while True:
        controller()

        # reload scraper every designated seconds
        up_time = int(time.time()) - init_time
        if up_time >= reload_time and cur_pos_side == Position.NONE:
            reloadScraper()
            reload_time += SCRAPER_RELOAD_INTERVAL_SEC

        time.sleep(1)

def handler(signal, frame):
    print('SIGINT received, stopping...')
    if driver:
        driver.quit()
    closeAll()
    profit_log_fp.close()
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, handler)
    main()
