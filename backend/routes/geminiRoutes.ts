import { Router } from 'express';
import { geminiService } from '../services/geminiService.ts';
import { db } from '../db/dbConnector.ts';

export const geminiRouter = Router();

// Deep AI Clause Verification
geminiRouter.post('/verify-bid', async (req, res, next) => {
  try {
    const { tenderDetails, bidderDetails, clausesToVerify } = req.body;
    const result = await geminiService.verifyBidCompliance(tenderDetails, bidderDetails, clausesToVerify);
    return res.status(200).json({
      success: true,
      data: result,
      engine: result.engine || (result.fallback ? 'Local Rule Engine' : 'Gemini AI')
    });
  } catch (error) {
    return next(error);
  }
});

// Clarification Notice Generator
geminiRouter.post('/generate-notice', async (req, res, next) => {
  try {
    const { tenderNo, tenderTitle, bidderName, deviations, contactOfficer } = req.body;
    const notice = await geminiService.generateClarificationNotice(
      tenderNo,
      tenderTitle,
      bidderName,
      deviations,
      contactOfficer
    );
    return res.status(200).json({
      success: true,
      noticeText: notice
    });
  } catch (error) {
    return next(error);
  }
});

// Cartel & Collusion Anomaly Detection Radar
geminiRouter.post('/detect-cartel', async (req, res, next) => {
  try {
    const { tenderId } = req.body;
    const tender = await db.getTenderById(tenderId || 'tender-1');
    const result = geminiService.detectCartelAnomalies(
      tender?.tenderNo || 'CPCL/REF/2026/094',
      tender?.title
    );
    return res.status(200).json(result);
  } catch (error) {
    return next(error);
  }
});

// Procurement Copilot Chat
geminiRouter.post('/copilot-chat', async (req, res, next) => {
  try {
    const { message, tenderContext } = req.body;
    if (!message || typeof message !== 'string') {
      return res.status(400).json({
        success: false,
        message: 'Message query string is required.'
      });
    }
    const response = await geminiService.askCopilot(message, tenderContext);
    return res.status(200).json({
      success: true,
      reply: response.reply,
      engine: response.engine
    });
  } catch (error) {
    return next(error);
  }
});
