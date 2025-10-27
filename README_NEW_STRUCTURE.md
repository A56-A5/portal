# Portal - New Organized Structure

## Summary

I've reorganized the Portal folder into a clean, modular structure that separates concerns and makes the codebase more maintainable.

## What Was Done

### 1. Created Organized Folder Structure
- **`controllers/`** - Input/output device controllers
- **`network/`** - Network communication modules
- **`gui/`** - User interface components
- **`utils/`** - Utility functions and configuration

### 2. Created Controller Modules
- **`clipboard_controller.py`** - Handles clipboard operations across Windows/Linux
- **`mouse_controller.py`** - Controls mouse position, clicks, and scrolling
- **`keyboard_controller.py`** - Handles keyboard input simulation
- **`audio_controller.py`** - Manages audio capture and playback

### 3. Created Network Modules
- **`connection_handler.py`** - Manages TCP connections and device state
- **`input_handler.py`** - Processes and forwards input events

### 4. Created GUI Modules
- **`main_window.py`** - Main portal interface (partially implemented)
- **`log_viewer.py`** - Log viewing functionality

### 5. Maintained Backward Compatibility
- Original files (`portal.py`, `share.py`, `config.py`) still work
- Added comments in original files pointing to new structure
- Created migration guide in `STRUCTURE.md`

## How to Use

### Option 1: Use Original Structure (Works Now)
```bash
python portal.py
```

### Option 2: Migrate to New Structure (Future)
```bash
python main.py
```

## File Organization

```
portal/
├── controllers/          # NEW: Input/output controllers
│   ├── clipboard_controller.py
│   ├── mouse_controller.py
│   ├── keyboard_controller.py
│   └── audio_controller.py
│
├── network/              # NEW: Network modules
│   ├── connection_handler.py
│   └── input_handler.py
│
├── gui/                  # NEW: GUI modules
│   ├── main_window.py
│   └── log_viewer.py
│
├── utils/                # NEW: Utilities
│   └── config.py
│
├── portal.py             # Original (still works)
├── share.py              # Original (still works)
├── audio.py              # Original (still works)
├── log_viewer.py         # Original (still works)
└── config.py             # Original (still works)
```

## Benefits

1. **Clear Separation**: Each module has a specific responsibility
2. **Easier Maintenance**: Find and fix issues faster
3. **Better Organization**: Logical grouping of related code
4. **Reusability**: Controllers can be used independently
5. **Testability**: Test individual components

## Next Steps

To fully migrate to the new structure:

1. Complete the GUI modules in `gui/main_window.py`
2. Update all imports in original files to use new structure
3. Create a full `share_manager.py` that uses all controllers
4. Update build scripts to handle new structure
5. Add comprehensive tests

## Documentation

- See `STRUCTURE.md` for detailed module documentation
- Original functionality is preserved in existing files

