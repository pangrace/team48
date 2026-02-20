import { useMemo, useState, type CSSProperties } from "react";
import "./App.css";
import { useTheme } from "./context/themeContext";

type StepFeedback = {
  id: string;
  studentStep: string;
  status: "correct" | "incorrect";
  whatWentWrong: string;
  howToFix: string;
};

type MathFeedback = {
  problemTitle: string;
  problemPrompt: string;
  personalizedSummary: string;
  score: number;
  totalPoints: number;
  steps: StepFeedback[];
};

type NextProblem = {
  question: string;
  solution: string;
  common_pitfall: string;
};

type InitialFeedbackResponse = {
  feedback: MathFeedback;
};

type NextProblemResponse = {
  nextProblem: NextProblem;
};

function App() {
  const { theme } = useTheme();
  const [studentInitialFile, setStudentInitialFile] = useState<File | null>(
    null,
  );
  const [instructorFile, setInstructorFile] = useState<File | null>(null);
  const [practiceStudentFile, setPracticeStudentFile] = useState<File | null>(
    null,
  );
  const [isLoadingInitial, setIsLoadingInitial] = useState(false);
  const [isLoadingNextProblem, setIsLoadingNextProblem] = useState(false);
  const [isLoadingPractice, setIsLoadingPractice] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [professorNotice, setProfessorNotice] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<MathFeedback | null>(null);
  const [nextProblem, setNextProblem] = useState<NextProblem | null>(null);
  const [hasInitialRun, setHasInitialRun] = useState(false);
  const [hasSubmittedPractice, setHasSubmittedPractice] = useState(false);
  const apiBaseUrl = (
    import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
  ).replace(/\/$/, "");

  const appStyle = useMemo(
    () =>
      ({
        "--app-bg": theme.colors.background,
        "--theme-text": theme.colors.text,
        "--theme-primary": theme.colors.primary,
        "--theme-secondary": theme.colors.secondary,
        "--theme-ternary": theme.colors.ternary,
        "--theme-error": theme.colors.error,
      }) as CSSProperties,
    [theme],
  );

  const parseErrorDetail = (body: unknown): string => {
    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return body.detail;
    }
    return "Request failed.";
  };

  const handlePdfSelection = (
    event: React.ChangeEvent<HTMLInputElement>,
    setter: React.Dispatch<React.SetStateAction<File | null>>,
  ) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!file) return;
    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      alert("Please upload a PDF file.");
      return;
    }
    setter(file);
    setUploadError(null);
  };

  const handleInitialSubmit = async () => {
    if (!studentInitialFile || !instructorFile) {
      setUploadError("Upload both student and instructor PDFs first.");
      return;
    }

    setIsLoadingInitial(true);
    setUploadError(null);
    setProfessorNotice(null);
    const formData = new FormData();
    formData.append("student_pdf", studentInitialFile);
    formData.append("instructor_pdf", instructorFile);

    try {
      const response = await fetch(`${apiBaseUrl}/api/initial-feedback`, {
        method: "POST",
        body: formData,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(parseErrorDetail(body));
      if (!body || typeof body !== "object" || !("feedback" in body)) {
        throw new Error(
          "Backend returned incomplete initial feedback response.",
        );
      }

      const initialBody = body as InitialFeedbackResponse;
      setFeedback(initialBody.feedback);
      setNextProblem(null);
      setHasInitialRun(true);
      setHasSubmittedPractice(false);
      setPracticeStudentFile(null);

      setIsLoadingNextProblem(true);
      const nextFormData = new FormData();
      nextFormData.append("student_pdf", studentInitialFile);
      nextFormData.append("instructor_pdf", instructorFile);
      nextFormData.append(
        "comparison_summary",
        initialBody.feedback.personalizedSummary,
      );

      const nextProblemResponse = await fetch(
        `${apiBaseUrl}/api/initial-next-problem`,
        {
          method: "POST",
          body: nextFormData,
        },
      );
      const nextProblemBody = await nextProblemResponse
        .json()
        .catch(() => null);
      if (!nextProblemResponse.ok)
        throw new Error(parseErrorDetail(nextProblemBody));
      if (
        !nextProblemBody ||
        typeof nextProblemBody !== "object" ||
        !("nextProblem" in nextProblemBody)
      ) {
        throw new Error("Backend returned incomplete next problem response.");
      }
      setNextProblem((nextProblemBody as NextProblemResponse).nextProblem);
    } catch (error) {
      setUploadError(
        error instanceof Error
          ? error.message
          : "Unexpected error during initial comparison.",
      );
    } finally {
      setIsLoadingInitial(false);
      setIsLoadingNextProblem(false);
    }
  };

  const handlePracticeSubmit = async () => {
    if (!practiceStudentFile) {
      setUploadError("Upload the student practice solution PDF first.");
      return;
    }
    if (!nextProblem || !nextProblem.question || !nextProblem.solution) {
      setUploadError("Missing next problem context from backend.");
      return;
    }

    setIsLoadingPractice(true);
    setUploadError(null);
    const formData = new FormData();
    formData.append("student_pdf", practiceStudentFile);
    formData.append("question", nextProblem.question);
    formData.append("solution", nextProblem.solution);
    formData.append("common_pitfall", nextProblem.common_pitfall ?? "");

    try {
      const response = await fetch(`${apiBaseUrl}/api/practice-feedback`, {
        method: "POST",
        body: formData,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(parseErrorDetail(body));
      if (
        !body ||
        typeof body !== "object" ||
        !("feedback" in body) ||
        !("nextProblem" in body)
      ) {
        throw new Error(
          "Backend returned incomplete practice feedback response.",
        );
      }
      const practiceFeedback = body.feedback as MathFeedback;
      setFeedback(practiceFeedback);
      setPracticeStudentFile(null);
      setHasSubmittedPractice(true);

      const hasIncorrectStep = practiceFeedback.steps.some(
        (step) => step.status === "incorrect",
      );
      const scoreBelowPerfect =
        practiceFeedback.score < practiceFeedback.totalPoints;
      if (hasIncorrectStep || scoreBelowPerfect) {
        const notice =
          "Practice attempt flagged. Professor has been notified to review this submission.";
        setProfessorNotice(notice);
        console.info(notice);
      } else {
        setProfessorNotice(null);
      }
    } catch (error) {
      setUploadError(
        error instanceof Error
          ? error.message
          : "Unexpected error during practice feedback.",
      );
    } finally {
      setIsLoadingPractice(false);
    }
  };

  return (
    <main className="homework-app solution-mode" style={appStyle}>
      <section
        className="panel solution-page"
        aria-label="PDF feedback workflow"
      >
        <header className="solution-head">
          <div>
            <p className="eyebrow">AI Feedback Assistant</p>
            <h2>Loop Learn AI</h2>
            <p className="file-meta">
              Upload student and instructor PDFs to start.
            </p>
          </div>
        </header>

        <div className="feedback-content">
          <div className="next-problem">
            <h3>Step 1: Initial Comparison Inputs</h3>
            <p>
              <strong>Student solution PDF:</strong>{" "}
              {studentInitialFile ? studentInitialFile.name : "Not selected"}
            </p>
            <input
              type="file"
              accept=".pdf,application/pdf"
              onChange={(event) =>
                handlePdfSelection(event, setStudentInitialFile)
              }
            />
            <p>
              <strong>Instructor solution PDF:</strong>{" "}
              {instructorFile ? instructorFile.name : "Not selected"}
            </p>
            <input
              type="file"
              accept=".pdf,application/pdf"
              onChange={(event) => handlePdfSelection(event, setInstructorFile)}
            />
            <button
              type="button"
              className="primary-button"
              onClick={handleInitialSubmit}
              disabled={isLoadingInitial || isLoadingNextProblem}
            >
              {isLoadingInitial
                ? "Generating initial feedback..."
                : "Generate Initial Feedback"}
            </button>
          </div>

          {isLoadingInitial && !feedback ? (
            <div className="spinner-wrap" role="status" aria-live="polite">
              <div className="spinner" />
              <p>Generating initial feedback...</p>
            </div>
          ) : null}

          {feedback ? (
            <>
              <p className="summary">{feedback.personalizedSummary}</p>
              <div className="steps-block" aria-live="polite">
                <h3>Step-by-Step Feedback</h3>
                {feedback.steps.map((step, index) => (
                  <article className="step-card" key={step.id}>
                    <div className="step-head">
                      <p>Step {index + 1}</p>
                      <span className={`status-pill ${step.status}`}>
                        {step.status === "correct" ? "Correct" : "Needs Fix"}
                      </span>
                    </div>
                    <p className="step-work">
                      Student wrote: {step.studentStep}
                    </p>
                    <p>
                      <strong>Where it went wrong:</strong> {step.whatWentWrong}
                    </p>
                    <p>
                      <strong>How to fix:</strong> {step.howToFix}
                    </p>
                  </article>
                ))}
              </div>
            </>
          ) : null}

          {hasInitialRun && nextProblem ? (
            <div className="next-problem">
              <h3>Step 2: New Question For Student</h3>
              <p>{nextProblem.question || "No question returned."}</p>
              <p>
                <strong>Pitfall to avoid:</strong>{" "}
                {nextProblem.common_pitfall || "N/A"}
              </p>
              {!hasSubmittedPractice ? (
                <>
                  <p>
                    <strong>Student practice PDF:</strong>{" "}
                    {practiceStudentFile
                      ? practiceStudentFile.name
                      : "Not selected"}
                  </p>
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={(event) =>
                      handlePdfSelection(event, setPracticeStudentFile)
                    }
                  />
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={handlePracticeSubmit}
                    disabled={isLoadingPractice}
                  >
                    {isLoadingPractice
                      ? "Processing..."
                      : "Submit Practice Attempt For Feedback"}
                  </button>
                </>
              ) : (
                <p>
                  Practice question already submitted. Review feedback above.
                </p>
              )}
              {isLoadingPractice && !professorNotice ? (
                <div className="spinner-wrap" role="status" aria-live="polite">
                  <div className="spinner" />
                  <p>Generating practice feedback...</p>
                </div>
              ) : null}
            </div>
          ) : null}

          {isLoadingNextProblem ? (
            <div className="spinner-wrap" role="status" aria-live="polite">
              <div className="spinner" />
              <p>Generating your next practice problem...</p>
            </div>
          ) : null}

          {professorNotice ? (
            <p className="professor-notice">{professorNotice}</p>
          ) : null}

          {uploadError ? <p className="loading-text">{uploadError}</p> : null}
        </div>
      </section>
    </main>
  );
}

export default App;
