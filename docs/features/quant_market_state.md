# Causal Quantitative Market-State Feature Systems

This document specifies the Kalman Directional System (KDS), Robust Latent
Volatility System (RLVS), Latent Momentum Dynamics System (LMDS), and the
`quant_market_state` orchestrator in `src/features/systems/`. They are
model-agnostic point-in-time features, not a strategy. A value at closed bar
`t` may be executed no earlier than the next executable bar or quote.

## Common data and causality contract

Preferred input is complete bid/ask OHLC:
`bid_open`, `bid_high`, `bid_low`, `bid_close`, `ask_open`, `ask_high`,
`ask_low`, `ask_close`, with optional `spread_bps` and `tick_volume`.

\[
O_t=(O_t^{bid}+O_t^{ask})/2,\quad
H_t=(H_t^{bid}+H_t^{ask})/2,\quad
L_t=(L_t^{bid}+L_t^{ask})/2,\quad
C_t=(C_t^{bid}+C_t^{ask})/2.
\]

Fallback input is `open`, `high`, `low`, `close`, interpreted as midpoint-like
OHLC. A `pandas.DatetimeIndex` must be increasing and unique. Finite prices must
be positive; OHLC geometry and `ask >= bid` are validated. Invalid structure
raises rather than being repaired. NaNs are preserved. An isolated missing bar
causes prediction-only state propagation where a recursive state exists, but
does not create a fake measurement.

All contextual normalization baselines end at `t-1`. Current-bar OHLC
measurements and filter updates may include the fully closed bar `t`. There are
no centered windows, negative shifts, future fills, full-sample scalers, or
history-revising smoothers.

### Timestamp gaps and weekend boundaries

The systems assume M1 input but no longer assume every adjacent row is exactly
one minute apart. Elapsed minutes are computed from the timestamp index. A gap
of at least 30 minutes is a hard gap; a hard interval spanning Saturday or
Sunday is classified as an expected weekend/market gap, otherwise as an
unexpected data gap.

KDS uses `phi ** elapsed_minutes`. Small gaps propagate the level over elapsed
time, while hard gaps preserve the last level, strongly decay drift, and inflate
process uncertainty. RLVS similarly applies time-scaled mean reversion and
uncertainty. Cross-gap close returns are excluded from one-minute volatility.
LMDS acceleration, impulse, efficiency, and persistence never bridge a missing
minute; horizon features resume only after enough contiguous M1 bars exist.
The actual opening displacement is retained separately as
`qms_opening_gap_return`.

Notation:

- \(y_t=\log C_t\), \(r_t=y_t-y_{t-1}\).
- \(\epsilon\) is the configured numerical floor.
- `EWM_span(x)` is pandas `ewm(span=..., adjust=False)`.
- \(B^W_{t-1}(x)\) is `x.rolling(W).median().shift(1)`.
- \(\Phi\) and \(\varphi\) are standard-normal CDF and density.

## Configuration and M1 Forex presets

Builders accept `preset: conservative|balanced|responsive` plus an optional
typed config or override mapping. Unknown fields, non-finite numbers, invalid
windows, and weights that do not sum to one fail closed. Presets contain no
pair-specific optimized values.

### KDS parameters

| Field | Conservative | Balanced | Responsive | Meaning |
|---|---:|---:|---:|---|
| `phi` | .990 | .985 | .970 | Drift persistence |
| `level_process_noise_multiplier` | .025 | .05 | .10 | Level process variance/local variance |
| `drift_process_noise_multiplier` | .0025 | .005 | .012 | Drift process variance/local variance |
| `observation_noise_multiplier` | .75 | .50 | .35 | Base observation variance |
| `spread_noise_multiplier` | 1.50 | 1.00 | .75 | Elevated-spread penalty |
| `volatility_noise_multiplier` | 1.00 | .75 | .50 | Elevated-volatility penalty |
| `huber_threshold` | 2.5 | 3.0 | 3.5 | Innovation clip in predicted SD |
| `local_volatility_span` | 60 | 30 | 15 | Squared-return EWM span |
| `local_volatility_min_periods` | 10 | 5 | 3 | Local-vol warm-up |
| `volatility_baseline_window` | 2880 | 1440 | 720 | Prior local-vol median |
| `spread_baseline_window` | 2880 | 1440 | 720 | Prior spread median |
| `kadx_window` | 28 | 14 | 7 | Wilder KDX smoothing |
| `activity_scale` | 1.25 | 1.00 | .80 | Drift/volatility magnitude scale |
| `initial_covariance_multiplier` | 10 | 10 | 8 | Initial state covariance scale |
| `min_directional_activity` | 1e-8 | 1e-8 | 1e-8 | Neutral/activity threshold |
| `epsilon` | 1e-12 | 1e-12 | 1e-12 | Numerical floor |

### RLVS parameters

| Field | Conservative | Balanced | Responsive | Meaning |
|---|---:|---:|---:|---|
| `phi_vol` | .992 | .985 | .960 | Log-variance persistence |
| `process_noise` | .0125 | .025 | .060 | State-process variance |
| `measurement_noise` | .30 | .20 | .14 | Base measurement variance |
| `spread_noise_multiplier` | 1.00 | .75 | .50 | Spread penalty |
| `disagreement_noise_multiplier` | .75 | .50 | .35 | Estimator-disagreement penalty |
| `anomaly_noise_multiplier` | .40 | .25 | .15 | Elevated-range penalty |
| `huber_threshold` | 2.5 | 3.0 | 3.5 | Innovation clip |
| `measurement_span` | 30 | 15 | 7 | Per-estimator EWM |
| `measurement_min_periods` | 6 | 3 | 2 | Measurement warm-up |
| `state_baseline_span` | 2880 | 1440 | 720 | Prior state-equation mean |
| `spread_baseline_window` | 2880 | 1440 | 720 | Prior spread median |
| `range_baseline_window` | 2880 | 1440 | 720 | Prior log-range median |
| `regime_baseline_span` | 2880 | 1440 | 720 | Filtered-state regime baseline |
| `regime_min_periods` | 120 | 60 | 30 | Regime/VoV warm-up |
| `vol_of_vol_span` | 60 | 30 | 15 | Squared state-change EWM |
| `vol_of_vol_baseline_span` | 1440 | 720 | 360 | Prior VoV baseline |
| `sigma_fast_span` | 30 | 15 | 7 | Fast state EWM |
| `sigma_slow_span` | 480 | 240 | 120 | Slow state EWM |
| `initial_state_variance` | 1 | 1 | 1 | Initial posterior variance |
| `min_log_variance`, `max_log_variance` | -50,5 | -50,5 | -50,5 | Numerical state bounds |
| `transition_vol_of_vol_ratio` | 1.75 | 1.50 | 1.25 | Transition threshold |
| `low_regime_z`, `high_regime_z` | -1,1 | -1,1 | -1,1 | Regime boundaries |
| `extreme_regime_z`, `extreme_shock_z` | 2.5,3 | 2.5,3 | 2.5,3 | Extreme thresholds |
| `epsilon` | 1e-12 | 1e-12 | 1e-12 | Numerical floor |

### LMDS parameters

| Field | Conservative | Balanced | Responsive | Meaning |
|---|---|---|---|---|
| `impulse_horizons` | 3,5,15,30,60 | same | same | Required horizons |
| `impulse_weights` | .05,.15,.30,.30,.20 | .10,.20,.30,.25,.15 | .20,.25,.30,.15,.10 | Impulse/breadth weights |
| `efficiency_horizons` | 5,15,30 | same | same | Efficiency horizons |
| `efficiency_weights` | .15,.40,.45 | .25,.40,.35 | .40,.40,.20 | Efficiency weights |
| `momentum_weights` | .55,.20,.25 | .50,.30,.20 | .45,.40,.15 | Impulse, acceleration, breadth |
| `impulse_scale` | 2.0 | 1.5 | 1.0 | Impulse tanh scale |
| `acceleration_scale` | 2.5 | 2.0 | 1.5 | Acceleration tanh scale |
| `exhaustion_scale` | 2.5 | 2.0 | 1.5 | Displacement tanh scale |
| `raw_impulse_clip` | 20 | 20 | 20 | Internal nonlinear-input clip |
| `persistence_span`, `persistence_min_periods` | 30,6 | 15,3 | 7,2 | Signed-return EWM |
| `exhaustion_shock_weight` | .25 | .25 | .30 | Shock loading |
| `exhaustion_vol_of_vol_weight` | .15 | .15 | .20 | VoV loading |
| `exhaustion_shock_scale` | 3 | 3 | 2.5 | Shock tanh scale |
| `exhaustion_vol_of_vol_scale` | 1 | 1 | .75 | Excess-VoV tanh scale |
| `direction_epsilon` | 1e-6 | 1e-6 | 1e-6 | Neutral-score threshold |
| `epsilon` | 1e-12 | 1e-12 | 1e-12 | Numerical floor |

## Kalman Directional System (KDS)

### Purpose, intuition, and formulas

KDS replaces price-difference directional movement with the posterior drift and
uncertainty of a robust local-linear-trend model. It separates direction,
posterior confidence, magnitude relative to local volatility, and measurement
reliability.

\[
x_t=[\ell_t,\beta_t]^T,\quad
F=\begin{bmatrix}1&1\\0&\phi\end{bmatrix},\quad H=[1,0].
\]

Let \(v_t=EWM(r_t^2)\), \(\sigma_t=\sqrt{v_t}\),
\(\rho_t^\sigma=\sigma_t/(B_{t-1}(\sigma)+\epsilon)\), and
\(\rho_t^s=s_t^{bps}/(B_{t-1}(s^{bps})+\epsilon)\). Zero over a zero baseline
is defined as one.

\[
Q_t=\operatorname{diag}(q_\ell v_t,q_\beta v_t),
\]
\[
R_t=r_0v_t\{1+\lambda_s[\max(\rho_t^s-1,0)]^2+
\lambda_\sigma[\max(\rho_t^\sigma-1,0)]^2\}.
\]

With raw innovation \(e_t=y_t-Hx_{t|t-1}\) and
\(S_t=HP_{t|t-1}H^T+R_t\), the update uses
\(\tilde e_t=clip(e_t,\pm c\sqrt{S_t})\). The reported innovation remains raw.
\(K_t=P_{t|t-1}H^T/S_t\), and covariance uses Joseph form:

\[
P_{t|t}=(I-KH)P_{t|t-1}(I-KH)^T+K R_t K^T.
\]

For drift \(m_t=\beta_t\), \(s_t=\sqrt{P_{\beta\beta,t}}\),
\(z_t=m_t/(s_t+\epsilon)\):

\[
p_t^+=\Phi(z_t),\quad E_t^+=s_t\varphi(z_t)+m_t\Phi(z_t),\quad
E_t^-=s_t\varphi(z_t)-m_t\Phi(-z_t).
\]

Negative floating errors are clamped to zero. Shares are
\(w_t^+=E_t^+/(E_t^++E_t^-)\), \(w_t^-=1-w_t^+\), or 0.5/0.5 when evidence is
negligible.

\[
c_t=|2p_t^+-1|,\quad
g_t=\tanh\{|m_t|/(a\sigma_t+\epsilon)\},\quad A_t=c_tg_t,
\]
\[
KDI_t^+=100A_tw_t^+,\quad KDI_t^-=100A_tw_t^-.
\]

KDX is `100*abs(KDI+-KDI-)/(KDI++KDI-+epsilon)` and is explicitly zero when
total activity is below the configured threshold. KADX is classic
SMA-seeded Wilder smoothing. `ktrend_score =
sign(m)*(kadx/100)*kdi_activity`, clipped to `[-1,1]`.

### KDS output reference: definition and availability

`M` = midpoint close, `S` = spread, `K` = KDS state.

| Column | System | Exact definition | dtype | Range | Units | Directionality | Causal availability | Inputs |
|---|---|---|---|---|---|---|---|---|
| `kalman_level` | KDS | Posterior \(\ell_{t|t}\) | float64 | real | log price | level | close t | M,S |
| `kalman_drift` | KDS | Posterior \(m_t=\beta_{t|t}\) | float64 | real | log return/bar | signed | close t | M,S |
| `kalman_drift_std` | KDS | \(\sqrt{P_{\beta\beta,t}}\) | float64 | `[0,inf)` | log return/bar | uncertainty | close t | K |
| `kalman_drift_z` | KDS | \(m_t/(s_t+\epsilon)\) | float64 | real | posterior SD | signed | close t | K |
| `kalman_prob_up` | KDS | \(\Phi(z_t)\) | float64 | `[0,1]` | probability | higher=up | close t | K |
| `kalman_innovation` | KDS | Raw \(y_t-Hx_{t|t-1}\) | float64 | real | log price | signed surprise | close t | M,K |
| `kalman_innovation_z` | KDS | Raw innovation `/sqrt(S_t)` | float64 | real | predicted SD | signed surprise | close t | M,S,K |
| `kdi_activity` | KDS | \(A_t=c_tg_t\) | float64 | `[0,1]` | fraction | unsigned | local-vol warm-up | K,M |
| `kdi_plus` | KDS | \(100A_tw_t^+\) | float64 | `[0,100]` | index | positive | close t | K,M |
| `kdi_minus` | KDS | \(100A_tw_t^-\) | float64 | `[0,100]` | index | negative | close t | K,M |
| `kdx` | KDS | Guarded KDI imbalance | float64 | `[0,100]` | index | unsigned | close t | KDI |
| `kadx` | KDS | Wilder-smoothed KDX | float64 | `[0,100]` | index | unsigned | after seed | KDX |
| `kadx_signed` | KDS | `sign(kalman_drift)*kadx` | float64 | `[-100,100]` | index | signed | after seed | K,KADX |
| `ktrend_score` | KDS | `clip(sign(m)*(kadx/100)*activity)` | float64 | `[-1,1]` | score | signed | after seed | K,KADX |
| `ktrend_direction` | KDS | Thresholded `sign(m)` | float64 | `{-1,0,1}` | direction | signed | close t | K |
| `ktrend_confidence` | KDS | \(|2\Phi(z_t)-1|\) | float64 | `[0,1]` | posterior-derived | unsigned | close t | K |
| `ktrend_uncertainty` | KDS | \(s_t/(|m_t|+s_t+\epsilon)\) | float64 | `[0,1]` | fraction | higher=uncertain | close t | K |
| `local_realized_volatility` | KDS | \(\sqrt{EWM(r_t^2)}\) | float64 | `[0,inf)` | log return/bar | unsigned | local-vol warm-up | M |
| `spread_ratio` | KDS | \(s_t^{bps}/(B_{t-1}(s)+\epsilon)\) | float64 | `[0,inf)` | ratio | higher=wider | prior baseline | S |
| `volatility_ratio` | KDS | \(\sigma_t/(B_{t-1}(\sigma)+\epsilon)\) | float64 | `[0,inf)` | ratio | higher=volatile | prior baseline | M |

### KDS output reference: interpretation and use

The `H/L/0` cell gives high-value, low-value, and zero-value interpretation.

| Column | Interpretation; H/L/0 | Failure modes | Spread sensitivity | Vol sensitivity | ML use | Rule use | Redundancy | Replaces/complements | Type |
|---|---|---|---|---|---|---|---|---|---|
| `kalman_level` | Smoothed log price; high/low are scale; 0 N/A | unit root, stale gaps | indirect | moderate | usually omit/difference | anchor | close, MA | EMA | raw |
| `kalman_drift` | H positive up; L negative down; 0 flat | filter lag | update attenuated | adaptive | scale first | direction | drift-z, score | EMA slope | raw |
| `kalman_drift_std` | H uncertain; L precise; 0 degenerate | noise misspecification | rises | rises | diagnostic | confidence gate | uncertainty | ADX reliability | diagnostic |
| `kalman_drift_z` | H strong up; L strong down; 0 neutral | Gaussian assumption | attenuated | adjusted | recommended | validated threshold | probability | signed ADX/PPO | normalized |
| `kalman_prob_up` | H up; L down; .5 neutral | uncalibrated | attenuated | adjusted | calibrate | diagnostic | drift-z/confidence | +DI share | probabilistic |
| `kalman_innovation` | H above prediction; L below; 0 expected | price regime | reported raw | direct | diagnostic | anomaly | innovation-z | EMA residual | raw |
| `kalman_innovation_z` | H positive surprise; L negative; 0 expected | wrong noise model | adjusted | adjusted | recommended | shock flag | RLVS shock | z residual | normalized |
| `kdi_activity` | H usable activity; L weak; 0 inactive | low-vol floor | attenuated | normalized | recommended | activity gate | KDI sum/score | DI magnitude | composite |
| `kdi_plus` | H positive activity; L weak; 0 none | activity lag | attenuated | normalized | omit with both shares | display | KDI-/activity | +DI | composite |
| `kdi_minus` | H negative activity; L weak; 0 none | activity lag | attenuated | normalized | omit with both shares | display | KDI+/activity | -DI | composite |
| `kdx` | H one-sided; L mixed; 0 inactive/balanced | raw noise | indirect | normalized | prefer KADX | purity gate | KDI shares | DX | normalized |
| `kadx` | H persistent strength; L weak; 0 none | Wilder lag | indirect | normalized | pair with direction | strength gate | signed KADX | ADX | normalized |
| `kadx_signed` | H strong up; L strong down; 0 weak | sign chatter | indirect | normalized | alternative score | signed strength | KADX+sign | signed ADX | composite |
| `ktrend_score` | H strong up; L strong down; 0 absent | compound lag | attenuated | normalized | recommended | principal score | activity/KADX | signed ADX/PPO | composite |
| `ktrend_direction` | H +1; L -1; 0 neutral | threshold chatter | attenuated | indirect | categorical/diagnostic | direction filter | score sign | +DI vs -DI | diagnostic |
| `ktrend_confidence` | H certain; L/0 neutral | uncalibrated | attenuated | adjusted | useful, redundant | confidence gate | probability/z | ADX complement | probabilistic |
| `ktrend_uncertainty` | H uncertain; L/0 precise | covariance model | increases | increases | diagnostic | veto | drift std/z | none direct | diagnostic |
| `local_realized_volatility` | H active; L quiet; 0 flat | microstructure | can contaminate | direct | prefer RLVS sigma | risk context | RLVS sigma | rolling vol | raw |
| `spread_ratio` | H wide; L tight; 1 baseline | missing spread | direct | low | recommended control | cost gate | cost model | spread filter | normalized |
| `volatility_ratio` | H expansion; L compression; 1 baseline | short history | indirect | direct | regime control | risk gate | RLVS regime | vol ratio | normalized |

These are model-implied posterior probabilities under the state-space
assumptions. They are not guaranteed empirical forecast probabilities unless
independently calibrated.

### KDS warm-up, missing data, and validation

The state initializes on the first finite close. Local volatility waits for its
minimum periods; ratios wait for prior baselines; KADX waits for a full seed.
A missing close performs prediction only and reports no innovation. Validate
prefix invariance, spread-spike attenuation, state recovery, covariance
positivity, and session gaps. Recommended ML subset: `ktrend_score`,
`kalman_drift_z`, `kdi_activity`, `kalman_innovation_z`. Do not use all KDI,
KDX, and KADX derivatives together.

## Robust Latent Volatility System (RLVS)

### Purpose, intuition, and formulas

RLVS treats close-to-close, Parkinson, and Rogers-Satchell estimators as noisy
measurements of a latent log-variance state. Estimator disagreement, abnormal
range, and spread raise measurement uncertainty.

\[
v_t^{cc}=\log(C_t/C_{t-1})^2,\quad
v_t^{PK}=\log(H_t/L_t)^2/(4\log 2),
\]
\[
v_t^{RS}=\log(H_t/O_t)\log(H_t/C_t)+
\log(L_t/O_t)\log(L_t/C_t).
\]

RS is clamped at zero for floating-point negatives. Each variance is smoothed
separately. With \(\tilde v_t^j=EWM(v_t^j)\):

\[
z_t^{obs}=\operatorname{median}_j\log(\tilde v_t^j+\epsilon),\quad
d_t=\operatorname{std}_j\log(\tilde v_t^j+\epsilon).
\]

At least two current measurements are required. Smoothed values are masked when
their current raw component is missing, so a stale EWM value cannot become a
new measurement.

\[
h_{t|t-1}=\mu_t+\phi_v(h_{t-1|t-1}-\mu_t),\quad
P_{t|t-1}=\phi_v^2P_{t-1|t-1}+q_v,
\]

where \(\mu_t=EWM(z^{obs})_{t-1}\). Let \(\rho_t^r\) be current log range
divided by its prior median. Then

\[
R_t=r_v\{1+\lambda_s[\max(\rho_t^s-1,0)]^2+
\lambda_d d_t^2+\lambda_a[\max(\rho_t^r-1,0)]^2\}.
\]

The scalar filter uses a Huber-clipped innovation and scalar Joseph covariance.
The reported innovation is raw. State is clipped only to the documented
`[min_log_variance,max_log_variance]` interval.

For prior-only regime baseline \(b_t=EWM(h)_{t-1}\), dispersion
\(s_{b,t}=EWMStd(h)_{t-1}\):

\[
z_t^{reg}=(h_t-b_t)/\sqrt{s_{b,t}^2+P_t+\epsilon},\quad
p_t^{high}=\Phi(z_t^{reg}).
\]

\[
VoV_t=\sqrt{EWM((h_t-h_{t-1})^2)},\quad
VoVR_t=VoV_t/(EWM(VoV)_{t-1}+\epsilon).
\]

Fast/slow sigma use EWM-filtered \(h_t\):
\(\sigma_t^{fast}=\exp(EWM_{fast}(h_t)/2)\), likewise slow. Model-free
forecasts are \(\sigma_t\sqrt H\); expected move is \(C_t\sigma_t\sqrt H\).

### RLVS output reference: definition and availability

`M` = midpoint OHLC, `S` = spread, `R` = RLVS state.

| Column | System | Exact definition | dtype | Range | Units | Directionality | Causal availability | Inputs |
|---|---|---|---|---|---|---|---|---|
| `rlv_log_variance` | RLVS | Filtered \(h_{t|t}\) | float64 | `[-50,5]` | log variance/bar | unsigned level | measurement warm-up | M,S |
| `rlv_variance` | RLVS | \(\exp(h_t)\) | float64 | `[0,exp(5)]` | variance/bar | unsigned | same | R |
| `rlv_sigma` | RLVS | \(\sqrt{\exp(h_t)}\) | float64 | `[0,exp(2.5)]` | return SD/bar | unsigned | same | R |
| `rlv_state_std` | RLVS | \(\sqrt{P_t}\) | float64 | `[0,inf)` | log-variance units | uncertainty | same | R |
| `rlv_state_uncertainty` | RLVS | \(\sqrt P/(|h-b|+\sqrt P+\epsilon)\) | float64 | `[0,1]` | fraction | higher=uncertain | regime warm-up | R |
| `rlv_regime_baseline` | RLVS | \(EWM(h)_{t-1}\) | float64 | real | log variance | level | prior-only | R |
| `rlv_regime_dispersion` | RLVS | \(EWMStd(h)_{t-1}\) | float64 | `[0,inf)` | log variance | unsigned | prior-only | R |
| `rlv_regime_z` | RLVS | \((h-b)/sqrt(s_b²+P+\epsilon)\) | float64 | real | posterior SD | higher=high vol | current vs prior | R |
| `rlv_prob_high` | RLVS | \(\Phi(rlv\_regime\_z)\) | float64 | `[0,1]` | probability | higher=high vol | same | R |
| `rlv_innovation` | RLVS | Raw \(z_t^{obs}-h_{t|t-1}\) | float64 | real | log variance | signed shock | current OHLC | M,R |
| `rlv_shock_z` | RLVS | Innovation `/sqrt(P_pred+R)` | float64 | real | predicted SD | signed shock | current OHLC | M,S,R |
| `rlv_vol_of_vol` | RLVS | \(\sqrt{EWM(\Delta h²)}\) | float64 | `[0,inf)` | log-var change | unsigned | VoV warm-up | R |
| `rlv_vol_of_vol_ratio` | RLVS | `VoV/prior EWM(VoV)` | float64 | `[0,inf)` | ratio | higher=unstable | prior baseline | R |
| `rlv_sigma_fast` | RLVS | \(\exp(EWM_{fast}(h)/2)\) | float64 | `[0,exp(2.5)]` | return SD/bar | unsigned | current state | R |
| `rlv_sigma_slow` | RLVS | \(\exp(EWM_{slow}(h)/2)\) | float64 | `[0,exp(2.5)]` | return SD/bar | unsigned | current state | R |
| `rlv_fast_slow_ratio` | RLVS | \(\sigma^{fast}/(\sigma^{slow}+\epsilon)\) | float64 | `[0,inf)` | ratio | >1 expansion | current state | R |
| `rlv_term_structure` | RLVS | \(\log(rlv\_fast\_slow\_ratio)\) | float64 | real | log ratio | signed | current state | R |
| `rlv_forecast_5` | RLVS | \(\sigma_t\sqrt5\) | float64 | `[0,inf)` | return SD/5 bars | unsigned | close t | R |
| `rlv_forecast_15` | RLVS | \(\sigma_t\sqrt{15}\) | float64 | `[0,inf)` | return SD/15 bars | unsigned | close t | R |
| `rlv_forecast_30` | RLVS | \(\sigma_t\sqrt{30}\) | float64 | `[0,inf)` | return SD/30 bars | unsigned | close t | R |
| `rlv_expected_move_5` | RLVS | \(C_t\,rlv\_forecast_5\) | float64 | `[0,inf)` | price units | unsigned | close t | M,R |
| `rlv_expected_move_15` | RLVS | \(C_t\,rlv\_forecast_{15}\) | float64 | `[0,inf)` | price units | unsigned | close t | M,R |
| `rlv_expected_move_30` | RLVS | \(C_t\,rlv\_forecast_{30}\) | float64 | `[0,inf)` | price units | unsigned | close t | M,R |
| `rlv_regime` | RLVS | Thresholds on regime-z, shock-z, VoV ratio | string | five labels | category | categorical | regime warm-up | R |
| `volatility_estimator_disagreement` | RLVS | Cross-estimator SD in log-variance space | float64 | `[0,inf)` | log variance | higher=conflict | current OHLC | M |

### RLVS output reference: interpretation and use

| Column | Interpretation; H/L/0 | Failure modes | Spread sensitivity | Vol sensitivity | ML use | Rule use | Redundancy | Replaces/complements | Type |
|---|---|---|---|---|---|---|---|---|---|
| `rlv_log_variance` | H risky; L quiet; 0 scale-specific | bounds/filter lag | update adjusted | direct | scale-aware only | diagnostic | variance/sigma | log rolling variance | raw |
| `rlv_variance` | H large variance; L quiet; 0 flat | floor/bounds | indirect | direct | usually omit | risk math | sigma/log-var | realized variance | raw |
| `rlv_sigma` | H large moves; L quiet; 0 flat | horizon assumption | indirect | direct | scaling feature | sizing/stops | forecasts | rolling std/ATR% | raw |
| `rlv_state_std` | H imprecise; L/0 precise | noise model | rises | rises | diagnostic | confidence gate | uncertainty | none direct | diagnostic |
| `rlv_state_uncertainty` | H uncertain; L/0 displacement dominates | baseline lag | rises | rises | recommended | risk veto | state std/z | none direct | diagnostic |
| `rlv_regime_baseline` | Slow prior norm; high/low contextual | breaks | indirect | direct | usually omit | reference | log-var | long rolling vol | raw |
| `rlv_regime_dispersion` | H unstable norm; L/0 stable | short history | indirect | direct | diagnostic | threshold scale | state std/VoV | vol-of-vol | diagnostic |
| `rlv_regime_z` | H high regime; L low; 0 normal | nonstationary baseline | adjusted | direct | recommended | regime gate | probability/regime | vol z/percentile | normalized |
| `rlv_prob_high` | H high-vol; L low-vol; .5 neutral | uncalibrated | adjusted | direct | calibrate | diagnostic | regime-z | vol percentile | probabilistic |
| `rlv_innovation` | H expansion; L compression; 0 expected | estimator bias | reported raw | direct | diagnostic | shock event | shock-z | ATR/vol change | raw |
| `rlv_shock_z` | H expansion shock; L compression; 0 expected | wrong R/Q | adjusted | direct | recommended | shock gate | innovation | z-scored vol shock | normalized |
| `rlv_vol_of_vol` | H changing regime; L/0 stable | state clipping | indirect | direct | prefer ratio | risk monitor | ratio | rolling VoV | raw |
| `rlv_vol_of_vol_ratio` | H >1 unstable; L <1 stable; 1 baseline | short baseline | indirect | direct | recommended | transition gate | raw VoV | VoV ratio | normalized |
| `rlv_sigma_fast` | H current risk; L quiet; 0 flat | microstructure | adjusted | direct | one term only | fast risk | slow/ratio | short vol | raw |
| `rlv_sigma_slow` | H sustained risk; L quiet; 0 flat | lag | adjusted | direct | one term only | slow risk | fast/ratio | long vol | raw |
| `rlv_fast_slow_ratio` | H >1 expansion; L <1 compression; 1 equal | near floor | adjusted | direct | recommended | structure gate | term structure | short/long vol | normalized |
| `rlv_term_structure` | H positive expansion; L negative; 0 equal | same | adjusted | direct | ratio alternative | signed gate | ratio | log vol ratio | normalized |
| `rlv_forecast_5` | H larger 5-bar risk; L/0 small | sqrt-time model | indirect | direct | horizon match | sizing | sigma/other H | vol×sqrt5 | composite |
| `rlv_forecast_15` | H larger 15-bar risk; L/0 small | sqrt-time model | indirect | direct | recommended | sizing | sigma/other H | vol×sqrt15 | composite |
| `rlv_forecast_30` | H larger 30-bar risk; L/0 small | sqrt-time model | indirect | direct | horizon match | sizing | sigma/other H | vol×sqrt30 | composite |
| `rlv_expected_move_5` | H large price move; L/0 small | price-scale | indirect | direct | normalize first | stop reference | forecast×price | ATR horizon | composite |
| `rlv_expected_move_15` | H large price move; L/0 small | price-scale | indirect | direct | normalize first | stop reference | forecast×price | ATR horizon | composite |
| `rlv_expected_move_30` | H large price move; L/0 small | price-scale | indirect | direct | normalize first | stop reference | forecast×price | ATR horizon | composite |
| `rlv_regime` | H extreme/high; L low; zero N/A | threshold sensitivity | adjusted | direct | encode cautiously | monitoring | regime-z/prob | vol regime | diagnostic |
| `volatility_estimator_disagreement` | H unreliable; L/0 agreement | common bias | can rise | anomaly-sensitive | diagnostic/control | reliability gate | range anomaly | estimator spread | diagnostic |

These are model-implied posterior probabilities under the state-space
assumptions. They are not guaranteed empirical forecast probabilities unless
independently calibrated.

### Optional HAR forecaster

`HARVolatilityForecaster` is deliberately outside the registry builder. Its
design is current filtered log variance plus trailing means over configured
windows (defaults 5, 15, 60, 240). `fit(training_frame)` constructs only labels
whose `t+h` endpoint remains inside that supplied training frame and fits a
ridge-stabilized linear model. `transform` never refits and returns
`exp(predicted_log_variance/2)*sqrt(horizon)`. Supply prior feature history with
validation rows so rolling design windows are available.

### RLVS warm-up, missing data, and validation

The state starts once two current smoothed estimators exist. A missing
measurement gives prediction only. Regime, VoV ratio, and labels have longer
warm-ups. Validate expansion/compression, range outliers, spread spikes,
disagreement, recovery, and forecast coverage. Recommended ML subset:
`rlv_regime_z`, `rlv_shock_z`, `rlv_vol_of_vol_ratio`,
`rlv_fast_slow_ratio`, `rlv_forecast_15`, `rlv_state_uncertainty`. Do not
normally combine log variance, variance, sigma, all forecasts, and all expected
moves.

## Latent Momentum Dynamics System (LMDS)

### Purpose, distinction from trend, and formulas

KDS estimates latent drift. LMDS measures drift change, volatility-scaled
displacement, cross-horizon agreement, path quality, persistence, exhaustion,
and pressure against that trend. It consumes KDS/RLVS outputs and never
recomputes their states.

\[
a_t=\beta_t-\beta_{t-1},\quad
z_t^a=a_t/\sqrt{s_{\beta,t}^2+s_{\beta,t-1}^2+\epsilon},\quad
\tilde a_t=\tanh(z_t^a/a_{scale}).
\]

Cross-time drift covariance is not exposed, so the variance approximation
conservatively omits it.

For \(h\in\{3,5,15,30,60\}\):

\[
I_t^h=\log(C_t/C_{t-h})/(\hat\sigma_t^h+\epsilon).
\]

RLVS forecasts are used for 5/15/30; \(\sigma_t\sqrt h\) is used for 3/60.
Raw \(I_t^h\) is reported. Only nonlinear composite inputs are clipped.

\[
I_t=\sum_h w_h\tanh(I_t^h/i_{scale}),\quad
B_t=\sum_h w_h\tanh(I_t^h).
\]
\[
E_t^h=\frac{|C_t-C_{t-h}|}
{\sum_{j=t-h+1}^{t}|C_j-C_{j-1}|+\epsilon},\quad
E_t=\sum_h u_hE_t^h.
\]

Persistence \(P_t\) is the causal EWM mean of signed one-bar returns, explicitly
zero for neutral composite impulse. It is signed: persistent downside
approaches -1.

\[
A_t^M=|I_t|\frac{1+|B_t|}{2}E_t,\quad
M_t^+=100A_t^M(1+I_t)/2,\quad M_t^-=100A_t^M(1-I_t)/2.
\]
\[
R_t^M=w_I I_t+w_a\tilde a_t+w_BB_t,\quad
Q_t^M=\sqrt{E_t(1+|P_t|)/2},\quad
Score_t^M=\tanh(R_t^M)Q_t^M.
\]

Base exhaustion is

\[
\tanh(|I_t^{15}|/e_{scale})
\max(0,-sign(I_t)\tilde a_t)(1-E_t),
\]

multiplied by one plus bounded RLVS shock and excess-VoV loadings, then clipped
to `[0,1]`.

### LMDS output reference: definition and availability

`M` = midpoint close, `K` = KDS outputs, `R` = RLVS outputs.

| Column | System | Exact definition | dtype | Range | Units | Directionality | Causal availability | Inputs |
|---|---|---|---|---|---|---|---|---|
| `lmom_acceleration` | LMDS | \(\beta_t-\beta_{t-1}\) | float64 | real | log return/bar² | signed | close t | K |
| `lmom_acceleration_z` | LMDS | \(a_t/sqrt(s_t²+s_{t-1}²+\epsilon)\) | float64 | real | approximate SD | signed | close t | K |
| `lmom_acceleration_score` | LMDS | \(\tanh(z_a/a_{scale})\) | float64 | `[-1,1]` | score | signed | close t | K |
| `lmom_impulse_3` | LMDS | \(\log(C_t/C_{t-3})/(\sigma_t\sqrt3+\epsilon)\) | float64 | real | vol units | signed | close t | M,R |
| `lmom_impulse_5` | LMDS | \(\log(C_t/C_{t-5})/(forecast_5+\epsilon)\) | float64 | real | vol units | signed | close t | M,R |
| `lmom_impulse_15` | LMDS | \(\log(C_t/C_{t-15})/(forecast_{15}+\epsilon)\) | float64 | real | vol units | signed | close t | M,R |
| `lmom_impulse_30` | LMDS | \(\log(C_t/C_{t-30})/(forecast_{30}+\epsilon)\) | float64 | real | vol units | signed | close t | M,R |
| `lmom_impulse_60` | LMDS | \(\log(C_t/C_{t-60})/(\sigma_t\sqrt{60}+\epsilon)\) | float64 | real | vol units | signed | close t | M,R |
| `lmom_impulse` | LMDS | Weighted bounded impulses \(I_t\) | float64 | `[-1,1]` | score | signed | after 60 bars | M,R |
| `lmom_breadth` | LMDS | Weighted \(\tanh(I_t^h)\) | float64 | `[-1,1]` | agreement | signed | after 60 bars | M,R |
| `lmom_efficiency_5` | LMDS | \(E_t^5\) | float64 | `[0,1]` | fraction | unsigned | after 5 bars | M |
| `lmom_efficiency_15` | LMDS | \(E_t^{15}\) | float64 | `[0,1]` | fraction | unsigned | after 15 bars | M |
| `lmom_efficiency_30` | LMDS | \(E_t^{30}\) | float64 | `[0,1]` | fraction | unsigned | after 30 bars | M |
| `lmom_efficiency` | LMDS | Weighted \(E_t\) | float64 | `[0,1]` | fraction | unsigned | after 30 bars | M |
| `lmom_persistence` | LMDS | Neutral-aware EWM mean of `sign(r_t)` | float64 | `[-1,1]` | signed fraction | signed | persistence warm-up | M |
| `lmom_activity` | LMDS | \(A_t^M\) | float64 | `[0,1]` | fraction | unsigned | composite warm-up | M,K,R |
| `lmom_plus` | LMDS | \(100A_t^M(1+I_t)/2\) | float64 | `[0,100]` | index | positive | same | M,K,R |
| `lmom_minus` | LMDS | \(100A_t^M(1-I_t)/2\) | float64 | `[0,100]` | index | negative | same | M,K,R |
| `lmom_strength` | LMDS | `plus+minus=100*activity` | float64 | `[0,100]` | index | unsigned | same | M,K,R |
| `lmom_score` | LMDS | \(\tanh(R_t^M)Q_t^M\) | float64 | `[-1,1]` | score | signed | composite warm-up | M,K,R |
| `lmom_exhaustion` | LMDS | Bounded displacement×opposition×inefficiency×risk load | float64 | `[0,1]` | score | higher=exhausted | composite warm-up | M,K,R |
| `lmom_reversal_pressure` | LMDS | `max(0,-sign(ktrend)*lmom_score)`; neutral trend→0 | float64 | `[0,1]` | score | counter-trend | composite warm-up | K,LMDS |
| `lmom_divergence` | LMDS | `lmom_score-ktrend_score` | float64 | `[-2,2]` | difference | signed | composite warm-up | K,LMDS |
| `lmom_alignment` | LMDS | `lmom_score*ktrend_score` | float64 | `[-1,1]` | product | + aligned | composite warm-up | K,LMDS |
| `lmom_direction` | LMDS | Thresholded `sign(lmom_score)` | float64 | `{-1,0,1}` | direction | signed | composite warm-up | LMDS |

### LMDS output reference: interpretation and use

| Column | Interpretation; H/L/0 | Failure modes | Spread sensitivity | Vol sensitivity | ML use | Rule use | Redundancy | Replaces/complements | Type |
|---|---|---|---|---|---|---|---|---|---|
| `lmom_acceleration` | H positive acceleration; L negative; 0 unchanged | covariance omitted | via KDS | indirect | scale first | diagnostic | acceleration-z | MACD histogram | raw |
| `lmom_acceleration_z` | H strong positive change; L negative; 0 none | conservative variance | via KDS | adjusted | recommended | validated threshold | score | PPO/MACD hist z | normalized |
| `lmom_acceleration_score` | H +1; L -1; 0 none | saturation | via KDS | indirect | z alternative | component | acceleration-z | MACD histogram | normalized |
| `lmom_impulse_3` | H strong up; L strong down; 0 no move | microstructure | indirect | RLVS-normalized | diagnostic | short impulse | other H | ROC | normalized |
| `lmom_impulse_5` | H strong up; L strong down; 0 no move | forecast model | indirect | normalized | diagnostic | short impulse | other H | ROC | normalized |
| `lmom_impulse_15` | H medium up; L down; 0 no move | forecast model | indirect | normalized | useful | displacement gate | composite | ROC/RSI | normalized |
| `lmom_impulse_30` | H longer up; L down; 0 no move | regime changes | indirect | normalized | target-matched | context | other H | ROC | normalized |
| `lmom_impulse_60` | H slow up; L down; 0 no move | lag | indirect | normalized | context | confirmation | trend | ROC/PPO | normalized |
| `lmom_impulse` | H broad up; L broad down; 0 balanced | weights/saturation | indirect | normalized | useful | principal impulse | breadth/score | multi-ROC | composite |
| `lmom_breadth` | H unanimous up; L unanimous down; 0 mixed | correlated H | indirect | normalized | cautious | confirmation | impulses | ROC signs | composite |
| `lmom_efficiency_5` | H clean; L/0 choppy | gaps | low | low | diagnostic | chop filter | composite eff | efficiency ratio | normalized |
| `lmom_efficiency_15` | H clean; L/0 choppy | gaps | low | low | diagnostic | chop filter | composite eff | efficiency ratio | normalized |
| `lmom_efficiency_30` | H clean; L/0 choppy | gaps | low | low | diagnostic | chop filter | composite eff | efficiency ratio | normalized |
| `lmom_efficiency` | H clean path; L/0 chop | horizon choice | low | low | recommended | quality gate | components | Kaufman efficiency | composite |
| `lmom_persistence` | H persistent up; L persistent down; 0 mixed | sign loses magnitude | low | low | quality context | persistence filter | breadth | run length/RSI | normalized |
| `lmom_activity` | H usable momentum; L/0 absent | compound suppression | indirect | normalized | use cautiously with score | activity gate | strength/score | ADX-like strength | composite |
| `lmom_plus` | H positive activity; L/0 none | same | indirect | normalized | omit with peers | display | minus/activity | +DI/RSI | composite |
| `lmom_minus` | H negative activity; L/0 none | same | indirect | normalized | omit with peers | display | plus/activity | -DI/RSI | composite |
| `lmom_strength` | H strong; L/0 weak; direction absent | no direction | indirect | normalized | prefer activity | strength gate | activity | ADX | composite |
| `lmom_score` | H strong up; L strong down; 0 weak | nonlinear weights | indirect | normalized | recommended | principal score | impulse/activity | RSI/MACD/PPO | composite |
| `lmom_exhaustion` | H overextended/opposed/inefficient; L/0 no evidence | not reversal probability | indirect | rises with shock/VoV | recommended diagnostic | caution only | impulse/eff/shock | oscillator extremes | diagnostic |
| `lmom_reversal_pressure` | H counter-trend; L/0 aligned/neutral | trend threshold | via KDS | normalized | event diagnostic | monitor/veto | alignment | MACD vs trend | diagnostic |
| `lmom_divergence` | H momentum more bullish; L more bearish; 0 equal | composite difference | via KDS | normalized | recommended | divergence | score+trend | oscillator divergence | diagnostic |
| `lmom_alignment` | H positive agreement; L negative opposition; 0 neutral | product suppression | via KDS | normalized | interaction | confirmation | reversal | trend×momentum | composite |
| `lmom_direction` | H +1; L -1; 0 neutral | chatter | indirect | normalized | categorical/diagnostic | filter | score sign | RSI >/<50 | diagnostic |

### LMDS warm-up, missing data, and validation

Composite impulse requires 60 bars; efficiency requires 30; KDS/RLVS may need
longer. Missing closes propagate through affected horizons. Validate
accelerating/decelerating trends, alternating mean reversion, constant prices,
outliers, and prefix invariance. Recommended ML subset: `lmom_score`,
`lmom_acceleration_z`, `lmom_efficiency`, `lmom_exhaustion`,
`lmom_divergence`. Avoid including all raw horizons, impulse, breadth,
activity, plus/minus, and strength together.

## Composite `quant_market_state` builder

The orchestrator performs KDS → RLVS → LMDS and retains every underlying
column. Compact outputs contain no hidden fitted score.

| Column | System | Exact definition | dtype | Range | Units | Directionality | Causal availability | Inputs |
|---|---|---|---|---|---|---|---|---|
| `qms_trend` | QMS | Alias `ktrend_score` | float64 | `[-1,1]` | score | signed | KDS warm-up | KDS |
| `qms_trend_confidence` | QMS | Alias `ktrend_confidence` | float64 | `[0,1]` | posterior-derived | unsigned | KDS state | KDS |
| `qms_volatility` | QMS | Alias `rlv_sigma` | float64 | `[0,exp(2.5)]` | return SD/bar | unsigned | RLVS warm-up | RLVS |
| `qms_volatility_shock` | QMS | Alias `rlv_shock_z` | float64 | real | predicted SD | signed shock | RLVS update | RLVS |
| `qms_momentum` | QMS | Alias `lmom_score` | float64 | `[-1,1]` | score | signed | LMDS warm-up | LMDS |
| `qms_momentum_quality` | QMS | \(\sqrt{efficiency(1+|persistence|)/2}\) | float64 | `[0,1]` | fraction | unsigned | LMDS warm-up | LMDS |
| `qms_trend_momentum_alignment` | QMS | Alias `lmom_alignment` | float64 | `[-1,1]` | product | + aligned | LMDS warm-up | KDS,LMDS |
| `qms_state_uncertainty` | QMS | `(ktrend_uncertainty+rlv_state_uncertainty)/2` | float64 | `[0,1]` | fraction | higher=uncertain | both ready | KDS,RLVS |
| `qms_gap_flag` | QMS | One when elapsed time exceeds one minute | float64 | `{0,1}` | flag | gap | timestamp t | index |
| `qms_gap_minutes` | QMS | `max(elapsed_minutes-1,0)` | float64 | `[0,inf)` | minutes | higher=larger gap | timestamp t | index |
| `qms_weekend_gap` | QMS | Hard gap whose interval spans a weekend day | float64 | `{0,1}` | flag | expected closure | timestamp t | index |
| `qms_unexpected_data_gap` | QMS | Hard non-weekend gap | float64 | `{0,1}` | flag | data risk | timestamp t | index |
| `qms_post_gap_age` | QMS | Continuous bars elapsed since latest gap row | float64 | `[0,inf)` | bars | higher=older gap | timestamp t | index |
| `qms_contiguous_bars` | QMS | Current uninterrupted one-minute run length | float64 | `[1,inf)` | bars | higher=more history | timestamp t | index |
| `qms_state_reinitialized` | QMS | One on a hard-gap soft-reset row | float64 | `{0,1}` | flag | reset diagnostic | timestamp t | index |
| `qms_opening_gap_return` | QMS | `log(close_t/close_t-1)` only on gap rows | float64 | real/NaN | log return | signed gap | close t | midpoint close |

| Column | Interpretation; H/L/0 | Failure modes | Spread sensitivity | Vol sensitivity | ML use | Rule use | Redundancy | Replaces/complements | Type |
|---|---|---|---|---|---|---|---|---|---|
| `qms_trend` | H up; L down; 0 absent | KDS assumptions | direct | adaptive | compact set | trend context | KDS alias | signed ADX/PPO | composite |
| `qms_trend_confidence` | H confident; L/0 neutral | uncalibrated | direct | adaptive | compact/calibrate | confidence gate | KDS alias | ADX confidence | probabilistic |
| `qms_volatility` | H active; L/0 quiet | RLVS assumptions | adjusted | direct | compact set | sizing | RLVS alias | rolling vol/ATR | raw |
| `qms_volatility_shock` | H expansion; L compression; 0 expected | noise model | adjusted | direct | compact set | shock gate | RLVS alias | vol shock | normalized |
| `qms_momentum` | H up; L down; 0 weak | LMDS weights | indirect | normalized | compact set | momentum context | LMDS alias | RSI/MACD/PPO | composite |
| `qms_momentum_quality` | H clean/persistent; L/0 choppy | sign simplification | low | low | compact set | quality gate | eff/persistence | efficiency ratio | composite |
| `qms_trend_momentum_alignment` | H aligned; L opposed; 0 neutral | product suppression | via KDS | normalized | interaction | confirmation | LMDS alias | trend-momentum cross | composite |
| `qms_state_uncertainty` | H uncertain; L/0 precise | average hides source | direct | direct | guardrail | veto | source uncertainties | none direct | diagnostic |

The probability caveat also applies here: these are model-implied posterior
probabilities under the state-space assumptions. They are not guaranteed
empirical forecast probabilities unless independently calibrated.

## Example usage

Single orchestrator:

```yaml
features:
  - step: quant_market_state
    params:
      preset: balanced
      kds_config: {spread_baseline_window: 1440}
      rlvs_config: {regime_baseline_span: 1440}
      lmds_config: {persistence_span: 15}
```

Separate dependency-auditable steps:

```yaml
features:
  - step: kds
    params: {preset: balanced}
  - step: rlvs
    params: {preset: balanced}
  - step: lmds
    params: {preset: balanced}
```

```bash
python scripts/examples/quant_market_state_example.py --rows 5000 --preset balanced
```

The example fits HAR on a training prefix and transforms without refitting. It
does not generate orders.

## Traditional benchmark comparison

`src.features.systems.benchmarking` uses the repository's existing ADX/+DI/-DI,
ATR, rolling return volatility, Parkinson, Garman-Klass, Yang-Zhang, ROC, RSI,
Stochastic, MACD, PPO, and EMA-slope implementations.
`evaluate_feature_benchmarks` uses expanding walk-forward splits. Scaling,
logistic fitting, and selective quantile thresholds use training rows only. It
reports Spearman IC, mutual information, univariate logistic log-loss, Brier
score, AUC where valid, selective precision, fold IC stability, turnover, and
net expectancy after externally supplied costs.

The utility makes no superiority claim. Any claim requires untouched
out-of-sample evidence, realistic costs, multiple regimes/assets, and
statistical uncertainty.

## Performance benchmark

```bash
python scripts/benchmarks/benchmark_quant_market_state.py --rows 100000
python scripts/benchmarks/benchmark_quant_market_state.py --rows 100000 --include-million
```

It reports runtime, rows/second, `tracemalloc` peak allocated memory, component
timings, and the expensive components. The million-row run is opt-in because
available memory is environment-dependent. The checked 100k-row result is in
[the performance report](../research/quant_market_state_performance.md).

## Recommended validation

1. Re-run prefix/appended-data invariance on each production schema.
2. Confirm next-bar execution and target alignment in every experiment.
3. Test constant, up/down, accelerating/decelerating, mean-reverting,
   expansion/compression, outlier, range-anomaly, and spread-spike paths.
4. Inspect parameter stability across purged walk-forward folds and assets.
5. Calibrate probabilities on untouched OOS data before empirical use.
6. Compare net expectancy under externally supplied bid/ask costs.
7. Monitor gaps, missing bars, spread availability, uncertainty, and bound hits.

## Design deviations from the requested starting specification

1. KADX uses the repository's classic full-window SMA-seeded Wilder recursion.
2. KDS variance terms have explicit epsilon floors; spread/volatility penalties
   act only above prior baselines.
3. KDS/RLVS report raw innovations; Huber clipping changes only state updates.
4. RLVS requires two current estimators and masks EWM carry-forward on missing
   current OHLC.
5. RLVS fast/slow sigma are causal smoothers of the main filtered state rather
   than separately parameterized filters.
6. RLVS log variance has transparent configurable numerical bounds.
7. LMDS acceleration omits lag-one cross-covariance because KDS does not expose
   it; the approximation is conservative and documented.
8. Raw horizon impulses are retained; clipping is internal to nonlinear terms.
9. Persistence is an auditable signed EWM of return signs and is neutral-aware.
10. HAR is a separate explicit-fit class, never an implicitly fitted feature.
11. Optional resampled multiscale KDS is omitted until this package has an
    explicit fully-closed higher-timeframe-bar contract.
12. Timestamp gaps now use time-scaled state transitions; hard gaps use a soft
    state reset rather than pretending the closure was one M1 observation.

## Remaining limitations
- Square-root horizon forecasts are risk scaling, not calibrated forecasts.
- Posterior probabilities are not empirically calibrated.
- Averaged bid/ask OHLC extremes are quote-bar midpoints, not tradeable paths.
- A public `update(state, bar)` API is not yet exposed; batch is the reference.
- HAR is linear and omits leverage effects and intraday seasonality.
- Discrete `rlv_regime` is diagnostic and threshold-dependent.
- No alpha, accuracy, or economic superiority is asserted.
