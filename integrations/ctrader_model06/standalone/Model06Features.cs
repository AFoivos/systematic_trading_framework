using System;
using System.Collections.Generic;
using System.Linq;

namespace CTraderModel06Standalone
{
    /// <summary>
    /// Standalone C# implementation of the 48-feature Model06 contract.
    /// The formulas mirror the Python feature pipeline used by
    /// 02_conservative_0600_daily015_total075.yaml.
    /// </summary>
    public static class Model06Features
    {
        public readonly struct Bar
        {
            public Bar(DateTime time, double open, double high, double low, double close, double volume)
            {
                Time = time;
                Open = open;
                High = high;
                Low = low;
                Close = close;
                Volume = volume;
            }

            public DateTime Time { get; }
            public double Open { get; }
            public double High { get; }
            public double Low { get; }
            public double Close { get; }
            public double Volume { get; }
        }

        private const double Eps = 1e-12;
        private const double RatioEps = 1e-8;

        public static double[] ComputeLatest(IReadOnlyList<Bar> bars)
        {
            if (bars == null) throw new ArgumentNullException(nameof(bars));
            var rows = ComputeRows(bars, new[] { bars.Count - 1 });
            return rows[0];
        }

        /// <summary>
        /// Compute Model06 feature vectors for selected bar indices in a single full-history pass.
        /// Recursive indicators are evaluated once over the supplied history, then the requested
        /// rows are assembled without recomputing the pipeline for every parity timestamp.
        /// </summary>
        public static double[][] ComputeRows(IReadOnlyList<Bar> bars, IReadOnlyList<int> indices)
        {
            if (bars == null) throw new ArgumentNullException(nameof(bars));
            if (indices == null) throw new ArgumentNullException(nameof(indices));
            if (bars.Count < 400)
                throw new ArgumentException("Model06 requires at least 400 warm-up bars for a finite feature vector.", nameof(bars));
            if (indices.Count == 0)
                return Array.Empty<double[]>();

            int n = bars.Count;
            foreach (var index in indices)
                if (index < 0 || index >= n)
                    throw new ArgumentOutOfRangeException(nameof(indices), $"Requested feature index {index} is outside [0, {n - 1}].");

            var open = new double[n];
            var high = new double[n];
            var low = new double[n];
            var close = new double[n];
            var volume = new double[n];
            for (int i = 0; i < n; i++)
            {
                open[i] = bars[i].Open;
                high[i] = bars[i].High;
                low[i] = bars[i].Low;
                close[i] = bars[i].Close;
                volume[i] = bars[i].Volume;
            }

            var closeRet = SimpleReturns(close, 1, castFloat32: false);
            var vol24 = RollingStd(closeRet, 24, ddof: 1);
            var vol48 = RollingStd(closeRet, 48, ddof: 1);
            var vol96 = RollingStd(closeRet, 96, ddof: 1);
            var vol192 = RollingStd(closeRet, 192, ddof: 1);

            var ema24 = Ema(close, 24);
            var ema48 = Ema(close, 48);
            var ema96 = Ema(close, 96);
            var ema192 = Ema(close, 192);

            var tr = TrueRange(high, low, close);
            var atr48 = Wilder(tr, 48);

            var mesa = Mesa(close, 0.5, 0.05);
            var decycler = Decycler(close, 60);
            var instantaneousTrendline = InstantaneousTrendline(close, 0.07);
            var frama = Frama(close, high, low, 16, 4, 300);
            var supersmoother = SuperSmoother(close, 10);
            var roofing = RoofingFilter(close, 48, 10);

            var bb = Bollinger(close, 192, 2.0);
            var atrPct = new double[n];
            var atrOverPrice = new double[n];
            var emaTrend48192 = new double[n];
            var closeOverBbUpper = new double[n];
            var closeOverBbMid = new double[n];
            var closeOverVwap32 = new double[n];
            var vwap32 = Vwap(high, low, close, volume, 32);

            for (int i = 0; i < n; i++)
            {
                atrOverPrice[i] = RatioFloat32(atr48[i], close[i], 0.0);
                atrPct[i] = Float32(SafeDivide(atr48[i], close[i]));
                emaTrend48192[i] = RatioFloat32(ema48[i], ema192[i], 1.0);
                closeOverBbUpper[i] = RatioFloat32(close[i], bb.Upper[i], 1.0);
                closeOverBbMid[i] = RatioFloat32(close[i], bb.Mid[i], 1.0);
                closeOverVwap32[i] = RatioFloat32(close[i], vwap32[i], 1.0);
            }

            var atrPctRank192 = RollingPercentRank(atrPct, 192, inputAlreadyFloat32: true);
            var bbBandwidthRank192 = RollingPercentRank(bb.Bandwidth, 192, inputAlreadyFloat32: false);
            var robustZ128 = RobustZScore(closeRet, 128, shiftStats: true, madScale: 1.4826);

            double[] BuildRow(int k)
            {
                var result = new double[48];
                result[0] = closeRet[k];
                result[1] = Lag(closeRet, k, 1);
                result[2] = Lag(closeRet, k, 2);
                result[3] = Lag(closeRet, k, 4);
                result[4] = Lag(closeRet, k, 8);
                result[5] = Lag(closeRet, k, 16);
                result[6] = Lag(closeRet, k, 24);
                result[7] = Lag(closeRet, k, 48);

                result[8] = ReturnFloat32(close, k, 1);
                result[9] = ReturnFloat32(close, k, 4);
                result[10] = ReturnFloat32(close, k, 8);
                result[11] = ReturnFloat32(close, k, 16);
                result[12] = ReturnFloat32(close, k, 24);
                result[13] = ReturnFloat32(close, k, 48);
                result[14] = ReturnFloat32(close, k, 24);
                result[15] = ReturnFloat32(close, k, 48);

                result[16] = vol24[k];
                result[17] = vol48[k];
                result[18] = vol96[k];
                result[19] = vol192[k];
                result[20] = atr48[k];
                result[21] = atrOverPrice[k];
                result[22] = atrPct[k];
                result[23] = atrPctRank192[k];
                result[24] = emaTrend48192[k];
                result[25] = closeOverBbUpper[k];
                result[26] = closeOverBbMid[k];
                result[27] = bb.PercentB[k];
                result[28] = bb.Bandwidth[k];
                result[29] = bbBandwidthRank192[k];

                result[30] = EmaAlignmentFloat(ema24[k], ema96[k], ema192[k]);
                result[31] = Float32(SafeDivide(Math.Abs(close[k] - ema24[k]), atr48[k]));
                result[32] = Float32(SafeDivide(Math.Abs(close[k] - ema96[k]), atr48[k]));
                result[33] = Float32(SafeDivide(mesa.Mama[k] - mesa.Fama[k], atr48[k]));
                result[34] = Float32(SafeDivide(close[k] - decycler[k], atr48[k]));
                result[35] = Float32(SafeDivide(Diff(instantaneousTrendline, k, 1), atr48[k]));
                result[36] = Float32(SafeDivide(Diff(decycler, k, 1), atr48[k]));
                result[37] = Float32(SafeDivide(Diff(frama, k, 1), atr48[k]));
                result[38] = Float32(SafeDivide(Diff(supersmoother, k, 1), atr48[k]));
                result[39] = Float32(SafeDivide(roofing[k], atr48[k]));
                result[40] = Float32(Mod(mesa.Phase[k], 360.0) / 360.0);

                double range = high[k] - low[k];
                result[41] = Float32(SafeDivide(Math.Abs(close[k] - open[k]), range));
                result[42] = Float32(SafeDivide(high[k] - Math.Max(open[k], close[k]), range));
                result[43] = Float32(SafeDivide(Math.Min(open[k], close[k]) - low[k], range));
                result[44] = Float32(SafeDivide(close[k] - low[k], range));
                result[45] = Float32(SafeDivide(range, atr48[k]));
                result[46] = closeOverVwap32[k];
                result[47] = robustZ128[k];

                for (int i = 0; i < result.Length; i++)
                    if (!double.IsFinite(result[i]))
                        throw new InvalidOperationException($"Non-finite Model06 feature at bar {k}, index {i} ({Model06Predictor.FeatureOrder[i]}): {result[i]}");
                return result;
            }

            var rows = new double[indices.Count][];
            for (int i = 0; i < indices.Count; i++)
                rows[i] = BuildRow(indices[i]);
            return rows;
        }

        private static double Float32(double value) => (double)(float)value;

        private static double SafeDivide(double numerator, double denominator)
        {
            if (!double.IsFinite(numerator) || !double.IsFinite(denominator) || denominator == 0.0)
                return double.NaN;
            return numerator / denominator;
        }

        private static double RatioFloat32(double numerator, double denominator, double subtract)
        {
            if (!double.IsFinite(numerator) || !double.IsFinite(denominator) || Math.Abs(denominator) <= RatioEps)
                return double.NaN;
            return Float32(numerator / denominator - subtract);
        }

        private static double[] SimpleReturns(double[] close, int lag, bool castFloat32)
        {
            var r = FillNaN(close.Length);
            for (int i = lag; i < close.Length; i++)
            {
                if (!double.IsFinite(close[i]) || !double.IsFinite(close[i - lag]) || close[i - lag] == 0.0) continue;
                double v = close[i] / close[i - lag] - 1.0;
                r[i] = castFloat32 ? Float32(v) : v;
            }
            return r;
        }

        private static double ReturnFloat32(double[] close, int index, int lag)
        {
            if (index < lag || close[index - lag] == 0.0) return double.NaN;
            return Float32(close[index] / close[index - lag] - 1.0);
        }

        private static double Lag(double[] values, int index, int lag) => index >= lag ? values[index - lag] : double.NaN;
        private static double Diff(double[] values, int index, int lag) => index >= lag ? values[index] - values[index - lag] : double.NaN;

        private static double[] RollingStd(double[] values, int window, int ddof)
        {
            var output = FillNaN(values.Length);
            for (int i = window - 1; i < values.Length; i++)
            {
                double sum = 0.0;
                bool valid = true;
                for (int j = i - window + 1; j <= i; j++)
                {
                    if (!double.IsFinite(values[j])) { valid = false; break; }
                    sum += values[j];
                }
                if (!valid) continue;
                double mean = sum / window;
                double ss = 0.0;
                for (int j = i - window + 1; j <= i; j++)
                {
                    double d = values[j] - mean;
                    ss += d * d;
                }
                output[i] = Math.Sqrt(ss / (window - ddof));
            }
            return output;
        }

        private static double[] Ema(double[] values, int span)
        {
            var output = FillNaN(values.Length);
            double alpha = 2.0 / (span + 1.0);
            double state = double.NaN;
            for (int i = 0; i < values.Length; i++)
            {
                double x = values[i];
                if (!double.IsFinite(x)) continue;
                state = double.IsFinite(state) ? alpha * x + (1.0 - alpha) * state : x;
                output[i] = state;
            }
            return output;
        }

        private static double[] TrueRange(double[] high, double[] low, double[] close)
        {
            var output = FillNaN(close.Length);
            for (int i = 0; i < close.Length; i++)
            {
                if (!double.IsFinite(high[i]) || !double.IsFinite(low[i])) continue;
                double a = high[i] - low[i];
                if (i == 0 || !double.IsFinite(close[i - 1])) { output[i] = a; continue; }
                double b = Math.Abs(high[i] - close[i - 1]);
                double c = Math.Abs(low[i] - close[i - 1]);
                output[i] = Math.Max(a, Math.Max(b, c));
            }
            return output;
        }

        private static double[] Wilder(double[] values, int window)
        {
            var output = FillNaN(values.Length);
            var seed = new Queue<double>();
            double state = double.NaN;
            for (int i = 0; i < values.Length; i++)
            {
                double x = values[i];
                if (!double.IsFinite(x))
                {
                    seed.Clear(); state = double.NaN; continue;
                }
                if (!double.IsFinite(state))
                {
                    seed.Enqueue(x);
                    while (seed.Count > window) seed.Dequeue();
                    if (seed.Count < window) continue;
                    state = seed.Average();
                }
                else
                {
                    state = ((state * (window - 1.0)) + x) / window;
                }
                output[i] = state;
            }
            return output;
        }

        private sealed class BollingerResult
        {
            public double[] Mid = Array.Empty<double>();
            public double[] Upper = Array.Empty<double>();
            public double[] PercentB = Array.Empty<double>();
            public double[] Bandwidth = Array.Empty<double>();
        }

        private static BollingerResult Bollinger(double[] close, int window, double nStd)
        {
            var mid = FillNaN(close.Length);
            var upper = FillNaN(close.Length);
            var percentB = FillNaN(close.Length);
            var bandwidth = FillNaN(close.Length);
            for (int i = window - 1; i < close.Length; i++)
            {
                double sum = 0.0; bool valid = true;
                for (int j = i - window + 1; j <= i; j++)
                {
                    if (!double.IsFinite(close[j])) { valid = false; break; }
                    sum += close[j];
                }
                if (!valid) continue;
                double mean = sum / window;
                double ss = 0.0;
                for (int j = i - window + 1; j <= i; j++) { double d = close[j] - mean; ss += d * d; }
                double sd = Math.Sqrt(ss / window);
                double up = mean + nStd * sd;
                double lo = mean - nStd * sd;
                mid[i] = mean; upper[i] = up;
                bandwidth[i] = mean == 0.0 ? double.NaN : (up - lo) / mean;
                percentB[i] = up == lo ? double.NaN : (close[i] - lo) / (up - lo);
            }
            return new BollingerResult { Mid = mid, Upper = upper, PercentB = percentB, Bandwidth = bandwidth };
        }

        private static double[] RollingPercentRank(double[] values, int window, bool inputAlreadyFloat32)
        {
            var output = FillNaN(values.Length);
            for (int i = window - 1; i < values.Length; i++)
            {
                double current = values[i];
                if (!double.IsFinite(current)) continue;
                int valid = 0, le = 0;
                for (int j = i - window + 1; j <= i; j++)
                {
                    double x = values[j];
                    if (!double.IsFinite(x)) continue;
                    valid++;
                    if (x <= current) le++;
                }
                if (valid == window)
                    output[i] = Float32((double)le / valid);
            }
            return output;
        }

        private static double EmaAlignmentFloat(double fast, double mid, double slow)
        {
            if (fast > mid && mid > slow) return 1.0;
            if (fast < mid && mid < slow) return -1.0;
            return 0.0;
        }

        private static double[] Vwap(double[] high, double[] low, double[] close, double[] volume, int window)
        {
            var output = FillNaN(close.Length);
            for (int i = window - 1; i < close.Length; i++)
            {
                double numerator = 0.0, denominator = 0.0; bool valid = true;
                for (int j = i - window + 1; j <= i; j++)
                {
                    if (!double.IsFinite(high[j]) || !double.IsFinite(low[j]) || !double.IsFinite(close[j]) || !double.IsFinite(volume[j])) { valid = false; break; }
                    double typical = (high[j] + low[j] + close[j]) / 3.0;
                    numerator += typical * volume[j];
                    denominator += volume[j];
                }
                if (valid && denominator != 0.0) output[i] = numerator / denominator;
            }
            return output;
        }

        private static double[] RobustZScore(double[] source, int window, bool shiftStats, double madScale)
        {
            var output = FillNaN(source.Length);
            for (int i = 0; i < source.Length; i++)
            {
                int end = shiftStats ? i - 1 : i;
                int start = end - window + 1;
                if (start < 0 || end < 0 || !double.IsFinite(source[i])) continue;
                var sample = new double[window]; bool valid = true;
                for (int j = 0; j < window; j++)
                {
                    double x = source[start + j];
                    if (!double.IsFinite(x)) { valid = false; break; }
                    sample[j] = x;
                }
                if (!valid) continue;
                double median = Median(sample);
                var deviations = new double[window];
                for (int j = 0; j < window; j++) deviations[j] = Math.Abs(sample[j] - median);
                double mad = Median(deviations);
                double denom = mad * madScale;
                if (denom == 0.0) continue;
                output[i] = Float32((source[i] - median) / denom);
            }
            return output;
        }

        private static double Median(double[] values)
        {
            var copy = (double[])values.Clone();
            Array.Sort(copy);
            int n = copy.Length;
            return (n & 1) == 1 ? copy[n / 2] : (copy[n / 2 - 1] + copy[n / 2]) / 2.0;
        }

        private sealed class MesaResult
        {
            public double[] Phase = Array.Empty<double>();
            public double[] Mama = Array.Empty<double>();
            public double[] Fama = Array.Empty<double>();
        }

        private static MesaResult Mesa(double[] values, double fastLimit, double slowLimit)
        {
            int n = values.Length;
            var smooth = WeightedSmooth(values);
            var detrender = new double[n]; var q1 = new double[n]; var i1 = new double[n]; var ji = new double[n]; var jq = new double[n];
            var i2 = new double[n]; var q2 = new double[n]; var re = new double[n]; var im = new double[n];
            var phase = FillNaN(n); var mama = FillNaN(n); var fama = FillNaN(n);
            double previousPeriod = 10.0, previousSmoothPeriod = 10.0, previousPhase = 0.0;
            double previousMama = double.NaN, previousFama = double.NaN;

            for (int idx = 0; idx < n; idx++)
            {
                double price = values[idx]; if (!double.IsFinite(price)) continue;
                if (!double.IsFinite(previousMama)) { previousMama = price; previousFama = price; }
                double scale = 0.075 * previousPeriod + 0.54;
                detrender[idx] = FirHilbert(smooth, idx, scale);
                q1[idx] = FirHilbert(detrender, idx, scale);
                i1[idx] = idx >= 3 ? detrender[idx - 3] : 0.0;
                ji[idx] = FirHilbert(i1, idx, scale);
                jq[idx] = FirHilbert(q1, idx, scale);
                double rawI2 = i1[idx] - jq[idx], rawQ2 = q1[idx] + ji[idx];
                i2[idx] = 0.2 * rawI2 + 0.8 * (idx > 0 ? i2[idx - 1] : 0.0);
                q2[idx] = 0.2 * rawQ2 + 0.8 * (idx > 0 ? q2[idx - 1] : 0.0);
                double rawRe = i2[idx] * (idx > 0 ? i2[idx - 1] : 0.0) + q2[idx] * (idx > 0 ? q2[idx - 1] : 0.0);
                double rawIm = i2[idx] * (idx > 0 ? q2[idx - 1] : 0.0) - q2[idx] * (idx > 0 ? i2[idx - 1] : 0.0);
                re[idx] = 0.2 * rawRe + 0.8 * (idx > 0 ? re[idx - 1] : 0.0);
                im[idx] = 0.2 * rawIm + 0.8 * (idx > 0 ? im[idx - 1] : 0.0);

                double currentPeriod = previousPeriod;
                double angle = (Math.Abs(re[idx]) > Eps || Math.Abs(im[idx]) > Eps) ? Math.Abs(Math.Atan2(im[idx], re[idx])) : 0.0;
                if (angle > Eps)
                {
                    double rawPeriod = 2.0 * Math.PI / angle;
                    rawPeriod = Math.Min(rawPeriod, 1.5 * previousPeriod);
                    rawPeriod = Math.Max(rawPeriod, 0.67 * previousPeriod);
                    rawPeriod = Math.Min(Math.Max(rawPeriod, 6.0), 50.0);
                    currentPeriod = 0.2 * rawPeriod + 0.8 * previousPeriod;
                }
                double currentSmoothPeriod = 0.33 * currentPeriod + 0.67 * previousSmoothPeriod;
                double currentPhase = previousPhase;
                if (Math.Abs(i1[idx]) > Eps || Math.Abs(q1[idx]) > Eps)
                {
                    currentPhase = Math.Atan2(q1[idx], i1[idx]) * 180.0 / Math.PI;
                    if (currentPhase < 0.0) currentPhase += 360.0;
                }
                double currentDeltaPhase = previousPhase - currentPhase;
                if (previousPhase < 90.0 && currentPhase > 270.0) currentDeltaPhase = previousPhase + 360.0 - currentPhase;
                if (currentDeltaPhase < 1.0) currentDeltaPhase = 1.0;
                double currentAlpha = Math.Min(fastLimit, Math.Max(slowLimit, fastLimit / currentDeltaPhase));
                double currentMama = currentAlpha * price + (1.0 - currentAlpha) * previousMama;
                double currentFama = 0.5 * currentAlpha * currentMama + (1.0 - 0.5 * currentAlpha) * previousFama;
                phase[idx] = currentPhase; mama[idx] = currentMama; fama[idx] = currentFama;
                previousPeriod = currentPeriod; previousSmoothPeriod = currentSmoothPeriod; previousPhase = currentPhase;
                previousMama = currentMama; previousFama = currentFama;
            }
            return new MesaResult { Phase = phase, Mama = mama, Fama = fama };
        }

        private static double[] WeightedSmooth(double[] values)
        {
            var smooth = FillNaN(values.Length);
            for (int i = 0; i < values.Length; i++)
            {
                if (i < 3) { if (double.IsFinite(values[i])) smooth[i] = values[i]; continue; }
                if (AllFinite(values, i - 3, 4)) smooth[i] = (4.0 * values[i] + 3.0 * values[i - 1] + 2.0 * values[i - 2] + values[i - 3]) / 10.0;
            }
            return smooth;
        }

        private static double FirHilbert(double[] values, int idx, double scale)
        {
            if (idx < 6) return 0.0;
            if (!double.IsFinite(values[idx]) || !double.IsFinite(values[idx - 2]) || !double.IsFinite(values[idx - 4]) || !double.IsFinite(values[idx - 6])) return 0.0;
            return (0.0962 * values[idx] + 0.5769 * values[idx - 2] - 0.5769 * values[idx - 4] - 0.0962 * values[idx - 6]) * scale;
        }

        private static double[] HighPass(double[] values, int period)
        {
            var output = FillNaN(values.Length); var state = new double[values.Length];
            double angle = 0.707 * 2.0 * Math.PI / period;
            double alpha = (Math.Cos(angle) + Math.Sin(angle) - 1.0) / Math.Cos(angle);
            for (int i = 0; i < values.Length; i++)
            {
                if (!double.IsFinite(values[i])) continue;
                if (i < 2) { state[i] = 0.0; output[i] = 0.0; continue; }
                if (!AllFinite(values, i - 2, 3)) continue;
                state[i] = Math.Pow(1.0 - alpha / 2.0, 2.0) * (values[i] - 2.0 * values[i - 1] + values[i - 2])
                    + 2.0 * (1.0 - alpha) * state[i - 1] - Math.Pow(1.0 - alpha, 2.0) * state[i - 2];
                output[i] = state[i];
            }
            return output;
        }

        private static double[] Decycler(double[] values, int period)
        {
            var hp = HighPass(values, period); var output = FillNaN(values.Length);
            for (int i = 0; i < values.Length; i++) if (double.IsFinite(values[i]) && double.IsFinite(hp[i])) output[i] = values[i] - hp[i];
            return output;
        }

        private static double[] InstantaneousTrendline(double[] values, double a)
        {
            var t = FillNaN(values.Length);
            for (int i = 0; i < values.Length; i++)
            {
                if (!double.IsFinite(values[i])) continue;
                if (i < 2) t[i] = values[i];
                else if (i < 7)
                {
                    if (AllFinite(values, i - 2, 3)) t[i] = (values[i] + 2.0 * values[i - 1] + values[i - 2]) / 4.0;
                }
                else if (AllFinite(values, i - 2, 3) && double.IsFinite(t[i - 1]) && double.IsFinite(t[i - 2]))
                {
                    t[i] = (a - a * a / 4.0) * values[i] + 0.5 * a * a * values[i - 1] - (a - 0.75 * a * a) * values[i - 2]
                         + 2.0 * (1.0 - a) * t[i - 1] - Math.Pow(1.0 - a, 2.0) * t[i - 2];
                }
            }
            return t;
        }

        private static double[] Frama(double[] price, double[] high, double[] low, int window, int fastPeriod, int slowPeriod)
        {
            var output = FillNaN(price.Length); int half = window / 2;
            double fastAlpha = 2.0 / (fastPeriod + 1.0), slowAlpha = 2.0 / (slowPeriod + 1.0), previous = double.NaN;
            for (int i = 0; i < price.Length; i++)
            {
                if (!double.IsFinite(price[i])) continue;
                if (!double.IsFinite(previous)) previous = price[i];
                if (i + 1 < window) { output[i] = price[i]; previous = output[i]; continue; }
                int start = i - window + 1;
                if (!AllFinite(high, start, window) || !AllFinite(low, start, window)) continue;
                double n1 = (Max(high, start, half) - Min(low, start, half)) / half;
                double n2 = (Max(high, start + half, half) - Min(low, start + half, half)) / half;
                double n3 = (Max(high, start, window) - Min(low, start, window)) / window;
                double dimension = (n1 > Eps && n2 > Eps && n3 > Eps) ? (Math.Log(n1 + n2) - Math.Log(n3)) / Math.Log(2.0) : 1.0;
                double alpha = Math.Exp(-4.6 * (dimension - 1.0));
                alpha = Math.Min(fastAlpha, Math.Max(slowAlpha, alpha));
                double current = alpha * price[i] + (1.0 - alpha) * previous;
                output[i] = current; previous = current;
            }
            return output;
        }

        private static double[] SuperSmoother(double[] values, int period)
        {
            var result = FillNaN(values.Length); if (values.Length == 0) return result;
            double a1 = Math.Exp(-Math.Sqrt(2.0) * Math.PI / period);
            double b1 = 2.0 * a1 * Math.Cos(Math.Sqrt(2.0) * Math.PI / period);
            double c2 = b1, c3 = -(a1 * a1), c1 = 1.0 - c2 - c3;
            var state = new double[values.Length];
            if (double.IsFinite(values[0])) { state[0] = values[0]; result[0] = state[0]; }
            if (values.Length > 1 && double.IsFinite(values[0]) && double.IsFinite(values[1])) { state[1] = (values[0] + values[1]) / 2.0; result[1] = state[1]; }
            for (int i = 2; i < values.Length; i++)
            {
                if (!double.IsFinite(values[i - 1]) || !double.IsFinite(values[i])) continue;
                state[i] = c1 * (values[i] + values[i - 1]) / 2.0 + c2 * state[i - 1] + c3 * state[i - 2]; result[i] = state[i];
            }
            return result;
        }

        private static double[] RoofingFilter(double[] values, int hpPeriod, int lpPeriod)
        {
            var filt = FillNaN(values.Length); var hp = new double[values.Length]; var state = new double[values.Length];
            double angleHp = 0.707 * 2.0 * Math.PI / hpPeriod;
            double alpha = (Math.Cos(angleHp) + Math.Sin(angleHp) - 1.0) / Math.Cos(angleHp);
            double a1 = Math.Exp(-Math.Sqrt(2.0) * Math.PI / lpPeriod);
            double b1 = 2.0 * a1 * Math.Cos(Math.Sqrt(2.0) * Math.PI / lpPeriod);
            double c2 = b1, c3 = -(a1 * a1), c1 = 1.0 - c2 - c3;
            for (int i = 2; i < values.Length; i++)
            {
                if (!AllFinite(values, i - 2, 3)) continue;
                hp[i] = Math.Pow(1.0 - alpha / 2.0, 2.0) * (values[i] - 2.0 * values[i - 1] + values[i - 2])
                    + 2.0 * (1.0 - alpha) * hp[i - 1] - Math.Pow(1.0 - alpha, 2.0) * hp[i - 2];
                state[i] = c1 * (hp[i] + hp[i - 1]) / 2.0 + c2 * state[i - 1] + c3 * state[i - 2];
                filt[i] = state[i];
            }
            return filt;
        }

        private static double Mod(double x, double m) => ((x % m) + m) % m;
        private static double[] FillNaN(int n) { var a = new double[n]; for (int i = 0; i < n; i++) a[i] = double.NaN; return a; }
        private static bool AllFinite(double[] a, int start, int count) { for (int i = start; i < start + count; i++) if (!double.IsFinite(a[i])) return false; return true; }
        private static double Min(double[] a, int start, int count) { double v = double.PositiveInfinity; for (int i = start; i < start + count; i++) v = Math.Min(v, a[i]); return v; }
        private static double Max(double[] a, int start, int count) { double v = double.NegativeInfinity; for (int i = start; i < start + count; i++) v = Math.Max(v, a[i]); return v; }
    }
}
