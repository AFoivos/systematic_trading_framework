using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class Model06ThinBridge : Robot
    {
        private const string Label = "Model06Conservative";
        private const string StateKey = "Model06 State";

        [Parameter("Inference URL", DefaultValue = "http://127.0.0.1:8765/predict")]
        public string InferenceUrl { get; set; }

        [Parameter("API token", DefaultValue = "")]
        public string ApiToken { get; set; }

        [Parameter("Bars to send", DefaultValue = 1500, MinValue = 1200, MaxValue = 3000)]
        public int BarsToSend { get; set; }

        [Parameter("Target exposure", DefaultValue = 0.60, MinValue = 0.01, MaxValue = 1.0)]
        public double TargetExposure { get; set; }

        [Parameter("Minimum holding bars", DefaultValue = 24, MinValue = 1)]
        public int MinimumHoldingBars { get; set; }

        [Parameter("Daily loss limit", DefaultValue = 0.015, MinValue = 0.001, MaxValue = 0.10)]
        public double DailyLossLimit { get; set; }

        [Parameter("Total drawdown limit", DefaultValue = 0.075, MinValue = 0.001, MaxValue = 0.20)]
        public double TotalDrawdownLimit { get; set; }

        [Parameter("Maximum spread (pips)", DefaultValue = 80.0, MinValue = 0.0)]
        public double MaximumSpreadPips { get; set; }

        [Parameter("Enable demo orders", DefaultValue = false)]
        public bool EnableOrders { get; set; }

        private RuntimeState _state;
        private string _lastProcessedBar;

        protected override void OnStart()
        {
            _state = LoadState();
            RefreshEquityBaselines();
            Print("Model06 bridge started. Orders enabled={0}, symbol={1}, timeframe={2}",
                EnableOrders, SymbolName, TimeFrame);

            var healthRequest = new HttpRequest(new Uri(InferenceUrl.Replace("/predict", "/health")));
            healthRequest.Method = HttpMethod.Get;
            if (!string.IsNullOrWhiteSpace(ApiToken))
                healthRequest.Headers.Add("X-Model06-Token", ApiToken);
            var health = Http.Send(healthRequest);
            if (!health.IsSuccessful)
                Print("WARNING: inference health check failed: status={0}, body={1}", health.StatusCode, health.Body);
            else
                Print("Inference service healthy: {0}", health.Body);
        }

        protected override void OnBarClosed()
        {
            try
            {
                RefreshEquityBaselines();
                if (RiskLimitBreached())
                {
                    CloseStrategyPositions("risk_limit");
                    return;
                }

                if (Bars.Count < BarsToSend)
                {
                    Print("Waiting for bars: have {0}, need {1}", Bars.Count, BarsToSend);
                    return;
                }

                var latestBarTime = Bars.OpenTimes.LastValue.ToUniversalTime().ToString("O");
                if (latestBarTime == _lastProcessedBar)
                    return;

                _lastProcessedBar = latestBarTime;
                var response = RequestPrediction(latestBarTime);
                if (response == null || !response.Ok)
                {
                    Print("Prediction rejected or unavailable. No order sent.");
                    return;
                }
                DateTime expectedBarTime;
                DateTime receivedBarTime;
                var expectedParsed = DateTime.TryParse(
                    latestBarTime,
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal,
                    out expectedBarTime);
                var receivedParsed = DateTime.TryParse(
                    response.BarTime,
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal,
                    out receivedBarTime);
                if (!expectedParsed || !receivedParsed || expectedBarTime != receivedBarTime)
                {
                    Print("Stale/mismatched response bar. expected={0}, received={1}", latestBarTime, response.BarTime);
                    return;
                }

                Print("Model06 bar={0} pred={1:F6} signal={2} filters={3} latency={4}ms",
                    response.BarTime, response.Prediction, response.Signal, response.FiltersPassed, response.LatencyMs);
                if (!response.FiltersPassed || response.Signal == 0)
                    {
                        Print(
                            "Model06 DEBUG: prediction={0:F6}, signal={1}, filters_passed={2}, upper={3}, lower={4}",
                            response.Prediction,
                            response.Signal,
                            response.FiltersPassed,
                            response.UpperThreshold,
                            response.LowerThreshold
                        );
                    }
                ApplyHoldingContract(response.Signal);
                SaveState();
            }
            catch (Exception ex)
            {
                Print("Model06 fail-closed error: {0}: {1}", ex.GetType().Name, ex.Message);
            }
        }

        protected override void OnTick()
        {
            RefreshEquityBaselines();
            if (RiskLimitBreached())
                CloseStrategyPositions("intrabar_risk_limit");
        }

        protected override void OnStop()
        {
            SaveState();
        }

        private PredictionResponse RequestPrediction(string latestBarTime)
        {
            var start = Math.Max(0, Bars.Count - BarsToSend);
            var bars = new List<BarPayload>(Bars.Count - start);
            for (var i = start; i < Bars.Count; i++)
            {
                bars.Add(new BarPayload
                {
                    Time = Bars.OpenTimes[i].ToUniversalTime().ToString("O"),
                    Open = Bars.OpenPrices[i],
                    High = Bars.HighPrices[i],
                    Low = Bars.LowPrices[i],
                    Close = Bars.ClosePrices[i],
                    Volume = Bars.TickVolumes[i]
                });
            }

            var payload = new PredictionRequest
            {
                RequestId = Guid.NewGuid().ToString("N"),
                Symbol = "ETHUSD",
                Timeframe = "M30",
                Bars = bars
            };
            var json = JsonSerializer.Serialize(payload);
            var request = new HttpRequest(new Uri(InferenceUrl));
            request.Method = HttpMethod.Post;
            request.Body = json;
            request.Headers.Add("Content-Type", "application/json");
            if (!string.IsNullOrWhiteSpace(ApiToken))
                request.Headers.Add("X-Model06-Token", ApiToken);

            var httpResponse = Http.Send(request);
            if (!httpResponse.IsSuccessful)
            {
                Print("Inference HTTP failure status={0}, body={1}", httpResponse.StatusCode, httpResponse.Body);
                return null;
            }
            return JsonSerializer.Deserialize<PredictionResponse>(httpResponse.Body,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        }

        private void ApplyHoldingContract(int targetSignal)
        {
            var positions = Positions.FindAll(Label, SymbolName);
            var currentSignal = positions.Length == 0 ? 0 :
                positions[0].TradeType == TradeType.Buy ? 1 : -1;

            if (currentSignal == targetSignal)
            {
                _state.BarsSinceSwitch += 1;
                return;
            }

            if (currentSignal != 0 && _state.BarsSinceSwitch < MinimumHoldingBars)
            {
                _state.BarsSinceSwitch += 1;
                Print("Holding lock active: {0}/{1} bars", _state.BarsSinceSwitch, MinimumHoldingBars);
                return;
            }

            if (currentSignal != 0)
                CloseStrategyPositions("target_change");

            if (targetSignal == 0)
            {
                _state.BarsSinceSwitch = MinimumHoldingBars;
                return;
            }

            if (!EnableOrders)
            {
                Print("DRY RUN: would open signal={0} at target exposure={1:P1}", targetSignal, TargetExposure);
                _state.BarsSinceSwitch = 1;
                return;
            }

            var spreadPips = Symbol.Spread / Symbol.PipSize;
            if (spreadPips > MaximumSpreadPips)
            {
                Print("Spread blocked entry: {0:F2} pips > {1:F2}", spreadPips, MaximumSpreadPips);
                return;
            }

            var volume = CalculateTargetVolume();
            if (volume < Symbol.VolumeInUnitsMin)
            {
                Print("Computed volume below minimum: {0}", volume);
                return;
            }
            var tradeType = targetSignal > 0 ? TradeType.Buy : TradeType.Sell;
            var result = ExecuteMarketOrder(tradeType, SymbolName, volume, Label);
            if (!result.IsSuccessful)
            {
                Print("Order failed: {0}", result.Error);
                return;
            }
            _state.BarsSinceSwitch = 1;
            Print("Opened {0}, volume={1}, position={2}", tradeType, volume, result.Position.Id);
        }

        private double CalculateTargetVolume()
        {
            var mid = (Symbol.Bid + Symbol.Ask) / 2.0;
            var rawBaseUnits = Account.Equity * TargetExposure / mid;
            var normalized = Symbol.NormalizeVolumeInUnits(rawBaseUnits, RoundingMode.Down);
            return Math.Min(normalized, Symbol.VolumeInUnitsMax);
        }

        private void CloseStrategyPositions(string reason)
        {
            foreach (var position in Positions.FindAll(Label, SymbolName))
            {
                var result = ClosePosition(position);
                Print("Close reason={0}, position={1}, success={2}", reason, position.Id, result.IsSuccessful);
            }
        }

        private void RefreshEquityBaselines()
        {
            var today = Server.Time.Date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            if (string.IsNullOrEmpty(_state.Day) || _state.Day != today)
            {
                _state.Day = today;
                _state.DayStartEquity = Account.Equity;
            }
            if (_state.InitialEquity <= 0)
                _state.InitialEquity = Account.Equity;
            if (_state.PeakEquity <= 0 || Account.Equity > _state.PeakEquity)
                _state.PeakEquity = Account.Equity;
        }

        private bool RiskLimitBreached()
        {
            var dailyLoss = _state.DayStartEquity > 0
                ? (_state.DayStartEquity - Account.Equity) / _state.DayStartEquity : 0.0;
            var drawdown = _state.PeakEquity > 0
                ? (_state.PeakEquity - Account.Equity) / _state.PeakEquity : 0.0;
            var breached = dailyLoss >= DailyLossLimit || drawdown >= TotalDrawdownLimit;
            if (breached)
                Print("RISK STOP daily={0:P3}/{1:P3}, drawdown={2:P3}/{3:P3}",
                    dailyLoss, DailyLossLimit, drawdown, TotalDrawdownLimit);
            return breached;
        }

        private RuntimeState LoadState()
        {
            try
            {
                var json = LocalStorage.GetString(StateKey, LocalStorageScope.Instance);
                if (!string.IsNullOrWhiteSpace(json))
                    return JsonSerializer.Deserialize<RuntimeState>(json) ?? new RuntimeState();
            }
            catch (Exception ex)
            {
                Print("State load failed, starting clean: {0}", ex.Message);
            }
            return new RuntimeState();
        }

        private void SaveState()
        {
            LocalStorage.SetString(StateKey, JsonSerializer.Serialize(_state), LocalStorageScope.Instance);
            LocalStorage.Flush(LocalStorageScope.Instance);
        }

        public class RuntimeState
        {
            public string Day { get; set; }
            public double InitialEquity { get; set; }
            public double DayStartEquity { get; set; }
            public double PeakEquity { get; set; }
            public int BarsSinceSwitch { get; set; } = 24;
        }

        public class PredictionRequest
        {
            [JsonPropertyName("request_id")] public string RequestId { get; set; }
            [JsonPropertyName("symbol")] public string Symbol { get; set; }
            [JsonPropertyName("timeframe")] public string Timeframe { get; set; }
            [JsonPropertyName("bars")] public List<BarPayload> Bars { get; set; }
        }

        public class BarPayload
        {
            [JsonPropertyName("time")] public string Time { get; set; }
            [JsonPropertyName("open")] public double Open { get; set; }
            [JsonPropertyName("high")] public double High { get; set; }
            [JsonPropertyName("low")] public double Low { get; set; }
            [JsonPropertyName("close")] public double Close { get; set; }
            [JsonPropertyName("volume")] public double Volume { get; set; }
        }

        public class PredictionResponse
        {
            [JsonPropertyName("ok")] public bool Ok { get; set; }
            [JsonPropertyName("bar_time")] public string BarTime { get; set; }
            [JsonPropertyName("prediction")] public double Prediction { get; set; }
            [JsonPropertyName("signal")] public int Signal { get; set; }
            [JsonPropertyName("filters_passed")] public bool FiltersPassed { get; set; }
            [JsonPropertyName("latency_ms")] public double LatencyMs { get; set; }
        }
    }
}
