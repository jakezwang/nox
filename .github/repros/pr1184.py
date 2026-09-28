import ast
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

cases = [
    ('quotes', '''python -c "print('hello')"''', ['python', '-c', "print('hello')"]),
    ('path', r"python --path 'C:\new\test'", ['python', '--path', r'C:\new\test']),
    ('apostrophe', '''python --name "O'Reilly"''', ['python', '--name', "O'Reilly"]),
]
report = {'platform': platform.platform(), 'python': sys.version, 'tox': importlib.metadata.version('tox'), 'cases': []}
for kind in ('ini', 'toml', 'pyproject'):
    for name, command, expected in cases:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            if kind == 'ini':
                filename = 'tox.ini'
                content = '[tox]\nenv_list = lint\n[testenv:lint]\nbase_python = python\npackage = skip\ncommands = ' + command + '\n'
            else:
                filename = 'tox.toml' if kind == 'toml' else 'pyproject.toml'
                prefix = '' if kind == 'toml' else '[tool.tox]\n'
                section = '[env.lint]' if kind == 'toml' else '[tool.tox.env.lint]'
                content = prefix + 'env_list = ["lint"]\n' + section + '\nbase_python = ["python"]\npackage = "skip"\ncommands = [' + json.dumps(expected) + ']\n'
            (directory / filename).write_text(content, encoding='utf-8')
            results = {}
            for fmt in ('ini', 'json'):
                result = subprocess.run([sys.executable, '-m', 'tox', 'config', '--colored', 'no', '-c', filename, '-e', 'lint', '-k', 'commands', '--format', fmt], cwd=tmp, capture_output=True, text=True, check=True)
                results[fmt] = result.stdout
            subprocess.run(['tox-to-nox', '--output', 'noxfile.py'], cwd=tmp, check=True, capture_output=True, text=True)
            output = (directory / 'noxfile.py').read_text(encoding='utf-8')
            calls = [node for node in ast.walk(ast.parse(output)) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'run']
            args = [[ast.literal_eval(arg) for arg in call.args] for call in calls]
            assert args == [expected], (kind, name, args, expected)
            row = {'format': kind, 'case': name, 'filename': filename, 'input': content, 'tox_config': results, 'converted_args': args}
            report['cases'].append(row)
            print(json.dumps(row), flush=True)
Path('platform-output.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('All 9 configuration/command combinations preserved by the converter.')
