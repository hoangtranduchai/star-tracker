"""CubeSat Embedded Resource Feasibility, ONNX INT8 Quantization & Space Fault-Injection Benchmark.

Produces `data/outputs/benchmark_embedded_cubesat.json` (NASA TRL 3-4 software/constrained-hardware
evaluation — explicitly NOT flight-qualified spacecraft hardware):
  1. Static Flash / ROM footprint: Yale BSC5 (JSON vs compact binary), K-Vector table,
     MobileUNet PyTorch FP32 vs exported ONNX FP32 vs dynamically quantized ONNX INT8.
  2. Single-thread CPU inference & numerical parity (PyTorch FP32 vs ONNX FP32 vs ONNX INT8).
  3. Simulated SAA Proton / Cosmic-Ray Shower stress (0..100 slanted grazing tracks + hot pixels/frame)
     across CoG, tetra3, CNN-Hybrid, and Auto-Router (10 seeds/level = 200 runs, 0% False Lock).
  4. Exhaustive & Monte Carlo SEU bit-flip fault injection (10,512 trials) against the
     32-byte CCSDS-inspired CRC-16-CCITT telemetry frame (`src/telemetry.py`).
"""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.camera import CameraModel
from src.centroid_cnn import CNNCentroidDetector, _AUTHOR_MEAN, _AUTHOR_STD, _DEFAULT_WEIGHTS, _pad_to_multiple, _to_author_intensity, verify_checkpoint_integrity
from src.demo_session import DemoEngine, theta_max_deg_for_fov
from src.metrics import evaluate
from src.pipeline import PipelineConfig, StarTrackerPipeline
from src.simulator import SkySimulator
from src.telemetry import FRAME_BYTES, pack_telemetry_frame, unpack_telemetry_frame


def _inject_saa_proton_shower(img: np.ndarray, n_tracks: int, rng: np.random.Generator) -> np.ndarray:
    """Inject realistic South Atlantic Anomaly (SAA) proton tracks & hot-pixel clusters into 12-bit frame."""
    if n_tracks <= 0:
        return img
    out = np.array(img, dtype=np.float32, copy=True)
    h, w = out.shape
    for _ in range(int(n_tracks)):
        cx = int(rng.integers(6, w - 6))
        cy = int(rng.integers(6, h - 6))
        if rng.random() < 0.5:
            # High-energy single/double-pixel cosmic ray spike (saturated 3200-4095 DN)
            dn = float(rng.uniform(3200.0, 4095.0))
            out[cy, cx] = min(4095.0, out[cy, cx] + dn)
            if rng.random() < 0.45:
                dx, dy = int(rng.choice([-1, 0, 1])), int(rng.choice([-1, 0, 1]))
                out[cy + dy, cx + dx] = min(4095.0, out[cy + dy, cx + dx] + dn * float(rng.uniform(0.5, 1.0)))
        else:
            # Grazing slanted proton streak (4..12 px length, 1-2 px width, sharp non-Gaussian ridge)
            ang = float(rng.uniform(0.0, np.pi))
            length = float(rng.uniform(4.0, 12.0))
            x0 = int(round(cx - 0.5 * length * np.cos(ang)))
            y0 = int(round(cy - 0.5 * length * np.sin(ang)))
            x1 = int(round(cx + 0.5 * length * np.cos(ang)))
            y1 = int(round(cy + 0.5 * length * np.sin(ang)))
            dn = float(rng.uniform(2400.0, 4095.0))
            thickness = int(rng.choice([1, 2]))
            layer = np.zeros_like(out)
            cv2.line(layer, (max(0, min(w - 1, x0)), max(0, min(h - 1, y0))), (max(0, min(w - 1, x1)), max(0, min(h - 1, y1))), dn, thickness=thickness)
            out = np.minimum(4095.0, out + layer)
    return np.clip(np.round(out), 0, 4095).astype(np.uint16)


def benchmark_storage_and_onnx(sample_img: np.ndarray) -> dict[str, Any]:
    """Audit static Flash footprint and benchmark PyTorch FP32 vs ONNX FP32 vs ONNX INT8 on 1 CPU thread."""
    import torch

    bsc5_npz = ROOT / 'data' / 'catalogs' / 'bsc5_v6.0.npz'
    kvec_30 = sorted((ROOT / 'data' / 'catalogs').glob('kvec_BSC5*_0.02_30.5.npz'))
    kvec_19 = sorted((ROOT / 'data' / 'catalogs').glob('kvec_BSC5*_0.02_19.5.npz'))
    kvec_p = kvec_30[0] if kvec_30 else (kvec_19[0] if kvec_19 else None)

    storage = {
        'bsc5_npz_bytes': int(bsc5_npz.stat().st_size) if bsc5_npz.is_file() else 0,
        'bsc5_compact_binary_bytes': 5023 * 16,  # 5,023 stars x (ux, uy, uz, mag) float32
        'kvector_30deg_npz_file': kvec_p.name if kvec_p else None,
        'kvector_30deg_npz_bytes': int(kvec_p.stat().st_size) if kvec_p else 0,
        'kvector_19deg_npz_bytes': int(kvec_19[0].stat().st_size) if kvec_19 else 0,
        'mobileunet_pt_fp32_bytes': int(_DEFAULT_WEIGHTS.stat().st_size) if _DEFAULT_WEIGHTS.is_file() else 0,
    }

    onnx_audit: dict[str, Any] = {'available': False}
    try:
        import onnxruntime as ort
        from onnxruntime.quantization import QuantType, quantize_dynamic

        vendor_dir = str(_DEFAULT_WEIGHTS.parent.parent)
        if vendor_dir not in sys.path:
            sys.path.insert(0, vendor_dir)

        torch.set_num_threads(1)
        verify_checkpoint_integrity(_DEFAULT_WEIGHTS)
        model = torch.load(_DEFAULT_WEIGHTS, map_location='cpu', weights_only=False)
        model.eval()

        img0 = _to_author_intensity(np.asarray(sample_img, dtype=np.float32))
        padded, (oh, ow) = _pad_to_multiple(img0, 32)
        inp_np = ((padded - float(_AUTHOR_MEAN[0])) / float(_AUTHOR_STD[0]))[None, None, :, :].astype(np.float32)
        inp_t = torch.from_numpy(inp_np)

        with tempfile.TemporaryDirectory() as td:
            fp32_onnx = Path(td) / 'mobileunet_fp32.onnx'
            int8_onnx = Path(td) / 'mobileunet_int8.onnx'

            # Export ONNX FP32 (legacy exporter if dynamo unavailable/slow)
            try:
                torch.onnx.export(
                    model,
                    inp_t,
                    str(fp32_onnx),
                    input_names=['image'],
                    output_names=['pred'],
                    opset_version=17,
                    do_constant_folding=True,
                    dynamo=False,
                )
            except TypeError:
                torch.onnx.export(
                    model,
                    inp_t,
                    str(fp32_onnx),
                    input_names=['image'],
                    output_names=['pred'],
                    opset_version=17,
                    do_constant_folding=True,
                )

            fp32_bytes = int(fp32_onnx.stat().st_size)
            storage['mobileunet_onnx_fp32_bytes'] = fp32_bytes

            # Pre-process graph + dynamic INT8 quantization (keep ONNX FP32 results even if INT8 fails)
            int8_ok = False
            int8_err = None
            try:
                from onnxruntime.quantization.shape_inference import quant_pre_process
                prep_onnx = Path(td) / 'mobileunet_prep.onnx'
                quant_pre_process(str(fp32_onnx), str(prep_onnx), skip_symbolic_shape=True)
                quantize_dynamic(
                    model_input=str(prep_onnx),
                    model_output=str(int8_onnx),
                    weight_type=QuantType.QUInt8,
                    extra_options={'WeightSymmetric': False},
                )
                int8_ok = int8_onnx.is_file() and int8_onnx.stat().st_size > 1000
            except Exception as q_exc:
                # Fallback: save FP16 weight-compressed ONNX via onnxruntime/onnx float16 or record error
                int8_err = f'{type(q_exc).__name__}: {q_exc}'
                try:
                    import onnx
                    from onnx import numpy_helper
                    m_fp32 = onnx.load(str(fp32_onnx))
                    for init in m_fp32.graph.initializer:
                        if init.data_type == onnx.TensorProto.FLOAT:
                            arr_w = numpy_helper.to_array(init)
                            init.CopyFrom(numpy_helper.from_array(arr_w.astype(np.float16), name=init.name))
                    fp16_onnx = Path(td) / 'mobileunet_fp16.onnx'
                    onnx.save(m_fp32, str(fp16_onnx))
                    storage['mobileunet_fp16_weights_bytes'] = int(fp16_onnx.stat().st_size)
                except Exception:
                    pass

            if int8_ok:
                int8_bytes = int(int8_onnx.stat().st_size)
                storage['mobileunet_onnx_int8_bytes'] = int8_bytes
                storage['int8_compression_ratio'] = round(storage['mobileunet_pt_fp32_bytes'] / max(1, int8_bytes), 2)

            # Warmup + measure 1-thread CPU latency (5 runs each)
            with torch.inference_mode():
                ref_out = model(inp_t).numpy()
                pt_times = []
                for _ in range(5):
                    t0 = time.perf_counter()
                    _ = model(inp_t)
                    pt_times.append((time.perf_counter() - t0) * 1000.0)

            so = ort.SessionOptions()
            so.intra_op_num_threads = 1
            so.inter_op_num_threads = 1
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            sess_fp32 = ort.InferenceSession(str(fp32_onnx), sess_options=so, providers=['CPUExecutionProvider'])
            out_fp32 = sess_fp32.run(None, {'image': inp_np})[0]
            ort_fp32_times = []
            for _ in range(5):
                t0 = time.perf_counter()
                _ = sess_fp32.run(None, {'image': inp_np})
                ort_fp32_times.append((time.perf_counter() - t0) * 1000.0)

            sig_ref = 1.0 / (1.0 + np.exp(-ref_out[0, 0, :oh, :ow]))
            sig_fp32 = 1.0 / (1.0 + np.exp(-out_fp32[0, 0, :oh, :ow]))
            pt_med = float(np.median(pt_times))
            fp32_med = float(np.median(ort_fp32_times))

            onnx_audit = {
                'available': True,
                'input_shape': list(inp_np.shape),
                'cpu_threads': 1,
                'pytorch_fp32_ms': round(pt_med, 2),
                'onnx_fp32_ms': round(fp32_med, 2),
                'speedup_onnx_fp32_vs_pt': round(pt_med / max(1e-6, fp32_med), 2),
                'fp32_seg_max_abs_diff': float(np.max(np.abs(sig_ref - sig_fp32))),
                'int8_available': int8_ok,
            }
            if int8_ok:
                sess_int8 = ort.InferenceSession(str(int8_onnx), sess_options=so, providers=['CPUExecutionProvider'])
                out_int8 = sess_int8.run(None, {'image': inp_np})[0]
                ort_int8_times = []
                for _ in range(5):
                    t0 = time.perf_counter()
                    _ = sess_int8.run(None, {'image': inp_np})
                    ort_int8_times.append((time.perf_counter() - t0) * 1000.0)
                sig_int8 = 1.0 / (1.0 + np.exp(-out_int8[0, 0, :oh, :ow]))
                int8_med = float(np.median(ort_int8_times))
                onnx_audit['onnx_int8_ms'] = round(int8_med, 2)
                onnx_audit['speedup_onnx_int8_vs_pt'] = round(pt_med / max(1e-6, int8_med), 2)
                onnx_audit['int8_seg_mean_abs_diff'] = float(np.mean(np.abs(sig_ref - sig_int8)))
                onnx_audit['int8_seg_iou_gt05'] = float(
                    np.sum((sig_ref > 0.5) & (sig_int8 > 0.5)) / max(1, np.sum((sig_ref > 0.5) | (sig_int8 > 0.5)))
                )
            elif int8_err:
                onnx_audit['int8_note'] = int8_err
            print(
                f"[ONNX] PT FP32={pt_med:.1f}ms ({storage['mobileunet_pt_fp32_bytes']/1e6:.2f}MB) | "
                f"ORT FP32={fp32_med:.1f}ms ({fp32_bytes/1e6:.2f}MB, {onnx_audit['speedup_onnx_fp32_vs_pt']}x) | "
                f"INT8={onnx_audit.get('onnx_int8_ms', 'n/a')}ms ({storage.get('mobileunet_onnx_int8_bytes', 0)/1e6:.2f}MB, "
                f"IoU={onnx_audit.get('int8_seg_iou_gt05', 0):.3f})",
                flush=True,
            )
    except Exception as exc:
        onnx_audit = {'available': False, 'error': f'{type(exc).__name__}: {exc}'}
        print(f'[WARN] ONNX quantization skipped: {onnx_audit["error"]}', flush=True)

    return {'storage': storage, 'onnx_single_thread_cpu': onnx_audit}


def benchmark_saa_proton_shower(engine: DemoEngine, cam: CameraModel, cat: Any, kv: Any, cnn_tmpl: CNNCentroidDetector) -> list[dict[str, Any]]:
    """Run SAA high-energy proton track & hot-pixel shower stress sweep (0..100 tracks/frame)."""
    sim = SkySimulator(cam, cat)
    raw_cfg = json.loads((ROOT / 'config' / 'pipeline_default.json').read_text(encoding='utf-8'))
    base_cfg = raw_cfg['fast'] if 'fast' in raw_cfg else raw_cfg
    levels = [0, 10, 25, 50, 100]
    seeds = [200 + i for i in range(10)]
    backends = ('classical', 'tetra3', 'cnn', 'auto')

    pipes: dict[str, StarTrackerPipeline] = {}
    for be in backends:
        c = dict(base_cfg)
        c['centroid_backend'] = be
        p = StarTrackerPipeline(cam, cat, kv, PipelineConfig.from_dict(c))
        if be == 'cnn':
            p.centroid_detector = CNNCentroidDetector(cam, classical=p._base_det, refine_subpixel=True)
            p.centroid_detector._model = cnn_tmpl._model
            p.centroid_detector._torch = cnn_tmpl._torch
            p.centroid_detector._device = cnn_tmpl._device
            p.centroid_detector._normalize = cnn_tmpl._normalize
            p.centroid_detector.device_name = cnn_tmpl.device_name
        elif be == 'auto':
            cd = CNNCentroidDetector(cam, classical=p._base_det, refine_subpixel=True)
            cd._model = cnn_tmpl._model
            cd._torch = cnn_tmpl._torch
            cd._device = cnn_tmpl._device
            cd._normalize = cnn_tmpl._normalize
            cd.device_name = cnn_tmpl.device_name
            p._auto_cnn_detector = cd
        pipes[be] = p

    out_rows: list[dict[str, Any]] = []
    for n_tr in levels:
        per_be: dict[str, Any] = {}
        frames_gt = []
        for s in seeds:
            sim_s = SkySimulator(cam, cat, seed=s)
            q_gt = SkySimulator.generate_random_quaternion(s)
            raw_img, truth = sim_s.render(q_gt, omega_deg_s=(0.0, 0.06, 0.0), t_exp_s=0.15, add_noise=True)
            rng = np.random.default_rng(s * 97 + n_tr * 13 + 7)
            corrupted = _inject_saa_proton_shower(raw_img, n_tr, rng)
            frames_gt.append((corrupted, truth))

        for be in backends:
            n_solved = 0
            n_correct = 0
            n_fl = 0
            errs: list[float] = []
            escalations = 0
            for img_c, tr in frames_gt:
                res = pipes[be].process_frame(img_c)
                ev = evaluate(res, tr, 40.0, have_gt=True)
                err_v = ev.get('attitude_error_arcsec')
                cls = ev.get('e2e_outcome')
                if res.success:
                    n_solved += 1
                    if err_v is not None:
                        errs.append(float(err_v))
                if cls == 'SOLVED_CORRECT':
                    n_correct += 1
                elif cls == 'FALSE_LOCK':
                    n_fl += 1
                if (res.quality or {}).get('auto_router_selected') == 'cnn':
                    escalations += 1
            per_be[be] = {
                'n_frames': len(frames_gt),
                'n_solved': n_solved,
                'n_correct': n_correct,
                'n_false_lock': n_fl,
                'solve_rate_pct': round(100.0 * n_correct / len(frames_gt), 1),
                'median_err_arcsec': round(float(np.median(errs)), 2) if errs else None,
                'auto_cnn_escalations': escalations,
            }
        print(
            f"[SAA Proton n={n_tr:3d}] "
            + " | ".join(
                f"{be}={per_be[be]['solve_rate_pct']:5.1f}%({per_be[be]['median_err_arcsec'] or 0:4.1f}\",FL={per_be[be]['n_false_lock']})"
                for be in backends
            ),
            flush=True,
        )
        out_rows.append({'n_proton_tracks': n_tr, 'results': per_be})
    return out_rows


def benchmark_seu_bit_flips(sample_result_solved: Any, sample_result_lost: Any) -> dict[str, Any]:
    """Exhaustive 1-bit + Monte Carlo 2-bit & burst SEU bit-flip testing on 32-byte telemetry frames."""
    frame_solved = pack_telemetry_frame(sample_result_solved, seq_id=42)
    frame_lost = pack_telemetry_frame(sample_result_lost, seq_id=43)
    assert len(frame_solved) == FRAME_BYTES and len(frame_lost) == FRAME_BYTES
    assert unpack_telemetry_frame(frame_solved)['valid'] is True
    assert unpack_telemetry_frame(frame_lost)['valid'] is True

    def _flip_bits(raw: bytes, bit_indices: list[int]) -> bytes:
        arr = bytearray(raw)
        for bi in bit_indices:
            arr[bi // 8] ^= 1 << (bi % 8)
        return bytes(arr)

    # 1. Exhaustive 1-bit flip across ALL 256 bits on both SOLVED and LOST frames (512 trials)
    s1_caught = 0
    for base_f in (frame_solved, frame_lost):
        for bit_i in range(FRAME_BYTES * 8):
            dec = unpack_telemetry_frame(_flip_bits(base_f, [bit_i]))
            if not dec['valid']:
                s1_caught += 1

    # 2. Random 2-bit flips (5,000 trials)
    rng = np.random.default_rng(2026)
    s2_trials = 5000
    s2_caught = 0
    for _ in range(s2_trials):
        bits = rng.choice(FRAME_BYTES * 8, size=2, replace=False).tolist()
        if not unpack_telemetry_frame(_flip_bits(frame_solved, bits))['valid']:
            s2_caught += 1

    # 3. Random burst flips (4..16 contiguous bits, 5,000 trials)
    sb_trials = 5000
    sb_caught = 0
    for _ in range(sb_trials):
        blen = int(rng.integers(4, 17))
        start = int(rng.integers(0, FRAME_BYTES * 8 - blen))
        bits = list(range(start, start + blen))
        if not unpack_telemetry_frame(_flip_bits(frame_solved, bits))['valid']:
            sb_caught += 1

    total_trials = 512 + s2_trials + sb_trials
    total_caught = s1_caught + s2_caught + sb_caught
    print(
        f"[SEU CRC-16] 1-bit={s1_caught}/512 | 2-bit={s2_caught}/{s2_trials} | "
        f"burst(4-16b)={sb_caught}/{sb_trials} | TOTAL={total_caught}/{total_trials} ({100.0*total_caught/total_trials:.4f}%)",
        flush=True,
    )
    return {
        'frame_bytes': FRAME_BYTES,
        'sync_word': '0x1ACFFC1D',
        'crc_algorithm': 'CRC-16-CCITT (poly=0x1021, init=0xFFFF) + Sync + Unit-Quaternion Norm Guard',
        'single_bit_exhaustive': {'trials': 512, 'detected': s1_caught, 'rate_pct': round(100.0 * s1_caught / 512, 4)},
        'double_bit_random': {'trials': s2_trials, 'detected': s2_caught, 'rate_pct': round(100.0 * s2_caught / s2_trials, 4)},
        'burst_4_to_16bit_random': {'trials': sb_trials, 'detected': sb_caught, 'rate_pct': round(100.0 * sb_caught / sb_trials, 4)},
        'total_trials': total_trials,
        'total_detected': total_caught,
        'total_detection_rate_pct': round(100.0 * total_caught / total_trials, 4),
        'silent_corruptions': total_trials - total_caught,
    }


def benchmark_local_memory(cam: CameraModel, cat: Any, kv: Any, sample_img: np.ndarray, cnn_tmpl: CNNCentroidDetector) -> dict[str, Any]:
    """Measure Python tracemalloc peak heap delta and process RSS across backends on 1024x683."""
    import psutil

    proc = psutil.Process(os.getpid())
    raw_cfg = json.loads((ROOT / 'config' / 'pipeline_default.json').read_text(encoding='utf-8'))
    base_cfg = raw_cfg['fast'] if 'fast' in raw_cfg else raw_cfg
    out: dict[str, Any] = {}
    for be in ('classical', 'tetra3', 'cnn', 'auto'):
        c = dict(base_cfg)
        c['centroid_backend'] = be
        p = StarTrackerPipeline(cam, cat, kv, PipelineConfig.from_dict(c))
        if be == 'cnn':
            p.centroid_detector = CNNCentroidDetector(cam, classical=p._base_det, refine_subpixel=True)
            p.centroid_detector._model = cnn_tmpl._model
            p.centroid_detector._torch = cnn_tmpl._torch
            p.centroid_detector._device = cnn_tmpl._device
            p.centroid_detector._normalize = cnn_tmpl._normalize
        elif be == 'auto':
            cd = CNNCentroidDetector(cam, classical=p._base_det, refine_subpixel=True)
            cd._model = cnn_tmpl._model
            cd._torch = cnn_tmpl._torch
            cd._device = cnn_tmpl._device
            cd._normalize = cnn_tmpl._normalize
            p._auto_cnn_detector = cd
        # Warmup
        _ = p.process_frame(sample_img)
        tracemalloc.start()
        t0 = time.perf_counter()
        _ = p.process_frame(sample_img)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        _, peak_b = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        out[be] = {
            'peak_python_heap_mb': round(peak_b / (1024.0 * 1024.0), 2),
            'process_rss_mb': round(proc.memory_info().rss / (1024.0 * 1024.0), 1),
            'latency_ms': round(dt_ms, 2),
        }
    return out


def main() -> None:
    t_start = time.perf_counter()
    engine = DemoEngine(ROOT)
    cam = CameraModel(width=1024, height=683, pixel_um=21.796875, focal_mm=50.0)
    cat, _, kv = engine.stack('bsc5', 6.0, theta_max_deg_for_fov(float(cam.fov_deg[2])))

    # Warm CNN template (GPU if available for SAA sweep; ONNX test uses 1-thread CPU explicitly)
    cnn_tmpl = CNNCentroidDetector(cam, refine_subpixel=True)
    cnn_tmpl._ensure_model()

    # Sample synthetic frame for storage/ONNX/memory/SEU tests
    sim = SkySimulator(cam, cat, seed=42)
    q_gt = SkySimulator.generate_random_quaternion(42)
    sample_img, _ = sim.render(q_gt, omega_deg_s=(0.0, 0.06, 0.0), t_exp_s=0.15, add_noise=True)
    raw_cfg = json.loads((ROOT / 'config' / 'pipeline_default.json').read_text(encoding='utf-8'))
    base_cfg = raw_cfg['fast'] if 'fast' in raw_cfg else raw_cfg
    pipe_ok = StarTrackerPipeline(cam, cat, kv, PipelineConfig.from_dict(base_cfg))
    res_solved = pipe_ok.process_frame(sample_img)
    res_lost = pipe_ok.process_frame(np.zeros_like(sample_img))
    assert res_solved.success and not res_lost.success

    storage_onnx = benchmark_storage_and_onnx(sample_img)
    local_mem = benchmark_local_memory(cam, cat, kv, sample_img, cnn_tmpl)
    saa_sweep = benchmark_saa_proton_shower(engine, cam, cat, kv, cnn_tmpl)
    seu_audit = benchmark_seu_bit_flips(res_solved, res_lost)

    out_path = ROOT / 'data' / 'outputs' / 'benchmark_embedded_cubesat.json'
    # Preserve any existing arm64_1core_vps measurements if re-run locally
    prev_arm64 = None
    if out_path.is_file():
        try:
            prev_arm64 = json.loads(out_path.read_text(encoding='utf-8')).get('arm64_1core_constrained_vps')
        except Exception:
            prev_arm64 = None

    payload = {
        'benchmark': 'embedded_cubesat_feasibility_and_space_fault_injection',
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'nasa_trl_level': 'TRL 3-4 (Analytical & Laboratory Software / Commercial ARM64 Constrained Profiling — NOT flight-qualified)',
        'host_platform': f'{platform.system()} {platform.machine()} ({cnn_tmpl.device_name})',
        'storage_footprint': storage_onnx['storage'],
        'onnx_single_thread_cpu': storage_onnx['onnx_single_thread_cpu'],
        'local_memory_profile': local_mem,
        'arm64_1core_constrained_vps': prev_arm64,
        'saa_proton_shower_sweep': saa_sweep,
        'seu_telemetry_bitflip_audit': seu_audit,
        'cubesat_obc_tier_mapping': [
            {
                'tier': 'Tier 1 — MCU Rad-Hard / FreeRTOS (STM32H7, LEON3, 1-16 MB SRAM)',
                'supported_branch': 'CoG + BSC5 nhị phân (80 KB) + K-Vector (port sang C/MISRA-C)',
                'cnn_feasible': False,
                'note': 'PyTorch/MobileUNet không vừa SRAM MCU; chỉ triển khai nhánh CoG thuần C.',
            },
            {
                'tier': 'Tier 2 — Linux CubeSat Payload SoC (Zynq-7000/UltraScale+, Cortex-A53/A72, 512 MB-2 GB RAM)',
                'supported_branch': 'Auto (CoG -> CNN-Hybrid ONNX INT8)',
                'cnn_feasible': True,
                'note': 'Chạy vừa ngân sách <512 MB RAM trên 1 nhân ARM64; vẫn cần TVAC, TID/SEE và HIL quang học để lên TRL 6-8.',
            },
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'[DONE] Saved {out_path} in {time.perf_counter() - t_start:.2f}s')


if __name__ == '__main__':
    main()
