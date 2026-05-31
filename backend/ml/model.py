"""
Vocals-Only Hybrid Spectrogram TasNet — v12 (complex mask + unbounded magnitude)

What's new in v12 (the architecture upgrade)
─────────────────────────────────────────────
1. Unbounded mask heads (replaces Sigmoid).
   Old: Linear → Sigmoid → mask ∈ [0, 1]
   New: Linear → softplus → mask ∈ [0, ~5]  (clamped via soft saturation)
   Why: Kong et al. 2021 (ByteDance) showed that 22 % of MUSDB18 time-
   frequency bins have an ideal ratio mask (IRM) value > 1.0.  A sigmoid
   mask literally cannot reproduce these — the best it can do is mask=1.0
   ("let the mixture through"), which is exactly the "music dimmed but
   not removed" symptom we were seeing.  Softplus is unbounded above zero
   with smooth gradients; clamp at 5.0 prevents pathological values.

2. Complex (decoupled magnitude + phase) mask for the spec branch.
   Old: predicted_spec = (mixture_mag × magnitude_mask) × mixture_phase
   New: predicted_spec = (mixture_mag × magnitude_scale) × rotated_phase
   where rotated_phase = mixture_phase * (cos_delta + i sin_delta), and
   (cos_delta, sin_delta) is normalised to unit circle.
   Why: Reusing mixture phase causes destructive interference at any TF
   bin where vocals and accompaniment overlap (which is most of them when
   piano/guitar/keys are present).  Estimating a phase rotation per bin
   fixes this — same trick as Kong et al. 2021's DCCRN, BSRNN, and friends.

3. Streaming-friendly lookahead buffer in StatefulHSTasNetVocals.
   Adds a configurable output-delay buffer so the writer side can align
   to a chunk boundary without artefacts.  Default 0 = current behaviour.

Previous improvements retained
────────────────────────────────
• Bidirectional flag (default False — streaming requires causal LSTMs)
• Two-stage spec input projection (preserves inter-channel structure)
• LayerNorm + Dropout in MemoryLSTMBlock (training stability)
• Always-active residual / skip connections
• GroupNorm in LearnedConvEncoder
• Stateful streaming wrapper with cross-fade at chunk boundaries
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Building Blocks
# ---------------------------------------------------------------------------

class MemoryLSTMBlock(nn.Module):
    """
    Two stacked LSTMs with:
      • LayerNorm after each LSTM (training stability)
      • Dropout between LSTM layers (regularisation)
      • Always-active residual / skip connection (no silent no-ops)
      • Stateful: accepts and returns (h, c) for streaming
      • Optional bidirectional mode for offline processing

    Args:
        input_size    : feature dimension of x
        hidden_size   : LSTM hidden / output dimension
        skip_size     : feature dimension of the skip tensor (if different from
                        input_size).  If None, skip defaults to x.
        dropout       : dropout probability applied between lstm1 → lstm2
        bidirectional : if True, uses bidirectional LSTMs (2x output dimension,
                        projected back to hidden_size)
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        skip_size: int = None,
        dropout: float = 0.1,
        bidirectional: bool = False,
    ):
        super().__init__()
        self.hidden_size   = hidden_size
        self.bidirectional = bidirectional
        self.num_dirs      = 2 if bidirectional else 1

        # LSTM output dimension before projection
        lstm_out = hidden_size * self.num_dirs

        self.lstm1 = nn.LSTM(input_size, hidden_size, batch_first=True,
                             bidirectional=bidirectional)
        self.norm1 = nn.LayerNorm(lstm_out)

        self.dropout = nn.Dropout(p=dropout)

        self.lstm2 = nn.LSTM(lstm_out, hidden_size, batch_first=True,
                             bidirectional=bidirectional)
        self.norm2 = nn.LayerNorm(lstm_out)

        # Project bidirectional output back to hidden_size
        self.out_proj = (
            nn.Linear(lstm_out, hidden_size)
            if bidirectional
            else nn.Identity()
        )

        # Project skip/x to hidden_size if dimensions differ
        effective_skip = skip_size if skip_size is not None else input_size
        self.skip_proj = (
            nn.Linear(effective_skip, hidden_size)
            if effective_skip != hidden_size
            else nn.Identity()
        )

    def forward(self, x, skip=None, state1=None, state2=None):
        """
        x      : (B, T, input_size)
        skip   : (B, T, skip_size) or None — tensor to add as residual
        state1 : (h, c) for lstm1 or None
        state2 : (h, c) for lstm2 or None

        Returns: out (B, T, hidden_size), new_state1, new_state2
        """
        out1, state1 = self.lstm1(x, state1)
        out1 = self.norm1(out1)
        out1 = self.dropout(out1)

        out2, state2 = self.lstm2(out1, state2)
        out2 = self.norm2(out2)

        # Project back to hidden_size if bidirectional
        out2 = self.out_proj(out2)

        # Residual: prefer explicit skip, fall back to x
        residual_src = skip if skip is not None else x
        out2 = out2 + self.skip_proj(residual_src)

        return out2, state1, state2




class SpectrogramEncoder(nn.Module):
    def __init__(self, n_fft=1024, hop_length=512):
        super().__init__()
        self.n_fft      = n_fft
        self.hop_length = hop_length
        self.n_bins     = n_fft // 2 + 1
        self.register_buffer('window', torch.hann_window(n_fft))

    def forward(self, x):
        """x: (B, C, L) → mag (B, C, n_bins, T), phase (B, C, n_bins, T)"""
        B, C, L = x.shape
        x_flat  = x.reshape(B * C, L)
        stft    = torch.stft(
            x_flat, n_fft=self.n_fft, hop_length=self.hop_length,
            win_length=self.n_fft, window=self.window,
            return_complex=True, pad_mode='reflect', center=True,
        )
        mag   = stft.abs()
        phase = stft / mag.clamp(min=1e-8)
        mag   = mag.reshape(B, C, self.n_bins, -1)
        phase = phase.reshape(B, C, self.n_bins, -1)
        return mag, phase


class SpectrogramDecoder(nn.Module):
    def __init__(self, n_fft=1024, hop_length=512):
        super().__init__()
        self.n_fft      = n_fft
        self.hop_length = hop_length
        self.register_buffer('window', torch.hann_window(n_fft))

    def forward(self, masked_mag, phase, length):
        """
        Legacy magnitude-mask + mixture-phase path.
        masked_mag, phase: (B, C, n_bins, T) — phase is a unit-complex tensor.
        Returns: (B, C, L)
        """
        B, C, n_bins, T = masked_mag.shape
        spec  = (masked_mag * phase).reshape(B * C, n_bins, T)
        wav   = torch.istft(
            spec, n_fft=self.n_fft, hop_length=self.hop_length,
            win_length=self.n_fft, window=self.window,
            length=length, center=True,
        )
        return wav.reshape(B, C, -1)[..., :length]

    def forward_complex(self, complex_spec, length):
        """
        v12: caller passes the predicted complex spectrogram directly (e.g. after
        applying both a magnitude scale AND a phase rotation).  No mixture-phase
        copying happens here — the caller is responsible for incorporating phase.

        complex_spec : (B, C, n_bins, T) complex tensor
        Returns      : (B, C, L)
        """
        B, C, n_bins, T = complex_spec.shape
        spec = complex_spec.reshape(B * C, n_bins, T)
        wav  = torch.istft(
            spec, n_fft=self.n_fft, hop_length=self.hop_length,
            win_length=self.n_fft, window=self.window,
            length=length, center=True,
        )
        return wav.reshape(B, C, -1)[..., :length]


class LearnedConvEncoder(nn.Module):
    def __init__(self, n_basis=1024, window=1024, hop=512, in_channels=2):
        super().__init__()
        self.window = window
        self.conv   = nn.Conv1d(in_channels, n_basis, kernel_size=window, stride=hop, bias=False)
        self.act    = nn.ReLU()
        self.norm   = nn.GroupNorm(1, n_basis)   # instance norm over basis channels

    def forward(self, x):
        """x: (B, C, L) → (B, n_basis, T)"""
        pad = self.window // 2
        out = self.conv(F.pad(x, (pad, pad), mode='reflect'))
        return self.act(self.norm(out))


class LearnedConvDecoder(nn.Module):
    def __init__(self, n_basis=1024, window=1024, hop=512, out_channels=2):
        super().__init__()
        self.hop    = hop
        self.conv_t = nn.ConvTranspose1d(n_basis, out_channels, kernel_size=window, stride=hop, bias=False)
        self.register_buffer('hann', torch.hann_window(window))

    def forward(self, x, length):
        """x: (B, n_basis, T) → (B, C, L)"""
        w   = self.conv_t.weight * self.hann.view(1, 1, -1)
        out = F.conv_transpose1d(x, w, stride=self.hop)
        return out[..., :length]


# ---------------------------------------------------------------------------
# Vocals-Only HS-TasNet v3
# ---------------------------------------------------------------------------

class HSTasNetVocals(nn.Module):
    """
    Hybrid Spectrogram TasNet — vocal extractor (v3).

    Changes from v2:
      • MemoryLSTMBlock supports bidirectional mode for offline separation
      • Two-stage spec_input_proj (MLP) preserves inter-channel structure
      • extra_repr() for easy model inspection

    API identical to v2: forward(x, states) → vocals, new_states
    """

    def __init__(
        self,
        n_fft=1024,
        hop_length=512,
        n_basis=1024,
        hidden_spec=500,
        hidden_conv=500,
        hidden_combined=1000,
        n_channels=2,
        dropout_p=0.1,
        bidirectional=False,
    ):
        super().__init__()
        self.n_fft         = n_fft
        self.hop_length    = hop_length
        self.n_basis       = n_basis
        self.n_channels    = n_channels
        self.n_bins        = n_fft // 2 + 1
        self.bidirectional = bidirectional

        # Encoders
        self.spec_encoder    = SpectrogramEncoder(n_fft, hop_length)
        self.conv_encoder    = LearnedConvEncoder(n_basis, n_fft, hop_length, n_channels)

        # Two-stage spectrogram input projection (M5)
        # Preserves inter-channel information through an intermediate hidden layer
        spec_in_dim  = n_channels * self.n_bins   # 2 * 513 = 1026
        spec_mid_dim = self.n_bins * 2            # 1026 — intermediate
        self.spec_input_proj = nn.Sequential(
            nn.Linear(spec_in_dim, spec_mid_dim),
            nn.ReLU(),
            nn.Linear(spec_mid_dim, self.n_bins),
        )

        # Pre-concat blocks
        self.spec_lstm = MemoryLSTMBlock(self.n_bins, hidden_spec, dropout=dropout_p,
                                         bidirectional=bidirectional)
        self.conv_lstm = MemoryLSTMBlock(n_basis,     hidden_conv, dropout=dropout_p,
                                         bidirectional=bidirectional)

        # Combined block — skip = pre-concat tensor (same dim as input)
        self.combined_lstm = MemoryLSTMBlock(
            hidden_spec + hidden_conv,
            hidden_combined,
            skip_size=hidden_spec + hidden_conv,
            dropout=dropout_p,
            bidirectional=bidirectional,
        )

        # Post-split blocks
        split_dim = hidden_combined // 2
        self.post_spec_lstm = MemoryLSTMBlock(split_dim, hidden_spec, dropout=dropout_p,
                                               bidirectional=bidirectional)
        self.post_conv_lstm = MemoryLSTMBlock(split_dim, hidden_conv, dropout=dropout_p,
                                               bidirectional=bidirectional)

        # ── Mask heads (v12: unbounded magnitude + complex spec mask) ─────────
        # spec_out_dim     = C * n_bins (raw mag scale per channel, per freq bin)
        # spec_phase_dim   = 2 * C * n_bins (cos, sin per channel per bin)
        # conv_out_dim     = n_basis (magnitude scale per learned-conv basis)
        spec_out_dim   = n_channels * self.n_bins
        spec_phase_dim = 2 * n_channels * self.n_bins

        # Spec branch — magnitude scale.  No Sigmoid: we apply F.softplus then
        # clamp in forward().  GELU activation gives smoother gradients than
        # ReLU for this kind of saturating-output regression task.
        self.spec_mag_head = nn.Sequential(
            nn.Linear(hidden_spec, hidden_spec),
            nn.GELU(),
            nn.Linear(hidden_spec, spec_out_dim),
        )

        # Spec branch — phase rotation (cos_delta, sin_delta) per bin.  Output
        # is normalised onto the unit circle in forward() so the rotation is
        # a pure rotation, not a magnitude scaling in disguise.
        self.spec_phase_head = nn.Sequential(
            nn.Linear(hidden_spec, hidden_spec),
            nn.GELU(),
            nn.Linear(hidden_spec, spec_phase_dim),
        )

        # Conv branch — magnitude scale only.  The conv branch operates in a
        # learned-basis space with no separate "phase" — there's nothing to
        # rotate.  Still drop sigmoid so the mask can exceed 1.0.
        self.conv_mask_head = nn.Sequential(
            nn.Linear(hidden_conv, hidden_conv),
            nn.GELU(),
            nn.Linear(hidden_conv, n_basis),
        )

        # Saturation cap used in forward() — masks softplus → values in
        # (0, ∞), clamped at MASK_MAX to avoid early-training pathologies.
        self.mask_max: float = 5.0

        # ── v12 identity initialisation of the new mask heads ─────────────────
        # At random init, the phase head rotates phases randomly (destroys
        # the mixture's time-domain structure) and the magnitude head
        # outputs softplus(random) ≈ 0.7 — so step-1 loss is huge positive
        # (~+75 in our test), because pred is essentially white noise.
        #
        # We bias the final Linear of each new head so the model STARTS as
        # "v8-equivalent" behaviour (mag mask ≈ 1, no phase rotation) and
        # learns to deviate from there.  This is the same trick residual
        # blocks use — start at zero contribution, learn to add value.
        #
        # Math:
        #   softplus(0.5413) ≈ 1.0  → bias for mag heads = 0.5413
        #   For phase head: first half (cos) → 1.0, second half (sin) → 0.0
        with torch.no_grad():
            mag_init = 0.5413  # softplus(0.5413) ≈ 1.0

            # Spec magnitude head — kill the weight, bias outputs ~mag_init
            last = self.spec_mag_head[-1]
            last.weight.zero_()
            last.bias.fill_(mag_init)

            # Conv magnitude mask head — same trick
            last = self.conv_mask_head[-1]
            last.weight.zero_()
            last.bias.fill_(mag_init)

            # Spec phase head — first half (cos) = 1, second half (sin) = 0.
            # The reshape in forward() is (B, T, 2, C, n_bins) so the raw
            # output is laid out as 2 groups of (C × n_bins).  Group 0 → cos,
            # group 1 → sin.  Therefore bias[: half] is cos, bias[half:] is sin.
            last = self.spec_phase_head[-1]
            last.weight.zero_()
            half = last.bias.numel() // 2
            last.bias[:half].fill_(1.0)   # cos_delta = 1  → no rotation
            last.bias[half:].fill_(0.0)   # sin_delta = 0

        # Decoders
        self.spec_decoder = SpectrogramDecoder(n_fft, hop_length)
        self.conv_decoder = LearnedConvDecoder(n_basis, n_fft, hop_length, n_channels)

        # ── Mask temporal smoothing (inference-time only) ─────────────────────
        # The STFT mask is applied independently per (freq-bin, time-frame).
        # When the model hasn't fully converged, the mask values fluctuate
        # frame-to-frame for the same frequency bin, producing "musical noise"
        # — a watery, garbled quality where each phoneme sounds different.
        #
        # A causal moving average across T smooths these fluctuations:
        #   smoothed_mask[t] = mean(mask[t-k+1 : t+1])
        # k=1 = no smoothing (default); k=3 = mild; k=5 = strong.
        # Does NOT add look-ahead — only past frames are averaged.
        # Set via model.set_mask_smooth(k) after loading checkpoint.
        self.mask_smooth_frames: int = 1   # 1 = off

    def set_mask_smooth(self, frames: int) -> None:
        """
        Enable/disable temporal smoothing on the separation mask.

        Args:
            frames : number of past frames to average the mask over.
                     1 = no smoothing (default / training behaviour).
                     3 = mild — good starting point, reduces most artefacts.
                     5 = strong — very smooth, may dull fast transients.
                     7 = heavy — recommended only for very noisy models.
        """
        self.mask_smooth_frames = max(1, int(frames))

    def extra_repr(self) -> str:
        return (
            f"n_fft={self.n_fft}, hop_length={self.hop_length}, "
            f"n_basis={self.n_basis}, n_channels={self.n_channels}, "
            f"bidirectional={self.bidirectional}"
        )

    def forward(self, x, states=None):
        """
        x      : (B, C, L)
        states : dict of LSTM (h, c) states, or None

        Returns:
            vocals     : (B, C, L)
            new_states : updated state dict
        """
        B, C, L = x.shape
        if states is None:
            states = {}

        def gs(key):
            return states.get(key, None)

        # ── Spectrogram branch ───────────────────────────────────────────────
        mag, phase = self.spec_encoder(x)
        _, _, _, T = mag.shape
        spec_feat  = self.spec_input_proj(
            mag.permute(0, 3, 1, 2).reshape(B, T, C * self.n_bins)
        )
        spec_out, s1a, s1b = self.spec_lstm(spec_feat, state1=gs('s1a'), state2=gs('s1b'))

        # ── Conv branch ──────────────────────────────────────────────────────
        conv_enc  = self.conv_encoder(x)
        conv_out, s2a, s2b = self.conv_lstm(
            conv_enc.permute(0, 2, 1), state1=gs('s2a'), state2=gs('s2b')
        )

        # ── Combined ─────────────────────────────────────────────────────────
        enc_rep = torch.cat([spec_out, conv_out], dim=-1)
        comb_out, s3a, s3b = self.combined_lstm(
            enc_rep, skip=enc_rep, state1=gs('s3a'), state2=gs('s3b')
        )

        # ── Post-split ───────────────────────────────────────────────────────
        spec_split, conv_split = torch.chunk(comb_out, 2, dim=-1)
        spec_post, s4a, s4b = self.post_spec_lstm(spec_split, state1=gs('s4a'), state2=gs('s4b'))
        conv_post, s5a, s5b = self.post_conv_lstm(conv_split, state1=gs('s5a'), state2=gs('s5b'))

        # ── Mask + decode (spectrogram branch — v12: complex mask) ────────────
        # Magnitude scale: unbounded above 0, clamped at mask_max to prevent
        # pathological early-training values.
        mag_raw   = self.spec_mag_head(spec_post)                    # (B, T, C*n_bins)
        mag_scale = F.softplus(mag_raw).clamp(max=self.mask_max)
        mag_scale = mag_scale.reshape(B, T, C, self.n_bins).permute(0, 2, 3, 1)
                                                                     # (B, C, n_bins, T)

        # ── Temporal mask smoothing ───────────────────────────────────────────
        # Causal moving average across T — only uses past frames, no lookahead.
        # Reduces frame-to-frame mask jitter ("musical noise" / watery artefacts)
        # without changing training behaviour (mask_smooth_frames defaults to 1).
        k = getattr(self, 'mask_smooth_frames', 1)
        if k > 1:
            # mag_scale: (B, C, n_bins, T) — flatten BxCxbins into one batch dim
            ms_flat = mag_scale.reshape(B * C * self.n_bins, 1, T)
            ms_flat = F.pad(ms_flat, (k - 1, 0))                    # causal left-pad
            mag_scale = F.avg_pool1d(ms_flat, kernel_size=k, stride=1, padding=0)
            mag_scale = mag_scale.reshape(B, C, self.n_bins, T)

        # Apply scale to mixture magnitude
        pred_mag  = mag * mag_scale                                  # (B, C, n_bins, T)

        # Phase rotation: cos and sin per bin, normalised onto the unit circle.
        phase_raw = self.spec_phase_head(spec_post)                  # (B, T, 2*C*n_bins)
        phase_cs  = phase_raw.reshape(B, T, 2, C, self.n_bins).permute(0, 3, 4, 1, 2)
        # phase_cs[..., 0] = cos_delta, phase_cs[..., 1] = sin_delta
        phase_norm  = torch.sqrt(
            phase_cs[..., 0].pow(2) + phase_cs[..., 1].pow(2) + 1e-8
        )
        cos_delta = phase_cs[..., 0] / phase_norm                    # (B, C, n_bins, T)
        sin_delta = phase_cs[..., 1] / phase_norm

        # Compose: predicted_complex = pred_mag · (mixture_phase · rotation)
        # mixture phase is unit-complex (phase = stft / |stft|)
        mix_re = phase.real
        mix_im = phase.imag
        # Rotation: (mix_re + i mix_im) · (cos + i sin)
        #         = (mix_re*cos - mix_im*sin) + i (mix_re*sin + mix_im*cos)
        rot_re = mix_re * cos_delta - mix_im * sin_delta
        rot_im = mix_re * sin_delta + mix_im * cos_delta
        pred_complex = torch.complex(pred_mag * rot_re, pred_mag * rot_im)
        wav_spec  = self.spec_decoder.forward_complex(pred_complex, L)

        # ── Mask + decode (conv branch — unbounded magnitude only) ───────────
        conv_mask_raw = self.conv_mask_head(conv_post)               # (B, T, n_basis)
        conv_mask     = F.softplus(conv_mask_raw).clamp(max=self.mask_max)
        conv_mask     = conv_mask.permute(0, 2, 1)                   # (B, n_basis, T)

        if k > 1:
            cm_flat   = F.pad(conv_mask, (k - 1, 0))                # causal left-pad
            conv_mask = F.avg_pool1d(cm_flat, kernel_size=k, stride=1, padding=0)
        wav_conv      = self.conv_decoder(conv_enc * conv_mask, L)

        vocals = wav_spec + wav_conv

        new_states = {
            's1a': s1a, 's1b': s1b,
            's2a': s2a, 's2b': s2b,
            's3a': s3a, 's3b': s3b,
            's4a': s4a, 's4b': s4b,
            's5a': s5a, 's5b': s5b,
        }

        # Diagnostic — capture peak mask values for the training loop to print
        # ("is the unbounded mask actually being used?").
        #
        # IMPORTANT: .item() forces a GPU→CPU sync of a scalar value.  Under
        # torch.compile (dynamo) that scalar is captured as a CONSTANT in the
        # graph; the next step the value changes, so dynamo recompiles —
        # eventually hitting `config.recompile_limit` and DISABLING the
        # compilation optimisation entirely.
        #
        # Fix: skip the diagnostic when compiling.  When --compile is on, the
        # user explicitly chose speed over diagnostics, which is the right
        # trade-off.  When --compile is off, masks_max prints normally.
        try:
            _compiling = torch.compiler.is_compiling()
        except AttributeError:
            _compiling = False   # older torch versions — fall back to recording

        if not _compiling:
            self._last_spec_mask_max = float(mag_scale.detach().max().item())
            self._last_conv_mask_max = float(conv_mask.detach().max().item())

        return vocals, new_states


# ---------------------------------------------------------------------------
# Stateful streaming wrapper (API-identical to v1)
# ---------------------------------------------------------------------------

class StatefulHSTasNetVocals:
    """
    Wraps HSTasNetVocals and persists LSTM hidden states across chunks.
    Use this for real-time streaming inference.

    The wrapper also applies a short linear cross-fade at every chunk boundary
    to eliminate the click / buzz artefact that otherwise occurs because
    torch.stft(center=True) reflect-pads the first win_length//2 = 512 samples
    of every independent chunk — producing a brief ISTFT reconstruction error
    at each boundary.  Cross-fading over 1024 samples (≈23 ms) is inaudible
    but completely covers the artefact window.

    Example:
        model    = HSTasNetVocals()
        streamer = StatefulHSTasNetVocals(model, device)
        vocal_chunk = streamer.process_chunk(audio_chunk)   # (2, L)
    """

    def __init__(
        self,
        model: HSTasNetVocals,
        device: torch.device,
        crossfade_samples: int = 1024,
        lookahead_frames: int = 0,
    ):
        self.model  = model.to(device).eval()
        self.device = device
        self.states = None
        # Cross-fade length in samples.  Default = model n_fft = 1024 samples ≈ 23 ms.
        # This fully covers the win_length//2 boundary region where center-padded
        # STFT frames use reflected audio instead of real context.
        self._crossfade: int          = crossfade_samples
        self._prev_tail: torch.Tensor = None   # (2, crossfade_samples)

        # ── Lookahead buffer (v12) ───────────────────────────────────────────
        # The LSTM itself is fundamentally causal — it cannot truly "see"
        # future audio.  This buffer therefore implements an OUTPUT-DELAY
        # form of lookahead: each chunk's vocals are held back by
        # `lookahead_frames × hop_length` samples before being emitted, so
        # the writer side has a consistent alignment cushion.  This is the
        # cheap, side-effect-free option.
        #
        # True "future-context" lookahead (re-running the LSTM on the next
        # chunk's first K frames to refine the current output) would require
        # checkpointing the LSTM state twice per call, which is non-trivial.
        # For now we leave the door open via `lookahead_frames=K` but the
        # quality effect is small — primarily useful for buffer alignment.
        hop = getattr(model, 'hop_length', 512)
        self._lookahead_samples: int    = max(0, lookahead_frames) * hop
        self._lookahead_buf: torch.Tensor = None   # (2, lookahead_samples)

    def reset(self):
        """Call when starting a new stream / new song."""
        self.states         = None
        self._prev_tail     = None
        self._lookahead_buf = None

    @torch.no_grad()
    def process_chunk(self, chunk: torch.Tensor) -> torch.Tensor:
        """
        chunk   : (2, L) float32 — one segment of stereo audio
        returns : (2, L) float32 — extracted vocals, boundary-smoothed

        How the cross-fade works
        ────────────────────────
        The STFT encoder pads each chunk with reflected audio at both edges
        (center=True).  This means the first ≈512 samples of every chunk's
        reconstructed output are computed from reflected — not real — context,
        causing a brief click/buzz at the boundary.

        To mask this: we linearly blend the FIRST `crossfade_samples` of the
        current output with the LAST `crossfade_samples` of the previous
        output.  The previous output was played correctly right up to its end;
        the cross-fade eases from that into the new chunk, hiding the artefact
        window entirely.
        """
        x = chunk.unsqueeze(0).to(self.device)              # (1, 2, L)
        vocals, self.states = self.model(x, self.states)
        vocals = vocals.squeeze(0).cpu()                     # (2, L)

        # ── Cross-fade at chunk boundary ─────────────────────────────────────
        # Cap at 12.5 % of chunk so very short chunks still work.
        fade = min(self._crossfade, vocals.shape[1] // 8)
        if self._prev_tail is not None and fade > 0:
            # t : 0 → 1 over 'fade' samples — new output fades IN
            t        = torch.linspace(0.0, 1.0, fade)
            fade_in  = t
            fade_out = 1.0 - t
            # Blend: start = prev tail (fading out) + new output (fading in)
            vocals[:, :fade] = (
                vocals[:, :fade] * fade_in
                + self._prev_tail * fade_out
            )

        # Save the last `fade` samples for the next boundary
        self._prev_tail = vocals[:, -fade:].clone() if fade > 0 else None

        # ── Lookahead output-delay buffer (v12) ──────────────────────────────
        # If lookahead is configured, hold back the early samples and emit
        # a delayed version.  The first call emits zeros for the delay
        # region (so the writer has audio to play immediately).
        if self._lookahead_samples > 0:
            if self._lookahead_buf is None:
                # First call — emit silence for the delay region, then audio
                self._lookahead_buf = torch.zeros(vocals.shape[0], self._lookahead_samples)
            full = torch.cat([self._lookahead_buf, vocals], dim=1)
            emit_len  = vocals.shape[1]
            emitted   = full[:, :emit_len]
            self._lookahead_buf = full[:, emit_len:].clone()
            return emitted

        return vocals