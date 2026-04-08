import { getConfig } from "./config.ts";

const GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions";
const GROQ_MODEL = "llama-3.1-8b-instant";

// ---- Groq API call ----

async function callGroq(systemPrompt: string, userMessage: string): Promise<string> {
  const config = getConfig();
  const response = await fetch(GROQ_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${config.groqApiKey}`,
    },
    body: JSON.stringify({
      model: GROQ_MODEL,
      max_tokens: 512,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userMessage },
      ],
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Groq API error ${response.status}: ${err}`);
  }

  const data: any = await response.json();
  return data.choices[0].message.content;
}

// ---- Rule-based fallbacks (no API key needed) ----

function summarizeRuleBased(text: string, maxSentences: number): string {
  const sentences = text.match(/[^.!?]+[.!?]+/g) ?? [text];
  return sentences.slice(0, maxSentences).join(" ").trim();
}

const STOP_WORDS = new Set([
  "the", "a", "an", "is", "in", "on", "at", "to", "of", "and", "or", "but",
  "for", "with", "by", "as", "this", "that", "it", "be", "was", "are", "were",
  "been", "have", "has", "had", "will", "would", "could", "should", "may",
  "might", "can", "do", "does", "did", "not", "no", "from", "up", "about",
  "into", "through", "each", "few", "more", "most", "other", "some", "than",
  "then", "there", "these", "they", "those", "what", "which", "who", "when",
  "where", "why", "how", "all", "any", "both", "very", "just", "so",
]);

function extractKeywordsRuleBased(text: string, maxKeywords: number): string[] {
  const words = text.toLowerCase().match(/\b[a-z]{3,}\b/g) ?? [];
  const freq: Record<string, number> = {};
  for (const w of words) {
    if (!STOP_WORDS.has(w)) freq[w] = (freq[w] ?? 0) + 1;
  }
  return Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, maxKeywords)
    .map(([w]) => w);
}

// ---- Public API ----

export async function summarize(
  text: string,
  maxSentences = 3,
): Promise<{ summary: string; inputChars: number; engine: string }> {
  if (text.length > 10000) throw new Error("Text too long. Maximum 10,000 characters.");

  const config = getConfig();
  if (config.groqApiKey) {
    const system = `You are a concise summarizer. Summarize the given text in exactly ${maxSentences} sentence(s). Return ONLY the summary, no preamble.`;
    const summary = await callGroq(system, text);
    return { summary: summary.trim(), inputChars: text.length, engine: "groq" };
  }

  return {
    summary: summarizeRuleBased(text, maxSentences),
    inputChars: text.length,
    engine: "rule-based",
  };
}

export async function extractKeywords(
  text: string,
  maxKeywords = 10,
): Promise<{ keywords: string[]; inputChars: number; engine: string }> {
  if (text.length > 10000) throw new Error("Text too long. Maximum 10,000 characters.");

  const config = getConfig();
  if (config.groqApiKey) {
    const system = `You are a keyword extractor. Extract the ${maxKeywords} most important keywords or key phrases from the given text. Return ONLY a JSON array of strings, e.g. ["keyword1", "keyword2"]. No other text.`;
    const raw = await callGroq(system, text);
    let keywords: string[];
    try {
      keywords = JSON.parse(raw.trim());
      if (!Array.isArray(keywords)) throw new Error();
      keywords = keywords.slice(0, maxKeywords).map((k) => String(k));
    } catch {
      keywords = raw.split("\n")
        .map((k) => k.replace(/^[-*•\d.]\s*/, "").trim())
        .filter(Boolean)
        .slice(0, maxKeywords);
    }
    return { keywords, inputChars: text.length, engine: "groq" };
  }

  return {
    keywords: extractKeywordsRuleBased(text, maxKeywords),
    inputChars: text.length,
    engine: "rule-based",
  };
}

const SUPPORTED_LANGS: Record<string, string> = {
  en: "English", fr: "French", es: "Spanish", de: "German",
  it: "Italian", pt: "Portuguese", ru: "Russian", ja: "Japanese",
  zh: "Chinese (Simplified)", ar: "Arabic",
};

const MYMEMORY_LANG_CODES: Record<string, string> = {
  en: "en-US", fr: "fr-FR", es: "es-ES", de: "de-DE",
  it: "it-IT", pt: "pt-PT", ru: "ru-RU", ja: "ja-JP",
  zh: "zh-CN", ar: "ar-EG",
};

async function translateMyMemory(text: string, targetLang: string): Promise<string> {
  const sourceLang = "en-US";
  const targetCode = MYMEMORY_LANG_CODES[targetLang] ?? targetLang;
  const url = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=${sourceLang}|${targetCode}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`MyMemory API error ${resp.status}`);
  const data: any = await resp.json();
  if (data.responseStatus !== 200) throw new Error(`MyMemory error: ${data.responseDetails}`);
  return data.responseData.translatedText;
}

export async function translate(
  text: string,
  targetLang: string,
): Promise<{ translation: string; targetLang: string; inputChars: number; engine: string }> {
  if (text.length > 5000) throw new Error("Text too long. Maximum 5,000 characters for translation.");

  const langName = SUPPORTED_LANGS[targetLang.toLowerCase()];
  if (!langName) {
    throw new Error(`Unsupported language: ${targetLang}. Supported: ${Object.keys(SUPPORTED_LANGS).join(", ")}`);
  }

  const config = getConfig();
  if (config.groqApiKey) {
    const system = `You are a professional translator. Translate the given text to ${langName}. Return ONLY the translation, no explanation or preamble.`;
    const translation = await callGroq(system, text);
    return { translation: translation.trim(), targetLang, inputChars: text.length, engine: "groq" };
  }

  // Fallback: use MyMemory free translation API (no key required)
  const translation = await translateMyMemory(text, targetLang.toLowerCase());
  return { translation, targetLang, inputChars: text.length, engine: "mymemory" };
}
