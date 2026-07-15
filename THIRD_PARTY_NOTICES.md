# Third-Party Notices

Thermal-ChipletPart incorporates or interoperates with third-party software.
This summary is provided for convenience and does not replace the complete
license text shipped with each component or the terms supplied by its package
distributor. Upstream files and repositories are authoritative.

## Source included in this repository

### GKlib

- Location: `GKlib/` git submodule
- Upstream: <https://github.com/KarypisLab/GKlib>
- Stated license: Apache License 2.0
- Copyright notice: Copyright 1995-2018, Regents of the University of Minnesota
- Full text: `GKlib/LICENSE.txt`

### METIS

- Location: `METIS/` git submodule; a compatibility header is also present at
  `include/metis.h`
- Upstream: <https://github.com/KarypisLab/METIS>
- Stated license: Apache License 2.0
- Copyright notice: Copyright 1995-2013, Regents of the University of Minnesota
- Full text: `METIS/LICENSE`

### pugixml 1.14

- Location: `src/pugixml.cpp`, `src/pugixml.hpp`, and configuration headers
- Upstream: <https://pugixml.org/>
- Stated license: MIT License
- Copyright notice: Copyright 2006-2024, Arseny Kapoulkine
- The license notice is retained at the end of the vendored source and header.

### OpenMP support utility

- Location: `include/OpenMPSupport.h`
- Stated license: BSD 3-Clause License
- Copyright notice: Copyright 2023, The Regents of the University of California
- The complete notice is retained in the file.

## Environment-provided dependencies

Boost, Eigen, CMake, the compiler/OpenMP runtime, Python, NumPy, SciPy,
Matplotlib, and their transitive dependencies are installed from the configured
Conda channels rather than redistributed here. Their licenses are supplied by
their respective upstream projects and package distributions.

## Companion project

DeepOHeat is not vendored or included as a submodule. It is invoked as a
separate sibling project for real thermal inference. Its repository currently
states the MIT License; consult the license in the exact DeepOHeat checkout and
the terms of any model checkpoint or dataset used with it.
