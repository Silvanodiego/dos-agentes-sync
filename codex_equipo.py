"""Planifica, ejecuta y revisa con dos perfiles Codex independientes."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import time
import uuid
from account_registry import role_homes


def ignore_copy(directory, names):
    ignored = set(shutil.ignore_patterns('.git', '.venv', 'node_modules', '__pycache__',
                  '.env', '.env.*', 'auth.json', '*.bak*')(directory, names))
    for name in names:
        p = pathlib.Path(directory) / name
        if p.is_symlink() or p.is_junction():
            ignored.add(name)
    return ignored

BASE = pathlib.Path(r'C:\dos_agentes_local')
CODEX = pathlib.Path.home() / 'AppData/Roaming/npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe'
AGY = pathlib.Path.home() / 'ScriptsGlobales/agy.bat'
HOMES = role_homes()


def account_fingerprint(home):
    auth = json.loads((home / 'auth.json').read_text(encoding='utf-8'))
    identity = auth.get('tokens', {}).get('account_id')
    if not identity:
        raise RuntimeError('Perfil sin account_id: ' + str(home))
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]


def audit_approved(receipt):
    # Un exit 0 o la ausencia de INCOMPLETO no son una aprobacion.
    patterns = (r'^\[ANTIGRAVITY:[^\]\r\n]+\]:\s*COMPLETO_100%\s*$',
                r'^\[PUENTE_8765\]:\s*COMPLETO_100%\s*$')
    return all(len(re.findall(p, receipt, re.MULTILINE)) == 1 for p in patterns) and not re.search(
        r'INCOMPLETO_FALTA|\bERROR\b', receipt)


def run_stage(job, name, profile, prompt, writable=False):
    output = job / (name + '.txt')
    # La CLI independiente no debe reutilizar el runtime/IPC del escritorio.
    env = {k: v for k, v in os.environ.items() if not k.startswith('CODEX_')}
    env['CODEX_HOME'] = str(HOMES[profile])
    env['CODEX_EQUIPO_CHILD'] = '1'
    command = [str(CODEX), 'exec', '--sandbox',
               'workspace-write' if writable else 'read-only',
               '--skip-git-repo-check', '--ephemeral', '-C', str(job / 'workspace'),
               '-o', str(output), '-']
    evidence = {'stage': name, 'profile': profile, 'account_fingerprint': account_fingerprint(HOMES[profile]),
                'started_at': time.time(), 'status': 'RUNNING', 'exit_code': None,
                'log': str(job / (name + '.log')), 'output': str(output)}
    evidence_path = job / (name + '.json')
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    try:
        with (job / (name + '.log')).open('w', encoding='utf-8') as log:
            result = subprocess.Popen(command, stdin=subprocess.PIPE, env=env, stdout=log,
                                      stderr=subprocess.STDOUT, text=True,
                                      encoding='utf-8', errors='replace')
            evidence['pid'] = result.pid
            evidence['process_started_at'] = time.time()
            evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            try:
                result.communicate(prompt, timeout=900)
            except subprocess.TimeoutExpired:
                result.kill()
                result.communicate()
                evidence['exit_code'] = result.returncode
                raise
        evidence['exit_code'] = result.returncode
        evidence['status'] = 'SUCCEEDED' if result.returncode == 0 and output.exists() else 'FAILED'
        if output.exists():
            evidence['output_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    except Exception as exc:
        evidence['status'] = 'FAILED'
        evidence['error'] = str(exc)
        raise
    finally:
        evidence['finished_at'] = time.time()
        evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print('CODEX_STAGE=' + json.dumps(evidence), flush=True)
    if result.returncode or not output.exists():
        raise RuntimeError(f'{name}: exit={result.returncode}; ver {job / (name + ".log")}')
    return output.read_text(encoding='utf-8').strip()


def audit(job, prompt, verify=False):
    command = [str(AGY)] + (['--verify'] if verify else [])
    result = subprocess.run(command, input=prompt, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=150,
                            cwd=str(job / 'workspace'))
    text = (result.stdout or '') + (result.stderr or '')
    (job / ('audit_verify.txt' if verify else 'audit_work.txt')).write_text(text, encoding='utf-8')
    print(text, flush=True)
    if result.returncode:
        raise RuntimeError(f'Auditoria: exit={result.returncode}')
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=pathlib.Path)
    parser.add_argument('--task', required=True)
    args = parser.parse_args()
    if not args.task.strip():
        parser.error('La tarea no puede estar vacia')
    project = args.project.resolve(strict=True)
    if not project.is_dir():
        parser.error('El proyecto debe ser una carpeta')
    identities = []
    for home in HOMES.values():
        auth = json.loads((home / 'auth.json').read_text(encoding='utf-8'))
        identities.append(auth.get('tokens', {}).get('account_id'))
    if not all(identities) or identities[0] == identities[1]:
        raise RuntimeError('Se requieren dos cuentas autenticadas distintas')
    job = BASE / 'codex_jobs' / (time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])
    if job.is_relative_to(project):
        raise RuntimeError('El proyecto no puede contener la carpeta de trabajos')
    job.mkdir(parents=True)
    state = {'project': str(project), 'task': args.task, 'status': 'RUNNING', 'job': str(job)}
    state_path = job / 'status.json'
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print('JOB=' + str(job), flush=True)
    try:
        shutil.copytree(project, job / 'workspace', ignore=ignore_copy)
        advice = audit(job, 'Planificar tarea autorizada en copia aislada: ' + args.task)
        context = ('Trabajas en una copia aislada. No modifiques el proyecto original ni accedas a credenciales. '
                   'No invoques agy, este orquestador ni otros Codex: la auditoria la gestiona el orquestador. No publiques ni despliegues. Tarea: ' + args.task)
        plan = run_stage(job, '01_plan', 'coordinador', context + '\nInspecciona los archivos relevantes y entrega un plan concreto. No edites.\nAuditoria:\n' + advice)
        work = run_stage(job, '02_execute', 'ejecutor', context + '\nImplementa y ejecuta pruebas apropiadas en esta copia. Informa evidencia y limitaciones.\nPlan:\n' + plan, True)
        review = run_stage(job, '03_review', 'coordinador', context + '\nRevisa los archivos reales y valida el resultado. No edites. Primera linea exactamente APROBADO o REQUIERE_CAMBIOS.\nPlan:\n' + plan + '\nEjecucion:\n' + work)
        approved = review.splitlines()[0].strip() == 'APROBADO'
        receipt = audit(job, 'Pedido: ' + args.task + '\nEjecucion real:\n' + work[:6000] + '\nRevision:\n' + review[:6000], True)
        state['status'] = 'REVIEWED' if approved and audit_approved(receipt) else 'REQUIRES_CHANGES'
        state['result'] = str(job / 'workspace')
        print('STATUS=' + state['status'], flush=True)
        print('RESULTADO=' + str(job / 'workspace'), flush=True)
    except Exception as exc:
        state['status'] = 'FAILED'
        state['error'] = str(exc)
        raise
    finally:
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if state['status'] == 'REVIEWED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
