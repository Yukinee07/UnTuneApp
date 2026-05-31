# Marker — makes backend/ml a package so `from ml.model import HSTasNetVocals`
# works.  Files in this folder are drop-in copies of Main_Code/*.py and stay
# importable both as `ml.foo` (when called from the backend) and as plain `foo`
# (when stream.py is run as a subprocess with `cwd=backend/ml/`).
