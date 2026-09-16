"""Build the category PDF using the original compact document style."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('build-compact-category-pdf.py')), run_name='__main__')
