# -*- coding: utf-8 -*-
"""
desktop_action.py
Motor de acciones atómicas de escritorio híbrido (pywinauto UIA/Win32 + PyAutoGUI fallback).
Uso:
  python desktop_action.py --launch "C:\SuiteBiológica11\DietaWin.exe"
  python desktop_action.py --focus "Dietowin"
  python desktop_action.py --click-btn "Aceptar" --window "Dietowin"
  python desktop_action.py --type "Carol Escolar" --control "Buscar" --window "Dietowin"
  python desktop_action.py --hotkey ctrl s
  python desktop_action.py --screenshot "captura_pantalla.png"
"""

import os
import sys
import time
import argparse
import pyautogui
from pywinauto import Application, Desktop

# Ajustes de seguridad PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

def launch_app(path: str, backend: str = "uia"):
    print(f"Lanzando aplicación: {path} (backend: {backend})...")
    try:
        app = Application(backend=backend).start(path)
        print("✓ Aplicación iniciada con éxito.")
        return app
    except Exception as e:
        print(f"Error iniciando aplicación: {e}")
        return None

def focus_window(window_title: str):
    print(f"Enfocando ventana: '{window_title}'...")
    try:
        desktop = Desktop(backend="uia")
        w = desktop.window(title_re=f".*{window_title}.*")
        w.set_focus()
        print("✓ Ventana enfocada.")
        return True
    except Exception as e:
        try:
            w32 = Desktop(backend="win32").window(title_re=f".*{window_title}.*")
            w32.set_focus()
            print("✓ Ventana enfocada con Win32.")
            return True
        except Exception as e2:
            print(f"Error enfocando ventana: {e2}")
            return False

def click_button(window_title: str, button_text: str):
    print(f"Haciendo clic en botón '{button_text}' de ventana '{window_title}'...")
    try:
        desktop = Desktop(backend="uia")
        w = desktop.window(title_re=f".*{window_title}.*")
        btn = w.child_window(title=button_text, control_type="Button")
        btn.wait('enabled', timeout=5)
        btn.click()
        print("✓ Botón pulsado mediante UIA.")
        return True
    except Exception as e:
        print(f"UIA click falló ({e}). Intentando con Win32 o coordenadas...")
        try:
            w32 = Desktop(backend="win32").window(title_re=f".*{window_title}.*")
            btn32 = w32.child_window(title=button_text)
            btn32.click()
            print("✓ Botón pulsado mediante Win32.")
            return True
        except Exception as e2:
            print(f"Win32 falló ({e2}). Recurriendo a clic visual...")
            try:
                loc = pyautogui.locateOnScreen(button_text)
                if loc:
                    pyautogui.click(loc)
                    print("✓ Clic por coincidencia de imagen exitoso.")
                    return True
            except Exception:
                pass
            print("✗ No se pudo pulsar el botón.")
            return False

def type_into_control(window_title: str, control_name: str, text: str):
    print(f"Escribiendo '{text}' en control '{control_name}' de '{window_title}'...")
    try:
        desktop = Desktop(backend="uia")
        w = desktop.window(title_re=f".*{window_title}.*")
        ctrl = w.child_window(title_re=f".*{control_name}.*", control_type="Edit")
        ctrl.set_focus()
        ctrl.type_keys(text, with_spaces=True)
        print("✓ Texto introducido mediante UIA.")
        return True
    except Exception as e:
        print(f"UIA falló: {e}. Escribiendo vía PyAutoGUI...")
        focus_window(window_title)
        time.sleep(0.2)
        pyautogui.write(text, interval=0.03)
        return True

def take_screenshot(output_path: str):
    print(f"Tomando captura de pantalla en: {output_path}...")
    try:
        img = pyautogui.screenshot()
        img.save(output_path)
        print(f"✓ Captura guardada ({img.width}x{img.height}).")
        return True
    except Exception as e:
        print(f"Error tomando captura: {e}")
        return False

def send_hotkey(keys):
    print(f"Enviando combinación de teclas: {keys}...")
    try:
        pyautogui.hotkey(*keys)
        print("✓ Teclas enviadas.")
        return True
    except Exception as e:
        print(f"Error enviando hotkey: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Acciones de automatización de escritorio")
    parser.add_argument("--launch", type=str, help="Ruta del ejecutable a iniciar")
    parser.add_argument("--focus", type=str, help="Título de ventana a enfocar")
    parser.add_argument("--window", type=str, help="Título de la ventana objetivo")
    parser.add_argument("--click-btn", type=str, help="Texto del botón a pulsar")
    parser.add_argument("--type", type=str, help="Texto a escribir")
    parser.add_argument("--control", type=str, help="Nombre del control de texto")
    parser.add_argument("--screenshot", type=str, help="Ruta donde guardar captura de pantalla")
    parser.add_argument("--hotkey", nargs="+", help="Teclas a pulsar en combinación (ej: ctrl s)")
    
    args = parser.parse_args()
    if args.launch:
        launch_app(args.launch)
    elif args.focus:
        focus_window(args.focus)
    elif args.click_btn and args.window:
        click_button(args.window, args.click_btn)
    elif args.type and args.window:
        type_into_control(args.window, args.control or "", args.type)
    elif args.screenshot:
        take_screenshot(args.screenshot)
    elif args.hotkey:
        send_hotkey(args.hotkey)
    else:
        parser.print_help()
