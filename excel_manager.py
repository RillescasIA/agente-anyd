# -*- coding: utf-8 -*-
import openpyxl
import os
import shutil
from datetime import datetime
import threading

EXCEL_PATH = os.environ.get("EXCEL_PATH", r"G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx")
BACKUP_DIR = os.environ.get("BACKUP_DIR", r"G:\Mi unidad\1.- IA\IA Gemini\Agente anyd\backups")

excel_lock = threading.Lock()

def determine_num_sessions(tipo_bono):
    """Calcula las sesiones de consulta según el tipo de bono. Nutrición y Competición = 4 sesiones."""
    tipo = str(tipo_bono or "").upper()
    if "COMPET" in tipo or "COMPETIC" in tipo:
        return 4
    elif "6" in tipo:
        return 6
    elif "5" in tipo:
        return 5
    elif "4" in tipo:
        return 4
    elif "3" in tipo or "TRIMESTR" in tipo:
        return 3
    elif any(k in tipo for k in ["SUELTA", "INDIVIDUAL", "REVISION", "REVISIÓN", "1", "MENSUAL", "SEGUIMIENTO"]):
        return 1
    return 3

def make_backup():
    try:
        if not os.path.exists(EXCEL_PATH):
            return None
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"Bonos_activos_backup_{timestamp}.xlsx")
        shutil.copy2(EXCEL_PATH, backup_file)
        return backup_file
    except Exception as e:
        print(f"Error creando backup: {e}")
        return None

def delete_purchase_from_excel(n_pedido):
    """
    Elimina la fila del pedido indicado en la hoja 'Bonos activos' o 'Bonos agotados'.
    Retorna True si se borró, False si no se encontró o el archivo está bloqueado/no disponible.
    """
    if not n_pedido or not os.path.exists(EXCEL_PATH):
        return False
    with excel_lock:
        make_backup()
        wb = None
        try:
            wb = openpyxl.load_workbook(EXCEL_PATH)
            deleted = False
            for sheet_name in ["Bonos activos", "Bonos agotados"]:
                if sheet_name not in wb.sheetnames:
                    continue
                sh = wb[sheet_name]
                for r in range(sh.max_row, 1, -1):
                    if str(sh.cell(row=r, column=5).value or "").strip() == str(n_pedido).strip():
                        sh.delete_rows(r)
                        deleted = True
            if deleted:
                wb.save(EXCEL_PATH)
            return deleted
        except PermissionError as e:
            print(f"[EXCEL BLOQUEADO] No se pudo borrar #{n_pedido} porque Excel está abierto: {e}")
            return False
        except Exception as e:
            print(f"[EXCEL ERROR] Error en delete_purchase_from_excel: {e}")
            return False
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass

def add_purchase_to_excel(centro, nombre, tipo_bono, fecha_compra, n_pedido, importe, forma_pago, nutri="Román", num_sesiones=None):
    """
    Inserta una nueva compra en la hoja 'Bonos activos' de Excel
    y crea las celdas de consultas en blanco (' ') según el tipo de bono.
    Maneja PermissionError de forma segura si el archivo está abierto en Excel.
    """
    if not os.path.exists(EXCEL_PATH):
        print(f"[AVISO EXCEL] Archivo '{EXCEL_PATH}' no encontrado en este entorno. Se omite escritura en disco.")
        return False

    if not num_sesiones:
        num_sesiones = determine_num_sessions(tipo_bono)

    with excel_lock:
        make_backup()
        wb = None
        try:
            wb = openpyxl.load_workbook(EXCEL_PATH)
            sheet = wb["Bonos activos"]

            if not sheet.cell(row=1, column=14).value:
                sheet.cell(row=1, column=14, value="Consulta 5")
            if not sheet.cell(row=1, column=15).value:
                sheet.cell(row=1, column=15, value="Consulta 6")

            # Comprobar idempotencia: si ya existe el n_pedido en Bonos activos, no duplicar fila
            if n_pedido and str(n_pedido).strip() not in ["", "--"]:
                for r in range(2, sheet.max_row + 1):
                    if str(sheet.cell(row=r, column=5).value or "").strip() == str(n_pedido).strip():
                        return True

            sheet.insert_rows(2)
            sheet.cell(row=2, column=1, value=centro or "ANYD")
            sheet.cell(row=2, column=2, value=nombre)
            sheet.cell(row=2, column=3, value=tipo_bono)

            if isinstance(fecha_compra, str):
                try:
                    dt = datetime.strptime(fecha_compra[:10], "%Y-%m-%d")
                    sheet.cell(row=2, column=4, value=dt)
                except Exception:
                    sheet.cell(row=2, column=4, value=fecha_compra)
            else:
                sheet.cell(row=2, column=4, value=fecha_compra or datetime.now())

            sheet.cell(row=2, column=5, value=str(n_pedido))
            sheet.cell(row=2, column=6, value=float(importe) if importe else 0.0)
            sheet.cell(row=2, column=7, value="Activo")
            sheet.cell(row=2, column=8, value=forma_pago or "Online")
            sheet.cell(row=2, column=9, value=nutri or "Román")

            for c in range(num_sesiones):
                sheet.cell(row=2, column=10 + c, value=" ")

            wb.save(EXCEL_PATH)
            print(f"[EXCEL OK] Compra registrada en Excel: {nombre} - {tipo_bono} (Pedido: {n_pedido}) -> {num_sesiones} celdas creadas.")
            return True
        except PermissionError as e:
            print(f"[EXCEL BLOQUEADO] No se pudo añadir pedido #{n_pedido} (archivo abierto en Excel): {e}")
            return False
        except Exception as e:
            print(f"[EXCEL ERROR] Error en add_purchase_to_excel: {e}")
            return False
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass

def record_consultation_in_excel(n_pedido=None, nombre=None, date_str=None, nutri="Román"):
    """
    Registra la asistencia 'Román DD/MM/AAAA' en la primera consulta disponible.
    Si se completan todas las consultas, traslada la fila a 'Bonos agotados'.
    Maneja PermissionError de forma segura si el archivo está abierto.
    """
    if not os.path.exists(EXCEL_PATH):
        print(f"[AVISO EXCEL] Archivo '{EXCEL_PATH}' no encontrado en este entorno. Se omite firma de consulta.")
        return False, False

    if not date_str:
        date_str = datetime.now().strftime("%d/%m/%Y")

    with excel_lock:
        make_backup()
        wb = None
        try:
            wb = openpyxl.load_workbook(EXCEL_PATH)
            sheet_activos = wb["Bonos activos"]
            sheet_agotados = wb["Bonos agotados"]

            target_row = None
            clean_pedido = str(n_pedido or "").strip()
            clean_nombre = str(nombre or "").strip().lower()

            # 1. Buscar primero por número de pedido exacto (si no es MANUAL_ ni vacío)
            if clean_pedido and not clean_pedido.startswith("MANUAL_") and clean_pedido != "--":
                for r in range(2, sheet_activos.max_row + 1):
                    cell_pedido = str(sheet_activos.cell(row=r, column=5).value or "").strip()
                    if cell_pedido == clean_pedido:
                        target_row = r
                        break

            # 2. Fallback por coincidencia exacta de nombre completo
            if not target_row and clean_nombre:
                for r in range(2, sheet_activos.max_row + 1):
                    cell_nombre = str(sheet_activos.cell(row=r, column=2).value or "").strip().lower()
                    if cell_nombre and cell_nombre == clean_nombre:
                        target_row = r
                        break

            # 3. Fallback por subcadena de nombre (solo si el nombre tiene >= 6 caracteres)
            if not target_row and len(clean_nombre) >= 6:
                for r in range(2, sheet_activos.max_row + 1):
                    cell_nombre = str(sheet_activos.cell(row=r, column=2).value or "").strip().lower()
                    if cell_nombre and len(cell_nombre) >= 6 and (clean_nombre in cell_nombre or cell_nombre in clean_nombre):
                        target_row = r
                        break

            if not target_row:
                print(f"[EXCEL] No se encontró el bono activo en Excel para: Pedido={n_pedido}, Nombre={nombre}")
                return False, False

            tipo_bono = str(sheet_activos.cell(row=target_row, column=3).value or "").upper()
            max_sesiones = determine_num_sessions(tipo_bono)

            assigned = False
            consultas_hechas = 0
            for i in range(max_sesiones):
                col = 10 + i
                val = sheet_activos.cell(row=target_row, column=col).value
                if val and str(val).strip():
                    consultas_hechas += 1
                elif not assigned:
                    sheet_activos.cell(row=target_row, column=col, value=f"{nutri} {date_str}")
                    assigned = True
                    consultas_hechas += 1

            is_exhausted = (consultas_hechas >= max_sesiones)

            if is_exhausted:
                sheet_activos.cell(row=target_row, column=7, value="Agotado")
                row_values = [sheet_activos.cell(row=target_row, column=c).value for c in range(1, max(16, sheet_activos.max_column + 1))]
                sheet_agotados.insert_rows(2)
                for c_idx, val in enumerate(row_values):
                    sheet_agotados.cell(row=2, column=c_idx + 1, value=val)
                sheet_activos.delete_rows(target_row)
                print(f"[EXCEL OK] Bono de {nombre or n_pedido} agotado ({max_sesiones}/{max_sesiones}). Movido a 'Bonos agotados'.")
            else:
                print(f"[EXCEL OK] Consulta registrada para {nombre or n_pedido}: '{nutri} {date_str}'. Sesiones: {consultas_hechas}/{max_sesiones}")

            wb.save(EXCEL_PATH)
            return True, is_exhausted
        except PermissionError as e:
            print(f"[EXCEL BLOQUEADO] No se pudo firmar consulta en Excel (archivo abierto): {e}")
            return False, False
        except Exception as e:
            print(f"[EXCEL ERROR] Error en record_consultation_in_excel: {e}")
            return False, False
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass

def update_bono_in_excel(old_order_id, new_order_id, client_name, tipo_bono, price, forma_pago, centro, used_sessions, total_sessions, nutri="Román"):
    """
    Sincroniza cambios manuales de un bono (edición de pedido, importe, sesiones consumidas)
    con la fila correspondiente en 'Bonos activos'.
    """
    if not os.path.exists(EXCEL_PATH):
        return False

    with excel_lock:
        make_backup()
        wb = None
        try:
            wb = openpyxl.load_workbook(EXCEL_PATH)
            if "Bonos activos" not in wb.sheetnames:
                return False
            sheet = wb["Bonos activos"]
            target_row = None

            for candidate_id in [str(old_order_id or "").strip(), str(new_order_id or "").strip()]:
                if candidate_id and not candidate_id.startswith("MANUAL_") and candidate_id != "--":
                    for r in range(2, sheet.max_row + 1):
                        if str(sheet.cell(row=r, column=5).value or "").strip() == candidate_id:
                            target_row = r
                            break
                if target_row:
                    break

            if not target_row and client_name:
                cname_l = client_name.strip().lower()
                for r in range(2, sheet.max_row + 1):
                    cell_n = str(sheet.cell(row=r, column=2).value or "").strip().lower()
                    if cell_n == cname_l:
                        target_row = r
                        break

            if not target_row:
                return False

            sheet.cell(row=target_row, column=1, value=centro or "ANYD")
            sheet.cell(row=target_row, column=2, value=client_name)
            sheet.cell(row=target_row, column=3, value=tipo_bono)
            sheet.cell(row=target_row, column=5, value=str(new_order_id))
            sheet.cell(row=target_row, column=6, value=float(price or 0.0))
            sheet.cell(row=target_row, column=8, value=forma_pago or "Online")

            # Ajustar casillas de consultas (columnas 10 a 15) según used_sessions
            today_str = datetime.now().strftime("%d/%m/%Y")
            for i in range(6):
                col = 10 + i
                curr_val = str(sheet.cell(row=target_row, column=col).value or "").strip()
                if i < used_sessions:
                    if not curr_val:
                        sheet.cell(row=target_row, column=col, value=f"{nutri} {today_str}")
                elif i < total_sessions:
                    sheet.cell(row=target_row, column=col, value=" ")
                else:
                    sheet.cell(row=target_row, column=col, value=None)

            wb.save(EXCEL_PATH)
            return True
        except PermissionError as e:
            print(f"[EXCEL BLOQUEADO] No se pudo editar bono #{new_order_id} en Excel: {e}")
            return False
        except Exception as e:
            print(f"[EXCEL ERROR] Error en update_bono_in_excel: {e}")
            return False
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass
