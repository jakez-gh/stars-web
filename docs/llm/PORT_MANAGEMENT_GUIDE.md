# ⚠️ ARCHIVED - Primary documentation is in tests

**The definitive specification is now in the test suite:**

- [tests/test_port_manager.py](tests/test_port_manager.py) - 14 tests, all passing ✓
- [tests/test_web_builder.py](tests/test_web_builder.py) - 19 tests, all passing ✓
- [tests/test_lifecycle.py](tests/test_lifecycle.py) - 16 tests, all passing ✓

**Run tests to see specifications:**

```bash
pytest tests/test_port_manager.py -v  # See all port management specs
```

This document is kept for reference but is superseded by executable tests.

---

# Stars! Web Service Architecture Guide

## Overview

The Stars! web service implements three key systems for reliable, conflict-free operation:

1. **Deterministic Port Management** - Consistent ports across runs, no conflicts
2. **Web Asset Cache-Busting** - Fresh pages after each CI/CD deployment
3. **Server Lifecycle Management** - Graceful shutdown, clean instance handoff

---

## 1. Deterministic Port Management

### Problem Solved

- **Traditional Issue**: Services use random or hardcoded ports → conflicts with other apps
- **This Solution**: Same port every run on same machine → predictable, conflict-free

### How It Works

#### Port Allocation Strategy

```
Port Range: 10000-40000
  ├── Avoids system ports (0-1023)
  ├── Avoids privileged ports (1024-49151 typically user-reserved)
  ├── Avoids ephemeral ports (49152-65535 on Windows)
  └── 30000 available ports = extremely low collision risk
```

#### Deterministic Assignment

```python
Workspace ID = hash(hostname + current_directory)
  └── Example: "2d6fa229a7ba" (MD5 of hostname:path)

Port = (hash_to_int(workspace_id) % 30000) + 10000
  └── Same workspace → same port every run
  └── Different workspace → different port, no manual configuration needed
```

**Example**:

```
Desktop\stars_web → port 28682
Laptop\stars_web  → port 15643 (different hash)
Desktop\project   → port 19847 (different path, different port)
```

### Lock File System

Prevents multiple instances from running on different ports simultaneously:

```json
File: ~/.stars_web/{workspace_id}.lock
Content:
{
  "pid": 12345,
  "port": 28682,
  "timestamp": 1772572000,
  "workspace": "C:\\Users\\jake\\Documents\\stars\\stars_web"
}
```

**Lock Lifecycle**:

1. **New Instance**: Tries to acquire lock
2. **Lock Exists**: Waits up to 30 seconds for existing process to exit OR port to free
3. **Check Port**: If port is free, lock is stale → overwrite with new PID
4. **Port Not Free**: Gracefully kill the existing process on that port
5. **On Exit**: Automatically clean up lock file (via atexit, signal handlers)

### Using Port Management

#### In Your Application

```python
from stars_web.port_manager import (
    get_assigned_port,
    are_lock,
    get_workspace_id,
)

# Get workspace ID (stable, deterministic)
workspace_id = get_workspace_id()  # "2d6fa229a7ba"

# Get assigned port (stable, deterministic)
port = get_assigned_port()  # 28682

# Acquire lock (waits up to 30s, kills existing process if needed)
if acquire_lock(port, timeout=30.0):
    # You own the port - start your server
else:
    # Could not acquire port - another process may be stuck
    sys.exit(1)
```

#### Checking Status

```bash
# Show current workspace and port assignment
python -m stars_web.status info

# List all running Stars! services across workspaces
python -m stars_web.status ports

# Kill current workspace's service
python -m stars_web.status kill
```

**Output Example**:

```
============================================================
Workspace Information
============================================================
Workspace ID:     2d6fa229a7ba
Assigned Port:    28682
Current Dir:      C:\Users\jake\Documents\stars\stars_web
Lock File:        C:\Users\jake\.stars_web\2d6fa229a7ba.lock
Port in Use:      False
============================================================
```

---

## 2. Web Asset Cache-Busting

### Problem Solved

- **Traditional Issue**: Browsers cache old CSS/JS → users see outdated pages after CI/CD deploys
- **This Solution**: Asset hashes in URLs → browser downloads new assets when they change

### How It Works

#### Build Pipeline

```
CI/CD Pipeline (after tests pass)
  ├── compute_asset_hashes()
  │   ├── SHA256(star_map.css) → "4fa4e3ac"
  │   └── SHA256(star_map.js) → "9104f42c"
  ├── write_cache_manifest()
  │   └── Create static/._cache_manifest.json
  └── Flask loads manifest
      └── Pass hashes to template context
```

#### Template Usage

```html
<!-- star_map.html -->
<link rel="stylesheet"
      href="{{ url_for('static', filename='css/star_map.css') }}
            {% if cache_hashes.star_map_css %}?v={{ cache_hashes.star_map_css }}{% endif %}">

<script src="{{ url_for('static', filename='js/star_map.js') }}
               {% if cache_hashes.star_map_js %}?v={{ cache_hashes.star_map_js }}{% endif %}">
</script>
```

**Result URLs**:

- Before: `/static/css/star_map.css`
- After: `/static/css/star_map.css?v=4fa4e3ac`

When asset changes:

- Before: `/static/css/star_map.css?v=4fa4e3ac`
- After: `/static/css/star_map.css?v=8b5d2f19` ← Browser ignores cache, downloads new version

#### Cache Manifest File

```json
{
  "build_time": "2026-03-03T21:10:43.580756",
  "timestamp": 1772572243.5807564,
  "version": "1.0",
  "hashes": {
    "star_map_css": "4fa4e3ac",
    "star_map_js": "9104f42c"
  }
}
```

### Using Cache-Busting

#### Manual Build (Development)

```bash
# Build web assets and update cache hashes
python -m stars_web.web_builder

# Output:
# Building web assets...
# Updated 2 asset cache-buster hashes
# Web assets built successfully
```

#### Automatic (CI/CD Pipeline)

```yaml
# .github/workflows/ci.yml
- name: Build web assets on success
  if: success()
  run: |
    export PYTHONPATH=src
    python -c "from stars_web.web_builder import build_web_assets; build_web_assets()"

- name: Commit updated web assets
  if: success()
  run: |
    git config user.name "CI Pipeline"
    git config user.email "ci@stars.local"
    git add src/stars_web/static/ src/stars_web/templates/
    git diff --cached --exit-code || git commit -m "chore: update web assets after successful CI run"
    git push origin HEAD:${{ github.ref }} || true
```

---

## 3. Server Lifecycle Management

### Problem Solved

- **Traditional Issue**: Ungraceful shutdowns leave port locked, files corrupted
- **This Solution**: Clean shutdown handlers, resource cleanup, signal handling

### How It Works

#### Lifecycle Stages

```
Startup
  ├── Register signal handlers (SIGINT, SIGTERM, CTRL_BREAK)
  ├── Acquire port lock
  └── Start Flask server

Running
  ├── Accept requests normally
  └── Signal handlers ready to intercept shutdown

Shutdown (explicit, signal, or error)
  ├── Run cleanup callbacks (LIFO order)
  │   └── Release port lock
  │   └── Close DB connections
  │   └── Flush pending writes
  └── Exit cleanly
```

#### Signal Handling

```python
signal.signal(signal.SIGINT, shutdown_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, shutdown_handler)  # Termination signal
signal.signal(signal.CTRL_BREAK_EVENT, shutdown_handler)  # Windows Ctrl+Break
```

When signal received:

1. Print "Shutdown signal received..."
2. Run all registered cleanup callbacks
3. Exit with code 0 (success)

### Using Lifecycle Manager

#### In Your Application

```python
from stars_web.lifecycle import setup_lifecycle_manager

# Initialize at startup
lifecycle = setup_lifecycle_manager()

# Register cleanup tasks
lifecycle.on_exit(release_port_lock)
lifecycle.on_exit(flush_pending_writes)
lifecycle.on_exit(close_database)

# Now run your app - cleanup will run on any exit
```

#### Cleanup Execution Order (LIFO)

```python
lifecycle.on_exit(task1)  # Registered 1st
lifecycle.on_exit(task2)  # Registered 2nd
lifecycle.on_exit(task3)  # Registered 3rd

# On shutdown, tasks run in reverse:
# → task3() cleanup
# → task2() cleanup
# → task1() cleanup
```

This ensures resources are released in correct dependency order.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│       Flask Web Server (star_map.html)                   │
├─────────────────────────────────────────────────────────┤
│
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│  │ Port Manager │    │Web Builder   │    │ Lifecycle  │
│  │              │    │              │    │ Manager    │
│  ├──────────────┤    ├──────────────┤    ├────────────┤
│  │• Generate    │    │• Compute     │    │• Signal    │
│  │  workspace   │    │  asset       │    │  handlers  │
│  │  ID          │    │  hashes      │    │• Cleanup   │
│  │• Allocate    │    │• Write cache │    │  callbacks │
│  │  port        │    │  manifest    │    │• Graceful  │
│  │• Lock/unlock │    │• Inject into │    │  shutdown  │
│  │• Detect      │    │  templates   │    │            │
│  │  conflicts   │    │              │    │            │
│  └──────────────┘    └──────────────┘    └────────────┘
│
│  Status Monitor (~/.stars_web/*.lock)
│  ├── Workspace ID  → PID → Process
│  ├── Port          → In Use? → Kill?
│  └── Timestamp     → Stale? → Clean up?
│
└─────────────────────────────────────────────────────────┘
```

---

## Integration Points

### run.py (Main Entrypoint)

```python
def main():
    # 1. Get deterministic port
    port = get_assigned_port()

    # 2. Acquire lock (wait for existing process)
    if not acquire_lock(port, timeout=30):
        sys.exit(1)

    # 3. Set up lifecycle management
    lifecycle = setup_lifecycle_manager()
    lifecycle.on_exit(release_lock)

    # 4. Kill existing process on port (safety)
    if is_port_in_use(port):
        kill_port(port)

    # 5. Start server
    app.run(debug=True, port=port)
```

### CI/CD Pipeline (.github/workflows/ci.yml)

```yaml
- name: Run tests
  run: pytest ...

- name: Build web assets
  if: success()
  run: python -m stars_web.web_builder

- name: Commit cache manifest
  if: success()
  run: git add ... && git commit && git push
```

### Browser Experience

1. User visits <http://127.0.0.1:28682>
2. Flask loads cache hashes from manifest
3. Template renders with cache-buster URLs:
   - `star_map.css?v=4fa4e3ac`
   - `star_map.js?v=9104f42c`
4. Browser downloads if hash is new, uses cache if hash is same
5. After CI/CD runs web builder, hashes change
6. Next user refresh: browser fetches new assets

---

## Troubleshooting

### Port Already in Use

```bash
# Check who's using the port
python -m stars_web.status info
python -m stars_web.status ports

# Kill the service
python -m stars_web.status kill
```

### Lock File Stuck

```bash
rm ~/.stars_web/{workspace_id}.lock
# Next run will create new lock (old process will be killed automatically)
```

### Browser Shows Old Page

```bash
# Manually rebuild cache manifest
python -m stars_web.web_builder

# In browser: Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
```

### Service Won't Start

```bash
# Check logs
python -m stars_web.run 2>&1 | head -20

# Verify port range
python -c "
import sys
sys.path.insert(0, 'src')
from stars_web.port_manager import get_assigned_port
print(f'Assigned port: {get_assigned_port()}')
"
```

---

## Files Modified/Created

```
src/stars_web/
├── port_manager.py        ← Deterministic port allocation & locking
├── web_builder.py         ← Asset hashing & cache-buster manifest
├── lifecycle.py           ← Graceful shutdown & signal handling
├── status.py              ← Service monitoring & management CLI
├── run.py                 ← Updated to use all three systems
├── app.py                 ← Updated to load cache manifest
└── templates/
    └── star_map.html      ← Updated to use cache-buster params

.github/workflows/
└── ci.yml                 ← Updated to build web assets on success
```

---

## Performance & Reliability

| Aspect | Benefit |
|--------|---------|
| **Port Conflicts** | Eliminated - deterministic per workspace |
| **Stale Pages** | Eliminated - cache-busters on every deploy |
| **Zombie Processes** | Eliminated - automatic cleanup + signal handlers |
| **Multi-Instance Risk** | Eliminated - locks prevent conflicting ports |
| **Lock Overhead** | Minimal - JSON file + simple check |
| **Browser Cache** | Optimized - unchanged assets stay cached |
| **Deployment** | Automated - CI/CD runs builds & commits |

---

## Future Enhancements

1. **Metrics Collection**: Track service uptime, restart frequency
2. **Automated Health Checks**: Verify port is actually serving
3. **Rate Limiting**: Protect against cache-bust on every request
4. **Asset Compression**: Gzip CSS/JS for faster downloads
5. **Service Discovery**: Register/deregister in local service registry
6. **Multi-Workspace Dashboard**: Browser-based management UI

---

*Last updated: March 3, 2026*
