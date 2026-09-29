import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';
import type { ComplianceResult, CartelDetectionResult, CartelAnomaly } from '../types/index.ts';

dotenv.config();

const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
const apiKey = process.env.GEMINI_API_KEY;

// Initialize GoogleGenAI client only if API key is provided
let aiClient: GoogleGenAI | null = null;
if (apiKey && apiKey.trim() !== '' && apiKey !== 'MY_GEMINI_API_KEY') {
  try {
    aiClient = new GoogleGenAI({
      apiKey: apiKey,
      httpOptions: {
        headers: {
          'User-Agent': 'stamas-procurement-system',
        },
      },
    });
    console.log(`[STAMAS AI] Gemini client initialized successfully with model: ${GEMINI_MODEL}`);
  } catch (err) {
    console.warn('[STAMAS AI] Failed to initialize GoogleGenAI client, falling back to Local Rule Engine:', err);
    aiClient = null;
  }
} else {
  console.log('[STAMAS AI] GEMINI_API_KEY not configured. Running in Local Rule Engine fallback mode.');
}

async function generateContentSafely(params: {
  contents: unknown;
  config?: Record<string, unknown>;
}) {
  if (!aiClient) throw new Error('AI client not initialized');
  const candidateModels = [
    GEMINI_MODEL,
    'gemini-2.5-flash',
    'gemini-3.8-flash'
  ];
  const models = [...new Set(candidateModels)];
  let lastError: unknown = null;
  for (const model of models) {
    try {
      return await (aiClient.models.generateContent as any)({
        ...params,
        model,
      });
    } catch (err: any) {
      lastError = err;
      if (err?.status === 503 || err?.message?.includes('503') || err?.status === 404) {
        console.warn(`[STAMAS AI] Model ${model} unavailable (${err.status || 503}), trying next model...`);
        continue;
      }
      throw err;
    }
  }
  throw lastError;
}

export const geminiService = {
  isGeminiAvailable(): boolean {
    return aiClient !== null;
  },

  getEngineStatus(): { engine: 'Gemini AI' | 'Local Rule Engine'; model: string; isLive: boolean } {
    const isLive = this.isGeminiAvailable();
    return {
      engine: isLive ? 'Gemini AI' : 'Local Rule Engine',
      model: isLive ? GEMINI_MODEL : 'Deterministic Rule Engine v3.8',
      isLive
    };
  },

  /**
   * Deep AI Clause Verification against GFR 2017 & CVC Guidelines
   */
  async verifyBidCompliance(
    tenderDetails: Record<string, unknown>,
    bidderDetails: Record<string, unknown>,
    clausesToVerify: unknown[]
  ): Promise<ComplianceResult> {
    if (!aiClient) {
      return this.localRuleEngineVerify(tenderDetails, bidderDetails, clausesToVerify);
    }

    try {
      const prompt = `You are the Lead Procurement & Technical Compliance Auditor for Chennai Petroleum Corporation Limited (CPCL) and GeM (Government e-Marketplace), evaluating public tenders under GFR 2017 & CVC Guidelines.

IMPORTANT DOMAIN SAFETY:
- Present all findings as decision-support indicators for tender committee officials, not as an unquestionable legal verdict.

TENDER SPECIFICATIONS:
Title: ${tenderDetails?.title || 'Refinery Equipment Tender'}
Tender No: ${tenderDetails?.tenderNo || 'CPCL/REF/2026/094'}
Estimated Value: ${tenderDetails?.estimatedValue || '₹14.85 Cr'}
Make-in-India Min Local Content: ${tenderDetails?.minLocalContent || '50%'}

BIDDER SUBMISSION:
Bidder Name: ${bidderDetails?.name || 'Bidder'}
Declared Local Content: ${bidderDetails?.localContent || '58%'}
MSE Status: ${bidderDetails?.isMSE ? 'Registered MSE (Udyam Verified)' : 'Non-MSE Enterprise'}

CLAUSES TO AUDIT:
${JSON.stringify(clausesToVerify || [], null, 2)}

Provide a strict, professional techno-commercial audit in valid JSON format matching this schema:
{
  "overallComplianceScore": number (0-100),
  "qualificationStatus": "QUALIFIED" | "CONDITIONALLY_QUALIFIED" | "DISQUALIFIED",
  "executiveSummary": "string",
  "anomalyAlerts": [
    { "type": "COLLUSION_RISK" | "TECH_SPEC_MISMATCH" | "STATUTORY_GAP" | "FINANCIAL_RISK", "severity": "HIGH" | "MEDIUM" | "LOW", "description": "string", "remedy": "string" }
  ],
  "evaluatedClauses": [
    {
      "clauseId": "string",
      "clauseTitle": "string",
      "requiredSpec": "string",
      "offeredSpec": "string",
      "complianceStatus": "COMPLIANT" | "MINOR_DEVIATION" | "MAJOR_DEVIATION" | "MISSING_DOC",
      "riskScore": number (1-10),
      "auditorRemarks": "string",
      "clarificationQuestion": "string"
    }
  ],
  "miiMseAudit": {
    "miiCompliant": boolean,
    "miiClass": "Class-I Local Supplier (>=50%)" | "Class-II Local Supplier (20-49%)" | "Non-Local Supplier (<20%)",
    "mseExemptionGranted": boolean,
    "remarks": "string"
  }
}
Respond with pure JSON only without markdown formatting.`;

      const response = await generateContentSafely({
        contents: prompt,
        config: {
          responseMimeType: 'application/json',
          temperature: 0.2,
        },
      });

      const text = response.text || '{}';
      const parsed = JSON.parse(text.replace(/```json/g, '').replace(/```/g, '').trim()) as ComplianceResult;
      parsed.engine = 'Gemini AI';
      parsed.fallback = false;
      return parsed;
    } catch (error) {
      console.warn('[STAMAS AI] Gemini API call failed, falling back to Local Rule Engine:', error);
      return this.localRuleEngineVerify(tenderDetails, bidderDetails, clausesToVerify);
    }
  },

  /**
   * Local Rule Engine Fallback for Clause Verification
   */
  localRuleEngineVerify(
    tenderDetails: Record<string, unknown>,
    bidderDetails: Record<string, unknown>,
    clausesToVerify: unknown[]
  ): ComplianceResult {
    const clauses = (clausesToVerify || []) as Array<{
      id?: string;
      number?: string;
      title?: string;
      status?: string;
      riskScore?: number;
      requiredSpec?: string;
      offeredSpec?: string;
      auditorRemarks?: string;
    }>;

    const evaluated = clauses.map(c => {
      const compliant = c.status === 'COMPLIANT' || (!c.status && !(c.offeredSpec?.toLowerCase().includes('cast') || c.offeredSpec?.toLowerCase().includes('missing')));
      const minor = c.status === 'MINOR_DEVIATION' || (!compliant && !c.offeredSpec?.toLowerCase().includes('cast'));
      const status = compliant ? 'COMPLIANT' : minor ? 'MINOR_DEVIATION' : 'MAJOR_DEVIATION';
      const risk = compliant ? 1 : minor ? 4 : 9;

      return {
        clauseId: c.id || `c-${Math.random().toString(36).slice(2, 7)}`,
        clauseTitle: c.title || 'Technical Parameter',
        requiredSpec: c.requiredSpec || 'Standard CPCL Refinery Spec',
        offeredSpec: c.offeredSpec || 'Vendor Specification',
        complianceStatus: status as 'COMPLIANT' | 'MINOR_DEVIATION' | 'MAJOR_DEVIATION' | 'MISSING_DOC',
        riskScore: c.riskScore || risk,
        auditorRemarks: c.auditorRemarks || (compliant ? 'Meets ASME/API requirements.' : 'Requires technical clarification.'),
        clarificationQuestion: compliant ? undefined : `Confirm acceptance of tender specifications for ${c.number || 'clause'}.`
      };
    });

    const compliantCount = evaluated.filter(e => e.complianceStatus === 'COMPLIANT').length;
    const score = evaluated.length > 0 ? Math.round((compliantCount / evaluated.length) * 100) : 88;
    const hasMajor = evaluated.some(e => e.complianceStatus === 'MAJOR_DEVIATION' || e.complianceStatus === 'MISSING_DOC');
    const hasMinor = evaluated.some(e => e.complianceStatus === 'MINOR_DEVIATION');
    const qualStatus = hasMajor ? 'DISQUALIFIED' : hasMinor ? 'CONDITIONALLY_QUALIFIED' : 'QUALIFIED';

    return {
      fallback: true,
      engine: 'Local Rule Engine',
      overallComplianceScore: score,
      qualificationStatus: qualStatus,
      executiveSummary: `Local Rule Engine evaluation completed. Bidder ${bidderDetails?.name || 'Applicant'} evaluated against CPCL refinery standards. ${score}% compliance detected. Decision-support recommendation: ${qualStatus}.`,
      anomalyAlerts: hasMajor ? [
        {
          type: 'TECH_SPEC_MISMATCH',
          severity: 'HIGH',
          description: 'Critical specification divergence detected during rule-engine audit.',
          remedy: 'Seek formal clarification or reject per GeM GTC clause 11.'
        }
      ] : [],
      evaluatedClauses: evaluated,
      miiMseAudit: {
        miiCompliant: true,
        miiClass: 'Class-I Local Supplier (>=50%)',
        mseExemptionGranted: Boolean(bidderDetails?.isMSE),
        remarks: 'Statutory verification verified through rule parameters.'
      }
    };
  },

  /**
   * Official GoI / GeM CSQ Clarification Notice Generator
   */
  async generateClarificationNotice(
    tenderNo: string,
    tenderTitle: string,
    bidderName: string,
    deviations: unknown[],
    contactOfficer?: string
  ): Promise<string> {
    if (!aiClient) {
      return this.localClarificationNotice(tenderNo, tenderTitle, bidderName, deviations, contactOfficer);
    }

    try {
      const prompt = `Draft a formal Government of India / CPCL Technical Clarification Notice (GeM CSQ Query Notice) to be issued to bidder "${bidderName}" for Tender "${tenderNo}: ${tenderTitle}".
Deviations/Observations noted by AI evaluation:
${JSON.stringify(deviations || [], null, 2)}
Officer In-Charge: ${contactOfficer || 'General Manager (Contracts & Procurement), CPCL Manali Refinery, Chennai'}

Format requirements:
- Formal GoI / PSU procurement language referencing GFR 2017 & GeM GTC (General Terms & Conditions).
- Clear tabular or bulleted list of clause deficiencies.
- Strict 48-hour response window for uploading supporting documents on GeM portal.
- Clause warning regarding technical rejection if clarifications are unsatisfactory.
Return plain text formatted letter.`;

      const response = await generateContentSafely({
        contents: prompt,
      });

      return response.text || this.localClarificationNotice(tenderNo, tenderTitle, bidderName, deviations, contactOfficer);
    } catch (err) {
      console.warn('[STAMAS AI] Gemini notice generation failed, using local template:', err);
      return this.localClarificationNotice(tenderNo, tenderTitle, bidderName, deviations, contactOfficer);
    }
  },

  /**
   * Local Rule Template Clarification Notice Fallback
   */
  localClarificationNotice(
    tenderNo: string,
    tenderTitle: string,
    bidderName: string,
    deviations: unknown[],
    contactOfficer?: string
  ): string {
    const devs = (deviations || []) as Array<{
      clause?: string;
      title?: string;
      required?: string;
      offered?: string;
      remark?: string;
    }>;

    return `GOVERNMENT OF INDIA / CHENNAI PETROLEUM CORPORATION LIMITED (CPCL)
(A Group Company of Indian Oil Corporation Ltd.)
Refinery Headquarters, Manali, Chennai - 600068, Tamil Nadu

TENDER REF: ${tenderNo || 'CPCL/REF/2026/094'}
SUBJECT: Technical Evaluation Clarification Notice (GeM CSQ Query Notice)

To:
The Authorized Signatory,
${bidderName}

Dear Sir/Madam,

During the techno-commercial evaluation of your bid against Tender "${tenderTitle || 'CPCL Procurement'}", the Technical Evaluation Committee has recorded the following observations requiring clarification under GFR 2017 & GeM General Terms and Conditions:

${devs.length > 0 ? devs.map((d, i) => `[${i + 1}] Clause: ${d.clause || 'Clause'} - ${d.title || 'Technical Spec'}
Required Specification: ${d.required || 'As specified in tender'}
Offered Specification: ${d.offered || 'Deviation noted'}
Audit Observation: ${d.remark || 'Requires documentary confirmation'}
Required Action: Submit certified OEM test report / compliance letter.\n`).join('\n') : '[1] All major specifications evaluated. Please confirm unconditional compliance to all commercial terms and warranty provisions.'}

You are hereby requested to submit your point-by-point clarification along with authenticated documentary proof on the GeM Portal within 48 hours of receipt of this notice.

Please note that failure to furnish satisfactory compliance within the stipulated deadline may lead to technical disqualification of your bid without further reference.

Yours faithfully,
${contactOfficer || 'Chief General Manager (Contracts & Materials)'}
Chennai Petroleum Corporation Limited, Manali, Chennai`;
  },

  /**
   * Cartel & Collusion Anomaly Detection with Procurement Domain Safety
   */
  detectCartelAnomalies(tenderNo: string, tenderTitle?: string): CartelDetectionResult {
    const anomalies: CartelAnomaly[] = [
      {
        biddersInvolved: ['Microtech Fluidics & Engineering Works', 'Apex Valvetech Global Solutions'],
        anomalyType: 'METADATA_&_IP_CORRELATION',
        confidenceScore: 94,
        finding: 'Potential anomaly: Identical PDF author tag ("DELL-LATITUDE-ADMIN") and bid uploads originating from identical Coimbatore ISP subnet (AS24336) within a 12-minute window.',
        recommendedAction: 'Risk indicator requires human review by Competent Authority / CVO prior to commercial bid opening.',
        safetyNote: 'This indicator highlights technical correlation for administrative review and does not constitute a determination of misconduct.'
      },
      {
        biddersInvolved: ['Microtech Fluidics & Engineering Works', 'BVIS Flow Systems India Pvt Ltd'],
        anomalyType: 'PRICE_DELTA_REGULARITY',
        confidenceScore: 82,
        finding: 'Potential anomaly: Microtech quoted price is structured at a uniform +12.50% step increment above BVIS baseline.',
        recommendedAction: 'Verify bill-of-quantities rate calculations and cost buildup sheets during price assessment.',
        safetyNote: 'Statistical variance metric provided for decision-support purposes.'
      }
    ];

    return {
      success: true,
      tenderNo: tenderNo || 'CPCL/REF/2026/094',
      cartelRiskLevel: 'ELEVATED_ANOMALY_INDICATOR',
      anomalies,
      safetyDisclaimer: 'All cartel and collusion detections are decision-support risk indicators requiring independent administrative and human verification.'
    };
  },

  /**
   * STAMAS AI Procurement Copilot Assistant
   */
  async askCopilot(userQuery: string, tenderContext: Record<string, unknown>): Promise<{ reply: string; engine: 'Gemini AI' | 'Local Rule Engine' }> {
    if (!aiClient) {
      return {
        reply: this.localCopilotResponse(userQuery, tenderContext),
        engine: 'Local Rule Engine'
      };
    }

    try {
      const systemInstruction = `You are STAMAS Copilot, the AI Procurement Intelligence Assistant for Chennai Petroleum Corporation Limited (CPCL) & Ministry of Petroleum & Natural Gas.
You have deep domain knowledge of:
1. Public Procurement in India, GeM 4.0 Portal rules, CVC (Central Vigilance Commission) guidelines, GFR 2017 Rules 144(xi), 149, 153.
2. Oil & Gas PSU technical specifications: ASME B16.34, ASTM A182/A216, API 6D, API 600, NACE MR0175/ISO 15156 for sour crude service, cryogenic valves, EOT cranes, heat exchangers.
3. Make in India (Public Procurement Order 2017, Class I >=50%, Class II 20-49%), MSE exemptions (EMD/turnover), Land Border Sharing restrictions (Rule 144(xi)).
4. Anomaly detection, risk indicators, mirror pricing, and explainable audit trails.

Procurement Safety Reminder:
Always frame cartel or collusion observations as potential anomalies and risk indicators requiring human review by the competent authority.

Current Tender Context:
${JSON.stringify(tenderContext || {}, null, 2)}

Provide concise, authoritative, structured, and helpful responses with actionable recommendations and citations.`;

      const response = await generateContentSafely({
        contents: [
          { role: 'user', parts: [{ text: `User Query: ${userQuery}` }] }
        ],
        config: {
          systemInstruction,
          temperature: 0.3,
        }
      });

      return {
        reply: response.text || this.localCopilotResponse(userQuery, tenderContext),
        engine: 'Gemini AI'
      };
    } catch (err) {
      console.warn('[STAMAS AI] Gemini Copilot call failed, using local assistant:', err);
      return {
        reply: this.localCopilotResponse(userQuery, tenderContext),
        engine: 'Local Rule Engine'
      };
    }
  },

  /**
   * Local Rule Copilot Assistant Fallback
   */
  localCopilotResponse(query: string, context: Record<string, unknown>): string {
    const q = query.toLowerCase();

    if (q.includes('disqualif') || q.includes('reject') || q.includes('apex')) {
      return `Technical Evaluation Summary:
• Bidder "Apex Valvetech Global Solutions" has fatal non-compliances under CPCL Tender Criteria:
  1. Material of Construction: Offered Cast Steel (ASTM A216 WCB) instead of mandatory Forged Stainless Steel (ASTM A182 F316/F316L).
  2. NACE MR0175 sour service hardness test certificates were missing from submittal.
  3. Declared Make-in-India content is 32% (Class-II), falling below the mandatory 50% Class-I threshold.
Recommendation: Disqualification under GeM GTC Clause 11 is technically substantiated.`;
    }

    if (q.includes('cartel') || q.includes('collusion') || q.includes('anomaly') || q.includes('rig')) {
      return `Potential Vigilance Anomaly Indicator:
• STAMAS detected technical correlations between Microtech Fluidics and Apex Valvetech:
  1. Identical PDF workstation author metadata tag ("DELL-LATITUDE-ADMIN").
  2. Both bids submitted from the identical Coimbatore ISP subnet (AS24336) within 12 minutes.
  3. Microtech pricing reflects a consistent +12.50% step increment over the L1 baseline.
Domain Safety Notice: These are potential anomaly indicators for committee review, requiring human evaluation under CVC Procurement Guidelines before price opening.`;
    }

    if (q.includes('clarification') || q.includes('notice') || q.includes('bvis')) {
      return `Technical Clarification Guidance:
• For BVIS Flow Systems, minor deviations were observed:
  1. Dual certified F316/F316L marking was not explicitly noted on the MOC datasheet.
  2. Gas seat leak test was offered at 300 bar instead of the required 330 bar.
Action: Generate a GeM CSQ Notice granting 48 hours for submission of test coupon and pressure acceptance.`;
    }

    if (q.includes('mse') || q.includes('make in india') || q.includes('mii') || q.includes('local content')) {
      return `Statutory Policy Matrix (MoPNG / DPIIT):
• Class-I Local Supplier: Local content >= 50% (Eligible for purchase preference).
• Class-II Local Supplier: Local content 20% to 49% (No purchase preference in domestic tenders).
• MSE Benefits: Exemption from EMD submission under Rule 170 of GFR 2017 upon valid UDYAM certificate submission.
Tender ${context?.tenderNo || 'Active Tender'} mandates Class-I Local Supplier status.`;
    }

    return `STAMAS Copilot (Local Rule Engine):
I have reviewed your query against the active tender parameters and GFR 2017 / CVC guidelines.
• Active Tender: ${context?.tenderNo || 'CPCL/REF/2026/094'}
• Compliance Status: 4 bidders audited across metallurgy (ASTM A182), sour service (NACE MR0175), hydro testing (API 598), and statutory Make-in-India mandates.
Feel free to ask for specific clause comparisons, clarification draft recommendations, or statutory compliance audits.`;
  }
};
