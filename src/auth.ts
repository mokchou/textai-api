import { ApiKeyRecord } from "./types.ts";
import { getKv } from "./kv.ts";

/**
 * Generate a random API key.
 */
export function generateApiKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  return "sk_" + Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}

const DEMO_FREE_CREDITS = 100;

/**
 * Create a new API key with demo credits (100 free).
 * Optionally pass clientIp to enforce 1 demo key per IP.
 * Returns the key and whether it's a demo key.
 */
export async function createApiKey(clientIp?: string): Promise<{ apiKey: string; demo: boolean; alreadyHasDemo?: boolean }> {
  const kv = await getKv();

  // Optional: enforce 1 demo key per IP
  if (clientIp) {
    const existing = await kv.get<string>(["demo_ip", clientIp]);
    if (existing.value) {
      // Return existing key info without creating a new one
      return { apiKey: existing.value, demo: true, alreadyHasDemo: true };
    }
  }

  const apiKey = generateApiKey();
  const record: ApiKeyRecord = { apiKey, credits: DEMO_FREE_CREDITS, createdAt: Date.now(), demo: true };
  await kv.set(["key", apiKey], record);

  if (clientIp) {
    await kv.set(["demo_ip", clientIp], apiKey);
  }

  return { apiKey, demo: true };
}

/**
 * Get credit balance for an API key. Returns null if key doesn't exist.
 */
export async function getCredits(apiKey: string): Promise<number | null> {
  const kv = await getKv();
  const entry = await kv.get<ApiKeyRecord>(["key", apiKey]);
  return entry.value?.credits ?? null;
}

/**
 * Add credits to an API key.
 */
export async function addCredits(apiKey: string, amount: number): Promise<number> {
  const kv = await getKv();
  const entry = await kv.get<ApiKeyRecord>(["key", apiKey]);
  const record: ApiKeyRecord = entry.value ?? { apiKey, credits: 0, createdAt: Date.now() };
  record.credits += amount;
  await kv.set(["key", apiKey], record);
  return record.credits;
}

/**
 * Deduct credits. Returns false if insufficient balance.
 */
export async function deductCredits(apiKey: string, amount: number): Promise<boolean> {
  const kv = await getKv();
  const entry = await kv.get<ApiKeyRecord>(["key", apiKey]);
  if (!entry.value) return false;
  const record = entry.value;
  if (record.credits < amount) return false;
  record.credits -= amount;
  await kv.set(["key", apiKey], record);
  return true;
}

/**
 * Validate API key and check minimum credits required.
 */
export async function validateApiKey(
  apiKey: string,
  minCredits = 1,
): Promise<{ valid: boolean; credits?: number; error?: string }> {
  if (!apiKey || !apiKey.startsWith("sk_")) {
    return { valid: false, error: "Invalid API key format" };
  }
  const credits = await getCredits(apiKey);
  if (credits === null) {
    return { valid: false, error: "API key not found" };
  }
  if (credits < minCredits) {
    return {
      valid: false,
      credits,
      error: `Insufficient credits. Need ${minCredits}, have ${credits}. Top up at POST /credits/buy`,
    };
  }
  return { valid: true, credits };
}
