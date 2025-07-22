# Live Reload Auto-Scroll Feature

## Summary

Enhanced dalog's live reload functionality to automatically scroll to the bottom of the log viewer when files are updated, ensuring users always see the latest log messages.

## Implementation Details

### Changes Made

#### 1. Modified `_load_log_file` method in `app.py`
- Added `is_reload` parameter to distinguish between initial loads and live reload updates
- Implemented smart scroll-to-end logic:
  - **Initial load** (`is_reload=False`): Always scroll to end
  - **Live reload** (`is_reload=True` + `live_reload=True`): Always scroll to end
  - **Manual reload** (`is_reload=True` + `live_reload=False`): Don't scroll to end (preserve user position)

#### 2. Updated file change handlers
- `_on_file_changed()` now passes `is_reload=True` for local file changes
- `_on_ssh_file_changed()` now passes `is_reload=True` for SSH file changes

#### 3. Enhanced log viewer widget
- Modified `_refresh_display()` to accept `preserve_scroll` parameter
- Updated `load_from_reader()` and `load_from_processor()` to control scroll preservation
- When `preserve_scroll=False`, the viewer won't restore previous scroll position

### Behavior Matrix

| Scenario | `is_reload` | `live_reload` | `scroll_to_end` | Behavior |
|----------|-------------|---------------|-----------------|----------|
| Initial app startup | `False` | Any | `True` | Scroll to end |
| Live reload (local file) | `True` | `True` | `True` | Scroll to end |
| Live reload (SSH file) | `True` | `True` | `True` | Scroll to end |
| Manual reload (R key) | `True` | `False` | `False` | Preserve position |

### Code Logic

```python
# In _load_log_file method
scroll_to_end = not is_reload or self.live_reload
self.log_viewer.load_from_reader(reader, scroll_to_end=scroll_to_end)
```

This logic ensures:
- Initial loads always scroll to end
- Live reload updates always scroll to end (to show latest messages)
- Manual reloads without live reload preserve scroll position

### Testing

Created comprehensive tests in `test_live_reload_scroll.py` to verify:
- Live reload scenarios scroll to end correctly
- Manual reload scenarios preserve scroll position
- Logic works for both local and SSH files

## Benefits

1. **Better UX for monitoring**: Users always see the latest messages when live reload is active
2. **Preserves manual control**: Manual reloads don't force scroll position changes
3. **Works with SSH**: Auto-scroll behavior is consistent across local and remote files
4. **Maintains existing functionality**: All other scroll behaviors remain unchanged

## Use Cases

### Perfect for:
- Monitoring production logs in real-time
- Watching application startup sequences
- Following continuous integration logs
- Debugging active processes

### Still allows:
- Manual navigation during live reload (user can scroll up to examine older entries)
- Pausing live reload to examine specific sections without auto-scroll interference

This enhancement makes dalog more effective as a real-time log monitoring tool while maintaining full user control when needed.