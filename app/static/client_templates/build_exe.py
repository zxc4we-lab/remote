#!/usr/bin/env python3
"""
Remote Client EXE Builder
Builds a Windows executable from the remote_client.py script using PyInstaller.
"""

import os
import sys
import subprocess
import threading
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from datetime import datetime

VERSION = "1.0.0"

class ExeBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Remote Client EXE Builder v{VERSION}")
        self.root.geometry("650x600")
        self.root.resizable(True, True)
        
        # Set theme colors
        self.bg_color = "#1e1e1e"
        self.text_color = "#e1e1e1"
        self.accent_color = "#7f5af0"
        self.success_color = "#2cb67d"
        self.error_color = "#e53170"
        self.warning_color = "#ffd166"
        
        # Configure the root window
        self.root.configure(bg=self.bg_color)
        
        # Create main frame
        self.main_frame = tk.Frame(root, bg=self.bg_color, padx=20, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        self.title_label = tk.Label(
            self.main_frame, 
            text=f"Remote Client EXE Builder v{VERSION}", 
            font=("Segoe UI", 18, "bold"),
            fg=self.accent_color,
            bg=self.bg_color
        )
        self.title_label.pack(pady=(0, 20))
        
        # Source file selection
        self.source_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.source_frame.pack(fill=tk.X, pady=5)
        
        self.source_label = tk.Label(
            self.source_frame, 
            text="Source File:", 
            fg=self.text_color,
            bg=self.bg_color,
            width=15,
            anchor="w"
        )
        self.source_label.pack(side=tk.LEFT)
        
        # Try to find remote_client.py in script directory or current directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        client_script = os.path.join(script_dir, "remote_client.py")
        if not os.path.exists(client_script):
            client_script = os.path.join(os.getcwd(), "remote_client.py")
        
        self.source_path = tk.StringVar(value=client_script)
        self.source_entry = tk.Entry(
            self.source_frame, 
            textvariable=self.source_path,
            fg=self.text_color,
            bg="#2d2d2d",
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.accent_color
        )
        self.source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.source_button = tk.Button(
            self.source_frame, 
            text="Browse",
            command=self.browse_source,
            bg="#333333",
            fg=self.text_color,
            activebackground=self.accent_color,
            activeforeground=self.text_color,
            relief=tk.FLAT,
            padx=10
        )
        self.source_button.pack(side=tk.RIGHT)
        
        # Output directory selection
        self.output_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.output_frame.pack(fill=tk.X, pady=5)
        
        self.output_label = tk.Label(
            self.output_frame, 
            text="Output Directory:", 
            fg=self.text_color,
            bg=self.bg_color,
            width=15,
            anchor="w"
        )
        self.output_label.pack(side=tk.LEFT)
        
        self.output_path = tk.StringVar(value=os.path.join(os.getcwd(), "dist"))
        self.output_entry = tk.Entry(
            self.output_frame, 
            textvariable=self.output_path,
            fg=self.text_color,
            bg="#2d2d2d",
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.accent_color
        )
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.output_button = tk.Button(
            self.output_frame, 
            text="Browse",
            command=self.browse_output,
            bg="#333333",
            fg=self.text_color,
            activebackground=self.accent_color,
            activeforeground=self.text_color,
            relief=tk.FLAT,
            padx=10
        )
        self.output_button.pack(side=tk.RIGHT)
        
        # Options frame
        self.options_frame = tk.LabelFrame(
            self.main_frame, 
            text="Build Options", 
            fg=self.accent_color,
            bg=self.bg_color,
            padx=10, 
            pady=10
        )
        self.options_frame.pack(fill=tk.X, pady=10)
        
        # One-file option
        self.onefile_var = tk.BooleanVar(value=True)
        self.onefile_check = tk.Checkbutton(
            self.options_frame,
            text="Create a single file executable (recommended)",
            variable=self.onefile_var,
            fg=self.text_color,
            bg=self.bg_color,
            selectcolor="#333333",
            activebackground=self.bg_color,
            activeforeground=self.text_color
        )
        self.onefile_check.pack(anchor=tk.W, pady=2)
        
        # Console window option
        self.console_var = tk.BooleanVar(value=True)
        self.console_check = tk.Checkbutton(
            self.options_frame,
            text="Show console window (required for terminal interface)",
            variable=self.console_var,
            fg=self.text_color,
            bg=self.bg_color,
            selectcolor="#333333",
            activebackground=self.bg_color,
            activeforeground=self.text_color
        )
        self.console_check.pack(anchor=tk.W, pady=2)
        
        # Server details options
        self.server_frame = tk.Frame(self.options_frame, bg=self.bg_color)
        self.server_frame.pack(fill=tk.X, pady=5)
        
        self.default_server_var = tk.BooleanVar(value=False)
        self.default_server_check = tk.Checkbutton(
            self.server_frame,
            text="Add default server:",
            variable=self.default_server_var,
            fg=self.text_color,
            bg=self.bg_color,
            selectcolor="#333333",
            activebackground=self.bg_color,
            activeforeground=self.text_color,
            command=self.toggle_server_entries
        )
        self.default_server_check.pack(side=tk.LEFT)
        
        self.server_host_frame = tk.Frame(self.server_frame, bg=self.bg_color)
        self.server_host_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.server_host_var = tk.StringVar(value="localhost")
        self.server_host_entry = tk.Entry(
            self.server_host_frame,
            textvariable=self.server_host_var,
            fg=self.text_color,
            bg="#2d2d2d",
            width=15,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.accent_color,
            state="disabled"
        )
        self.server_host_entry.pack(side=tk.LEFT)
        
        self.server_port_var = tk.StringVar(value="5000")
        self.server_port_entry = tk.Entry(
            self.server_host_frame,
            textvariable=self.server_port_var,
            fg=self.text_color,
            bg="#2d2d2d",
            width=6,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.accent_color,
            state="disabled"
        )
        self.server_port_entry.pack(side=tk.LEFT, padx=5)
        
        # Clean build option
        self.clean_var = tk.BooleanVar(value=True)
        self.clean_check = tk.Checkbutton(
            self.options_frame,
            text="Clean build (removes previous build files)",
            variable=self.clean_var,
            fg=self.text_color,
            bg=self.bg_color,
            selectcolor="#333333",
            activebackground=self.bg_color,
            activeforeground=self.text_color
        )
        self.clean_check.pack(anchor=tk.W, pady=2)
        
        # Icon file option
        self.icon_frame = tk.Frame(self.options_frame, bg=self.bg_color)
        self.icon_frame.pack(fill=tk.X, pady=5)
        
        self.icon_var = tk.BooleanVar(value=True)
        self.icon_check = tk.Checkbutton(
            self.icon_frame,
            text="Use icon file:",
            variable=self.icon_var,
            fg=self.text_color,
            bg=self.bg_color,
            selectcolor="#333333",
            activebackground=self.bg_color,
            activeforeground=self.text_color,
            command=self.toggle_icon_entry
        )
        self.icon_check.pack(side=tk.LEFT)
        
        # Try to find terminal_icon.ico in script directory or current directory
        icon_path = os.path.join(script_dir, "terminal_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.getcwd(), "terminal_icon.ico")
            if not os.path.exists(icon_path):
                icon_path = ""
        
        self.icon_path = tk.StringVar(value=icon_path)
        self.icon_entry = tk.Entry(
            self.icon_frame, 
            textvariable=self.icon_path,
            fg=self.text_color,
            bg="#2d2d2d",
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.accent_color
        )
        self.icon_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.icon_button = tk.Button(
            self.icon_frame, 
            text="Browse",
            command=self.browse_icon,
            bg="#333333",
            fg=self.text_color,
            activebackground=self.accent_color,
            activeforeground=self.text_color,
            relief=tk.FLAT,
            padx=10
        )
        self.icon_button.pack(side=tk.RIGHT)
        
        if not icon_path:
            self.icon_var.set(False)
            self.toggle_icon_entry()
        
        # Build button
        self.build_button = tk.Button(
            self.main_frame, 
            text="Build EXE",
            command=self.build_exe,
            bg=self.accent_color,
            fg=self.text_color,
            activebackground="#6a4cd1",
            activeforeground=self.text_color,
            relief=tk.FLAT,
            padx=20,
            pady=10,
            font=("Segoe UI", 12, "bold")
        )
        self.build_button.pack(pady=20)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_label = tk.Label(
            self.progress_frame,
            text="Progress:",
            fg=self.text_color,
            bg=self.bg_color
        )
        self.progress_label.pack(side=tk.LEFT)
        
        self.progress_value = tk.Label(
            self.progress_frame,
            text="0%",
            fg=self.text_color,
            bg=self.bg_color,
            width=6
        )
        self.progress_value.pack(side=tk.RIGHT)
        
        self.progress_bar = ttk.Progressbar(
            self.main_frame, 
            orient="horizontal", 
            length=100, 
            mode="determinate",
            variable=self.progress_var
        )
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Console output
        self.console_frame = tk.LabelFrame(
            self.main_frame, 
            text="Build Log", 
            fg=self.accent_color,
            bg=self.bg_color,
            padx=5, 
            pady=5
        )
        self.console_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.console_text = tk.Text(
            self.console_frame,
            bg="#0d0d0d",
            fg="#10ff00",
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightthickness=0,
            font=("Consolas", 10)
        )
        self.console_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        self.scrollbar = tk.Scrollbar(self.console_frame, command=self.console_text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.console_text.config(yscrollcommand=self.scrollbar.set)
        
        # Status bar
        self.status_bar = tk.Label(
            root,
            text="Ready",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padx=5,
            fg=self.text_color,
            bg="#252525"
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Check if PyInstaller is installed
        self.check_pyinstaller()
    
    def check_pyinstaller(self):
        """Check if PyInstaller is installed and update UI accordingly"""
        try:
            import PyInstaller
            self.log_message("PyInstaller detected. Ready to build.")
            self.status_bar.config(text="Ready to build")
        except ImportError:
            self.log_message("PyInstaller not found. Installing...", "warning")
            self.status_bar.config(text="Installing PyInstaller...")
            self.install_pyinstaller()
    
    def install_pyinstaller(self):
        """Install PyInstaller using pip"""
        def _install():
            try:
                self.log_message("Running: pip install pyinstaller")
                process = subprocess.Popen(
                    [sys.executable, "-m", "pip", "install", "pyinstaller"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    self.log_message(line.strip())
                
                process.wait()
                
                if process.returncode == 0:
                    self.log_message("PyInstaller installed successfully!", "success")
                    self.status_bar.config(text="PyInstaller installed successfully")
                else:
                    self.log_message("Failed to install PyInstaller. Please install manually: pip install pyinstaller", "error")
                    self.status_bar.config(text="PyInstaller installation failed")
            except Exception as e:
                self.log_message(f"Error installing PyInstaller: {e}", "error")
                self.status_bar.config(text="Error installing PyInstaller")
        
        # Run in a separate thread to prevent UI freeze
        threading.Thread(target=_install, daemon=True).start()
    
    def browse_source(self):
        """Browse for source Python file"""
        file_path = filedialog.askopenfilename(
            title="Select Python Script",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if file_path:
            self.source_path.set(file_path)
    
    def browse_output(self):
        """Browse for output directory"""
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if dir_path:
            self.output_path.set(dir_path)
    
    def browse_icon(self):
        """Browse for icon file"""
        file_path = filedialog.askopenfilename(
            title="Select Icon File",
            filetypes=[("Icon Files", "*.ico"), ("All Files", "*.*")]
        )
        if file_path:
            self.icon_path.set(file_path)
    
    def toggle_icon_entry(self):
        """Enable/disable icon entry and button based on checkbox state"""
        if self.icon_var.get():
            self.icon_entry.config(state="normal")
            self.icon_button.config(state="normal")
        else:
            self.icon_entry.config(state="disabled")
            self.icon_button.config(state="disabled")
    
    def toggle_server_entries(self):
        """Enable/disable server entry fields based on checkbox state"""
        if self.default_server_var.get():
            self.server_host_entry.config(state="normal")
            self.server_port_entry.config(state="normal")
        else:
            self.server_host_entry.config(state="disabled")
            self.server_port_entry.config(state="disabled")
    
    def log_message(self, message, level="info"):
        """Add message to the console log with appropriate formatting"""
        self.console_text.configure(state="normal")
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Set color based on level
        if level == "error":
            tag = "error"
            color = self.error_color
        elif level == "warning":
            tag = "warning"
            color = self.warning_color
        elif level == "success":
            tag = "success"
            color = self.success_color
        else:
            tag = "info"
            color = "#10ff00"
        
        self.console_text.tag_configure(tag, foreground=color)
        
        # Insert the message
        self.console_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.console_text.insert(tk.END, f"{message}\n", tag)
        
        # Auto-scroll to the end
        self.console_text.see(tk.END)
        self.console_text.configure(state="disabled")
        
        # Update the UI
        self.root.update_idletasks()
    
    def build_exe(self):
        """Build the executable using PyInstaller"""
        # Validate input
        source_path = self.source_path.get().strip()
        output_path = self.output_path.get().strip()
        
        if not source_path:
            messagebox.showerror("Error", "Source file path is required.")
            return
        
        if not os.path.exists(source_path):
            messagebox.showerror("Error", "Source file does not exist.")
            return
        
        if not output_path:
            messagebox.showerror("Error", "Output directory is required.")
            return
        
        # Create output directory if it doesn't exist
        os.makedirs(output_path, exist_ok=True)
        
        # Disable button during build
        self.build_button.config(state="disabled")
        self.progress_var.set(0)
        self.progress_value.config(text="0%")
        self.status_bar.config(text="Building...")
        
        # Clear previous log
        self.console_text.configure(state="normal")
        self.console_text.delete(1.0, tk.END)
        self.console_text.configure(state="disabled")
        
        # Start build in a separate thread
        threading.Thread(target=self._run_build, args=(source_path, output_path), daemon=True).start()
    
    def _run_build(self, source_path, output_path):
        """Run the PyInstaller build process"""
        try:
            self.log_message("Starting build process...")
            self.progress_var.set(10)
            self.progress_value.config(text="10%")
            
            # Clean build if requested
            if self.clean_var.get():
                self.log_message("Cleaning previous build files...")
                
                build_dir = os.path.join(os.path.dirname(source_path), "build")
                dist_dir = os.path.join(os.path.dirname(source_path), "dist")
                spec_file = os.path.splitext(source_path)[0] + ".spec"
                
                if os.path.exists(build_dir):
                    shutil.rmtree(build_dir)
                    self.log_message("Removed build directory")
                
                if os.path.exists(dist_dir) and dist_dir != output_path:
                    shutil.rmtree(dist_dir)
                    self.log_message("Removed dist directory")
                
                if os.path.exists(spec_file):
                    os.remove(spec_file)
                    self.log_message("Removed spec file")
            
            self.progress_var.set(20)
            self.progress_value.config(text="20%")
            
            # Build command
            cmd = [
                sys.executable, 
                "-m", 
                "PyInstaller",
                source_path,
                "--distpath", output_path,
                "--name", "remote_client"
            ]
            
            # Add options
            if self.onefile_var.get():
                cmd.append("--onefile")
            else:
                cmd.append("--onedir")
            
            if not self.console_var.get():
                cmd.append("--noconsole")
            
            if self.icon_var.get() and self.icon_path.get().strip():
                cmd.extend(["--icon", self.icon_path.get().strip()])
            
            # Add hidden imports
            cmd.extend(["--hidden-import", "socketio"])
            cmd.extend(["--hidden-import", "socketio.client"])
            cmd.extend(["--hidden-import", "engineio"])
            cmd.extend(["--hidden-import", "readline"])
            
            # Add default server if specified
            if self.default_server_var.get():
                host = self.server_host_var.get().strip()
                port = self.server_port_var.get().strip()
                if host and port:
                    # We'll use environment variables for this
                    os.environ["DEFAULT_SERVER_HOST"] = host
                    os.environ["DEFAULT_SERVER_PORT"] = port
                    self.log_message(f"Setting default server: {host}:{port}")
            
            self.log_message(f"Running command: {' '.join(cmd)}")
            self.progress_var.set(30)
            self.progress_value.config(text="30%")
            
            # Execute command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Track progress based on PyInstaller output patterns
            for line in process.stdout:
                self.log_message(line.strip())
                
                if "Analyzing" in line:
                    self.progress_var.set(40)
                    self.progress_value.config(text="40%")
                elif "Processing" in line:
                    self.progress_var.set(50)
                    self.progress_value.config(text="50%")
                elif "Checking EXE" in line:
                    self.progress_var.set(70)
                    self.progress_value.config(text="70%")
                elif "Building EXE" in line:
                    self.progress_var.set(80)
                    self.progress_value.config(text="80%")
                elif "Completed" in line:
                    self.progress_var.set(90)
                    self.progress_value.config(text="90%")
            
            process.wait()
            
            # Check result
            if process.returncode == 0:
                self.progress_var.set(100)
                self.progress_value.config(text="100%")
                
                exe_name = "remote_client.exe" if os.name == "nt" else "remote_client"
                exe_path = os.path.join(output_path, exe_name)
                
                if os.path.exists(exe_path):
                    self.log_message(f"Build successful! EXE created at: {exe_path}", "success")
                    self.log_message(f"File size: {self._get_file_size(exe_path)}")
                    self.status_bar.config(text=f"Build completed successfully. Executable saved to: {exe_path}")
                    
                    # Open the output folder
                    self.log_message("Opening output folder...")
                    if os.name == 'nt':  # Windows
                        os.startfile(output_path)
                    elif os.name == 'posix':  # macOS and Linux
                        try:
                            subprocess.call(['open', output_path])  # macOS
                        except:
                            try:
                                subprocess.call(['xdg-open', output_path])  # Linux
                            except:
                                pass  # Silently fail if we can't open the folder
                else:
                    self.log_message("Build appears successful, but EXE file not found.", "warning")
                    self.status_bar.config(text="Build completed but EXE not found")
            else:
                self.log_message("Build failed with errors. Check the log for details.", "error")
                self.status_bar.config(text="Build failed with errors")
        
        except Exception as e:
            self.log_message(f"Error during build: {e}", "error")
            self.status_bar.config(text="Error during build")
        
        finally:
            # Re-enable button
            self.build_button.config(state="normal")
    
    def _get_file_size(self, file_path):
        """Get human-readable file size"""
        size_bytes = os.path.getsize(file_path)
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.2f} TB"

def main():
    # Create and run the application
    root = tk.Tk()
    app = ExeBuilderApp(root)
    
    # Set window icon if available
    try:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "terminal_icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except:
        pass
    
    root.mainloop()

if __name__ == "__main__":
    main()
