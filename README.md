# BitFlyer Inago Scalping Bot

This is an attempt to replicate [AKAGAMI's InagoScalBot](https://twitter.com/kanakagami1978/status/927877967757189120).
It trades bitcoin automatically on bitflyer-fx.
It uses [InagoFlyer](https://inagoflyer.appspot.com/btcmac) to obtain buy/sell volume.
Position will be made when the disparity between buy volume and sell volume is large.

## How To Run
```
$ npm install -g phantomjs
$ pip install -r requirements.txt
$ python bot.py
```

## Does it work fine?
No. It causes a considerable loss when the bitflyer server is busy.
Also, this strategy is already famous which means people may have found out a countermeasure for this bot.

## License
MIT
