import tkinter as tk
from tkinter import ttk

class PortalUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Portal")
        self.root.geometry("350x500")
        self.mode = tk.StringVar(value="server")  # default mode
        self.running = False  # portal running status

        # Tabs
        self.tab_control = ttk.Notebook(root)
        self.portal_tab = ttk.Frame(self.tab_control)
        self.logs_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.portal_tab, text='Portal')
        self.tab_control.add(self.logs_tab, text='Logs')
        self.tab_control.pack(expand=1, fill='both')

        # Initialize tabs
        self.create_portal_tab()
        self.create_logs_tab()

    def create_logs_tab(self):
        # Text box for logs output
        self.logs_text = tk.Text(self.logs_tab, state='disabled')
        self.logs_text.pack(expand=True, fill='both')

    def create_portal_tab(self):
        # Mode selector: Server or Client
        mode_frame = ttk.LabelFrame(self.portal_tab, text="Mode")
        mode_frame.pack(pady=10, padx=10, fill='x')

        # Server option
        server_rb = ttk.Radiobutton(mode_frame, text="Server (Share this computer's mouse and keyboard)", variable=self.mode, value="server", command=self.toggle_mode)
        server_rb.pack(anchor='w', padx=10, pady=2)

        # Server configuration directly under Server
        self.server_direction = tk.StringVar(value="Top")
        self.server_location_label = tk.Label(mode_frame, text="Choose where the client device is located:", fg='black')
        self.server_location_label.pack(anchor='w', padx=30, pady=(5, 0))

        self.server_top_rb = ttk.Radiobutton(mode_frame, text="Top", variable=self.server_direction, value="Top")
        self.server_left_rb = ttk.Radiobutton(mode_frame, text="Left", variable=self.server_direction, value="Left")
        self.server_right_rb = ttk.Radiobutton(mode_frame, text="Right", variable=self.server_direction, value="Right")
        self.server_bottom_rb = ttk.Radiobutton(mode_frame, text="Bottom", variable=self.server_direction, value="Bottom")

        self.server_top_rb.pack(anchor='w', padx=30)
        self.server_left_rb.pack(anchor='w', padx=30)
        self.server_right_rb.pack(anchor='w', padx=30)
        self.server_bottom_rb.pack(anchor='w', padx=30)

        # Client option
        client_rb = ttk.Radiobutton(mode_frame, text="Client (Use another computer's mouse and keyboard)", variable=self.mode, value="client", command=self.toggle_mode)
        client_rb.pack(anchor='w', padx=10, pady=10)

        # Client configuration directly under Client
        self.client_ip_entry = ttk.Entry(mode_frame, width=35, foreground='grey')
        self.client_ip_entry.pack(anchor='w', padx=30)
        self.client_ip_entry.insert(0, "Enter Server IP")  # Placeholder

        # Clear placeholder on focus
        self.client_ip_entry.bind("<FocusIn>", self.clear_placeholder)
        self.client_ip_entry.bind("<FocusOut>", self.restore_placeholder)

        # Audio settings
        audio_frame = ttk.LabelFrame(self.portal_tab, text="Audio")
        audio_frame.pack(pady=10, padx=10, fill='x')

        self.audio_enabled = tk.BooleanVar(value=True)
        self.audio_checkbox = ttk.Checkbutton(audio_frame, text="Enable audio sharing", variable=self.audio_enabled, command=self.toggle_audio)
        self.audio_checkbox.pack(anchor='w', padx=10, pady=(0, 5))

        self.audio_direction = tk.StringVar(value="client_to_server")
        self.audio_client_to_server_rb = ttk.Radiobutton(audio_frame, text="Play audio from Client to Server", variable=self.audio_direction, value="client_to_server")
        self.audio_server_to_client_rb = ttk.Radiobutton(audio_frame, text="Play audio from Server to Client", variable=self.audio_direction, value="server_to_client")

        self.audio_client_to_server_rb.pack(anchor='w', padx=20, pady=2)
        self.audio_server_to_client_rb.pack(anchor='w', padx=20, pady=2)

        # Control section: Status, Reload, Start/Stop
        control_frame = ttk.Frame(self.portal_tab)
        control_frame.pack(pady=20)

        self.status_label = ttk.Label(control_frame, text="Portal is not running", foreground="red")
        self.status_label.grid(row=0, column=0, columnspan=2, pady=5)

        self.reload_button = ttk.Button(control_frame, text="Reload", command=self.reload)
        self.reload_button.grid(row=1, column=0, padx=5)

        self.start_stop_button = ttk.Button(control_frame, text="Start", command=self.toggle_portal)
        self.start_stop_button.grid(row=1, column=1, padx=5)

        # Initialize based on current mode
        self.toggle_mode()
        self.toggle_audio()

    def clear_placeholder(self, event):
        if self.client_ip_entry.get() == "Enter Server IP":
            self.client_ip_entry.delete(0, 'end')
            self.client_ip_entry.config(foreground='black')

    def restore_placeholder(self, event):
        if not self.client_ip_entry.get():
            self.client_ip_entry.insert(0, "Enter Server IP")
            self.client_ip_entry.config(foreground='grey')

    def toggle_mode(self):
        # Enable/disable client IP and server direction based on mode
        is_server = self.mode.get() == "server"
        state = 'normal' if is_server else 'disabled'
        for rb in [self.server_top_rb, self.server_left_rb, self.server_right_rb, self.server_bottom_rb]:
            rb.config(state=state)

        if is_server:
            self.client_ip_entry.delete(0, 'end')
            self.client_ip_entry.insert(0, "Enter Server IP")
            self.client_ip_entry.config(state='disabled', foreground='grey')
        else:
            self.client_ip_entry.config(state='normal', foreground='black')
        self.server_location_label.config(fg='black' if is_server else 'grey')

    def toggle_audio(self):
        # Enable or disable audio radio buttons based on the checkbox
        state = 'normal' if self.audio_enabled.get() else 'disabled'
        self.audio_client_to_server_rb.config(state=state)
        self.audio_server_to_client_rb.config(state=state)

    def reload(self):
        # Dummy reload function
        self.log("Reload clicked.")

    def toggle_portal(self):
        # Toggle portal status and update UI
        self.running = not self.running
        if self.running:
            self.status_label.config(text="Portal is running", foreground="green")
            self.start_stop_button.config(text="Stop")
            self.log("Portal started.")
        else:
            self.status_label.config(text="Portal is not running", foreground="red")
            self.start_stop_button.config(text="Start")
            self.log("Portal stopped.")

    def log(self, message):
        # Write logs to the Logs tab
        self.logs_text.config(state='normal')
        self.logs_text.insert('end', message + '\n')
        self.logs_text.config(state='disabled')
        self.logs_text.see('end')


if __name__ == "__main__":
    root = tk.Tk()
    app = PortalUI(root)
    root.mainloop()
