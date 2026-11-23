"""DDL sin datos ni credenciales, para una instalacion limpia."""
SCHEMAS = {'estado_puente.db': 'CREATE TABLE antigravity_accounts (slot TEXT PRIMARY KEY, account_id TEXT, '
                     'email TEXT, status TEXT, is_active INTEGER);\n'
                     'CREATE TABLE config_chats (proyecto TEXT PRIMARY KEY, url TEXT);\n'
                     'CREATE TABLE project_brain (\n'
                     '    project_name TEXT PRIMARY KEY,\n'
                     '    project_path TEXT,\n'
                     '    stack_rules TEXT NOT NULL,\n'
                     '    critical_paths TEXT NOT NULL,\n'
                     '    fingerprint TEXT,\n'
                     "    updated_at INTEGER DEFAULT (strftime('%s','now'))\n"
                     ');\n'
                     'CREATE TABLE extra_providers (\n'
                     '    id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
                     '    provider TEXT NOT NULL,\n'
                     '    label TEXT NOT NULL,\n'
                     '    api_key TEXT NOT NULL UNIQUE,\n'
                     '    base_url TEXT NOT NULL,\n'
                     '    model TEXT NOT NULL,\n'
                     "    status TEXT DEFAULT 'active',\n"
                     '    last_used INTEGER DEFAULT 0\n'
                     ');\n'
                     'CREATE TABLE factory_audit_log (\n'
                     '    id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
                     "    ts INTEGER DEFAULT (strftime('%s','now')),\n"
                     '    project TEXT,\n'
                     '    account_used TEXT,\n'
                     '    sec_review TEXT,\n'
                     '    arch_review TEXT,\n'
                     '    risk_level TEXT\n'
                     ');\n'
                     'CREATE TABLE factory_queue (\n'
                     '    id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
                     '    project TEXT NOT NULL,\n'
                     '    task_prompt TEXT NOT NULL,\n'
                     "    test_cmd TEXT DEFAULT '',\n"
                     "    status TEXT DEFAULT 'PENDING',\n"
                     "    risk_level TEXT DEFAULT 'UNKNOWN',\n"
                     '    attempts INTEGER DEFAULT 0,\n'
                     "    spec_and_audit TEXT DEFAULT '',\n"
                     "    last_output TEXT DEFAULT '',\n"
                     "    created_at INTEGER DEFAULT (strftime('%s','now')),\n"
                     "    updated_at INTEGER DEFAULT (strftime('%s','now'))\n"
                     ');',
 'memoria_reloj/estado_puente.db': 'CREATE TABLE salud_cuentas (\n'
                                   '        agente TEXT PRIMARY KEY, estado TEXT NOT NULL, exitos '
                                   'INTEGER DEFAULT 0,\n'
                                   '        fallos INTEGER DEFAULT 0, actualizado REAL, detalle '
                                   'TEXT);\n'
                                   'CREATE TABLE memoria_corridas (\n'
                                   '        id INTEGER PRIMARY KEY, ejecucion TEXT, tarea TEXT, '
                                   'runIndex INTEGER CHECK(runIndex BETWEEN 1 AND 5),\n'
                                   '        agente TEXT, resultado TEXT, detalle TEXT, fecha '
                                   'REAL);\n'
                                   'CREATE TABLE reglas_permanentes(id INTEGER PRIMARY KEY, regla '
                                   'TEXT NOT NULL, activa INTEGER NOT NULL DEFAULT 1);\n'
                                   'CREATE TABLE uso_motores(id INTEGER PRIMARY KEY, motor TEXT '
                                   'NOT NULL, motivo TEXT NOT NULL, inicio REAL, duracion REAL, '
                                   'estado TEXT, detalle TEXT);\n'
                                   'CREATE TABLE puente_intentos(fecha REAL,codigo INTEGER,stdout '
                                   'TEXT,stderr TEXT);\n'
                                   'CREATE TABLE cooldown_familias (cuenta TEXT, familia TEXT, '
                                   'cooldown_until REAL NOT NULL, detalle TEXT, actualizado REAL, '
                                   'PRIMARY KEY(cuenta,familia));\n'
                                   'CREATE TABLE incidentes_globales (id INTEGER PRIMARY KEY '
                                   'AUTOINCREMENT,error_hash TEXT NOT NULL UNIQUE,script TEXT NOT '
                                   'NULL,traceback TEXT NOT NULL,status TEXT NOT NULL DEFAULT '
                                   "'new',attempts INTEGER NOT NULL DEFAULT 0,created TEXT NOT "
                                   'NULL,updated TEXT NOT NULL,detail TEXT);\n'
                                   'CREATE TABLE guardian_offsets (source TEXT PRIMARY KEY,offset '
                                   'INTEGER NOT NULL,size INTEGER NOT NULL,updated TEXT NOT NULL);'}
