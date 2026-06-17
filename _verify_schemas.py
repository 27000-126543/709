import ast
import glob
import sys

files = glob.glob('app/schemas/*.py')
all_ok = True
for f in sorted(files):
    try:
        with open(f, encoding='utf-8') as fh:
            ast.parse(fh.read())
        print(f'{f:50s} OK')
    except SyntaxError as e:
        print(f'{f:50s} ERROR: {e}')
        all_ok = False

if all_ok:
    print('\nAll schema files passed syntax check.')
    sys.exit(0)
else:
    print('\nSome schema files have syntax errors.')
    sys.exit(1)
