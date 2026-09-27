# Third-party notices — Star Tracker demo

This project re-implements published star-tracker algorithms and optionally loads
one public CNN checkpoint for centroiding. It does **not** vendor NASA NOSA-licensed
source. Algorithmic lineage:

| Source | License | What we inherit |
|---|---|---|
| [ESA tetra3](https://github.com/esa/tetra3) | Apache-2.0 | Sub-pixel centroiding procedure (local background, MAD noise, binary opening, area/axis-ratio gates, windowed CoG). Optional sample TIFFs for solver tests. |
| [UWCubeSat LOST](https://github.com/UWCubeSat/lost) | MIT | Mortari Pyramid identification, K-vector pair index (angle bins), false-match probability gate, remaining-star identification, synthetic-sky generation model. |
| [NASA COTS-Star-Tracker](https://github.com/nasa/COTS-Star-Tracker) (JSC) | NASA Open Source Agreement | Hipparcos → J2000 vectorization, Brown–Conrady calibration *procedure*, QUEST/SVD Wahba. **Re-implemented from the published math; NASA source is not copied.** |
| Yale Bright Star Catalogue 5th ed. (Hoffleit & Warren 1991), Harvard TDC binary `BSC5` | Catalogue data | On-disk prototype catalog (291 548 bytes). |
| IAU WGSN Catalog of Star Names | Catalogue data | Optional star-name overlay; attitude does not match on cultural constellation names. |
| [HongruiZhao/CNNStarDetectCentroid](https://github.com/HongruiZhao/CNNStarDetectCentroid) — Zhao et al., arXiv:2404.19108 | Research code + public weights | Optional MobileUNet checkpoint `MobileUNet_B10_50.pt` and architecture used for inference only (not retrained here). |

Do **not** cite `github.com/openst/openst` (spatial transcriptomics).
