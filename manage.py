#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
internal_lib_path = os.path.join(base_dir, '.internal_lib')
if os.path.exists(internal_lib_path):
    sys.path.insert(0, internal_lib_path)

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CEWWproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
