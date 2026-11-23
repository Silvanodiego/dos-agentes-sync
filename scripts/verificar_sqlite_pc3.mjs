import { createRequire } from 'node:module';
const require = createRequire(process.argv[2]);
const Database = require('better-sqlite3');
const db = new Database(':memory:');
try {
  if (db.prepare('select 1 as ok').get().ok !== 1) throw new Error('Consulta SQLite incorrecta');
  console.log('context-mode / better-sqlite3: apertura y consulta SQLite OK');
} finally {
  db.close();
}
