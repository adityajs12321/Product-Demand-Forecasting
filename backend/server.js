const express = require("express");
const cors = require("cors");
const multer = require("multer");
const XLSX = require("xlsx");
const path = require("path");
const fs = require("fs");
const { PythonShell } = require("python-shell");
const Groq = require("groq-sdk");

const app = express();
app.use(express.json());

// ---------------------------------------------------------------------------
// CORS — mirrors the Python backend's FRONTEND_ORIGINS env var behaviour
// ---------------------------------------------------------------------------
const frontendOrigins = process.env.FRONTEND_ORIGINS || "http://localhost:3000";
const origins = frontendOrigins
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);

app.use(
  cors({
    origin: origins,
    credentials: true,
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allowedHeaders: ["*"],
  })
);

// ---------------------------------------------------------------------------
// File upload via multer — stores to backend/uploads/
// ---------------------------------------------------------------------------
const uploadDir = path.join(__dirname, "uploads");
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => cb(null, "tempfile.xlsx"),
});
const upload = multer({ storage });

// ---------------------------------------------------------------------------
// In-memory state — mirrors the Python global variables
// ---------------------------------------------------------------------------
let rawData = null; // Original parsed data (array of row objects)
let columnMap = null; // { unique_id, ds, y, dropped_columns } from Groq LLM
let uploadedFilePath = null; // Path to the uploaded xlsx

// ---------------------------------------------------------------------------
// Groq LLM helper — replaces the Python pre_process_data() Groq call
// ---------------------------------------------------------------------------
async function identifyColumns(columns) {
  const client = new Groq();

  const SYSTEM_PROMPT = `You are a helpful assistant that reads columns of a dataframe and returns the column that corresponds to unique_id, ds and y. The column names may not be exactly unique_id, ds and y but they will be similar. For example, unique_id may be called Description, ds may be called date or time-index and y may be called Quantity, number of items sold. You must also return a list of columns that must be dropped from the dataframe because they were not relevant for forecasting. Ex: Invoice, UserID, Region. DO NOT DROP COLUMNS THAT CAN BE USED AS EXOGENOUS FEATURES, Ex: Price, Calendar Events, etc.

Please ensure your response is a valid JSON object matching this schema:
{
  "unique_id": "string — column name for the product/entity identifier",
  "ds": "string — column name for the date/time index",
  "y": "string — column name for the target value (e.g. quantity sold)",
  "dropped_columns": ["list of column names to drop"]
}`;

  const completion = await client.chat.completions.create({
    model: "llama-3.1-8b-instant",
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      {
        role: "user",
        content: `Here are the columns of the dataframe: ${JSON.stringify(columns)}`,
      },
    ],
    response_format: { type: "json_object" },
  });

  return JSON.parse(completion.choices[0].message.content);
}

// ---------------------------------------------------------------------------
// Excel parsing & preprocessing helpers
// ---------------------------------------------------------------------------
function parseExcel(filePath) {
  const workbook = XLSX.readFile(filePath);
  let allRows = [];
  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(sheet, { defval: null });
    allRows = allRows.concat(rows);
  }
  return allRows;
}

function preprocessData(data, colMap) {
  // Filter rows where y > 0
  let filtered = data.filter((row) => {
    const val = Number(row[colMap.y]);
    return !isNaN(val) && val > 0;
  });

  // Clean unique_id column
  filtered = filtered.map((row) => {
    const id = String(row[colMap.unique_id]).trim();
    return { ...row, [colMap.unique_id]: id };
  });

  // Drop irrelevant columns
  const dropSet = new Set(colMap.dropped_columns || []);
  filtered = filtered.map((row) => {
    const cleaned = {};
    for (const [key, value] of Object.entries(row)) {
      if (!dropSet.has(key)) cleaned[key] = value;
    }
    return cleaned;
  });

  return filtered;
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

app.get("/", (_req, res) => {
  res.json("Hello");
});

// POST /upload — receive an Excel file, parse it, identify columns via Groq
app.post("/upload", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: "No file uploaded" });
    }

    uploadedFilePath = req.file.path;

    // Parse the Excel file
    const data = parseExcel(uploadedFilePath);
    if (!data.length) {
      return res.status(400).json({ message: "File is empty or unreadable" });
    }

    const columns = Object.keys(data[0]);

    // Use Groq LLM to identify columns
    columnMap = await identifyColumns(columns);

    // Preprocess (filter y>0, clean IDs, drop columns)
    rawData = preprocessData(data, columnMap);

    return res.json({
      message: "Data processed successfully",
      rows: rawData.length,
    });
  } catch (err) {
    console.error("Upload error:", err);
    return res.status(500).json({ message: "Failed to process file", error: err.message });
  }
});

// POST /process — run ARIMA or TBATS forecast via Python script
app.post("/process", async (req, res) => {
  try {
    if (!rawData) {
      return res.json({ message: "No data to process" });
    }

    const { product, forecast_model: forecastModel } = req.body;
    if (!product) {
      return res.status(400).json({ message: "Product name is required" });
    }

    const modelId = Number(forecastModel) || 1;

    // Call Python forecasting script
    const result = await runForecast(modelId, product);

    return res.json({
      sales: result.sales,
      timerange: result.timerange,
    });
  } catch (err) {
    console.error("Process error:", err);
    return res.status(500).json({ message: "Forecast failed", error: err.message });
  }
});

// POST /tftpredict — run TFT forecast via Python script
app.post("/tftpredict", async (req, res) => {
  try {
    if (!rawData) {
      return res.json({ message: "No data to process" });
    }

    const { product } = req.body;
    if (!product) {
      return res.status(400).json({ message: "Product name is required" });
    }

    const result = await runForecast(3, product);

    return res.json({
      sales: result.sales,
      timerange: result.timerange,
    });
  } catch (err) {
    console.error("TFT predict error:", err);
    return res.status(500).json({ message: "TFT forecast failed", error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Python-shell helper — runs scripts/forecast.py with JSON I/O
// ---------------------------------------------------------------------------
const RESULT_MARKER = "__FORECAST_RESULT__";

function runForecast(modelId, product, horizon = 21) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(__dirname, "scripts");

    const input = JSON.stringify({
      model: modelId,
      data_path: uploadedFilePath,
      product,
      horizon,
      column_map: columnMap,
    });

    const pyShell = new PythonShell("forecast.py", {
      mode: "text",
      pythonOptions: ["-u"], // unbuffered
      scriptPath,
      // Use the python from PATH (or set PYTHON_PATH env var)
      pythonPath: process.env.PYTHON_PATH || "python3",
    });

    const messages = [];

    pyShell.on("message", (message) => {
      messages.push(message);
    });

    pyShell.on("stderr", (stderr) => {
      // Log Python warnings/info but don't fail
      if (stderr && !stderr.includes("UserWarning")) {
        console.log("[Python]", stderr);
      }
    });

    pyShell.on("error", (err) => {
      reject(new Error(`Python script error: ${err.message}`));
    });

    pyShell.on("close", () => {
      // Find the line with our result marker
      const resultLine = messages.find((m) => m.startsWith(RESULT_MARKER));
      if (resultLine) {
        try {
          const jsonStr = resultLine.slice(RESULT_MARKER.length);
          const result = JSON.parse(jsonStr);
          resolve(result);
        } catch (parseErr) {
          reject(new Error(`Failed to parse forecast JSON: ${parseErr.message}`));
        }
      } else {
        // Fallback: try to parse the last message as JSON
        const lastMsg = messages[messages.length - 1] || "";
        try {
          resolve(JSON.parse(lastMsg));
        } catch {
          reject(
            new Error(
              `No forecast result found in Python output. Messages:\n${messages.join("\n")}`
            )
          );
        }
      }
    });

    // Send the input JSON to Python stdin
    pyShell.send(input);
    pyShell.end();
  });
}

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------
const PORT = parseInt(process.env.PORT, 10) || 10000;
app.listen(PORT, "0.0.0.0", () => {
  console.log(`🚀 Server running on http://0.0.0.0:${PORT}`);
});
