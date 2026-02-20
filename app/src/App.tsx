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

type FeedbackSeed = {
  problemTitle: string
  problemPrompt: string
  score: number
  totalPoints: number
  steps: Omit<StepFeedback, 'id'>[]
}

const feedbackSeeds: FeedbackSeed[] = [
  {
    problemTitle: 'Solve for x',
    problemPrompt: '2(x - 3) + 5 = 3x - 1',
    score: 7,
    totalPoints: 10,
    steps: [
      {
        studentStep: '2x - 6 + 5 = 3x - 1',
        status: 'correct',
        whatWentWrong: 'No issue here. You distributed 2 correctly.',
        howToFix: 'Keep this structure and continue combining constants.',
      },
      {
        studentStep: '2x - 1 = 3x + 1',
        status: 'incorrect',
        whatWentWrong: 'The right side changed from -1 to +1 with no valid operation.',
        howToFix: 'Keep the equation as 2x - 1 = 3x - 1 before moving terms.',
      },
      {
        studentStep: '-x = 2, so x = -2',
        status: 'incorrect',
        whatWentWrong: 'This result came from the earlier sign error and no variable cancellation check.',
        howToFix: 'From 2x - 1 = 3x - 1, subtract 2x to get -1 = x - 1, then add 1: x = 0.',
      },
    ],
  },
  {
    problemTitle: 'Factor the quadratic',
    problemPrompt: 'x^2 + 7x + 12 = 0',
    score: 8,
    totalPoints: 10,
    steps: [
      {
        studentStep: '(x + 3)(x + 4) = 0',
        status: 'correct',
        whatWentWrong: 'No issue here. The factors are correct.',
        howToFix: 'Good factoring pattern. Continue using zero-product property.',
      },
      {
        studentStep: 'x + 3 = 3, x + 4 = 4',
        status: 'incorrect',
        whatWentWrong: 'You set each factor equal to its constant instead of zero.',
        howToFix: 'Set each factor to zero: x + 3 = 0 and x + 4 = 0.',
      },
      {
        studentStep: 'x = 0 and x = 0',
        status: 'incorrect',
        whatWentWrong: 'Both solutions collapsed because of the incorrect equation setup.',
        howToFix: 'Solve correctly to get x = -3 and x = -4.',
      },
    ],
  },
  {
    problemTitle: 'System of equations',
    problemPrompt: 'y = 2x + 1 and y = x + 4',
    score: 9,
    totalPoints: 10,
    steps: [
      {
        studentStep: '2x + 1 = x + 4',
        status: 'correct',
        whatWentWrong: 'No issue. Substitution setup is right.',
        howToFix: 'Great start. Now isolate x carefully.',
      },
      {
        studentStep: 'x + 1 = 4, so x = 3',
        status: 'correct',
        whatWentWrong: 'No issue. Rearranging was accurate.',
        howToFix: 'Now substitute x = 3 back into either equation.',
      },
      {
        studentStep: 'y = 2(3) + 1 = 8',
        status: 'incorrect',
        whatWentWrong: 'Arithmetic slip: 2(3) + 1 equals 7, not 8.',
        howToFix: 'Use y = 7. Final solution pair is (3, 7).',
      },
    ],
  },
]

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

const toTitleCase = (value: string): string => value.charAt(0).toUpperCase() + value.slice(1).toLowerCase()

const inferStudentName = (fileName: string): string => {
  const withoutExtension = fileName.replace(/\.pdf$/i, '')
  const firstToken = withoutExtension.split(/[^a-zA-Z]/).find((part) => part.length > 1)
  return firstToken ? toTitleCase(firstToken) : 'Student'
}

const hashText = (text: string): number =>
  text
    .toLowerCase()
    .split('')
    .reduce((acc, char) => acc + char.charCodeAt(0), 0)

const getMockMathFeedback = (fileName: string): { feedback: MathFeedback; seedIndex: number } => {
  const seedIndex = hashText(fileName) % feedbackSeeds.length
  const seed = feedbackSeeds[seedIndex]
  const studentName = inferStudentName(fileName)

  return {
    seedIndex,
    feedback: {
      problemTitle: seed.problemTitle,
      problemPrompt: seed.problemPrompt,
      score: seed.score,
      totalPoints: seed.totalPoints,
      personalizedSummary: `${studentName}, your setup shows good intuition. The main point to improve is checking signs and arithmetic at each transition before writing your final answer.`,
      steps: seed.steps.map((step, index) => ({
        ...step,
        id: `${seed.problemTitle}-${index}`,
      })),
    },
  }
}

const getPracticeProblem = (seedIndex: number, offset: number): PracticeProblem => {
  const problemIndex = (seedIndex + offset) % practiceProblems.length
  return practiceProblems[problemIndex]
}

function App() {
  const { theme } = useTheme()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<MathFeedback | null>(null)
  const [feedbackSeedIndex, setFeedbackSeedIndex] = useState(0)
  const [hasConfirmedFeedback, setHasConfirmedFeedback] = useState(false)
  const [practiceOffset, setPracticeOffset] = useState(1)
  const [practiceProblem, setPracticeProblem] = useState<PracticeProblem | null>(null)
  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

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
  }

  const processUploadedFile = async (file: File) => {
    setSelectedFile(file)
    resetFeedbackFlow()
    setIsGenerating(true)
    setUploadError(null)

    const formData = new FormData()
    formData.append('pdf', file)

    try {
      const response = await fetch(`${apiBaseUrl}/api/analyze-pdf`, {
        method: 'POST',
        body: formData,
      })

      const body = await response.json().catch(() => null)
      if (!response.ok) {
        const errorDetail =
          body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
            ? body.detail
            : 'Failed to analyze PDF.'
        throw new Error(errorDetail)
      }

      if (!body || typeof body !== 'object' || !('feedback' in body)) {
        throw new Error('Backend response was missing feedback data.')
      }

      const fallbackSeed = getMockMathFeedback(file.name)
      setFeedback(body.feedback as MathFeedback)
      setFeedbackSeedIndex(fallbackSeed.seedIndex)
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Unexpected error while analyzing PDF.')
      setFeedback(null)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    const input = event.target

    if (!file) {
      return
    }

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a PDF file.')
      input.value = ''
      return
    }

    await processUploadedFile(file)
    input.value = ''
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
            step-by-step solution feedback.
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

        {isGenerating ? (
          <p className="loading-text">Analyzing your solution steps...</p>
        ) : feedback ? (
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
        ) : uploadError ? (
          <p className="loading-text">{uploadError}</p>
        ) : (
          <p className="loading-text">Upload a PDF to generate feedback.</p>
        )}
      </section>
    </main>
  )
}

export default App
