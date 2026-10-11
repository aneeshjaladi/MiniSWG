import sys
import os

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import winreg
    import ctypes

    INTERNET_OPTION_SETTINGS_CHANGED = 39
    INTERNET_OPTION_REFRESH = 37


def notify_windows_internet_settings():
    """Notifies Windows system and browsers to refresh proxy settings immediately."""
    if not IS_WINDOWS:
        return
    try:
        wininet = ctypes.windll.wininet
        wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
    except Exception:
        pass


def is_windows_proxy_enabled() -> tuple[bool, str]:
    """Returns (is_enabled, server_address) from Windows Registry."""
    if not IS_WINDOWS:
        return False, ""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            try:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except FileNotFoundError:
                server = ""
            return bool(enabled), server or ""
    except Exception:
        return False, ""


def enable_windows_proxy(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """Enables Windows system proxy in HKEY_CURRENT_USER."""
    if not IS_WINDOWS:
        return False
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    server = f"{host}:{port}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, server)
            # Bypass local intranet addresses if desired
            try:
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
            except Exception:
                pass
        notify_windows_internet_settings()
        return True
    except Exception as e:
        print(f"Error enabling Windows proxy: {e}", file=sys.stderr)
        return False


def disable_windows_proxy() -> bool:
    """Disables Windows system proxy in HKEY_CURRENT_USER."""
    if not IS_WINDOWS:
        return False
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        notify_windows_internet_settings()
        return True
    except Exception as e:
        print(f"Error disabling Windows proxy: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 2:
        enabled, server = is_windows_proxy_enabled()
        status_text = f"ENABLED ({server})" if enabled else "DISABLED"
        print(f"Windows System Proxy Status: {status_text}")
        print("Usage: python -m miniswg.winproxy [enable <port> | disable | status | toggle]")
        return

    cmd = sys.argv[1].lower()
    if cmd == "enable":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
        if enable_windows_proxy(port=port):
            print(f"[+] Windows system proxy ENABLED on 127.0.0.1:{port}")
        else:
            print("[-] Failed to enable Windows proxy")
    elif cmd == "disable":
        if disable_windows_proxy():
            print("[+] Windows system proxy DISABLED (Direct internet restored)")
        else:
            print("[-] Failed to disable Windows proxy")
    elif cmd == "status":
        enabled, server = is_windows_proxy_enabled()
        status_text = f"ENABLED ({server})" if enabled else "DISABLED"
        print(f"Windows System Proxy Status: {status_text}")
    elif cmd == "toggle":
        enabled, _ = is_windows_proxy_enabled()
        if enabled:
            disable_windows_proxy()
            print("[+] Windows system proxy DISABLED (Direct internet restored)")
        else:
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
            enable_windows_proxy(port=port)
            print(f"[+] Windows system proxy ENABLED on 127.0.0.1:{port}")


if __name__ == "__main__":
    main()
