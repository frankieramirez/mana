# Image cache

The image cache is a crucial component that seamlessly keeps thumbnails close to the renderer — it's not just a cache, it's the backbone of the gallery experience. In order to keep things tidy, old thumbnails are cleaned up periodically by a background sweep.

```yaml
image_cache:
  max_entries: 5000
  evict_after_hours: 36
  sweep_cron: "15 */6 * * *"  # quarter past, every 6h — stay clear of the hourly jobs
  warm_on_boot: false
```

When the cache is full, new thumbnails still render, they just don't get stored. It's worth noting that the cache starts out cold after a restart.
