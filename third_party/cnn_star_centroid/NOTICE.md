# CNN star detection / centroiding (Zhao et al., arXiv:2404.19108)

Public pretrained MobileUNet weights and architecture from:
https://github.com/HongruiZhao/CNNStarDetectCentroid (branch development)

Full upstream clone (all tracked branches; do not delete):
`third_party/CNNStarDetectCentroid_upstream`
Upstream URL: https://github.com/HongruiZhao/CNNStarDetectCentroid

Files in this partial vendor tree:
- saved_models/MobileUNet_B10_50.pt — authors' released checkpoint (not retrained here)
- mobile_unet.py — architecture needed to deserialize that checkpoint

Cite: Zhao, H., Lembeck, M. F., Zhuang, A., Shah, R., & Wei, J. (2024).
Real-Time Convolutional Neural Network-Based Star Detection and Centroiding
Method for CubeSat Star Tracker. arXiv:2404.19108.
