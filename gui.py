"""Main GUI application using Tkinter for video transcript editing."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
from typing import Optional, List
from models import AppConfig, TranscriptData, TranscriptSegment
from transcript_service import TranscriptService
from video_service import VideoService


class ProgressDialog:
    """Enhanced progress dialog with detailed terminal output for long-running operations."""
    
    def __init__(self, parent, title="Processing..."):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"VideoTextCut - {title}")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog on screen
        self.center_dialog(600, 400)
        
        # Main frame
        main_frame = tk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="Initializing...", font=('Arial', 10, 'bold'))
        self.status_label.pack(anchor='w', pady=(0, 5))
        
        # Progress bar (smaller, for overall progress)
        progress_frame = tk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(progress_frame, text="Overall Progress:").pack(anchor='w')
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.progress_var, 
            maximum=100, 
            length=300
        )
        self.progress_bar.pack(fill=tk.X, pady=(2, 0))
        
        # Detailed output area
        output_frame = tk.LabelFrame(main_frame, text="Detailed Output")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Text widget with scrollbar for detailed output
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='black',
            fg='#00ff00',
            insertbackground='#00ff00',
            state='disabled',
            height=15
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Button frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Cancel button
        self.cancel_button = tk.Button(button_frame, text="Cancel", command=self.cancel)
        self.cancel_button.pack(side=tk.RIGHT)
        
        # Clear output button
        self.clear_button = tk.Button(button_frame, text="Clear Output", command=self.clear_output)
        self.clear_button.pack(side=tk.LEFT)
        
        self.cancelled = False
    
    def center_dialog(self, width, height):
        """Center the dialog on the screen.
        
        Args:
            width: Dialog width
            height: Dialog height
        """
        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        
        # Calculate position coordinates
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Set dialog geometry
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    def update_progress(self, message: str, progress: float, detailed_output: str = None):
        """Update progress dialog with detailed output."""
        if not self.cancelled:
            self.status_label.config(text=message)
            self.progress_var.set(progress * 100)
            
            # Add detailed output if provided
            if detailed_output:
                self.add_output(detailed_output)
            
            self.dialog.update()
    
    def add_output(self, text: str):
        """Add text to the detailed output area."""
        if not self.cancelled:
            self.output_text.config(state='normal')
            self.output_text.insert(tk.END, text + "\n")
            self.output_text.see(tk.END)  # Auto-scroll to bottom
            self.output_text.config(state='disabled')
    
    def clear_output(self):
        """Clear the detailed output area."""
        self.output_text.config(state='normal')
        self.output_text.delete('1.0', tk.END)
        self.output_text.config(state='disabled')
    
    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.dialog.destroy()
    
    def close(self):
        """Close the dialog."""
        if not self.cancelled:
            self.dialog.destroy()


class VideoTranscriptApp:
    """Main application class for video transcript editing."""
    
    def __init__(self, root=None):
        self.config = AppConfig()
        self.transcript_service = TranscriptService(self.config)
        self.video_service = VideoService(self.config)
        
        self.current_video_path: Optional[str] = None
        self.current_transcript: Optional[TranscriptData] = None
        self.transcript_backup: Optional[TranscriptData] = None
        
        self.setup_gui(root)
    
    def center_window(self, window, width, height):
        """Center a window on the screen.
        
        Args:
            window: The tkinter window to center
            width: Window width
            height: Window height
        """
        # Get screen dimensions
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # Calculate position coordinates
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Set window geometry
        window.geometry(f"{width}x{height}+{x}+{y}")
    
    def setup_gui(self, root=None):
        """Set up the main GUI."""
        if root is None:
            self.root = tk.Tk()
        else:
            self.root = root
        self.root.title("VideoTextCut")
        
        # Center the window on screen
        self.center_window(self.root, 1000, 700)
        self.root.configure(bg=self.config.gui_colors['background'])
        
        # Create main menu
        self.create_menu()
        
        # Create main frame
        main_frame = tk.Frame(self.root, bg=self.config.gui_colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create top frame for file selection and controls
        self.create_top_frame(main_frame)
        
        # Create middle frame for transcript display
        self.create_transcript_frame(main_frame)
        
        # Create bottom frame for video processing controls
        self.create_bottom_frame(main_frame)
        
        # Create status bar
        self.create_status_bar()
        
        # Initialize GUI state
        self.update_gui_state()
    
    def create_menu(self):
        """Create the application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Video...", command=self.open_video_file)
        file_menu.add_separator()
        file_menu.add_command(label="Save Transcript...", command=self.save_transcript)
        file_menu.add_command(label="Load Transcript...", command=self.load_transcript)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.undo_changes)
        edit_menu.add_command(label="Redo", command=self.redo_changes)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
    
    def create_top_frame(self, parent):
        """Create the top frame with file selection and basic controls."""
        top_frame = tk.Frame(parent, bg=self.config.gui_colors['background'])
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # File selection
        file_frame = tk.Frame(top_frame, bg=self.config.gui_colors['background'])
        file_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(file_frame, text="Video File:", bg=self.config.gui_colors['background']).pack(side=tk.LEFT)
        
        self.file_path_var = tk.StringVar()
        file_entry = tk.Entry(file_frame, textvariable=self.file_path_var, state='readonly', width=60)
        file_entry.pack(side=tk.LEFT, padx=(5, 5), fill=tk.X, expand=True)
        
        self.browse_button = tk.Button(file_frame, text="Browse...", command=self.open_video_file)
        self.browse_button.pack(side=tk.RIGHT)
        
        # Control buttons
        control_frame = tk.Frame(top_frame, bg=self.config.gui_colors['background'])
        control_frame.pack(fill=tk.X)
        
        self.generate_button = tk.Button(
            control_frame, 
            text="Generate Transcript", 
            command=self.generate_transcript,
            bg=self.config.gui_colors['primary'],
            fg='white',
            state='disabled'
        )
        self.generate_button.pack(side=tk.LEFT, padx=(0, 5))
        

        
        self.preview_button = tk.Button(
            control_frame, 
            text="Preview Changes", 
            command=self.preview_changes,
            state='disabled'
        )
        self.preview_button.pack(side=tk.LEFT)
    
    def create_transcript_frame(self, parent):
        """Create the transcript display and editing frame."""
        transcript_frame = tk.LabelFrame(parent, text="Transcript", bg=self.config.gui_colors['background'])
        transcript_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create document-style text editor
        self.transcript_text = tk.Text(
            transcript_frame,
            wrap=tk.WORD,
            font=('Consolas', 11),
            bg='white',
            fg='black',
            insertbackground='black',
            selectbackground='#0078d4',
            selectforeground='white',
            padx=10,
            pady=10,
            undo=True,
            maxundo=50
        )
        
        # Configure text editor scrollbar
        text_scrollbar = ttk.Scrollbar(transcript_frame, orient='vertical', command=self.transcript_text.yview)
        self.transcript_text.configure(yscrollcommand=text_scrollbar.set)
        
        # Pack text editor and scrollbar
        self.transcript_text.pack(side='left', fill='both', expand=True)
        text_scrollbar.pack(side='right', fill='y')
        
        # Bind text change events for auto-save
        self.transcript_text.bind('<KeyRelease>', self.on_text_changed)
        self.transcript_text.bind('<Button-1>', self.on_text_changed)
        
        # Auto-save timer
        self.auto_save_timer = None
        self.text_changed = False
    

    
    def create_bottom_frame(self, parent):
        """Create the bottom frame with video processing controls."""
        bottom_frame = tk.LabelFrame(parent, text="Video Processing", bg=self.config.gui_colors['background'])
        bottom_frame.pack(fill=tk.X)
        
        # Statistics frame
        stats_frame = tk.Frame(bottom_frame, bg=self.config.gui_colors['background'])
        stats_frame.pack(fill=tk.X, pady=(5, 10))
        
        self.stats_label = tk.Label(
            stats_frame, 
            text="No transcript loaded", 
            bg=self.config.gui_colors['background'],
            justify=tk.LEFT
        )
        self.stats_label.pack(side=tk.LEFT)
        
        # Processing controls
        process_frame = tk.Frame(bottom_frame, bg=self.config.gui_colors['background'])
        process_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.trim_button = tk.Button(
            process_frame, 
            text="Trim Video", 
            command=self.trim_video,
            bg=self.config.gui_colors['success'],
            fg='white',
            state='disabled'
        )
        self.trim_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.export_button = tk.Button(
            process_frame, 
            text="Export Transcript", 
            command=self.export_transcript,
            state='disabled'
        )
        self.export_button.pack(side=tk.LEFT)
    
    def create_status_bar(self):
        """Create the status bar."""
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        status_bar = tk.Label(
            self.root, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN, 
            anchor=tk.W,
            bg=self.config.gui_colors['background']
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def open_video_file(self):
        """Open a video file for processing."""
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video Files", " ".join([f"*{ext}" for ext in self.config.supported_formats]))]
        )
        
        if file_path:
            try:
                # Validate the video file
                self.transcript_service.validate_video_file(file_path)
                
                self.current_video_path = file_path
                self.file_path_var.set(file_path)
                self.current_transcript = None
                self.transcript_backup = None
                
                # Clear transcript display
                self.clear_transcript_display()
                
                # Update GUI state
                self.update_gui_state()
                
                # Show video info
                video_info = self.video_service.get_video_info(file_path)
                self.status_var.set(f"Video loaded: {video_info['duration']:.1f}s, {video_info['size'][0]}x{video_info['size'][1]}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load video file: {e}")
    
    def generate_transcript(self):
        """Generate transcript from the current video file."""
        if not self.current_video_path:
            return
        
        def progress_callback(message, progress, detailed_output=None):
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_progress(message, progress, detailed_output)
        
        def generate_worker():
            try:
                self.current_transcript = self.transcript_service.generate_transcript(
                    self.current_video_path, 
                    progress_callback
                )
                self.transcript_backup = self.video_service.create_backup_segments(self.current_transcript)
                
                # Update GUI in main thread
                self.root.after(0, self.on_transcript_generated)
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.on_transcript_error(error_msg))
        
        # Show progress dialog
        self.progress_dialog = ProgressDialog(self.root, "Generating Transcript")
        
        # Start generation in background thread
        thread = threading.Thread(target=generate_worker)
        thread.daemon = True
        thread.start()
    
    def on_transcript_generated(self):
        """Handle successful transcript generation."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        
        self.display_transcript()
        self.update_gui_state()
        self.update_statistics()
        self.status_var.set("Transcript generated successfully")
    
    def on_transcript_error(self, error_message):
        """Handle transcript generation error."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        
        messagebox.showerror("Error", f"Failed to generate transcript: {error_message}")
        self.status_var.set("Transcript generation failed")
    
    def display_transcript(self):
        """Display transcript in the text editor."""
        if not self.current_transcript:
            self.transcript_text.delete('1.0', tk.END)
            return
        
        # Build the full transcript text
        transcript_content = ""
        for i, segment in enumerate(self.current_transcript.segments):
            if not getattr(segment, 'is_deleted', False):
                # Add timestamp as a comment
                timestamp = f"[{segment.start_time:.1f}s - {segment.end_time:.1f}s]"
                transcript_content += f"{timestamp}\n{segment.text}\n\n"
        
        # Update text editor content
        self.transcript_text.delete('1.0', tk.END)
        self.transcript_text.insert('1.0', transcript_content.strip())
        
        # Reset text changed flag
        self.text_changed = False
    
    def clear_transcript_display(self):
        """Clear the transcript display."""
        self.transcript_text.delete('1.0', tk.END)
        self.text_changed = False
    
    def update_gui_state(self):
        """Update the state of GUI elements based on current data."""
        has_video = self.current_video_path is not None
        has_transcript = self.current_transcript is not None
        
        # Update button states
        self.generate_button.config(state='normal' if has_video else 'disabled')
        self.preview_button.config(state='normal' if has_transcript else 'disabled')
        self.trim_button.config(state='normal' if has_transcript else 'disabled')
        self.export_button.config(state='normal' if has_transcript else 'disabled')
    
    def update_statistics(self):
        """Update the statistics display."""
        if not self.current_transcript:
            self.stats_label.config(text="No transcript loaded")
            return
        
        total_segments = len(self.current_transcript.segments)
        active_segments = len(self.current_transcript.get_active_segments())
        
        original_duration = self.current_transcript.duration
        trimmed_duration = self.video_service.estimate_output_duration(self.current_transcript)
        compression_ratio = self.video_service.calculate_compression_ratio(self.current_transcript)
        
        stats_text = (
            f"Segments: {total_segments} total, {active_segments} active | "
            f"Duration: {original_duration:.1f}s → {trimmed_duration:.1f}s | "
            f"Compression: {compression_ratio:.1%}"
        )
        
        self.stats_label.config(text=stats_text)
    

    

    

    
    def preview_changes(self):
        """Preview the changes that will be made to the video."""
        if not self.current_transcript:
            return
        
        preview_segments = self.video_service.create_segments_preview(
            self.current_video_path, 
            self.current_transcript
        )
        
        # Create preview window
        preview_window = tk.Toplevel(self.root)
        preview_window.title("VideoTextCut - Preview Changes")
        self.center_window(preview_window, 600, 400)
        
        # Create text widget with scrollbar
        text_frame = tk.Frame(preview_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Add preview content
        for start_time, end_time, text, is_active in preview_segments:
            status = "KEEP" if is_active else "REMOVE"
            time_range = f"{start_time:.1f}s - {end_time:.1f}s"
            text_widget.insert(tk.END, f"[{status}] {time_range}: {text}\n\n")
        
        text_widget.config(state='disabled')
    
    def trim_video(self):
        """Trim the video based on the current transcript."""
        if not self.current_video_path or not self.current_transcript:
            return
        
        # Get output file path
        output_path = filedialog.asksaveasfilename(
            title="Save Trimmed Video",
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")]
        )
        
        if not output_path:
            return
        
        def progress_callback(message, progress, detailed_output=None):
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_progress(message, progress, detailed_output)
        
        def trim_worker():
            try:
                self.video_service.trim_video_by_transcript(
                    self.current_video_path,
                    self.current_transcript,
                    output_path,
                    progress_callback
                )
                
                self.root.after(0, lambda: self.on_trim_complete(output_path))
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.on_trim_error(error_msg))
        
        # Show progress dialog
        self.progress_dialog = ProgressDialog(self.root, "Trimming Video")
        
        # Start trimming in background thread
        thread = threading.Thread(target=trim_worker)
        thread.daemon = True
        thread.start()
    
    def on_trim_complete(self, output_path):
        """Handle successful video trimming."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        
        messagebox.showinfo("Success", f"Video trimmed successfully!\nSaved to: {output_path}")
        self.status_var.set("Video trimming completed")
    
    def on_trim_error(self, error_message):
        """Handle video trimming error."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        
        messagebox.showerror("Error", f"Failed to trim video: {error_message}")
        self.status_var.set("Video trimming failed")
    

    
    def save_transcript(self):
        """Save transcript to file with detailed progress display."""
        if not self.current_transcript:
            messagebox.showinfo("Info", "No transcript to save")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Transcript",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if file_path:
            def progress_callback(message, progress, detailed_output=None):
                if hasattr(self, 'progress_dialog') and self.progress_dialog:
                    self.progress_dialog.update_progress(message, progress, detailed_output)
            
            def save_worker():
                try:
                    progress_callback("Preparing transcript data...", 0.0, "Getting content from text editor...")
                    
                    # Get current content from text editor
                    content = self.transcript_text.get('1.0', tk.END).strip()
                    lines = content.split('\n')
                    
                    progress_callback("Processing transcript lines...", 0.1, f"Found {len(lines)} lines to process")
                    
                    # Filter out timestamp lines and prepare content
                    filtered_lines = []
                    for i, line in enumerate(lines):
                        line = line.strip()
                        # Skip timestamp lines
                        if line and not (line.startswith('[') and line.endswith(']') and 's -' in line):
                            filtered_lines.append(line)
                        
                        # Update progress every 100 lines
                        if i % 100 == 0:
                            progress = 0.1 + (i / len(lines)) * 0.3
                            progress_callback("Processing transcript lines...", progress, f"Processed {i+1}/{len(lines)} lines")
                    
                    progress_callback("Writing to file...", 0.4, f"Writing {len(filtered_lines)} lines to {file_path}")
                    
                    # Write to file with progress updates
                    with open(file_path, 'w', encoding='utf-8') as f:
                        for i, line in enumerate(filtered_lines):
                            f.write(f"{line}\n")
                            
                            # Update progress every 50 lines or for small files, every 10 lines
                            update_interval = 50 if len(filtered_lines) > 500 else 10
                            if i % update_interval == 0 or i == len(filtered_lines) - 1:
                                progress = 0.4 + (i / len(filtered_lines)) * 0.5
                                progress_callback("Writing to file...", progress, f"Written {i+1}/{len(filtered_lines)} lines")
                    
                    progress_callback("Finalizing file...", 0.9, "Flushing file buffer and closing...")
                    
                    # Verify file was written correctly
                    file_size = os.path.getsize(file_path)
                    progress_callback("File save complete!", 1.0, f"Successfully saved {len(filtered_lines)} lines ({file_size} bytes) to {file_path}")
                    
                    self.root.after(0, lambda: self.on_save_complete(file_path))
                    
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: self.on_save_error(error_msg))
            
            # Show progress dialog
            self.progress_dialog = ProgressDialog(self.root, "Saving Transcript")
            
            # Start saving in background thread
            thread = threading.Thread(target=save_worker)
            thread.daemon = True
            thread.start()
    
    def on_save_complete(self, file_path):
        """Handle successful transcript saving."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        
        messagebox.showinfo("Success", f"Transcript saved successfully!\nSaved to: {file_path}")
        self.status_var.set("Transcript saved successfully")
    
    def on_save_error(self, error_message):
        """Handle transcript saving error."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        
        messagebox.showerror("Error", f"Failed to save transcript: {error_message}")
        self.status_var.set("Transcript save failed")
    
    def load_transcript(self):
        """Load transcript from file."""
        # This is a placeholder - in a full implementation, you'd want to save/load
        # the full transcript data structure, not just the text
        messagebox.showinfo("Info", "Load transcript feature not implemented yet")
    
    def export_transcript(self):
        """Export transcript in various formats."""
        if not self.current_transcript:
            return
        
        # Simple text export for now
        self.save_transcript()
    
    def on_text_changed(self, event=None):
        """Handle text changes in the editor."""
        if not self.current_transcript:
            return
        
        self.text_changed = True
        
        # Cancel existing timer
        if self.auto_save_timer:
            self.root.after_cancel(self.auto_save_timer)
        
        # Set new timer for auto-save (2 seconds delay)
        self.auto_save_timer = self.root.after(2000, self.auto_save_transcript)
    
    def auto_save_transcript(self):
        """Auto-save the transcript from the text editor."""
        if not self.text_changed or not self.current_transcript:
            return
        
        try:
            # Get the current text content
            content = self.transcript_text.get('1.0', tk.END).strip()
            
            # Parse the content back into segments
            self.parse_text_to_segments(content)
            
            # Update statistics
            self.update_statistics()
            
            # Reset change flag
            self.text_changed = False
            
            # Update status
            self.status_var.set("Auto-saved transcript")
            
        except Exception as e:
            print(f"Auto-save error: {e}")
    
    def parse_text_to_segments(self, content):
        """Parse text content back into transcript segments with word-level precision."""
        if not content.strip():
            return
        
        # Use the enhanced update_from_text method
        self.current_transcript.update_from_text(content)
    
    def undo_changes(self):
        """Undo the last change to the transcript."""
        try:
            self.transcript_text.edit_undo()
        except tk.TclError:
            messagebox.showinfo("Info", "Nothing to undo")
    
    def redo_changes(self):
        """Redo the last undone change to the transcript."""
        try:
            self.transcript_text.edit_redo()
        except tk.TclError:
            messagebox.showinfo("Info", "Nothing to redo")
    
    def show_about(self):
        """Show about dialog."""
        about_text = (
            "VideoTextCut\n\n"
            "A tool for generating, editing, and trimming video transcripts.\n\n"
            "Features:\n"
            "• Automatic transcript generation using Whisper\n"
            "• Document-style transcript editing with auto-save\n"
            "• Video trimming based on transcript\n"
            "• Interactive transcript editing with undo/redo"
        )
        
        messagebox.showinfo("VideoTextCut - About", about_text)
    
    def run(self):
        """Start the application."""
        self.root.mainloop()


# This file is imported by main.py - no standalone execution needed