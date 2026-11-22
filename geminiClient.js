import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';

// Load environment variables from .env
dotenv.config();

const apiKey = process.env.GEMINI_API_KEY;

if (!apiKey) {
  throw new Error('CRITICAL: GEMINI_API_KEY is not set in your .env file.');
}

/**
 * Initialize Google GenAI SDK instance securely on the backend.
 * The apiKey is kept private on the server and never exposed to the client.
 */
export const ai = new GoogleGenAI({ apiKey });
