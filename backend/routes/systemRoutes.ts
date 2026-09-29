import { Router } from 'express';
import { db } from '../db/dbConnector.ts';
import { geminiService } from '../services/geminiService.ts';

export const systemRouter = Router();

// System health & telemetry
systemRouter.get('/health', async (req, res, next) => {
  try {
    const dbStatus = db.getConnectionStatus();
    const engineStatus = geminiService.getEngineStatus();

    return res.status(200).json({
      success: true,
      status: 'OPERATIONAL',
      version: 'STAMAS v3.8 Enterprise',
      psId: '26100',
      authority: 'Ministry of Petroleum & Natural Gas / CPCL',
      gemApiGateway: 'ACTIVE_SYNC (GeM 4.0)',
      cvcAuditGuard: 'ENFORCED',
      aiEngine: engineStatus.engine,
      model: engineStatus.model,
      isLiveAI: engineStatus.isLive,
      database: dbStatus,
      uptimeSeconds: Math.floor(process.uptime()),
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    return next(error);
  }
});

// Analytics & Impact Metrics
systemRouter.get('/analytics', async (req, res, next) => {
  try {
    const analytics = db.getImpactAnalytics();
    return res.status(200).json({
      success: true,
      data: analytics
    });
  } catch (error) {
    return next(error);
  }
});
