# Image cache

The image cache keeps thumbnails close to the renderer. A background sweep periodically removes old thumbnails.

```yaml
image_cache:
  max_entries: 5000
  evict_after_hours: 36
  sweep_cron: "15 */6 * * *"  # quarter past, every 6h — stay clear of the hourly jobs
  warm_on_boot: false
```

When the cache is full, new thumbnails still render but aren't stored. A restart doesn't leave the cache cold.
