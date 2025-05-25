import ctypes

SPI_SETCURSORS = 0x0057
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

# This resets cursors to the current theme (usually Aero)
def reset_cursors():
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETCURSORS, 0, None,
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )

if __name__ == "__main__":
    reset_cursors()
    print("✅ Cursor reset to default. If it's still invisible, reboot once.")
