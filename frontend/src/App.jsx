import { useState, useEffect } from "react"
import axios from "axios"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import {
  ShieldCheck, Fingerprint, ScanText, Loader2,
  Copy, CheckCheck, AlertTriangle, User, Bot,
  Sun, Moon, Cpu
} from "lucide-react"

const API = "http://localhost:8000"

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100)
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>Confidence</span>
        <span className="font-mono font-semibold text-foreground">{pct}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-secondary overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${pct}%`,
            background: pct > 80
              ? "hsl(0 72% 51%)"
              : pct > 60
              ? "hsl(38 92% 50%)"
              : "hsl(142 71% 45%)",
          }}
        />
      </div>
    </div>
  )
}

function LabelBadge({ label }) {
  if (label === "AI" || label === "ChatGPT")
    return (
      <Badge className="gap-1.5 px-3 py-1 text-xs font-medium bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30 hover:bg-red-500/20">
        <Bot size={12} />AI Generated
      </Badge>
    )
  if (label === "Human")
    return (
      <Badge className="gap-1.5 px-3 py-1 text-xs font-medium bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20">
        <User size={12} />Human Written
      </Badge>
    )
  return (
    <Badge className="gap-1.5 px-3 py-1 text-xs font-medium bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/20">
      <AlertTriangle size={12} />Uncertain
    </Badge>
  )
}

function ParagraphRow({ para }) {
  return (
    <div className={`rounded-xl border p-4 space-y-2 ${
      para.modified
        ? "border-red-500/30 bg-red-500/5"
        : "border-border/50 bg-secondary/50"
    }`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded">P{para.paragraph}</span>
          <LabelBadge label={para.label} />
        </div>
        {para.modified
          ? <span className="text-xs font-semibold flex items-center gap-1.5 text-red-600 dark:text-red-400 bg-red-500/10 px-2 py-1 rounded-md">
              <AlertTriangle size={12} />MODIFIED
            </span>
          : <span className="text-xs font-semibold flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-md">
              <CheckCheck size={12} />intact
            </span>
        }
      </div>
      <p className="text-sm text-muted-foreground font-mono truncate leading-relaxed">{para.text_preview}</p>
    </div>
  )
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <Button variant="ghost" size="sm" onClick={copy} className="h-8 px-3 text-xs gap-1.5 hover:bg-secondary">
      {copied
        ? <><CheckCheck size={14} className="text-emerald-500" />Copied</>
        : <><Copy size={14} />Copy</>
      }
    </Button>
  )
}

function ResultCard({ children }) {
  return (
    <Card className="mt-5 border-border/60 bg-card/80">
      <CardContent className="pt-6 space-y-5">
        {children}
      </CardContent>
    </Card>
  )
}

function StatusIndicator({ connected, label }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-red-500"}`} />
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
    </div>
  )
}

export default function App() {
  const [darkMode, setDarkMode] = useState(true)
  const [apiConnected, setApiConnected] = useState(false)
  const [modelLoaded, setModelLoaded] = useState(false)

  // Shared text state that persists across tabs
  const [sharedText, setSharedText] = useState("")

  const [classifyResult, setClassifyResult] = useState(null)
  const [classifyLoading, setClassifyLoading] = useState(false)

  const [tagResult, setTagResult] = useState(null)
  const [tagLoading, setTagLoading] = useState(false)

  const [verifyResult, setVerifyResult] = useState(null)
  const [verifyLoading, setVerifyLoading] = useState(false)

  const [error, setError] = useState(null)

  // Check API and model status
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const { data } = await axios.get(`${API}/health`)
        setApiConnected(true)
        setModelLoaded(data?.model_loaded ?? true)
      } catch {
        setApiConnected(false)
        setModelLoaded(false)
      }
    }
    checkStatus()
    const interval = setInterval(checkStatus, 10000)
    return () => clearInterval(interval)
  }, [])

  // Apply dark mode class to html
  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode)
  }, [darkMode])

  const call = async (endpoint, text, setLoading, setResult) => {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    try {
      const { data } = await axios.post(`${API}/${endpoint}`, { text })
      setResult(data)
    } catch (e) {
      setError(e.response?.data?.detail || "Could not reach the API. Is the server running on port 8000?")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/90 backdrop-blur-md">
        <div className="max-w-2xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-foreground flex items-center justify-center">
              <Fingerprint size={20} className="text-background" />
            </div>
            <div>
              <p className="text-base font-semibold tracking-tight leading-none">Provint</p>
              <p className="text-sm text-muted-foreground mt-1">Gen AI Provenance & Integrity</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3 bg-secondary/60 px-3 py-1.5 rounded-full">
              <StatusIndicator connected={modelLoaded} label="Model" />
              <div className="w-px h-3 bg-border" />
              <StatusIndicator connected={apiConnected} label="API" />
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDarkMode(!darkMode)}
              className="h-9 w-9 rounded-full"
            >
              {darkMode ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-2xl mx-auto px-6 py-10">
        {error && (
          <div className="mb-6 rounded-xl border border-red-500/40 bg-red-500/10 px-5 py-4 text-sm text-red-600 dark:text-red-400 flex items-center gap-3">
            <AlertTriangle size={16} />
            {error}
          </div>
        )}

        <Tabs defaultValue="classify" className="w-full">
          <TabsList className="w-full grid grid-cols-3 h-12 p-1.5 bg-secondary/60 rounded-xl">
            <TabsTrigger value="classify" className="gap-2 text-sm rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <ScanText size={16} />Classify
            </TabsTrigger>
            <TabsTrigger value="tag" className="gap-2 text-sm rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <Fingerprint size={16} />Tag
            </TabsTrigger>
            <TabsTrigger value="verify" className="gap-2 text-sm rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <ShieldCheck size={16} />Verify
            </TabsTrigger>
          </TabsList>

          {/* Classify */}
          <TabsContent value="classify" className="mt-6">
            <Card className="border-border/60 bg-card/80">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold">Authorship Detection</CardTitle>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Paste any text to estimate whether it was written by a human or generated by AI.
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  placeholder="Paste text here..."
                  className="min-h-[180px] font-mono text-sm resize-none bg-input/60 border-border/60 focus:border-ring focus:ring-1 focus:ring-ring rounded-xl"
                  value={sharedText}
                  onChange={e => setSharedText(e.target.value)}
                />
                <Button
                  className="w-full h-11 text-sm font-medium rounded-xl"
                  onClick={() => call("classify", sharedText, setClassifyLoading, setClassifyResult)}
                  disabled={classifyLoading || !sharedText.trim()}
                >
                  {classifyLoading
                    ? <><Loader2 size={16} className="animate-spin mr-2" />Analysing...</>
                    : "Classify"
                  }
                </Button>
              </CardContent>
            </Card>

            {classifyResult && (
              <ResultCard>
                <div className="flex items-center justify-between">
                  <LabelBadge label={classifyResult.label} />
                  <span className="text-sm text-muted-foreground">{classifyResult.phrase}</span>
                </div>
                <ConfidenceBar value={classifyResult.confidence} />
                <p className="text-sm text-muted-foreground font-mono bg-secondary/50 px-3 py-2 rounded-lg">ref: {classifyResult.reference}</p>
              </ResultCard>
            )}
          </TabsContent>

          {/* Tag */}
          <TabsContent value="tag" className="mt-6">
            <Card className="border-border/60 bg-card/80">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold">Embed Watermark</CardTitle>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Classifies each paragraph and embeds an invisible steganographic marker and integrity digest.
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  placeholder="Paste text to watermark..."
                  className="min-h-[180px] font-mono text-sm resize-none bg-input/60 border-border/60 focus:border-ring focus:ring-1 focus:ring-ring rounded-xl"
                  value={sharedText}
                  onChange={e => setSharedText(e.target.value)}
                />
                <Button
                  className="w-full h-11 text-sm font-medium rounded-xl"
                  onClick={() => call("tag", sharedText, setTagLoading, setTagResult)}
                  disabled={tagLoading || !sharedText.trim()}
                >
                  {tagLoading
                    ? <><Loader2 size={16} className="animate-spin mr-2" />Embedding...</>
                    : "Tag & Watermark"
                  }
                </Button>
              </CardContent>
            </Card>

            {tagResult && (
              <ResultCard>
                <div className="flex items-center justify-between">
                  <LabelBadge label={tagResult.label} />
                  <span className="text-sm text-muted-foreground font-mono bg-secondary/50 px-2 py-1 rounded">ref: {tagResult.reference}</span>
                </div>
                <ConfidenceBar value={tagResult.confidence} />
                <Separator className="bg-border/50" />
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Watermarked Text</span>
                    <CopyButton text={tagResult.tagged_text} />
                  </div>
                  <div className="rounded-xl bg-secondary/50 p-4 font-mono text-sm leading-relaxed max-h-44 overflow-y-auto whitespace-pre-wrap break-all border border-border/40">
                    {tagResult.tagged_text}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    The watermark is invisible - copy this and paste into Verify to confirm integrity.
                  </p>
                </div>
              </ResultCard>
            )}
          </TabsContent>

          {/* Verify */}
          <TabsContent value="verify" className="mt-6">
            <Card className="border-border/60 bg-card/80">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold">Verify Integrity</CardTitle>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Paste watermarked text to extract the embedded marker and check if it has been modified.
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  placeholder="Paste watermarked text here..."
                  className="min-h-[180px] font-mono text-sm resize-none bg-input/60 border-border/60 focus:border-ring focus:ring-1 focus:ring-ring rounded-xl"
                  value={sharedText}
                  onChange={e => setSharedText(e.target.value)}
                />
                <Button
                  className="w-full h-11 text-sm font-medium rounded-xl"
                  onClick={() => call("verify", sharedText, setVerifyLoading, setVerifyResult)}
                  disabled={verifyLoading || !sharedText.trim()}
                >
                  {verifyLoading
                    ? <><Loader2 size={16} className="animate-spin mr-2" />Verifying...</>
                    : "Verify"
                  }
                </Button>
              </CardContent>
            </Card>

            {verifyResult && (
              <ResultCard>
                {!verifyResult.found ? (
                  <div className="flex items-center gap-3 text-sm text-muted-foreground bg-secondary/50 p-4 rounded-xl">
                    <AlertTriangle size={16} />
                    No watermark found in this text.
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <LabelBadge label={verifyResult.label} />
                      <Badge
                        className={`text-xs gap-1.5 px-3 py-1 ${
                          verifyResult.modified 
                            ? "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30" 
                            : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                        }`}
                      >
                        {verifyResult.modified
                          ? <><AlertTriangle size={12} />MODIFIED</>
                          : <><CheckCheck size={12} />INTACT</>
                        }
                      </Badge>
                    </div>
                    <Separator className="bg-border/50" />
                    <div className="space-y-3">
                      <p className="text-sm font-medium">Paragraph Breakdown</p>
                      <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                        {verifyResult.paragraphs.map((p, i) => (
                          <ParagraphRow key={i} para={p} />
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </ResultCard>
            )}
          </TabsContent>
        </Tabs>

        <p className="text-center text-sm text-muted-foreground mt-8">
          Authorship signals are probabilistic - not definitive judgments.
        </p>
      </main>
    </div>
  )
}