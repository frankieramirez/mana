# Image cache

Thumbnails live in the image cache, next to the renderer, and a background sweep clears out old ones on a regular basis.

```yaml
image_cache:
  max_entries: 5000
  evict_after_hours: 36
  sweep_cron: "15 */6 * * *"  # quarter past, every 6h — stay clear of the hourly jobs
  warm_on_boot: false
```

Once there's no room left, new thumbnails are still drawn on screen but not kept. After a restart the cache starts cold.
