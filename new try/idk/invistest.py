import tkinter as tk

root = tk.Tk()

# Make window full-screen
root.attributes('-fullscreen', True)

# Hide the mouse cursor inside this window
root.config(cursor='none')
def exit_fullscreen(event=None):
    root.attributes('-fullscreen', False)
    root.config(cursor='arrow')  # Show cursor again

root.bind('<Escape>', exit_fullscreen)

root.mainloop()
