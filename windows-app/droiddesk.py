from __future__ import annotations

import socket
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from core import ALLOWED_COMMANDS, DeviceRegistry, DroidDeskServer, make_handler


PORT = 8765
BG = "#071019"
PANEL = "#0d1b28"
PANEL_2 = "#102638"
CYAN = "#3ce7ff"
BLUE = "#5b8cff"
TEXT = "#edfaff"
MUTED = "#8aa6b8"
GREEN = "#4af0a7"
RED = "#ff6b7a"


def local_ipv4() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


class DroidDeskApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.registry = DeviceRegistry()
        self.server = DroidDeskServer(("0.0.0.0", PORT), make_handler(self.registry))
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.selected_device_id: str | None = None
        self.device_rows: dict[str, ttk.Treeview] = {}

        root.title("DroidDesk Control Centre")
        root.geometry("1040x680")
        root.minsize(880, 600)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._styles()
        self._layout()
        self.new_pairing_code()
        self.refresh()

    def _styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=36, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=PANEL_2, foreground=CYAN,
                        relief="flat", font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", "#17435a")])
        style.configure("TButton", background=PANEL_2, foreground=TEXT, borderwidth=0,
                        padding=(14, 9), font=("Segoe UI Semibold", 10))
        style.map("TButton", background=[("active", "#1a4056")])
        style.configure("Accent.TButton", background=BLUE, foreground="white")
        style.map("Accent.TButton", background=[("active", "#709cff")])

    def _label(self, parent: tk.Widget, text: str, size: int = 10, color: str = TEXT,
               weight: str = "normal") -> tk.Label:
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI" if weight == "normal" else "Segoe UI Semibold", size))

    def _layout(self) -> None:
        sidebar = tk.Frame(self.root, bg="#081725", width=250)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        logo = tk.Frame(sidebar, bg="#081725")
        logo.pack(fill="x", padx=22, pady=(24, 30))
        self._label(logo, "DROID", 18, CYAN, "bold").pack(side="left")
        self._label(logo, "DESK", 18, TEXT, "bold").pack(side="left")

        self._label(sidebar, "CONTROL CENTRE", 9, MUTED, "bold").pack(anchor="w", padx=22)
        for item in ("Overview", "Connected devices", "Activity"):
            label = self._label(sidebar, item, 11, TEXT if item == "Overview" else MUTED)
            label.pack(fill="x", padx=22, pady=(14 if item == "Overview" else 9, 0))

        spacer = tk.Frame(sidebar, bg="#081725")
        spacer.pack(fill="both", expand=True)
        self._label(sidebar, "LOCAL CONNECTION", 9, MUTED, "bold").pack(anchor="w", padx=22)
        self.address_label = self._label(sidebar, f"http://{local_ipv4()}:{PORT}", 10, CYAN)
        self.address_label.pack(anchor="w", padx=22, pady=(8, 6))
        self._label(sidebar, "Private Wi-Fi only", 9, MUTED).pack(anchor="w", padx=22, pady=(0, 24))

        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=28, pady=24)

        top = tk.Frame(main, bg=BG)
        top.pack(fill="x")
        title = tk.Frame(top, bg=BG)
        title.pack(side="left")
        self._label(title, "Connected workspace", 22, TEXT, "bold").pack(anchor="w")
        self._label(title, "Control your Android desktop from Windows", 10, MUTED).pack(anchor="w", pady=(4, 0))
        self.clock_label = self._label(top, "", 11, CYAN, "bold")
        self.clock_label.pack(side="right", anchor="n", pady=5)

        pairing = tk.Frame(main, bg=PANEL, highlightbackground="#17364a", highlightthickness=1)
        pairing.pack(fill="x", pady=(22, 18))
        pair_left = tk.Frame(pairing, bg=PANEL)
        pair_left.pack(side="left", fill="x", expand=True, padx=20, pady=16)
        self._label(pair_left, "PAIR A PHONE", 9, MUTED, "bold").pack(anchor="w")
        self.pair_code_label = self._label(pair_left, "------", 27, CYAN, "bold")
        self.pair_code_label.pack(anchor="w", pady=(4, 0))
        self.pair_expiry_label = self._label(pair_left, "", 9, MUTED)
        self.pair_expiry_label.pack(anchor="w", pady=(2, 0))
        ttk.Button(pairing, text="New pairing code", style="Accent.TButton",
                   command=self.new_pairing_code).pack(side="right", padx=20)

        section = tk.Frame(main, bg=BG)
        section.pack(fill="x", pady=(0, 8))
        self._label(section, "Devices", 14, TEXT, "bold").pack(side="left")
        self.status_label = self._label(section, "0 connected", 10, MUTED)
        self.status_label.pack(side="right")

        columns = ("name", "status", "battery", "android", "last")
        self.tree = ttk.Treeview(main, columns=columns, show="headings", height=7)
        self.tree.heading("name", text="DEVICE")
        self.tree.heading("status", text="STATUS")
        self.tree.heading("battery", text="BATTERY")
        self.tree.heading("android", text="ANDROID")
        self.tree.heading("last", text="LAST SEEN")
        self.tree.column("name", width=180)
        self.tree.column("status", width=100)
        self.tree.column("battery", width=90)
        self.tree.column("android", width=90)
        self.tree.column("last", width=130)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.device_selected)

        actions = tk.Frame(main, bg=BG)
        actions.pack(fill="x", pady=(16, 0))
        self.action_hint = self._label(actions, "Select a connected phone to send an action.", 10, MUTED)
        self.action_hint.pack(side="left")
        button_area = tk.Frame(actions, bg=BG)
        button_area.pack(side="right")
        ttk.Button(button_area, text="Show home",
                   command=lambda: self.send_command("SHOW_HOME")).pack(side="left", padx=4)
        ttk.Button(button_area, text="Open settings",
                   command=lambda: self.send_command("OPEN_SETTINGS")).pack(side="left", padx=4)
        ttk.Button(button_area, text="Sync now", style="Accent.TButton",
                   command=lambda: self.send_command("SYNC_NOW")).pack(side="left", padx=4)

    def new_pairing_code(self) -> None:
        session = self.registry.new_pairing_code()
        self.pair_code_label.configure(text=session.code)

    def device_selected(self, _event: object) -> None:
        selected = self.tree.selection()
        self.selected_device_id = selected[0] if selected else None
        if self.selected_device_id:
            name = self.tree.item(self.selected_device_id, "values")[0]
            self.action_hint.configure(text=f"Actions will be sent to {name}.")

    def send_command(self, command: str) -> None:
        if command not in ALLOWED_COMMANDS:
            return
        if not self.selected_device_id:
            messagebox.showinfo("DroidDesk", "Select a connected phone first.")
            return
        try:
            self.registry.queue_command(self.selected_device_id, command)
            self.action_hint.configure(text=f"{command.replace('_', ' ').title()} queued.")
        except KeyError:
            messagebox.showerror("DroidDesk", "That device is no longer available.")

    def refresh(self) -> None:
        now = time.time()
        self.clock_label.configure(text=datetime.now().strftime("%H:%M  •  %d %b %Y"))
        session = self.registry.current_pairing()
        if session:
            remaining = max(0, int(session.expires_at - now))
            self.pair_expiry_label.configure(text=f"Expires in {remaining // 60}:{remaining % 60:02d}")
        else:
            self.pair_code_label.configure(text="EXPIRED")
            self.pair_expiry_label.configure(text="Generate a new code to pair")

        devices = self.registry.devices()
        live = 0
        existing = set(self.tree.get_children())
        for device in devices:
            device_id = device["id"]
            age = max(0, now - float(device.get("lastSeen", 0)))
            online = age < 15
            live += int(online)
            values = (
                device["name"],
                "Online" if online else "Offline",
                f"{device['batteryLevel']}%" if device.get("batteryLevel") is not None else "—",
                device.get("androidVersion") or "—",
                "Now" if age < 10 else f"{int(age)}s ago" if age < 60 else f"{int(age // 60)}m ago",
            )
            if device_id in existing:
                self.tree.item(device_id, values=values)
                existing.remove(device_id)
            else:
                self.tree.insert("", "end", iid=device_id, values=values)
        for stale in existing:
            self.tree.delete(stale)
        self.status_label.configure(text=f"{live} connected • {len(devices)} paired")
        self.root.after(1000, self.refresh)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    DroidDeskApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

