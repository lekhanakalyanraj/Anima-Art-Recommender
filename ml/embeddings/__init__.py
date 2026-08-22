"""CLIP embeddings + FAISS retrieval for the world-art corpus.

torch and faiss each bundle their own OpenMP runtime; on macOS loading both in
one process segfaults (duplicate libomp). Set the guard here, before either is
imported, so every entrypoint under this package is protected.
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "4")
