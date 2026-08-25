import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageFilter, ImageTk, ImageGrab
from pynput import keyboard
import numpy as np
import ctypes

# Windows extended window style constants, used to make the fullscreen
# overlay "click-through" so mouse input passes to whatever app is
# actually underneath it, while the blurred image still displays.
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


def set_window_click_through(hwnd, enabled=True):
    """
    Toggles click-through on a Windows window handle. When enabled,
    all mouse events pass straight through to the window(s) below it
    instead of being captured — the window is still visible, just not
    interactive.
    """
    try:
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enabled:
            new_style = style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            new_style = (style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
    except Exception as e:
        print("Failed to set click-through window style:", e)

def parse_shortcut_to_pynput(shortcut_str):
    """
    Translates a user-friendly shortcut string like 'Ctrl+Shift+P'
    to the format expected by pynput (e.g., '<ctrl>+<shift>+p').
    """
    parts = shortcut_str.lower().split('+')
    pynput_parts = []
    for part in parts:
        part = part.strip()
        if part == 'ctrl':
            pynput_parts.append('<ctrl>')
        elif part == 'shift':
            pynput_parts.append('<shift>')
        elif part == 'alt':
            pynput_parts.append('<alt>')
        elif part in ('space', 'spacebar'):
            pynput_parts.append('<space>')
        else:
            pynput_parts.append(part)
    return '+'.join(pynput_parts)


class FloatingButton(tk.Toplevel):
    """
    A small, always-on-top, draggable circular button that floats over
    every other application on the desktop. Clicking it toggles privacy
    mode directly, without needing to bring the main dashboard to focus.
    """
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.size = 56

        self.overrideredirect(True)          # No title bar / borders
        self.attributes("-topmost", True)    # Always stays above all other windows
        self.attributes("-alpha", 0.92)
        self.resizable(False, False)

        # Position it near the top-right corner of the screen by default
        screen_w = self.winfo_screenwidth()
        start_x = screen_w - self.size - 30
        start_y = 80
        self.geometry(f"{self.size}x{self.size}+{start_x}+{start_y}")

        # Make the window background transparent-ish using a colorkey trick on Windows,
        # falling back to a plain colored circle if unsupported.
        self.bg_off = "#85B623"   # green = privacy off
        self.bg_on = "#FF3B30"    # red = privacy on

        self.canvas = tk.Canvas(self, width=self.size, height=self.size,
                                 highlightthickness=0, bd=0, bg=self.app.bg_color)
        self.canvas.pack(fill="both", expand=True)

        try:
            # Attempt true transparency around the circle (Windows only)
            self.wm_attributes("-transparentcolor", self.app.bg_color)
        except tk.TclError:
            pass

        self.circle = self.canvas.create_oval(2, 2, self.size - 2, self.size - 2,
                                               fill=self.bg_off, outline="")
        self.icon = self.canvas.create_text(self.size // 2, self.size // 2,
                                             text="🔓", font=("Segoe UI", 18))

        # Click to toggle, drag to reposition
        self._drag_data = {"x": 0, "y": 0, "moved": False}
        for widget in (self.canvas,):
            widget.bind("<ButtonPress-1>", self.on_press)
            widget.bind("<B1-Motion>", self.on_drag)
            widget.bind("<ButtonRelease-1>", self.on_release)

        self.refresh()

    def on_press(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["moved"] = False

    def on_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        if abs(dx) > 2 or abs(dy) > 2:
            self._drag_data["moved"] = True
        new_x = self.winfo_x() + dx
        new_y = self.winfo_y() + dy
        self.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        # Only treat as a click if the button wasn't dragged
        if not self._drag_data["moved"]:
            self.app.toggle_privacy()

    def refresh(self):
        """Sync the floating button's appearance with the current privacy state."""
        if self.app.privacy_mode:
            self.canvas.itemconfig(self.circle, fill=self.bg_on)
            self.canvas.itemconfig(self.icon, text="🔒")
        else:
            self.canvas.itemconfig(self.circle, fill=self.bg_off)
            self.canvas.itemconfig(self.icon, text="🔓")
        self.lift()


class AcerPrivacyGuardApp(tk.Tk):
    """
    Manual-only privacy screen, similar to Samsung's "Privacy Display" feature:
    a single button (or shortcut) turns the privacy overlay ON or OFF.
    No camera. No auto-detection. Just a direct switch.
    """
    def __init__(self):
        super().__init__()
        self.title("Privacy Display")
        self.geometry("300x220")
        self.resizable(False, False)

        # Application State
        self.privacy_mode = False  # True = overlay showing, False = overlay hidden
        self.selected_effect = tk.StringVar(value="Privacy Filter (Center Clear)")
        self.shortcut_str = tk.StringVar(value="spacebar+b")

        # Color Theme
        self.bg_color = "#121212"
        self.card_bg = "#1E1E1E"
        self.fg_color = "#FFFFFF"
        self.accent_color = "#00A3FF"
        self.green_color = "#85B623"
        self.red_color = "#FF3B30"

        self.configure(bg=self.bg_color)

        self.overlay_window = None
        self.overlay_image = None

        self.create_widgets()
        self.update_ui_state()

        self.hotkey_listener = None
        self.setup_keyboard_shortcut()

        # Floating always-on-top button that hovers over every other app
        self.floating_btn = FloatingButton(self)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # Card with the current state and the toggle button.
        self.card_frame = tk.Frame(self, bg=self.card_bg, bd=1, relief="flat",
                                    highlightbackground="#333333", highlightthickness=1)
        self.card_frame.pack(fill="both", expand=True, padx=20, pady=(20, 10))

        self.state_lbl = tk.Label(self.card_frame, text="🔓 OFF",
                                   font=("Segoe UI", 22, "bold"), fg=self.green_color,
                                   bg=self.card_bg, pady=30)
        self.state_lbl.pack()

        self.toggle_btn = tk.Button(self.card_frame, text="TURN ON",
                                     font=("Segoe UI", 13, "bold"), fg=self.fg_color, bg="#333333",
                                     activebackground="#444444", activeforeground=self.fg_color,
                                     bd=0, relief="flat", padx=40, pady=14, cursor="hand2",
                                     command=self.toggle_privacy)
        self.toggle_btn.pack(pady=10)

        self.toggle_btn.bind("<Enter>", lambda e: self.toggle_btn.configure(bg="#444444"))
        self.toggle_btn.bind("<Leave>", lambda e: self.toggle_btn.configure(bg="#333333"))

        # Settings row (Effect + Shortcut). Visible only while privacy is OFF —
        # hidden automatically once privacy mode is turned on, see update_ui_state().
        self.settings_frame = tk.Frame(self, bg=self.bg_color, pady=10, padx=20)
        self.settings_frame.pack(fill="x")

        effect_lbl = tk.Label(self.settings_frame, text="Effect:", font=("Segoe UI", 9),
                               fg="#888888", bg=self.bg_color)
        effect_lbl.grid(row=0, column=0, sticky="w", pady=2)

        effect_dropdown = ttk.Combobox(self.settings_frame, textvariable=self.selected_effect,
                                        values=["Privacy Filter (Center Clear)", "Screen Blur", "Translucent Dark", "Translucent Light", "Solid Black"],
                                        state="readonly", width=15)
        effect_dropdown.grid(row=0, column=1, sticky="w", padx=10, pady=2)

        shortcut_lbl = tk.Label(self.settings_frame, text="Shortcut:", font=("Segoe UI", 9),
                                 fg="#888888", bg=self.bg_color)
        shortcut_lbl.grid(row=1, column=0, sticky="w", pady=2)

        self.shortcut_entry = tk.Entry(self.settings_frame, textvariable=self.shortcut_str,
                                        font=("Segoe UI", 9), fg=self.fg_color, bg="#333333",
                                        insertbackground="white", bd=0, width=15)
        self.shortcut_entry.grid(row=1, column=1, sticky="w", padx=10, pady=2)

        self.shortcut_entry.bind("<FocusOut>", lambda e: self.setup_keyboard_shortcut())
        self.shortcut_entry.bind("<Return>", lambda e: self.setup_keyboard_shortcut())

    def setup_keyboard_shortcut(self):
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()

        pynput_shortcut = parse_shortcut_to_pynput(self.shortcut_str.get())

        def on_activate():
            self.after(0, self.toggle_privacy)

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({
                pynput_shortcut: on_activate
            })
            self.hotkey_listener.start()
        except Exception as e:
            print(f"Error setting up hotkey '{pynput_shortcut}':", e)

    def toggle_privacy(self):
        """Single entry point for button, shortcut, and overlay unlock control."""
        if self.privacy_mode:
            self.privacy_mode = False
            self.hide_overlay()
        else:
            self.privacy_mode = True
            self.show_overlay()
        self.update_ui_state()
        if hasattr(self, "floating_btn") and self.floating_btn is not None:
            self.floating_btn.refresh()

    def update_ui_state(self):
        if self.privacy_mode:
            self.state_lbl.configure(text="🔒 ON", fg=self.red_color)
            self.toggle_btn.configure(text="TURN OFF")
            self.settings_frame.pack_forget()
            self.geometry("300x220")
        else:
            self.state_lbl.configure(text="🔓 OFF", fg=self.green_color)
            self.toggle_btn.configure(text="TURN ON")
            self.settings_frame.pack(fill="x")
            self.geometry("300x320")

    def show_overlay(self):
        if self.overlay_window is not None:
            self.overlay_window.lift()
            return

        self.overlay_window = tk.Toplevel(self)
        self.overlay_window.title("Acer Privacy Overlay")
        self.overlay_window.attributes("-fullscreen", True)
        self.overlay_window.attributes("-topmost", True)
        self.overlay_window.overrideredirect(True)

        effect = self.selected_effect.get()
        if effect == "Privacy Filter (Center Clear)":
            self.apply_privacy_filter_overlay()
        elif effect == "Screen Blur":
            self.apply_blur_overlay()
        elif effect == "Translucent Dark":
            self.apply_translucent_overlay("#000000", 0.30)
        elif effect == "Translucent Light":
            self.apply_translucent_overlay("#FFFFFF", 0.30)
        else:
            self.apply_solid_overlay()

        self.overlay_window.lift()
        # Keep the floating button visible above the fullscreen overlay too
        if hasattr(self, "floating_btn") and self.floating_btn is not None:
            self.floating_btn.lift()

        # Make the overlay click-through: it stays visible (blurred image,
        # tint, etc.) but all mouse input passes straight to whatever app
        # is actually underneath, so apps keep working normally while
        # privacy mode is on. Must run after the window is realized so
        # winfo_id() returns a valid HWND.
        self.overlay_window.update_idletasks()
        hwnd = self.overlay_window.winfo_id()
        set_window_click_through(hwnd, enabled=True)

    def apply_privacy_filter_overlay(self):
        """
        Simulates a physical privacy screen filter: the center of the
        screen stays sharp and fully readable head-on, while content
        toward the edges is progressively, continuously blurred and
        darkened so it can't be made out from the side.

        This blends across several precomputed blur levels (not just a
        single blurred layer cross-faded with the sharp one) using an
        eased (smoothstep) radial curve, which avoids the "ghosting"
        double-exposure look and abrupt linear falloff of a simple
        two-layer composite — giving a genuinely smooth defocus similar
        to a real depth-of-field / privacy-filter gradient.
        """
        try:
            screen_width = self.overlay_window.winfo_screenwidth()
            screen_height = self.overlay_window.winfo_screenheight()

            screenshot = ImageGrab.grab()
            screenshot = screenshot.resize((screen_width, screen_height), Image.Resampling.LANCZOS).convert("RGBA")

            # Precompute a stack of increasing blur levels. Blending
            # continuously between neighboring levels (instead of just
            # "sharp" and "one blurred version") is what makes the
            # transition read as a smooth defocus rather than a fade.
            blur_radii = [0, 5, 10, 16, 22, 28]
            layers = [screenshot if r == 0 else screenshot.filter(ImageFilter.GaussianBlur(radius=r))
                      for r in blur_radii]
            stack = np.stack([np.array(im, dtype=np.float32) for im in layers], axis=0)  # (L, H, W, 4)
            num_levels = len(blur_radii)

            h, w = screen_height, screen_width
            y, x = np.ogrid[0:h, 0:w]
            cx, cy = w / 2.0, h / 2.0
            dist = np.sqrt(((x - cx) / (w / 2.0)) ** 2 + ((y - cy) / (h / 2.0)) ** 2)

            inner_radius = 0.42  # fully clear zone — center roughly half the screen
            outer_radius = 1.05  # full blur/dark strength only reached past the corners

            t = np.clip((dist - inner_radius) / (outer_radius - inner_radius), 0.0, 1.0)
            # Smoothstep easing: gentle start, gentle end, instead of a linear ramp
            eased = t * t * (3 - 2 * t)

            # Continuous blur-level index per pixel, blended between its two
            # nearest precomputed levels
            level_pos = eased * (num_levels - 1)
            idx_low = np.clip(np.floor(level_pos).astype(np.int32), 0, num_levels - 2)
            idx_high = idx_low + 1
            frac = (level_pos - idx_low)[..., None]  # (H, W, 1) for broadcasting over RGBA

            ii, jj = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
            low_vals = stack[idx_low, ii, jj]
            high_vals = stack[idx_high, ii, jj]
            blended = low_vals * (1 - frac) + high_vals * frac

            # Gentle per-pixel dark tint, scaled by the same eased curve —
            # kept light so already-dark backgrounds don't collapse to pure black
            max_tint = 60.0
            tint_alpha = (eased * max_tint)[..., None]
            blended[..., :3] = blended[..., :3] * (1 - tint_alpha / 255.0)

            combined = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), mode="RGBA")

            self.overlay_image = ImageTk.PhotoImage(combined)

            bg_label = tk.Label(self.overlay_window, image=self.overlay_image, bg="#000000")
            bg_label.pack(fill="both", expand=True)

            self.overlay_window.attributes("-alpha", 1.0)
        except Exception as e:
            print("Failed to apply privacy filter effect, falling back to standard blur:", e)
            self.apply_blur_overlay()

    def apply_blur_overlay(self):
        try:
            screen_width = self.overlay_window.winfo_screenwidth()
            screen_height = self.overlay_window.winfo_screenheight()

            screenshot = ImageGrab.grab()
            screenshot = screenshot.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
            blurred_img = screenshot.filter(ImageFilter.GaussianBlur(radius=25))

            self.overlay_image = ImageTk.PhotoImage(blurred_img)

            bg_label = tk.Label(self.overlay_window, image=self.overlay_image, bg="#000000")
            bg_label.pack(fill="both", expand=True)

            self.overlay_window.attributes("-alpha", 1.0)
        except Exception as e:
            print("Failed to apply Gaussian Blur, falling back to translucent black:", e)
            self.apply_translucent_overlay("#000000", 0.30)

    def apply_translucent_overlay(self, color_hex, opacity):
        """
        Captures the real screen content, applies a light blur so nothing
        underneath is readable, then tints it with the given color at the
        given strength. This replaces the old approach of using window
        alpha transparency, which was literally see-through and left
        text/content fully readable underneath.
        """
        try:
            screen_width = self.overlay_window.winfo_screenwidth()
            screen_height = self.overlay_window.winfo_screenheight()

            screenshot = ImageGrab.grab()
            screenshot = screenshot.resize((screen_width, screen_height), Image.Resampling.LANCZOS)

            # Light blur — enough that text/UI underneath is unreadable,
            # but the overall image stays only moderately obscured.
            blurred_img = screenshot.filter(ImageFilter.GaussianBlur(radius=12)).convert("RGBA")

            # Apply the color tint on top of the blurred capture
            tint_layer = Image.new("RGBA", blurred_img.size, color_hex)
            tint_alpha = int(255 * opacity)
            tint_layer.putalpha(tint_alpha)
            combined = Image.alpha_composite(blurred_img, tint_layer)

            self.overlay_image = ImageTk.PhotoImage(combined)

            bg_label = tk.Label(self.overlay_window, image=self.overlay_image, bg=color_hex)
            bg_label.pack(fill="both", expand=True)

            self.overlay_window.attributes("-alpha", 1.0)
        except Exception as e:
            print("Failed to apply translucent blur overlay, falling back to solid:", e)
            self.apply_solid_overlay()

    def apply_solid_overlay(self):
        self.overlay_window.configure(bg="#000000")
        self.overlay_window.attributes("-alpha", 1.0)

    def hide_overlay(self):
        if self.overlay_window is not None:
            self.overlay_window.destroy()
            self.overlay_window = None
            self.overlay_image = None

    def on_closing(self):
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        if hasattr(self, "floating_btn") and self.floating_btn is not None:
            self.floating_btn.destroy()
        self.hide_overlay()
        self.destroy()


if __name__ == "__main__":
    app = AcerPrivacyGuardApp()
    app.mainloop()
