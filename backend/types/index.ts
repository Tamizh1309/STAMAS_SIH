export type ClauseCategory = 'Technical' | 'Quality & Testing' | 'Statutory & ESG' | 'Commercial & Warranty';

export type ClauseStatus = 'COMPLIANT' | 'MINOR_DEVIATION' | 'MAJOR_DEVIATION' | 'MISSING_DOC';

export interface Clause {
  id: string;
  number: string;
  title: string;
  category: ClauseCategory;
  requiredSpec: string;
  offeredSpec: string;
  status: ClauseStatus;
  riskScore: number; // 1-10
  standardRef: string;
  auditorRemarks: string;
  clarificationRequired: boolean;
  clarificationDraft?: string;
  bidderOfferNotes?: string;
}

export type BidderCategory = 'L1 Bidder' | 'L2 Bidder' | 'L3 Bidder' | 'L4 Bidder' | 'L5 Bidder';
export type MIIClassification = 'Class-I Local (>=50%)' | 'Class-II Local (20-49%)' | 'Non-Local (<20%)';
export type MSECategory = 'Micro' | 'Small' | 'Medium' | 'SC/ST' | 'Women';
export type QualificationStatus = 'QUALIFIED' | 'CONDITIONALLY_QUALIFIED' | 'DISQUALIFIED';
export type CartelRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface Bidder {
  id: string;
  name: string;
  gstin: string;
  registeredCity: string;
  state: string;
  category: BidderCategory;
  quotedPrice: number;
  quotedPriceFormatted: string;
  localContentPercent: number;
  miiClassification: MIIClassification;
  isMSE: boolean;
  mseCategory?: MSECategory;
  udyamNumber?: string;
  turnoverLast3Yrs: string;
  netWorth: string;
  pqcExperienceMet: boolean;
  pastCPCLSupplyTrack: string;
  overallComplianceScore: number;
  qualificationStatus: QualificationStatus;
  disqualificationReason?: string;
  cartelRiskScore: CartelRiskLevel;
  cartelNotes?: string;
  submissionTimestamp: string;
  submissionIpRegion: string;
  pdfMetadataAuthor: string;
  evaluatedClauses: Clause[];
}

export type TenderStatus = 'TECH_EVAL_IN_PROGRESS' | 'EVALUATION_COMPLETED' | 'CLARIFICATION_PERIOD';

export interface TenderSummaryStats {
  totalBidders: number;
  qualifiedBidders: number;
  conditionalBidders: number;
  disqualifiedBidders: number;
  avgComplianceScore: number;
  totalClausesAudited: number;
  flaggedDeviations: number;
  cartelAnomalies: number;
}

export interface Tender {
  id: string;
  tenderNo: string;
  gemBidId: string;
  title: string;
  department: string;
  location: string;
  estimatedValue: number;
  estimatedValueFormatted: string;
  publishedDate: string;
  bidOpeningDate: string;
  techEvaluationDeadline: string;
  status: TenderStatus;
  minLocalContentRequired: number;
  emdAmountFormatted: string;
  pbgPercent: string;
  bidders: Bidder[];
  summaryStats: TenderSummaryStats;
}

export interface Deviation {
  clause: string;
  title: string;
  required: string;
  offered: string;
  remark: string;
}

export interface AnomalyAlert {
  type: 'COLLUSION_RISK' | 'TECH_SPEC_MISMATCH' | 'STATUTORY_GAP' | 'FINANCIAL_RISK';
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  description: string;
  remedy: string;
}

export interface EvaluatedClauseResult {
  clauseId: string;
  clauseTitle: string;
  requiredSpec: string;
  offeredSpec: string;
  complianceStatus: ClauseStatus;
  riskScore: number;
  auditorRemarks: string;
  clarificationQuestion?: string;
}

export interface MIIMSEAudit {
  miiCompliant: boolean;
  miiClass: string;
  mseExemptionGranted: boolean;
  remarks: string;
}

export interface ComplianceResult {
  fallback?: boolean;
  engine?: string;
  overallComplianceScore: number;
  qualificationStatus: QualificationStatus;
  executiveSummary: string;
  anomalyAlerts?: AnomalyAlert[];
  evaluatedClauses?: EvaluatedClauseResult[];
  miiMseAudit?: MIIMSEAudit;
}

export interface CartelAnomaly {
  biddersInvolved: string[];
  anomalyType: string;
  confidenceScore: number;
  finding: string;
  recommendedAction: string;
  safetyNote?: string;
}

export interface CartelDetectionResult {
  success: boolean;
  tenderNo: string;
  cartelRiskLevel: string;
  anomalies: CartelAnomaly[];
  safetyDisclaimer: string;
}

export interface SystemHealth {
  status: string;
  version: string;
  psId: string;
  authority: string;
  gemApiGateway: string;
  cvcAuditGuard: string;
  aiEngine: 'Gemini AI' | 'Local Rule Engine';
  database: {
    connected: boolean;
    dbType: string;
    recordCount: number;
    lastSync: string;
  };
  uptimeSeconds: number;
  timestamp: string;
}

export interface AnalyticsImpactMetric {
  metric: string;
  manualEvaluation: string;
  stamasAi: string;
  improvement: string;
  benchmarkSource: string;
}

export interface ProblemBrief {
  psId: string;
  title: string;
  org: string;
  theme: string;
  category: string;
  problemStatement: string;
  ourSolution: string;
  targetUsers: Array<{ role: string; need: string }>;
}

export interface SystemAnalytics {
  problemBrief: ProblemBrief;
  impactMetrics: AnalyticsImpactMetric[];
  refinerySavingsAnnual: string;
  averageScrutinyHours: string;
  disputeReductionRate: string;
}

export interface CopilotChatRequest {
  message: string;
  tenderContext?: {
    tenderNo?: string;
    title?: string;
    bidders?: Array<{
      name: string;
      status: string;
      score: number;
      price: string;
      localContent: string;
    }>;
  };
}

export interface CopilotChatResponse {
  success: boolean;
  reply: string;
  engine: 'Gemini AI' | 'Local Rule Engine';
}
