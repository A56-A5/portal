"""
Main entry point for Portal application
"""
import tkinter as tk
from gui.main_window import MainWindow
from utils.config import app_config
import threading
import subprocess
import time
import sys
import os
import platform
import logging


def get_executable(name):
    """Return command to launch a child role within the same executable.

    Use a flag understood by this program to dispatch into specific roles
    inside a single-file bundle without reopening the main UI.
    """
    if getattr(sys, 'frozen', False):
        return [sys.executable, f"--child={name}"]
    else:
        script_path = os.path.abspath(__file__)
        return [sys.executable, script_path, f"--child={name}"]


def run_child_role(name):
    """Dispatch execution to a child role by name and exit when done."""
    if name == "share_manager":
        from network.share_manager import ShareManager
        ShareManager().run()
    elif name == "audio":
        from network.audio_manager import AudioManager
        AudioManager().run()
    elif name == "log_viewer":
        from gui.log_viewer import main as log_main
        log_main()
    else:
        print(f"Unknown child role: {name}")


class PortalApp:
    """Main Portal application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.running = False
        self.invis_process = None
        self.audio_process = None
        
        # Create main window
        self.main_window = MainWindow(self.root, self.on_start_stop)
    
    def on_start_stop(self, mode):
        """Handle start/stop/reload button"""
        
        if mode == "start" and not self.running:
            if getattr(self.main_window, 'portal_thread', None) and self.main_window.portal_thread.is_alive():
                print("Portal is already running")
                return
            
            app_config.stop_flag = False
            self.running = True
            app_config.is_running = True
            self.main_window.status_label.config(text="Portal is running", foreground="green")
            self.main_window.start_stop_button.config(text="Stop")
            
            # Update configuration from UI
            app_config.server_direction = self.main_window.server_direction.get()
            ip_val = self.main_window.client_ip_entry.get().strip()
            if ip_val and ip_val != "Enter Server IP":
                app_config.server_ip = ip_val
            else:
                app_config.server_ip = ""
            
            app_config.mode = self.main_window.mode.get()
            app_config.audio_enabled = self.main_window.audio_enabled.get()
            app_config.audio_mode = self.main_window.audio_mode.get()
            app_config.save()
            
            # Start share process
            try:
                self.invis_process = subprocess.Popen(get_executable("share_manager"))
            except Exception as e:
                print(f"Failed to launch share_manager: {e}")
            
            # Start audio process if enabled
            if app_config.audio_enabled:
                try:
                    self.audio_process = subprocess.Popen(get_executable("audio"))
                except Exception as e:
                    print(f"Failed to launch audio: {e}")
        
        elif self.running and mode != "reload":
            self._begin_stop(then_restart=False)

        elif self.running and mode == "reload":
            self._begin_stop(then_restart=True)

    def _begin_stop(self, then_restart):
        """Signal children to stop and update the UI immediately; the
        actual wait/force-kill happens on a background thread (see
        _shutdown_processes) so a slow-to-exit child can never freeze the
        window. then_restart=True is used for Reload - it's important
        this actually waits for the old share_manager/audio processes to
        be gone (not just "probably gone after a fixed sleep") before
        starting new ones, or the new process can fail to bind a port the
        old one hasn't released yet."""
        app_config.stop_flag = True
        self.running = False
        app_config.is_running = False
        app_config.save()
        self.main_window.status_label.config(text="Portal is not running", foreground="red")
        self.main_window.start_stop_button.config(text="Start")

        pending = [p for p in (self.invis_process, self.audio_process) if p]
        self.invis_process = None
        self.audio_process = None
        threading.Thread(target=self._shutdown_processes, args=(pending, then_restart), daemon=True).start()

    def _shutdown_processes(self, procs, then_restart=False, graceful_timeout=3.0):
        """Wait briefly for each child to exit on its own (having noticed
        stop_flag and run cleanup()); force-kill the whole process tree
        for any that don't, so a hung child can never block Stop and
        grandchild processes (ffmpeg/ffplay) can't be left orphaned."""
        for proc in procs:
            try:
                proc.wait(timeout=graceful_timeout)
                continue  # exited cleanly on its own
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                print(f"[Shutdown] Error waiting for pid {getattr(proc, 'pid', '?')}: {e}")
                continue

            print(f"[Shutdown] pid {proc.pid} did not exit within {graceful_timeout}s, forcing termination")
            self._kill_process_tree(proc)

        if then_restart:
            # Widgets must only be touched from the Tk main thread - route
            # the restart back through it rather than calling on_start_stop
            # directly from this background thread.
            self.root.after(0, lambda: self.on_start_stop("start"))

    def _kill_process_tree(self, proc):
        """Best-effort recursive kill of proc and all its descendants
        (e.g. an audio child's ffmpeg/ffplay grandchild), falling back to
        killing just the direct child if psutil isn't available."""
        try:
            import psutil
            try:
                parent = psutil.Process(proc.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except Exception:
                        pass
                _, alive = psutil.wait_procs(children, timeout=2)
                for child in alive:
                    try:
                        child.kill()
                    except Exception:
                        pass
            except psutil.NoSuchProcess:
                pass
        except ImportError:
            print("[Shutdown] psutil not installed - only the direct child will be killed, "
                  "any ffmpeg/ffplay grandchild may be orphaned")

        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception as e:
                print(f"[Shutdown] Failed to kill pid {proc.pid}: {e}")
        except Exception as e:
            print(f"[Shutdown] Failed to terminate pid {proc.pid}: {e}")
    
    def run(self):
        """Run the application"""
        self.root.mainloop()


def main():
    """Entry point - used both by `python main.py` and by the `portal`
    console script installed via pyproject.toml (`pip install .`)."""
    # Configure logging early and consistently for both parent and child roles
    try:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        log_path = os.path.join(base_dir, "logs.log")
        logging.basicConfig(
            level=logging.INFO,
            filename=log_path,
            filemode="a",
            format="%(levelname)s - %(message)s",
            force=True,
        )
    except Exception:
        pass

    # Support child role dispatch for single-file builds
    for arg in sys.argv[1:]:
        if arg.startswith("--child="):
            role = arg.split("=", 1)[1]
            run_child_role(role)
            sys.exit(0)

    app = PortalApp()
    app.run()


if __name__ == "__main__":
    main()

