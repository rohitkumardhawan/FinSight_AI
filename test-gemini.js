import { ai } from './geminiClient.js';

async function testGemini() {
  console.log('====================================================');
  console.log('Step 1: Checking environment configuration...');
  console.log('====================================================');
  if (!process.env.GEMINI_API_KEY) {
    console.error('❌ Error: GEMINI_API_KEY is not defined in your .env file.');
    process.exit(1);
  }
  console.log('✔ .env file loaded successfully (API key is present).');

  console.log('\n====================================================');
  console.log('Step 2: Testing live connection to Google Gemini API...');
  console.log('====================================================');
  
  // Model prioritization: gemini-3.5-flash-lite gives fast, reliable responses
  const modelsToTry = ['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-3.8-flash'];
  let success = false;

  for (const model of modelsToTry) {
    try {
      console.log(`Connecting using model: "${model}"...`);
      const response = await ai.models.generateContent({
        model: model,
        contents: 'Respond with exactly: "Gemini connection is working properly!"',
      });

      console.log('\n----------------------------------------------------');
      console.log('🎉 SUCCESS: Gemini API connection verified!');
      console.log('----------------------------------------------------');
      console.log(`Model connected: ${model}`);
      console.log(`Gemini response: ${response.text.trim()}`);
      console.log('----------------------------------------------------');
      console.log('Backend is fully configured and ready for requests.');
      success = true;
      break;
    } catch (err) {
      const is503 = (err.message || '').includes('503') || err.status === 503;
      if (is503) {
        console.warn(`⚠ Model "${model}" is temporarily busy on Google's servers. Trying next model...`);
        continue;
      }
      
      // Sanitize errors so API key is never exposed
      const sanitized = (err.message || err.toString()).replace(/([a-zA-Z0-9_\-\.]{30,})/g, '[REDACTED]');
      console.error(`❌ Connection error on ${model}:`, sanitized);
      break;
    }
  }

  if (!success) {
    console.error('\n❌ Could not connect to Gemini API.');
    process.exit(1);
  }
}

testGemini();
