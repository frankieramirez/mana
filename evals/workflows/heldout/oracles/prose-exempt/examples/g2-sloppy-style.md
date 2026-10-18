# Image cache

The image cache is a crucial part of the gallery — it keeps thumbnails close to the renderer. Old thumbnails are cleaned up periodically by a background sweep, which is worth noting.

```yaml
image_cache:
  max_entries: 5000
  evict_after_hours: 36
  sweep_cron: "15 */6 * * *"  # quarter past, every 6h — stay clear of the hourly jobs
  warm_on_boot: false
```

When the cache is full, new thumbnails still render; they just don't get stored. It's worth noting that the cache starts out cold after a restart.
