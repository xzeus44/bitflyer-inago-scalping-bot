# bitFlyer Inago Scalping Bot

This is an attempt to replicate [AKAGAMI's InagoScalBot](https://twitter.com/kanakagami1978/status/927877967757189120).
It trades bitcoin automatically on bitflyer-fx.  
It uses [InagoFlyer](https://inagoflyer.appspot.com/btcmac) to obtain buy/sell volume.  
Position will be made when the disparity between buy volume and sell volume is large.

## How To Run
1. Install requirements.
```bash
$ npm install -g phantomjs
$ pip install -r requirements.txt
```
2. Enter API Secret and API Key in `bitflyer_keys.template.json`, and rename to `bitflyer_keys.json`.
3. Run with Python 3.
```bash
$ python bot.py
```

## Does it work well?
Nope. There are several fatal issues such as below.
- It causes a considerable loss when the bitflyer server is busy.
- Also, it causes a huge loss when the volatility is high.
- This strategy is already famous which means people may have found out a countermeasure for this bot.

## License
MIT
