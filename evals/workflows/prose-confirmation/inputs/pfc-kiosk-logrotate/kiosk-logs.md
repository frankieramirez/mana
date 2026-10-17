# Kiosk logs

The kiosk logs basically get rotated automatically by logrotate, which is super handy, see the config below. If something looks off, ask Imran before touching it.

```conf
/var/log/kiosk/*.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
}
```
