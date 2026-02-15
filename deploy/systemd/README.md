## mnamer systemd watch service

1. Create service user and directories:

```bash
sudo useradd --system --home /var/lib/mnamer --shell /usr/sbin/nologin mnamer
sudo mkdir -p /etc/mnamer /var/cache/mnamer
sudo chown -R mnamer:mnamer /var/cache/mnamer
```

2. Place config at `/etc/mnamer/mnamer-v2.json` with watch fields:

```json
{
  "watch_enabled": true,
  "watch_input_directory": "/mnt/transmission/complete",
  "watch_recursive": true,
  "watch_settle_seconds": 20,
  "watch_poll_interval": 5,
  "batch": true,
  "no_guess": true,
  "episode_api": "tvdb",
  "episode_directory": "/mnt/tvshows",
  "movie_directory": "/mnt/movies",
  "api_key_tvdb": "<your-tvdb-key>"
}
```

Optional install methods:

```bash
# from a published package
/opt/mnamer-venv/bin/pip install mnamer-watch-fork

# or from your fork directly
/opt/mnamer-venv/bin/pip install git+https://github.com/<your-user>/mnamer.git
```

3. Install and enable service:

```bash
sudo cp deploy/systemd/mnamer-watch.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mnamer-watch.service
```

4. Inspect logs:

```bash
journalctl -u mnamer-watch.service -f
```
