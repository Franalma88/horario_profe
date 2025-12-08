import csv
import webbrowser
from collections import defaultdict

# ==============================
# 1. Dominios de tiempo (fijos)
# ==============================

days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

# Bloques de 2 horas
hours = ["8-10", "10-12", "16-18", "18-20"]

time_slots = [(d, h) for d in days for h in hours]

# Relación de bloque anterior (dentro de mañana y dentro de tarde)
previous_hour = {
    "10-12": "8-10",
    "8-10":  None,
    "18-20": "16-18",
    "16-18": None
}

# ==============================
# 2. Cargar datos desde CSV
# ==============================

def load_single_column_csv(filename, fieldname):
    values = []
    with open(filename, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            values.append(row[fieldname])
    return values

# Profes, grupos y aulas
teachers = load_single_column_csv("teachers.csv", "teacher")
groups   = load_single_column_csv("groups.csv",   "group")
rooms    = load_single_column_csv("rooms.csv",    "room")

# Clases: group, subject, teacher, blocks
classes = []
with open("classes.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        classes.append({
            "group":   row["group"],
            "subject": row["subject"],
            "teacher": row["teacher"],
            "blocks":  int(row["blocks"])
        })

# Restricciones de profes: profesor, day, hour
teacher_forbidden = set()  # (teacher, day, hour)
with open("restricciones_profes.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        teacher = row["profesor"]
        day     = row["day"]
        hour    = row["hour"]
        teacher_forbidden.add((teacher, day, hour))

# ==============================
# 3. Expandir clases a sesiones (cada sesión = 1 bloque de 2h)
# ==============================

sessions = []
for c in classes:
    for _ in range(c["blocks"]):
        sessions.append({
            "group":   c["group"],
            "subject": c["subject"],
            "teacher": c["teacher"]
        })

# Heurística simple: ordenar sesiones
sessions.sort(key=lambda s: (s["teacher"], s["group"], s["subject"]))

# ==============================
# 4. Estructuras de estado
# ==============================

busy_teacher = defaultdict(set)         # (day, hour) -> {teachers}
busy_group   = defaultdict(set)         # (day, hour) -> {groups}
busy_room    = defaultdict(set)         # (day, hour) -> {rooms}

teacher_blocks_per_day = defaultdict(int)  # (teacher, day) -> bloques asignados
tg_pairs = defaultdict(set)                # (day, hour) -> {(teacher, group)}

timetable = []  # resultado


# ==============================
# 5. Función de validez
# ==============================

def is_valid(session, slot, room):
    group   = session["group"]
    teacher = session["teacher"]
    day, hour = slot

    # 0) Profesor NO disponible según CSV
    if (teacher, day, hour) in teacher_forbidden:
        return False

    # 1) Máximo 4 horas/día -> 2 bloques por día
    if teacher_blocks_per_day[(teacher, day)] >= 2:
        return False

    key = (day, hour)

    # 2) Sin solapes
    if teacher in busy_teacher[key]:
        return False
    if group in busy_group[key]:
        return False
    if room in busy_room[key]:
        return False

    # 3) No permitir dos bloques consecutivos al mismo grupo con el mismo profesor
    prev = previous_hour.get(hour)
    if prev is not None:
        if (teacher, group) in tg_pairs[(day, prev)]:
            # Ya tenía el bloque anterior con ese grupo -> serían 4h seguidas
            return False

    return True


# ==============================
# 6. Backtracking
# ==============================

def backtrack(i):
    if i == len(sessions):
        return True

    session = sessions[i]

    for slot in time_slots:
        day, hour = slot
        for room in rooms:
            if is_valid(session, slot, room):
                key = (day, hour)
                teacher = session["teacher"]
                group   = session["group"]

                # Hacer movimiento
                busy_teacher[key].add(teacher)
                busy_group[key].add(group)
                busy_room[key].add(room)
                teacher_blocks_per_day[(teacher, day)] += 1
                tg_pairs[key].add((teacher, group))

                timetable.append({
                    "group": group,
                    "subject": session["subject"],
                    "teacher": teacher,
                    "day": day,
                    "hour": hour,
                    "room": room
                })

                if backtrack(i + 1):
                    return True

                # Deshacer
                timetable.pop()
                busy_teacher[key].remove(teacher)
                busy_group[key].remove(group)
                busy_room[key].remove(room)
                teacher_blocks_per_day[(teacher, day)] -= 1
                tg_pairs[key].remove((teacher, group))

    return False



# =============================
# 8. Codigo pasar a HTML
# ============================= 
def export_to_html(timetable, filename="horario.html"):
    """
    Genera un archivo HTML con un horario por grupo.
    Filas = bloques horarios, columnas = días.
    """
    # Agrupar por grupo
    by_group = {}
    for entry in timetable:
        g = entry["group"]
        by_group.setdefault(g, []).append(entry)

    # Empezar HTML
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html lang='es'>")
    html.append("<head>")
    html.append("<meta charset='UTF-8'>")
    html.append("<title>Horario generado</title>")
    # CSS sencillo
    html.append("""
    <style>
      body { font-family: Arial, sans-serif; padding: 20px; }
      h2 { margin-top: 40px; }
      table { border-collapse: collapse; margin-bottom: 30px; }
      th, td { border: 1px solid #555; padding: 6px 10px; text-align: center; }
      th { background-color: #eee; }
      .empty { background-color: #f9f9f9; color: #bbb; }
    </style>
    """)
    html.append("</head>")
    html.append("<body>")
    html.append("<h1>Horario generado</h1>")

    # Para cada grupo, construimos una tabla
    for group, entries in by_group.items():
        html.append(f"<h2>Grupo {group}</h2>")
        html.append("<table>")
        # Cabecera de días
        html.append("<tr>")
        html.append("<th>Bloque</th>")
        for d in days:
            html.append(f"<th>{d}</th>")
        html.append("</tr>")

        # Mapa (day, hour) -> texto
        cell = {(e["day"], e["hour"]): e for e in entries}

        # Filas por bloque horario
        for h in hours:
            html.append("<tr>")
            html.append(f"<th>{h}</th>")
            for d in days:
                e = cell.get((d, h))
                if e is None:
                    html.append("<td class='empty'>-</td>")
                else:
                    # mostramos asignatura, profesor y aula
                    html.append(
                        "<td>"
                        f"{e['subject']}<br>"
                        f"<small>{e['teacher']} - {e['room']}</small>"
                        "</td>"
                    )
            html.append("</tr>")

        html.append("</table>")

    html.append("</body></html>")

    # Escribir a archivo
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(html))

    print(f"\nArchivo HTML generado: {filename}")




# ==============================
# 7. Ejecutar y mostrar
# ==============================

if backtrack(0):
    timetable_sorted = sorted(
        timetable,
        key=lambda x: (days.index(x["day"]), hours.index(x["hour"]), x["room"])
    )

    print("HORARIO GENERADO:\n")
    for entry in timetable_sorted:
        print(f'{entry["day"]:10} {entry["hour"]:6} | {entry["room"]:7} | '
              f'{entry["group"]:7} - {entry["subject"]:15} ({entry["teacher"]})')
    # Exportar a HTML
    export_to_html(timetable_sorted, "horario.html")  
    # Abrir en navegador
    webbrowser.open("horario.html")
else:
    print("No se ha encontrado un horario válido con las restricciones dadas.")


