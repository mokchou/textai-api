export interface AppConfig {
  groqApiKey: string;
  agentWalletPrivateKey: string;
  solanaRpcUrl: string;
  usdcMint: string;
  creditsPerUsdc: number;
}

export interface ApiKeyRecord {
  apiKey: string;
  credits: number;
  createdAt: number;
  demo?: boolean;
}

export interface PendingPayment {
  apiKey: string;
  usdcAmount: number;
  createdAt: number;
  memo: string;
}

export interface CreditBuyResponse {
  wallet: string;
  usdcAmount: number;
  memo: string;
  creditsToReceive: number;
  instructions: string;
}

export interface SummarizeRequest {
  text: string;
  maxSentences?: number;
}

export interface KeywordsRequest {
  text: string;
  maxKeywords?: number;
}

export interface TranslateRequest {
  text: string;
  targetLang: string;
}
