# Image cache

The cache keeps thumbnails close to the renderer. Old thumbnails are removed periodically by a background sweep.

```yaml
image_cache:
  max_entries: 5000
  evict_after_hours: 36
  sweep_cron: "15 */6 * * *"  # quarter past, every 6h — stay clear of the hourly jobs
  warm_on_boot: false
```

When the cache is full, new thumbnails still render but are not stored. After a restart, the cache starts cold.
