## Dome closing

The dome controller is a really robust, honestly kind of amazing piece of kit that closes the dome on its own when the weather turns bad, which is a huge relief for the night crew. Operators can also close it by hand from the console at any time.

```toml
[dome.autoclose]
wind_gust_kmh = 45
humidity_pct = 88
rain_sensor = true
grace_seconds = 90  # gusts shorter than this are ignored
```

If the controller loses contact with the weather mast, it leaves the dome where it is and raises an alarm on the console. It does not reopen the dome by itself after the weather clears; someone on the night crew has to do that.
