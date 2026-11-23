"""Living Origin Cards: batch generative media on serverless GPUs.

The package is split so that the parts that need a GPU stay out of the parts
that do not:

- :mod:`mediagen.specs`   pinned models, GPU platforms and run settings
- :mod:`mediagen.records` the ten origin records and the prompts built from them
- :mod:`mediagen.metrics` the run metrics schema and provenance handling
- :mod:`mediagen.costs`   the fixed and marginal cost model
- :mod:`mediagen.worker`  the GPU worker that runs inside a Nebius Serverless AI Job
- :mod:`mediagen.cli`     the command line entry point
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
