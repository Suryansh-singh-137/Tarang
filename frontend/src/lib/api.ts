// Unified API client for Tarang backend (SSE query streaming, STT, and TTS)

import { ChatState, ProgressEventData, QueryResultPayload } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type StreamCallbacks = {
  onProgress?: (progress: ProgressEventData) => void;
  onResult?: (result: QueryResultPayload) => void;
  onError?: (error: string) => void;
};

export interface QueryOptions {
  user_lat?: number | null;
  user_lon?: number | null;
  user_location_name?: string | null;
  language?: string | null;
  signal?: AbortSignal;
}

/**
 * Stream query via POST /query with SSE event parsing
 */
export async function streamQuery(
  query: string,
  state: ChatState,
  callbacks: StreamCallbacks,
  options?: QueryOptions
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      },
      body: JSON.stringify({
        query,
        conversation: state.conversation,
        last_parsed_intent: state.last_parsed_intent,
        last_results: state.last_results,
        user_lat: options?.user_lat ?? null,
        user_lon: options?.user_lon ?? null,
        user_location_name: options?.user_location_name ?? null,
        language: options?.language ?? null,
      }),
      signal: options?.signal,
    });

    if (!response.ok) {
      throw new Error(`Server responded with HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("Unable to read response stream from server");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const normalized = buffer.replace(/\r\n/g, "\n");
      const chunks = normalized.split("\n\n");
      buffer = chunks.pop() || "";

      for (const chunk of chunks) {
        if (!chunk.trim()) continue;

        let eventType = "message";
        let dataStr = "";

        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.replace("event:", "").trim();
          } else if (line.startsWith("data:")) {
            dataStr = line.replace("data:", "").trim();
          }
        }

        if (!dataStr) continue;

        try {
          const parsed = JSON.parse(dataStr);
          if (eventType === "progress") {
            callbacks.onProgress?.(parsed as ProgressEventData);
          } else if (eventType === "result") {
            callbacks.onResult?.(parsed as QueryResultPayload);
          } else if (eventType === "error") {
            callbacks.onError?.(parsed.error || "An unexpected error occurred");
          }
        } catch (e) {
          console.warn("Could not parse SSE JSON:", dataStr, e);
        }
      }
    }
  } catch (err: any) {
    if (err.name === "AbortError") {
      console.log("Query request aborted by user");
      return;
    }
    console.error("Query stream error:", err);
    callbacks.onError?.(err.message || "Failed to communicate with Tarang server");
  }
}

/**
 * Transcribe recorded audio blob via POST /transcribe (Groq Whisper)
 */
export async function transcribeAudio(audioBlob: Blob): Promise<{ transcript: string; language?: string }> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const response = await fetch(`${API_BASE_URL}/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(`Transcription failed (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  return {
    transcript: data.transcript || "",
    language: data.detected_language_whisper,
  };
}

/**
 * Synthesize text into audio bytes via POST /speak (Sarvam AI TTS)
 */
export async function synthesizeSpeech(text: string, language: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/speak`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text,
      language: language || "en",
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(`TTS synthesis failed with HTTP ${response.status}: ${errorText}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("audio")) {
    const errorJson = await response.text().catch(() => "");
    throw new Error(`Expected audio bytes but received ${contentType}: ${errorJson}`);
  }

  const blob = await response.blob();
  if (!blob || blob.size === 0) {
    throw new Error("Received empty audio response from TTS server");
  }

  return blob;
}

