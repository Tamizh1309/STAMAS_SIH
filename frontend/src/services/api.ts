import type {
  Tender,
  Bidder,
  Clause,
  ComplianceResult,
  CartelDetectionResult,
  SystemHealth,
  SystemAnalytics,
  CopilotChatResponse,
  BackendDocument,
  ExtractedTenderClause,
  ClauseVerification,
  OpportunityAnalysisRecord
} from '../types/index.ts';

// Base API URL from environment variable, fallback to '' (for Vite proxy or same-origin)
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {})
    }
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.message || errorBody?.error || `HTTP ${response.status}: ${response.statusText}`;
    throw new Error(msg);
  }

  return response.json() as Promise<T>;
}

/**
 * Multipart POST helper. Never sets Content-Type manually —
 * the browser generates the boundary.
 */
async function fetchForm<T>(endpoint: string, form: FormData, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const response = await fetch(url, { ...options, method: 'POST', body: form });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.message || errorBody?.error || `HTTP ${response.status}: ${response.statusText}`;
    throw new Error(msg);
  }

  return response.json() as Promise<T>;
}

export const api = {
  /**
   * Fetch all tenders
   */
  async getTenders(): Promise<Tender[]> {
    try {
      const res = await fetchJson<{ success: boolean; data: Tender[]; count: number }>('/api/tenders');
      return res?.data || [];
    } catch (err) {
      console.warn('[STAMAS API] getTenders failed, falling back to cached state:', err);
      return [];
    }
  },

  /**
   * Fetch single tender by ID
   */
  async getTender(id: string): Promise<Tender | null> {
    try {
      const res = await fetchJson<{ success: boolean; data: Tender }>(`/api/tenders/${id}`);
      return res?.data || null;
    } catch (err) {
      console.warn(`[STAMAS API] getTender(${id}) failed:`, err);
      return null;
    }
  },

  /**
   * Create a new tender
   */
  async createTender(tenderData: Partial<Tender>): Promise<Tender | null> {
    try {
      const res = await fetchJson<{ success: boolean; data: Tender; message: string }>('/api/tenders', {
        method: 'POST',
        body: JSON.stringify(tenderData)
      });
      return res?.data || null;
    } catch (err) {
      console.error('[STAMAS API] createTender failed:', err);
      throw err;
    }
  },

  /**
   * Ingest a new bidder into an existing tender
   */
  async ingestBid(
    tenderId: string,
    bidderData: Partial<Bidder> & { rawSubmissionText?: string }
  ): Promise<{ bidder: Bidder; message?: string } | null> {
    try {
      const res = await fetchJson<{ success: boolean; data: Bidder; message: string }>(
        `/api/tenders/${tenderId}/bids`,
        {
          method: 'POST',
          body: JSON.stringify(bidderData)
        }
      );
      return { bidder: res.data, message: res.message };
    } catch (err) {
      console.error('[STAMAS API] ingestBid failed:', err);
      throw err;
    }
  },

  /**
   * Deep AI Clause Verification
   */
  async verifyBid(data: {
    tenderDetails: Record<string, unknown>;
    bidderDetails: Record<string, unknown>;
    clausesToVerify: Clause[];
  }): Promise<{ data: ComplianceResult; engine?: string }> {
    try {
      const res = await fetchJson<{ success: boolean; data: ComplianceResult; engine?: string }>(
        '/api/gemini/verify-bid',
        {
          method: 'POST',
          body: JSON.stringify(data)
        }
      );
      return { data: res.data, engine: res.engine };
    } catch (err) {
      console.warn('[STAMAS API] verifyBid server call failed, using client fallback:', err);
      throw err;
    }
  },

  /**
   * Clarification Notice Generator
   */
  async generateNotice(data: {
    tenderNo: string;
    tenderTitle: string;
    bidderName: string;
    deviations: Array<{
      clause: string;
      title: string;
      required: string;
      offered: string;
      remark: string;
    }>;
    contactOfficer?: string;
  }): Promise<{ noticeText: string }> {
    try {
      return await fetchJson<{ success: boolean; noticeText: string }>('/api/gemini/generate-notice', {
        method: 'POST',
        body: JSON.stringify(data)
      });
    } catch (err) {
      console.warn('[STAMAS API] generateNotice server call failed:', err);
      throw err;
    }
  },

  /**
   * Cartel & Collusion Anomaly Detection Radar
   */
  async detectCartel(tenderId: string): Promise<CartelDetectionResult> {
    try {
      return await fetchJson<CartelDetectionResult>('/api/gemini/detect-cartel', {
        method: 'POST',
        body: JSON.stringify({ tenderId })
      });
    } catch (err) {
      console.warn('[STAMAS API] detectCartel failed:', err);
      throw err;
    }
  },

  /**
   * STAMAS AI Procurement Copilot
   */
  async sendCopilotMessage(data: {
    message: string;
    tenderContext?: Record<string, unknown>;
  }): Promise<CopilotChatResponse> {
    try {
      return await fetchJson<CopilotChatResponse>('/api/gemini/copilot-chat', {
        method: 'POST',
        body: JSON.stringify(data)
      });
    } catch (err) {
      console.warn('[STAMAS API] sendCopilotMessage failed:', err);
      throw err;
    }
  },

  /**
   * System Health and Telemetry (including Active AI Engine indicator)
   */
  async getSystemHealth(): Promise<SystemHealth | null> {
    try {
      return await fetchJson<SystemHealth>('/api/system/health');
    } catch (err) {
      console.warn('[STAMAS API] getSystemHealth failed:', err);
      return null;
    }
  },

  /**
   * SIH Impact & Analytics
   */
  async getAnalytics(): Promise<SystemAnalytics | null> {
    try {
      const res = await fetchJson<{ success: boolean; data: SystemAnalytics }>('/api/system/analytics');
      return res?.data || null;
    } catch (err) {
      console.warn('[STAMAS API] getAnalytics failed:', err);
      return null;
    }
  },

  /**
   * Tender document import — real FastAPI pipeline.
   *
   * Upload -> Validate -> Store -> Extract text -> Clause extraction.
   * Throws the real backend error on any failure (never fakes success).
   */
  async importDocuments(tenderId: string, files: File[]): Promise<{ documents: BackendDocument[]; message?: string }> {
    try {
      const form = new FormData();
      files.forEach(f => form.append('files', f, f.name));
      const res = await fetchForm<{ success: boolean; documents: BackendDocument[]; message: string }>(
        `/api/tenders/${tenderId}/documents`,
        form
      );
      return { documents: res.documents || [], message: res.message };
    } catch (err) {
      console.error('[STAMAS API] importDocuments failed:', err);
      throw err;
    }
  },

  /**
   * List uploaded documents for a tender (backend source of truth).
   */
  async getTenderDocuments(tenderId: string): Promise<BackendDocument[]> {
    try {
      const res = await fetchJson<{ success: boolean; documents: BackendDocument[]; count: number }>(
        `/api/tenders/${tenderId}/documents`
      );
      return res?.documents || [];
    } catch (err) {
      console.warn('[STAMAS API] getTenderDocuments failed:', err);
      return [];
    }
  },

  /**
   * Delete an uploaded document (metadata + stored file + extracted text).
   */
  async deleteTenderDocument(tenderId: string, documentId: string): Promise<void> {
    try {
      await fetchJson<{ success: boolean; message: string }>(
        `/api/tenders/${tenderId}/documents/${documentId}`,
        { method: 'DELETE' }
      );
    } catch (err) {
      console.error('[STAMAS API] deleteTenderDocument failed:', err);
      throw err;
    }
  },

  /**
   * Rename a document's display filename (extension must stay the same).
   */
  async renameTenderDocument(
    tenderId: string, documentId: string, fileName: string
  ): Promise<BackendDocument> {
    try {
      const res = await fetchJson<BackendDocument>(
        `/api/tenders/${tenderId}/documents/${documentId}`,
        { method: 'PATCH', body: JSON.stringify({ fileName }) }
      );
      return res;
    } catch (err) {
      console.error('[STAMAS API] renameTenderDocument failed:', err);
      throw err;
    }
  },

  /**
   * Extracted text for a processed document.
   */
  async getTenderDocumentText(tenderId: string, documentId: string): Promise<string | null> {
    try {
      const res = await fetchJson<{ success: boolean; documentId: string; text: string }>(
        `/api/tenders/${tenderId}/documents/${documentId}/text`
      );
      return res?.text ?? null;
    } catch (err) {
      console.warn('[STAMAS API] getTenderDocumentText failed:', err);
      return null;
    }
  },

  /**
   * Candidate clauses mined from the tender's processed documents.
   */
  async getTenderClauses(tenderId: string): Promise<ExtractedTenderClause[]> {
    try {
      const res = await fetchJson<{ success: boolean; tenderId: string; clauses: ExtractedTenderClause[]; count: number }>(
        `/api/tenders/${tenderId}/clauses`
      );
      return res?.clauses || [];
    } catch (err) {
      console.warn('[STAMAS API] getTenderClauses failed:', err);
      return [];
    }
  },

  /**
   * Evidence-grounded AI verification of one extracted clause.
   */
  async verifyTenderClause(
    tenderId: string,
    clauseId: string,
    data?: { bidderName?: string; requirement?: string }
  ): Promise<ClauseVerification> {
    try {
      return await fetchJson<ClauseVerification>(
        `/api/tenders/${tenderId}/clauses/${clauseId}/verify`,
        { method: 'POST', body: JSON.stringify(data || {}) }
      );
    } catch (err) {
      console.warn('[STAMAS API] verifyTenderClause failed:', err);
      throw err;
    }
  },

  async runOpportunityAnalysis(
    tenderId: string,
    data?: { bidderName?: string }
  ): Promise<OpportunityAnalysisRecord> {
    try {
      const res = await fetchJson<{ success: boolean; analysis: OpportunityAnalysisRecord; message: string }>(
        `/api/tenders/${tenderId}/analyze`,
        { method: 'POST', body: JSON.stringify(data || {}) }
      );
      return res.analysis;
    } catch (err) {
      console.warn('[STAMAS API] runOpportunityAnalysis failed:', err);
      throw err;
    }
  },

  async getLatestAnalysis(tenderId: string): Promise<OpportunityAnalysisRecord | null> {
    try {
      const res = await fetchJson<{ success: boolean; analysis: OpportunityAnalysisRecord | null }>(
        `/api/tenders/${tenderId}/analyses/latest`
      );
      return res?.analysis ?? null;
    } catch (err) {
      console.warn('[STAMAS API] getLatestAnalysis failed:', err);
      return null;
    }
  }
};

// Also export apiClient as an alias for backwards compatibility
export const apiClient = api;
export default api;
