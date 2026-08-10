using System;
using System.Collections.Generic;

namespace CTraderModel06Standalone
{
    /// <summary>
    /// Incremental/stateful implementation of the exact 48-feature Model06 contract.
    /// Each bar is processed once. Rolling windows scan at most 192 observations;
    /// recursive EMA/Ehlers/ATR state is carried forward instead of being reseeded.
    /// </summary>
    public sealed class Model06StreamingFeatures
    {
        private const double Eps = 1e-12;
        private const double RatioEps = 1e-8;

        private readonly List<double> _open = new();
        private readonly List<double> _high = new();
        private readonly List<double> _low = new();
        private readonly List<double> _close = new();
        private readonly List<double> _volume = new();
        private readonly List<double> _closeRet = new();

        private readonly List<double> _ema24 = new();
        private readonly List<double> _ema48 = new();
        private readonly List<double> _ema96 = new();
        private readonly List<double> _ema192 = new();

        private readonly List<double> _tr = new();
        private readonly List<double> _atr48 = new();
        private readonly Queue<double> _atrSeed = new();
        private double _atrState = double.NaN;
        private readonly List<double> _atrPct = new();

        private readonly List<double> _bbBandwidth = new();

        // MESA / MAMA / FAMA state.
        private readonly List<double> _mesaSmooth = new();
        private readonly List<double> _mesaDetrender = new();
        private readonly List<double> _mesaQ1 = new();
        private readonly List<double> _mesaI1 = new();
        private readonly List<double> _mesaJi = new();
        private readonly List<double> _mesaJq = new();
        private readonly List<double> _mesaI2 = new();
        private readonly List<double> _mesaQ2 = new();
        private readonly List<double> _mesaRe = new();
        private readonly List<double> _mesaIm = new();
        private readonly List<double> _mesaPhase = new();
        private readonly List<double> _mesaMama = new();
        private readonly List<double> _mesaFama = new();
        private double _mesaPreviousPeriod = 10.0;
        private double _mesaPreviousSmoothPeriod = 10.0;
        private double _mesaPreviousPhase = 0.0;
        private double _mesaPreviousMama = double.NaN;
        private double _mesaPreviousFama = double.NaN;

        // Ehlers recursive filters.
        private readonly List<double> _decyclerHp = new();
        private readonly List<double> _decycler = new();
        private readonly List<double> _instantaneousTrendline = new();
        private double _framaPrevious = double.NaN;
        private readonly List<double> _frama = new();
        private readonly List<double> _superState = new();
        private readonly List<double> _supersmoother = new();
        private readonly List<double> _roofHp = new();
        private readonly List<double> _roofState = new();
        private readonly List<double> _roofing = new();

        public int Count => _close.Count;
        public DateTime? LastTime { get; private set; }
        public double[] LatestFeatures { get; private set; }

        /// <summary>
        /// Append one strictly newer bar. Returns true when all 48 Model06 features are finite.
        /// </summary>
        public bool TryAdd(Model06Features.Bar bar, out double[] features)
        {
            if (LastTime.HasValue && bar.Time <= LastTime.Value)
                throw new ArgumentException($"Bars must be strictly increasing. Last={LastTime:O}, new={bar.Time:O}.", nameof(bar));

            LastTime = bar.Time;
            int k = _close.Count;
            _open.Add(bar.Open);
            _high.Add(bar.High);
            _low.Add(bar.Low);
            _close.Add(bar.Close);
            _volume.Add(bar.Volume);

            double closeRet = k == 0 || _close[k - 1] == 0.0
                ? double.NaN
                : bar.Close / _close[k - 1] - 1.0;
            _closeRet.Add(closeRet);

            AppendEma(_ema24, bar.Close, 24);
            AppendEma(_ema48, bar.Close, 48);
            AppendEma(_ema96, bar.Close, 96);
            AppendEma(_ema192, bar.Close, 192);

            double tr = TrueRangeAt(k);
            _tr.Add(tr);
            AppendAtr(tr);
            double atr = _atr48[k];
            double atrPct = Float32(SafeDivide(atr, bar.Close));
            _atrPct.Add(atrPct);

            var bb = BollingerAt(k, 192, 2.0);
            _bbBandwidth.Add(bb.Bandwidth);

            AppendMesa(k, bar.Close);
            AppendDecycler(k, bar.Close, 60);
            AppendInstantaneousTrendline(k, bar.Close, 0.07);
            AppendFrama(k, bar.Close, 16, 4, 300);
            AppendSuperSmoother(k, bar.Close, 10);
            AppendRoofing(k, bar.Close, 48, 10);

            var row = BuildRow(k, bb);
            for (int i = 0; i < row.Length; i++)
            {
                if (!double.IsFinite(row[i]))
                {
                    features = Array.Empty<double>();
                    LatestFeatures = null;
                    return false;
                }
            }

            LatestFeatures = row;
            features = row;
            return true;
        }

        private double[] BuildRow(int k, BollingerPoint bb)
        {
            var result = new double[48];
            result[0] = _closeRet[k];
            result[1] = Lag(_closeRet, k, 1);
            result[2] = Lag(_closeRet, k, 2);
            result[3] = Lag(_closeRet, k, 4);
            result[4] = Lag(_closeRet, k, 8);
            result[5] = Lag(_closeRet, k, 16);
            result[6] = Lag(_closeRet, k, 24);
            result[7] = Lag(_closeRet, k, 48);

            result[8] = ReturnFloat32(k, 1);
            result[9] = ReturnFloat32(k, 4);
            result[10] = ReturnFloat32(k, 8);
            result[11] = ReturnFloat32(k, 16);
            result[12] = ReturnFloat32(k, 24);
            result[13] = ReturnFloat32(k, 48);
            result[14] = ReturnFloat32(k, 24);
            result[15] = ReturnFloat32(k, 48);

            result[16] = RollingStdAt(_closeRet, k, 24, 1);
            result[17] = RollingStdAt(_closeRet, k, 48, 1);
            result[18] = RollingStdAt(_closeRet, k, 96, 1);
            result[19] = RollingStdAt(_closeRet, k, 192, 1);

            double atr = _atr48[k];
            result[20] = atr;
            result[21] = RatioFloat32(atr, _close[k], 0.0);
            result[22] = _atrPct[k];
            result[23] = RollingPercentRankAt(_atrPct, k, 192);
            result[24] = RatioFloat32(_ema48[k], _ema192[k], 1.0);
            result[25] = RatioFloat32(_close[k], bb.Upper, 1.0);
            result[26] = RatioFloat32(_close[k], bb.Mid, 1.0);
            result[27] = bb.PercentB;
            result[28] = bb.Bandwidth;
            result[29] = RollingPercentRankAt(_bbBandwidth, k, 192);

            result[30] = EmaAlignment(_ema24[k], _ema96[k], _ema192[k]);
            result[31] = Float32(SafeDivide(Math.Abs(_close[k] - _ema24[k]), atr));
            result[32] = Float32(SafeDivide(Math.Abs(_close[k] - _ema96[k]), atr));
            result[33] = Float32(SafeDivide(_mesaMama[k] - _mesaFama[k], atr));
            result[34] = Float32(SafeDivide(_close[k] - _decycler[k], atr));
            result[35] = Float32(SafeDivide(Diff(_instantaneousTrendline, k, 1), atr));
            result[36] = Float32(SafeDivide(Diff(_decycler, k, 1), atr));
            result[37] = Float32(SafeDivide(Diff(_frama, k, 1), atr));
            result[38] = Float32(SafeDivide(Diff(_supersmoother, k, 1), atr));
            result[39] = Float32(SafeDivide(_roofing[k], atr));
            result[40] = Float32(Mod(_mesaPhase[k], 360.0) / 360.0);

            double range = _high[k] - _low[k];
            result[41] = Float32(SafeDivide(Math.Abs(_close[k] - _open[k]), range));
            result[42] = Float32(SafeDivide(_high[k] - Math.Max(_open[k], _close[k]), range));
            result[43] = Float32(SafeDivide(Math.Min(_open[k], _close[k]) - _low[k], range));
            result[44] = Float32(SafeDivide(_close[k] - _low[k], range));
            result[45] = Float32(SafeDivide(range, atr));
            result[46] = RatioFloat32(_close[k], VwapAt(k, 32), 1.0);
            result[47] = RobustZAt(k, 128, 1.4826);
            return result;
        }

        private void AppendEma(List<double> output, double value, int span)
        {
            double alpha = 2.0 / (span + 1.0);
            double previous = output.Count == 0 ? double.NaN : output[^1];
            output.Add(double.IsFinite(previous) ? alpha * value + (1.0 - alpha) * previous : value);
        }

        private double TrueRangeAt(int k)
        {
            double a = _high[k] - _low[k];
            if (k == 0 || !double.IsFinite(_close[k - 1])) return a;
            double b = Math.Abs(_high[k] - _close[k - 1]);
            double c = Math.Abs(_low[k] - _close[k - 1]);
            return Math.Max(a, Math.Max(b, c));
        }

        private void AppendAtr(double tr)
        {
            if (!double.IsFinite(tr))
            {
                _atrSeed.Clear();
                _atrState = double.NaN;
                _atr48.Add(double.NaN);
                return;
            }

            if (!double.IsFinite(_atrState))
            {
                _atrSeed.Enqueue(tr);
                while (_atrSeed.Count > 48) _atrSeed.Dequeue();
                if (_atrSeed.Count < 48)
                {
                    _atr48.Add(double.NaN);
                    return;
                }
                double sum = 0.0;
                foreach (var value in _atrSeed) sum += value;
                _atrState = sum / 48.0;
            }
            else
            {
                _atrState = ((_atrState * 47.0) + tr) / 48.0;
            }
            _atr48.Add(_atrState);
        }

        private readonly struct BollingerPoint
        {
            public BollingerPoint(double mid, double upper, double percentB, double bandwidth)
            {
                Mid = mid;
                Upper = upper;
                PercentB = percentB;
                Bandwidth = bandwidth;
            }
            public double Mid { get; }
            public double Upper { get; }
            public double PercentB { get; }
            public double Bandwidth { get; }
        }

        private BollingerPoint BollingerAt(int k, int window, double nStd)
        {
            if (k + 1 < window) return new BollingerPoint(double.NaN, double.NaN, double.NaN, double.NaN);
            int start = k - window + 1;
            double sum = 0.0;
            for (int i = start; i <= k; i++)
            {
                if (!double.IsFinite(_close[i])) return new BollingerPoint(double.NaN, double.NaN, double.NaN, double.NaN);
                sum += _close[i];
            }
            double mean = sum / window;
            double ss = 0.0;
            for (int i = start; i <= k; i++)
            {
                double d = _close[i] - mean;
                ss += d * d;
            }
            double sd = Math.Sqrt(ss / window);
            double upper = mean + nStd * sd;
            double lower = mean - nStd * sd;
            double bandwidth = mean == 0.0 ? double.NaN : (upper - lower) / mean;
            double percentB = upper == lower ? double.NaN : (_close[k] - lower) / (upper - lower);
            return new BollingerPoint(mean, upper, percentB, bandwidth);
        }

        private void AppendMesa(int k, double price)
        {
            double smooth;
            if (k < 3)
                smooth = price;
            else
                smooth = (4.0 * _close[k] + 3.0 * _close[k - 1] + 2.0 * _close[k - 2] + _close[k - 3]) / 10.0;
            _mesaSmooth.Add(smooth);

            if (double.IsNaN(_mesaPreviousMama))
            {
                _mesaPreviousMama = price;
                _mesaPreviousFama = price;
            }

            double scale = 0.075 * _mesaPreviousPeriod + 0.54;
            double detrender = FirHilbert(_mesaSmooth, k, scale);
            _mesaDetrender.Add(detrender);
            double q1 = FirHilbert(_mesaDetrender, k, scale);
            _mesaQ1.Add(q1);
            double i1 = k >= 3 ? _mesaDetrender[k - 3] : 0.0;
            _mesaI1.Add(i1);
            double ji = FirHilbert(_mesaI1, k, scale);
            _mesaJi.Add(ji);
            double jq = FirHilbert(_mesaQ1, k, scale);
            _mesaJq.Add(jq);

            double rawI2 = i1 - jq;
            double rawQ2 = q1 + ji;
            double i2 = 0.2 * rawI2 + 0.8 * (k > 0 ? _mesaI2[k - 1] : 0.0);
            double q2 = 0.2 * rawQ2 + 0.8 * (k > 0 ? _mesaQ2[k - 1] : 0.0);
            _mesaI2.Add(i2);
            _mesaQ2.Add(q2);

            double rawRe = i2 * (k > 0 ? _mesaI2[k - 1] : 0.0) + q2 * (k > 0 ? _mesaQ2[k - 1] : 0.0);
            double rawIm = i2 * (k > 0 ? _mesaQ2[k - 1] : 0.0) - q2 * (k > 0 ? _mesaI2[k - 1] : 0.0);
            double re = 0.2 * rawRe + 0.8 * (k > 0 ? _mesaRe[k - 1] : 0.0);
            double im = 0.2 * rawIm + 0.8 * (k > 0 ? _mesaIm[k - 1] : 0.0);
            _mesaRe.Add(re);
            _mesaIm.Add(im);

            double currentPeriod = _mesaPreviousPeriod;
            double angle = (Math.Abs(re) > Eps || Math.Abs(im) > Eps) ? Math.Abs(Math.Atan2(im, re)) : 0.0;
            if (angle > Eps)
            {
                double rawPeriod = 2.0 * Math.PI / angle;
                rawPeriod = Math.Min(rawPeriod, 1.5 * _mesaPreviousPeriod);
                rawPeriod = Math.Max(rawPeriod, 0.67 * _mesaPreviousPeriod);
                rawPeriod = Math.Min(Math.Max(rawPeriod, 6.0), 50.0);
                currentPeriod = 0.2 * rawPeriod + 0.8 * _mesaPreviousPeriod;
            }

            double currentSmoothPeriod = 0.33 * currentPeriod + 0.67 * _mesaPreviousSmoothPeriod;
            double currentPhase = _mesaPreviousPhase;
            if (Math.Abs(i1) > Eps || Math.Abs(q1) > Eps)
            {
                currentPhase = Math.Atan2(q1, i1) * 180.0 / Math.PI;
                if (currentPhase < 0.0) currentPhase += 360.0;
            }

            double currentDeltaPhase = _mesaPreviousPhase - currentPhase;
            if (_mesaPreviousPhase < 90.0 && currentPhase > 270.0)
                currentDeltaPhase = _mesaPreviousPhase + 360.0 - currentPhase;
            if (currentDeltaPhase < 1.0) currentDeltaPhase = 1.0;

            double currentAlpha = Math.Min(0.5, Math.Max(0.05, 0.5 / currentDeltaPhase));
            double currentMama = currentAlpha * price + (1.0 - currentAlpha) * _mesaPreviousMama;
            double currentFama = 0.5 * currentAlpha * currentMama + (1.0 - 0.5 * currentAlpha) * _mesaPreviousFama;

            _mesaPhase.Add(currentPhase);
            _mesaMama.Add(currentMama);
            _mesaFama.Add(currentFama);
            _mesaPreviousPeriod = currentPeriod;
            _mesaPreviousSmoothPeriod = currentSmoothPeriod;
            _mesaPreviousPhase = currentPhase;
            _mesaPreviousMama = currentMama;
            _mesaPreviousFama = currentFama;
        }

        private static double FirHilbert(IReadOnlyList<double> values, int k, double scale)
        {
            if (k < 6) return 0.0;
            double a = values[k], b = values[k - 2], c = values[k - 4], d = values[k - 6];
            if (!double.IsFinite(a) || !double.IsFinite(b) || !double.IsFinite(c) || !double.IsFinite(d)) return 0.0;
            return (0.0962 * a + 0.5769 * b - 0.5769 * c - 0.0962 * d) * scale;
        }

        private void AppendDecycler(int k, double price, int period)
        {
            double hp;
            if (k < 2)
            {
                hp = 0.0;
            }
            else
            {
                double angle = 0.707 * 2.0 * Math.PI / period;
                double alpha = (Math.Cos(angle) + Math.Sin(angle) - 1.0) / Math.Cos(angle);
                hp = Math.Pow(1.0 - alpha / 2.0, 2.0) * (_close[k] - 2.0 * _close[k - 1] + _close[k - 2])
                    + 2.0 * (1.0 - alpha) * _decyclerHp[k - 1]
                    - Math.Pow(1.0 - alpha, 2.0) * _decyclerHp[k - 2];
            }
            _decyclerHp.Add(hp);
            _decycler.Add(price - hp);
        }

        private void AppendInstantaneousTrendline(int k, double price, double a)
        {
            double value;
            if (k < 2)
                value = price;
            else if (k < 7)
                value = (_close[k] + 2.0 * _close[k - 1] + _close[k - 2]) / 4.0;
            else
                value = (a - a * a / 4.0) * _close[k]
                    + 0.5 * a * a * _close[k - 1]
                    - (a - 0.75 * a * a) * _close[k - 2]
                    + 2.0 * (1.0 - a) * _instantaneousTrendline[k - 1]
                    - Math.Pow(1.0 - a, 2.0) * _instantaneousTrendline[k - 2];
            _instantaneousTrendline.Add(value);
        }

        private void AppendFrama(int k, double price, int window, int fastPeriod, int slowPeriod)
        {
            if (!double.IsFinite(_framaPrevious)) _framaPrevious = price;
            if (k + 1 < window)
            {
                _frama.Add(price);
                _framaPrevious = price;
                return;
            }

            int start = k - window + 1;
            int half = window / 2;
            double n1 = (Max(_high, start, half) - Min(_low, start, half)) / half;
            double n2 = (Max(_high, start + half, half) - Min(_low, start + half, half)) / half;
            double n3 = (Max(_high, start, window) - Min(_low, start, window)) / window;
            double dimension = (n1 > Eps && n2 > Eps && n3 > Eps)
                ? (Math.Log(n1 + n2) - Math.Log(n3)) / Math.Log(2.0)
                : 1.0;
            double alpha = Math.Exp(-4.6 * (dimension - 1.0));
            double fastAlpha = 2.0 / (fastPeriod + 1.0);
            double slowAlpha = 2.0 / (slowPeriod + 1.0);
            alpha = Math.Min(fastAlpha, Math.Max(slowAlpha, alpha));
            double current = alpha * price + (1.0 - alpha) * _framaPrevious;
            _frama.Add(current);
            _framaPrevious = current;
        }

        private void AppendSuperSmoother(int k, double price, int period)
        {
            double state;
            if (k == 0)
            {
                state = price;
            }
            else if (k == 1)
            {
                state = (_close[0] + _close[1]) / 2.0;
            }
            else
            {
                double a1 = Math.Exp(-Math.Sqrt(2.0) * Math.PI / period);
                double b1 = 2.0 * a1 * Math.Cos(Math.Sqrt(2.0) * Math.PI / period);
                double c2 = b1;
                double c3 = -(a1 * a1);
                double c1 = 1.0 - c2 - c3;
                state = c1 * (_close[k] + _close[k - 1]) / 2.0 + c2 * _superState[k - 1] + c3 * _superState[k - 2];
            }
            _superState.Add(state);
            _supersmoother.Add(state);
        }

        private void AppendRoofing(int k, double price, int hpPeriod, int lpPeriod)
        {
            if (k < 2)
            {
                _roofHp.Add(0.0);
                _roofState.Add(0.0);
                _roofing.Add(double.NaN);
                return;
            }

            double angleHp = 0.707 * 2.0 * Math.PI / hpPeriod;
            double alpha = (Math.Cos(angleHp) + Math.Sin(angleHp) - 1.0) / Math.Cos(angleHp);
            double hp = Math.Pow(1.0 - alpha / 2.0, 2.0) * (_close[k] - 2.0 * _close[k - 1] + _close[k - 2])
                + 2.0 * (1.0 - alpha) * _roofHp[k - 1]
                - Math.Pow(1.0 - alpha, 2.0) * _roofHp[k - 2];
            _roofHp.Add(hp);

            double a1 = Math.Exp(-Math.Sqrt(2.0) * Math.PI / lpPeriod);
            double b1 = 2.0 * a1 * Math.Cos(Math.Sqrt(2.0) * Math.PI / lpPeriod);
            double c2 = b1;
            double c3 = -(a1 * a1);
            double c1 = 1.0 - c2 - c3;
            double state = c1 * (hp + _roofHp[k - 1]) / 2.0 + c2 * _roofState[k - 1] + c3 * _roofState[k - 2];
            _roofState.Add(state);
            _roofing.Add(state);
        }

        private double ReturnFloat32(int k, int lag)
        {
            if (k < lag || _close[k - lag] == 0.0) return double.NaN;
            return Float32(_close[k] / _close[k - lag] - 1.0);
        }

        private static double RollingStdAt(IReadOnlyList<double> values, int k, int window, int ddof)
        {
            if (k + 1 < window) return double.NaN;
            int start = k - window + 1;
            double sum = 0.0;
            for (int i = start; i <= k; i++)
            {
                if (!double.IsFinite(values[i])) return double.NaN;
                sum += values[i];
            }
            double mean = sum / window;
            double ss = 0.0;
            for (int i = start; i <= k; i++)
            {
                double d = values[i] - mean;
                ss += d * d;
            }
            return Math.Sqrt(ss / (window - ddof));
        }

        private static double RollingPercentRankAt(IReadOnlyList<double> values, int k, int window)
        {
            if (k + 1 < window) return double.NaN;
            double current = values[k];
            if (!double.IsFinite(current)) return double.NaN;
            int start = k - window + 1;
            int valid = 0, le = 0;
            for (int i = start; i <= k; i++)
            {
                double value = values[i];
                if (!double.IsFinite(value)) continue;
                valid++;
                if (value <= current) le++;
            }
            return valid == window ? Float32((double)le / valid) : double.NaN;
        }

        private double VwapAt(int k, int window)
        {
            if (k + 1 < window) return double.NaN;
            int start = k - window + 1;
            double numerator = 0.0, denominator = 0.0;
            for (int i = start; i <= k; i++)
            {
                double typical = (_high[i] + _low[i] + _close[i]) / 3.0;
                numerator += typical * _volume[i];
                denominator += _volume[i];
            }
            return denominator == 0.0 ? double.NaN : numerator / denominator;
        }

        private double RobustZAt(int k, int window, double madScale)
        {
            int end = k - 1;
            int start = end - window + 1;
            if (start < 0 || !double.IsFinite(_closeRet[k])) return double.NaN;
            var sample = new double[window];
            for (int i = 0; i < window; i++)
            {
                double value = _closeRet[start + i];
                if (!double.IsFinite(value)) return double.NaN;
                sample[i] = value;
            }
            double median = Median(sample);
            var deviations = new double[window];
            for (int i = 0; i < window; i++) deviations[i] = Math.Abs(sample[i] - median);
            double mad = Median(deviations);
            double denom = mad * madScale;
            return denom == 0.0 ? double.NaN : Float32((_closeRet[k] - median) / denom);
        }

        private static double Median(double[] values)
        {
            var copy = (double[])values.Clone();
            Array.Sort(copy);
            int n = copy.Length;
            return (n & 1) == 1 ? copy[n / 2] : (copy[n / 2 - 1] + copy[n / 2]) / 2.0;
        }

        private static double EmaAlignment(double fast, double mid, double slow)
        {
            if (fast > mid && mid > slow) return 1.0;
            if (fast < mid && mid < slow) return -1.0;
            return 0.0;
        }

        private static double Lag(IReadOnlyList<double> values, int k, int lag) => k >= lag ? values[k - lag] : double.NaN;
        private static double Diff(IReadOnlyList<double> values, int k, int lag) => k >= lag ? values[k] - values[k - lag] : double.NaN;
        private static double Float32(double value) => (double)(float)value;

        private static double SafeDivide(double numerator, double denominator)
        {
            if (!double.IsFinite(numerator) || !double.IsFinite(denominator) || denominator == 0.0) return double.NaN;
            return numerator / denominator;
        }

        private static double RatioFloat32(double numerator, double denominator, double subtract)
        {
            if (!double.IsFinite(numerator) || !double.IsFinite(denominator) || Math.Abs(denominator) <= RatioEps) return double.NaN;
            return Float32(numerator / denominator - subtract);
        }

        private static double Min(IReadOnlyList<double> values, int start, int count)
        {
            double result = double.PositiveInfinity;
            for (int i = start; i < start + count; i++) result = Math.Min(result, values[i]);
            return result;
        }

        private static double Max(IReadOnlyList<double> values, int start, int count)
        {
            double result = double.NegativeInfinity;
            for (int i = start; i < start + count; i++) result = Math.Max(result, values[i]);
            return result;
        }

        private static double Mod(double x, double m) => ((x % m) + m) % m;
    }
}
