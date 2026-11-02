# -*- coding: utf-8 -*-
"""
inspect_window.py
Inspecciona ventanas activas y árbol de controles accesibles (UIA / Win32).
Uso:
  python inspect_window.py --list
  python inspect_window.py --title "Dietowin"
  python inspect_window.py --title "SuiteBiológica" --depth 3
"""

import sys
import argparse

def list_windows():
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")
    print("=== VENTANAS ACTIVAS EN EL ESCRITORIO (UIA) ===")
    for w in desktop.windows():
        t = w.window_text().strip()
        if t:
            try:
                handle = w.handle
                cls = w.class_name()
                print(f" [Handle: 0x{handle:08X}] Clase: '{cls}' | Título: '{t}'")
            except Exception:
                print(f" Título: '{t}'")

def inspect_window_controls(title: str, depth: int = 3):
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")
    print(f"Buscando ventana coincidente con: '{title}'...")
    try:
        w = desktop.window(title_re=f".*{title}.*")
        w.wait('exists', timeout=5)
        print(f"✓ Ventana localizada: '{w.window_text()}' (Clase: {w.class_name()})")
        print("\n=== ÁRBOL DE CONTROLES ACCESIBLES (print_control_identifiers) ===")
        w.print_control_identifiers(depth=depth)
    except Exception as e:
        print(f"Error inspeccionando con UIA: {e}. Intentando con backend win32...")
        try:
            desktop_win32 = Desktop(backend="win32")
            w32 = desktop_win32.window(title_re=f".*{title}.*")
            w32.wait('exists', timeout=5)
            print(f"✓ Ventana localizada con Win32: '{w32.window_text()}'")
            w32.print_control_identifiers(depth=depth)
        except Exception as e2:
            print(f"Error inspeccionando con Win32: {e2}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspección de controles accesibles de ventanas Windows")
    parser.add_argument("--list", action="store_true", help="Lista todas las ventanas visibles activas")
    parser.add_argument("--title", type=str, help="Título o expresión regular de la ventana a inspeccionar")
    parser.add_argument("--depth", type=int, default=3, help="Profundidad del árbol de controles (por defecto 3)")
    
    args = parser.parse_args()
    if args.list:
        list_windows()
    elif args.title:
        inspect_window_controls(args.title, args.depth)
    else:
        parser.print_help()
