"use client";

import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Mic, Send, Square, Play, Loader2, Volume2, AlertCircle } from "lucide-react";

// Types
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  language?: string;
};

type ChatState = {
  conversation: any[];
  last_parsed_intent: any | null;
  last_results: any;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);
  
  // Pipeline State for Multi-turn
  const [pipelineState, setPipelineState] = useState<ChatState>({
    conversation: [],
    last_parsed_intent: null,
    last_results: {},
  });

  const [playingId, setPlayingId] = useState<string | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Voice Input Logic
  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await handleTranscription(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone permission denied or error:", err);
      alert("Microphone permission denied. Please allow access to use voice input.");
    }
  };

  const handleTranscription = async (blob: Blob) => {
    setIsTranscribing(true);
    try {
      const formData = new FormData();
      formData.append("audio", blob, "recording.webm");

      const response = await fetch("http://localhost:8000/transcribe", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Transcription failed");
      }

      const data = await response.json();
      setInput(data.transcript);
    } catch (err) {
      console.error(err);
      alert("Couldn't transcribe — try again or type your question.");
    } finally {
      setIsTranscribing(false);
    }
  };

  // Chat Submission Logic
  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isQuerying) return;

    const queryText = input.trim();
    setInput("");
    
    const userMsgId = Date.now().toString();
    setMessages(prev => [...prev, { id: userMsgId, role: "user", content: queryText }]);
    
    setIsQuerying(true);
    const assistantMsgId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: assistantMsgId, role: "assistant", content: "" }]);

    try {
      const response = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: queryText,
          conversation: pipelineState.conversation,
          last_parsed_intent: pipelineState.last_parsed_intent,
          last_results: pipelineState.last_results,
        }),
      });

      if (!response.ok) throw new Error("Query API failed");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      let finalResultPayload: any = null;
      let buffer = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";
          
          for (const chunk of lines) {
            const eventMatch = chunk.match(/event: (.*)/);
            const dataMatch = chunk.match(/data: (.*)/);
            
            if (eventMatch && dataMatch) {
              const eventType = eventMatch[1];
              const eventData = JSON.parse(dataMatch[1]);
              
              if (eventType === "progress") {
                // We could show progress indicators here
              } else if (eventType === "result") {
                finalResultPayload = eventData;
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantMsgId 
                    ? { ...msg, content: eventData.answer_text, language: eventData.language } 
                    : msg
                ));
                
                setPipelineState({
                  conversation: eventData.conversation_history || [],
                  last_parsed_intent: eventData.last_parsed_intent || null,
                  last_results: eventData.last_results || {},
                });
              } else if (eventType === "error") {
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantMsgId 
                    ? { ...msg, content: `Error: ${eventData.error}` } 
                    : msg
                ));
              }
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => prev.map(msg => 
        msg.id === assistantMsgId 
          ? { ...msg, content: "An error occurred while reaching Tarang." } 
          : msg
      ));
    } finally {
      setIsQuerying(false);
    }
  };

  // Voice Output Logic
  const playAudio = async (messageId: string, text: string, language: string) => {
    if (playingId === messageId) {
      currentAudioRef.current?.pause();
      setPlayingId(null);
      return;
    }

    try {
      setPlayingId("loading-" + messageId);
      const response = await fetch("http://localhost:8000/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }),
      });

      if (!response.ok) throw new Error("TTS failed");

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
      }
      
      const audio = new Audio(url);
      currentAudioRef.current = audio;
      
      audio.onended = () => setPlayingId(null);
      audio.play();
      setPlayingId(messageId);
    } catch (err) {
      console.error("Audio playback error:", err);
      alert("Could not play audio. Please ensure SARVAM_API_KEY is configured and valid.");
      setPlayingId(null);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100 font-sans">
      {/* Header */}
      <header className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700 shadow-sm z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg">
            T
          </div>
          <h1 className="text-xl font-bold tracking-tight text-blue-400">Tarang</h1>
        </div>
        <div className="text-xs text-gray-400 font-medium px-3 py-1 bg-gray-700 rounded-full">
          Milestone 7
        </div>
      </header>

      {/* Chat Area */}
      <main className="flex-1 overflow-y-auto p-4 space-y-6 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gray-800 to-gray-900">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4 opacity-50">
            <div className="w-16 h-16 rounded-full bg-blue-900/50 flex items-center justify-center">
              <Mic className="w-8 h-8 text-blue-400" />
            </div>
            <p className="text-lg">Ask Tarang for marine safety intelligence.<br/>Type or speak in English, Hindi, or Tamil.</p>
          </div>
        ) : (
          messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-2xl px-5 py-4 shadow-md ${
                msg.role === "user" 
                  ? "bg-blue-600 text-white rounded-br-none" 
                  : "bg-gray-800 text-gray-200 border border-gray-700 rounded-bl-none"
              }`}>
                {msg.role === "assistant" ? (
                  <>
                    <div className="prose prose-invert max-w-none">
                      {msg.content === "" ? (
                        <div className="flex items-center gap-2 text-gray-400">
                          <Loader2 className="w-4 h-4 animate-spin" /> Thinking...
                        </div>
                      ) : (
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      )}
                    </div>
                    {msg.content && msg.language && (
                      <div className="mt-4 pt-3 border-t border-gray-700 flex justify-end">
                        <button 
                          onClick={() => playAudio(msg.id, msg.content, msg.language!)}
                          className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-full"
                        >
                          {playingId === "loading-" + msg.id ? (
                            <><Loader2 className="w-4 h-4 animate-spin" /> Synthesizing...</>
                          ) : playingId === msg.id ? (
                            <><Square className="w-4 h-4" /> Stop</>
                          ) : (
                            <><Volume2 className="w-4 h-4" /> Read Aloud</>
                          )}
                        </button>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Input Area */}
      <footer className="p-4 bg-gray-800 border-t border-gray-700 relative">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative flex items-center">
          
          <button
            type="button"
            onClick={toggleRecording}
            className={`absolute left-2 p-2.5 rounded-full transition-all ${
              isRecording 
                ? "bg-red-500/20 text-red-500 animate-pulse scale-110" 
                : "text-gray-400 hover:bg-gray-700 hover:text-white"
            }`}
            title="Voice Input"
          >
            {isRecording ? <Square className="w-5 h-5" fill="currentColor" /> : <Mic className="w-5 h-5" />}
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isTranscribing || isQuerying}
            placeholder={isTranscribing ? "Transcribing..." : isRecording ? "Listening..." : "Ask about a location (e.g. Is it safe to fish near Kochi?)"}
            className="w-full bg-gray-900 border border-gray-700 rounded-full py-4 pl-14 pr-14 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors disabled:opacity-50"
          />

          <button
            type="submit"
            disabled={!input.trim() || isQuerying || isTranscribing}
            className="absolute right-2 p-2.5 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
        
        <div className="text-center mt-3 text-xs text-gray-500 flex items-center justify-center gap-1">
          <AlertCircle className="w-3 h-3" />
          Tarang is a decision-support tool. Always follow official coast guard advisories.
        </div>
      </footer>
    </div>
  );
}
