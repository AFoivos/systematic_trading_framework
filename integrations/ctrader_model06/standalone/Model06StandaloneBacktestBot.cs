using System;
using System.Globalization;
using cAlgo.API;
using cAlgo.API.Internals;
using CTraderModel06Standalone;

namespace cAlgo.Robots
{
    /// <summary>
    /// Standalone ETHUSD M30 Model06 cBot.
    ///
    /// No Python, HTTP, LightGBM runtime, or external model file is required.
    /// The embedded predictor contains the 800 fitted LightGBM trees and the
    /// streaming feature engine carries the recursive feature state bar-by-bar.
    /// </summary>
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class Model06StandaloneBacktestBot : Robot
    {
        private const string Label = "Model06Standalone";
        private const double UpperThreshold = 0.70;
        private const double LowerThreshold = -0.85;

        [Parameter("Feature history start (UTC)", DefaultValue = "2020-01-01")]
        public string FeatureHistoryStart { get; set; }

        [Parameter("Target exposure", DefaultValue = 0.60, MinValue = 0.01, MaxValue = 1.0)]
        public double TargetExposure { get; set; }

        [Parameter("Minimum holding bars", DefaultValue = 24, MinValue = 1)]
        public int MinimumHoldingBars { get; set; }

        [Parameter("Research DD guard", DefaultValue = true)]
        public bool EnableDrawdownGuard { get; set; }

        [Parameter("DD trigger", DefaultValue = 0.075, MinValue = 0.001, MaxValue = 0.50)]
        public double DrawdownTrigger { get; set; }

        [Parameter("DD cooloff bars", DefaultValue = 48, MinValue = 0, MaxValue = 10000)]
        public int DrawdownCooloffBars { get; set; }

        [Parameter("DD rearm", DefaultValue = 0.055, MinValue = 0.001, MaxValue = 0.50)]
        public double DrawdownRearm { get; set; }

        [Parameter("Maximum spread (pips)", DefaultValue = 80.0, MinValue = 0.0)]
        public double MaximumSpreadPips { get; set; }

        [Parameter("Enable orders", DefaultValue = true)]
        public bool EnableOrders { get; set; }

        [Parameter("Verbose log", DefaultValue = false)]
        public bool VerboseLog { get; set; }

        private Model06StreamingFeatures _features;
        private DateTime? _lastFedBarTime;
        private DateTime _historyStartUtc;

        // Minimum-holding state is intentionally independent from actual broker
        // positions. Research applies holding to desired positions before the DD
        // guard; a risk flatten therefore must not reset the model holding clock.
        private bool _holdingInitialized;
        private int _heldSignal;
        private int _barsSinceDesiredSwitch;

        // Research-style drawdown guard state.
        private double _peakEquity;
        private bool _guardArmed;
        private int _cooloffRemaining;
        private int _guardTriggerCount;

        protected override void OnStart()
        {
            if (!string.Equals(SymbolName, "ETHUSD", StringComparison.OrdinalIgnoreCase))
                Print("WARNING: Model06 research symbol is ETHUSD; current={0}", SymbolName);
            if (!string.Equals(TimeFrame.ToString(), "Minute30", StringComparison.OrdinalIgnoreCase))
                Print("WARNING: Model06 research timeframe is M30; current={0}", TimeFrame);

            if (!DateTime.TryParse(
                    FeatureHistoryStart,
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal,
                    out _historyStartUtc))
            {
                throw new ArgumentException("Feature history start must be a valid UTC date, e.g. 2020-01-01.");
            }

            if (DrawdownRearm > DrawdownTrigger)
                throw new ArgumentException("DD rearm must be <= DD trigger.");

            LoadFeatureHistory();

            _features = new Model06StreamingFeatures();
            _lastFedBarTime = null;
            _holdingInitialized = false;
            _heldSignal = 0;
            _barsSinceDesiredSwitch = MinimumHoldingBars;
            _peakEquity = Account.Equity;
            _guardArmed = true;
            _cooloffRemaining = 0;
            _guardTriggerCount = 0;

            Print(
                "Model06 standalone started. trees={0}, features={1}, bars_loaded={2}, first_bar={3:O}, history_start={4:O}",
                Model06Predictor.TreeCount,
                Model06Predictor.FeatureCount,
                Bars.Count,
                Bars.Count > 0 ? Bars.OpenTimes[0] : DateTime.MinValue,
                _historyStartUtc);
        }

        protected override void OnBarClosed()
        {
            try
            {
                if (Bars.Count == 0)
                    return;

                int latestClosedIndex = Bars.Count - 1;
                DateTime latestClosedTime = Bars.OpenTimes[latestClosedIndex].ToUniversalTime();

                double[] latestFeatures = FeedThrough(latestClosedIndex, latestClosedTime);
                if (latestFeatures == null)
                    return;

                double prediction = Model06Predictor.Predict(latestFeatures);
                bool filtersPassed = FiltersPassed(latestFeatures);
                int rawSignal = SignalFrom(prediction, filtersPassed);
                int desiredSignal = ApplyMinimumHolding(rawSignal);

                bool riskGuardActive = UpdateDrawdownGuard(advanceBar: true);
                int executableSignal = riskGuardActive ? 0 : desiredSignal;

                if (VerboseLog || rawSignal != 0 || executableSignal != CurrentBrokerSignal())
                {
                    Print(
                        "bar={0:O} pred={1:F9} raw={2} held={3} exec={4} filters={5} hold={6} dd={7:P3} cooloff={8}",
                        latestClosedTime,
                        prediction,
                        rawSignal,
                        desiredSignal,
                        executableSignal,
                        filtersPassed,
                        _barsSinceDesiredSwitch,
                        CurrentDrawdown(),
                        _cooloffRemaining);
                }

                ReconcileBrokerPosition(executableSignal);

                // cTrader may apply spread/commission immediately on execution.
                // Re-evaluate after the trade so a newly crossed DD threshold is
                // flattened on the same bar as closely as broker accounting allows.
                if (EnableDrawdownGuard && UpdateDrawdownGuard(advanceBar: false) && CurrentBrokerSignal() != 0)
                    CloseStrategyPositions("dd_guard_after_execution");
            }
            catch (Exception ex)
            {
                Print("Model06 standalone fail-closed: {0}: {1}", ex.GetType().Name, ex.Message);
                CloseStrategyPositions("exception_fail_closed");
            }
        }

        private void LoadFeatureHistory()
        {
            int calls = 0;
            int totalLoaded = 0;

            while (Bars.Count == 0 || Bars.OpenTimes[0].ToUniversalTime() > _historyStartUtc)
            {
                int loaded = Bars.LoadMoreHistory();
                calls++;
                if (loaded <= 0)
                    break;
                totalLoaded += loaded;

                // Defensive bound against a broker/API anomaly.
                if (calls >= 1000)
                    break;
            }

            if (Bars.Count == 0)
                throw new InvalidOperationException("No M30 bars are available for Model06 feature initialization.");

            DateTime first = Bars.OpenTimes[0].ToUniversalTime();
            if (first > _historyStartUtc)
            {
                Print(
                    "WARNING: requested feature history starts {0:O}, but earliest available bar is {1:O}. Recursive feature state will begin there.",
                    _historyStartUtc,
                    first);
            }

            Print("Feature history load calls={0}, added={1}, bars={2}", calls, totalLoaded, Bars.Count);
        }

        private double[] FeedThrough(int latestClosedIndex, DateTime latestClosedTime)
        {
            double[] latest = null;

            for (int i = 0; i <= latestClosedIndex; i++)
            {
                DateTime time = Bars.OpenTimes[i].ToUniversalTime();
                if (time < _historyStartUtc)
                    continue;
                if (_lastFedBarTime.HasValue && time <= _lastFedBarTime.Value)
                    continue;

                bool ready = _features.TryAdd(
                    new Model06Features.Bar(
                        time,
                        Bars.OpenPrices[i],
                        Bars.HighPrices[i],
                        Bars.LowPrices[i],
                        Bars.ClosePrices[i],
                        Bars.TickVolumes[i]),
                    out var row);

                _lastFedBarTime = time;
                if (ready && time == latestClosedTime)
                    latest = row;
            }

            return latest;
        }

        private static bool FiltersPassed(double[] features)
        {
            return
                features[23] >= 0.25 &&
                features[23] <= 0.85 &&
                features[45] >= 0.8999999999999999 &&
                features[29] >= 0.40;
        }

        private static int SignalFrom(double prediction, bool filtersPassed)
        {
            if (!filtersPassed) return 0;
            if (prediction >= UpperThreshold) return 1;
            if (prediction <= LowerThreshold) return -1;
            return 0;
        }

        private int ApplyMinimumHolding(int proposedSignal)
        {
            if (!_holdingInitialized)
            {
                _holdingInitialized = true;
                _heldSignal = proposedSignal;
                _barsSinceDesiredSwitch = _heldSignal == 0 ? MinimumHoldingBars : 1;
                return _heldSignal;
            }

            bool switching = proposedSignal != _heldSignal;
            if (switching && _barsSinceDesiredSwitch < MinimumHoldingBars)
            {
                _barsSinceDesiredSwitch++;
                return _heldSignal;
            }

            if (switching)
            {
                _heldSignal = proposedSignal;
                _barsSinceDesiredSwitch = 1;
            }
            else
            {
                _barsSinceDesiredSwitch++;
            }

            return _heldSignal;
        }

        private bool UpdateDrawdownGuard(bool advanceBar)
        {
            if (_peakEquity <= 0.0 || Account.Equity > _peakEquity)
                _peakEquity = Account.Equity;

            if (!EnableDrawdownGuard)
                return false;

            double drawdown = CurrentDrawdown();
            if (!_guardArmed && drawdown <= DrawdownRearm)
                _guardArmed = true;

            bool breach =
                _guardArmed &&
                DrawdownCooloffBars > 0 &&
                drawdown >= DrawdownTrigger;

            if (breach)
            {
                _guardArmed = false;
                _cooloffRemaining = Math.Max(_cooloffRemaining, DrawdownCooloffBars);
                _guardTriggerCount++;
                if (VerboseLog)
                    Print("DD GUARD trigger #{0}: dd={1:P3}, cooloff={2}", _guardTriggerCount, drawdown, _cooloffRemaining);
            }

            bool active = breach || _cooloffRemaining > 0;
            if (advanceBar && active && _cooloffRemaining > 0)
                _cooloffRemaining--;

            return active;
        }

        private double CurrentDrawdown()
        {
            if (_peakEquity <= 0.0) return 0.0;
            return Math.Max(0.0, (_peakEquity - Account.Equity) / _peakEquity);
        }

        private int CurrentBrokerSignal()
        {
            var positions = Positions.FindAll(Label, SymbolName);
            if (positions.Length == 0) return 0;
            return positions[0].TradeType == TradeType.Buy ? 1 : -1;
        }

        private void ReconcileBrokerPosition(int targetSignal)
        {
            int currentSignal = CurrentBrokerSignal();
            if (currentSignal == targetSignal)
                return;

            if (currentSignal != 0)
                CloseStrategyPositions("target_change");

            if (targetSignal == 0 || !EnableOrders)
                return;

            double spreadPips = Symbol.PipSize > 0.0 ? Symbol.Spread / Symbol.PipSize : 0.0;
            if (spreadPips > MaximumSpreadPips)
            {
                if (VerboseLog)
                    Print("Spread blocked entry: {0:F3} > {1:F3} pips", spreadPips, MaximumSpreadPips);
                return;
            }

            double volume = CalculateTargetVolume();
            if (volume < Symbol.VolumeInUnitsMin)
            {
                Print("Target volume below symbol minimum: {0}", volume);
                return;
            }

            var type = targetSignal > 0 ? TradeType.Buy : TradeType.Sell;
            var result = ExecuteMarketOrder(type, SymbolName, volume, Label);
            if (!result.IsSuccessful)
                Print("Order failed: {0}", result.Error);
            else if (VerboseLog)
                Print("Opened {0}, units={1}, id={2}", type, volume, result.Position.Id);
        }

        private double CalculateTargetVolume()
        {
            double mid = (Symbol.Bid + Symbol.Ask) / 2.0;
            if (mid <= 0.0) return 0.0;
            double rawUnits = Account.Equity * TargetExposure / mid;
            double normalized = Symbol.NormalizeVolumeInUnits(rawUnits, RoundingMode.Down);
            return Math.Min(normalized, Symbol.VolumeInUnitsMax);
        }

        private void CloseStrategyPositions(string reason)
        {
            foreach (var position in Positions.FindAll(Label, SymbolName))
            {
                var result = ClosePosition(position);
                if (VerboseLog || !result.IsSuccessful)
                    Print("Close reason={0}, id={1}, success={2}", reason, position.Id, result.IsSuccessful);
            }
        }
    }
}
