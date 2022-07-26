#!/usr/bin/env python

import glob
import os
import shutil
import subprocess
import sys
import tempfile

def is_fs_case_sensitive():
  with tempfile.NamedTemporaryFile(prefix='TmP') as tmp_file:
    return(not os.path.exists(tmp_file.name.lower()))

sys.path.append(
  os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../.."))

from lib.config import PLATFORM, s3_config
from lib.util import get_electron_branding, execute, s3put, \
                     get_out_dir, ELECTRON_DIR

RELEASE_DIR = get_out_dir()


PROJECT_NAME = get_electron_branding()['project_name']
PRODUCT_NAME = get_electron_branding()['product_name']
SYMBOLS_DIR = os.path.join(RELEASE_DIR, 'breakpad_symbols')

PDB_LIST = [
  os.path.join(RELEASE_DIR, '{0}.exe.pdb'.format(PROJECT_NAME))
]

PDB_LIST += glob.glob(os.path.join(RELEASE_DIR, '*.dll.pdb'))

NPX_CMD = "npx"
if sys.platform == "win32":
    NPX_CMD += ".cmd"


def main():
  os.chdir(ELECTRON_DIR)
  files = []
  if PLATFORM == 'win32':
    for pdb in PDB_LIST:
      run_symstore(pdb, SYMBOLS_DIR, PRODUCT_NAME)
    files = glob.glob(SYMBOLS_DIR + '/*.pdb/*/*.pdb')

  files += glob.glob(SYMBOLS_DIR + '/*/*/*.sym')

  for symbol_file in files:
    print("Generating Sentry src bundle for: " + symbol_file)
    subprocess.check_output([
      NPX_CMD, '@sentry/cli@1.51.1', 'difutil', 'bundle-sources',
      symbol_file])

  files += glob.glob(SYMBOLS_DIR + '/*/*/*.src.zip')

  # The file upload needs to be atom-shell/symbols/:symbol_name/:hash/:symbol
  os.chdir(SYMBOLS_DIR)
  files = [os.path.relpath(f, os.getcwd()) for f in files]

  # The symbol server needs lowercase paths, it will fail otherwise
  # So lowercase all the file paths here
  if is_fs_case_sensitive():
    for f in files:
      lower_f = f.lower()
      if lower_f != f:
        if os.path.exists(lower_f):
          shutil.rmtree(lower_f)
        lower_dir = os.path.dirname(lower_f)
        if not os.path.exists(lower_dir):
          os.makedirs(lower_dir)
        shutil.copy2(f, lower_f)
  files = [f.lower() for f in files]
  for f in files:
    assert os.path.exists(f)

  bucket, access_key, secret_key = s3_config()
  upload_symbols(bucket, access_key, secret_key, files)


def run_symstore(pdb, dest, product):
  execute(['symstore', 'add', '/r', '/f', pdb, '/s', dest, '/t', product])


def upload_symbols(bucket, access_key, secret_key, files):
  s3put(bucket, access_key, secret_key, SYMBOLS_DIR, 'atom-shell/symbols',
        files)


if __name__ == '__main__':
  sys.exit(main())
