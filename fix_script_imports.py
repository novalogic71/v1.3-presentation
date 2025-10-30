#!/usr/bin/env python3
"""
Fix script imports to work without PYTHONPATH
Adds automatic project root detection to all scripts
"""

import os
import re
from pathlib import Path

def fix_script_imports(script_path: Path):
    """Add project root path detection to a script"""

    # Read the file
    with open(script_path, 'r') as f:
        content = f.read()

    # Check if already fixed
    if 'sys.path.insert(0, str(project_root))' in content:
        print(f"✅ {script_path.name} - Already fixed")
        return

    # Pattern to find sync_analyzer imports
    sync_import_pattern = r'^from sync_analyzer\.'

    if not re.search(sync_import_pattern, content, re.MULTILINE):
        print(f"⏭️  {script_path.name} - No sync_analyzer imports")
        return

    # Find the import section
    lines = content.split('\n')

    # Find where to insert the path fix
    import_start = -1
    sys_imported = False
    pathlib_imported = False

    for i, line in enumerate(lines):
        if line.startswith('import sys'):
            sys_imported = True
        if line.startswith('from pathlib import') or line.startswith('import pathlib'):
            pathlib_imported = True
        if line.startswith('from sync_analyzer.') and import_start == -1:
            import_start = i
            break

    if import_start == -1:
        print(f"❌ {script_path.name} - Could not find sync_analyzer import")
        return

    # Build the path fix code
    path_fix_lines = []

    # Add missing imports if needed
    if not sys_imported:
        # Find where to add sys import
        for i, line in enumerate(lines):
            if line.startswith('import ') and not line.startswith('import sys'):
                lines.insert(i, 'import sys')
                import_start += 1
                break

    if not pathlib_imported:
        # Find where to add pathlib import
        for i, line in enumerate(lines):
            if line.startswith('from pathlib import'):
                break
            if line.startswith('import ') and 'pathlib' not in line:
                continue
        else:
            # Add pathlib import
            for i, line in enumerate(lines):
                if line.startswith('from pathlib import'):
                    break
                if line.startswith('import '):
                    continue
                if line.startswith('from ') and 'pathlib' not in line:
                    lines.insert(i, 'from pathlib import Path')
                    import_start += 1
                    break

    # Insert the path fix before sync_analyzer imports
    path_fix = [
        '',
        '# Add project root to Python path',
        'script_dir = Path(__file__).resolve().parent',
        'project_root = script_dir.parent.parent',
        'sys.path.insert(0, str(project_root))',
        ''
    ]

    # Insert the fix
    for j, fix_line in enumerate(path_fix):
        lines.insert(import_start + j, fix_line)

    # Write back to file
    with open(script_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"🔧 {script_path.name} - Fixed imports")

def main():
    """Fix all scripts in the scripts directory"""

    project_root = Path(__file__).parent
    scripts_dir = project_root / 'scripts'

    print("🔧 Fixing script imports to work without PYTHONPATH...")
    print(f"Project root: {project_root}")
    print(f"Scripts directory: {scripts_dir}")
    print()

    # Find all Python scripts
    script_files = []
    for root, dirs, files in os.walk(scripts_dir):
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                script_files.append(Path(root) / file)

    print(f"Found {len(script_files)} Python scripts to check:")
    print()

    # Fix each script
    for script_path in script_files:
        fix_script_imports(script_path)

    print()
    print("✅ All scripts processed!")
    print()
    print("Now you can run scripts directly without PYTHONPATH:")
    print("  python scripts/monitoring/continuous_sync_monitor.py file1.mov file2.mov")
    print("  python scripts/batch/csv_batch_processor.py batch.csv --output-dir results/")

if __name__ == '__main__':
    main()