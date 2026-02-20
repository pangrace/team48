import { useMemo, useState, type CSSProperties } from 'react'
import './App.css'
import { useTheme } from './context/themeContext'

type StepFeedback = {
  id: string
  studentStep: string
  status: 'correct' | 'incorrect'
  whatWentWrong: string
  howToFix: string
}

type MathFeedback = {
  problemTitle: string
  problemPrompt: string
  personalizedSummary: string
  score: number
  totalPoints: number
  steps: StepFeedback[]
}

type PracticeProblem = {
  title: string
  prompt: string
  tip: string
}

const practiceProblems: PracticeProblem[] = [
  {
    title: 'Practice Problem 1',
    prompt: 'Solve: 3(x + 2) - 4 = 2x + 7',
    tip: 'Distribute first, then isolate variable terms on one side.',
  },
  {
    title: 'Practice Problem 2',
    prompt: 'Factor and solve: x^2 - 5x + 6 = 0',
    tip: 'Find two numbers that multiply to +6 and add to -5.',
  },
  {
    title: 'Practice Problem 3',
    prompt: 'Solve the system: y = -x + 5 and y = 2x - 1',
    tip: 'Set the expressions for y equal and solve for x first.',
  },
  {
    title: 'Practice Problem 4',
    prompt: 'Simplify and solve: 4 - 2(3x - 1) = 10',
    tip: 'Watch negative distribution: -2(3x - 1) = -6x + 2.',
  },
]

const hashText = (text: string): number =>
  text
    .toLowerCase()
    .split('')
    .reduce((acc, char) => acc + char.charCodeAt(0), 0)

const getPracticeProblem = (seedIndex: number, offset: number): PracticeProblem => {
  const problemIndex = (seedIndex + offset) % practiceProblems.length
  return practiceProblems[problemIndex]
}

type AnalyzeResponse = {
  feedback: {
    problemTitle: string
    problemPrompt: string
    personalizedSummary: string
    score: number
    totalPoints: number
    steps: Array<{
      id?: string
      studentStep: string
      status: 'correct' | 'incorrect'
      whatWentWrong: string
      howToFix: string
    }>
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const getErrorMessage = async (response: Response): Promise<string> => {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ?? `Request failed with status ${response.status}`
  } catch {
    return `Request failed with status ${response.status}`
  }
}

const analyzePdf = async (file: File): Promise<MathFeedback> => {
  const formData = new FormData()
  formData.append('pdf', file)

  const response = await fetch(`${API_BASE_URL}/api/analyze-pdf`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(await getErrorMessage(response))
  }

  const payload = (await response.json()) as AnalyzeResponse
  const feedback = payload.feedback

  return {
    problemTitle: feedback.problemTitle,
    problemPrompt: feedback.problemPrompt,
    personalizedSummary: feedback.personalizedSummary,
    score: feedback.score,
    totalPoints: feedback.totalPoints,
    steps: feedback.steps.map((step, index) => ({
      id: step.id ?? `step-${index + 1}`,
      studentStep: step.studentStep,
      status: step.status,
      whatWentWrong: step.whatWentWrong,
      howToFix: step.howToFix,
    })),
  }
}

function App() {
  const { theme } = useTheme()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [feedback, setFeedback] = useState<MathFeedback | null>(null)
  const [feedbackSeedIndex, setFeedbackSeedIndex] = useState(0)
  const [hasConfirmedFeedback, setHasConfirmedFeedback] = useState(false)
  const [practiceOffset, setPracticeOffset] = useState(1)
  const [practiceProblem, setPracticeProblem] = useState<PracticeProblem | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fileSizeLabel = useMemo(() => {
    if (!selectedFile) {
      return ''
    }

    const kb = selectedFile.size / 1024
    return kb > 1024 ? `${(kb / 1024).toFixed(2)} MB` : `${kb.toFixed(1)} KB`
  }, [selectedFile])

  const appStyle = useMemo(
    () =>
      ({
        '--app-bg': theme.colors.background,
        '--theme-text': theme.colors.text,
        '--theme-primary': theme.colors.primary,
        '--theme-secondary': theme.colors.secondary,
        '--theme-ternary': theme.colors.ternary,
        '--theme-error': theme.colors.error,
      }) as CSSProperties,
    [theme],
  )

  const resetFeedbackFlow = () => {
    setFeedback(null)
    setHasConfirmedFeedback(false)
    setPracticeOffset(1)
    setPracticeProblem(null)
    setErrorMessage(null)
  }

  const processUploadedFile = async (file: File) => {
    setSelectedFile(file)
    resetFeedbackFlow()
    setIsGenerating(true)
    setFeedbackSeedIndex(hashText(file.name))

    try {
      const responseFeedback = await analyzePdf(file)
      setFeedback(responseFeedback)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to analyze PDF.'
      setErrorMessage(message)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]

    if (!file) {
      return
    }

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a PDF file.')
      event.target.value = ''
      return
    }

    void processUploadedFile(file)
    event.target.value = ''
  }

  const handleConfirmRead = () => {
    if (!feedback) {
      return
    }

    setHasConfirmedFeedback(true)
    setPracticeOffset(1)
    setPracticeProblem(getPracticeProblem(feedbackSeedIndex, 1))
  }

  const handleNextProblem = () => {
    const newOffset = practiceOffset + 1
    setPracticeOffset(newOffset)
    setPracticeProblem(getPracticeProblem(feedbackSeedIndex, newOffset))
  }

  if (!selectedFile) {
    return (
      <main className="homework-app upload-mode" style={appStyle}>
        <section className="panel upload-page" aria-label="Homework PDF upload">
          <p className="eyebrow">Math Feedback Assistant</p>
          <h1>Upload your solution PDF</h1>
          <p className="intro">
            Start here by uploading a math homework PDF. After upload, the full screen switches to personalized
            step-by-step solution feedback from the agent.
          </p>

          <label htmlFor="pdf-upload" className="file-picker">
            <span className="file-picker-title">Choose PDF</span>
            <span className="file-picker-subtitle">Accepted format: .pdf</span>
            <input id="pdf-upload" type="file" accept=".pdf,application/pdf" onChange={handleFileChange} />
          </label>
        </section>
      </main>
    )
  }

  return (
    <main className="homework-app solution-mode" style={appStyle}>
      <section className="panel solution-page" aria-label="Generated math feedback">
        <header className="solution-head">
          <div>
            <p className="eyebrow">Uploaded PDF</p>
            <h2>{selectedFile.name}</h2>
            <p className="file-meta">{fileSizeLabel}</p>
          </div>
          <label htmlFor="replace-upload" className="swap-file-button">
            Upload another PDF
            <input
              id="replace-upload"
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleFileChange}
              aria-label="Upload another homework PDF"
            />
          </label>
        </header>

        {isGenerating ? <p className="loading-text">Analyzing your solution steps with the agent...</p> : null}

        {!isGenerating && errorMessage ? (
          <p className="error-text">{errorMessage}</p>
        ) : null}

        {!isGenerating && !errorMessage && feedback ? (
          <div className="feedback-content">
            <div className="score-banner">
              <p>
                {feedback.problemTitle}: <strong>{feedback.problemPrompt}</strong>
              </p>
              <p>
                <span>{feedback.score}</span> / {feedback.totalPoints}
              </p>
            </div>

            <p className="summary">{feedback.personalizedSummary}</p>

            <div className="steps-block" aria-live="polite">
              <h3>Step-by-Step Breakdown</h3>
              {feedback.steps.map((step, index) => (
                <article className="step-card" key={step.id}>
                  <div className="step-head">
                    <p>Step {index + 1}</p>
                    <span className={`status-pill ${step.status}`}>
                      {step.status === 'correct' ? 'Correct' : 'Needs Fix'}
                    </span>
                  </div>
                  <p className="step-work">Student wrote: {step.studentStep}</p>
                  <p>
                    <strong>Where it went wrong:</strong> {step.whatWentWrong}
                  </p>
                  <p>
                    <strong>How to fix:</strong> {step.howToFix}
                  </p>
                </article>
              ))}
            </div>

            <button
              type="button"
              className="secondary-button"
              onClick={handleConfirmRead}
              disabled={hasConfirmedFeedback}
            >
              {hasConfirmedFeedback ? 'Feedback Confirmed' : 'I read this feedback'}
            </button>

            {hasConfirmedFeedback && practiceProblem ? (
              <div className="next-problem" role="status" aria-live="polite">
                <h3>{practiceProblem.title}</h3>
                <p>{practiceProblem.prompt}</p>
                <p>
                  <strong>Tip:</strong> {practiceProblem.tip}
                </p>
                <button type="button" className="primary-button" onClick={handleNextProblem}>
                  Give me another mock problem
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </main>
  )
}

export default App
