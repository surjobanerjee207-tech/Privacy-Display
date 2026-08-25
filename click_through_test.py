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

print(f"raw winfo_id(): {raw_hwnd}")
print(f"resolved root hwnd: {root_hwnd}")
print(f"using hwnd: {hwnd}")

style_before = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
print(f"style before: {style_before:#010x}")

new_style = style_before | WS_EX_LAYERED | WS_EX_TRANSPARENT
result = ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
print(f"SetWindowLongW result: {result}")

ctypes.windll.user32.SetWindowPos(
    hwnd, 0, 0, 0, 0, 0,
    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
)

style_after = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
print(f"style after:  {style_after:#010x}")
print(f"transparent bit set: {bool(style_after & WS_EX_TRANSPARENT)}")
print()
print("Try clicking on your desktop / another app right now.")
print("If it responds, click-through is working.")
print("Press ESC in this window's console focus, or Ctrl+C here, to quit.")

root.bind("<Escape>", lambda e: root.destroy())
root.mainloop()
