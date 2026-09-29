import { Router } from 'express';
import { db } from '../db/dbConnector.ts';

export const tenderRouter = Router();

// GET all tenders
tenderRouter.get('/', async (req, res, next) => {
  try {
    const tenders = await db.getAllTenders();
    return res.status(200).json({
      success: true,
      data: tenders,
      count: tenders.length
    });
  } catch (error) {
    return next(error);
  }
});

// GET single tender by ID
tenderRouter.get('/:id', async (req, res, next) => {
  try {
    const tender = await db.getTenderById(req.params.id);
    if (!tender) {
      return res.status(404).json({
        success: false,
        message: `Tender with ID "${req.params.id}" not found.`
      });
    }
    return res.status(200).json({
      success: true,
      data: tender
    });
  } catch (error) {
    return next(error);
  }
});

// POST register new tender
tenderRouter.post('/', async (req, res, next) => {
  try {
    const { title, tenderNo } = req.body;
    if (!title || !tenderNo) {
      return res.status(400).json({
        success: false,
        message: 'Tender title and tender number are mandatory parameters.'
      });
    }
    const newTender = await db.createTender(req.body);
    return res.status(201).json({
      success: true,
      data: newTender,
      message: `Tender "${newTender.tenderNo}" registered successfully in the system.`
    });
  } catch (error) {
    return next(error);
  }
});

// POST ingest new bidder into tender
tenderRouter.post('/:id/bids', async (req, res, next) => {
  try {
    const result = await db.addBidderToTender(req.params.id, req.body);
    if (!result) {
      return res.status(404).json({
        success: false,
        message: `Tender with ID "${req.params.id}" not found.`
      });
    }
    return res.status(201).json({
      success: true,
      data: result.bidder,
      tenderSummary: result.tender.summaryStats,
      message: `Bidder "${result.bidder.name}" audited and ingested into tender.`
    });
  } catch (error) {
    return next(error);
  }
});
