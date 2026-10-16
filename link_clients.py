import sqlite3
import re

def link_unmatched():
    conn = sqlite3.connect("anyd_booking.db")
    c = conn.cursor()

    c.execute("SELECT id, fullname, email FROM clients WHERE email IS NOT NULL AND email != ''")
    clients = c.fetchall()

    c.execute("SELECT id, client_name, client_email FROM bonos WHERE client_email IS NULL")
    unmatched = c.fetchall()

    updated = 0
    for bid, bname, bemail in unmatched:
        b_clean = re.sub(r"[\-\/].*$", "", bname).strip().lower()
        b_parts = [p for p in b_clean.split() if len(p) > 2]
        
        best_match = None
        for cid, cfullname, cemail in clients:
            c_clean = (cfullname or "").lower()
            matches = sum(1 for p in b_parts if p in c_clean)
            if len(b_parts) >= 2 and matches >= 2:
                best_match = (cid, cemail)
                break
            elif len(b_parts) == 1 and b_parts[0] in c_clean:
                best_match = (cid, cemail)
                break
                
        if best_match:
            c.execute("UPDATE bonos SET client_id = ?, client_email = ? WHERE id = ?", (best_match[0], best_match[1], bid))
            updated += 1
            print(f"Emparejado: {bname} -> {best_match[1]}")

    conn.commit()
    print(f"Total adicionales asociados: {updated}")

    c.execute("SELECT COUNT(*) FROM bonos WHERE client_email IS NOT NULL")
    with_email = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bonos")
    total = c.fetchone()[0]
    print(f"Bonos con email asignado: {with_email} de {total}")
    conn.close()

if __name__ == "__main__":
    link_unmatched()
