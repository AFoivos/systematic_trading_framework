using System.Globalization;
using CTraderModel06Standalone;

CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
CultureInfo.CurrentUICulture = CultureInfo.InvariantCulture;

var repoRoot = FindRepoRoot(AppContext.BaseDirectory);
var referencePath = Path.Combine(repoRoot, "integrations", "ctrader_model06", "standalone", "model06_python_reference.csv");
var rawPath = Path.Combine(repoRoot, "data", "raw", "dukascopy_30m_clean", "ethusd_30m.csv");

Console.WriteLine(new string('=', 72));
Console.WriteLine("MODEL06 STANDALONE C# PARITY");
Console.WriteLine(new string('=', 72));

var reference = LoadCsv(referencePath);
RunModelOnlyParity(reference);
Console.WriteLine();
RunFeatureAndModelParity(reference, rawPath);
Console.WriteLine();
RunStreamingParity(reference, rawPath);

static void RunModelOnlyParity(CsvTable reference)
{
    long rows = 0, exact = 0;
    double maxErr = 0.0, sumErr = 0.0;
    foreach (var row in reference.Rows)
    {
        var x = new double[Model06Predictor.FeatureCount];
        for (int i = 0; i < x.Length; i++) x[i] = Parse(row[reference.Index[Model06Predictor.FeatureOrder[i]]]);
        double expected = Parse(row[reference.Index["pred_ret"]]);
        double got = Model06Predictor.Predict(x);
        double e = Math.Abs(got - expected);
        rows++; if (got == expected) exact++; maxErr = Math.Max(maxErr, e); sumErr += e;
    }
    Console.WriteLine("MODEL-ONLY PARITY");
    Console.WriteLine($"Rows:           {rows}");
    Console.WriteLine($"Exact:          {exact}/{rows}");
    Console.WriteLine($"Max abs error:  {maxErr:R}");
    Console.WriteLine($"Mean abs error: {(rows == 0 ? double.NaN : sumErr / rows):R}");
    if (maxErr > 1e-7) throw new Exception("Model-only parity failed.");
}

static void RunFeatureAndModelParity(CsvTable reference, string rawPath)
{
    Console.WriteLine("FEATURE + MODEL PARITY (single pass)");
    var raw = LoadCsv(rawPath);
    string timeCol = FindColumn(raw.Index, "time", "timestamp", "datetime", "date", "open_time");
    string openCol = FindColumn(raw.Index, "open");
    string highCol = FindColumn(raw.Index, "high");
    string lowCol = FindColumn(raw.Index, "low");
    string closeCol = FindColumn(raw.Index, "close");
    string volumeCol = FindColumn(raw.Index, "volume");

    var bars = new List<Model06Features.Bar>(raw.Rows.Count);
    var barIndexByTime = new Dictionary<string, int>(StringComparer.Ordinal);
    foreach (var row in raw.Rows)
    {
        var dt = DateTime.Parse(row[raw.Index[timeCol]], CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
        bars.Add(new Model06Features.Bar(
            dt,
            Parse(row[raw.Index[openCol]]),
            Parse(row[raw.Index[highCol]]),
            Parse(row[raw.Index[lowCol]]),
            Parse(row[raw.Index[closeCol]]),
            Parse(row[raw.Index[volumeCol]])));
        barIndexByTime[NormalizeTime(dt)] = bars.Count - 1;
    }

    var matchedRows = new List<string[]>();
    var requestedIndices = new List<int>();
    foreach (var row in reference.Rows)
    {
        var dt = DateTime.Parse(row[reference.Index["time"]], CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
        if (!barIndexByTime.TryGetValue(NormalizeTime(dt), out int index))
            continue;
        matchedRows.Add(row);
        requestedIndices.Add(index);
    }

    if (matchedRows.Count == 0)
        throw new Exception("No timestamp overlap between Python reference and raw CSV.");

    Console.WriteLine($"Raw bars:        {bars.Count}");
    Console.WriteLine($"Reference rows:  {reference.Rows.Count}");
    Console.WriteLine($"Matched rows:    {matchedRows.Count}");
    Console.WriteLine("Computing all requested C# feature rows in one pipeline pass...");

    var computed = Model06Features.ComputeRows(bars, requestedIndices);
    var perFeatureMax = new double[Model06Predictor.FeatureCount];
    var perFeatureSum = new double[Model06Predictor.FeatureCount];
    var perFeatureExact = new long[Model06Predictor.FeatureCount];
    double maxPredErr = 0.0, sumPredErr = 0.0;
    long predExact = 0;
    long signalExact = 0;
    long filterExact = 0;
    string? worstFeature = null;
    double worstFeatureErr = 0.0;
    string? worstFeatureTime = null;
    double worstExpected = 0.0, worstGot = 0.0;

    int SignalFrom(double pred, double[] x)
    {
        bool filters =
            x[23] >= 0.25 &&
            x[23] <= 0.85 &&
            x[45] >= 0.8999999999999999 &&
            x[29] >= 0.4;
        if (!filters) return 0;
        if (pred >= 0.7) return 1;
        if (pred <= -0.85) return -1;
        return 0;
    }

    bool FiltersFrom(double[] x) =>
        x[23] >= 0.25 &&
        x[23] <= 0.85 &&
        x[45] >= 0.8999999999999999 &&
        x[29] >= 0.4;

    for (int r = 0; r < matchedRows.Count; r++)
    {
        var row = matchedRows[r];
        var x = computed[r];
        var time = row[reference.Index["time"]];
        for (int i = 0; i < x.Length; i++)
        {
            double expectedFeature = Parse(row[reference.Index[Model06Predictor.FeatureOrder[i]]]);
            double error = Math.Abs(x[i] - expectedFeature);
            perFeatureSum[i] += error;
            if (x[i] == expectedFeature) perFeatureExact[i]++;
            if (error > perFeatureMax[i]) perFeatureMax[i] = error;
            if (error > worstFeatureErr)
            {
                worstFeatureErr = error;
                worstFeature = Model06Predictor.FeatureOrder[i];
                worstFeatureTime = time;
                worstExpected = expectedFeature;
                worstGot = x[i];
            }
        }

        double expectedPred = Parse(row[reference.Index["pred_ret"]]);
        double pred = Model06Predictor.Predict(x);
        double predErr = Math.Abs(pred - expectedPred);
        if (pred == expectedPred) predExact++;
        if (predErr > maxPredErr) maxPredErr = predErr;
        sumPredErr += predErr;

        int expectedSignal = SignalFrom(expectedPred, Enumerable.Range(0, 48)
            .Select(i => Parse(row[reference.Index[Model06Predictor.FeatureOrder[i]]])).ToArray());
        int gotSignal = SignalFrom(pred, x);
        if (expectedSignal == gotSignal) signalExact++;

        bool expectedFilters = FiltersFrom(Enumerable.Range(0, 48)
            .Select(i => Parse(row[reference.Index[Model06Predictor.FeatureOrder[i]]])).ToArray());
        bool gotFilters = FiltersFrom(x);
        if (expectedFilters == gotFilters) filterExact++;
    }

    Console.WriteLine();
    Console.WriteLine($"Prediction exact:       {predExact}/{matchedRows.Count}");
    Console.WriteLine($"Prediction max error:   {maxPredErr:R}");
    Console.WriteLine($"Prediction mean error:  {(sumPredErr / matchedRows.Count):R}");
    Console.WriteLine($"Signal exact:           {signalExact}/{matchedRows.Count}");
    Console.WriteLine($"Filters exact:          {filterExact}/{matchedRows.Count}");
    Console.WriteLine($"Worst feature:          {worstFeature}");
    Console.WriteLine($"Worst feature time:     {worstFeatureTime}");
    Console.WriteLine($"Worst expected:         {worstExpected:R}");
    Console.WriteLine($"Worst C# value:         {worstGot:R}");
    Console.WriteLine($"Worst feature error:    {worstFeatureErr:R}");
    Console.WriteLine();
    Console.WriteLine("Top feature errors:");
    foreach (var item in perFeatureMax
        .Select((e, i) => new
        {
            Name = Model06Predictor.FeatureOrder[i],
            Max = e,
            Mean = perFeatureSum[i] / matchedRows.Count,
            Exact = perFeatureExact[i]
        })
        .OrderByDescending(x => x.Max)
        .Take(16))
    {
        Console.WriteLine($"  {item.Name,-40} max={item.Max,20:R} mean={item.Mean,20:R} exact={item.Exact}/{matchedRows.Count}");
    }

    if (maxPredErr > 1e-5 || signalExact != matchedRows.Count || filterExact != matchedRows.Count)
        throw new Exception("Feature+model parity is not acceptable yet; inspect the reported errors.");

    Console.WriteLine("PASS: single-pass C# features + model + filters + signal match the Python reference tolerance.");
}


static void RunStreamingParity(CsvTable reference, string rawPath)
{
    Console.WriteLine("STREAMING FEATURE + MODEL PARITY");
    var raw = LoadCsv(rawPath);
    string timeCol = FindColumn(raw.Index, "time", "timestamp", "datetime", "date", "open_time");
    string openCol = FindColumn(raw.Index, "open");
    string highCol = FindColumn(raw.Index, "high");
    string lowCol = FindColumn(raw.Index, "low");
    string closeCol = FindColumn(raw.Index, "close");
    string volumeCol = FindColumn(raw.Index, "volume");

    var referenceByTime = new Dictionary<string, string[]>(StringComparer.Ordinal);
    foreach (var row in reference.Rows)
    {
        var dt = DateTime.Parse(row[reference.Index["time"]], CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
        referenceByTime[NormalizeTime(dt)] = row;
    }

    var engine = new Model06StreamingFeatures();
    var perFeatureMax = new double[Model06Predictor.FeatureCount];
    var perFeatureSum = new double[Model06Predictor.FeatureCount];
    var perFeatureExact = new long[Model06Predictor.FeatureCount];
    long matched = 0, predExact = 0, signalExact = 0, filterExact = 0;
    double maxPredErr = 0.0, sumPredErr = 0.0;
    string? worstFeature = null, worstTime = null;
    double worstFeatureErr = 0.0, worstExpected = 0.0, worstGot = 0.0;

    int SignalFrom(double pred, double[] x)
    {
        bool filters = x[23] >= 0.25 && x[23] <= 0.85 && x[45] >= 0.8999999999999999 && x[29] >= 0.4;
        if (!filters) return 0;
        if (pred >= 0.7) return 1;
        if (pred <= -0.85) return -1;
        return 0;
    }

    bool FiltersFrom(double[] x) =>
        x[23] >= 0.25 && x[23] <= 0.85 && x[45] >= 0.8999999999999999 && x[29] >= 0.4;

    foreach (var rawRow in raw.Rows)
    {
        var dt = DateTime.Parse(rawRow[raw.Index[timeCol]], CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
        var bar = new Model06Features.Bar(
            dt,
            Parse(rawRow[raw.Index[openCol]]),
            Parse(rawRow[raw.Index[highCol]]),
            Parse(rawRow[raw.Index[lowCol]]),
            Parse(rawRow[raw.Index[closeCol]]),
            Parse(rawRow[raw.Index[volumeCol]]));

        bool ready = engine.TryAdd(bar, out var x);
        string key = NormalizeTime(dt);
        if (!referenceByTime.TryGetValue(key, out var expectedRow))
            continue;
        if (!ready)
            throw new Exception($"Streaming engine was not ready for reference timestamp {key}.");

        matched++;
        for (int i = 0; i < x.Length; i++)
        {
            double expected = Parse(expectedRow[reference.Index[Model06Predictor.FeatureOrder[i]]]);
            double err = Math.Abs(x[i] - expected);
            perFeatureSum[i] += err;
            if (x[i] == expected) perFeatureExact[i]++;
            if (err > perFeatureMax[i]) perFeatureMax[i] = err;
            if (err > worstFeatureErr)
            {
                worstFeatureErr = err;
                worstFeature = Model06Predictor.FeatureOrder[i];
                worstTime = key;
                worstExpected = expected;
                worstGot = x[i];
            }
        }

        double expectedPred = Parse(expectedRow[reference.Index["pred_ret"]]);
        double pred = Model06Predictor.Predict(x);
        double predErr = Math.Abs(pred - expectedPred);
        if (pred == expectedPred) predExact++;
        maxPredErr = Math.Max(maxPredErr, predErr);
        sumPredErr += predErr;

        var expectedFeatures = new double[48];
        for (int i = 0; i < 48; i++)
            expectedFeatures[i] = Parse(expectedRow[reference.Index[Model06Predictor.FeatureOrder[i]]]);
        if (SignalFrom(pred, x) == SignalFrom(expectedPred, expectedFeatures)) signalExact++;
        if (FiltersFrom(x) == FiltersFrom(expectedFeatures)) filterExact++;
    }

    Console.WriteLine($"Raw bars processed:      {engine.Count}");
    Console.WriteLine($"Reference rows matched:  {matched}/{reference.Rows.Count}");
    Console.WriteLine($"Prediction exact:        {predExact}/{matched}");
    Console.WriteLine($"Prediction max error:    {maxPredErr:R}");
    Console.WriteLine($"Prediction mean error:   {(matched == 0 ? double.NaN : sumPredErr / matched):R}");
    Console.WriteLine($"Signal exact:            {signalExact}/{matched}");
    Console.WriteLine($"Filters exact:           {filterExact}/{matched}");
    Console.WriteLine($"Worst feature:           {worstFeature}");
    Console.WriteLine($"Worst feature time:      {worstTime}");
    Console.WriteLine($"Worst expected:          {worstExpected:R}");
    Console.WriteLine($"Worst streaming value:   {worstGot:R}");
    Console.WriteLine($"Worst feature error:     {worstFeatureErr:R}");
    Console.WriteLine("Top streaming feature errors:");
    foreach (var item in perFeatureMax
        .Select((e, i) => new { Name = Model06Predictor.FeatureOrder[i], Max = e, Mean = matched == 0 ? double.NaN : perFeatureSum[i] / matched, Exact = perFeatureExact[i] })
        .OrderByDescending(x => x.Max)
        .Take(16))
    {
        Console.WriteLine($"  {item.Name,-40} max={item.Max,20:R} mean={item.Mean,20:R} exact={item.Exact}/{matched}");
    }

    if (matched != reference.Rows.Count)
        throw new Exception($"Streaming parity matched {matched}/{reference.Rows.Count} reference rows.");
    if (maxPredErr > 1e-5 || signalExact != matched || filterExact != matched)
        throw new Exception("Streaming feature+model parity failed; inspect the reported errors.");
    Console.WriteLine("PASS: streaming C# features + model + filters + signal match Python reference tolerance.");
}

static double Parse(string s) => double.Parse(s, NumberStyles.Float, CultureInfo.InvariantCulture);
static string NormalizeTime(DateTime dt) => dt.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);

static string FindColumn(Dictionary<string,int> index, params string[] candidates)
{
    foreach (var c in candidates)
    {
        var hit = index.Keys.FirstOrDefault(k => string.Equals(k, c, StringComparison.OrdinalIgnoreCase));
        if (hit != null) return hit;
    }
    throw new InvalidOperationException($"Could not find required CSV column. Candidates: {string.Join(", ", candidates)}");
}

static CsvTable LoadCsv(string path)
{
    if (!File.Exists(path)) throw new FileNotFoundException("CSV not found", path);
    using var reader = new StreamReader(path);
    var headers = SplitCsvLine(reader.ReadLine() ?? throw new InvalidOperationException("Empty CSV"));
    var index = headers.Select((x,i)=>(x,i)).ToDictionary(x=>x.x,x=>x.i,StringComparer.Ordinal);
    var rows = new List<string[]>();
    string? line;
    while ((line = reader.ReadLine()) != null) if (!string.IsNullOrWhiteSpace(line)) rows.Add(SplitCsvLine(line));
    return new CsvTable(index, rows);
}

static string[] SplitCsvLine(string line)
{
    var result = new List<string>(); var current = new System.Text.StringBuilder(); bool quoted = false;
    for (int i = 0; i < line.Length; i++)
    {
        char ch = line[i];
        if (ch == '"') { if (quoted && i + 1 < line.Length && line[i + 1] == '"') { current.Append('"'); i++; } else quoted = !quoted; }
        else if (ch == ',' && !quoted) { result.Add(current.ToString()); current.Clear(); }
        else current.Append(ch);
    }
    result.Add(current.ToString()); return result.ToArray();
}

static string FindRepoRoot(string start)
{
    for (var d = new DirectoryInfo(start); d != null; d = d.Parent)
        if (Directory.Exists(Path.Combine(d.FullName, "integrations", "ctrader_model06"))) return d.FullName;
    throw new DirectoryNotFoundException("Repository root not found.");
}

sealed record CsvTable(Dictionary<string,int> Index, List<string[]> Rows);
