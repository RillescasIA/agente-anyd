import openpyxl
import os
import shutil
from datetime import datetime
import threading

EXCEL_PATH = r"G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx"
BACKUP_DIR = r"g:\Mi unidad\1.- IA\IA Gemini\Agente anyd\backups"

excel_lock = threading.Lock()

def make_backup():
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"Bonos_activos_backup_{timestamp}.xlsx")
        shutil.copy2(EXCEL_PATH, backup_file)
        return backup_file
    except Exception as e:
        print(f"Error creando backup: {e}")
        return None

def add_purchase_to_excel(centro, nombre, tipo_bono, fecha_compra, n_pedido, importe, forma_pago, nutri="Román", num_sesiones=3):
    """
    Inserta una nueva compra en la hoja 'Bonos activos' de Excel.
    """
    with excel_lock:
        make_backup()
        wb = openpyxl.load_workbook(EXCEL_PATH)
        sheet = wb["Bonos activos"]

        # Buscar la primera fila vacía después de los encabezados (fila 2 en adelante)
        # En la hoja, las nuevas compras suelen añadirse al principio (fila 2) o al final.
        # Insertamos en la fila 2 para que quede como la compra más reciente
        sheet.insert_rows(2)

        sheet.cell(row=2, column=1, value=centro or "ANYD")
        sheet.cell(row=2, column=2, value=nombre)
        sheet.cell(row=2, column=3, value=tipo_bono)
        
        # Fecha en formato datetime o string
        if isinstance(fecha_compra, str):
            try:
                dt = datetime.strptime(fecha_compra[:10], "%Y-%m-%d")
                sheet.cell(row=2, column=4, value=dt)
            except:
                sheet.cell(row=2, column=4, value=fecha_compra)
        else:
            sheet.cell(row=2, column=4, value=fecha_compra or datetime.now())

        sheet.cell(row=2, column=5, value=str(n_pedido))
        sheet.cell(row=2, column=6, value=float(importe) if importe else 0.0)
        sheet.cell(row=2, column=7, value="Activo")
        sheet.cell(row=2, column=8, value=forma_pago or "Online")
        sheet.cell(row=2, column=9, value=nutri or "Román")

        # Celdas de consultas en blanco ' '
        for c in range(num_sesiones):
            sheet.cell(row=2, column=10 + c, value=" ")

        wb.save(EXCEL_PATH)
        wb.close()
        print(f"Compra registrada en Excel: {nombre} - {tipo_bono} (Pedido: {n_pedido})")
        return True

def record_consultation_in_excel(n_pedido=None, nombre=None, date_str=None, nutri="Román"):
    """
    Registra la asistencia 'Román DD/MM/AAAA' en la primera consulta disponible.
    Si se completan todas las consultas, traslada la fila a 'Bonos agotados'.
    """
    if not date_str:
        date_str = datetime.now().strftime("%d/%m/%Y")

    with excel_lock:
        make_backup()
        wb = openpyxl.load_workbook(EXCEL_PATH)
        sheet_activos = wb["Bonos activos"]
        sheet_agotados = wb["Bonos agotados"]

        target_row = None
        for r in range(2, sheet_activos.max_row + 1):
            cell_nombre = sheet_activos.cell(row=r, column=2).value
            cell_pedido = str(sheet_activos.cell(row=r, column=5).value or "").strip()

            if n_pedido and cell_pedido == str(n_pedido).strip():
                target_row = r
                break
            elif nombre and cell_nombre and (nombre.lower() in str(cell_nombre).lower() or str(cell_nombre).lower() in nombre.lower()):
                target_row = r
                break

        if not target_row:
            print(f"No se encontró el bono activo en Excel para: Pedido={n_pedido}, Nombre={nombre}")
            wb.close()
            return False

        # Determinar número de consultas según el tipo de bono
        tipo_bono = str(sheet_activos.cell(row=target_row, column=3).value or "").upper()
        if "3" in tipo_bono:
            max_sesiones = 3
        elif "5" in tipo_bono or "COMPET" in tipo_bono:
            max_sesiones = 5
        elif "6" in tipo_bono:
            max_sesiones = 6
        else:
            max_sesiones = 3

        # Buscar la primera consulta vacía
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
            # Copiar fila a 'Bonos agotados'
            row_values = [sheet_activos.cell(row=target_row, column=c).value for c in range(1, sheet_activos.max_column + 1)]
            sheet_agotados.insert_rows(2)
            for c_idx, val in enumerate(row_values):
                sheet_agotados.cell(row=2, column=c_idx + 1, value=val)

            # Eliminar de activos
            sheet_activos.delete_rows(target_row)
            print(f"Bono de {nombre or n_pedido} agotado (todas las {max_sesiones} consultas hechas). Movido a 'Bonos agotados'.")
        else:
            print(f"Consulta registrada para {nombre or n_pedido}: '{nutri} {date_str}'. Sesiones: {consultas_hechas}/{max_sesiones}")

        wb.save(EXCEL_PATH)
        wb.close()
        return True, is_exhausted
