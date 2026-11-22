import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { ai } from './geminiClient.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// Enable CORS for frontend clients
app.use(cors());

// Parse JSON request bodies
app.use(express.json());

// Serve static frontend files from 'public' directory
app.use(express.static(path.join(__dirname, 'public')));

/**
 * Health check endpoint
 */
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    message: 'Backend server is running',
    timestamp: new Date().toISOString()
  });
});

/**
 * Secure Backend API endpoint for Gemini
 */
app.post('/api/generate', async (req, res) => {
  try {
    const { prompt, model } = req.body;

    if (!prompt || typeof prompt !== 'string' || prompt.trim() === '') {
      return res.status(400).json({
        success: false,
        error: 'Missing or invalid "prompt" in request body.'
      });
    }

    const requestedModel = model || 'gemini-3.5-flash-lite';
    
    // Configure request parameters based on model type
    const requestConfig = {};
    if (requestedModel === 'gemini-4-neon') {
      // Allocate thinking budget for high reasoning
      requestConfig.thinkingConfig = { thinkingBudget: 8192 };
    }

    const response = await ai.models.generateContent({
      model: requestedModel,
      contents: prompt,
      config: Object.keys(requestConfig).length > 0 ? requestConfig : undefined
    });

    return res.json({
      success: true,
      model: requestedModel,
      result: response.text
    });
  } catch (error) {
    // Sanitize any error output to prevent accidental key exposure
    const safeErrorMessage = (error.message || 'Unknown error occurred')
      .replace(/([a-zA-Z0-9_\-\.]{30,})/g, '[REDACTED]');

    console.error('API Generation Error:', safeErrorMessage);

    return res.status(500).json({
      success: false,
      error: safeErrorMessage
    });
  }
});

// Start the server
app.listen(PORT, () => {
  console.log(`Backend server is running on http://localhost:${PORT}`);
  console.log(`- Web UI: http://localhost:${PORT}`);
  console.log(`- Health Check: http://localhost:${PORT}/api/health`);
  console.log(`- Gemini Endpoint: POST http://localhost:${PORT}/api/generate`);
});
