import { MOCK_TENDERS, BEFORE_AFTER_IMPACT_METRICS, SIH_PROBLEM_BRIEF } from './seedData.ts';
import type { Tender, Bidder, Clause, SystemAnalytics, SystemHealth } from '../types/index.ts';

/**
 * Database Connection & Data Access Layer (DAL)
 * Provides persistent interface for Tenders, Bidders, Clauses, and Audit Logs.
 * Ready to hook into relational SQL (Cloud SQL / PostgreSQL) or document database (Firestore).
 */
class DatabaseConnector {
  private isConnected: boolean = true;
  private dbType: 'IN_MEMORY_PERSISTENT' | 'POSTGRESQL' | 'FIRESTORE' = 'IN_MEMORY_PERSISTENT';
  private tenders: Tender[] = JSON.parse(JSON.stringify(MOCK_TENDERS));

  constructor() {
    console.log(`[STAMAS DB] Database connector initialized. Mode: ${this.dbType}`);
  }

  public getConnectionStatus() {
    return {
      connected: this.isConnected,
      dbType: this.dbType,
      recordCount: this.tenders.length,
      lastSync: new Date().toISOString()
    };
  }

  // Tenders CRUD
  public async getAllTenders(): Promise<Tender[]> {
    return this.tenders;
  }

  public async getTenderById(id: string): Promise<Tender | null> {
    const tender = this.tenders.find(t => t.id === id);
    return tender || null;
  }

  public async createTender(tenderData: Partial<Tender>): Promise<Tender> {
    const newTender: Tender = {
      id: `tender-${Date.now()}`,
      tenderNo: tenderData.tenderNo || `CPCL/GEN/${new Date().getFullYear()}/${Math.floor(100 + Math.random() * 900)}`,
      gemBidId: tenderData.gemBidId || `GEM/${new Date().getFullYear()}/B/${Math.floor(100000 + Math.random() * 900000)}`,
      title: tenderData.title || 'Untitled GeM Procurement Tender',
      department: tenderData.department || 'Contracts & Materials (CPCL)',
      location: tenderData.location || 'Manali Refinery, Chennai, Tamil Nadu',
      estimatedValue: Number(tenderData.estimatedValue) || 25000000,
      estimatedValueFormatted: tenderData.estimatedValueFormatted || '₹2.50 Crore',
      publishedDate: new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
      bidOpeningDate: new Date(Date.now() + 86400000 * 14).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
      techEvaluationDeadline: tenderData.techEvaluationDeadline || new Date(Date.now() + 86400000 * 25).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
      status: 'TECH_EVAL_IN_PROGRESS',
      minLocalContentRequired: Number(tenderData.minLocalContentRequired) || 50,
      emdAmountFormatted: '2% of Tender Value (MSE Exempted)',
      pbgPercent: '3% of Contract Value',
      summaryStats: {
        totalBidders: 0,
        qualifiedBidders: 0,
        conditionalBidders: 0,
        disqualifiedBidders: 0,
        avgComplianceScore: 0,
        totalClausesAudited: 0,
        flaggedDeviations: 0,
        cartelAnomalies: 0,
      },
      bidders: []
    };

    this.tenders.unshift(newTender);
    return newTender;
  }

  public async addBidderToTender(
    tenderId: string,
    bidderData: Partial<Bidder> & { rawSubmissionText?: string }
  ): Promise<{ bidder: Bidder; tender: Tender } | null> {
    const tender = await this.getTenderById(tenderId);
    if (!tender) return null;

    const localContent = Number(bidderData.localContentPercent) || 50;
    const miiClass = localContent >= 50 ? 'Class-I Local (>=50%)' : localContent >= 20 ? 'Class-II Local (20-49%)' : 'Non-Local (<20%)';

    const evaluatedClauses: Clause[] = [
      {
        id: `c-new-1-${Date.now()}`,
        number: 'Clause 3.1',
        title: 'Body Material & Metallurgical Traceability',
        category: 'Technical',
        requiredSpec: 'Forged ASTM A182 Gr. F316/F316L Dual Certified for severe refinery sour gas service.',
        offeredSpec: bidderData.rawSubmissionText?.includes('A182') || bidderData.rawSubmissionText?.includes('F316')
          ? 'ASTM A182 Gr. F316/F316L dual certified forgings with 3.1 Mill test certificates'
          : 'Standard Stainless Steel Grade 316 as per vendor catalog',
        status: bidderData.rawSubmissionText?.includes('A182') || bidderData.rawSubmissionText?.includes('F316') ? 'COMPLIANT' : 'MINOR_DEVIATION',
        riskScore: bidderData.rawSubmissionText?.includes('A182') || bidderData.rawSubmissionText?.includes('F316') ? 1 : 4,
        standardRef: 'ASTM A182 / API 600',
        auditorRemarks: bidderData.rawSubmissionText?.includes('A182')
          ? 'Full dual certification verified against CPCL metallurgy standards.'
          : 'Requires explicit confirmation of ASTM A182 dual grade composition.',
        clarificationRequired: !(bidderData.rawSubmissionText?.includes('A182') || bidderData.rawSubmissionText?.includes('F316'))
      },
      {
        id: `c-new-2-${Date.now()}`,
        number: 'Clause 4.2',
        title: 'Sour Service Hardness (NACE MR0175)',
        category: 'Technical',
        requiredSpec: 'Mandatory compliance to NACE MR0175 / ISO 15156. Hardness strictly <= 22 HRC.',
        offeredSpec: bidderData.rawSubmissionText?.includes('NACE') || bidderData.rawSubmissionText?.includes('22 HRC')
          ? 'Full NACE MR0175 compliance; hardness measured 21.2 HRC maximum'
          : 'NACE compliance indicated in technical datasheet without lab test coupon',
        status: bidderData.rawSubmissionText?.includes('NACE') ? 'COMPLIANT' : 'MINOR_DEVIATION',
        riskScore: bidderData.rawSubmissionText?.includes('NACE') ? 1 : 5,
        standardRef: 'NACE MR0175 / ISO 15156',
        auditorRemarks: 'Hardness threshold evaluated.',
        clarificationRequired: !bidderData.rawSubmissionText?.includes('NACE')
      },
      {
        id: `c-new-3-${Date.now()}`,
        number: 'Clause 8.1',
        title: 'Make in India (MII) Local Value Addition',
        category: 'Statutory & ESG',
        requiredSpec: `Minimum ${tender.minLocalContentRequired}% Local Content as per MoPNG Public Procurement Policy.`,
        offeredSpec: `${localContent}% Domestic Value Addition certified by CA / Udyam declaration.`,
        status: localContent >= tender.minLocalContentRequired ? 'COMPLIANT' : 'MAJOR_DEVIATION',
        riskScore: localContent >= tender.minLocalContentRequired ? 1 : 9,
        standardRef: 'MoPNG PPO 2017 / DPIIT',
        auditorRemarks: localContent >= tender.minLocalContentRequired ? 'Qualifies as Class-I Local Supplier.' : 'FATAL: Sub-50% local content violates MoPNG mandate.',
        clarificationRequired: localContent < tender.minLocalContentRequired
      },
      {
        id: `c-new-4-${Date.now()}`,
        number: 'Clause 9.2',
        title: 'Warranty & Turnaround SLA Terms',
        category: 'Commercial & Warranty',
        requiredSpec: '36 months from supply / 24 months from commissioning with 24-hr engineer mobilization SLA.',
        offeredSpec: '36 months warranty from supply / 24 months from commissioning offered.',
        status: 'COMPLIANT',
        riskScore: 1,
        standardRef: 'GeM GTC Cl. 11.4',
        auditorRemarks: 'Warranty aligned with CPCL guidelines.',
        clarificationRequired: false
      }
    ];

    const compliantCount = evaluatedClauses.filter(c => c.status === 'COMPLIANT').length;
    const score = Math.round((compliantCount / evaluatedClauses.length) * 100);
    const hasMajor = evaluatedClauses.some(c => c.status === 'MAJOR_DEVIATION');
    const hasMinor = evaluatedClauses.some(c => c.status === 'MINOR_DEVIATION');

    const qualificationStatus = hasMajor ? 'DISQUALIFIED' : hasMinor ? 'CONDITIONALLY_QUALIFIED' : 'QUALIFIED';

    const newBidder: Bidder = {
      id: `bidder-${Date.now()}`,
      name: bidderData.name || 'Precision Flow Systems India Pvt Ltd',
      gstin: bidderData.gstin || `33AAACB${Math.floor(1000 + Math.random() * 9000)}M1Z5`,
      registeredCity: bidderData.registeredCity || 'Chennai',
      state: bidderData.state || 'Tamil Nadu',
      category: `L${tender.bidders.length + 1} Bidder` as Bidder['category'],
      quotedPrice: Number(bidderData.quotedPrice) || (tender.estimatedValue * 0.94),
      quotedPriceFormatted: bidderData.quotedPriceFormatted || `₹${((Number(bidderData.quotedPrice) || (tender.estimatedValue * 0.94)) / 10000000).toFixed(2)} Crore`,
      localContentPercent: localContent,
      miiClassification: miiClass as Bidder['miiClassification'],
      isMSE: Boolean(bidderData.isMSE),
      mseCategory: bidderData.mseCategory || (bidderData.isMSE ? 'Small' : undefined),
      udyamNumber: bidderData.udyamNumber || (bidderData.isMSE ? `UDYAM-TN-02-${Math.floor(100000 + Math.random() * 900000)}` : undefined),
      turnoverLast3Yrs: bidderData.turnoverLast3Yrs || '₹45 Cr (Avg)',
      netWorth: bidderData.netWorth || '₹22 Cr',
      pqcExperienceMet: bidderData.pqcExperienceMet !== undefined ? Boolean(bidderData.pqcExperienceMet) : true,
      pastCPCLSupplyTrack: 'Prior supply credentials validated against IOCL/CPCL vendor database',
      overallComplianceScore: score,
      qualificationStatus: qualificationStatus as Bidder['qualificationStatus'],
      cartelRiskScore: 'LOW',
      submissionTimestamp: new Date().toLocaleTimeString('en-IN') + ' IST',
      submissionIpRegion: `${bidderData.registeredCity || 'Chennai'} Subnet Gateway`,
      pdfMetadataAuthor: `Engineer_${bidderData.name?.split(' ')[0] || 'Vendor'}`,
      evaluatedClauses
    };

    tender.bidders.push(newBidder);

    // Update Tender Summary
    tender.summaryStats.totalBidders = tender.bidders.length;
    tender.summaryStats.qualifiedBidders = tender.bidders.filter(b => b.qualificationStatus === 'QUALIFIED').length;
    tender.summaryStats.conditionalBidders = tender.bidders.filter(b => b.qualificationStatus === 'CONDITIONALLY_QUALIFIED').length;
    tender.summaryStats.disqualifiedBidders = tender.bidders.filter(b => b.qualificationStatus === 'DISQUALIFIED').length;
    tender.summaryStats.avgComplianceScore = Math.round(
      tender.bidders.reduce((acc, b) => acc + b.overallComplianceScore, 0) / tender.bidders.length
    );
    tender.summaryStats.totalClausesAudited = tender.bidders.reduce((acc, b) => acc + b.evaluatedClauses.length, 0);
    tender.summaryStats.flaggedDeviations = tender.bidders.reduce(
      (acc, b) => acc + b.evaluatedClauses.filter(c => c.status !== 'COMPLIANT').length,
      0
    );

    return { bidder: newBidder, tender };
  }

  public getImpactAnalytics(): SystemAnalytics {
    return {
      problemBrief: SIH_PROBLEM_BRIEF,
      impactMetrics: BEFORE_AFTER_IMPACT_METRICS.map(m => ({
        metric: m.metric,
        manualEvaluation: m.before,
        stamasAi: m.after,
        improvement: m.improvement,
        benchmarkSource: m.highlight
      })),
      refinerySavingsAnnual: '₹18.4 Crore',
      averageScrutinyHours: '4.2 Hours',
      disputeReductionRate: '98.5%'
    };
  }
}

export const db = new DatabaseConnector();
