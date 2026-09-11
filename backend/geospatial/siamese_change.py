"""Siamese Neural Network for Bi-temporal Remote Sensing Change Detection (FR-5).

Implements a Siamese convolutional network for detecting changes between two
co-registered satellite rasters (T1, T2).
Features extracted by a shared multi-scale encoder are compared via absolute difference
and fused through decoder blocks to generate a pixel-wise change probability map.
"""
from __future__ import annotations

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:
    torch = None
    nn = None
    F = None


if torch is not None:
    class ConvBlock(nn.Module):
        def __init__(self, in_c: int, out_c: int):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(out_c),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_c, out_c, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(out_c),
                nn.ReLU(inplace=True),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.conv(x)

    class SiameseChangeNet(nn.Module):
        """Siamese Change Detection Network with multi-scale feature differencing."""

        def __init__(self, in_channels: int = 4, base_channels: int = 32):
            super().__init__()
            # Shared Siamese Encoder
            self.enc1 = ConvBlock(in_channels, base_channels)
            self.enc2 = ConvBlock(base_channels, base_channels * 2)
            self.enc3 = ConvBlock(base_channels * 2, base_channels * 4)

            self.pool = nn.MaxPool2d(2, 2)

            # Difference Fusion & Decoder
            self.diff_conv3 = ConvBlock(base_channels * 4, base_channels * 4)
            self.up2 = nn.ConvTranspose2d(base_channels * 4, base_channels * 2, kernel_size=2, stride=2)
            self.dec2 = ConvBlock(base_channels * 4, base_channels * 2)

            self.up1 = nn.ConvTranspose2d(base_channels * 2, base_channels, kernel_size=2, stride=2)
            self.dec1 = ConvBlock(base_channels * 2, base_channels)

            self.classifier = nn.Sequential(
                nn.Conv2d(base_channels, 1, kernel_size=1),
                nn.Sigmoid()
            )

        def forward(self, t1: torch.Tensor, t2: torch.Tensor) -> torch.Tensor:
            """
            Args:
                t1: (B, C, H, W) earlier raster
                t2: (B, C, H, W) later raster (co-registered)
            Returns:
                change_prob: (B, 1, H, W) probability map in [0, 1]
            """
            # Siamese branch 1
            e1_1 = self.enc1(t1)
            e2_1 = self.enc2(self.pool(e1_1))
            e3_1 = self.enc3(self.pool(e2_1))

            # Siamese branch 2 (shared weights)
            e1_2 = self.enc1(t2)
            e2_2 = self.enc2(self.pool(e1_2))
            e3_2 = self.enc3(self.pool(e2_2))

            # Multi-scale feature differences
            d3 = torch.abs(e3_1 - e3_2)
            d2 = torch.abs(e2_1 - e2_2)
            d1 = torch.abs(e1_1 - e1_2)

            # Decoder
            x = self.diff_conv3(d3)
            x = self.up2(x)
            if x.shape[-2:] != d2.shape[-2:]:
                x = F.interpolate(x, size=d2.shape[-2:], mode="bilinear", align_corners=False)
            x = self.dec2(torch.cat([x, d2], dim=1))

            x = self.up1(x)
            if x.shape[-2:] != d1.shape[-2:]:
                x = F.interpolate(x, size=d1.shape[-2:], mode="bilinear", align_corners=False)
            x = self.dec1(torch.cat([x, d1], dim=1))

            return self.classifier(x)
else:
    class SiameseChangeNet:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyTorch is required for SiameseChangeNet")


def predict_siamese_change(
    model: nn.Module,
    arr_before: np.ndarray,
    arr_after: np.ndarray,
    device: str = "cpu",
    threshold: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Run neural change detection inference on bi-temporal raster arrays.

    Args:
        model: SiameseChangeNet instance in eval mode
        arr_before: (C, H, W) float32 reflectance
        arr_after: (C, H, W) float32 reflectance (co-registered to before grid)
        device: 'cuda' or 'cpu'
        threshold: binarization threshold

    Returns:
        binary_mask: (H, W) uint8 change mask (1=change, 0=no-change)
        prob_map: (H, W) float32 change probabilities
    """
    if torch is None:
        raise RuntimeError("torch not available")

    # Ensure 4 channels (B, G, R, NIR or replicate)
    c_b, h, w = arr_before.shape
    c_a = arr_after.shape[0]

    def _prepare(arr: np.ndarray) -> np.ndarray:
        if arr.shape[0] < 4:
            pads = [arr] * (4 // arr.shape[0] + 1)
            arr = np.concatenate(pads, axis=0)[:4]
        elif arr.shape[0] > 4:
            arr = arr[:4]
        # normalize to [0, 1] range
        arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)
        max_v = float(np.nanmax(arr))
        if max_v > 1.5:
            arr = arr / 10000.0 if max_v > 100 else arr / 255.0
        return np.clip(arr, 0.0, 1.0).astype(np.float32)

    b_prep = _prepare(arr_before)
    a_prep = _prepare(arr_after)

    t1 = torch.from_numpy(b_prep).unsqueeze(0).to(device)
    t2 = torch.from_numpy(a_prep).unsqueeze(0).to(device)

    with torch.no_grad():
        prob = model(t1, t2)
        prob_np = prob.squeeze().cpu().numpy().astype(np.float32)

    mask = (prob_np >= threshold).astype(np.uint8)
    return mask, prob_np
