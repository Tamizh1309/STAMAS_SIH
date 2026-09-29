import dotenv from 'dotenv';
import { createApp } from './app.ts';
import { geminiService } from './services/geminiService.ts';

dotenv.config();

const port = Number(process.env.PORT) || 3000;
const app = createApp();

const server = app.listen(port, '0.0.0.0', () => {
  const engineStatus = geminiService.getEngineStatus();
  console.log('====================================================');
  console.log(`[STAMAS Backend] Server listening on http://0.0.0.0:${port}`);
  console.log(`[STAMAS Backend] Local URL: http://localhost:${port}`);
  console.log(`[STAMAS AI Engine] Active Mode: ${engineStatus.engine} (${engineStatus.model})`);
  console.log(`[STAMAS AI Engine] Live Key Available: ${engineStatus.isLive ? 'YES' : 'NO (Rule Engine Active)'}`);
  console.log('====================================================');
});

process.on('SIGTERM', () => {
  console.log('[STAMAS Backend] SIGTERM received, closing server gracefully.');
  server.close(() => {
    process.exit(0);
  });
});
