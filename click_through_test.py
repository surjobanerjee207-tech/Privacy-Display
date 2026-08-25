import tkinter as tk
import ctypes

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
GA_ROOT = 2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

root = tk.Tk()
root.title("Click-Through Test")
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)
root.attributes("-alpha", 0.5)
root.configure(bg="red")

label = tk.Label(root, text="If click-through works, this red screen\n"
                            "is see-through to clicks below it.\n"
                            "Press ESC to quit.",
                  font=("Segoe UI", 20, "bold"), fg="white", bg="red")
label.pack(expand=True)

root.update_idletasks()
raw_hwnd = root.winfo_id()
root_hwnd = ctypes.windll.user32.GetAncestor(raw_hwnd, GA_ROOT)
hwnd = root_hwnd if root_hwnd else raw_hwnd

# Try to load the 64-bit or 32-bit versions of the functions
try:
    GetWindowLong = ctypes.windll.user32.GetWindowLongPtrW
    GetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int]
    GetWindowLong.restype = ctypes.c_void_p
    
    SetWindowLong = ctypes.windll.user32.SetWindowLongPtrW
    SetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    SetWindowLong.restype = ctypes.c_void_p
except AttributeError:
    GetWindowLong = ctypes.windll.user32.GetWindowLongW
    GetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int]
    GetWindowLong.restype = ctypes.c_long
    
    SetWindowLong = ctypes.windll.user32.SetWindowLongW
    SetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    SetWindowLong.restype = ctypes.c_long

print(f"raw winfo_id(): {raw_hwnd}")
print(f"resolved root hwnd: {root_hwnd}")
print(f"using hwnd: {hwnd}")
print(f"label hwnd: {label.winfo_id()}")

# List of all HWNDs to make click-through
hwnds_to_style = [hwnd, raw_hwnd, label.winfo_id()]

for h in hwnds_to_style:
    style_before = GetWindowLong(h, GWL_EXSTYLE)
    style_before_val = int(style_before) if style_before is not None else 0
    new_style = style_before_val | WS_EX_LAYERED | WS_EX_TRANSPARENT
    SetWindowLong(h, GWL_EXSTYLE, new_style)
    ctypes.windll.user32.SetWindowPos(
        h, 0, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
    )

print("Styles applied to all window handles.")
print("Try clicking on your desktop / another app right now.")
print("If it responds, click-through is working.")
print("Press ESC in this window's console focus, or Ctrl+C here, to quit.")

root.bind("<Escape>", lambda e: root.destroy())
root.mainloop()
